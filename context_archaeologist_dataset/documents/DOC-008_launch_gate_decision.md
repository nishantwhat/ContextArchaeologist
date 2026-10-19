# Launch Council Decision: Northstar Release Gate

**Document ID:** DOC-008  
**Decision date:** 2026-04-02  
**Issued by:** Mira Sen, Launch Council Chair  
**Version:** 1.0 · **Status:** Authoritative current decision

## Decision
The 11 May target in DOC-003 is withdrawn. The limited-cohort launch is moved to a **date to be confirmed after the release gates pass**. No calendar date is currently authorized.

This decision supersedes the schedule target in DOC-003 and any copied date in draft planning artifacts, including DOC-007.

## Mandatory release gates
Launch Council will authorize a date only after all of the following are recorded:
1. Product accepts the release candidate.
2. Platform Engineering records a successful recovery rehearsal, including elapsed time and data-integrity checks.
3. Security Engineering records production approval after reviewing the run record and final access-control export.
4. Customer Operations freezes the rota and approves the customer FAQ for external distribution.

A gate owner saying a task is “nearly done” does not satisfy the gate. All four conditions must be evidenced in the archive.

## Decision authority
This record is authoritative for the launch policy and date status. Technical evidence remains governed by the relevant functional records; this decision does not claim that the gates have passed.

## Review trigger
Program Management may request a new Launch Council decision only after the four gate records are assembled. Until then, report the launch date as **not yet authorized / to be confirmed**, not 11 May.
