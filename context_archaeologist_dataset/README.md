# Context Archaeologist — Northstar Synthetic Archive

## Package contents
- `documents/`: 12 application-facing Markdown/TXT workplace records.
- `metadata/document_manifest.json`: public document metadata and passage IDs.
- `metadata/passage_index.json`: optional paragraph-level index with short excerpts.
- `metadata/claim_evidence_map.json`: developer/evaluation-only claim graph; **do not expose to the live agent**.
- `evaluation/`: 10 investigation scenarios, expected outcomes, and scoring rubric; **evaluation only**.
- `ground_truth/`: hidden fictional timeline and generation notes; **never ingest into live retrieval**.
- `scripts/validate_dataset.py`: structural and evidence-reference checks.
- `validation_report.json`: result of package validation.

## Quick start
Unzip the package. Point the Streamlit app's document loader at `documents/`. Load `metadata/document_manifest.json` for IDs, document types, dates, status, and authority hints. Optionally use `metadata/passage_index.json` to map paragraph-level citations.

## Citation convention
- Document ID: `DOC-NNN`
- Passage ID: `DOC-NNN-PNN`
- A final answer should cite a filename and passage ID, with a short excerpt when practical.
- Passage IDs follow blank-line-separated blocks in the source document, starting at `P01`. Headings and metadata blocks are passages too.

## Suggested minimal public manifest contract
Each `documents[]` entry includes `id`, `filename`, `title`, `type`, `author`, `created`, `updated`, `version`, `status`, `authority`, `path`, `format`, and `passage_ids`. The schema is intentionally plain JSON.

## Suggested retrieval workflow
1. Search documents for the user's question.
2. Retrieve relevant passages and identify dates, document status, and domain authority.
3. If a record references a decision, dependency, or approval, perform a second retrieval for that linked record.
4. Compare claims using temporal precedence and document status, not recency alone.
5. Validate every citation against the passage index.
6. If the necessary evidence is absent, state the limitation and abstain from unsupported conclusions.

## Evaluation isolation
The live application should not load `evaluation/`, `ground_truth/`, or `metadata/claim_evidence_map.json`. Use those only from a separate evaluator or developer workflow.

## Fictional-data notice
All entities and records are synthetic and created solely for demonstration and testing.
