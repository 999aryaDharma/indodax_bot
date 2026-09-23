# Indodax Systematic — Control Plane Design System

## 1. Product Identity

**Indodax Systematic** is an institutional-style systematic trading control plane composed of two clearly separated environments:

1. **Production**

   * operational monitoring
   * portfolio state
   * execution
   * OMS
   * risk
   * reconciliation
   * releases
   * incidents
   * infrastructure
   * audit

2. **Research Workbench**

   * datasets
   * strategies
   * fundamental/on-chain components
   * ML/DL models
   * pipelines
   * experiments
   * backtests
   * candidates
   * isolated shadow agents
   * tournament
   * portfolio shadow

The interface must make this distinction obvious at all times.

The frontend is a **control plane and observability surface**.

It never becomes the authoritative owner of:

* exchange balances
* orders
* fills
* OMS state
* ledger state
* positions
* risk truth
* reconciliation truth
* candidate identity
* release identity
* production authorization

Authoritative state comes from backend services.

The UI displays, explains, compares, investigates, and invokes guarded actions against those backend systems.

---

# 2. Design Character

The visual direction combines three reference qualities:

### Cloudflare

Use its qualities of:

* calm infrastructure-console shell
* excellent information density
* restrained navigation
* strong hierarchy
* useful tables
* good operational status presentation

Do not clone Cloudflare visually.

### Linear

Use its qualities of:

* typography
* spacing discipline
* polished interactions
* command palette
* drawers
* subtle transitions
* excellent dark UI refinement

### Grafana

Use its qualities of:

* observability hierarchy
* time-series presentation
* incident context
* logs
* filtering
* operational investigation

The resulting product should feel like:

> **A professional quantitative trading control plane and research operating system.**

It must not look like:

* Binance
* Bybit
* retail crypto dashboards
* meme trading applications
* neon fintech dashboards
* a generic admin template
* a wall of KPI cards
* a Bloomberg Terminal imitation

The application should feel credible after being open for **4–8 hours continuously**.

Healthy operation should visually feel boring.

Critical states should become impossible to miss.

---

# 3. Core Design Principles

## 3.1 Operational truth before decoration

The most important information is:

1. Can the system trade?
2. Is the system healthy?
3. Is market data healthy?
4. Is reconciliation healthy?
5. Are there UNKNOWN orders?
6. Is risk within limits?
7. Which immutable candidate and release are running?
8. Has anything unusual happened?

Those questions outrank decorative portfolio information.

---

## 3.2 Research flexibility, production rigidity

The two environments intentionally have different interaction philosophies.

### Research

Research is:

* composable
* exploratory
* customizable
* comparative
* experiment-oriented

Users may:

* select datasets
* select pairs
* change date ranges
* create strategies
* configure indicators
* configure fundamental factors
* train models
* combine TA + fundamental + ML/DL
* change thresholds
* clone experiments
* run backtests
* register candidates
* start shadow agents

### Production

Production is:

* immutable
* guarded
* deliberate
* review-driven
* observable rather than editable

Production must never visually encourage live tweaking.

Production candidate configuration is displayed as:

> immutable release state

rather than editable forms.

Changing production behavior means creating and qualifying a new candidate/release.

---

# 4. Global Application Architecture

Primary navigation:

```text
OVERVIEW

PRODUCTION
├── Operations
├── Portfolio
├── Positions
├── Orders
├── Risk
├── Reconciliation
├── Manual Approval
├── Releases
└── Incidents

RESEARCH
├── Workbench
├── Strategies
├── Models
├── Factors
├── Pipelines
├── Datasets
├── Experiments
├── Backtests
├── Candidates
├── Tournament
└── Portfolio Shadow

SYSTEM
├── Market Data
├── Venue
├── Infrastructure
├── Logs
├── Audit
└── Settings
```

Navigation should be grouped, not presented as one undifferentiated list.

Production and Research must remain visually distinguishable.

Use section headings and subtle separators rather than different visual themes.

---

# 5. Application Shell

## Desktop

Primary target:

* 1440px
* 1600px
* 1920px

Minimum serious workstation width:

* 1280px

Structure:

```text
┌──────────────────────────────────────────────────────────────┐
│ Sidebar │ Global Context / Safety / Operator                │
│         ├────────────────────────────────────────────────────┤
│         │                                                    │
│         │                Main Workspace                      │
│         │                                                    │
│         │                                                    │
└──────────────────────────────────────────────────────────────┘
```

### Sidebar

Expanded:

`232–248px`

Collapsed:

`56–64px`

The sidebar contains:

* product identity
* grouped navigation
* environment distinction
* system indicator summary
* operator/account area

Do not use oversized icons.

Do not turn every navigation item into a pill.

Selected navigation should be visible but understated.

---

## Global Context Bar

Height:

`44–52px`

Possible contents:

```text
BTC/IDR      WITA (UTC+8) 21:42:21

MODE
SHADOW

RECON
HEALTHY · 4s

UNKNOWN
0

OPERATOR
arya
```

Depending on the page, pair context may disappear when irrelevant.

Operational timestamps should be presented in the operator's configured display zone. The current operator display zone is `Asia/Makassar` (WITA, UTC+8); API and persisted timestamps remain timezone-aware UTC, and the UI converts only for display.

The context bar may also show:

* active release
* candidate
* venue
* data freshness
* current environment

It must remain compact.

---

# 6. Color System

The application uses a **soft graphite / charcoal dark palette**.

Dark does not mean pure black.

## Base

```text
Canvas                 #0D0F12
Sidebar                #0A0C0F
Surface                #13161B
Surface Raised         #181C22
Surface Hover          #1C2128
Surface Selected       #20262E
Border                 #292F38
Border Strong          #353C47
```

## Text

```text
Text Primary           #E7E9ED
Text Secondary         #A9AFB9
Text Muted             #7B838F
Text Disabled          #555D68
```

## Informational

```text
Blue                    #6EA8FE
Blue Muted              rgba(110,168,254,.12)

Indigo / Strategy       #918CD8
Indigo Muted            rgba(145,140,216,.12)
```

## Semantic

```text
Healthy Green           #63C18A
Warning Amber           #D7A85D
Critical Red            #D87979
Recovery Purple         #A58BD4
Unknown Gray            #8C95A3
```

Semantic colors must never become decorative branding colors.

Do not tint entire screens green because systems are healthy.

Do not render entire table rows red for ordinary errors.

Color communicates **meaning**, not excitement.

---

# 7. Environment Semantics

## Research

Research may use restrained indigo as its identity accent.

Examples:

```text
RESEARCH
Experiment
Candidate
Agent
Model
Pipeline
Dataset
```

Indigo identifies research entities.

It does not indicate system health.

---

## Production

Production does not receive a bright branding color.

Production is represented through:

* neutral graphite surfaces
* factual state
* operational status
* safety semantics

This helps prevent visual gamification of live trading.

---

# 8. Typography

Preferred:

* Geist
* Inter

Use one family consistently.

## Scale

```text
Page Title              22–26px
Page Subtitle           13–14px
Section Heading         14–16px
Body                    13–14px
Table                   12–13px
Metadata                11–12px
Badge                    11px
Metric Primary          20–28px
```

Avoid giant finance-dashboard typography.

A portfolio balance does not need 48px type.

Use:

```css
font-variant-numeric: tabular-nums;
```

for:

* prices
* balances
* timestamps
* percentages
* latency
* P&L
* drawdowns
* model scores

Financial and operational numbers should align visually.

---

# 9. Spacing and Density

Base spacing unit:

`4px`

Common spacing:

```text
4
8
12
16
20
24
32
```

Page padding:

`20–28px`

Panel gaps:

`12–16px`

Section separation:

`24–32px`

Dense data is encouraged.

Visual clutter is not.

---

# 10. Corner Radius

The UI should not look excessively soft.

Recommended:

```text
Small controls          4–6px
Inputs                   6px
Panels                   6–8px
Drawers                  8px
Modals                   8–10px
```

Avoid:

* 16–24px rounded cards
* pill everything
* oversized floating panels

---

# 11. Elevation

Use borders before shadows.

Primary separation tools:

1. background tone
2. border
3. spacing
4. typography

Shadows should be reserved for:

* dropdowns
* command palette
* dialogs
* floating popovers

Do not create card stacks using heavy box shadows.

---

# 12. Status Hierarchy

Operational status has strict visual priority.

Priority:

```text
1. CRITICAL
2. HALTED
3. UNKNOWN financial state
4. RECONCILIATION MISMATCH
5. CLOCK UNSAFE
6. MARKET DATA STALE
7. RISK BREACH
8. RECOVERY
9. WARNING
10. HEALTHY
```

A high-priority state must not be visually hidden by portfolio performance.

Example:

```text
SYSTEM HALTED
Reconciliation mismatch detected.

New order submissions are blocked.
Existing venue orders have not been modified.

Last healthy reconciliation:
13:41:14 UTC

[Inspect mismatch]
```

Never communicate a critical state using color alone.

Always combine:

* icon
* text
* label
* contextual explanation

---

# 13. Execution Modes

Supported production runtime modes:

```text
DISABLED
RECOVERY
READ_ONLY
SHADOW
MANUAL_APPROVAL
AUTONOMOUS_LIMITED
HALTED
```

Do not invent UI-only modes.

Mode transitions must reflect backend legal transitions.

The UI must not imply arbitrary switching.

Example mode badge:

```text
● SHADOW
```

Mode details may display:

```text
Orders submitted to venue      NO
Simulated fills                YES
Risk engine                    ACTIVE
Reconciliation                 ACTIVE
Candidate                      cand-btc-c07-042
```

---

# 14. Safety Banner

The application must have a global safety banner capable of appearing above page content.

Trigger examples:

* HALTED
* RECOVERY
* UNKNOWN OMS state
* reconciliation mismatch
* stale market data
* unsafe clock
* venue unavailable
* risk authority unavailable
* release verification failure

Example:

```text
HALTED

New order submission is blocked because the latest
reconciliation snapshot disagrees with venue state.

2 mismatches · detected 13:42:03 UTC

[Inspect Reconciliation]
```

Never add:

```text
Fix automatically
Sync balance
Force resolve
```

as casual primary actions.

---

# 15. Status Strip

Overview should include a compact infrastructure-style status strip.

Example:

```text
Execution Mode      SHADOW
Venue               HEALTHY
Market Data         HEALTHY · 1.2s
Reconciliation      HEALTHY · 4s
OMS UNKNOWN         0
Risk                HEALTHY
Release             VERIFIED
Backup              18m ago
```

This should answer system-health questions faster than a collection of cards.

---

# 16. Metrics

Portfolio summary metrics may include:

```text
Equity
Daily P&L
Exposure
Drawdown
Available Cash
Open Orders
```

Preferred layout:

```text
Equity              Rp102.43M
Daily P&L           +Rp430K
Exposure            23.4%
Drawdown            2.8%
Cash                Rp78.22M
Open Orders         3
```

Metrics should not dominate the screen.

The dashboard is about **operational control**, not celebrating returns.

---

# 17. Charts

Charts must support investigation.

Visual style:

* thin lines
* low-contrast grid
* restrained axes
* readable tooltips
* tabular numeric formatting
* minimal animation
* no glow
* no gradients for decoration
* no pseudo-3D

Use semantic overlays carefully.

---

## Equity Chart

May show:

* equity
* benchmark
* drawdown
* execution markers
* incidents
* release transitions

BTC price should not automatically become the dominant chart.

---

## Health Timeline

Display:

```text
Market
Venue
Reconciliation
OMS
Risk
Infrastructure
```

across time.

Useful for understanding whether:

> strategy losses occurred during a system incident

or:

> execution degraded independently from strategy performance.

---

# 18. Tables

Tables are first-class components.

Use them heavily.

Row height:

`30–38px`

Characteristics:

* sticky headers when useful
* numeric alignment
* compact filters
* sortable columns
* column visibility
* resizable columns where appropriate
* horizontal scrolling at smaller widths
* row selection only when meaningful
* details through drawer

Avoid giant row spacing.

---

## Order Table Example

```text
Time
Order ID
Pair
Side
Type
Qty
Price
Filled
State
Candidate
Agent
Mode
```

UNKNOWN state must be visually prominent.

Example:

```text
UNKNOWN
Venue truth unresolved
```

not merely an amber dot.

---

# 19. Detail Drawers

Use drawers instead of navigating away for investigative detail.

Example order drawer:

```text
ORDER #ORD-19402

Identity
├── OMS ID
├── Client Order ID
├── Venue Order ID
└── Correlation ID

Strategy
├── Agent
├── Candidate
├── Strategy
├── Model
└── Release

Decision Trace
├── Signal
├── Portfolio
├── Risk
├── OMS
├── Venue
└── Fill

Reconciliation

Raw Evidence

Audit Events
```

This should feel closer to infrastructure tracing than retail trading history.

---

# 20. Production Overview

The Production Overview must answer within approximately five seconds:

```text
Is the system healthy?

Can it currently submit orders?

What candidate is running?

What is portfolio exposure?

What is current risk?

Is reconciliation healthy?

Are UNKNOWN orders present?

Has anything unusual happened?
```

Recommended hierarchy:

```text
Safety / Critical Banner

System Status Strip

Portfolio + Risk Summary

Equity / P&L

Health Timeline

Positions

Orders

Recent Incidents / Audit Events
```

---

# 21. Portfolio

Portfolio pages should emphasize:

* authoritative balances
* positions
* exposure
* strategy attribution
* realized/unrealized P&L
* concentration
* limits

Do not make portfolio P&L visually resemble a retail exchange.

Strategy sleeves may appear for attribution.

Venue portfolio remains authoritative.

---

# 22. Reconciliation

Reconciliation is a major operational page.

Layout:

```text
RECONCILIATION

Last run          13:42:14 UTC
Age               4s
Status            HEALTHY

Internal          Venue          Difference
BTC               ...
IDR               ...
Orders            ...
Fills             ...
Positions         ...
```

When mismatch occurs:

```text
RECONCILIATION MISMATCH

New order submission blocked.
```

Action:

```text
Inspect Difference
```

Never:

```text
Fix Balance
```

---

# 23. Risk

Risk UI should expose:

* current limits
* utilization
* daily loss
* drawdown
* exposure
* concentration
* position limits
* throttle state
* kill switch
* unknown-order guard
* reconciliation guard

Example:

```text
Daily Loss
Rp430K / Rp4M
10.8%

Gross Exposure
23.4% / 40%

BTC Exposure
8.2% / 15%
```

Limit utilization is more useful than isolated numbers.

---

# 24. Kill Switch

Kill-switch state should be prominent when active.

Activation/reset are not symmetric casual toggles.

Reset must be a guarded workflow.

Possible confirmation sequence:

```text
Kill switch reset requested

Required evidence:
✓ Reconciliation healthy
✓ UNKNOWN orders = 0
✓ Market data healthy
✓ Risk state recovered

Operator
arya

Reason
[............................]

Type:
RESET KILL SWITCH

[Reset]
```

---

# 25. Manual Approval

Manual Approval must feel like an execution-control workflow, not a notification inbox.

List:

```text
Proposal
Pair
Side
Notional
Strategy
Candidate
Risk State
Expires
Status
```

Drawer:

```text
Proposal Identity
Signal Evidence
Current Portfolio
Current Risk
Current Market
Candidate Identity
Release Identity
Proposed Order
Expiry
```

Execution requires current backend validation.

The UI must clearly communicate:

> approval does not bypass current risk or reconciliation checks.

---

# 26. Release Page

Production releases are immutable operational artifacts.

Display:

```text
Release
prod-0.4.3

Git
c2567f5960

Candidate
cand-btc-c07-042

Strategy
C07 Mean Reversion v4

Model
M02-XGB-023

Feature Schema
fs-18

Risk Policy
risk-v12

Execution Policy
exec-v7

Bundle Digest
sha256:...

Verification
VERIFIED
```

Avoid implying cryptographic signatures if only integrity hashes exist.

Truthful wording is mandatory.

---

# 27. Readiness Gates

Production readiness should have a dedicated screen.

```text
G0 Code & Verification
G1 Market/Data Readiness
G2 Research Evidence
G3 Forward Evidence
G4 Infrastructure
G5 Venue Read-Only
G6 Manual Micro-Live
G7 Autonomous Limited
```

Example:

```text
G3 · Forward Evidence

Calendar Age
41 / 90 days

Closed Forward Trades
58 / 100

Unresolved Incidents
0

Recovery Drill
NOT PROVEN

STATUS
NOT QUALIFIED
```

Progress bars must never imply automatic promotion.

Passing metrics does not equal authorization.

---

# 28. Incident Management

Incident page should resemble an operational incident console.

Example:

```text
INC-2026-0142

Severity
Critical

Started
13:41:03 UTC

Resolved
—

Impact
New order submission halted

Cause
Reconciliation mismatch

Affected systems
OMS
Venue Adapter
Reconciliation

Timeline
13:41:03 mismatch detected
13:41:04 write authority revoked
13:41:06 operator notified
```

Support:

* timeline
* evidence
* linked orders
* linked audit events
* recovery state

---

# 29. Audit Log

Audit log must be immutable-looking and investigative.

Use a log explorer inspired by infrastructure tooling.

Columns:

```text
Timestamp
Actor
Action
Entity
Result
Correlation ID
Source
```

Filters:

```text
actor:
action:
entity:
candidate:
release:
order:
severity:
time:
```

Raw events may be viewed in structured form.

---

# 30. Research Workbench

Research is not a small secondary analytics screen.

It is a full research operating environment.

Primary lifecycle:

```text
IDEA
  ↓
COMPONENTS
  ↓
PIPELINE
  ↓
DATASET
  ↓
EXPERIMENT
  ↓
BACKTEST
  ↓
CANDIDATE
  ↓
SHADOW AGENT
  ↓
TOURNAMENT
  ↓
QUALIFICATION
```

The interface must make this lifecycle understandable.

---

# 31. Workbench Composer

The fundamental unit is an **Experiment**.

Example:

```text
BTC/IDR
1H

Dataset
2021-01-01 → 2025-12-31

C07 Mean Reversion
        ↓
BTC Fundamental Value
        ↓
EMA200 Regime Filter
        ↓
M02 XGBoost
        +
D04 iTransformer
        ↓
Soft Voting
        ↓
Risk Configuration
        ↓
Execution Simulation
```

Workbench supports two editing modes.

---

## Form Mode

Best for simple research.

Sections:

```text
Market
Dataset
Strategy
Fundamental / On-chain
Models
Ensemble
Risk
Execution
Evaluation
```

---

## Graph Mode

Best for advanced pipelines.

Visual inspiration:

* n8n
* Node-RED
* ComfyUI

but visually restrained and consistent with this product.

Nodes are **typed components**, not unrestricted code blocks.

Possible component types:

```text
TECHNICAL
FUNDAMENTAL
ONCHAIN
TOKENOMICS
ALTERNATIVE_DATA
ML_MODEL
DL_MODEL
FILTER
ENSEMBLE
RISK
EXECUTION
```

Connections must be validated.

Invalid pipelines should explain:

```text
Model expects FeatureSchema v4.
Dataset provides FeatureSchema v3.
```

rather than simply failing.

---

# 32. Strategy Registry

Strategy registry displays:

```text
Strategy ID
Name
Family
Version
Timeframe
Parameters
Status
Experiments
Candidates
```

Examples:

```text
C01 Donchian
C02 EMA Trend Pullback
C03 Time-Series Momentum
C07 Mean Reversion
F01 Crypto Value
F02 Value + Quality
```

Strategies are versioned.

Never silently overwrite strategy behavior.

---

# 33. Factor Registry

Fundamental research requires a dedicated factor surface.

Factor families:

```text
VALUE
QUALITY
GROWTH
NETWORK
TOKENOMICS
ONCHAIN
LIQUIDITY
SECURITY
ADOPTION
ECONOMICS
SUPPLY_DILUTION
YIELD_CARRY
ALTERNATIVE_DATA
```

Example factor detail:

```text
Revenue Yield

Family
VALUE

Formula
TTM protocol revenue / circulating market cap

Applicable
DeFi

Direction
Higher is better

Normalization
Peer-group robust z-score

Lag
24h publication lag

Version
factor-v3
```

---

# 34. Model Registry

Support:

```text
Classical ML
Deep Learning
Ensemble
Meta Models
```

Example models:

```text
M01 Logistic Regression
M02 XGBoost
D01 ResMLP
D02 TCN
D03 ResNet-LSTM
D04 iTransformer
```

Model detail includes:

```text
Model ID
Version
Artifact hash
Feature schema
Training dataset
Training period
Metrics
Created
Candidate usage
```

---

# 35. Dataset Lab

Dataset UX must support:

```text
Venue
Pair
Timeframe
From
To

[Fetch Historical Data]
```

Example:

```text
INDODAX
BTC/IDR
1H

2021-01-01
→
2025-12-31
```

Result:

```text
Dataset
ds-btcidr-1h-2021-2025-v3

Bars
43,812

Missing
2

Duplicates
0

Status
VERIFIED

SHA256
8f92...

Source
Indodax

Point-in-Time
YES
```

Dataset lifecycle:

```text
Source
 ↓
Raw Artifact
 ↓
Normalize
 ↓
Quality Validation
 ↓
Gap Detection
 ↓
Immutable Dataset
```

Historical data should be fetched once and reused.

---

# 36. Experiment Page

Experiment identity:

```text
EXP-00412
```

Sections:

```text
Configuration
Pipeline
Dataset
Execution Assumptions
Results
Robustness
Artifacts
Lineage
```

Experiments are immutable after execution.

Changing configuration creates:

```text
Clone Experiment
```

not an overwrite.

---

# 37. Backtest Results

Backtest result page should include:

```text
Net Return
Max Drawdown
Sharpe
Sortino
Calmar
Profit Factor
Expectancy
Trades
Fees
Turnover
```

Visualizations:

```text
Equity Curve
Drawdown
Monthly Returns
Trade Distribution
Regime Performance
Exposure
Trade List
```

Research charts may be more analytical than production charts, but retain the same visual language.

---

# 38. Experiment Compare

Support comparing multiple experiments.

Example table:

```text
EXP       Return   DD      Sharpe   PF    Trades   Fees
00412     18.4%    8.1%    1.42     1.31  112      ...
00413     16.2%    5.4%    1.58     1.44   94      ...
00414     23.8%   17.8%    1.21     1.20  173      ...
```

Include normalized equity comparison.

Do not visually declare a winner automatically.

---

# 39. Candidate Registry

An experiment may become a **Candidate**.

Candidate freeze displays:

```text
Candidate ID
Strategy Hash
Model Hashes
Dataset Hash
Feature Schema
Risk Config
Execution Config
Git SHA
Created
Research Evidence
```

Action:

```text
Promote to Candidate
```

never:

```text
Deploy Live
```

Research does not bypass qualification.

---

# 40. Tournament

Tournament compares isolated forward-shadow agents.

Each agent owns:

```text
Virtual Account
Virtual Cash
Virtual Positions
Virtual Orders
Virtual Fills
Virtual Ledger
Risk State
Candidate Identity
```

All agents receive the same canonical market feed where applicable.

Tournament page may show:

```text
Agent
Candidate
Family
Age
Equity
Return
Max DD
Sharpe
Trades
Fees
Status
Qualified
```

Important:

**Rank and Production Eligibility are different concepts.**

Example:

```text
Rank #1
Production Eligible: NO
Reason: insufficient forward evidence
```

No automatic promotion.

---

# 41. Tournament Cohorts

Support cohort filtering:

```text
All
BTC
Altcoin
Trend
Mean Reversion
Fundamental
Hybrid
ML
New Candidates
Qualified
Retired
```

Do not compare incomparable strategy horizons using a single magical score.

---

# 42. Agent Detail

Agent detail page:

```text
AGENT-023

Candidate
cand-btc-c07-042

Strategy
C07 + Fundamental Filter

Virtual Capital
Rp1,000,000

Forward Age
41 days

Closed Trades
58

Equity
Rp1,084,220

Max DD
4.2%
```

Tabs:

```text
Overview
Positions
Orders
Trades
Performance
Decision Trace
Risk
Evidence
Artifacts
```

---

# 43. Portfolio Shadow

Portfolio Shadow is distinct from Tournament Shadow.

Tournament:

```text
Agent A → Wallet A
Agent B → Wallet B
Agent C → Wallet C
```

Portfolio Shadow:

```text
Selected candidates
       ↓
Shared simulated portfolio
       ↓
Portfolio allocator
       ↓
Shared capital
```

The UI must communicate this difference clearly.

---

# 44. Infrastructure

Infrastructure should resemble a serious service console.

Display:

```text
Service
Host
Version
Status
CPU
Memory
Latency
Restarts
Last Heartbeat
```

Systems may include:

```text
Market Gateway
Strategy Runtime
Portfolio Service
Risk Engine
OMS
Venue Adapter
Ledger
Reconciliation
Metrics
Database
```

Host view:

```text
Lenovo Research Node
ASUS Observer Node
Production Linux Node
```

depending on deployment stage.

---

# 45. Market Data Health

Dedicated operational page.

Display:

```text
Pair
Interval
Last Event
Age
Sequence
Gap
Clock Drift
Status
```

Example:

```text
BTC/IDR
1m
13:42:09
1.2s
918273
0
84ms
HEALTHY
```

Stale data must be immediately obvious.

---

# 46. Venue

Venue page should expose capabilities and permissions.

Example:

```text
INDODAX

Connectivity
HEALTHY

Authenticated Read
VERIFIED

Trading Permission
ENABLED

Withdrawal Permission
FORBIDDEN FOR BOT

Clock Offset
84ms

Last Private Read
13:42:07
```

Withdrawal capability should be especially explicit.

---

# 47. Command Palette

Shortcut:

```text
Cmd/Ctrl + K
```

Supports:

```text
Navigate
Search orders
Search agents
Search candidates
Search releases
Search incidents
Search experiments
Search datasets
```

Do not place dangerous actions as casual command-palette shortcuts.

---

# 48. Search

Global search may recognize entity IDs.

Examples:

```text
ORD-194
AGENT-023
EXP-00412
cand-btc-c07-042
prod-0.4.3
INC-2026-0142
```

Results should identify entity type clearly.

---

# 49. Interaction Motion

Motion exists only to improve comprehension.

Recommended:

```text
100–180ms
```

Use for:

* drawer movement
* dropdown appearance
* hover transitions
* row expansion
* graph selection

Do not use:

* continuous pulsing for healthy states
* animated profit numbers
* glowing status rings
* celebratory effects
* bouncing charts

Critical state may use a brief entrance emphasis, then remain static.

---

# 50. Loading States

Use:

* skeletons for structured content
* inline spinners for actions
* explicit stale states when old data remains visible

Never replace previously known system state with a blank screen during refresh.

Example:

```text
Last known: HEALTHY
Refreshing...
Data age: 8s
```

---

# 51. Empty States

Empty states must be factual.

Example:

```text
No UNKNOWN orders

OMS currently has no unresolved venue state.
```

Research:

```text
No experiments yet

Create an experiment from the Workbench or clone an existing one.
```

Avoid cartoon illustrations.

---

# 52. Error States

Errors should answer:

```text
What failed?
What was affected?
What remains safe?
What can the operator inspect?
```

Example:

```text
Private venue read failed.

New order authority remains disabled.

Last successful private read:
13:39:18 UTC

[Open Venue Diagnostics]
```

---

# 53. Copywriting

Tone:

* factual
* restrained
* technical
* concise
* operational

Preferred:

```text
Reconciliation mismatch detected.
```

Avoid:

```text
Oops! Something went wrong.
```

Preferred:

```text
Candidate is not production eligible.
```

Avoid:

```text
Almost there!
```

This is operational software.

---

# 54. Accessibility

Minimum requirements:

* WCAG AA contrast
* visible keyboard focus
* keyboard-accessible navigation
* semantic HTML
* status not color-only
* chart values available through tooltip/table representation
* form errors linked to fields
* icon buttons have accessible labels

Critical system state must remain understandable in grayscale.

---

# 55. Responsive Behavior

Primary experience is desktop.

At 1280px:

* collapse secondary sidebar details
* preserve critical status
* allow horizontal table scrolling
* reduce panel columns

Mobile is secondary.

Mobile should prioritize:

```text
System Health
Mode
Incidents
Risk
Orders
Approvals
```

Do not attempt to reproduce full Research Graph editing on mobile.

---

# 56. Component Library

Recommended frontend stack:

```text
React
TypeScript
Tailwind CSS
shadcn/ui primitives
Lucide icons
Recharts
```

Create reusable primitives:

```text
AppShell
Sidebar
ContextBar
SafetyBanner
StatusBadge
StatusStrip
Metric
MetricGroup
DataTable
FilterBar
TimeRangePicker
ChartPanel
Drawer
EntityHeader
AuditTimeline
HealthTimeline
ModeBadge
RiskGauge
LimitBar
CandidateBadge
AgentBadge
ReleaseBadge
DatasetBadge
PipelineNode
PipelineCanvas
EvidencePanel
GuardedActionDialog
CommandPalette
```

Do not over-abstract before usage patterns become clear.

---

# 57. Visual Priority

Every page should follow this hierarchy:

```text
1. Critical safety state
2. Trading authority / execution mode
3. Health / freshness / reconciliation
4. Portfolio and risk
5. Current entity/context
6. Analysis
7. Historical detail
8. Metadata
```

Research pages change the middle layers:

```text
1. Experiment/candidate identity
2. Data validity
3. Pipeline configuration
4. Evidence/results
5. Comparisons
6. Lineage
7. Metadata
```

---

# 58. Anti-Patterns

Never use:

* neon crypto colors
* glowing borders
* cyberpunk visuals
* glassmorphism
* excessive gradients
* huge P&L typography
* decorative candlestick backgrounds
* animated coin icons
* confetti
* always-pulsing indicators
* 20 KPI cards at once
* giant rounded cards
* fake terminal styling
* color as the only status signal
* editable production configuration disguised as settings
* automatic balance correction actions
* automatic candidate promotion
* misleading “signed” terminology when only hashes exist

---

# 59. Reference Overview Composition

At 1440px:

```text
┌───────────────────────────────────────────────────────────────────┐
│ Context: SHADOW · Recon Healthy · UNKNOWN 0 · UTC · Operator     │
├───────────────────────────────────────────────────────────────────┤
│ STATUS STRIP                                                      │
│ Mode | Venue | Market | Recon | OMS | Risk | Release | Backup    │
├───────────────────────────────────────────────────────────────────┤
│ Equity      P&L       Exposure      DD       Cash       Orders    │
├──────────────────────────────────────┬────────────────────────────┤
│ Equity / P&L                         │ Risk / Exposure            │
│                                      │                            │
├──────────────────────────────────────┴────────────────────────────┤
│ Health Timeline                                                    │
├───────────────────────────────────────────────────────────────────┤
│ Positions                                                          │
├───────────────────────────────────────────────────────────────────┤
│ Orders                                                             │
├──────────────────────────────────────┬────────────────────────────┤
│ Recent Incidents                     │ Recent Audit               │
└──────────────────────────────────────┴────────────────────────────┘
```

---

# 60. Reference Research Composition

```text
┌───────────────────────────────────────────────────────────────────┐
│ Research / Workbench                          EXP-DRAFT           │
├───────────────────────────────────────────────────────────────────┤
│ Pair BTC/IDR · 1H · Dataset 2021–2025 · Form | Graph             │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│ Dataset                                                           │
│    ↓                                                              │
│ Fundamental Value                                                 │
│    ↓                                                              │
│ C07 Mean Reversion                                                │
│    ↓                                                              │
│ M02 XGBoost + D04 iTransformer                                    │
│    ↓                                                              │
│ Ensemble                                                          │
│    ↓                                                              │
│ Risk                                                              │
│    ↓                                                              │
│ Execution Simulator                                               │
│                                                                   │
├───────────────────────────────────────────────────────────────────┤
│ Configuration Summary | Validation | Estimated Resource Use       │
├───────────────────────────────────────────────────────────────────┤
│ [Save Draft]                         [Run Experiment]              │
└───────────────────────────────────────────────────────────────────┘
```

---

# 61. Mock Production State

Use consistent prototype data:

```text
Mode
SHADOW

Equity
Rp102.43M

Cash
Rp78.22M

BTC
0.00421

ETH
0.072

Daily P&L
+Rp430K

Drawdown
2.8%

Exposure
23.4%

Reconciliation
HEALTHY · 4s

OMS UNKNOWN
0

Clock Offset
84ms

Release
prod-0.4.3

Git
c2567f5960

Forward Evidence
41 / 90 days
58 / 100 trades
```

Mock states should also include failure scenarios.

Required prototype states:

```text
Healthy
HALTED
RECOVERY
Reconciliation mismatch
OMS UNKNOWN
Market stale
Manual approval waiting
Candidate not qualified
```

---

# 62. Final Product Principle

The entire UI should continuously reinforce one architectural truth:

```text
RESEARCH
creates evidence.

CANDIDATES
freeze evidence.

FORWARD TESTING
builds confidence.

GOVERNANCE
authorizes promotion.

PRODUCTION
executes immutable approved behavior.

BACKEND SERVICES
own financial truth.

THE UI
observes, investigates, compares, and safely controls.
```

The final product should feel like an **institutional systematic trading operating system**, not a cryptocurrency trading website.

When there is tension between visual excitement and operational clarity:

**operational clarity wins.**

When there is tension between convenience and safety in Production:

**safety wins.**

When there is tension between rigidity and experimentation in Research:

**reproducible experimentation wins.**
