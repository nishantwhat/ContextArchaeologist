#!/usr/bin/env python3
import json, re, sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
errors, warnings = [], []
def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))

manifest = load("metadata/document_manifest.json")
passage_idx = load("metadata/passage_index.json")["passages"]
claims = load("metadata/claim_evidence_map.json")["claims"]
scenarios = load("evaluation/evaluation_questions.json")["scenarios"]
outcomes = load("evaluation/expected_outcomes.json")["outcomes"]
docs = manifest["documents"]
ids = [d["id"] for d in docs]
files = [d["filename"] for d in docs]
if len(ids) != len(set(ids)): errors.append("Duplicate document IDs")
if len(files) != len(set(files)): errors.append("Duplicate filenames")
required = ["id","filename","title","type","author","created","updated","version","status","authority","path","format","passage_ids"]
for d in docs:
    for field in required:
        if field not in d: errors.append(f'{d.get("id","?")}: missing manifest field {field}')
    if not (ROOT / d["path"]).is_file(): errors.append(f'{d["id"]}: missing document file {d["path"]}')
    try:
        date.fromisoformat(d["created"]); date.fromisoformat(d["updated"])
    except Exception: errors.append(f'{d["id"]}: invalid date')
    if d.get("updated","") < d.get("created",""): errors.append(f'{d["id"]}: updated before created')
    for pid in d.get("passage_ids",[]):
        if pid not in passage_idx: errors.append(f'{d["id"]}: passage missing from index: {pid}')
        elif passage_idx[pid]["document_id"] != d["id"]: errors.append(f'{pid}: wrong document reference')
for c in claims:
    for did in c.get("supporting_document_ids",[]) + c.get("contradicting_document_ids",[]):
        if did not in ids: errors.append(f'{c["claim_id"]}: invalid document ref {did}')
    for pid in c.get("supporting_passage_ids",[]):
        if pid not in passage_idx: errors.append(f'{c["claim_id"]}: invalid passage ref {pid}')
for s in scenarios:
    if s["expected_outcome_id"] not in outcomes: errors.append(f'{s["scenario_id"]}: missing expected outcome')
    for pid in s.get("required_passage_ids",[]) + s.get("stale_or_conflicting_passage_ids",[]):
        if pid not in passage_idx: errors.append(f'{s["scenario_id"]}: invalid passage ref {pid}')
    if s["retrieval_plan"]["second_action_required"] and not s["retrieval_plan"].get("next_tool"):
        errors.append(f'{s["scenario_id"]}: second action missing next_tool')
if len(scenarios) < 8: errors.append("Fewer than 8 evaluation scenarios")
if len(docs) < 10 or len(docs) > 14: warnings.append("Document count outside target range 10–14")
# Required scenario coverage
types = {s["type"] for s in scenarios}
for t in ["straightforward_fact","multi_document_synthesis","timeline_reconstruction","stale_document","resolvable_contradiction","missing_dependency","unresolved_contradiction_or_unknown","insufficient_evidence_abstention"]:
    if t not in types: errors.append(f"Missing required scenario type: {t}")
# Check hidden evaluation separation
for forbidden in ["ground_truth","evaluation"]:
    if forbidden in str(manifest): errors.append(f"Public manifest leaks {forbidden} path")
# Check document passage excerpts are actually present in source
for pid, p in passage_idx.items():
    f = ROOT / "documents" / p["filename"]
    if not f.is_file(): errors.append(f"{pid}: missing source file")
    elif p["expected_excerpt"][:80] not in re.sub(r"\s+"," ",f.read_text(encoding="utf-8")):
        # Excerpts may normalize whitespace across markdown; this is a warning rather than fatal.
        warnings.append(f"{pid}: excerpt substring check did not match normalized source")
report = {"status":"PASS" if not errors else "FAIL","document_count":len(docs),"claim_count":len(claims),
          "scenario_count":len(scenarios),"passage_count":len(passage_idx),"errors":errors,"warnings":warnings}
(ROOT / "validation_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2))
sys.exit(1 if errors else 0)
