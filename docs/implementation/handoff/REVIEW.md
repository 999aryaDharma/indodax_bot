# DOC-01 independent review

Status: CHANGES_REQUESTED; round 1 findings addressed in working tree, exact-SHA re-review pending. Maximum five rounds; no counter reset.

## Round 1

Independent reviewer: `/root/architecture_doc_review` (fresh-context GPT-6 Astra agent; not implementation owner).
Reviewed SHA: `fe9edc17c175f6179bfbb3b2d3b571adaaa9900c`.
Audit/base SHA: `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`.
Verdict: CHANGES_REQUESTED. Critical: 0; Important: 2; Minor: 3.

| Finding | Severity | Required correction | Owner response |
|---|---|---|---|
| R1 Historical experiment/candidate bootstrap cycle | Important | A first experiment must run before completed candidate evidence exists | RuntimePlan/VerifiedRuntimePlan contract; common load_plan evaluator; candidate adds reviewed evidence around same executed plan; RW0/RP2/RW3/RW4 acceptance extended |
| R2 Event recovery protocol undecided | Important | Choose full state/outbox/cursor protocol, including no-fill events | PREPARED/DECIDED/ATTEMPTING/ACKNOWLEDGED protocol with exact store methods, crash cases, delayed fills and PM-02/RP-04 ownership |
| R3 Result schemas missing | Minor | Define validity/provenance/error and result payloads | Shared response/metric/error envelopes plus task-owned report/result schemas in CONTRACTS |
| R4 Source hash representation ambiguous | Minor | Distinguish Git LF blob from Windows CRLF checkout | Both hashes explicitly labeled in MANIFEST-RECOVERY |
| R5 READY self-test depends on last row | Minor | Construct unmet dependency, independent of row ordering | Self-dependent READY mutation; BASE-01-last suite verified |

Reviewer commands: planning validator PASS (119 nodes/214 edges, 7/7 negative mutations); program validator PASS (27 tasks, 4/4 negative mutations at reviewed SHA); reversed-record suites PASS; premature RP-01 readiness rejected; BASE-01-last suite failed and reproduced R5; base-to-head diff check exit 0; product path diff empty. Environment Python 3.13.5/Windows. No product tests or live actions.

Declined-to-judge items: product-test correctness, live venue behavior, operational readiness, current fees/licenses/hardware, real-money activation. Coordinator ruling: these remain outside docs-only evidence and explicitly blocked for activation; local documentation checks must not be substituted for them.

## Fix verification

Added documentation-contract assertions first: program validator exit 1 with missing bootstrap, event protocol and result schema. After fixes: planning validator 7/7 negative cases PASS; program validator 6/6 PASS; BASE-01-last negative suite PASS; base-to-working-tree diff check clean. These are documentation/tool checks, not product behavioral tests.

No independent PASS is claimed until round 2 reviews the committed fixes.
