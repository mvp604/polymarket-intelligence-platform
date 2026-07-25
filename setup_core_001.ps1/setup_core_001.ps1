# ============================================================
# POLYMARKET INTELLIGENCE PLATFORM
# CORE-001: PROJECT MANAGEMENT FRAMEWORK
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================"
Write-Host " Polymarket Intelligence Platform - CORE-001"
Write-Host " Creating project management framework..."
Write-Host "============================================================"
Write-Host ""

$ProjectRoot = (Get-Location).Path

if (-not (Test-Path ".\src")) {
    throw @"
The 'src' folder was not found.

Open the correct project folder in VS Code:
Polymarket Intelligence Platform

Then run this script again from the project root.

Current folder:
$ProjectRoot
"@
}

Write-Host "[OK] Project root detected:"
Write-Host "     $ProjectRoot"
Write-Host ""

$ManagedFiles = @(
    "README.md",
    "ROADMAP.md",
    "CURRENT_SPRINT.md",
    "PROJECT_STATUS.md",
    "NEXT_TASK.md",
    "ARCHITECTURE.md",
    "DECISIONS.md",
    "CHANGELOG.md"
)

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$BackupRoot = Join-Path $ProjectRoot "backups\project-docs\$Timestamp"
$ExistingFiles = @()

foreach ($File in $ManagedFiles) {
    if (Test-Path $File) {
        $ExistingFiles += $File
    }
}

if ($ExistingFiles.Count -gt 0) {
    New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null

    foreach ($File in $ExistingFiles) {
        Copy-Item -Path $File -Destination (Join-Path $BackupRoot $File) -Force
    }

    Write-Host "[OK] Existing documentation backed up to:"
    Write-Host "     $BackupRoot"
    Write-Host ""
}
else {
    Write-Host "[OK] No existing managed documentation required backup."
    Write-Host ""
}

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-ProjectFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    $FullPath = Join-Path $ProjectRoot $Path
    [System.IO.File]::WriteAllText($FullPath, $Content.TrimStart(), $Utf8NoBom)
    Write-Host "[CREATED] $Path"
}

$ReadmeContent = @'
# Polymarket Intelligence Platform

## Mission

Build a professional-grade Polymarket intelligence platform that collects,
validates, stores, analyzes, and explains official public market and wallet data.

The platform is designed to surface higher-quality opportunities through:

- Wallet intelligence
- Category specialization analysis
- Consensus detection
- Conviction scoring
- Historical tracking
- Market structure analysis
- Signal validation
- Performance measurement
- Explainable opportunity reports

The objective is not to display the most data.

The objective is to produce trustworthy, actionable, and testable intelligence.

---

## North Star

Every proposed feature must answer:

> Does this improve decision quality, reliability, maintainability, or measurable platform performance?

If the answer is no, it should not be prioritized for Version 1.0.

---

## Development Principles

1. Use official Polymarket public data whenever available.
2. Keep data collection separate from analysis engines.
3. Store reusable data instead of repeatedly requesting it.
4. Avoid duplicate business logic.
5. Make every engine modular and testable.
6. Preserve historical observations for validation.
7. Measure signals before promoting them.
8. Prefer correctness and reliability over speed of development.
9. Do not advance until the active task meets its definition of done.
10. Keep exactly one authoritative active task in `NEXT_TASK.md`.

---

## Current Known Project Components

The project currently includes or has included work on:

- `src/database.py`
- `src/wallet_tracker.py`
- `src/conviction_engine.py`
- `src/consensus_history.py`
- `src/consensus_diagnostics.py`

Known database concepts include:

- Wallet scans
- Wallet positions
- Consensus history
- Market-level conviction scoring
- Historical consensus observations

These components must be audited before they are formally marked production-ready.

---

## Project Documents

| File | Purpose |
|---|---|
| `README.md` | Project introduction and operating instructions |
| `ROADMAP.md` | Long-term development phases |
| `CURRENT_SPRINT.md` | Current sprint objective and checklist |
| `PROJECT_STATUS.md` | Current platform health and progress |
| `NEXT_TASK.md` | The single active engineering task |
| `ARCHITECTURE.md` | Authoritative high-level architecture |
| `DECISIONS.md` | Architecture Decision Records |
| `CHANGELOG.md` | Completed changes and milestones |

---

## Standard Project Commands

### `Project Brief`

Review project documents and provide the current version, phase, sprint, task,
completed work, blockers, risks, and recommended action.

### `Audit Project`

Review architecture, database integrity, data flow, duplicate logic, testing,
technical debt, reliability, documentation, security, and performance risks.

### `Review Module: <module name>`

Perform a focused review of one module before modifying or building on it.

### `Advance Project`

Advance only after the active task is verified complete.

Required sequence:

1. Read `ROADMAP.md`.
2. Read `CURRENT_SPRINT.md`.
3. Read `PROJECT_STATUS.md`.
4. Read `NEXT_TASK.md`.
5. Inspect relevant code and tests.
6. Verify the definition of done.
7. Update documentation.
8. Close the task.
9. Select the next dependency-aware task.

### `Freeze Release`

Create a stable checkpoint before a major architectural or database change.

---

## Initial Setup

From the repository root:

```powershell
python --version
```

Create a virtual environment if needed:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies when `requirements.txt` exists:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## Current Execution Notes

The authoritative execution command must be confirmed during the CORE-002 audit.

Until then, run only verified individual modules from the repository root.

---

## Versioning

Current development version:

`0.1.0`

---

## Definition of Done

A task is complete only when all applicable conditions are met:

- Implementation exists
- Relevant tests pass
- Integration is verified
- Error handling is included
- Documentation is updated
- No known regression remains
- Project status is updated
- The next task is selected only after verification

---

## Current Direction

The immediate focus is core infrastructure stabilization.

See:

`NEXT_TASK.md`
'@

Write-ProjectFile -Path "README.md" -Content $ReadmeContent

$RoadmapContent = @'
# Product Roadmap

## Product Objective

Create a modular, explainable, historically validated Polymarket intelligence
platform powered by official public market and wallet data.

---

# Phase 1 — Core Infrastructure

## Scope

- Project management framework
- Configuration management
- Central logging
- Database bootstrap
- Schema versioning
- Migration framework
- Health checks
- Error classification
- Engine interface
- Engine registry
- Dependency management
- Unified execution pipeline
- Testing framework
- Safe rollback and recovery
- Project state reporting

## Exit Criteria

- One verified startup path
- Database health audit
- Actionable configuration failures
- Testable core modules
- Accurate project state
- Safe startup failure behavior

---

# Phase 2 — Official Data Acquisition

## Planned Sources

- Gamma API
- Data API
- CLOB REST API
- WebSocket feeds
- Market metadata
- Events
- Outcomes
- Order books
- Prices
- Price history
- Spreads
- Trades
- Activity
- Positions
- Holders
- Open interest
- Leaderboards
- Sports metadata
- Resolution data

## Required Capabilities

- Pagination
- Rate-limit handling
- Retries and backoff
- Caching
- Deduplication
- Normalization
- Validation
- Timestamp consistency
- Historical storage
- Data-quality reporting
- Source provenance

---

# Phase 3 — Wallet Intelligence

## Planned Capabilities

- Wallet discovery
- Wallet ranking
- Realized and unrealized PnL
- Return consistency
- Drawdown
- Category specialization
- Market-type specialization
- Entry and exit timing
- Holding duration
- Position sizing behavior
- Conviction behavior
- Risk-adjusted performance
- Wallet confidence scoring
- Wallet history
- Wallet cluster analysis
- Related-wallet detection

---

# Phase 4 — Market Intelligence Engines

## Planned Engines

- Consensus Engine
- Weighted Consensus Engine
- Conviction Engine
- Portfolio Overlap Engine
- Position Evolution Engine
- Smart-Money Rotation Engine
- Market Momentum Engine
- Liquidity and Spread Engine
- Order-Book Imbalance Engine
- Market Structure Engine
- Specialist Wallet Engine
- Opportunity Scoring Engine
- Risk Engine
- Alert Qualification Engine

---

# Phase 5 — Historical Validation and Learning

## Planned Capabilities

- Resolution tracking
- Signal outcome tracking
- Backtesting
- Walk-forward validation
- Calibration analysis
- Brier score
- Hit rate
- ROI
- Expected value
- Drawdown
- Confidence-band performance
- Category-level performance
- Wallet-level performance
- Engine-version comparisons
- False-positive analysis

---

# Phase 6 — Automation and Monitoring

## Planned Capabilities

- Scheduled ingestion
- Scheduled engine execution
- WebSocket consumers
- Job state tracking
- Retry queues
- Failure alerts
- Data freshness checks
- Stale-signal invalidation
- Snapshot retention
- Operational metrics
- Audit trails

---

# Phase 7 — Reporting, Alerts, and Dashboard

## Planned Surfaces

- Live opportunity board
- Elite wallet rankings
- Wallet profiles
- Category specialist board
- Market heatmap
- Consensus timeline
- Conviction timeline
- Historical performance reports
- Watchlists
- Alert center
- Personal dashboard
- Operations dashboard

---

# Phase 8 — Controlled Production Release

## Planned Capabilities

- Authentication
- Authorization
- User accounts
- Subscription plans
- Credit system
- Per-report purchases
- Referral program
- Personalized dashboards
- Billing integration
- Privacy controls
- Terms and disclosures
- Production deployment
- Backup and disaster recovery
- Monitoring
- Support procedures

---

# Roadmap Governance

1. One active task at a time.
2. Dependencies determine task order.
3. New ideas enter a backlog before entering a sprint.
4. Completed modules are not rebuilt without a documented reason.
5. Architectural changes require an ADR.
6. Dashboard work does not outrank data correctness.
7. AI does not replace missing data validation.
8. Advancement requires verified completion.
'@

Write-ProjectFile -Path "ROADMAP.md" -Content $RoadmapContent

$CurrentSprintContent = @'
# Current Sprint

## Sprint ID

`CORE-SPRINT-001`

## Sprint Name

Core Infrastructure Stabilization

## Roadmap Phase

Phase 1 — Core Infrastructure

## Sprint Objective

Establish the project-management framework and begin validating startup,
database, configuration, logging, and execution foundations.

---

## Completed

- [x] Create `README.md`
- [x] Create `ROADMAP.md`
- [x] Create `CURRENT_SPRINT.md`
- [x] Create `PROJECT_STATUS.md`
- [x] Create `NEXT_TASK.md`
- [x] Create `ARCHITECTURE.md`
- [x] Create `DECISIONS.md`
- [x] Create `CHANGELOG.md`
- [x] Define the `Advance Project` checkpoint
- [x] Define the one-active-task rule
- [x] Define the project definition of done

---

## Active Task

`CORE-002 — Audit and Implement Platform Bootstrap and Health Framework`

See:

`NEXT_TASK.md`

---

## Planned Sprint Work

- [ ] Audit current startup and execution entry points
- [ ] Audit database initialization
- [ ] Audit schema creation and consistency
- [ ] Identify required tables and indexes
- [ ] Confirm configuration loading
- [ ] Establish central logging
- [ ] Establish health-check result structure
- [ ] Establish error classifications
- [ ] Define one authoritative bootstrap sequence
- [ ] Add or improve automated tests
- [ ] Verify startup behavior
- [ ] Update architecture and status documents

---

## Sprint Guardrails

Do not prioritize:

- Dashboard development
- Subscription billing
- Referral dashboards
- New user-facing reports
- Additional speculative scoring engines
- AI summaries
- Cosmetic interface work
'@

Write-ProjectFile -Path "CURRENT_SPRINT.md" -Content $CurrentSprintContent

$ProjectStatusContent = @'
# Project Status

## Platform

Polymarket Intelligence Platform

## Development Version

`0.1.0`

## Overall Status

`FOUNDATION IN PROGRESS`

## Current Roadmap Phase

Phase 1 — Core Infrastructure

## Current Sprint

`CORE-SPRINT-001 — Core Infrastructure Stabilization`

## Current Active Task

`CORE-002 — Audit and Implement Platform Bootstrap and Health Framework`

---

# Documentation Status

- [x] README
- [x] Roadmap
- [x] Current sprint
- [x] Project status
- [x] Next task
- [x] Architecture
- [x] Architecture decisions
- [x] Changelog

---

# Known Existing Components

- `src/database.py`
- `src/wallet_tracker.py`
- `src/conviction_engine.py`
- `src/consensus_history.py`
- `src/consensus_diagnostics.py`

These must be audited before being labeled production-ready.

---

# Completed Milestones

## CORE-001

Project Management Framework

Status:

`COMPLETE`

---

# In Progress

## CORE-002

Platform Bootstrap and Health Framework

Status:

`READY FOR CODEBASE AUDIT`

---

# Potential Audit Targets

- Database bootstrap consistency
- Schema drift
- Unverified startup entry points
- Byte Order Mark contamination
- Central logging consistency
- Missing or incomplete automated tests
- Configuration-loading fragmentation

These are audit targets, not confirmed current failures.

---

# Next Milestone

A repeatable startup sequence reporting:

- Configuration health
- Database connectivity
- Schema health
- Logging readiness
- Engine readiness
- Overall readiness

---

# Required Next Action

Inspect the current codebase before generating replacement infrastructure code.
'@

Write-ProjectFile -Path "PROJECT_STATUS.md" -Content $ProjectStatusContent

$NextTaskContent = @'
# Next Task

## Task ID

`CORE-002`

## Title

Audit and Implement Platform Bootstrap and Health Framework

## Status

`READY`

## Priority

Critical

---

## Objective

Create one authoritative, deterministic, and testable process that prepares the
platform to run and reports whether it is healthy.

---

## Required First Step

Audit the existing repository.

Identify:

- Current Python files
- Existing startup scripts
- Database initialization logic
- Current schema
- Existing tables and indexes
- Configuration files
- Logging configuration
- Test files
- Engine interfaces
- Scheduler code
- Dependency declarations
- Environment variable usage
- Existing health-check logic

---

## Expected Capabilities

1. Bootstrap manager
2. Structured health-check results
3. Database connectivity check
4. Schema validation
5. Required-table validation
6. Required-index validation
7. Configuration validation
8. Logging readiness check
9. Engine readiness check
10. Actionable startup summary
11. Error classifications
12. Automated tests
13. Updated documentation

---

## Success Criteria

- One authoritative startup path exists.
- Startup is repeatable.
- Required configuration is validated.
- Database connectivity is verified.
- Required schema objects are verified.
- Critical failures stop execution.
- Warnings are clearly reported.
- Errors have clear categories and messages.
- Logging initializes consistently.
- A readable health report is produced.
- Relevant automated tests pass.
- Existing behavior has not regressed.
- Architecture documentation is updated.
- Project status is updated.

---

## Definition of Done Checklist

- [ ] Repository audit completed
- [ ] Existing implementation documented
- [ ] Gaps identified
- [ ] Architecture selected
- [ ] ADR added if required
- [ ] Code implemented
- [ ] Tests created or updated
- [ ] Tests passed
- [ ] Manual startup verified
- [ ] Failure scenarios verified
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] Project status updated
- [ ] No known regression remains

---

## Advancement Rule

`Advance Project` must review CORE-002 until this checklist is verified.
'@

Write-ProjectFile -Path "NEXT_TASK.md" -Content $NextTaskContent

$ArchitectureContent = @'
# Platform Architecture

## Architecture Status

This document describes the target architecture and currently known system.

Items labeled as target are not considered implemented until verified in code.

---

# 1. Architectural Goals

- Correct
- Reliable
- Explainable
- Modular
- Testable
- Scalable
- Observable
- Recoverable
- Historically reproducible

---

# 2. Core Data Flow

```text
Official Polymarket Sources
            |
            v
     Acquisition Layer
            |
            v
 Validation and Normalization
            |
            v
       Storage Layer
            |
            v
   Intelligence Engines
            |
            v
 Historical Validation
            |
            v
 Opportunity and Risk Layer
            |
            v
 Reports, Alerts, Dashboard
```

---

# 3. Configuration Layer

Responsibilities:

- Environment variables
- Runtime settings
- API settings
- Database paths
- Thresholds
- Feature flags
- Logging settings
- Scheduler settings

---

# 4. Bootstrap and Health Layer

Responsibilities:

- Initialize logging
- Load configuration
- Verify filesystem access
- Connect to database
- Validate schema
- Validate indexes
- Register engines
- Check dependencies
- Report readiness

Target states:

- `READY`
- `READY_WITH_WARNINGS`
- `NOT_READY`

---

# 5. Acquisition Layer

Responsibilities:

- Fetch official public data
- Handle pagination
- Handle rate limits
- Retry temporary failures
- Cache responses
- Attach source provenance
- Prevent duplicate ingestion
- Record timestamps

---

# 6. Validation and Normalization Layer

Responsibilities:

- Validate payloads
- Normalize IDs
- Normalize timestamps
- Normalize numeric values
- Map markets and outcomes
- Detect malformed records
- Detect stale records
- Record data-quality warnings

---

# 7. Storage Layer

Current known technology:

- SQLite

Target responsibilities:

- Schema initialization
- Versioned migrations
- Foreign-key enforcement
- Transaction safety
- Required indexes
- Historical retention
- Auditability
- Query performance

---

# 8. Intelligence Layer

Each engine should:

- Have one primary responsibility
- Declare required inputs
- Return structured outputs
- Avoid duplicate data collection
- Include score evidence
- Be versioned
- Be independently testable

---

# 9. Historical Validation Layer

Responsibilities:

- Store promoted signals
- Track market movement
- Track resolutions
- Calculate accuracy
- Calculate ROI
- Measure calibration
- Segment results
- Compare engine versions
- Detect performance decay

---

# 10. Orchestration Layer

Responsibilities:

- Dependency-aware execution
- Job scheduling
- Run identifiers
- Start and finish timestamps
- Retry policy
- Idempotency
- Failure handling
- Execution summaries
- State persistence

---

# 11. Presentation Layer

Future responsibilities:

- Opportunity board
- Wallet rankings
- Market profiles
- Reports
- Alerts
- Watchlists
- Historical replay
- Performance dashboards

The presentation layer should not contain authoritative scoring logic.

---

# 12. Error Categories

- Configuration
- Database
- Schema
- API
- Network
- Validation
- Engine
- Scheduler
- Filesystem
- Unexpected

---

# 13. Testing Strategy

- Unit tests
- Database tests
- Migration tests
- Contract tests
- API fixture tests
- Integration tests
- Failure-path tests
- Regression tests
- Historical replay tests

Live API dependence should be isolated to explicitly marked integration tests.
'@

Write-ProjectFile -Path "ARCHITECTURE.md" -Content $ArchitectureContent

$DecisionsContent = @'
# Architecture Decision Records

---

# ADR-001 — Official Public Data First

## Status

Accepted

## Decision

Prioritize relevant official Polymarket public data sources before unofficial
aggregators.

---

# ADR-002 — Separate Collection from Intelligence

## Status

Accepted

## Decision

Intelligence engines consume shared normalized data instead of independently
requesting the same external data.

---

# ADR-003 — Historical Observations Are First-Class Data

## Status

Accepted

## Decision

Preserve historical market, wallet, consensus, and signal observations when
required for later validation.

---

# ADR-004 — One Active Engineering Task

## Status

Accepted

## Decision

Keep exactly one authoritative active task in `NEXT_TASK.md`.

---

# ADR-005 — Advance Only After Verification

## Status

Accepted

## Decision

`Advance Project` is a completion checkpoint, not a request for the next idea.

---

# ADR-006 — SQLite Remains the Initial Database

## Status

Accepted for Current Development Stage

## Decision

Continue using SQLite until measured requirements justify migration.

---

# ADR-007 — UTF-8 Without BOM

## Status

Accepted

## Decision

Generated source and documentation files use UTF-8 without a Byte Order Mark.

---

# ADR-008 — Dashboard Follows Verified Intelligence

## Status

Accepted

## Decision

Do not prioritize dashboard expansion before data correctness, platform health,
and signal validation.

---

# ADR Template

```text
# ADR-XXX — Title

## Status

Proposed | Accepted | Superseded | Rejected

## Decision

What was decided?

## Context

Why was the decision needed?

## Alternatives Considered

What other approaches were considered?

## Consequences

Benefits and tradeoffs.

## Date

YYYY-MM-DD
```
'@

Write-ProjectFile -Path "DECISIONS.md" -Content $DecisionsContent

$ChangelogContent = @'
# Changelog

# [0.1.0] — Project Management Foundation

## Added

- Project README
- Dependency-driven roadmap
- Current sprint document
- Project status report
- Single active-task document
- High-level architecture document
- Architecture Decision Records
- Project changelog
- Standard project commands
- Formal definition of done
- Advancement verification rule
- UTF-8 without BOM generation standard

## Changed

- `Advance Project` is now a completion checkpoint.
- New work must follow the active roadmap phase and task.
- Progress must be based on verified repository state.

## Current Active Task

`CORE-002 — Audit and Implement Platform Bootstrap and Health Framework`

---

# Earlier Development Work — Unversioned

Known earlier work includes:

- SQLite database initialization
- Wallet scan storage
- Position storage
- Wallet tracking
- Conviction scoring
- Consensus history
- Consensus diagnostics

These require repository verification before formal release status.
'@

Write-ProjectFile -Path "CHANGELOG.md" -Content $ChangelogContent

Write-Host ""
Write-Host "Validating generated framework..."
Write-Host ""

$ValidationFailures = @()

foreach ($File in $ManagedFiles) {
    $FullPath = Join-Path $ProjectRoot $File

    if (-not (Test-Path $FullPath)) {
        $ValidationFailures += "$File was not created."
        continue
    }

    $Length = (Get-Item $FullPath).Length

    if ($Length -le 0) {
        $ValidationFailures += "$File is empty."
    }
    else {
        Write-Host "[PASS] $File ($Length bytes)"
    }
}

if ($ValidationFailures.Count -gt 0) {
    Write-Host ""
    Write-Host "CORE-001 validation failed:" -ForegroundColor Red

    foreach ($Failure in $ValidationFailures) {
        Write-Host " - $Failure" -ForegroundColor Red
    }

    throw "Project framework creation did not complete successfully."
}

Write-Host ""

if (Get-Command git -ErrorAction SilentlyContinue) {
    if (Test-Path ".\.git") {
        Write-Host "Git status:"
        Write-Host "------------------------------------------------------------"
        git status --short
        Write-Host "------------------------------------------------------------"
        Write-Host ""
    }
}

Write-Host "============================================================" -ForegroundColor Green
Write-Host " CORE-001 COMPLETE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Created and validated:"
foreach ($File in $ManagedFiles) {
    Write-Host " - $File"
}

Write-Host ""
Write-Host "Current active task:"
Write-Host " CORE-002 - Audit and Implement Platform Bootstrap and Health Framework"
Write-Host ""
Write-Host "Next command:"
Write-Host " Advance Project"
Write-Host ""