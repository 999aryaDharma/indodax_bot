# Sprint manifest recovery

Classification: FACT / DOCUMENTATION REPAIR. Date: 2026-09-21.

Source SHA: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`.
Corrupted Windows checkout bytes SHA-256 (CRLF working-tree representation): `1ace3784ec638263effb188955a42881b3a55874786760d6e51c101236791a51`.
The original logical source remains in Git at that SHA; its LF Git-blob SHA-256 is `acef546b4f8ed95816379b03dbe83358930454d8939e7d0537d9506fc7356713`. Checkout CRLF conversion explains the different byte digest. No runtime evidence was rewritten.

The source contained a literal truncation header and an internal truncation marker. All 18 available manifest revisions failed JSON parsing. 63 intact records were salvageable; all 92 sprint documents were used to reconstruct paths, readings, dependencies and acceptance behavior. User selected conservative reconstruction. Handoffs do not establish independent approval; later handoffs remain REVIEW. Status means delivery governance, not absent implementation. Legacy aliases in test mappings are retained as planned identities, not assertions that functions exist.

External gate metadata was retained from intact records; reconstructed records also inherit their sprint External gates and required-reading policies. No external gate is waived.

| Sprint | Spec status | Recovered status | Basis |
|---|---|---|---|
| AGENT-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| BAR-01 | DONE | DONE | Qualified historical import retained; no fresh test or reviewer claim. |
| BASE-01 | DONE | DONE | Qualified historical import retained; no fresh test or reviewer claim. |
| BASE-02 | DONE | DONE | Qualified historical import retained; no fresh test or reviewer claim. |
| BASE-03 | DONE | DONE | Qualified historical import retained; no fresh test or reviewer claim. |
| BASE-04 | DONE | DONE | Qualified historical import retained; no fresh test or reviewer claim. |
| BASE-05 | DONE | DONE | Qualified historical import retained; no fresh test or reviewer claim. |
| BASE-06 | DONE | DONE | Qualified historical import retained; no fresh test or reviewer claim. |
| D01-01 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| D02-01 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| D03-01 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| D04-01 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| DL-01 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| DL-02 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| F01-01 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| F01-02 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| G01-01 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| EVAL-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| EVAL-02 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| EVAL-03 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| FEAT-01 | READY | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| FEAT-02 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| FEAT-03 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| FEAT-04 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| LABEL-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| LABEL-02 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| SPLIT-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| TRAIN-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| DATA-01 | DONE | DONE | Qualified historical import retained; no fresh test or reviewer claim. |
| DATA-02 | DONE | DONE | Qualified historical import retained; no fresh test or reviewer claim. |
| DATA-03 | DONE | DONE | Qualified historical import retained; no fresh test or reviewer claim. |
| DATA-04 | DONE | DONE | Qualified historical import retained; no fresh test or reviewer claim. |
| DATA-05 | DONE | DONE | Qualified historical import retained; no fresh test or reviewer claim. |
| DATA-06 | DONE | DONE | Qualified historical import retained; no fresh test or reviewer claim. |
| L01-01 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| L02-01 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| LOB-01 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| M01-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| M02-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| M03-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| M04-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| M05-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| M06-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| ML-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| ML-02 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| ML-03 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| ML-04 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| R01-01 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| OPS-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| OPS-02 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| OPS-03 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| JOB-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| JOB-02 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| JOB-03 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| REPORT-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| REPORT-02 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| SHADOW-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| SHADOW-02 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| SHADOW-03 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| COST-01 | READY | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| LED-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| SIM-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| SIM-02 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| SIM-03 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| SIM-04 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| C01-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| C02-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| C03-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| C04-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| C05-01 | PLANNED | PLANNED | Sprint specification; no completion inferred. |
| C06-01 | PLANNED | PLANNED | Sprint specification; no completion inferred. |
| C07-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| C08-01 | PLANNED | PLANNED | Sprint specification; no completion inferred. |
| C09-01 | PLANNED | PLANNED | Sprint specification; no completion inferred. |
| C10-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| C11-01 | PLANNED | PLANNED | Sprint specification; no completion inferred. |
| C12-01 | PLANNED | PLANNED | Sprint specification; no completion inferred. |
| S01-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| S02-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| S03-01 | PLANNED | PLANNED | Sprint specification; no completion inferred. |
| S04-01 | PLANNED | PLANNED | Sprint specification; no completion inferred. |
| S05-01 | PLANNED | PLANNED | Sprint specification; no completion inferred. |
| S06-01 | PLANNED | PLANNED | Sprint specification; no completion inferred. |
| S07-01 | PLANNED | PLANNED | Sprint specification; no completion inferred. |
| S08-01 | PLANNED | PLANNED | Sprint specification; no completion inferred. |
| S09-01 | PLANNED | PLANNED | Sprint specification; no completion inferred. |
| STRAT-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| UNIV-01 | DONE | DONE | Qualified historical import retained; no fresh test or reviewer claim. |
| QA-01 | PLANNED | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| QA-02 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| QA-03 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
| REL-01 | REVIEW | REVIEW | Implementation handoff exists; independent PASS not established in this recovery. |
