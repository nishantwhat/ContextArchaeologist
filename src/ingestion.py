"""Document Ingestion and Indexing Engine for Context Archaeologist.

Ingests application-facing documents and public manifests from
context_archaeologist_dataset. Does NOT touch ground_truth or evaluation folders.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DocumentMetadata:
    id: str
    filename: str
    title: str
    type: str
    author: str
    created: str
    updated: str
    version: str
    status: str
    authority: str
    path: str
    format: str
    passage_ids: List[str] = field(default_factory=list)


@dataclass
class PassageRecord:
    passage_id: str
    document_id: str
    filename: str
    section: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentArchive:
    """Manages the ingested corporate archive, metadata, and passage search index."""

    def __init__(self, dataset_dir: Path | str):
        self.dataset_dir = Path(dataset_dir).resolve()
        self.documents_dir = self.dataset_dir / "documents"
        self.manifest_path = self.dataset_dir / "metadata" / "document_manifest.json"
        self.passage_index_path = self.dataset_dir / "metadata" / "passage_index.json"

        self.documents: Dict[str, DocumentMetadata] = {}
        self.doc_texts: Dict[str, str] = {}
        self.passages: Dict[str, PassageRecord] = {}

        self._load_archive()

    def _load_archive(self) -> None:
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

        passage_idx_data: Dict[str, Any] = {}
        if self.passage_index_path.exists():
            with open(self.passage_index_path, "r", encoding="utf-8") as f:
                passage_idx_data = json.load(f).get("passages", {})

        for doc_entry in manifest_data.get("documents", []):
            doc_id = doc_entry["id"]
            meta = DocumentMetadata(
                id=doc_id,
                filename=doc_entry.get("filename", ""),
                title=doc_entry.get("title", ""),
                type=doc_entry.get("type", ""),
                author=doc_entry.get("author", ""),
                created=doc_entry.get("created", ""),
                updated=doc_entry.get("updated", ""),
                version=doc_entry.get("version", ""),
                status=doc_entry.get("status", ""),
                authority=doc_entry.get("authority", ""),
                path=doc_entry.get("path", ""),
                format=doc_entry.get("format", "markdown"),
                passage_ids=doc_entry.get("passage_ids", []),
            )
            self.documents[doc_id] = meta

            # Read raw document file
            file_path = self.dataset_dir / meta.path
            if not file_path.exists():
                file_path = self.documents_dir / meta.filename

            raw_text = ""
            if file_path.exists():
                raw_text = file_path.read_text(encoding="utf-8")
            self.doc_texts[doc_id] = raw_text

            # Parse passages if not already detailed, or align with passage index
            blocks = [b.strip() for b in re.split(r"\n\s*\n", raw_text) if b.strip()]
            for idx, pid in enumerate(meta.passage_ids):
                block_content = blocks[idx] if idx < len(blocks) else ""
                expected = passage_idx_data.get(pid, {})
                section_name = expected.get("section", f"Section {idx+1}")
                if not block_content and "expected_excerpt" in expected:
                    block_content = expected["expected_excerpt"]

                self.passages[pid] = PassageRecord(
                    passage_id=pid,
                    document_id=doc_id,
                    filename=meta.filename,
                    section=section_name,
                    content=block_content,
                    metadata={
                        "title": meta.title,
                        "created": meta.created,
                        "updated": meta.updated,
                        "version": meta.version,
                        "status": meta.status,
                        "authority": meta.authority,
                        "author": meta.author,
                        "type": meta.type,
                    },
                )

    def get_document(self, doc_id: str) -> Optional[DocumentMetadata]:
        return self.documents.get(doc_id)

    def get_document_content(self, doc_id: str) -> str:
        return self.doc_texts.get(doc_id, "")

    def get_passage(self, passage_id: str) -> Optional[PassageRecord]:
        return self.passages.get(passage_id)

    def list_all_documents(self) -> List[DocumentMetadata]:
        return sorted(list(self.documents.values()), key=lambda d: d.created)

    def validate_citation(self, citation_id: str) -> bool:
        """Checks if citation_id (DOC-XXX or DOC-XXX-PXX) exists in the archive."""
        citation_id = citation_id.strip()
        if citation_id in self.passages:
            return True
        if citation_id in self.documents:
            return True
        return False
