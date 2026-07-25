# Opportunity Enrichment Engine

This phase sits between Opportunity Intelligence and Institutional Review.

It enriches each current opportunity with:

- wallet and elite-wallet counts
- combined capital and capital strength
- wallet quality
- timing score and timing status
- current price, liquidity, and spread
- market structure
- historical reliability
- data completeness

It publishes an `OpportunityEnriched` event whenever the enriched state changes.
The Institutional Review Engine then consumes that event and creates a new
immutable review using the richer payload.

## Install

```powershell
python tools/apply_opportunity_enrichment_integration.py
python -m pytest tests/test_opportunity_enrichment_engine.py -q
python src/opportunity_enrichment_engine.py
python src/institutional_review_engine.py
python src/opportunity_enrichment_health.py
python src/institutional_review_health.py
```

Run the Institutional Review Engine repeatedly until its source event count is
zero when the enrichment engine creates more than 10,000 events.
