"""Tools available to the Context Archaeologist Agent.

Real callable Python tools:
1. search_archive(query, limit, filters) - Lexical and passage similarity search
2. get_document_details(doc_id) - Read full document content and metadata
3. get_passage_details(passage_id) - Read targeted excerpt and section
4. follow_references(doc_id) - Find forward and backward document references
5. inspect_timeline(topic) - Chronological listing of documents & decisions
6. validate_citations(citations) - Ensure citations accurately map to real records
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from rapidfuzz import fuzz

from src.ingestion import DocumentArchive, PassageRecord


class ToolRegistry:
    def __init__(self, archive: DocumentArchive):
        self.archive = archive

    def search_archive(
        self, query: str, limit: int = 5, doc_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search the document archive across passage contents, titles, and sections.

        Returns ranked passage matches with metadata, score, and citation ID.
        """
        results = []
        q_clean = query.lower().strip()
        q_tokens = set(re.findall(r"\w+", q_clean))

        for pid, passage in self.archive.passages.items():
            meta = passage.metadata
            if doc_type and meta.get("type") != doc_type:
                continue

            content_lower = passage.content.lower()
            title_lower = meta.get("title", "").lower()
            section_lower = passage.section.lower()

            # Rapidfuzz partial ratio on content and section
            content_score = fuzz.partial_ratio(q_clean, content_lower)
            title_score = fuzz.partial_ratio(q_clean, title_lower)

            # Token overlap score
            matched_tokens = sum(1 for tok in q_tokens if tok in content_lower or tok in title_lower)
            token_ratio = (matched_tokens / len(q_tokens)) if q_tokens else 0.0

            # Boost if query mentions doc_id directly
            direct_id_boost = 30.0 if (passage.document_id.lower() in q_clean or pid.lower() in q_clean) else 0.0

            # Combined heuristic score
            final_score = (content_score * 0.45) + (title_score * 0.25) + (token_ratio * 30.0) + direct_id_boost

            if final_score > 35.0 or direct_id_boost > 0:
                results.append(
                    {
                        "passage_id": pid,
                        "document_id": passage.document_id,
                        "filename": passage.filename,
                        "title": meta.get("title", ""),
                        "created": meta.get("created", ""),
                        "status": meta.get("status", ""),
                        "authority": meta.get("authority", ""),
                        "section": passage.section,
                        "excerpt": passage.content[:600] + ("..." if len(passage.content) > 600 else ""),
                        "score": round(final_score, 2),
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def get_document_details(self, doc_id: str) -> Dict[str, Any]:
        """Fetch complete document metadata, status, date, and full text content."""
        doc = self.archive.get_document(doc_id)
        if not doc:
            return {"error": f"Document ID '{doc_id}' not found in archive."}

        content = self.archive.get_document_content(doc_id)
        return {
            "id": doc.id,
            "filename": doc.filename,
            "title": doc.title,
            "type": doc.type,
            "author": doc.author,
            "created": doc.created,
            "updated": doc.updated,
            "version": doc.version,
            "status": doc.status,
            "authority": doc.authority,
            "passage_ids": doc.passage_ids,
            "content": content,
        }

    def get_passage_details(self, passage_id: str) -> Dict[str, Any]:
        """Fetch the exact text and metadata for a specific passage ID."""
        p = self.archive.get_passage(passage_id)
        if not p:
            return {"error": f"Passage '{passage_id}' not found."}
        return {
            "passage_id": p.passage_id,
            "document_id": p.document_id,
            "filename": p.filename,
            "section": p.section,
            "content": p.content,
            "metadata": p.metadata,
        }

    def follow_references(self, doc_id: str) -> Dict[str, Any]:
        """Extract explicit cross-document references (e.g. DOC-003, DOC-008) mentioned in a document.

        Also finds any documents that cite this document back.
        """
        content = self.archive.get_document_content(doc_id)
        if not content:
            return {"error": f"Document {doc_id} has no content."}

        # Find mentioned DOC-XXX
        mentioned_raw = set(re.findall(r"DOC-\d{3}", content))
        mentioned = [d for d in mentioned_raw if d != doc_id and d in self.archive.documents]

        # Reverse references: who mentions doc_id?
        referenced_by = []
        for other_id, other_content in self.archive.doc_texts.items():
            if other_id != doc_id and doc_id in other_content:
                referenced_by.append(other_id)

        return {
            "document_id": doc_id,
            "explicit_outgoing_references": sorted(mentioned),
            "referenced_by_incoming": sorted(referenced_by),
        }

    def inspect_timeline(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return documents sorted chronologically by creation date, with status and authority."""
        docs = self.archive.list_all_documents()
        timeline = []
        for d in docs:
            timeline.append(
                {
                    "date": d.created,
                    "updated": d.updated,
                    "document_id": d.id,
                    "title": d.title,
                    "status": d.status,
                    "authority": d.authority,
                    "author": d.author,
                    "type": d.type,
                }
            )
        return timeline

    def validate_citations(self, citations: List[str]) -> Dict[str, Any]:
        """Validate an agent's cited passage or document IDs against the verified index."""
        valid = []
        invalid = []
        for c in citations:
            c_clean = c.strip()
            if self.archive.validate_citation(c_clean):
                valid.append(c_clean)
            else:
                invalid.append(c_clean)

        return {
            "valid_citations": valid,
            "invalid_citations": invalid,
            "all_valid": len(invalid) == 0,
        }
