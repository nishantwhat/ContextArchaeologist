# Engineering Dependency Update — Backup and Recovery

**Document ID:** DOC-004  
**Owner:** Dev Malik, Platform Engineering Lead  
**Created:** 2026-03-06 · **Updated:** 2026-03-10 · **Version:** 1.2

## Current state
The backup-policy configuration reached staging on 5 March. The first recovery rehearsal on 9 March restored the database but failed the team's timing objective: the restore took 74 minutes against a 60-minute objective.

The team has not yet recorded a passing rehearsal. A second rehearsal is planned after the index snapshot change is deployed; no completed result is attached to this report.

## Dependency chain
1. Deploy the index snapshot change to staging.
2. Run the recovery rehearsal and record elapsed time plus data-integrity checks.
3. Have Platform Engineering publish the run record.
4. Request Security review of the production configuration.

A successful rehearsal is evidence for the gate, but it is not itself Security approval.

## Clarification
The staging rollout is complete. The production recovery gate is **not** complete as of this update. “Backup policy deployed” must not be interpreted as “recovery approved.”

## Related records
DOC-002 records the original dependency. DOC-008 defines the later release gate.
