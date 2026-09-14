# Dependency graph
Full edge list; prerequisite → consumer. Manifest is authoritative.
| Consumer | Direct prerequisites |
|---|---|
| BASE-01 | None |
| BASE-02 | BASE-01 |
| BASE-03 | BASE-01 |
| BASE-04 | BASE-01 |
| BASE-05 | BASE-02, BASE-03, BASE-04 |
| BASE-06 | BASE-05 |
| DATA-01 | BASE-01 |
| DATA-02 | DATA-01 |
| DATA-03 | DATA-02 |
| DATA-04 | DATA-03 |
| DATA-05 | DATA-02 |
| UNIV-01 | DATA-04, DATA-05 |
| BAR-01 | DATA-04, DATA-05 |
| DATA-06 | BASE-06, UNIV-01, BAR-01 |
| FEAT-01 | DATA-06 |
| FEAT-02 | FEAT-01 |
| FEAT-03 | FEAT-01 |
| FEAT-04 | FEAT-02, FEAT-03 |
| COST-01 | DATA-01 |
| LED-01 | COST-01, BASE-04 |
| SIM-01 | COST-01, BAR-01 |
| SIM-02 | LED-01, SIM-01 |
| SIM-03 | SIM-02, DATA-06 |
| SIM-04 | SIM-03 |
| LABEL-01 | FEAT-04, SIM-01 |
| LABEL-02 | LABEL-01 |
| SPLIT-01 | LABEL-02 |
| TRAIN-01 | SPLIT-01, FEAT-04 |
| STRAT-01 | SIM-03, FEAT-04 |
| C01-01 | STRAT-01 |
| C07-01 | STRAT-01 |
| C02-01 | STRAT-01 |
| C03-01 | STRAT-01 |
| C04-01 | STRAT-01 |
| C10-01 | C01-01, C07-01 |
| S01-01 | STRAT-01 |
| S02-01 | STRAT-01 |
| C05-01 | STRAT-01 |
| C06-01 | STRAT-01 |
| C08-01 | STRAT-01 |
| C09-01 | STRAT-01 |
| C11-01 | STRAT-01 |
| C12-01 | C04-01 |
| S03-01 | STRAT-01 |
| S04-01 | STRAT-01, LOB-01 |
| S05-01 | STRAT-01 |
| S06-01 | STRAT-01 |
| S07-01 | C04-01, S01-01 |
| S08-01 | STRAT-01, LOB-01 |
| S09-01 | STRAT-01 |
| EVAL-01 | SIM-04 |
| EVAL-02 | EVAL-01 |
| EVAL-03 | EVAL-02, SPLIT-01 |
| ML-01 | TRAIN-01 |
| ML-02 | ML-01, SIM-01 |
| ML-03 | ML-02, EVAL-01 |
| M01-01 | ML-03 |
| M02-01 | ML-03, M01-01 |
| ML-04 | M01-01, M02-01, EVAL-03 |
| JOB-01 | EVAL-01 |
| JOB-02 | JOB-01 |
| JOB-03 | JOB-02, EVAL-03, ML-04 |
| SHADOW-01 | EVAL-03, ML-04, DATA-05 |
| SHADOW-02 | SHADOW-01, SIM-02 |
| SHADOW-03 | SHADOW-02, EVAL-03 |
| QA-01 | JOB-03, SHADOW-02, C01-01, C02-01, C03-01, C04-01, C07-01, C10-01, S01-01, S02-01, ML-04 |
| DL-01 | QA-01, JOB-02 |
| D01-01 | DL-01 |
| DL-02 | DL-01 |
| D02-01 | D01-01, DL-02 |
| D03-01 | D02-01, LABEL-02 |
| D04-01 | D02-01 |
| G01-01 | D01-01, C04-01 |
| F01-01 | DL-01 |
| F01-02 | F01-01, D01-01 |
| LOB-01 | DATA-06, FEAT-04 |
| L01-01 | LOB-01, D01-01 |
| L02-01 | L01-01 |
| M03-01 | ML-04 |
| M04-01 | ML-04 |
| M05-01 | ML-04, C01-01 |
| M06-01 | ML-04 |
| R01-01 | QA-01, SHADOW-02 |
| OPS-01 | JOB-02, SHADOW-02 |
| OPS-02 | DATA-06, JOB-01 |
| OPS-03 | OPS-02, EVAL-01 |
| REPORT-01 | EVAL-03, SIM-04 |
| REPORT-02 | REPORT-01, SHADOW-02 |
| AGENT-01 | REPORT-01, JOB-03 |
| QA-02 | REPORT-02, AGENT-01, OPS-02 |
| QA-03 | OPS-01, OPS-03, QA-01 |
| REL-01 | QA-02, QA-03, QA-01, REPORT-02 |

## Selected critical boundaries

```mermaid
flowchart TD
  FEAT_04["FEAT-04 features"] --> LABEL_01["LABEL-01 net return"]
  SIM_01["SIM-01 execution"] --> LABEL_01
  LABEL_01 --> LABEL_02["LABEL-02 barriers"]
  LABEL_02 --> SPLIT_01["SPLIT-01 folds"]
```

```mermaid
flowchart TD
  SHADOW_01["SHADOW-01 decisions"] --> SHADOW_02["SHADOW-02 shared ledger"]
  SIM_02["SIM-02 risk"] --> SHADOW_02
  SHADOW_02 --> SHADOW_03["SHADOW-03 replacement"]
  EVAL_03["EVAL-03 sealed lifecycle"] --> SHADOW_03
```

Nodes: 92. Edges: 153. Cycles must equal 0; enforced by validator.
