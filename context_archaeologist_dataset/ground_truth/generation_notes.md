# Generation Notes — Hidden Evaluation Material

This is a fully synthetic archive for the Context Archaeologist PoC. The organization, product, people, dates, and records are fictional.

## Core truth
- January baseline: 20 April 2026, explicitly a planning target.
- 18 February: target moved to 11 May, with gates unchanged.
- 2 April: Launch Council withdrew 11 May and made the date contingent on all four gates. No current launch date is authorized.
- As of 9 April, the archive does not evidence unconditional Product acceptance, a passing recovery rehearsal, Security production approval, or completed Customer Operations readiness.
- The second recovery attempt's outcome is deliberately unknown. The final run record is absent; neither pass nor fail is justified.
- Security's non-receipt of the access-control export is scoped to the review record. The archive cannot prove whether the artifact exists elsewhere.

## Authority model
Authority is domain-specific. DOC-008 controls launch policy/date authorization. DOC-004 controls engineering status. DOC-006 and DOC-011 control the recorded Security review state. DOC-007 is explicitly a draft. Recency alone is not sufficient.

## Leakage controls
Do not place this directory or the `evaluation/` directory in the live retrieval corpus. Only `documents/` and the public `metadata/document_manifest.json` (optionally `metadata/passage_index.json`) should be exposed to the application. `claim_evidence_map.json` is evaluation/developer material and should not be indexed by the live agent.

## Evaluation design
The scenarios test direct retrieval, corroboration, multi-hop retrieval, temporal precedence, stale-document handling, context-sensitive interpretation, and calibrated abstention. Observable checks are used instead of hidden chain-of-thought requirements.
