# Institutional Intelligence Engine Specification

Version: 3.0.0-alpha  
Status: Approved for implementation

## 1. Mission

Transform raw public Polymarket wallet data into explainable,
versioned, evidence-aware institutional intelligence profiles.

The engine produces research rankings and behavioral analytics.
It does not produce calibrated probabilities or guarantees.

## 2. Pipeline position

Elite Wallet Discovery
→ Wallet Profile Collection
→ Institutional Intelligence
→ Wallet Rating
→ Institutional Wallet DNA
→ Weighted Consensus
→ Conviction
→ Signal Fusion
→ Opportunity Ranking

## 3. Primary input tables

- discovered_wallets
- wallet_profiles_raw
- wallet_current_position_snapshots
- wallet_closed_position_snapshots
- wallet_trade_snapshots
- wallet_activity_snapshots
- wallet_profile_collection_runs

## 4. Legacy fallback inputs

- wallet_scans
- positions

Legacy inputs may be used only when production collector data is
unavailable for a wallet.

Production and legacy observations must not be combined in a way
that double-counts the same position.

## 5. Output tables

### wallet_intelligence_profiles

Stores the latest profile for every wallet.

Required dimensions:

- performance_score
- timing_score
- conviction_score
- consistency_score
- risk_score
- specialization_score
- influence_score
- copyability_score
- confidence_score
- overall_score
- overall_grade
- score_version
- calculated_at
- last_run_id

### wallet_intelligence_snapshots

Stores immutable historical profile snapshots.

### wallet_category_performance

Stores category-specific wallet evidence and scores.

### wallet_behavior_flags

Stores explainable detected behaviors and warnings.

### wallet_intelligence_runs

Stores execution status, configuration, row counts, diagnostics,
duration, and errors.

## 6. Evidence hierarchy

Evidence strength, from strongest to weakest:

1. Resolved positions with realized results
2. Closed positions with realized PnL
3. Complete historical trade sequences
4. Repeated current-position snapshots
5. A single current-position snapshot
6. Discovery leaderboard information

Scores must reflect evidence quality.

## 7. Scoring dimensions

### Performance

Measures realized and observed economic performance.

Inputs may include:

- realized PnL
- unrealized PnL
- ROI
- win rate
- profit factor
- expectancy
- entry edge
- drawdown

Unrealized PnL must not be treated as equivalent to realized PnL.

### Timing

Measures whether entries occur before favorable price movement.

Initial implementation may use observed entry-to-current-price edge.
Future versions will use complete market price history.

### Conviction

Measures sizing and position-building behavior.

Inputs may include:

- average position value
- largest position value
- portfolio share
- repeated buying
- scaling direction
- holding persistence

Large position size alone does not prove skill.

### Consistency

Measures repeatability across markets and time.

Inputs may include:

- rolling ROI stability
- PnL volatility
- recurring profitable periods
- category stability
- recent versus long-term performance

### Risk

Measures capital management quality.

Inputs may include:

- concentration
- diversification
- downside exposure
- loss severity
- drawdown
- simultaneous market exposure

A high risk score means stronger risk control.

### Specialization

Measures category-specific evidence and performance.

Scores require both:

- category activity
- category-specific performance evidence

Volume without performance is not specialization.

### Influence

Measures whether wallet activity tends to precede:

- price movement
- volume changes
- elite-wallet participation
- consensus formation

This score remains provisional until adequate temporal market data
exists.

### Copyability

Measures whether following the wallet is practically replicable.

Inputs may include:

- holding duration
- trade frequency
- liquidity
- entry-price persistence
- slippage
- position visibility
- available reaction time

## 8. Confidence model

Confidence is independent of performance.

Confidence should increase with:

- number of observations
- number of unique markets
- resolved outcomes
- collection history
- category evidence
- time-span coverage

Confidence should decrease with:

- missing fields
- conflicting observations
- duplicate-heavy data
- incomplete history
- very small samples

Wallets with confidence below the minimum threshold receive the
PROVISIONAL grade regardless of raw score.

## 9. Overall score

Version 3.0 initial weights:

- Performance: 24%
- Timing: 17%
- Consistency: 16%
- Risk control: 14%
- Recent form: 12%
- Conviction: 9%
- Confidence: 8%

Specialization, influence, and copyability will initially be
reported independently until their evidence is sufficiently mature.

Weights must be versioned and stored with every run.

## 10. Grade boundaries

- S: 92 or higher
- A+: 85–91.99
- A: 78–84.99
- B+: 70–77.99
- B: 62–69.99
- C: 52–61.99
- D: below 52
- PROVISIONAL: insufficient confidence

## 11. Current-position selection

For each wallet:

1. Select the latest successful or partial applied collection.
2. Load current-position rows belonging to that run.
3. Deduplicate positions using the strongest available identity:
   - asset
   - condition_id and outcome
   - condition_id and outcome_index
4. Preserve the source run ID and observation timestamp.
5. Do not combine multiple current snapshots as simultaneous exposure.

## 12. Historical analysis

Historical snapshots may be used to identify:

- position additions
- reductions
- exits
- new entries
- holding duration
- scaling behavior
- concentration changes
- category migration

Historical snapshots must not be summed as current capital exposure.

## 13. Run statuses

Supported statuses:

- RUNNING
- SUCCESS
- PARTIAL
- FAILED
- SKIPPED

A single-wallet failure must not invalidate successful wallet
profiles unless strict execution mode is enabled.

## 14. Execution modes

### Dry run

- Reads source data
- Calculates profiles
- Produces diagnostics
- Does not mutate intelligence tables

### Apply

- Calculates profiles
- Upserts latest profiles
- Inserts immutable snapshots
- Persists category results and behavior flags
- Finalizes the run record

## 15. Testing requirements

Required automated tests:

- Production source is preferred over legacy source
- Legacy fallback works
- Current snapshots are not double-counted
- Duplicate positions are removed
- Realized and unrealized PnL remain separate
- Missing evidence produces provisional ratings
- Grade boundaries are deterministic
- Dry run does not persist
- Apply persists profiles and snapshots
- Partial wallet failures are recorded
- Repeated executions produce deterministic scores
- Source raw tables remain unchanged

## 16. Non-negotiable principles

- Explainability over opaque scoring
- Evidence quality over leaderboard rank
- Realized performance over unrealized appearance
- Category skill over universal wallet reputation
- Historical reproducibility
- No forced signal
- No score represented as certainty