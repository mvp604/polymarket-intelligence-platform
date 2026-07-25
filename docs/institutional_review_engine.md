# Institutional Review Engine

The Institutional Review Engine consumes `OpportunityCreated` and
`OpportunityUpdated` events and creates immutable institutional assessments.

## Outputs

- `institutional_review_runs`
- `institutional_reviews`
- `current_institutional_reviews`
- `ranked_institutional_reviews`
- `OpportunityReviewed` platform events
- consumer receipts for idempotent processing

## Decisions

- `APPROVE`
- `REVIEW`
- `MONITOR`
- `REJECT`

The engine is deterministic. A review is unique by opportunity, source state
checksum, and model version.

## Run

```powershell
python src/institutional_review_engine.py
python src/institutional_review_health.py
python -m pytest tests/test_institutional_review_engine.py -q
```
