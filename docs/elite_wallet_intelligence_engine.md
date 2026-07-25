# Elite Wallet Intelligence Engine

This phase profiles wallets from stored positions and produces:

- realized, unrealized, and total PnL
- deployed capital and ROI
- resolved-position hit rate
- consistency
- conviction and sizing discipline
- category specialization
- activity and data quality
- wallet grade and elite status
- category-specific wallet rankings

Statuses are `ELITE`, `QUALIFIED`, `WATCHLIST`, and `UNVERIFIED`.

The engine publishes `EliteWalletProfiled` only when a wallet profile changes.

## Important limitation

The current `positions` table may contain snapshots rather than a complete
resolved-trade ledger. Inferred resolution and win logic are recorded in
`evidence_json`. A future realized-outcome ledger can replace those inferences
without changing the public profile schema.

## Run

```powershell
python tools/apply_elite_wallet_integration.py
python -m pytest tests/test_elite_wallet_intelligence_engine.py -q
python -m pytest tests/test_opportunity_enrichment_engine.py -q
python src/elite_wallet_intelligence_engine.py
python src/elite_wallet_intelligence_health.py
python src/opportunity_enrichment_engine.py
python src/institutional_review_engine.py
```
