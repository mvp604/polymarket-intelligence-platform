# Database Schema Specification v1.0

## Audit Summary

- Generated: `2026-07-22T20:59:47+00:00`
- Database: `C:\Users\mitch\OneDrive\Desktop\Polymarket Intelligence Platform\database\polymarket.db`
- SQLite version: `3.50.4`
- Journal mode: `wal`
- Foreign keys enabled: `False`
- Integrity check: `ok`
- Tables: `202`
- Views: `0`
- Triggers: `0`
- Indexes: `377`

## Repository Planning Matrix

| Table | Rows | Primary Key | Foreign Keys | Source References |
|---|---:|---|---:|---:|
| ai_reports | 0 | id | 0 | 1 |
| alerts | 299 | id | 0 | 13 |
| api_endpoint_tests | 144 | test_key | 1 | 1 |
| api_pagination_probes | 122 | probe_key | 1 | 1 |
| api_validation_runs | 2 | id | 0 | 1 |
| backtest_results | 64 | id | 0 | 10 |
| candidate_qualification_history | 4600 | id | 0 | 1 |
| candidate_qualification_runs | 5 | id | 0 | 1 |
| candidate_wallet_evaluations | 920 | wallet | 0 | 4 |
| canonical_backfill_audit | 1175 | id | 1 | 1 |
| canonical_backfill_runs | 7 | run_id | 0 | 1 |
| canonical_coverage_audit | 262 | id | 0 | 1 |
| canonical_coverage_audit_runs | 2 | id | 0 | 1 |
| canonical_identity_refresh_audit | 300 | id | 0 | 1 |
| canonical_identity_refresh_runs | 3 | id | 0 | 1 |
| canonical_identity_sync_audit | 262 | id | 0 | 1 |
| canonical_identity_sync_runs | 2 | id | 0 | 1 |
| canonical_market_identities | 21765 | condition_id | 0 | 18 |
| canonical_market_identity_aliases | 7320 | alias_key | 1 | 1 |
| canonical_market_identity_runs | 3 | id | 0 | 2 |
| closing_line_history | 87 | id | 0 | 4 |
| closing_line_metrics | 87 | opportunity_key | 0 | 8 |
| closing_line_runs | 1 | id | 0 | 1 |
| condition_id_lineage_audit_results | 144 | id | 1 | 1 |
| condition_id_lineage_audit_runs | 4 | run_id | 0 | 1 |
| consensus_history | 756 | id | 0 | 23 |
| decision_price_attribution_runs | 1 | run_id | 0 | 3 |
| decision_price_attributions | 131 | attribution_key | 0 | 3 |
| discovered_wallets | 48 | wallet | 0 | 2 |
| elite_wallet_category_weights | 51 | category_weight_key | 1 | 1 |
| elite_wallet_history | 26 | id | 0 | 1 |
| elite_wallet_rankings | 26 | wallet | 0 | 4 |
| elite_wallet_runs | 1 | id | 0 | 1 |
| engine_runs | 0 | id | 0 | 1 |
| entry_price_cache | 137 | opportunity_key | 0 | 1 |
| gamma_events | 2228 | gamma_event_id | 0 | 4 |
| gamma_market_outcomes | 41206 | outcome_key | 1 | 6 |
| gamma_markets | 21778 | gamma_market_id | 1 | 15 |
| gamma_registry_expansion_checkpoints | 0 | checkpoint_name | 0 | 1 |
| gamma_registry_expansion_errors | 0 | id | 0 | 1 |
| gamma_registry_expansion_recovery | 8780 | condition_id | 0 | 1 |
| gamma_registry_expansion_runs | 4 | id | 0 | 1 |
| gamma_registry_runs | 1 | id | 0 | 1 |
| historical_market_reconciliation_audit | 9732 | id | 1 | 1 |
| historical_market_reconciliation_runs | 3 | run_id | 0 | 1 |
| historical_market_reconciliation_summary | 4 | id | 1 | 1 |
| institutional_clob_market_cache | 39 | condition_id | 0 | 5 |
| institutional_consensus | 137 | consensus_key | 0 | 18 |
| institutional_consensus_history | 137 | id | 0 | 1 |
| institutional_consensus_runs | 1 | id | 0 | 1 |
| institutional_decision_diagnostic_history | 131 | id | 0 | 1 |
| institutional_decision_diagnostic_runs | 1 | run_id | 0 | 3 |
| institutional_decision_diagnostics | 131 | opportunity_key | 0 | 3 |
| institutional_decision_history | 131 | id | 0 | 6 |
| institutional_decision_history_v2 | 0 | id | 0 | 4 |
| institutional_decision_runs | 4 | run_id | 0 | 1 |
| institutional_decision_runs_v2 | 7 | run_id | 0 | 4 |
| institutional_decisions | 131 | opportunity_key | 0 | 3 |
| institutional_decisions_v2 | 0 | opportunity_key | 0 | 4 |
| institutional_learning_evaluations | 26 | evaluation_key | 0 | 2 |
| institutional_learning_observations | 131 | observation_key | 0 | 16 |
| institutional_learning_runs | 2 | run_id | 0 | 2 |
| institutional_settlement_intelligence_audit | 48 | audit_key | 0 | 5 |
| institutional_settlement_intelligence_runs | 3 | run_id | 0 | 5 |
| institutional_settlement_quarantine | 0 | quarantine_key | 0 | 5 |
| institutional_signal_feature_evaluations | 6 | evaluation_key | 0 | 2 |
| institutional_signal_learning_runs | 1 | run_id | 0 | 2 |
| institutional_signal_redundancy | 15 | redundancy_key | 0 | 2 |
| leaderboard_entries | 4496 | entry_key | 1 | 1 |
| leaderboard_snapshots | 18 | id | 0 | 1 |
| mapped_market_results | 116 | mapped_result_key | 0 | 12 |
| market_category_classifications | 0 | market_id | 0 | 2 |
| market_identifier_aliases | 7320 | alias_key | 1 | 3 |
| market_identifier_registry | 20590 | condition_id | 0 | 3 |
| market_identifier_runs | 2 | id | 0 | 1 |
| market_identifier_unmapped | 32480 | unmapped_key | 0 | 2 |
| market_identities | 1237 | canonical_key | 0 | 1 |
| market_identity_aliases | 6181 | alias_key | 0 | 1 |
| market_identity_enrichment_runs | 1 | id | 0 | 1 |
| market_identity_enrichments | 8358 | enrichment_key | 0 | 2 |
| market_identity_matches | 862 | source_key | 0 | 1 |
| market_identity_runs | 3 | id | 0 | 1 |
| market_identity_source_summary | 3 | source_table | 0 | 1 |
| market_leaders | 0 | id | 0 | 1 |
| market_lifecycle_manager_audit | 0 | id | 1 | 1 |
| market_lifecycle_manager_runs | 2 | run_id | 0 | 1 |
| market_mapper_runs | 1 | id | 0 | 1 |
| market_mapping_outcomes | 232 | mapping_outcome_key | 1 | 1 |
| market_mappings | 882 | mapping_key | 0 | 4 |
| market_memory_runs | 3 | id | 0 | 1 |
| market_memory_snapshots | 8282 | snapshot_key | 0 | 9 |
| market_memory_wallet_flows | 8875 | flow_key | 1 | 2 |
| market_metadata | 102 | market_id | 0 | 16 |
| market_opportunity_history | 5 | id | 0 | 1 |
| market_opportunity_runs | 4 | id | 0 | 1 |
| market_prediction_history | 38 | id | 0 | 1 |
| market_prediction_runs | 1 | id | 0 | 1 |
| market_predictions | 38 | prediction_key | 0 | 7 |
| market_price_history | 86 | id | 0 | 5 |
| market_price_metrics | 86 | market_id | 0 | 7 |
| market_resolution_outcomes | 41206 | resolution_outcome_key | 1 | 3 |
| market_resolution_runs | 1 | id | 0 | 1 |
| market_resolutions | 20603 | resolution_key | 0 | 6 |
| market_status_history | 141 | id | 1 | 3 |
| master_alerts | 1 | id | 0 | 3 |
| master_intelligence_dashboard | 40 | id | 0 | 1 |
| master_intelligence_dashboard_history | 122 | id | 0 | 1 |
| master_intelligence_dashboard_runs | 4 | id | 0 | 1 |
| master_opportunities | 131 | opportunity_key | 0 | 17 |
| master_opportunity_history | 131 | id | 0 | 2 |
| master_opportunity_runs | 1 | id | 0 | 1 |
| master_pipeline_runs | 5 | id | 0 | 2 |
| master_pipeline_step_runs | 17 | id | 1 | 1 |
| methodology_optimization_candidates | 162 | evaluation_key | 0 | 2 |
| methodology_optimization_runs | 1 | run_id | 0 | 2 |
| model_calibration_buckets | 30 | bucket_key | 0 | 2 |
| model_evaluation_metrics | 6 | evaluation_key | 0 | 2 |
| model_evaluation_runs | 1 | run_id | 0 | 2 |
| monitor_alerts | 0 | id | 1 | 2 |
| monitor_locks | 0 | lock_name | 0 | 2 |
| monitor_runs | 10 | id | 0 | 2 |
| monitor_settings | 12 | setting_key | 0 | 2 |
| official_wallet_activity | 141569 | activity_key | 0 | 7 |
| official_wallet_trades | 151182 | trade_key | 0 | 8 |
| opportunity_score_history | 501 | id | 0 | 1 |
| opportunity_scores | 131 | opportunity_key | 0 | 7 |
| performance_analytics_runs | 2 | run_id | 0 | 1 |
| platform_schema_migrations | 1 | migration_id | 0 | 1 |
| portfolio_overlap | 1763 | id | 0 | 8 |
| position_evolution | 345 | evolution_key | 0 | 12 |
| position_evolution_history | 345 | id | 0 | 1 |
| position_evolution_runs | 1 | id | 0 | 1 |
| positions | 23609 | id | 1 | 53 |
| price_history_runs | 1 | id | 0 | 1 |
| ranked_market_opportunities | 5 | opportunity_key | 0 | 5 |
| registry_validation_gate_results | 29196 | id | 1 | 1 |
| registry_validation_gate_runs | 5 | run_id | 0 | 1 |
| registry_validation_quarantine | 8872 | id | 0 | 1 |
| signal_fusion_alerts | 1 | id | 0 | 1 |
| signal_fusion_history | 131 | id | 0 | 1 |
| signal_fusion_runs | 1 | id | 0 | 1 |
| signal_fusion_scores | 131 | opportunity_key | 0 | 3 |
| signal_fusion_wallets | 179 | fusion_wallet_key | 1 | 1 |
| smart_money_flow_runs | 1 | id | 0 | 1 |
| smart_money_flow_signals | 38 | signal_key | 0 | 9 |
| smart_money_flow_wallet_events | 89 | event_key | 1 | 1 |
| tracked_markets | 102 | market_id | 1 | 4 |
| tracked_wallets | 26 | id | 0 | 2 |
| wallet_activity | 1148 | id | 2 | 3 |
| wallet_activity_checkpoints | 10 | wallet | 0 | 3 |
| wallet_activity_errors | 9 | id | 0 | 2 |
| wallet_activity_ingestion_runs | 2 | id | 0 | 2 |
| wallet_activity_snapshots | 1700 | id | 1 | 3 |
| wallet_alpha_components | 312 | component_key | 1 | 1 |
| wallet_alpha_history | 26 | id | 0 | 1 |
| wallet_alpha_profiles | 26 | wallet | 0 | 3 |
| wallet_alpha_runs | 1 | id | 0 | 1 |
| wallet_category_performance | 0 | wallet, category | 1 | 1 |
| wallet_category_specialties | 48 | wallet, category | 1 | 1 |
| wallet_closed_position_snapshots | 876 | id | 1 | 3 |
| wallet_cluster_members | 0 | id | 1 | 1 |
| wallet_clusters | 0 | id | 0 | 1 |
| wallet_current_position_snapshots | 2310 | id | 1 | 3 |
| wallet_discovery_events | 4496 | id | 0 | 1 |
| wallet_discovery_runs | 2 | run_id | 0 | 3 |
| wallet_discovery_runs_legacy_20260719_050932 | 2 | id | 0 | 0 |
| wallet_dna_categories | 51 | category_key | 1 | 2 |
| wallet_dna_history | 26 | id | 0 | 1 |
| wallet_dna_market_types | 100 | market_type_key | 1 | 1 |
| wallet_dna_profiles | 5 | wallet | 0 | 6 |
| wallet_dna_profiles_legacy_v1 | 26 | wallet | 0 | 0 |
| wallet_dna_runs | 2 | run_id | 0 | 2 |
| wallet_dna_runs_legacy_v1 | 1 | id | 0 | 0 |
| wallet_endpoint_support | 18 | support_key | 0 | 1 |
| wallet_influence_metrics | 0 | wallet | 1 | 1 |
| wallet_intelligence_profiles | 26 | wallet | 0 | 2 |
| wallet_intelligence_runs | 1 | id | 0 | 2 |
| wallet_intelligence_snapshots | 26 | id | 1 | 2 |
| wallet_leaderboard_snapshots | 60 | id | 1 | 2 |
| wallet_leaderboard_snapshots_backup_20260719_050932 | 0 | id | 1 | 0 |
| wallet_performance | 26 | wallet | 0 | 7 |
| wallet_performance_history | 52 | id | 0 | 1 |
| wallet_performance_markets | 16 | performance_market_key | 0 | 1 |
| wallet_performance_metrics | 6 | wallet | 0 | 2 |
| wallet_performance_runs | 2 | id | 0 | 1 |
| wallet_profile_collection_runs | 3 | run_id | 0 | 2 |
| wallet_profile_history | 529 | id | 0 | 3 |
| wallet_profiles | 29 | wallet | 0 | 11 |
| wallet_profiles_raw | 6 | wallet | 1 | 3 |
| wallet_rating_history | 1120 | id | 0 | 10 |
| wallet_registry | 923 | wallet | 0 | 6 |
| wallet_scans | 1134 | id | 0 | 32 |
| wallet_status_history | 1308 | id | 0 | 2 |
| wallet_trade_events | 17715 | trade_event_key | 0 | 1 |
| wallet_trade_ledger_history | 26 | id | 0 | 1 |
| wallet_trade_ledger_runs | 1 | id | 0 | 1 |
| wallet_trade_ledger_summary | 26 | wallet | 0 | 4 |
| wallet_trade_positions | 724 | position_key | 0 | 2 |
| wallet_trade_snapshots | 1700 | id | 1 | 3 |
| wallet_trust_history | 10 | id | 1 | 1 |
| wallet_trust_profiles | 10 | wallet | 0 | 6 |
| wallet_trust_runs | 3 | run_id | 0 | 1 |

## Tables

### `ai_reports`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | report_type | TEXT | True | — | 0 |
| 2 | report_title | TEXT | True | — | 0 |
| 3 | subject_type | TEXT | False | — | 0 |
| 4 | subject_id | TEXT | False | — | 0 |
| 5 | model_name | TEXT | False | — | 0 |
| 6 | report_text | TEXT | True | — | 0 |
| 7 | source_snapshot_time | TEXT | False | — | 0 |
| 8 | generated_at | TEXT | True | — | 0 |
| 9 | file_path | TEXT | False | — | 0 |
| 10 | token_usage | INTEGER | False | — | 0 |
| 11 | estimated_cost | REAL | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_ai_reports_generated_at | False | c | False | generated_at |
| idx_ai_reports_subject | False | c | False | subject_type, subject_id |
| idx_ai_reports_type | False | c | False | report_type |

#### Source References

- `src/intelligence_database.py:488,514,522,530,631`

#### Create SQL

```sql
CREATE TABLE ai_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            report_type TEXT NOT NULL,
            report_title TEXT NOT NULL,

            subject_type TEXT,
            subject_id TEXT,

            model_name TEXT,
            report_text TEXT NOT NULL,

            source_snapshot_time TEXT,
            generated_at TEXT NOT NULL,

            file_path TEXT,
            token_usage INTEGER,
            estimated_cost REAL
        )
```

### `alerts`

- Row count: `299`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | alert_key | TEXT | True | — | 0 |
| 2 | alert_type | TEXT | True | — | 0 |
| 3 | severity | TEXT | True | — | 0 |
| 4 | market_id | TEXT | True | — | 0 |
| 5 | title | TEXT | True | — | 0 |
| 6 | outcome | TEXT | True | — | 0 |
| 7 | message | TEXT | True | — | 0 |
| 8 | wallet_count | INTEGER | True | — | 0 |
| 9 | previous_wallet_count | INTEGER | False | — | 0 |
| 10 | combined_value | REAL | True | — | 0 |
| 11 | previous_combined_value | REAL | False | — | 0 |
| 12 | conviction_score | REAL | True | — | 0 |
| 13 | previous_conviction_score | REAL | False | — | 0 |
| 14 | observed_price_move | REAL | False | — | 0 |
| 15 | source_scanned_at | TEXT | True | — | 0 |
| 16 | created_at | TEXT | True | — | 0 |
| 17 | acknowledged | INTEGER | True | 0 | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_alerts_severity | False | c | False | severity |
| idx_alerts_market | False | c | False | market_id, outcome |
| idx_alerts_created_at | False | c | False | created_at |
| sqlite_autoindex_alerts_1 | True | u | False | alert_key |

#### Source References

- `src/alert_engine.py:61,87,94,101,320,322,341,356,369,382,389,391,431,454,472,489,503,524,539,552,556,560,569,576,590`
- `src/architecture_registry.py:325`
- `src/command_center.py:142,144,160,339,357,359,388,491,493,495,497,499,504,651,659,665,684`
- `src/dashboard.py:196,201,221,295,302,341,624,625,629,631,637,650,651,849,855,872,887,915,916`
- `src/dashboard_repository.py:364,374`
- `src/data_access.py:703,783`
- `src/intelligence_database.py:683`
- `src/market_monitor_database.py:211,499,638`
- `src/master_intelligence_dashboard_builder.py:270`
- `src/master_opportunity_engine.py:2267,2585`
- `src/platform_health.py:324,568,569`
- `src/signal_fusion_engine.py:3320,3599`
- `src/sports_live_listener.py:590,725,991,1096`

#### Create SQL

```sql
CREATE TABLE alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_key TEXT NOT NULL UNIQUE,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                message TEXT NOT NULL,
                wallet_count INTEGER NOT NULL,
                previous_wallet_count INTEGER,
                combined_value REAL NOT NULL,
                previous_combined_value REAL,
                conviction_score REAL NOT NULL,
                previous_conviction_score REAL,
                observed_price_move REAL,
                source_scanned_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                acknowledged INTEGER NOT NULL DEFAULT 0
            )
```

### `api_endpoint_tests`

- Row count: `144`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | test_key | TEXT | False | — | 1 |
| 1 | run_id | INTEGER | True | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | wallet_status | TEXT | False | — | 0 |
| 4 | test_name | TEXT | True | — | 0 |
| 5 | endpoint_path | TEXT | True | — | 0 |
| 6 | request_url | TEXT | True | — | 0 |
| 7 | request_params_json | TEXT | True | — | 0 |
| 8 | requested_limit | INTEGER | False | — | 0 |
| 9 | requested_offset | INTEGER | False | — | 0 |
| 10 | http_status | INTEGER | False | — | 0 |
| 11 | success | INTEGER | True | 0 | 0 |
| 12 | response_type | TEXT | False | — | 0 |
| 13 | response_count | INTEGER | False | — | 0 |
| 14 | response_bytes | INTEGER | True | 0 | 0 |
| 15 | elapsed_ms | REAL | False | — | 0 |
| 16 | error_type | TEXT | False | — | 0 |
| 17 | error_message | TEXT | False | — | 0 |
| 18 | response_body_preview | TEXT | False | — | 0 |
| 19 | response_headers_json | TEXT | False | — | 0 |
| 20 | tested_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| run_id | api_validation_runs | id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_api_endpoint_tests_endpoint | False | c | False | endpoint_path, http_status, success |
| idx_api_endpoint_tests_wallet | False | c | False | wallet, tested_at |
| sqlite_autoindex_api_endpoint_tests_1 | True | pk | False | test_key |

#### Source References

- `src/official_api_validator.py:180,208,211,655,1003`

#### Create SQL

```sql
CREATE TABLE api_endpoint_tests (
                test_key TEXT PRIMARY KEY,
                run_id INTEGER NOT NULL,
                wallet TEXT NOT NULL,
                wallet_status TEXT,
                test_name TEXT NOT NULL,
                endpoint_path TEXT NOT NULL,
                request_url TEXT NOT NULL,
                request_params_json TEXT NOT NULL,
                requested_limit INTEGER,
                requested_offset INTEGER,
                http_status INTEGER,
                success INTEGER NOT NULL DEFAULT 0,
                response_type TEXT,
                response_count INTEGER,
                response_bytes INTEGER NOT NULL DEFAULT 0,
                elapsed_ms REAL,
                error_type TEXT,
                error_message TEXT,
                response_body_preview TEXT,
                response_headers_json TEXT,
                tested_at TEXT NOT NULL,
                FOREIGN KEY(run_id)
                    REFERENCES api_validation_runs(id)
                    ON DELETE CASCADE
            )
```

### `api_pagination_probes`

- Row count: `122`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | probe_key | TEXT | False | — | 1 |
| 1 | run_id | INTEGER | True | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | endpoint_path | TEXT | True | — | 0 |
| 4 | requested_limit | INTEGER | True | — | 0 |
| 5 | requested_offset | INTEGER | True | — | 0 |
| 6 | http_status | INTEGER | False | — | 0 |
| 7 | success | INTEGER | True | 0 | 0 |
| 8 | response_count | INTEGER | False | — | 0 |
| 9 | response_bytes | INTEGER | True | 0 | 0 |
| 10 | elapsed_ms | REAL | False | — | 0 |
| 11 | error_type | TEXT | False | — | 0 |
| 12 | error_message | TEXT | False | — | 0 |
| 13 | response_body_preview | TEXT | False | — | 0 |
| 14 | probed_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| run_id | api_validation_runs | id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_api_pagination_probes_wallet | False | c | False | wallet, endpoint_path, requested_offset |
| sqlite_autoindex_api_pagination_probes_1 | True | pk | False | probe_key |

#### Source References

- `src/official_api_validator.py:238,260,733`

#### Create SQL

```sql
CREATE TABLE api_pagination_probes (
                probe_key TEXT PRIMARY KEY,
                run_id INTEGER NOT NULL,
                wallet TEXT NOT NULL,
                endpoint_path TEXT NOT NULL,
                requested_limit INTEGER NOT NULL,
                requested_offset INTEGER NOT NULL,
                http_status INTEGER,
                success INTEGER NOT NULL DEFAULT 0,
                response_count INTEGER,
                response_bytes INTEGER NOT NULL DEFAULT 0,
                elapsed_ms REAL,
                error_type TEXT,
                error_message TEXT,
                response_body_preview TEXT,
                probed_at TEXT NOT NULL,
                FOREIGN KEY(run_id)
                    REFERENCES api_validation_runs(id)
                    ON DELETE CASCADE
            )
```

### `api_validation_runs`

- Row count: `2`
- Referenced by: `api_endpoint_tests`, `api_pagination_probes`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | wallets_selected | INTEGER | True | 0 | 0 |
| 5 | endpoint_tests_planned | INTEGER | True | 0 | 0 |
| 6 | endpoint_tests_completed | INTEGER | True | 0 | 0 |
| 7 | successful_tests | INTEGER | True | 0 | 0 |
| 8 | failed_tests | INTEGER | True | 0 | 0 |
| 9 | pagination_probes | INTEGER | True | 0 | 0 |
| 10 | status | TEXT | True | — | 0 |
| 11 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/official_api_validator.py:165,203,255,565,604`

#### Create SQL

```sql
CREATE TABLE api_validation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,
                wallets_selected INTEGER NOT NULL DEFAULT 0,
                endpoint_tests_planned INTEGER NOT NULL DEFAULT 0,
                endpoint_tests_completed INTEGER NOT NULL DEFAULT 0,
                successful_tests INTEGER NOT NULL DEFAULT 0,
                failed_tests INTEGER NOT NULL DEFAULT 0,
                pagination_probes INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `backtest_results`

- Row count: `64`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | market_id | TEXT | True | — | 0 |
| 2 | title | TEXT | True | — | 0 |
| 3 | selected_outcome | TEXT | True | — | 0 |
| 4 | winning_outcome | TEXT | False | — | 0 |
| 5 | first_signal_at | TEXT | True | — | 0 |
| 6 | market_closed_at | TEXT | False | — | 0 |
| 7 | entry_price | REAL | True | — | 0 |
| 8 | conviction_score | REAL | True | — | 0 |
| 9 | conviction_grade | TEXT | True | — | 0 |
| 10 | wallet_count | INTEGER | True | — | 0 |
| 11 | hypothetical_stake | REAL | True | — | 0 |
| 12 | hypothetical_profit | REAL | False | — | 0 |
| 13 | hypothetical_return_pct | REAL | False | — | 0 |
| 14 | result_status | TEXT | True | — | 0 |
| 15 | evaluated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_backtest_results_score | False | c | False | conviction_score |
| idx_backtest_results_status | False | c | False | result_status |
| sqlite_autoindex_backtest_results_1 | True | u | False | market_id, selected_outcome, first_signal_at |

#### Source References

- `src/ai_research_engine.py:236`
- `src/backtesting_engine.py:114,144,152,322`
- `src/command_center.py:219,227`
- `src/dashboard.py:237,257,921`
- `src/decision_price_attribution_engine.py:13,57,809,821,846,849`
- `src/decision_price_attribution_engine_v10_backup.py:13,57,809,821,846,849`
- `src/decision_price_attribution_engine_v11_backup.py:13,57,809,821,846,849`
- `src/ml_ranking_engine.py:87,103`
- `src/opportunity_engine.py:476,1175`
- `src/platform_health.py:329`

#### Create SQL

```sql
CREATE TABLE backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                selected_outcome TEXT NOT NULL,
                winning_outcome TEXT,
                first_signal_at TEXT NOT NULL,
                market_closed_at TEXT,
                entry_price REAL NOT NULL,
                conviction_score REAL NOT NULL,
                conviction_grade TEXT NOT NULL,
                wallet_count INTEGER NOT NULL,
                hypothetical_stake REAL NOT NULL,
                hypothetical_profit REAL,
                hypothetical_return_pct REAL,
                result_status TEXT NOT NULL,
                evaluated_at TEXT NOT NULL,
                UNIQUE (
                    market_id,
                    selected_outcome,
                    first_signal_at
                )
            )
```

### `candidate_qualification_history`

- Row count: `4600`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | evaluation_score | REAL | False | — | 0 |
| 3 | evaluation_grade | TEXT | False | — | 0 |
| 4 | previous_status | TEXT | False | — | 0 |
| 5 | recommended_status | TEXT | False | — | 0 |
| 6 | resulting_status | TEXT | False | — | 0 |
| 7 | qualification_ready | INTEGER | False | — | 0 |
| 8 | needs_position_scan | INTEGER | False | — | 0 |
| 9 | needs_history_scan | INTEGER | False | — | 0 |
| 10 | analytical_evidence_score | REAL | False | — | 0 |
| 11 | leaderboard_appearances | INTEGER | False | — | 0 |
| 12 | alpha_score | REAL | False | — | 0 |
| 13 | elite_influence_score | REAL | False | — | 0 |
| 14 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_candidate_qualification_history_wallet | False | c | False | wallet, observed_at |

#### Source References

- `src/candidate_qualification_engine.py:359,385,1702,2244`

#### Create SQL

```sql
CREATE TABLE candidate_qualification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                wallet TEXT NOT NULL,

                evaluation_score REAL,
                evaluation_grade TEXT,

                previous_status TEXT,
                recommended_status TEXT,
                resulting_status TEXT,

                qualification_ready INTEGER,
                needs_position_scan INTEGER,
                needs_history_scan INTEGER,

                analytical_evidence_score REAL,
                leaderboard_appearances INTEGER,
                alpha_score REAL,
                elite_influence_score REAL,

                observed_at TEXT NOT NULL
            )
```

### `candidate_qualification_runs`

- Row count: `5`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | candidates_loaded | INTEGER | True | 0 | 0 |
| 5 | evaluations_saved | INTEGER | True | 0 | 0 |
| 6 | watchlist_recommendations | INTEGER | True | 0 | 0 |
| 7 | qualification_recommendations | INTEGER | True | 0 | 0 |
| 8 | candidates_promoted | INTEGER | True | 0 | 0 |
| 9 | protected_wallets_preserved | INTEGER | True | 0 | 0 |
| 10 | scan_required_count | INTEGER | True | 0 | 0 |
| 11 | manual_review_count | INTEGER | True | 0 | 0 |
| 12 | history_rows_saved | INTEGER | True | 0 | 0 |
| 13 | apply_status_changes | INTEGER | True | 0 | 0 |
| 14 | status | TEXT | True | — | 0 |
| 15 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/candidate_qualification_engine.py:390,1793,1838,2249`

#### Create SQL

```sql
CREATE TABLE candidate_qualification_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                candidates_loaded INTEGER
                    NOT NULL DEFAULT 0,

                evaluations_saved INTEGER
                    NOT NULL DEFAULT 0,

                watchlist_recommendations INTEGER
                    NOT NULL DEFAULT 0,

                qualification_recommendations INTEGER
                    NOT NULL DEFAULT 0,

                candidates_promoted INTEGER
                    NOT NULL DEFAULT 0,

                protected_wallets_preserved INTEGER
                    NOT NULL DEFAULT 0,

                scan_required_count INTEGER
                    NOT NULL DEFAULT 0,

                manual_review_count INTEGER
                    NOT NULL DEFAULT 0,

                history_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                apply_status_changes INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `candidate_wallet_evaluations`

- Row count: `920`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | evaluation_score | REAL | True | 0 | 0 |
| 2 | evaluation_grade | TEXT | True | 'PASS' | 0 |
| 3 | recommended_status | TEXT | True | 'CANDIDATE' | 0 |
| 4 | current_status | TEXT | True | 'CANDIDATE' | 0 |
| 5 | status_changed | INTEGER | True | 0 | 0 |
| 6 | qualification_ready | INTEGER | True | 0 | 0 |
| 7 | needs_position_scan | INTEGER | True | 1 | 0 |
| 8 | needs_history_scan | INTEGER | True | 1 | 0 |
| 9 | needs_manual_review | INTEGER | True | 0 | 0 |
| 10 | discovery_score | REAL | True | 0 | 0 |
| 11 | leaderboard_score | REAL | True | 0 | 0 |
| 12 | recurrence_score | REAL | True | 0 | 0 |
| 13 | rank_quality_score | REAL | True | 0 | 0 |
| 14 | pnl_quality_score | REAL | True | 0 | 0 |
| 15 | volume_quality_score | REAL | True | 0 | 0 |
| 16 | sports_relevance_score | REAL | True | 0 | 0 |
| 17 | analytical_evidence_score | REAL | True | 0 | 0 |
| 18 | alpha_score | REAL | False | — | 0 |
| 19 | alpha_grade | TEXT | False | — | 0 |
| 20 | alpha_confidence | TEXT | False | — | 0 |
| 21 | elite_influence_score | REAL | False | — | 0 |
| 22 | elite_tier | TEXT | False | — | 0 |
| 23 | performance_score | REAL | False | — | 0 |
| 24 | performance_grade | TEXT | False | — | 0 |
| 25 | dna_score | REAL | False | — | 0 |
| 26 | dna_grade | TEXT | False | — | 0 |
| 27 | ledger_quality_score | REAL | False | — | 0 |
| 28 | ledger_confidence | TEXT | False | — | 0 |
| 29 | trade_event_count | INTEGER | True | 0 | 0 |
| 30 | closed_position_count | INTEGER | True | 0 | 0 |
| 31 | resolved_positions | INTEGER | True | 0 | 0 |
| 32 | leaderboard_appearances | INTEGER | True | 0 | 0 |
| 33 | best_rank | INTEGER | False | — | 0 |
| 34 | weekly_pnl_appearances | INTEGER | True | 0 | 0 |
| 35 | weekly_volume_appearances | INTEGER | True | 0 | 0 |
| 36 | monthly_pnl_appearances | INTEGER | True | 0 | 0 |
| 37 | all_time_pnl_appearances | INTEGER | True | 0 | 0 |
| 38 | sports_appearances | INTEGER | True | 0 | 0 |
| 39 | latest_pnl | REAL | True | 0 | 0 |
| 40 | best_observed_pnl | REAL | True | 0 | 0 |
| 41 | latest_volume | REAL | True | 0 | 0 |
| 42 | highest_observed_volume | REAL | True | 0 | 0 |
| 43 | positive_evidence_count | INTEGER | True | 0 | 0 |
| 44 | risk_flag_count | INTEGER | True | 0 | 0 |
| 45 | positive_evidence_json | TEXT | False | — | 0 |
| 46 | risk_flags_json | TEXT | False | — | 0 |
| 47 | explanation_json | TEXT | False | — | 0 |
| 48 | evaluated_at | TEXT | True | — | 0 |
| 49 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_candidate_wallet_evaluations_status | False | c | False | recommended_status, qualification_ready, evaluation_score |
| idx_candidate_wallet_evaluations_score | False | c | False | evaluation_score |
| sqlite_autoindex_candidate_wallet_evaluations_1 | True | pk | False | wallet |

#### Source References

- `src/candidate_qualification_engine.py:220,347,353,1567,1581,2239`
- `src/official_api_validator.py:512`
- `src/official_wallet_activity_engine.py:367`
- `src/official_wallet_activity_engine_v2.py:899,904`

#### Create SQL

```sql
CREATE TABLE candidate_wallet_evaluations (
                wallet TEXT PRIMARY KEY,

                evaluation_score REAL
                    NOT NULL DEFAULT 0,

                evaluation_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                recommended_status TEXT
                    NOT NULL DEFAULT 'CANDIDATE',

                current_status TEXT
                    NOT NULL DEFAULT 'CANDIDATE',

                status_changed INTEGER
                    NOT NULL DEFAULT 0,

                qualification_ready INTEGER
                    NOT NULL DEFAULT 0,

                needs_position_scan INTEGER
                    NOT NULL DEFAULT 1,

                needs_history_scan INTEGER
                    NOT NULL DEFAULT 1,

                needs_manual_review INTEGER
                    NOT NULL DEFAULT 0,

                discovery_score REAL
                    NOT NULL DEFAULT 0,

                leaderboard_score REAL
                    NOT NULL DEFAULT 0,

                recurrence_score REAL
                    NOT NULL DEFAULT 0,

                rank_quality_score REAL
                    NOT NULL DEFAULT 0,

                pnl_quality_score REAL
                    NOT NULL DEFAULT 0,

                volume_quality_score REAL
                    NOT NULL DEFAULT 0,

                sports_relevance_score REAL
                    NOT NULL DEFAULT 0,

                analytical_evidence_score REAL
                    NOT NULL DEFAULT 0,

                alpha_score REAL,
                alpha_grade TEXT,
                alpha_confidence TEXT,

                elite_influence_score REAL,
                elite_tier TEXT,

                performance_score REAL,
                performance_grade TEXT,

                dna_score REAL,
                dna_grade TEXT,

                ledger_quality_score REAL,
                ledger_confidence TEXT,

                trade_event_count INTEGER
                    NOT NULL DEFAULT 0,

                closed_position_count INTEGER
                    NOT NULL DEFAULT 0,

                resolved_positions INTEGER
                    NOT NULL DEFAULT 0,

                leaderboard_appearances INTEGER
                    NOT NULL DEFAULT 0,

                best_rank INTEGER,

                weekly_pnl_appearances INTEGER
                    NOT NULL DEFAULT 0,

                weekly_volume_appearances INTEGER
                    NOT NULL DEFAULT 0,

                monthly_pnl_appearances INTEGER
                    NOT NULL DEFAULT 0,

                all_time_pnl_appearances INTEGER
                    NOT NULL DEFAULT 0,

                sports_appearances INTEGER
                    NOT NULL DEFAULT 0,

                latest_pnl REAL
                    NOT NULL DEFAULT 0,

                best_observed_pnl REAL
                    NOT NULL DEFAULT 0,

                latest_volume REAL
                    NOT NULL DEFAULT 0,

                highest_observed_volume REAL
                    NOT NULL DEFAULT 0,

                positive_evidence_count INTEGER
                    NOT NULL DEFAULT 0,

                risk_flag_count INTEGER
                    NOT NULL DEFAULT 0,

                positive_evidence_json TEXT,
                risk_flags_json TEXT,
                explanation_json TEXT,

                evaluated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `canonical_backfill_audit`

- Row count: `1175`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | market_id | TEXT | True | — | 0 |
| 3 | title | TEXT | False | — | 0 |
| 4 | action | TEXT | True | — | 0 |
| 5 | status | TEXT | True | — | 0 |
| 6 | reason_code | TEXT | True | — | 0 |
| 7 | reason_detail | TEXT | False | — | 0 |
| 8 | source_rowid | INTEGER | False | — | 0 |
| 9 | active | INTEGER | True | 0 | 0 |
| 10 | closed | INTEGER | True | 0 | 0 |
| 11 | archived | INTEGER | True | 0 | 0 |
| 12 | restricted | INTEGER | True | 0 | 0 |
| 13 | accepting_orders | INTEGER | True | 0 | 0 |
| 14 | tradable_identity | INTEGER | True | 0 | 0 |
| 15 | audited_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| run_id | canonical_backfill_runs | run_id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_canonical_backfill_audit_status | False | c | False | status, audited_at |
| idx_canonical_backfill_audit_market | False | c | False | market_id, audited_at |

#### Source References

- `src/canonical_backfill_engine.py:25`

#### Create SQL

```sql
CREATE TABLE "canonical_backfill_audit" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    title TEXT,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    reason_detail TEXT,
                    source_rowid INTEGER,
                    active INTEGER NOT NULL DEFAULT 0,
                    closed INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 0,
                    restricted INTEGER NOT NULL DEFAULT 0,
                    accepting_orders INTEGER NOT NULL DEFAULT 0,
                    tradable_identity INTEGER NOT NULL DEFAULT 0,
                    audited_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES "canonical_backfill_runs"(run_id)
                        ON DELETE CASCADE
                )
```

### `canonical_backfill_runs`

- Row count: `7`
- Referenced by: `canonical_backfill_audit`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | mode | TEXT | True | — | 0 |
| 5 | canonical_before | INTEGER | True | 0 | 0 |
| 6 | legacy_total | INTEGER | True | 0 | 0 |
| 7 | candidate_count | INTEGER | True | 0 | 0 |
| 8 | inserted_count | INTEGER | True | 0 | 0 |
| 9 | skipped_count | INTEGER | True | 0 | 0 |
| 10 | unresolved_required_columns | INTEGER | True | 0 | 0 |
| 11 | mapping_json | TEXT | False | — | 0 |
| 12 | status | TEXT | True | — | 0 |
| 13 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_canonical_backfill_runs_1 | True | pk | False | run_id |

#### Source References

- `src/canonical_backfill_engine.py:24`

#### Create SQL

```sql
CREATE TABLE "canonical_backfill_runs" (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    elapsed_seconds REAL,
                    mode TEXT NOT NULL,
                    canonical_before INTEGER NOT NULL DEFAULT 0,
                    legacy_total INTEGER NOT NULL DEFAULT 0,
                    candidate_count INTEGER NOT NULL DEFAULT 0,
                    inserted_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    unresolved_required_columns INTEGER NOT NULL DEFAULT 0,
                    mapping_json TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
```

### `canonical_coverage_audit`

- Row count: `262`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | opportunity_rowid | INTEGER | False | — | 0 |
| 3 | opportunity_condition_id | TEXT | False | — | 0 |
| 4 | opportunity_outcome | TEXT | False | — | 0 |
| 5 | opportunity_title | TEXT | False | — | 0 |
| 6 | opportunity_slug | TEXT | False | — | 0 |
| 7 | opportunity_gamma_id | TEXT | False | — | 0 |
| 8 | coverage_status | TEXT | True | — | 0 |
| 9 | diagnosis | TEXT | True | — | 0 |
| 10 | canonical_condition_id | TEXT | False | — | 0 |
| 11 | canonical_title | TEXT | False | — | 0 |
| 12 | evidence_json | TEXT | True | '{}' | 0 |
| 13 | created_at | TEXT | True | — | 0 |
| 14 | schema_version | INTEGER | True | 1 | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_coverage_audit_condition | False | c | False | opportunity_condition_id |
| idx_coverage_audit_status | False | c | False | coverage_status, diagnosis |
| idx_coverage_audit_run | False | c | False | run_id |

#### Source References

- `src/canonical_coverage_audit.py:23`

#### Create SQL

```sql
CREATE TABLE canonical_coverage_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                opportunity_rowid INTEGER,
                opportunity_condition_id TEXT,
                opportunity_outcome TEXT,
                opportunity_title TEXT,
                opportunity_slug TEXT,
                opportunity_gamma_id TEXT,
                coverage_status TEXT NOT NULL,
                diagnosis TEXT NOT NULL,
                canonical_condition_id TEXT,
                canonical_title TEXT,
                evidence_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 1
            )
```

### `canonical_coverage_audit_runs`

- Row count: `2`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | started_at | TEXT | True | — | 0 |
| 3 | finished_at | TEXT | False | — | 0 |
| 4 | duration_seconds | REAL | False | — | 0 |
| 5 | canonical_rows | INTEGER | True | 0 | 0 |
| 6 | canonical_unique_markets | INTEGER | True | 0 | 0 |
| 7 | tradable_canonical_markets | INTEGER | True | 0 | 0 |
| 8 | opportunity_rows | INTEGER | True | 0 | 0 |
| 9 | opportunity_unique_markets | INTEGER | True | 0 | 0 |
| 10 | matched_opportunity_rows | INTEGER | True | 0 | 0 |
| 11 | orphaned_opportunity_rows | INTEGER | True | 0 | 0 |
| 12 | matched_unique_markets | INTEGER | True | 0 | 0 |
| 13 | orphaned_unique_markets | INTEGER | True | 0 | 0 |
| 14 | canonical_without_opportunities | INTEGER | True | 0 | 0 |
| 15 | tradable_without_opportunities | INTEGER | True | 0 | 0 |
| 16 | coverage_percent_rows | REAL | True | 0 | 0 |
| 17 | coverage_percent_unique_markets | REAL | True | 0 | 0 |
| 18 | likely_pipeline_bypass_rows | INTEGER | True | 0 | 0 |
| 19 | likely_missing_canonical_import_rows | INTEGER | True | 0 | 0 |
| 20 | indeterminate_rows | INTEGER | True | 0 | 0 |
| 21 | duplicate_opportunity_groups | INTEGER | True | 0 | 0 |
| 22 | error_count | INTEGER | True | 0 | 0 |
| 23 | success | INTEGER | False | — | 0 |
| 24 | status | TEXT | True | 'RUNNING' | 0 |
| 25 | details_json | TEXT | True | '{}' | 0 |
| 26 | schema_version | INTEGER | True | 1 | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_coverage_runs_started | False | c | False | started_at |
| sqlite_autoindex_canonical_coverage_audit_runs_1 | True | u | False | run_id |

#### Source References

- `src/canonical_coverage_audit.py:24`

#### Create SQL

```sql
CREATE TABLE canonical_coverage_audit_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL,
                canonical_rows INTEGER NOT NULL DEFAULT 0,
                canonical_unique_markets INTEGER NOT NULL DEFAULT 0,
                tradable_canonical_markets INTEGER NOT NULL DEFAULT 0,
                opportunity_rows INTEGER NOT NULL DEFAULT 0,
                opportunity_unique_markets INTEGER NOT NULL DEFAULT 0,
                matched_opportunity_rows INTEGER NOT NULL DEFAULT 0,
                orphaned_opportunity_rows INTEGER NOT NULL DEFAULT 0,
                matched_unique_markets INTEGER NOT NULL DEFAULT 0,
                orphaned_unique_markets INTEGER NOT NULL DEFAULT 0,
                canonical_without_opportunities INTEGER NOT NULL DEFAULT 0,
                tradable_without_opportunities INTEGER NOT NULL DEFAULT 0,
                coverage_percent_rows REAL NOT NULL DEFAULT 0,
                coverage_percent_unique_markets REAL NOT NULL DEFAULT 0,
                likely_pipeline_bypass_rows INTEGER NOT NULL DEFAULT 0,
                likely_missing_canonical_import_rows INTEGER NOT NULL DEFAULT 0,
                indeterminate_rows INTEGER NOT NULL DEFAULT 0,
                duplicate_opportunity_groups INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                success INTEGER,
                status TEXT NOT NULL DEFAULT 'RUNNING',
                details_json TEXT NOT NULL DEFAULT '{}',
                schema_version INTEGER NOT NULL DEFAULT 1
            )
```

### `canonical_identity_refresh_audit`

- Row count: `300`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | condition_id | TEXT | False | — | 0 |
| 3 | action | TEXT | True | — | 0 |
| 4 | changed_columns_json | TEXT | True | '[]' | 0 |
| 5 | source_json | TEXT | True | '{}' | 0 |
| 6 | error_message | TEXT | False | — | 0 |
| 7 | created_at | TEXT | True | — | 0 |
| 8 | schema_version | INTEGER | True | 1 | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_identity_refresh_audit_condition | False | c | False | condition_id |
| idx_identity_refresh_audit_run | False | c | False | run_id |

#### Source References

- `src/canonical_identity_refresh_engine.py:26`

#### Create SQL

```sql
CREATE TABLE canonical_identity_refresh_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                condition_id TEXT,
                action TEXT NOT NULL,
                changed_columns_json TEXT NOT NULL DEFAULT '[]',
                source_json TEXT NOT NULL DEFAULT '{}',
                error_message TEXT,
                created_at TEXT NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 1
            )
```

### `canonical_identity_refresh_runs`

- Row count: `3`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | started_at | TEXT | True | — | 0 |
| 3 | finished_at | TEXT | False | — | 0 |
| 4 | duration_seconds | REAL | False | — | 0 |
| 5 | fetched_rows | INTEGER | True | 0 | 0 |
| 6 | normalized_rows | INTEGER | True | 0 | 0 |
| 7 | unique_condition_ids | INTEGER | True | 0 | 0 |
| 8 | inserted_rows | INTEGER | True | 0 | 0 |
| 9 | updated_rows | INTEGER | True | 0 | 0 |
| 10 | unchanged_rows | INTEGER | True | 0 | 0 |
| 11 | archived_rows | INTEGER | True | 0 | 0 |
| 12 | skipped_rows | INTEGER | True | 0 | 0 |
| 13 | duplicate_source_rows | INTEGER | True | 0 | 0 |
| 14 | error_count | INTEGER | True | 0 | 0 |
| 15 | success | INTEGER | False | — | 0 |
| 16 | status | TEXT | True | 'RUNNING' | 0 |
| 17 | details_json | TEXT | True | '{}' | 0 |
| 18 | schema_version | INTEGER | True | 1 | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_identity_refresh_runs_started | False | c | False | started_at |
| sqlite_autoindex_canonical_identity_refresh_runs_1 | True | u | False | run_id |

#### Source References

- `src/canonical_identity_refresh_engine.py:25`

#### Create SQL

```sql
CREATE TABLE canonical_identity_refresh_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL,
                fetched_rows INTEGER NOT NULL DEFAULT 0,
                normalized_rows INTEGER NOT NULL DEFAULT 0,
                unique_condition_ids INTEGER NOT NULL DEFAULT 0,
                inserted_rows INTEGER NOT NULL DEFAULT 0,
                updated_rows INTEGER NOT NULL DEFAULT 0,
                unchanged_rows INTEGER NOT NULL DEFAULT 0,
                archived_rows INTEGER NOT NULL DEFAULT 0,
                skipped_rows INTEGER NOT NULL DEFAULT 0,
                duplicate_source_rows INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                success INTEGER,
                status TEXT NOT NULL DEFAULT 'RUNNING',
                details_json TEXT NOT NULL DEFAULT '{}',
                schema_version INTEGER NOT NULL DEFAULT 1
            )
```

### `canonical_identity_sync_audit`

- Row count: `262`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | opportunity_rowid | INTEGER | False | — | 0 |
| 3 | source_market_id | TEXT | False | — | 0 |
| 4 | source_outcome | TEXT | False | — | 0 |
| 5 | status | TEXT | True | — | 0 |
| 6 | canonical_condition_id | TEXT | False | — | 0 |
| 7 | match_method | TEXT | False | — | 0 |
| 8 | match_value | TEXT | False | — | 0 |
| 9 | confidence | REAL | True | 0 | 0 |
| 10 | repaired | INTEGER | True | 0 | 0 |
| 11 | details_json | TEXT | True | '{}' | 0 |
| 12 | created_at | TEXT | True | — | 0 |
| 13 | schema_version | INTEGER | True | 1 | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_sync_audit_status | False | c | False | status |
| idx_sync_audit_run | False | c | False | run_id |

#### Source References

- `src/canonical_identity_synchronizer.py:24`

#### Create SQL

```sql
CREATE TABLE canonical_identity_sync_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                opportunity_rowid INTEGER,
                source_market_id TEXT,
                source_outcome TEXT,
                status TEXT NOT NULL,
                canonical_condition_id TEXT,
                match_method TEXT,
                match_value TEXT,
                confidence REAL NOT NULL DEFAULT 0,
                repaired INTEGER NOT NULL DEFAULT 0,
                details_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 1
            )
```

### `canonical_identity_sync_runs`

- Row count: `2`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | started_at | TEXT | True | — | 0 |
| 3 | finished_at | TEXT | False | — | 0 |
| 4 | duration_seconds | REAL | False | — | 0 |
| 5 | source_rows | INTEGER | True | 0 | 0 |
| 6 | resolved_rows | INTEGER | True | 0 | 0 |
| 7 | already_canonical_rows | INTEGER | True | 0 | 0 |
| 8 | repaired_rows | INTEGER | True | 0 | 0 |
| 9 | ambiguous_rows | INTEGER | True | 0 | 0 |
| 10 | orphaned_rows | INTEGER | True | 0 | 0 |
| 11 | skipped_rows | INTEGER | True | 0 | 0 |
| 12 | error_count | INTEGER | True | 0 | 0 |
| 13 | success | INTEGER | False | — | 0 |
| 14 | status | TEXT | True | 'RUNNING' | 0 |
| 15 | error_message | TEXT | False | — | 0 |
| 16 | details_json | TEXT | True | '{}' | 0 |
| 17 | schema_version | INTEGER | True | 1 | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_sync_runs_started | False | c | False | started_at |
| sqlite_autoindex_canonical_identity_sync_runs_1 | True | u | False | run_id |

#### Source References

- `src/canonical_identity_synchronizer.py:25`

#### Create SQL

```sql
CREATE TABLE canonical_identity_sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL,
                source_rows INTEGER NOT NULL DEFAULT 0,
                resolved_rows INTEGER NOT NULL DEFAULT 0,
                already_canonical_rows INTEGER NOT NULL DEFAULT 0,
                repaired_rows INTEGER NOT NULL DEFAULT 0,
                ambiguous_rows INTEGER NOT NULL DEFAULT 0,
                orphaned_rows INTEGER NOT NULL DEFAULT 0,
                skipped_rows INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                success INTEGER,
                status TEXT NOT NULL DEFAULT 'RUNNING',
                error_message TEXT,
                details_json TEXT NOT NULL DEFAULT '{}',
                schema_version INTEGER NOT NULL DEFAULT 1
            )
```

### `canonical_market_identities`

- Row count: `21765`
- Referenced by: `canonical_market_identity_aliases`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | condition_id | TEXT | False | — | 1 |
| 1 | gamma_market_id | TEXT | True | — | 0 |
| 2 | gamma_event_id | TEXT | False | — | 0 |
| 3 | question_id | TEXT | False | — | 0 |
| 4 | question | TEXT | True | — | 0 |
| 5 | description | TEXT | False | — | 0 |
| 6 | market_slug | TEXT | False | — | 0 |
| 7 | event_slug | TEXT | False | — | 0 |
| 8 | category | TEXT | False | — | 0 |
| 9 | subcategory | TEXT | False | — | 0 |
| 10 | market_type | TEXT | False | — | 0 |
| 11 | yes_token_id | TEXT | False | — | 0 |
| 12 | no_token_id | TEXT | False | — | 0 |
| 13 | yes_outcome_name | TEXT | False | — | 0 |
| 14 | no_outcome_name | TEXT | False | — | 0 |
| 15 | yes_implied_price | REAL | False | — | 0 |
| 16 | no_implied_price | REAL | False | — | 0 |
| 17 | polymarket_url | TEXT | False | — | 0 |
| 18 | url_source | TEXT | False | — | 0 |
| 19 | start_time | TEXT | False | — | 0 |
| 20 | end_time | TEXT | False | — | 0 |
| 21 | game_start_time | TEXT | False | — | 0 |
| 22 | time_status | TEXT | False | — | 0 |
| 23 | t_minus_target_at | TEXT | False | — | 0 |
| 24 | t_minus_seconds | INTEGER | False | — | 0 |
| 25 | t_minus_display | TEXT | False | — | 0 |
| 26 | active | INTEGER | True | 0 | 0 |
| 27 | closed | INTEGER | True | 0 | 0 |
| 28 | archived | INTEGER | True | 0 | 0 |
| 29 | resolved | INTEGER | True | 0 | 0 |
| 30 | restricted | INTEGER | True | 0 | 0 |
| 31 | accepting_orders | INTEGER | True | 0 | 0 |
| 32 | liquidity | REAL | True | 0 | 0 |
| 33 | volume | REAL | True | 0 | 0 |
| 34 | volume_24h | REAL | True | 0 | 0 |
| 35 | open_interest | REAL | True | 0 | 0 |
| 36 | spread | REAL | False | — | 0 |
| 37 | mapping_method | TEXT | False | — | 0 |
| 38 | mapping_confidence | REAL | True | 0 | 0 |
| 39 | registry_verified | INTEGER | True | 0 | 0 |
| 40 | identity_complete | INTEGER | True | 0 | 0 |
| 41 | tradable_identity | INTEGER | True | 0 | 0 |
| 42 | missing_fields_json | TEXT | False | — | 0 |
| 43 | source_tables_json | TEXT | False | — | 0 |
| 44 | metadata_json | TEXT | False | — | 0 |
| 45 | first_built_at | TEXT | True | — | 0 |
| 46 | last_built_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_canonical_market_identities_tokens | False | c | False | yes_token_id, no_token_id |
| idx_canonical_market_identities_event | False | c | False | gamma_event_id, event_slug |
| idx_canonical_market_identities_tradable | False | c | False | tradable_identity, active, mapping_confidence |
| sqlite_autoindex_canonical_market_identities_1 | True | pk | False | condition_id |

#### Source References

- `src/architecture_registry.py:428`
- `src/canonical_backfill_engine.py:27,287,849,1122`
- `src/canonical_coverage_audit.py:21,858`
- `src/canonical_identity_refresh_engine.py:24,1070`
- `src/canonical_identity_synchronizer.py:21`
- `src/canonical_market_identity_engine.py:313,381,389,396,420,1098,1115,1483,1499`
- `src/canonical_market_repository.py:18,137`
- `src/dashboard_schema_audit.py:12`
- `src/data_access.py:254,261,271,276,291,315,347,790`
- `src/historical_market_reconciliation_engine.py:21`
- `src/inspect_canonical_tradability.py:8`
- `src/institutional_decision_engine.py:41`
- `src/institutional_decision_engine_v2.py:56`
- `src/institutional_decision_engine_v2_baseline.py:56`
- `src/institutional_decision_engine_v2_v20_backup.py:56`
- `src/institutional_decision_engine_v2_v21_backup.py:56`
- `src/market_lifecycle_manager.py:27,492,590`
- `src/registry_validation_gate.py:505,552,570`

#### Create SQL

```sql
CREATE TABLE canonical_market_identities (
                condition_id TEXT PRIMARY KEY,

                gamma_market_id TEXT NOT NULL,
                gamma_event_id TEXT,

                question_id TEXT,
                question TEXT NOT NULL,
                description TEXT,

                market_slug TEXT,
                event_slug TEXT,

                category TEXT,
                subcategory TEXT,
                market_type TEXT,

                yes_token_id TEXT,
                no_token_id TEXT,

                yes_outcome_name TEXT,
                no_outcome_name TEXT,

                yes_implied_price REAL,
                no_implied_price REAL,

                polymarket_url TEXT,
                url_source TEXT,

                start_time TEXT,
                end_time TEXT,
                game_start_time TEXT,

                time_status TEXT,
                t_minus_target_at TEXT,
                t_minus_seconds INTEGER,
                t_minus_display TEXT,

                active INTEGER NOT NULL DEFAULT 0,
                closed INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                resolved INTEGER NOT NULL DEFAULT 0,
                restricted INTEGER NOT NULL DEFAULT 0,
                accepting_orders INTEGER NOT NULL DEFAULT 0,

                liquidity REAL NOT NULL DEFAULT 0,
                volume REAL NOT NULL DEFAULT 0,
                volume_24h REAL NOT NULL DEFAULT 0,
                open_interest REAL NOT NULL DEFAULT 0,
                spread REAL,

                mapping_method TEXT,
                mapping_confidence REAL NOT NULL DEFAULT 0,
                registry_verified INTEGER NOT NULL DEFAULT 0,

                identity_complete INTEGER NOT NULL DEFAULT 0,
                tradable_identity INTEGER NOT NULL DEFAULT 0,

                missing_fields_json TEXT,
                source_tables_json TEXT,
                metadata_json TEXT,

                first_built_at TEXT NOT NULL,
                last_built_at TEXT NOT NULL
            )
```

### `canonical_market_identity_aliases`

- Row count: `7320`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | alias_key | TEXT | False | — | 1 |
| 1 | condition_id | TEXT | True | — | 0 |
| 2 | alias_type | TEXT | True | — | 0 |
| 3 | alias_value | TEXT | True | — | 0 |
| 4 | normalized_alias_value | TEXT | True | — | 0 |
| 5 | verified | INTEGER | True | 0 | 0 |
| 6 | confidence | REAL | True | 0 | 0 |
| 7 | source_table | TEXT | True | — | 0 |
| 8 | source_row_identifier | TEXT | False | — | 0 |
| 9 | created_at | TEXT | True | — | 0 |
| 10 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| condition_id | canonical_market_identities | condition_id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_canonical_market_identity_aliases_lookup | False | c | False | alias_type, normalized_alias_value, verified, confidence |
| sqlite_autoindex_canonical_market_identity_aliases_1 | True | pk | False | alias_key |

#### Source References

- `src/canonical_market_identity_engine.py:401,426,1103,1111,1488`

#### Create SQL

```sql
CREATE TABLE canonical_market_identity_aliases (
                alias_key TEXT PRIMARY KEY,

                condition_id TEXT NOT NULL,

                alias_type TEXT NOT NULL,
                alias_value TEXT NOT NULL,
                normalized_alias_value TEXT NOT NULL,

                verified INTEGER NOT NULL DEFAULT 0,
                confidence REAL NOT NULL DEFAULT 0,

                source_table TEXT NOT NULL,
                source_row_identifier TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(condition_id)
                    REFERENCES canonical_market_identities(condition_id)
                    ON DELETE CASCADE
            )
```

### `canonical_market_identity_runs`

- Row count: `3`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | registry_rows_loaded | INTEGER | True | 0 | 0 |
| 5 | identities_saved | INTEGER | True | 0 | 0 |
| 6 | complete_identities | INTEGER | True | 0 | 0 |
| 7 | tradable_identities | INTEGER | True | 0 | 0 |
| 8 | aliases_saved | INTEGER | True | 0 | 0 |
| 9 | missing_url_count | INTEGER | True | 0 | 0 |
| 10 | missing_time_count | INTEGER | True | 0 | 0 |
| 11 | missing_token_count | INTEGER | True | 0 | 0 |
| 12 | status | TEXT | True | — | 0 |
| 13 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/canonical_market_identity_engine.py:433,1160,1192,1493`
- `src/inspect_canonical_tradability.py:9`

#### Create SQL

```sql
CREATE TABLE canonical_market_identity_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                registry_rows_loaded INTEGER NOT NULL DEFAULT 0,
                identities_saved INTEGER NOT NULL DEFAULT 0,
                complete_identities INTEGER NOT NULL DEFAULT 0,
                tradable_identities INTEGER NOT NULL DEFAULT 0,
                aliases_saved INTEGER NOT NULL DEFAULT 0,

                missing_url_count INTEGER NOT NULL DEFAULT 0,
                missing_time_count INTEGER NOT NULL DEFAULT 0,
                missing_token_count INTEGER NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `closing_line_history`

- Row count: `87`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | opportunity_key | TEXT | True | — | 0 |
| 2 | market_id | TEXT | True | — | 0 |
| 3 | title | TEXT | True | — | 0 |
| 4 | outcome | TEXT | True | — | 0 |
| 5 | current_price | REAL | True | — | 0 |
| 6 | weighted_average_entry | REAL | False | — | 0 |
| 7 | weighted_average_elite_entry | REAL | False | — | 0 |
| 8 | highest_observed_price | REAL | False | — | 0 |
| 9 | lowest_observed_price | REAL | False | — | 0 |
| 10 | price_move_from_entry | REAL | False | — | 0 |
| 11 | price_move_from_elite_entry | REAL | False | — | 0 |
| 12 | relative_move_from_entry | REAL | False | — | 0 |
| 13 | relative_move_from_elite_entry | REAL | False | — | 0 |
| 14 | gross_edge_remaining | REAL | False | — | 0 |
| 15 | edge_remaining_ratio | REAL | False | — | 0 |
| 16 | move_consumed_ratio | REAL | False | — | 0 |
| 17 | clv_points | REAL | False | — | 0 |
| 18 | clv_relative | REAL | False | — | 0 |
| 19 | clv_score | REAL | False | — | 0 |
| 20 | steam_score | REAL | False | — | 0 |
| 21 | reversal_score | REAL | False | — | 0 |
| 22 | volatility_score | REAL | False | — | 0 |
| 23 | movement_status | TEXT | False | — | 0 |
| 24 | market_speed | TEXT | False | — | 0 |
| 25 | steam_stage | TEXT | False | — | 0 |
| 26 | lifecycle_status | TEXT | False | — | 0 |
| 27 | seconds_to_start | INTEGER | False | — | 0 |
| 28 | wallet_count | INTEGER | False | — | 0 |
| 29 | elite_wallet_count | INTEGER | False | — | 0 |
| 30 | data_completeness_score | REAL | False | — | 0 |
| 31 | data_confidence | TEXT | False | — | 0 |
| 32 | chase_risk_score | REAL | False | — | 0 |
| 33 | edge_remaining_score | REAL | False | — | 0 |
| 34 | recommendation | TEXT | False | — | 0 |
| 35 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_closing_history_key | False | c | False | opportunity_key, observed_at |

#### Source References

- `src/closing_line_engine.py:218,258,1053,1156,1280`
- `src/decision_price_attribution_engine.py:9,53,565,578,603,606`
- `src/decision_price_attribution_engine_v10_backup.py:9,53,565,578,603,606`
- `src/decision_price_attribution_engine_v11_backup.py:9,53,565,578,603,606`

#### Create SQL

```sql
CREATE TABLE closing_line_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opportunity_key TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                current_price REAL NOT NULL,
                weighted_average_entry REAL,
                weighted_average_elite_entry REAL,
                highest_observed_price REAL,
                lowest_observed_price REAL,
                price_move_from_entry REAL,
                price_move_from_elite_entry REAL,
                relative_move_from_entry REAL,
                relative_move_from_elite_entry REAL,
                gross_edge_remaining REAL,
                edge_remaining_ratio REAL,
                move_consumed_ratio REAL,
                clv_points REAL,
                clv_relative REAL,
                clv_score REAL,
                steam_score REAL,
                reversal_score REAL,
                volatility_score REAL,
                movement_status TEXT,
                market_speed TEXT,
                steam_stage TEXT,
                lifecycle_status TEXT,
                seconds_to_start INTEGER,
                wallet_count INTEGER,
                elite_wallet_count INTEGER,
                data_completeness_score REAL,
                data_confidence TEXT,
                chase_risk_score REAL,
                edge_remaining_score REAL,
                recommendation TEXT,
                observed_at TEXT NOT NULL
            )
```

### `closing_line_metrics`

- Row count: `87`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | opportunity_key | TEXT | False | — | 1 |
| 1 | market_id | TEXT | True | — | 0 |
| 2 | title | TEXT | True | — | 0 |
| 3 | outcome | TEXT | True | — | 0 |
| 4 | current_price | REAL | True | — | 0 |
| 5 | first_wallet_entry | REAL | False | — | 0 |
| 6 | first_elite_entry | REAL | False | — | 0 |
| 7 | weighted_average_entry | REAL | False | — | 0 |
| 8 | weighted_average_elite_entry | REAL | False | — | 0 |
| 9 | best_observed_entry | REAL | False | — | 0 |
| 10 | worst_observed_entry | REAL | False | — | 0 |
| 11 | highest_observed_price | REAL | False | — | 0 |
| 12 | lowest_observed_price | REAL | False | — | 0 |
| 13 | price_move_from_entry | REAL | False | — | 0 |
| 14 | price_move_from_elite_entry | REAL | False | — | 0 |
| 15 | relative_move_from_entry | REAL | False | — | 0 |
| 16 | relative_move_from_elite_entry | REAL | False | — | 0 |
| 17 | gross_edge_at_entry | REAL | False | — | 0 |
| 18 | gross_edge_remaining | REAL | False | — | 0 |
| 19 | edge_remaining_ratio | REAL | False | — | 0 |
| 20 | move_consumed_ratio | REAL | False | — | 0 |
| 21 | clv_points | REAL | False | — | 0 |
| 22 | clv_relative | REAL | False | — | 0 |
| 23 | clv_score | REAL | False | — | 0 |
| 24 | steam_score | REAL | False | — | 0 |
| 25 | reversal_score | REAL | False | — | 0 |
| 26 | volatility_score | REAL | False | — | 0 |
| 27 | movement_status | TEXT | False | — | 0 |
| 28 | entry_age_seconds | INTEGER | False | — | 0 |
| 29 | elite_entry_age_seconds | INTEGER | False | — | 0 |
| 30 | market_speed | TEXT | False | — | 0 |
| 31 | steam_stage | TEXT | False | — | 0 |
| 32 | lifecycle_status | TEXT | False | — | 0 |
| 33 | seconds_to_start | INTEGER | False | — | 0 |
| 34 | wallet_count | INTEGER | True | 0 | 0 |
| 35 | elite_wallet_count | INTEGER | True | 0 | 0 |
| 36 | data_completeness_score | REAL | True | 0 | 0 |
| 37 | data_confidence | TEXT | True | 'LOW' | 0 |
| 38 | chase_risk_score | REAL | True | 0 | 0 |
| 39 | edge_remaining_score | REAL | True | 0 | 0 |
| 40 | recommendation | TEXT | True | 'WATCH' | 0 |
| 41 | explanation_json | TEXT | False | — | 0 |
| 42 | calculated_at | TEXT | True | — | 0 |
| 43 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_closing_metrics_rec | False | c | False | recommendation, clv_score |
| idx_closing_metrics_edge | False | c | False | edge_remaining_score |
| sqlite_autoindex_closing_line_metrics_1 | True | pk | False | opportunity_key |

#### Source References

- `src/closing_line_engine.py:165,213,216,1029,1034,1044,1155,1279`
- `src/dashboard_repository.py:363`
- `src/dashboard_schema_audit.py:19`
- `src/data_access.py:556,570,772,796`
- `src/inspect_master_inputs.py:16,152,217,295,355,390,391,469,505,506,507,508,528,529`
- `src/master_intelligence_dashboard_builder.py:257`
- `src/master_opportunity_engine.py:885,2199`
- `src/signal_fusion_engine.py:1565`

#### Create SQL

```sql
CREATE TABLE closing_line_metrics (
                opportunity_key TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                current_price REAL NOT NULL,
                first_wallet_entry REAL,
                first_elite_entry REAL,
                weighted_average_entry REAL,
                weighted_average_elite_entry REAL,
                best_observed_entry REAL,
                worst_observed_entry REAL,
                highest_observed_price REAL,
                lowest_observed_price REAL,
                price_move_from_entry REAL,
                price_move_from_elite_entry REAL,
                relative_move_from_entry REAL,
                relative_move_from_elite_entry REAL,
                gross_edge_at_entry REAL,
                gross_edge_remaining REAL,
                edge_remaining_ratio REAL,
                move_consumed_ratio REAL,
                clv_points REAL,
                clv_relative REAL,
                clv_score REAL,
                steam_score REAL,
                reversal_score REAL,
                volatility_score REAL,
                movement_status TEXT,
                entry_age_seconds INTEGER,
                elite_entry_age_seconds INTEGER,
                market_speed TEXT,
                steam_stage TEXT,
                lifecycle_status TEXT,
                seconds_to_start INTEGER,
                wallet_count INTEGER NOT NULL DEFAULT 0,
                elite_wallet_count INTEGER NOT NULL DEFAULT 0,
                data_completeness_score REAL NOT NULL DEFAULT 0,
                data_confidence TEXT NOT NULL DEFAULT 'LOW',
                chase_risk_score REAL NOT NULL DEFAULT 0,
                edge_remaining_score REAL NOT NULL DEFAULT 0,
                recommendation TEXT NOT NULL DEFAULT 'WATCH',
                explanation_json TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `closing_line_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | opportunities_seen | INTEGER | True | 0 | 0 |
| 5 | entry_rows_updated | INTEGER | True | 0 | 0 |
| 6 | metrics_updated | INTEGER | True | 0 | 0 |
| 7 | history_rows_created | INTEGER | True | 0 | 0 |
| 8 | status | TEXT | True | — | 0 |
| 9 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/closing_line_engine.py:260,1086,1112,1157`

#### Create SQL

```sql
CREATE TABLE closing_line_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,
                opportunities_seen INTEGER NOT NULL DEFAULT 0,
                entry_rows_updated INTEGER NOT NULL DEFAULT 0,
                metrics_updated INTEGER NOT NULL DEFAULT 0,
                history_rows_created INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `condition_id_lineage_audit_results`

- Row count: `144`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | condition_id | TEXT | True | — | 0 |
| 3 | canonical_found | INTEGER | True | 0 | 0 |
| 4 | legacy_found | INTEGER | True | 0 | 0 |
| 5 | registry_source | TEXT | False | — | 0 |
| 6 | first_source_table | TEXT | False | — | 0 |
| 7 | first_seen_at | TEXT | False | — | 0 |
| 8 | last_seen_at | TEXT | False | — | 0 |
| 9 | source_table_count | INTEGER | True | 0 | 0 |
| 10 | total_occurrences | INTEGER | True | 0 | 0 |
| 11 | title | TEXT | False | — | 0 |
| 12 | outcome | TEXT | False | — | 0 |
| 13 | diagnosis | TEXT | True | — | 0 |
| 14 | source_occurrences_json | TEXT | False | — | 0 |
| 15 | audited_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| run_id | condition_id_lineage_audit_runs | run_id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_condition_lineage_results_diagnosis | False | c | False | diagnosis, audited_at |
| idx_condition_lineage_results_condition | False | c | False | condition_id, audited_at |
| sqlite_autoindex_condition_id_lineage_audit_results_1 | True | u | False | run_id, condition_id |

#### Source References

- `src/condition_id_lineage_audit.py:73,904`

#### Create SQL

```sql
CREATE TABLE "condition_id_lineage_audit_results" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    condition_id TEXT NOT NULL,
                    canonical_found INTEGER NOT NULL DEFAULT 0,
                    legacy_found INTEGER NOT NULL DEFAULT 0,
                    registry_source TEXT,
                    first_source_table TEXT,
                    first_seen_at TEXT,
                    last_seen_at TEXT,
                    source_table_count INTEGER NOT NULL DEFAULT 0,
                    total_occurrences INTEGER NOT NULL DEFAULT 0,
                    title TEXT,
                    outcome TEXT,
                    diagnosis TEXT NOT NULL,
                    source_occurrences_json TEXT,
                    audited_at TEXT NOT NULL,
                    UNIQUE(run_id, condition_id),
                    FOREIGN KEY(run_id)
                        REFERENCES "condition_id_lineage_audit_runs"(run_id)
                        ON DELETE CASCADE
                )
```

### `condition_id_lineage_audit_runs`

- Row count: `4`
- Referenced by: `condition_id_lineage_audit_results`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | target_count | INTEGER | True | 0 | 0 |
| 5 | resolved_count | INTEGER | True | 0 | 0 |
| 6 | unresolved_count | INTEGER | True | 0 | 0 |
| 7 | source_tables_checked | INTEGER | True | 0 | 0 |
| 8 | results_written | INTEGER | True | 0 | 0 |
| 9 | status | TEXT | True | — | 0 |
| 10 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_condition_id_lineage_audit_runs_1 | True | pk | False | run_id |

#### Source References

- `src/condition_id_lineage_audit.py:72`

#### Create SQL

```sql
CREATE TABLE "condition_id_lineage_audit_runs" (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    elapsed_seconds REAL,
                    target_count INTEGER NOT NULL DEFAULT 0,
                    resolved_count INTEGER NOT NULL DEFAULT 0,
                    unresolved_count INTEGER NOT NULL DEFAULT 0,
                    source_tables_checked INTEGER NOT NULL DEFAULT 0,
                    results_written INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
```

### `consensus_history`

- Row count: `756`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | market_id | TEXT | True | — | 0 |
| 2 | title | TEXT | True | — | 0 |
| 3 | outcome | TEXT | True | — | 0 |
| 4 | wallet_count | INTEGER | True | — | 0 |
| 5 | combined_shares | REAL | True | — | 0 |
| 6 | combined_value | REAL | True | — | 0 |
| 7 | combined_pnl | REAL | True | — | 0 |
| 8 | conviction_score | REAL | True | — | 0 |
| 9 | conviction_grade | TEXT | True | — | 0 |
| 10 | average_entry_price | REAL | False | — | 0 |
| 11 | average_current_price | REAL | False | — | 0 |
| 12 | observed_price_move | REAL | False | — | 0 |
| 13 | scanned_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_consensus_history_market_outcome | False | c | False | market_id, outcome |

#### Source References

- `src/ai_research_engine.py:79,99,274`
- `src/alert_engine.py:139`
- `src/backtesting_engine.py:179,194`
- `src/command_center.py:100,110,128`
- `src/condition_id_lineage_audit.py:36`
- `src/consensus_history.py:54`
- `src/dashboard.py:110,123,141,280,906`
- `src/dashboard_schema_audit.py:23`
- `src/data_access.py:678,694,779,797`
- `src/database.py:66,157,497`
- `src/historical_market_reconciliation_engine.py:28`
- `src/market_classifier.py:359`
- `src/market_identity_engine.py:468`
- `src/market_intelligence_engine.py:125,128,154,613`
- `src/market_mapper_engine.py:22`
- `src/market_status_engine.py:333,343,355`
- `src/master_intelligence_dashboard_builder.py:264`
- `src/opportunity_engine.py:427,431,1173`
- `src/pages/1_Market_Intelligence_Timeline.py:104,116,148`
- `src/pages/2_Smart_Money_Radar.py:128,148`
- `src/pages/3_Capital_Flow.py:158,178`
- `src/platform_health.py:314,563`
- `src/registry_validation_gate.py:34`

#### Create SQL

```sql
CREATE TABLE consensus_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id TEXT NOT NULL,
            title TEXT NOT NULL,
            outcome TEXT NOT NULL,
            wallet_count INTEGER NOT NULL,
            combined_shares REAL NOT NULL,
            combined_value REAL NOT NULL,
            combined_pnl REAL NOT NULL,
            conviction_score REAL NOT NULL,
            conviction_grade TEXT NOT NULL,
            average_entry_price REAL,
            average_current_price REAL,
            observed_price_move REAL,
            scanned_at TEXT NOT NULL
        )
```

### `decision_price_attribution_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | engine_version | TEXT | True | — | 0 |
| 2 | mode | TEXT | True | — | 0 |
| 3 | started_at | TEXT | True | — | 0 |
| 4 | completed_at | TEXT | False | — | 0 |
| 5 | decisions_loaded | INTEGER | True | 0 | 0 |
| 6 | attributed_decisions | INTEGER | True | 0 | 0 |
| 7 | unattributed_decisions | INTEGER | True | 0 | 0 |
| 8 | fresh_attributions | INTEGER | True | 0 | 0 |
| 9 | stale_attributions | INTEGER | True | 0 | 0 |
| 10 | resolved_buy_records | INTEGER | True | 0 | 0 |
| 11 | resolved_avoid_records | INTEGER | True | 0 | 0 |
| 12 | rows_saved | INTEGER | True | 0 | 0 |
| 13 | duration_seconds | REAL | False | — | 0 |
| 14 | status | TEXT | True | — | 0 |
| 15 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_decision_price_attribution_runs_1 | True | pk | False | run_id |

#### Source References

- `src/decision_price_attribution_engine.py:429,1909,1938`
- `src/decision_price_attribution_engine_v10_backup.py:429,1843,1872`
- `src/decision_price_attribution_engine_v11_backup.py:429,1894,1923`

#### Create SQL

```sql
CREATE TABLE decision_price_attribution_runs (
            run_id TEXT PRIMARY KEY,

            engine_version TEXT NOT NULL,
            mode TEXT NOT NULL,

            started_at TEXT NOT NULL,
            completed_at TEXT,

            decisions_loaded INTEGER
                NOT NULL DEFAULT 0,

            attributed_decisions INTEGER
                NOT NULL DEFAULT 0,

            unattributed_decisions INTEGER
                NOT NULL DEFAULT 0,

            fresh_attributions INTEGER
                NOT NULL DEFAULT 0,

            stale_attributions INTEGER
                NOT NULL DEFAULT 0,

            resolved_buy_records INTEGER
                NOT NULL DEFAULT 0,

            resolved_avoid_records INTEGER
                NOT NULL DEFAULT 0,

            rows_saved INTEGER
                NOT NULL DEFAULT 0,

            duration_seconds REAL,
            status TEXT NOT NULL,
            error_message TEXT
        )
```

### `decision_price_attributions`

- Row count: `131`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | attribution_key | TEXT | False | — | 1 |
| 1 | source_history_id | INTEGER | True | — | 0 |
| 2 | source_run_id | TEXT | True | — | 0 |
| 3 | opportunity_key | TEXT | True | — | 0 |
| 4 | market_id | TEXT | True | — | 0 |
| 5 | title | TEXT | True | — | 0 |
| 6 | selected_outcome | TEXT | True | — | 0 |
| 7 | decision_action | TEXT | True | — | 0 |
| 8 | decision_grade | TEXT | True | — | 0 |
| 9 | decision_score | REAL | True | — | 0 |
| 10 | decision_confidence | REAL | True | — | 0 |
| 11 | methodology_version | TEXT | True | — | 0 |
| 12 | decision_at | TEXT | True | — | 0 |
| 13 | attributed_price | REAL | False | — | 0 |
| 14 | price_at | TEXT | False | — | 0 |
| 15 | price_age_seconds | REAL | False | — | 0 |
| 16 | price_age_hours | REAL | False | — | 0 |
| 17 | price_source | TEXT | True | 'NONE' | 0 |
| 18 | source_row_key | TEXT | False | — | 0 |
| 19 | match_method | TEXT | False | — | 0 |
| 20 | source_priority | INTEGER | False | — | 0 |
| 21 | source_sample_count | INTEGER | True | 0 | 0 |
| 22 | price_dispersion | REAL | False | — | 0 |
| 23 | attribution_status | TEXT | True | — | 0 |
| 24 | attribution_quality | TEXT | True | — | 0 |
| 25 | lookahead_safe | INTEGER | True | 1 | 0 |
| 26 | stale_price | INTEGER | True | 0 | 0 |
| 27 | resolved | INTEGER | True | 0 | 0 |
| 28 | actual_result | INTEGER | False | — | 0 |
| 29 | winning_outcome | TEXT | False | — | 0 |
| 30 | settlement_price | REAL | False | — | 0 |
| 31 | hypothetical_stake | REAL | True | 0 | 0 |
| 32 | hypothetical_shares | REAL | False | — | 0 |
| 33 | hypothetical_settlement_value | REAL | False | — | 0 |
| 34 | hypothetical_profit | REAL | False | — | 0 |
| 35 | hypothetical_roi | REAL | False | — | 0 |
| 36 | avoided_loss_amount | REAL | False | — | 0 |
| 37 | avoided_loss_roi | REAL | False | — | 0 |
| 38 | calculated_at | TEXT | True | — | 0 |
| 39 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_decision_price_quality | False | c | False | attribution_quality, stale_price |
| idx_decision_price_source | False | c | False | price_source, attribution_status |
| idx_decision_price_market | False | c | False | market_id, selected_outcome, decision_at |
| sqlite_autoindex_decision_price_attributions_2 | True | u | False | source_history_id, methodology_version |
| sqlite_autoindex_decision_price_attributions_1 | True | pk | False | attribution_key |

#### Source References

- `src/decision_price_attribution_engine.py:332,408,416,423,1742`
- `src/decision_price_attribution_engine_v10_backup.py:332,408,416,423,1676`
- `src/decision_price_attribution_engine_v11_backup.py:332,408,416,423,1727`

#### Create SQL

```sql
CREATE TABLE decision_price_attributions (
            attribution_key TEXT PRIMARY KEY,

            source_history_id INTEGER NOT NULL,
            source_run_id TEXT NOT NULL,

            opportunity_key TEXT NOT NULL,
            market_id TEXT NOT NULL,
            title TEXT NOT NULL,
            selected_outcome TEXT NOT NULL,

            decision_action TEXT NOT NULL,
            decision_grade TEXT NOT NULL,
            decision_score REAL NOT NULL,
            decision_confidence REAL NOT NULL,
            methodology_version TEXT NOT NULL,
            decision_at TEXT NOT NULL,

            attributed_price REAL,
            price_at TEXT,
            price_age_seconds REAL,
            price_age_hours REAL,

            price_source TEXT
                NOT NULL DEFAULT 'NONE',

            source_row_key TEXT,
            match_method TEXT,

            source_priority INTEGER,
            source_sample_count INTEGER
                NOT NULL DEFAULT 0,

            price_dispersion REAL,

            attribution_status TEXT
                NOT NULL,

            attribution_quality TEXT
                NOT NULL,

            lookahead_safe INTEGER
                NOT NULL DEFAULT 1,

            stale_price INTEGER
                NOT NULL DEFAULT 0,

            resolved INTEGER
                NOT NULL DEFAULT 0,

            actual_result INTEGER,
            winning_outcome TEXT,
            settlement_price REAL,

            hypothetical_stake REAL
                NOT NULL DEFAULT 0,

            hypothetical_shares REAL,
            hypothetical_settlement_value REAL,
            hypothetical_profit REAL,
            hypothetical_roi REAL,

            avoided_loss_amount REAL,
            avoided_loss_roi REAL,

            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            UNIQUE(
                source_history_id,
                methodology_version
            )
        )
```

### `discovered_wallets`

- Row count: `48`
- Referenced by: `wallet_category_specialties`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | username | TEXT | False | — | 0 |
| 2 | x_username | TEXT | False | — | 0 |
| 3 | profile_image | TEXT | False | — | 0 |
| 4 | verified_badge | INTEGER | True | 0 | 0 |
| 5 | first_discovered_at | TEXT | True | — | 0 |
| 6 | last_discovered_at | TEXT | True | — | 0 |
| 7 | discovery_count | INTEGER | True | 1 | 0 |
| 8 | leaderboard_appearances | INTEGER | True | 0 | 0 |
| 9 | categories_seen | INTEGER | True | 0 | 0 |
| 10 | periods_seen | INTEGER | True | 0 | 0 |
| 11 | best_rank | INTEGER | False | — | 0 |
| 12 | total_pnl_signal | REAL | True | 0 | 0 |
| 13 | total_volume_signal | REAL | True | 0 | 0 |
| 14 | elite_score | REAL | True | 0 | 0 |
| 15 | elite_grade | TEXT | False | — | 0 |
| 16 | primary_category | TEXT | False | — | 0 |
| 17 | discovery_reason | TEXT | False | — | 0 |
| 18 | active_watchlist | INTEGER | True | 0 | 0 |
| 19 | manually_approved | INTEGER | True | 0 | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_discovered_wallets_elite | False | c | False | elite_score, best_rank |
| sqlite_autoindex_discovered_wallets_1 | True | pk | False | wallet |

#### Source References

- `src/elite_wallet_discovery_engine.py:51`
- `src/wallet_profile_collector.py:36,311,333`

#### Create SQL

```sql
CREATE TABLE "discovered_wallets" (
                    wallet TEXT PRIMARY KEY,
                    username TEXT,
                    x_username TEXT,
                    profile_image TEXT,
                    verified_badge INTEGER NOT NULL DEFAULT 0,
                    first_discovered_at TEXT NOT NULL,
                    last_discovered_at TEXT NOT NULL,
                    discovery_count INTEGER NOT NULL DEFAULT 1,
                    leaderboard_appearances INTEGER NOT NULL DEFAULT 0,
                    categories_seen INTEGER NOT NULL DEFAULT 0,
                    periods_seen INTEGER NOT NULL DEFAULT 0,
                    best_rank INTEGER,
                    total_pnl_signal REAL NOT NULL DEFAULT 0,
                    total_volume_signal REAL NOT NULL DEFAULT 0,
                    elite_score REAL NOT NULL DEFAULT 0,
                    elite_grade TEXT,
                    primary_category TEXT,
                    discovery_reason TEXT,
                    active_watchlist INTEGER NOT NULL DEFAULT 0,
                    manually_approved INTEGER NOT NULL DEFAULT 0
                )
```

### `elite_wallet_category_weights`

- Row count: `51`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | category_weight_key | TEXT | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | category | TEXT | True | — | 0 |
| 3 | category_share | REAL | True | 0 | 0 |
| 4 | category_specialty_score | REAL | True | 0 | 0 |
| 5 | performance_score | REAL | True | 50 | 0 |
| 6 | alpha_score | REAL | True | 0 | 0 |
| 7 | category_influence_weight | REAL | True | 0 | 0 |
| 8 | category_confidence | TEXT | True | 'LOW' | 0 |
| 9 | calculated_at | TEXT | True | — | 0 |
| 10 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| wallet | elite_wallet_rankings | wallet | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_elite_wallet_category_weights_wallet | False | c | False | wallet, category_influence_weight |
| sqlite_autoindex_elite_wallet_category_weights_1 | True | pk | False | category_weight_key |

#### Source References

- `src/elite_wallet_ranking_engine.py:366,404,1654,1667,2102`

#### Create SQL

```sql
CREATE TABLE elite_wallet_category_weights (
                category_weight_key TEXT PRIMARY KEY,

                wallet TEXT NOT NULL,
                category TEXT NOT NULL,

                category_share REAL
                    NOT NULL DEFAULT 0,

                category_specialty_score REAL
                    NOT NULL DEFAULT 0,

                performance_score REAL
                    NOT NULL DEFAULT 50,

                alpha_score REAL
                    NOT NULL DEFAULT 0,

                category_influence_weight REAL
                    NOT NULL DEFAULT 0,

                category_confidence TEXT
                    NOT NULL DEFAULT 'LOW',

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(
                    wallet
                )
                REFERENCES elite_wallet_rankings(
                    wallet
                )
                ON DELETE CASCADE
            )
```

### `elite_wallet_history`

- Row count: `26`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | elite_rank | INTEGER | False | — | 0 |
| 3 | elite_tier | TEXT | False | — | 0 |
| 4 | influence_score | REAL | False | — | 0 |
| 5 | trust_weight | REAL | False | — | 0 |
| 6 | consensus_weight | REAL | False | — | 0 |
| 7 | prediction_weight | REAL | False | — | 0 |
| 8 | reliability_index | REAL | False | — | 0 |
| 9 | overall_research_weight | REAL | False | — | 0 |
| 10 | alpha_score | REAL | False | — | 0 |
| 11 | performance_score | REAL | False | — | 0 |
| 12 | dna_score | REAL | False | — | 0 |
| 13 | ledger_quality_score | REAL | False | — | 0 |
| 14 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_elite_wallet_history_wallet | False | c | False | wallet, observed_at |

#### Source References

- `src/elite_wallet_ranking_engine.py:409,433,1683,2107`

#### Create SQL

```sql
CREATE TABLE elite_wallet_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                wallet TEXT NOT NULL,
                elite_rank INTEGER,
                elite_tier TEXT,

                influence_score REAL,
                trust_weight REAL,
                consensus_weight REAL,
                prediction_weight REAL,
                reliability_index REAL,
                overall_research_weight REAL,

                alpha_score REAL,
                performance_score REAL,
                dna_score REAL,
                ledger_quality_score REAL,

                observed_at TEXT NOT NULL
            )
```

### `elite_wallet_rankings`

- Row count: `26`
- Referenced by: `elite_wallet_category_weights`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | elite_rank | INTEGER | False | — | 0 |
| 2 | elite_tier | TEXT | True | 'WATCHLIST' | 0 |
| 3 | influence_score | REAL | True | 0 | 0 |
| 4 | trust_weight | REAL | True | 0 | 0 |
| 5 | consensus_weight | REAL | True | 0 | 0 |
| 6 | prediction_weight | REAL | True | 0 | 0 |
| 7 | reliability_index | REAL | True | 0 | 0 |
| 8 | overall_research_weight | REAL | True | 0 | 0 |
| 9 | alpha_score | REAL | True | 0 | 0 |
| 10 | alpha_grade | TEXT | True | 'UNRATED' | 0 |
| 11 | alpha_confidence | TEXT | True | 'VERY LOW' | 0 |
| 12 | performance_score | REAL | True | 50 | 0 |
| 13 | performance_grade | TEXT | True | 'UNRATED' | 0 |
| 14 | dna_score | REAL | True | 50 | 0 |
| 15 | dna_grade | TEXT | True | 'UNRATED' | 0 |
| 16 | ledger_quality_score | REAL | True | 0 | 0 |
| 17 | ledger_confidence | TEXT | True | 'VERY LOW' | 0 |
| 18 | trade_event_count | INTEGER | True | 0 | 0 |
| 19 | closed_position_count | INTEGER | True | 0 | 0 |
| 20 | open_position_count | INTEGER | True | 0 | 0 |
| 21 | resolved_positions | INTEGER | True | 0 | 0 |
| 22 | win_rate | REAL | True | 0 | 0 |
| 23 | realized_roi | REAL | True | 0 | 0 |
| 24 | total_roi | REAL | True | 0 | 0 |
| 25 | total_estimated_pnl | REAL | True | 0 | 0 |
| 26 | timing_score | REAL | True | 50 | 0 |
| 27 | entry_quality_score | REAL | True | 50 | 0 |
| 28 | exit_quality_score | REAL | True | 50 | 0 |
| 29 | risk_adjusted_score | REAL | True | 50 | 0 |
| 30 | consistency_score | REAL | True | 50 | 0 |
| 31 | calibration_score | REAL | True | 50 | 0 |
| 32 | conviction_score | REAL | True | 50 | 0 |
| 33 | specialization_score | REAL | True | 0 | 0 |
| 34 | portfolio_independence_score | REAL | True | 50 | 0 |
| 35 | sample_size_score | REAL | True | 0 | 0 |
| 36 | recency_score | REAL | True | 50 | 0 |
| 37 | activity_score | REAL | True | 0 | 0 |
| 38 | primary_archetype | TEXT | False | — | 0 |
| 39 | primary_category | TEXT | False | — | 0 |
| 40 | sports_specialty | TEXT | False | — | 0 |
| 41 | market_type_specialty | TEXT | False | — | 0 |
| 42 | sports_expertise_score | REAL | True | 0 | 0 |
| 43 | politics_expertise_score | REAL | True | 0 | 0 |
| 44 | crypto_expertise_score | REAL | True | 0 | 0 |
| 45 | entertainment_expertise_score | REAL | True | 0 | 0 |
| 46 | other_expertise_score | REAL | True | 0 | 0 |
| 47 | category_confidence | TEXT | True | 'LOW' | 0 |
| 48 | positive_pnl_bonus | REAL | True | 0 | 0 |
| 49 | specialization_bonus | REAL | True | 0 | 0 |
| 50 | independence_bonus | REAL | True | 0 | 0 |
| 51 | high_confidence_bonus | REAL | True | 0 | 0 |
| 52 | negative_pnl_penalty | REAL | True | 0 | 0 |
| 53 | low_sample_penalty | REAL | True | 0 | 0 |
| 54 | weak_confidence_penalty | REAL | True | 0 | 0 |
| 55 | total_penalty | REAL | True | 0 | 0 |
| 56 | strengths_json | TEXT | False | — | 0 |
| 57 | risks_json | TEXT | False | — | 0 |
| 58 | explanation_json | TEXT | False | — | 0 |
| 59 | calculated_at | TEXT | True | — | 0 |
| 60 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_elite_wallet_rankings_tier | False | c | False | elite_tier, influence_score |
| idx_elite_wallet_rankings_score | False | c | False | influence_score |
| idx_elite_wallet_rankings_rank | False | c | False | elite_rank |
| sqlite_autoindex_elite_wallet_rankings_1 | True | pk | False | wallet |

#### Source References

- `src/candidate_qualification_engine.py:798`
- `src/elite_wallet_ranking_engine.py:180,349,355,361,396,1658,1662,2097`
- `src/institutional_trust_engine.py:31`
- `src/market_memory_engine.py:421,430`

#### Create SQL

```sql
CREATE TABLE elite_wallet_rankings (
                wallet TEXT PRIMARY KEY,

                elite_rank INTEGER,
                elite_tier TEXT
                    NOT NULL DEFAULT 'WATCHLIST',

                influence_score REAL
                    NOT NULL DEFAULT 0,

                trust_weight REAL
                    NOT NULL DEFAULT 0,

                consensus_weight REAL
                    NOT NULL DEFAULT 0,

                prediction_weight REAL
                    NOT NULL DEFAULT 0,

                reliability_index REAL
                    NOT NULL DEFAULT 0,

                overall_research_weight REAL
                    NOT NULL DEFAULT 0,

                alpha_score REAL
                    NOT NULL DEFAULT 0,

                alpha_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                alpha_confidence TEXT
                    NOT NULL DEFAULT 'VERY LOW',

                performance_score REAL
                    NOT NULL DEFAULT 50,

                performance_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                dna_score REAL
                    NOT NULL DEFAULT 50,

                dna_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                ledger_quality_score REAL
                    NOT NULL DEFAULT 0,

                ledger_confidence TEXT
                    NOT NULL DEFAULT 'VERY LOW',

                trade_event_count INTEGER
                    NOT NULL DEFAULT 0,

                closed_position_count INTEGER
                    NOT NULL DEFAULT 0,

                open_position_count INTEGER
                    NOT NULL DEFAULT 0,

                resolved_positions INTEGER
                    NOT NULL DEFAULT 0,

                win_rate REAL
                    NOT NULL DEFAULT 0,

                realized_roi REAL
                    NOT NULL DEFAULT 0,

                total_roi REAL
                    NOT NULL DEFAULT 0,

                total_estimated_pnl REAL
                    NOT NULL DEFAULT 0,

                timing_score REAL
                    NOT NULL DEFAULT 50,

                entry_quality_score REAL
                    NOT NULL DEFAULT 50,

                exit_quality_score REAL
                    NOT NULL DEFAULT 50,

                risk_adjusted_score REAL
                    NOT NULL DEFAULT 50,

                consistency_score REAL
                    NOT NULL DEFAULT 50,

                calibration_score REAL
                    NOT NULL DEFAULT 50,

                conviction_score REAL
                    NOT NULL DEFAULT 50,

                specialization_score REAL
                    NOT NULL DEFAULT 0,

                portfolio_independence_score REAL
                    NOT NULL DEFAULT 50,

                sample_size_score REAL
                    NOT NULL DEFAULT 0,

                recency_score REAL
                    NOT NULL DEFAULT 50,

                activity_score REAL
                    NOT NULL DEFAULT 0,

                primary_archetype TEXT,
                primary_category TEXT,
                sports_specialty TEXT,
                market_type_specialty TEXT,

                sports_expertise_score REAL
                    NOT NULL DEFAULT 0,

                politics_expertise_score REAL
                    NOT NULL DEFAULT 0,

                crypto_expertise_score REAL
                    NOT NULL DEFAULT 0,

                entertainment_expertise_score REAL
                    NOT NULL DEFAULT 0,

                other_expertise_score REAL
                    NOT NULL DEFAULT 0,

                category_confidence TEXT
                    NOT NULL DEFAULT 'LOW',

                positive_pnl_bonus REAL
                    NOT NULL DEFAULT 0,

                specialization_bonus REAL
                    NOT NULL DEFAULT 0,

                independence_bonus REAL
                    NOT NULL DEFAULT 0,

                high_confidence_bonus REAL
                    NOT NULL DEFAULT 0,

                negative_pnl_penalty REAL
                    NOT NULL DEFAULT 0,

                low_sample_penalty REAL
                    NOT NULL DEFAULT 0,

                weak_confidence_penalty REAL
                    NOT NULL DEFAULT 0,

                total_penalty REAL
                    NOT NULL DEFAULT 0,

                strengths_json TEXT,
                risks_json TEXT,
                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `elite_wallet_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | wallets_loaded | INTEGER | True | 0 | 0 |
| 5 | rankings_saved | INTEGER | True | 0 | 0 |
| 6 | category_rows_saved | INTEGER | True | 0 | 0 |
| 7 | history_rows_saved | INTEGER | True | 0 | 0 |
| 8 | status | TEXT | True | — | 0 |
| 9 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/elite_wallet_ranking_engine.py:438,1774,1813`

#### Create SQL

```sql
CREATE TABLE elite_wallet_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                wallets_loaded INTEGER
                    NOT NULL DEFAULT 0,

                rankings_saved INTEGER
                    NOT NULL DEFAULT 0,

                category_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                history_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `engine_runs`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_group_id | TEXT | False | — | 0 |
| 2 | engine_name | TEXT | True | — | 0 |
| 3 | status | TEXT | True | — | 0 |
| 4 | started_at | TEXT | True | — | 0 |
| 5 | finished_at | TEXT | False | — | 0 |
| 6 | elapsed_seconds | REAL | False | — | 0 |
| 7 | return_code | INTEGER | False | — | 0 |
| 8 | records_read | INTEGER | False | — | 0 |
| 9 | records_created | INTEGER | False | — | 0 |
| 10 | records_updated | INTEGER | False | — | 0 |
| 11 | error_type | TEXT | False | — | 0 |
| 12 | error_message | TEXT | False | — | 0 |
| 13 | log_path | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_engine_runs_started_at | False | c | False | started_at |
| idx_engine_runs_engine | False | c | False | engine_name |
| idx_engine_runs_group | False | c | False | run_group_id |

#### Source References

- `src/intelligence_database.py:542,570,578,586,632`

#### Create SQL

```sql
CREATE TABLE engine_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            run_group_id TEXT,
            engine_name TEXT NOT NULL,

            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,

            elapsed_seconds REAL,
            return_code INTEGER,

            records_read INTEGER,
            records_created INTEGER,
            records_updated INTEGER,

            error_type TEXT,
            error_message TEXT,
            log_path TEXT
        )
```

### `entry_price_cache`

- Row count: `137`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | opportunity_key | TEXT | False | — | 1 |
| 1 | market_id | TEXT | True | — | 0 |
| 2 | title | TEXT | True | — | 0 |
| 3 | outcome | TEXT | True | — | 0 |
| 4 | wallet_count | INTEGER | True | 0 | 0 |
| 5 | elite_wallet_count | INTEGER | True | 0 | 0 |
| 6 | total_current_value | REAL | True | 0 | 0 |
| 7 | elite_current_value | REAL | True | 0 | 0 |
| 8 | first_wallet_entry | REAL | False | — | 0 |
| 9 | first_wallet_entry_at | TEXT | False | — | 0 |
| 10 | first_elite_entry | REAL | False | — | 0 |
| 11 | first_elite_entry_at | TEXT | False | — | 0 |
| 12 | weighted_average_entry | REAL | False | — | 0 |
| 13 | weighted_average_elite_entry | REAL | False | — | 0 |
| 14 | best_observed_entry | REAL | False | — | 0 |
| 15 | worst_observed_entry | REAL | False | — | 0 |
| 16 | earliest_position_scan_id | INTEGER | False | — | 0 |
| 17 | latest_position_scan_id | INTEGER | False | — | 0 |
| 18 | wallets_json | TEXT | False | — | 0 |
| 19 | calculated_at | TEXT | True | — | 0 |
| 20 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_entry_cache_market | False | c | False | market_id |
| sqlite_autoindex_entry_price_cache_1 | True | pk | False | opportunity_key |

#### Source References

- `src/closing_line_engine.py:138,163,573,578,589,1154,1278`

#### Create SQL

```sql
CREATE TABLE entry_price_cache (
                opportunity_key TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                wallet_count INTEGER NOT NULL DEFAULT 0,
                elite_wallet_count INTEGER NOT NULL DEFAULT 0,
                total_current_value REAL NOT NULL DEFAULT 0,
                elite_current_value REAL NOT NULL DEFAULT 0,
                first_wallet_entry REAL,
                first_wallet_entry_at TEXT,
                first_elite_entry REAL,
                first_elite_entry_at TEXT,
                weighted_average_entry REAL,
                weighted_average_elite_entry REAL,
                best_observed_entry REAL,
                worst_observed_entry REAL,
                earliest_position_scan_id INTEGER,
                latest_position_scan_id INTEGER,
                wallets_json TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `gamma_events`

- Row count: `2228`
- Referenced by: `gamma_markets`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | gamma_event_id | TEXT | False | — | 1 |
| 1 | slug | TEXT | False | — | 0 |
| 2 | ticker | TEXT | False | — | 0 |
| 3 | title | TEXT | True | — | 0 |
| 4 | description | TEXT | False | — | 0 |
| 5 | category | TEXT | False | — | 0 |
| 6 | subcategory | TEXT | False | — | 0 |
| 7 | active | INTEGER | True | 0 | 0 |
| 8 | closed | INTEGER | True | 0 | 0 |
| 9 | archived | INTEGER | True | 0 | 0 |
| 10 | restricted | INTEGER | True | 0 | 0 |
| 11 | featured | INTEGER | True | 0 | 0 |
| 12 | start_time | TEXT | False | — | 0 |
| 13 | end_time | TEXT | False | — | 0 |
| 14 | created_at_gamma | TEXT | False | — | 0 |
| 15 | updated_at_gamma | TEXT | False | — | 0 |
| 16 | liquidity | REAL | True | 0 | 0 |
| 17 | volume | REAL | True | 0 | 0 |
| 18 | volume_24h | REAL | True | 0 | 0 |
| 19 | open_interest | REAL | True | 0 | 0 |
| 20 | market_count | INTEGER | True | 0 | 0 |
| 21 | tags_json | TEXT | False | — | 0 |
| 22 | series_json | TEXT | False | — | 0 |
| 23 | image_url | TEXT | False | — | 0 |
| 24 | icon_url | TEXT | False | — | 0 |
| 25 | raw_payload_json | TEXT | True | — | 0 |
| 26 | first_seen_at | TEXT | True | — | 0 |
| 27 | last_seen_at | TEXT | True | — | 0 |
| 28 | refreshed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_gamma_events_slug | False | c | False | slug |
| idx_gamma_events_active | False | c | False | active, closed, end_time |
| sqlite_autoindex_gamma_events_1 | True | pk | False | gamma_event_id |

#### Source References

- `src/canonical_market_repository.py:20`
- `src/gamma_market_registry.py:161,222,230,316,1021,1143,1529,1758`
- `src/gamma_registry_expansion_engine.py:860,1004,1014,1039,1079,1103,1320,2719,2819`
- `src/opportunity_ranking_engine.py:818,824,830`

#### Create SQL

```sql
CREATE TABLE gamma_events (
                gamma_event_id TEXT PRIMARY KEY,

                slug TEXT,
                ticker TEXT,

                title TEXT NOT NULL,
                description TEXT,

                category TEXT,
                subcategory TEXT,

                active INTEGER
                    NOT NULL DEFAULT 0,

                closed INTEGER
                    NOT NULL DEFAULT 0,

                archived INTEGER
                    NOT NULL DEFAULT 0,

                restricted INTEGER
                    NOT NULL DEFAULT 0,

                featured INTEGER
                    NOT NULL DEFAULT 0,

                start_time TEXT,
                end_time TEXT,
                created_at_gamma TEXT,
                updated_at_gamma TEXT,

                liquidity REAL
                    NOT NULL DEFAULT 0,

                volume REAL
                    NOT NULL DEFAULT 0,

                volume_24h REAL
                    NOT NULL DEFAULT 0,

                open_interest REAL
                    NOT NULL DEFAULT 0,

                market_count INTEGER
                    NOT NULL DEFAULT 0,

                tags_json TEXT,
                series_json TEXT,
                image_url TEXT,
                icon_url TEXT,

                raw_payload_json TEXT NOT NULL,

                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                refreshed_at TEXT NOT NULL
            )
```

### `gamma_market_outcomes`

- Row count: `41206`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | outcome_key | TEXT | False | — | 1 |
| 1 | gamma_market_id | TEXT | True | — | 0 |
| 2 | gamma_event_id | TEXT | False | — | 0 |
| 3 | condition_id | TEXT | False | — | 0 |
| 4 | outcome_index | INTEGER | True | — | 0 |
| 5 | outcome_name | TEXT | True | — | 0 |
| 6 | token_id | TEXT | False | — | 0 |
| 7 | implied_price | REAL | False | — | 0 |
| 8 | winner | INTEGER | True | 0 | 0 |
| 9 | first_seen_at | TEXT | True | — | 0 |
| 10 | last_seen_at | TEXT | True | — | 0 |
| 11 | refreshed_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| gamma_market_id | gamma_markets | gamma_market_id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_gamma_outcomes_token | False | c | False | token_id |
| idx_gamma_outcomes_market | False | c | False | gamma_market_id, outcome_index |
| sqlite_autoindex_gamma_market_outcomes_1 | True | pk | False | outcome_key |

#### Source References

- `src/canonical_market_identity_engine.py:308,518`
- `src/gamma_market_registry.py:348,381,388,1356,1551,1767`
- `src/gamma_registry_expansion_engine.py:194,1848,1870,1875,1907,1947,1971,2719,2829`
- `src/market_identifier_registry_engine.py:828,834,840`
- `src/market_mapper_engine.py:502`
- `src/market_resolution_engine.py:413,416,423`

#### Create SQL

```sql
CREATE TABLE gamma_market_outcomes (
                outcome_key TEXT PRIMARY KEY,

                gamma_market_id TEXT NOT NULL,
                gamma_event_id TEXT,

                condition_id TEXT,

                outcome_index INTEGER
                    NOT NULL,

                outcome_name TEXT NOT NULL,
                token_id TEXT,

                implied_price REAL,
                winner INTEGER
                    NOT NULL DEFAULT 0,

                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                refreshed_at TEXT NOT NULL,

                FOREIGN KEY(
                    gamma_market_id
                )
                REFERENCES gamma_markets(
                    gamma_market_id
                )
                ON DELETE CASCADE
            )
```

### `gamma_markets`

- Row count: `21778`
- Referenced by: `gamma_market_outcomes`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | gamma_market_id | TEXT | False | — | 1 |
| 1 | gamma_event_id | TEXT | False | — | 0 |
| 2 | condition_id | TEXT | False | — | 0 |
| 3 | question_id | TEXT | False | — | 0 |
| 4 | slug | TEXT | False | — | 0 |
| 5 | question | TEXT | True | — | 0 |
| 6 | description | TEXT | False | — | 0 |
| 7 | market_type | TEXT | False | — | 0 |
| 8 | category | TEXT | False | — | 0 |
| 9 | active | INTEGER | True | 0 | 0 |
| 10 | closed | INTEGER | True | 0 | 0 |
| 11 | archived | INTEGER | True | 0 | 0 |
| 12 | resolved | INTEGER | True | 0 | 0 |
| 13 | restricted | INTEGER | True | 0 | 0 |
| 14 | accepting_orders | INTEGER | True | 0 | 0 |
| 15 | neg_risk | INTEGER | True | 0 | 0 |
| 16 | start_time | TEXT | False | — | 0 |
| 17 | end_time | TEXT | False | — | 0 |
| 18 | game_start_time | TEXT | False | — | 0 |
| 19 | created_at_gamma | TEXT | False | — | 0 |
| 20 | updated_at_gamma | TEXT | False | — | 0 |
| 21 | liquidity | REAL | True | 0 | 0 |
| 22 | volume | REAL | True | 0 | 0 |
| 23 | volume_24h | REAL | True | 0 | 0 |
| 24 | open_interest | REAL | True | 0 | 0 |
| 25 | spread | REAL | False | — | 0 |
| 26 | last_trade_price | REAL | False | — | 0 |
| 27 | best_bid | REAL | False | — | 0 |
| 28 | best_ask | REAL | False | — | 0 |
| 29 | outcome_count | INTEGER | True | 0 | 0 |
| 30 | clob_token_ids_json | TEXT | False | — | 0 |
| 31 | outcomes_json | TEXT | False | — | 0 |
| 32 | outcome_prices_json | TEXT | False | — | 0 |
| 33 | resolution_source | TEXT | False | — | 0 |
| 34 | resolved_by | TEXT | False | — | 0 |
| 35 | image_url | TEXT | False | — | 0 |
| 36 | icon_url | TEXT | False | — | 0 |
| 37 | raw_payload_json | TEXT | True | — | 0 |
| 38 | first_seen_at | TEXT | True | — | 0 |
| 39 | last_seen_at | TEXT | True | — | 0 |
| 40 | refreshed_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| gamma_event_id | gamma_events | gamma_event_id | NO ACTION | SET NULL | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_gamma_markets_slug | False | c | False | slug |
| idx_gamma_markets_active | False | c | False | active, closed, end_time |
| idx_gamma_markets_event | False | c | False | gamma_event_id |
| idx_gamma_markets_condition | False | c | False | condition_id |
| sqlite_autoindex_gamma_markets_1 | True | pk | False | gamma_market_id |

#### Source References

- `src/canonical_backfill_engine.py:28,495,751,845,848`
- `src/canonical_market_identity_engine.py:303,491,646,663`
- `src/canonical_market_repository.py:19,139,645`
- `src/check_gamma_restricted.py:13,18,30`
- `src/condition_id_lineage_audit.py:898`
- `src/gamma_market_registry.py:234,324,330,336,344,373,1165,1540,1762`
- `src/gamma_registry_expansion_engine.py:193,684,698,704,858,860,1528,1538,1582,1622,1646,2719,2824`
- `src/historical_market_reconciliation_engine.py:22`
- `src/market_identifier_registry_engine.py:559,562,568,574,1827,3018`
- `src/market_lifecycle_manager.py:28,491,520`
- `src/market_mapper_engine.py:443,446,453`
- `src/market_memory_engine.py:448,454,532`
- `src/market_resolution_engine.py:381,384,391`
- `src/opportunity_ranking_engine.py:376,975,981,1742,1766`
- `src/registry_validation_gate.py:551,571,994,1004`

#### Create SQL

```sql
CREATE TABLE gamma_markets (
                gamma_market_id TEXT PRIMARY KEY,

                gamma_event_id TEXT,

                condition_id TEXT,
                question_id TEXT,

                slug TEXT,
                question TEXT NOT NULL,
                description TEXT,

                market_type TEXT,
                category TEXT,

                active INTEGER
                    NOT NULL DEFAULT 0,

                closed INTEGER
                    NOT NULL DEFAULT 0,

                archived INTEGER
                    NOT NULL DEFAULT 0,

                resolved INTEGER
                    NOT NULL DEFAULT 0,

                restricted INTEGER
                    NOT NULL DEFAULT 0,

                accepting_orders INTEGER
                    NOT NULL DEFAULT 0,

                neg_risk INTEGER
                    NOT NULL DEFAULT 0,

                start_time TEXT,
                end_time TEXT,
                game_start_time TEXT,

                created_at_gamma TEXT,
                updated_at_gamma TEXT,

                liquidity REAL
                    NOT NULL DEFAULT 0,

                volume REAL
                    NOT NULL DEFAULT 0,

                volume_24h REAL
                    NOT NULL DEFAULT 0,

                open_interest REAL
                    NOT NULL DEFAULT 0,

                spread REAL,
                last_trade_price REAL,
                best_bid REAL,
                best_ask REAL,

                outcome_count INTEGER
                    NOT NULL DEFAULT 0,

                clob_token_ids_json TEXT,
                outcomes_json TEXT,
                outcome_prices_json TEXT,

                resolution_source TEXT,
                resolved_by TEXT,

                image_url TEXT,
                icon_url TEXT,

                raw_payload_json TEXT NOT NULL,

                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                refreshed_at TEXT NOT NULL,

                FOREIGN KEY(
                    gamma_event_id
                )
                REFERENCES gamma_events(
                    gamma_event_id
                )
                ON DELETE SET NULL
            )
```

### `gamma_registry_expansion_checkpoints`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | checkpoint_name | TEXT | False | — | 1 |
| 1 | next_cursor | TEXT | False | — | 0 |
| 2 | last_market_updated_at | TEXT | False | — | 0 |
| 3 | last_success_at | TEXT | False | — | 0 |
| 4 | last_error_at | TEXT | False | — | 0 |
| 5 | last_error_message | TEXT | False | — | 0 |
| 6 | metadata_json | TEXT | False | — | 0 |
| 7 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_gamma_registry_expansion_checkpoints_1 | True | pk | False | checkpoint_name |

#### Source References

- `src/gamma_registry_expansion_engine.py:226`

#### Create SQL

```sql
CREATE TABLE gamma_registry_expansion_checkpoints (
                checkpoint_name TEXT PRIMARY KEY,

                next_cursor TEXT,
                last_market_updated_at TEXT,
                last_success_at TEXT,
                last_error_at TEXT,
                last_error_message TEXT,
                metadata_json TEXT,
                updated_at TEXT NOT NULL
            )
```

### `gamma_registry_expansion_errors`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | INTEGER | False | — | 0 |
| 2 | stage | TEXT | True | — | 0 |
| 3 | request_url | TEXT | False | — | 0 |
| 4 | condition_ids_json | TEXT | False | — | 0 |
| 5 | http_status | INTEGER | False | — | 0 |
| 6 | error_type | TEXT | True | — | 0 |
| 7 | error_message | TEXT | True | — | 0 |
| 8 | response_body_preview | TEXT | False | — | 0 |
| 9 | created_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_gamma_registry_expansion_errors_run | False | c | False | run_id, created_at |

#### Source References

- `src/gamma_registry_expansion_engine.py:238,254,2015`

#### Create SQL

```sql
CREATE TABLE gamma_registry_expansion_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                run_id INTEGER,
                stage TEXT NOT NULL,
                request_url TEXT,
                condition_ids_json TEXT,
                http_status INTEGER,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                response_body_preview TEXT,
                created_at TEXT NOT NULL
            )
```

### `gamma_registry_expansion_recovery`

- Row count: `8780`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | condition_id | TEXT | False | — | 1 |
| 1 | first_requested_at | TEXT | True | — | 0 |
| 2 | last_requested_at | TEXT | True | — | 0 |
| 3 | recovered | INTEGER | True | 0 | 0 |
| 4 | gamma_market_id | TEXT | False | — | 0 |
| 5 | market_slug | TEXT | False | — | 0 |
| 6 | event_slug | TEXT | False | — | 0 |
| 7 | recovery_method | TEXT | False | — | 0 |
| 8 | recovered_at | TEXT | False | — | 0 |
| 9 | request_count | INTEGER | True | 0 | 0 |
| 10 | last_error_message | TEXT | False | — | 0 |
| 11 | metadata_json | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_gamma_registry_expansion_recovery_1 | True | pk | False | condition_id |

#### Source References

- `src/gamma_registry_expansion_engine.py:259,2094,2114,2120,2125,2130,2135,2140,2143,2834`

#### Create SQL

```sql
CREATE TABLE gamma_registry_expansion_recovery (
                condition_id TEXT PRIMARY KEY,

                first_requested_at TEXT NOT NULL,
                last_requested_at TEXT NOT NULL,

                recovered INTEGER NOT NULL DEFAULT 0,
                gamma_market_id TEXT,
                market_slug TEXT,
                event_slug TEXT,

                recovery_method TEXT,
                recovered_at TEXT,

                request_count INTEGER NOT NULL DEFAULT 0,
                last_error_message TEXT,
                metadata_json TEXT
            )
```

### `gamma_registry_expansion_runs`

- Row count: `4`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | active_keyset_pages | INTEGER | True | 0 | 0 |
| 5 | active_markets_received | INTEGER | True | 0 | 0 |
| 6 | targeted_condition_ids | INTEGER | True | 0 | 0 |
| 7 | targeted_batches | INTEGER | True | 0 | 0 |
| 8 | targeted_markets_received | INTEGER | True | 0 | 0 |
| 9 | unique_markets_received | INTEGER | True | 0 | 0 |
| 10 | markets_inserted | INTEGER | True | 0 | 0 |
| 11 | markets_updated | INTEGER | True | 0 | 0 |
| 12 | outcomes_inserted | INTEGER | True | 0 | 0 |
| 13 | outcomes_updated | INTEGER | True | 0 | 0 |
| 14 | unresolved_before | INTEGER | True | 0 | 0 |
| 15 | unresolved_after | INTEGER | True | 0 | 0 |
| 16 | recovered_condition_ids | INTEGER | True | 0 | 0 |
| 17 | status | TEXT | True | — | 0 |
| 18 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/gamma_registry_expansion_engine.py:198,2203,2233,2839`

#### Create SQL

```sql
CREATE TABLE gamma_registry_expansion_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                active_keyset_pages INTEGER NOT NULL DEFAULT 0,
                active_markets_received INTEGER NOT NULL DEFAULT 0,

                targeted_condition_ids INTEGER NOT NULL DEFAULT 0,
                targeted_batches INTEGER NOT NULL DEFAULT 0,
                targeted_markets_received INTEGER NOT NULL DEFAULT 0,

                unique_markets_received INTEGER NOT NULL DEFAULT 0,
                markets_inserted INTEGER NOT NULL DEFAULT 0,
                markets_updated INTEGER NOT NULL DEFAULT 0,
                outcomes_inserted INTEGER NOT NULL DEFAULT 0,
                outcomes_updated INTEGER NOT NULL DEFAULT 0,

                unresolved_before INTEGER NOT NULL DEFAULT 0,
                unresolved_after INTEGER NOT NULL DEFAULT 0,
                recovered_condition_ids INTEGER NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `gamma_registry_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | events_fetched | INTEGER | True | 0 | 0 |
| 5 | markets_fetched | INTEGER | True | 0 | 0 |
| 6 | events_saved | INTEGER | True | 0 | 0 |
| 7 | markets_saved | INTEGER | True | 0 | 0 |
| 8 | outcomes_saved | INTEGER | True | 0 | 0 |
| 9 | status | TEXT | True | — | 0 |
| 10 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/gamma_market_registry.py:392,1434,1474`

#### Create SQL

```sql
CREATE TABLE gamma_registry_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                events_fetched INTEGER
                    NOT NULL DEFAULT 0,

                markets_fetched INTEGER
                    NOT NULL DEFAULT 0,

                events_saved INTEGER
                    NOT NULL DEFAULT 0,

                markets_saved INTEGER
                    NOT NULL DEFAULT 0,

                outcomes_saved INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `historical_market_reconciliation_audit`

- Row count: `9732`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | source_table | TEXT | True | — | 0 |
| 3 | source_rowid | INTEGER | False | — | 0 |
| 4 | market_id | TEXT | False | — | 0 |
| 5 | title | TEXT | False | — | 0 |
| 6 | outcome | TEXT | False | — | 0 |
| 7 | source_timestamp | TEXT | False | — | 0 |
| 8 | classification | TEXT | True | — | 0 |
| 9 | reason_code | TEXT | True | — | 0 |
| 10 | reason_detail | TEXT | False | — | 0 |
| 11 | canonical_match | INTEGER | True | 0 | 0 |
| 12 | gamma_match | INTEGER | True | 0 | 0 |
| 13 | malformed | INTEGER | True | 0 | 0 |
| 14 | reconciled_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| run_id | historical_market_reconciliation_runs | run_id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_historical_reconciliation_source | False | c | False | source_table, source_rowid |
| idx_historical_reconciliation_classification | False | c | False | classification, reconciled_at |
| idx_historical_reconciliation_market | False | c | False | market_id, reconciled_at |

#### Source References

- `src/historical_market_reconciliation_engine.py:24`

#### Create SQL

```sql
CREATE TABLE "historical_market_reconciliation_audit" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    source_table TEXT NOT NULL,
                    source_rowid INTEGER,
                    market_id TEXT,
                    title TEXT,
                    outcome TEXT,
                    source_timestamp TEXT,
                    classification TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    reason_detail TEXT,
                    canonical_match INTEGER NOT NULL DEFAULT 0,
                    gamma_match INTEGER NOT NULL DEFAULT 0,
                    malformed INTEGER NOT NULL DEFAULT 0,
                    reconciled_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES "historical_market_reconciliation_runs"(run_id)
                        ON DELETE CASCADE
                )
```

### `historical_market_reconciliation_runs`

- Row count: `3`
- Referenced by: `historical_market_reconciliation_audit`, `historical_market_reconciliation_summary`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | mode | TEXT | True | — | 0 |
| 5 | source_table_count | INTEGER | True | 0 | 0 |
| 6 | rows_scanned | INTEGER | True | 0 | 0 |
| 7 | rows_persisted | INTEGER | True | 0 | 0 |
| 8 | status | TEXT | True | — | 0 |
| 9 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_historical_market_reconciliation_runs_1 | True | pk | False | run_id |

#### Source References

- `src/historical_market_reconciliation_engine.py:23`

#### Create SQL

```sql
CREATE TABLE "historical_market_reconciliation_runs" (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    elapsed_seconds REAL,
                    mode TEXT NOT NULL,
                    source_table_count INTEGER NOT NULL DEFAULT 0,
                    rows_scanned INTEGER NOT NULL DEFAULT 0,
                    rows_persisted INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
```

### `historical_market_reconciliation_summary`

- Row count: `4`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | classification | TEXT | True | — | 0 |
| 3 | record_count | INTEGER | True | — | 0 |
| 4 | created_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| run_id | historical_market_reconciliation_runs | run_id | NO ACTION | CASCADE | NONE |

#### Indexes

None.

#### Source References

- `src/historical_market_reconciliation_engine.py:25`

#### Create SQL

```sql
CREATE TABLE "historical_market_reconciliation_summary" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    record_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES "historical_market_reconciliation_runs"(run_id)
                        ON DELETE CASCADE
                )
```

### `institutional_clob_market_cache`

- Row count: `39`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | condition_id | TEXT | False | — | 1 |
| 1 | question | TEXT | False | — | 0 |
| 2 | active | INTEGER | False | — | 0 |
| 3 | closed | INTEGER | False | — | 0 |
| 4 | archived | INTEGER | False | — | 0 |
| 5 | accepting_orders | INTEGER | False | — | 0 |
| 6 | game_start_time | TEXT | False | — | 0 |
| 7 | end_date_iso | TEXT | False | — | 0 |
| 8 | winning_outcome | TEXT | False | — | 0 |
| 9 | token_count | INTEGER | True | 0 | 0 |
| 10 | raw_payload_json | TEXT | True | — | 0 |
| 11 | fetched_at | TEXT | True | — | 0 |
| 12 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_institutional_clob_market_cache_1 | True | pk | False | condition_id |

#### Source References

- `src/institutional_resolution_intelligence_engine.py:324,1828`
- `src/institutional_resolution_intelligence_engine_backup_20260719_061600.py:324,1828`
- `src/institutional_resolution_intelligence_engine_v1_backup.py:324,1843`
- `src/institutional_settlement_intelligence_engine.py:379,1888`
- `src/institutional_settlement_intelligence_engine_backup_20260719_062517.py:379,1883`

#### Create SQL

```sql
CREATE TABLE institutional_clob_market_cache (
            condition_id TEXT PRIMARY KEY,

            question TEXT,

            active INTEGER,

            closed INTEGER,

            archived INTEGER,

            accepting_orders INTEGER,

            game_start_time TEXT,

            end_date_iso TEXT,

            winning_outcome TEXT,

            token_count INTEGER
                NOT NULL DEFAULT 0,

            raw_payload_json TEXT NOT NULL,

            fetched_at TEXT NOT NULL,

            updated_at TEXT NOT NULL
        )
```

### `institutional_consensus`

- Row count: `137`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | consensus_key | TEXT | False | — | 1 |
| 1 | market_id | TEXT | True | — | 0 |
| 2 | title | TEXT | True | — | 0 |
| 3 | outcome | TEXT | True | — | 0 |
| 4 | wallet_count | INTEGER | True | 0 | 0 |
| 5 | elite_wallet_count | INTEGER | True | 0 | 0 |
| 6 | effective_wallet_count | REAL | True | 0 | 0 |
| 7 | independent_wallet_score | REAL | True | 0 | 0 |
| 8 | total_current_value | REAL | True | 0 | 0 |
| 9 | elite_current_value | REAL | True | 0 | 0 |
| 10 | elite_value_share | REAL | True | 0 | 0 |
| 11 | average_wallet_quality | REAL | True | 0 | 0 |
| 12 | weighted_wallet_quality | REAL | True | 0 | 0 |
| 13 | weighted_entry_price | REAL | False | — | 0 |
| 14 | weighted_elite_entry_price | REAL | False | — | 0 |
| 15 | entry_price_stddev | REAL | True | 0 | 0 |
| 16 | entry_price_dispersion_score | REAL | True | 0 | 0 |
| 17 | earliest_entry_at | TEXT | False | — | 0 |
| 18 | latest_entry_at | TEXT | False | — | 0 |
| 19 | entry_span_seconds | INTEGER | True | 0 | 0 |
| 20 | synchronized_wallets_10m | INTEGER | True | 0 | 0 |
| 21 | synchronized_wallets_1h | INTEGER | True | 0 | 0 |
| 22 | synchronized_wallets_6h | INTEGER | True | 0 | 0 |
| 23 | synchronized_wallets_24h | INTEGER | True | 0 | 0 |
| 24 | synchronized_elite_wallets_10m | INTEGER | True | 0 | 0 |
| 25 | synchronized_elite_wallets_1h | INTEGER | True | 0 | 0 |
| 26 | synchronized_elite_wallets_6h | INTEGER | True | 0 | 0 |
| 27 | synchronized_elite_wallets_24h | INTEGER | True | 0 | 0 |
| 28 | time_sync_score | REAL | True | 0 | 0 |
| 29 | opposing_wallet_count | INTEGER | True | 0 | 0 |
| 30 | opposing_elite_wallet_count | INTEGER | True | 0 | 0 |
| 31 | opposing_current_value | REAL | True | 0 | 0 |
| 32 | market_total_value | REAL | True | 0 | 0 |
| 33 | agreement_value_share | REAL | True | 0 | 0 |
| 34 | conflict_ratio | REAL | True | 0 | 0 |
| 35 | opposing_conflict_score | REAL | True | 0 | 0 |
| 36 | overlap_pair_coverage | REAL | True | 0 | 0 |
| 37 | average_pair_overlap | REAL | True | 0 | 0 |
| 38 | portfolio_independence_score | REAL | True | 0 | 0 |
| 39 | capital_score | REAL | True | 0 | 0 |
| 40 | wallet_quality_score | REAL | True | 0 | 0 |
| 41 | agreement_score | REAL | True | 0 | 0 |
| 42 | freshness_score | REAL | True | 0 | 0 |
| 43 | consensus_strength | REAL | True | 0 | 0 |
| 44 | confidence_grade | TEXT | True | 'PASS' | 0 |
| 45 | signal_status | TEXT | True | 'PASS' | 0 |
| 46 | lifecycle_status | TEXT | False | — | 0 |
| 47 | seconds_to_start | INTEGER | False | — | 0 |
| 48 | data_completeness_score | REAL | True | 0 | 0 |
| 49 | data_confidence | TEXT | True | 'LOW' | 0 |
| 50 | wallets_json | TEXT | False | — | 0 |
| 51 | explanation_json | TEXT | False | — | 0 |
| 52 | calculated_at | TEXT | True | — | 0 |
| 53 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_institutional_consensus_grade | False | c | False | confidence_grade, consensus_strength |
| idx_institutional_consensus_rank | False | c | False | consensus_strength |
| sqlite_autoindex_institutional_consensus_1 | True | pk | False | consensus_key |

#### Source References

- `src/architecture_registry.py:446`
- `src/condition_id_lineage_audit.py:37`
- `src/dashboard_repository.py:361`
- `src/dashboard_schema_audit.py:17`
- `src/data_access.py:496,510,762,794`
- `src/historical_market_reconciliation_engine.py:29`
- `src/inspect_master_inputs.py:14,150,209,293,337,382,383,467,495,496,498,520,521,542`
- `src/institutional_consensus_engine.py:261,406,412,2022,2031,2051,2213,2566`
- `src/institutional_decision_engine.py:39`
- `src/institutional_decision_engine_v2.py:54`
- `src/institutional_decision_engine_v2_baseline.py:54`
- `src/institutional_decision_engine_v2_v20_backup.py:54`
- `src/institutional_decision_engine_v2_v21_backup.py:54`
- `src/master_intelligence_dashboard_builder.py:245`
- `src/master_opportunity_engine.py:875,2197`
- `src/prediction_engine.py:533`
- `src/registry_validation_gate.py:35`
- `src/signal_fusion_engine.py:22,1555,1992,2358`

#### Create SQL

```sql
CREATE TABLE institutional_consensus (
                consensus_key TEXT PRIMARY KEY,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                effective_wallet_count REAL
                    NOT NULL DEFAULT 0,

                independent_wallet_score REAL
                    NOT NULL DEFAULT 0,

                total_current_value REAL
                    NOT NULL DEFAULT 0,

                elite_current_value REAL
                    NOT NULL DEFAULT 0,

                elite_value_share REAL
                    NOT NULL DEFAULT 0,

                average_wallet_quality REAL
                    NOT NULL DEFAULT 0,

                weighted_wallet_quality REAL
                    NOT NULL DEFAULT 0,

                weighted_entry_price REAL,
                weighted_elite_entry_price REAL,

                entry_price_stddev REAL
                    NOT NULL DEFAULT 0,

                entry_price_dispersion_score REAL
                    NOT NULL DEFAULT 0,

                earliest_entry_at TEXT,
                latest_entry_at TEXT,

                entry_span_seconds INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_wallets_10m INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_wallets_1h INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_wallets_6h INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_wallets_24h INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_elite_wallets_10m INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_elite_wallets_1h INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_elite_wallets_6h INTEGER
                    NOT NULL DEFAULT 0,

                synchronized_elite_wallets_24h INTEGER
                    NOT NULL DEFAULT 0,

                time_sync_score REAL
                    NOT NULL DEFAULT 0,

                opposing_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                opposing_elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                opposing_current_value REAL
                    NOT NULL DEFAULT 0,

                market_total_value REAL
                    NOT NULL DEFAULT 0,

                agreement_value_share REAL
                    NOT NULL DEFAULT 0,

                conflict_ratio REAL
                    NOT NULL DEFAULT 0,

                opposing_conflict_score REAL
                    NOT NULL DEFAULT 0,

                overlap_pair_coverage REAL
                    NOT NULL DEFAULT 0,

                average_pair_overlap REAL
                    NOT NULL DEFAULT 0,

                portfolio_independence_score REAL
                    NOT NULL DEFAULT 0,

                capital_score REAL
                    NOT NULL DEFAULT 0,

                wallet_quality_score REAL
                    NOT NULL DEFAULT 0,

                agreement_score REAL
                    NOT NULL DEFAULT 0,

                freshness_score REAL
                    NOT NULL DEFAULT 0,

                consensus_strength REAL
                    NOT NULL DEFAULT 0,

                confidence_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                signal_status TEXT
                    NOT NULL DEFAULT 'PASS',

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                data_completeness_score REAL
                    NOT NULL DEFAULT 0,

                data_confidence TEXT
                    NOT NULL DEFAULT 'LOW',

                wallets_json TEXT,
                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `institutional_consensus_history`

- Row count: `137`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | consensus_key | TEXT | True | — | 0 |
| 2 | market_id | TEXT | True | — | 0 |
| 3 | title | TEXT | True | — | 0 |
| 4 | outcome | TEXT | True | — | 0 |
| 5 | wallet_count | INTEGER | False | — | 0 |
| 6 | elite_wallet_count | INTEGER | False | — | 0 |
| 7 | effective_wallet_count | REAL | False | — | 0 |
| 8 | independent_wallet_score | REAL | False | — | 0 |
| 9 | total_current_value | REAL | False | — | 0 |
| 10 | elite_current_value | REAL | False | — | 0 |
| 11 | elite_value_share | REAL | False | — | 0 |
| 12 | average_wallet_quality | REAL | False | — | 0 |
| 13 | weighted_wallet_quality | REAL | False | — | 0 |
| 14 | weighted_entry_price | REAL | False | — | 0 |
| 15 | weighted_elite_entry_price | REAL | False | — | 0 |
| 16 | entry_price_stddev | REAL | False | — | 0 |
| 17 | entry_price_dispersion_score | REAL | False | — | 0 |
| 18 | earliest_entry_at | TEXT | False | — | 0 |
| 19 | latest_entry_at | TEXT | False | — | 0 |
| 20 | entry_span_seconds | INTEGER | False | — | 0 |
| 21 | synchronized_wallets_10m | INTEGER | False | — | 0 |
| 22 | synchronized_wallets_1h | INTEGER | False | — | 0 |
| 23 | synchronized_wallets_6h | INTEGER | False | — | 0 |
| 24 | synchronized_wallets_24h | INTEGER | False | — | 0 |
| 25 | synchronized_elite_wallets_10m | INTEGER | False | — | 0 |
| 26 | synchronized_elite_wallets_1h | INTEGER | False | — | 0 |
| 27 | synchronized_elite_wallets_6h | INTEGER | False | — | 0 |
| 28 | synchronized_elite_wallets_24h | INTEGER | False | — | 0 |
| 29 | time_sync_score | REAL | False | — | 0 |
| 30 | opposing_wallet_count | INTEGER | False | — | 0 |
| 31 | opposing_elite_wallet_count | INTEGER | False | — | 0 |
| 32 | opposing_current_value | REAL | False | — | 0 |
| 33 | market_total_value | REAL | False | — | 0 |
| 34 | agreement_value_share | REAL | False | — | 0 |
| 35 | conflict_ratio | REAL | False | — | 0 |
| 36 | opposing_conflict_score | REAL | False | — | 0 |
| 37 | overlap_pair_coverage | REAL | False | — | 0 |
| 38 | average_pair_overlap | REAL | False | — | 0 |
| 39 | portfolio_independence_score | REAL | False | — | 0 |
| 40 | capital_score | REAL | False | — | 0 |
| 41 | wallet_quality_score | REAL | False | — | 0 |
| 42 | agreement_score | REAL | False | — | 0 |
| 43 | freshness_score | REAL | False | — | 0 |
| 44 | consensus_strength | REAL | False | — | 0 |
| 45 | confidence_grade | TEXT | False | — | 0 |
| 46 | signal_status | TEXT | False | — | 0 |
| 47 | lifecycle_status | TEXT | False | — | 0 |
| 48 | seconds_to_start | INTEGER | False | — | 0 |
| 49 | data_completeness_score | REAL | False | — | 0 |
| 50 | data_confidence | TEXT | False | — | 0 |
| 51 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_institutional_consensus_history_key | False | c | False | consensus_key, observed_at |

#### Source References

- `src/institutional_consensus_engine.py:417,494,2073,2214,2571`

#### Create SQL

```sql
CREATE TABLE institutional_consensus_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                consensus_key TEXT NOT NULL,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                wallet_count INTEGER,
                elite_wallet_count INTEGER,

                effective_wallet_count REAL,
                independent_wallet_score REAL,

                total_current_value REAL,
                elite_current_value REAL,
                elite_value_share REAL,

                average_wallet_quality REAL,
                weighted_wallet_quality REAL,

                weighted_entry_price REAL,
                weighted_elite_entry_price REAL,

                entry_price_stddev REAL,
                entry_price_dispersion_score REAL,

                earliest_entry_at TEXT,
                latest_entry_at TEXT,
                entry_span_seconds INTEGER,

                synchronized_wallets_10m INTEGER,
                synchronized_wallets_1h INTEGER,
                synchronized_wallets_6h INTEGER,
                synchronized_wallets_24h INTEGER,

                synchronized_elite_wallets_10m INTEGER,
                synchronized_elite_wallets_1h INTEGER,
                synchronized_elite_wallets_6h INTEGER,
                synchronized_elite_wallets_24h INTEGER,

                time_sync_score REAL,

                opposing_wallet_count INTEGER,
                opposing_elite_wallet_count INTEGER,
                opposing_current_value REAL,

                market_total_value REAL,
                agreement_value_share REAL,
                conflict_ratio REAL,
                opposing_conflict_score REAL,

                overlap_pair_coverage REAL,
                average_pair_overlap REAL,
                portfolio_independence_score REAL,

                capital_score REAL,
                wallet_quality_score REAL,
                agreement_score REAL,
                freshness_score REAL,

                consensus_strength REAL,
                confidence_grade TEXT,
                signal_status TEXT,

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                data_completeness_score REAL,
                data_confidence TEXT,

                observed_at TEXT NOT NULL
            )
```

### `institutional_consensus_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | active_groups_seen | INTEGER | True | 0 | 0 |
| 5 | consensus_rows_saved | INTEGER | True | 0 | 0 |
| 6 | history_rows_created | INTEGER | True | 0 | 0 |
| 7 | status | TEXT | True | — | 0 |
| 8 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/institutional_consensus_engine.py:499,2128,2161,2215`

#### Create SQL

```sql
CREATE TABLE institutional_consensus_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                active_groups_seen INTEGER
                    NOT NULL DEFAULT 0,

                consensus_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                history_rows_created INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `institutional_decision_diagnostic_history`

- Row count: `131`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | opportunity_key | TEXT | True | — | 0 |
| 2 | market_id | TEXT | False | — | 0 |
| 3 | title | TEXT | True | — | 0 |
| 4 | outcome | TEXT | False | — | 0 |
| 5 | current_action | TEXT | True | — | 0 |
| 6 | decision_grade | TEXT | False | — | 0 |
| 7 | decision_score | REAL | True | 0 | 0 |
| 8 | actionability_score | REAL | True | 0 | 0 |
| 9 | confidence | REAL | True | 0 | 0 |
| 10 | entry_quality_score | REAL | True | 0 | 0 |
| 11 | market_structure_score | REAL | True | 0 | 0 |
| 12 | trust_quality_score | REAL | True | 0 | 0 |
| 13 | data_quality_score | REAL | True | 0 | 0 |
| 14 | wallet_count | INTEGER | True | 0 | 0 |
| 15 | elite_wallet_count | INTEGER | True | 0 | 0 |
| 16 | supporting_wallet_count | INTEGER | True | 0 | 0 |
| 17 | trusted_wallet_count | INTEGER | True | 0 | 0 |
| 18 | hard_veto | INTEGER | True | 0 | 0 |
| 19 | buy_requirements_passed | INTEGER | True | 0 | 0 |
| 20 | buy_requirements_failed | INTEGER | True | 0 | 0 |
| 21 | watch_requirements_passed | INTEGER | True | 0 | 0 |
| 22 | watch_requirements_failed | INTEGER | True | 0 | 0 |
| 23 | buy_gap_score | REAL | True | 0 | 0 |
| 24 | watch_gap_score | REAL | True | 0 | 0 |
| 25 | nearest_upgrade | TEXT | True | — | 0 |
| 26 | upgrade_difficulty | TEXT | True | — | 0 |
| 27 | primary_blocker | TEXT | True | — | 0 |
| 28 | secondary_blocker | TEXT | False | — | 0 |
| 29 | blocker_category | TEXT | True | — | 0 |
| 30 | failed_buy_requirements_json | TEXT | True | — | 0 |
| 31 | failed_watch_requirements_json | TEXT | True | — | 0 |
| 32 | veto_reasons_json | TEXT | True | — | 0 |
| 33 | positive_reasons_json | TEXT | True | — | 0 |
| 34 | risk_flags_json | TEXT | True | — | 0 |
| 35 | upgrade_actions_json | TEXT | True | — | 0 |
| 36 | diagnostic_summary | TEXT | True | — | 0 |
| 37 | source_calculated_at | TEXT | False | — | 0 |
| 38 | diagnosed_at | TEXT | True | — | 0 |
| 39 | run_id | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_decision_diagnostic_history_run | False | c | False | run_id |
| idx_decision_diagnostic_history_key | False | c | False | opportunity_key |

#### Source References

- `src/decision_diagnostics_engine.py:186,252,258,950`

#### Create SQL

```sql
CREATE TABLE institutional_decision_diagnostic_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            opportunity_key TEXT NOT NULL,
            market_id TEXT,
            title TEXT NOT NULL,
            outcome TEXT,

            current_action TEXT NOT NULL,
            decision_grade TEXT,

            decision_score REAL NOT NULL DEFAULT 0,
            actionability_score REAL NOT NULL DEFAULT 0,
            confidence REAL NOT NULL DEFAULT 0,

            entry_quality_score REAL NOT NULL DEFAULT 0,
            market_structure_score REAL NOT NULL DEFAULT 0,
            trust_quality_score REAL NOT NULL DEFAULT 0,
            data_quality_score REAL NOT NULL DEFAULT 0,

            wallet_count INTEGER NOT NULL DEFAULT 0,
            elite_wallet_count INTEGER NOT NULL DEFAULT 0,
            supporting_wallet_count INTEGER NOT NULL DEFAULT 0,
            trusted_wallet_count INTEGER NOT NULL DEFAULT 0,

            hard_veto INTEGER NOT NULL DEFAULT 0,

            buy_requirements_passed INTEGER NOT NULL DEFAULT 0,
            buy_requirements_failed INTEGER NOT NULL DEFAULT 0,

            watch_requirements_passed INTEGER NOT NULL DEFAULT 0,
            watch_requirements_failed INTEGER NOT NULL DEFAULT 0,

            buy_gap_score REAL NOT NULL DEFAULT 0,
            watch_gap_score REAL NOT NULL DEFAULT 0,

            nearest_upgrade TEXT NOT NULL,
            upgrade_difficulty TEXT NOT NULL,

            primary_blocker TEXT NOT NULL,
            secondary_blocker TEXT,
            blocker_category TEXT NOT NULL,

            failed_buy_requirements_json TEXT NOT NULL,
            failed_watch_requirements_json TEXT NOT NULL,

            veto_reasons_json TEXT NOT NULL,
            positive_reasons_json TEXT NOT NULL,
            risk_flags_json TEXT NOT NULL,
            upgrade_actions_json TEXT NOT NULL,

            diagnostic_summary TEXT NOT NULL,

            source_calculated_at TEXT,
            diagnosed_at TEXT NOT NULL,
            run_id TEXT NOT NULL
        )
```

### `institutional_decision_diagnostic_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | methodology_version | TEXT | True | — | 0 |
| 2 | mode | TEXT | True | — | 0 |
| 3 | started_at | TEXT | True | — | 0 |
| 4 | completed_at | TEXT | False | — | 0 |
| 5 | source_decisions | INTEGER | True | 0 | 0 |
| 6 | diagnostics_analyzed | INTEGER | True | 0 | 0 |
| 7 | diagnostics_saved | INTEGER | True | 0 | 0 |
| 8 | history_saved | INTEGER | True | 0 | 0 |
| 9 | buy_ready_count | INTEGER | True | 0 | 0 |
| 10 | near_buy_count | INTEGER | True | 0 | 0 |
| 11 | watch_ready_count | INTEGER | True | 0 | 0 |
| 12 | near_watch_count | INTEGER | True | 0 | 0 |
| 13 | distant_count | INTEGER | True | 0 | 0 |
| 14 | veto_blocked_count | INTEGER | True | 0 | 0 |
| 15 | duration_seconds | REAL | False | — | 0 |
| 16 | status | TEXT | True | — | 0 |
| 17 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_institutional_decision_diagnostic_runs_1 | True | pk | False | run_id |

#### Source References

- `src/decision_diagnostics_engine.py:263,1186,1270,1423`
- `src/institutional_decision_audit_engine.py:97,100,118`
- `src/institutional_decision_intelligence_dashboard.py:95,696`

#### Create SQL

```sql
CREATE TABLE institutional_decision_diagnostic_runs (
            run_id TEXT PRIMARY KEY,
            methodology_version TEXT NOT NULL,
            mode TEXT NOT NULL,

            started_at TEXT NOT NULL,
            completed_at TEXT,

            source_decisions INTEGER NOT NULL DEFAULT 0,
            diagnostics_analyzed INTEGER NOT NULL DEFAULT 0,
            diagnostics_saved INTEGER NOT NULL DEFAULT 0,
            history_saved INTEGER NOT NULL DEFAULT 0,

            buy_ready_count INTEGER NOT NULL DEFAULT 0,
            near_buy_count INTEGER NOT NULL DEFAULT 0,
            watch_ready_count INTEGER NOT NULL DEFAULT 0,
            near_watch_count INTEGER NOT NULL DEFAULT 0,
            distant_count INTEGER NOT NULL DEFAULT 0,
            veto_blocked_count INTEGER NOT NULL DEFAULT 0,

            duration_seconds REAL,
            status TEXT NOT NULL,
            error_message TEXT
        )
```

### `institutional_decision_diagnostics`

- Row count: `131`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | opportunity_key | TEXT | False | — | 1 |
| 1 | market_id | TEXT | False | — | 0 |
| 2 | title | TEXT | True | — | 0 |
| 3 | outcome | TEXT | False | — | 0 |
| 4 | current_action | TEXT | True | — | 0 |
| 5 | decision_grade | TEXT | False | — | 0 |
| 6 | decision_score | REAL | True | 0 | 0 |
| 7 | actionability_score | REAL | True | 0 | 0 |
| 8 | confidence | REAL | True | 0 | 0 |
| 9 | entry_quality_score | REAL | True | 0 | 0 |
| 10 | market_structure_score | REAL | True | 0 | 0 |
| 11 | trust_quality_score | REAL | True | 0 | 0 |
| 12 | data_quality_score | REAL | True | 0 | 0 |
| 13 | wallet_count | INTEGER | True | 0 | 0 |
| 14 | elite_wallet_count | INTEGER | True | 0 | 0 |
| 15 | supporting_wallet_count | INTEGER | True | 0 | 0 |
| 16 | trusted_wallet_count | INTEGER | True | 0 | 0 |
| 17 | hard_veto | INTEGER | True | 0 | 0 |
| 18 | buy_requirements_passed | INTEGER | True | 0 | 0 |
| 19 | buy_requirements_failed | INTEGER | True | 0 | 0 |
| 20 | watch_requirements_passed | INTEGER | True | 0 | 0 |
| 21 | watch_requirements_failed | INTEGER | True | 0 | 0 |
| 22 | buy_gap_score | REAL | True | 0 | 0 |
| 23 | watch_gap_score | REAL | True | 0 | 0 |
| 24 | nearest_upgrade | TEXT | True | — | 0 |
| 25 | upgrade_difficulty | TEXT | True | — | 0 |
| 26 | primary_blocker | TEXT | True | — | 0 |
| 27 | secondary_blocker | TEXT | False | — | 0 |
| 28 | blocker_category | TEXT | True | — | 0 |
| 29 | failed_buy_requirements_json | TEXT | True | — | 0 |
| 30 | failed_watch_requirements_json | TEXT | True | — | 0 |
| 31 | veto_reasons_json | TEXT | True | — | 0 |
| 32 | positive_reasons_json | TEXT | True | — | 0 |
| 33 | risk_flags_json | TEXT | True | — | 0 |
| 34 | upgrade_actions_json | TEXT | True | — | 0 |
| 35 | diagnostic_summary | TEXT | True | — | 0 |
| 36 | source_calculated_at | TEXT | False | — | 0 |
| 37 | diagnosed_at | TEXT | True | — | 0 |
| 38 | run_id | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_decision_diagnostics_upgrade | False | c | False | nearest_upgrade |
| sqlite_autoindex_institutional_decision_diagnostics_1 | True | pk | False | opportunity_key |

#### Source References

- `src/decision_diagnostics_engine.py:129,246,937,1381`
- `src/institutional_decision_audit_engine.py:133`
- `src/institutional_decision_intelligence_dashboard.py:222,695`

#### Create SQL

```sql
CREATE TABLE institutional_decision_diagnostics (
            opportunity_key TEXT PRIMARY KEY,
            market_id TEXT,
            title TEXT NOT NULL,
            outcome TEXT,

            current_action TEXT NOT NULL,
            decision_grade TEXT,

            decision_score REAL NOT NULL DEFAULT 0,
            actionability_score REAL NOT NULL DEFAULT 0,
            confidence REAL NOT NULL DEFAULT 0,

            entry_quality_score REAL NOT NULL DEFAULT 0,
            market_structure_score REAL NOT NULL DEFAULT 0,
            trust_quality_score REAL NOT NULL DEFAULT 0,
            data_quality_score REAL NOT NULL DEFAULT 0,

            wallet_count INTEGER NOT NULL DEFAULT 0,
            elite_wallet_count INTEGER NOT NULL DEFAULT 0,
            supporting_wallet_count INTEGER NOT NULL DEFAULT 0,
            trusted_wallet_count INTEGER NOT NULL DEFAULT 0,

            hard_veto INTEGER NOT NULL DEFAULT 0,

            buy_requirements_passed INTEGER NOT NULL DEFAULT 0,
            buy_requirements_failed INTEGER NOT NULL DEFAULT 0,

            watch_requirements_passed INTEGER NOT NULL DEFAULT 0,
            watch_requirements_failed INTEGER NOT NULL DEFAULT 0,

            buy_gap_score REAL NOT NULL DEFAULT 0,
            watch_gap_score REAL NOT NULL DEFAULT 0,

            nearest_upgrade TEXT NOT NULL,
            upgrade_difficulty TEXT NOT NULL,

            primary_blocker TEXT NOT NULL,
            secondary_blocker TEXT,
            blocker_category TEXT NOT NULL,

            failed_buy_requirements_json TEXT NOT NULL,
            failed_watch_requirements_json TEXT NOT NULL,

            veto_reasons_json TEXT NOT NULL,
            positive_reasons_json TEXT NOT NULL,
            risk_flags_json TEXT NOT NULL,
            upgrade_actions_json TEXT NOT NULL,

            diagnostic_summary TEXT NOT NULL,

            source_calculated_at TEXT,
            diagnosed_at TEXT NOT NULL,
            run_id TEXT NOT NULL
        )
```

### `institutional_decision_history`

- Row count: `131`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | opportunity_key | TEXT | True | — | 0 |
| 3 | market_id | TEXT | True | — | 0 |
| 4 | title | TEXT | True | — | 0 |
| 5 | outcome | TEXT | True | — | 0 |
| 6 | decision_score | REAL | True | — | 0 |
| 7 | decision_grade | TEXT | True | — | 0 |
| 8 | decision_action | TEXT | True | — | 0 |
| 9 | actionability_score | REAL | True | — | 0 |
| 10 | confidence | REAL | True | — | 0 |
| 11 | weighted_trust_score | REAL | True | — | 0 |
| 12 | entry_quality_score | REAL | True | — | 0 |
| 13 | market_structure_score | REAL | True | — | 0 |
| 14 | data_quality_score | REAL | True | — | 0 |
| 15 | hard_veto | INTEGER | True | — | 0 |
| 16 | veto_reasons_json | TEXT | False | — | 0 |
| 17 | risk_flags_json | TEXT | False | — | 0 |
| 18 | observed_at | TEXT | True | — | 0 |
| 19 | methodology_version | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_institutional_decision_history | False | c | False | opportunity_key, observed_at |

#### Source References

- `src/decision_price_attribution_engine.py:318,321,488`
- `src/decision_price_attribution_engine_v10_backup.py:318,321,488`
- `src/decision_price_attribution_engine_v11_backup.py:318,321,488`
- `src/institutional_decision_engine.py:44`
- `src/institutional_learning_engine.py:11,284,500`
- `src/institutional_learning_engine_v10_scoring_backup.py:11,284,500`

#### Create SQL

```sql
CREATE TABLE institutional_decision_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,

                opportunity_key TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                decision_score REAL NOT NULL,
                decision_grade TEXT NOT NULL,
                decision_action TEXT NOT NULL,
                actionability_score REAL NOT NULL,

                confidence REAL NOT NULL,
                weighted_trust_score REAL NOT NULL,
                entry_quality_score REAL NOT NULL,
                market_structure_score REAL NOT NULL,
                data_quality_score REAL NOT NULL,

                hard_veto INTEGER NOT NULL,
                veto_reasons_json TEXT,
                risk_flags_json TEXT,

                observed_at TEXT NOT NULL,
                methodology_version TEXT NOT NULL
            )
```

### `institutional_decision_history_v2`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | opportunity_key | TEXT | True | — | 0 |
| 3 | market_id | TEXT | True | — | 0 |
| 4 | title | TEXT | True | — | 0 |
| 5 | outcome | TEXT | True | — | 0 |
| 6 | decision_score | REAL | True | — | 0 |
| 7 | decision_grade | TEXT | True | — | 0 |
| 8 | decision_action | TEXT | True | — | 0 |
| 9 | actionability_score | REAL | True | — | 0 |
| 10 | confidence | REAL | True | — | 0 |
| 11 | weighted_trust_score | REAL | True | — | 0 |
| 12 | entry_quality_score | REAL | True | — | 0 |
| 13 | market_structure_score | REAL | True | — | 0 |
| 14 | data_quality_score | REAL | True | — | 0 |
| 15 | hard_veto | INTEGER | True | — | 0 |
| 16 | veto_reasons_json | TEXT | False | — | 0 |
| 17 | risk_flags_json | TEXT | False | — | 0 |
| 18 | observed_at | TEXT | True | — | 0 |
| 19 | methodology_version | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/institutional_decision_engine_v2.py:59`
- `src/institutional_decision_engine_v2_baseline.py:59`
- `src/institutional_decision_engine_v2_v20_backup.py:59`
- `src/institutional_decision_engine_v2_v21_backup.py:59`

#### Create SQL

```sql
CREATE TABLE institutional_decision_history_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,

                opportunity_key TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                decision_score REAL NOT NULL,
                decision_grade TEXT NOT NULL,
                decision_action TEXT NOT NULL,
                actionability_score REAL NOT NULL,

                confidence REAL NOT NULL,
                weighted_trust_score REAL NOT NULL,
                entry_quality_score REAL NOT NULL,
                market_structure_score REAL NOT NULL,
                data_quality_score REAL NOT NULL,

                hard_veto INTEGER NOT NULL,
                veto_reasons_json TEXT,
                risk_flags_json TEXT,

                observed_at TEXT NOT NULL,
                methodology_version TEXT NOT NULL
            )
```

### `institutional_decision_runs`

- Row count: `4`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | mode | TEXT | True | — | 0 |
| 4 | methodology_version | TEXT | True | — | 0 |
| 5 | opportunity_limit | INTEGER | True | — | 0 |
| 6 | minimum_master_score | REAL | True | — | 0 |
| 7 | minimum_data_completeness | REAL | True | — | 0 |
| 8 | source_rows_seen | INTEGER | True | 0 | 0 |
| 9 | decisions_analyzed | INTEGER | True | 0 | 0 |
| 10 | decisions_saved | INTEGER | True | 0 | 0 |
| 11 | history_saved | INTEGER | True | 0 | 0 |
| 12 | buy_count | INTEGER | True | 0 | 0 |
| 13 | watch_count | INTEGER | True | 0 | 0 |
| 14 | wait_count | INTEGER | True | 0 | 0 |
| 15 | pass_count | INTEGER | True | 0 | 0 |
| 16 | avoid_count | INTEGER | True | 0 | 0 |
| 17 | veto_count | INTEGER | True | 0 | 0 |
| 18 | status | TEXT | True | — | 0 |
| 19 | duration_seconds | REAL | True | 0 | 0 |
| 20 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_institutional_decision_runs_1 | True | pk | False | run_id |

#### Source References

- `src/institutional_decision_engine.py:45`

#### Create SQL

```sql
CREATE TABLE institutional_decision_runs (
                run_id TEXT PRIMARY KEY,

                started_at TEXT NOT NULL,
                finished_at TEXT,

                mode TEXT NOT NULL,
                methodology_version TEXT NOT NULL,

                opportunity_limit INTEGER NOT NULL,
                minimum_master_score REAL NOT NULL,
                minimum_data_completeness REAL NOT NULL,

                source_rows_seen INTEGER NOT NULL DEFAULT 0,
                decisions_analyzed INTEGER NOT NULL DEFAULT 0,
                decisions_saved INTEGER NOT NULL DEFAULT 0,
                history_saved INTEGER NOT NULL DEFAULT 0,

                buy_count INTEGER NOT NULL DEFAULT 0,
                watch_count INTEGER NOT NULL DEFAULT 0,
                wait_count INTEGER NOT NULL DEFAULT 0,
                pass_count INTEGER NOT NULL DEFAULT 0,
                avoid_count INTEGER NOT NULL DEFAULT 0,
                veto_count INTEGER NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                duration_seconds REAL NOT NULL DEFAULT 0,
                error_message TEXT
            )
```

### `institutional_decision_runs_v2`

- Row count: `7`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | mode | TEXT | True | — | 0 |
| 4 | methodology_version | TEXT | True | — | 0 |
| 5 | opportunity_limit | INTEGER | True | — | 0 |
| 6 | minimum_master_score | REAL | True | — | 0 |
| 7 | minimum_data_completeness | REAL | True | — | 0 |
| 8 | source_rows_seen | INTEGER | True | 0 | 0 |
| 9 | decisions_analyzed | INTEGER | True | 0 | 0 |
| 10 | decisions_saved | INTEGER | True | 0 | 0 |
| 11 | history_saved | INTEGER | True | 0 | 0 |
| 12 | buy_count | INTEGER | True | 0 | 0 |
| 13 | watch_count | INTEGER | True | 0 | 0 |
| 14 | wait_count | INTEGER | True | 0 | 0 |
| 15 | pass_count | INTEGER | True | 0 | 0 |
| 16 | avoid_count | INTEGER | True | 0 | 0 |
| 17 | veto_count | INTEGER | True | 0 | 0 |
| 18 | status | TEXT | True | — | 0 |
| 19 | duration_seconds | REAL | True | 0 | 0 |
| 20 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_institutional_decision_runs_v2_1 | True | pk | False | run_id |

#### Source References

- `src/institutional_decision_engine_v2.py:60`
- `src/institutional_decision_engine_v2_baseline.py:60`
- `src/institutional_decision_engine_v2_v20_backup.py:60`
- `src/institutional_decision_engine_v2_v21_backup.py:60`

#### Create SQL

```sql
CREATE TABLE institutional_decision_runs_v2 (
                run_id TEXT PRIMARY KEY,

                started_at TEXT NOT NULL,
                finished_at TEXT,

                mode TEXT NOT NULL,
                methodology_version TEXT NOT NULL,

                opportunity_limit INTEGER NOT NULL,
                minimum_master_score REAL NOT NULL,
                minimum_data_completeness REAL NOT NULL,

                source_rows_seen INTEGER NOT NULL DEFAULT 0,
                decisions_analyzed INTEGER NOT NULL DEFAULT 0,
                decisions_saved INTEGER NOT NULL DEFAULT 0,
                history_saved INTEGER NOT NULL DEFAULT 0,

                buy_count INTEGER NOT NULL DEFAULT 0,
                watch_count INTEGER NOT NULL DEFAULT 0,
                wait_count INTEGER NOT NULL DEFAULT 0,
                pass_count INTEGER NOT NULL DEFAULT 0,
                avoid_count INTEGER NOT NULL DEFAULT 0,
                veto_count INTEGER NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                duration_seconds REAL NOT NULL DEFAULT 0,
                error_message TEXT
            )
```

### `institutional_decisions`

- Row count: `131`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | opportunity_key | TEXT | False | — | 1 |
| 1 | market_id | TEXT | True | — | 0 |
| 2 | title | TEXT | True | — | 0 |
| 3 | outcome | TEXT | True | — | 0 |
| 4 | market_type | TEXT | False | — | 0 |
| 5 | decision_score | REAL | True | 0 | 0 |
| 6 | decision_grade | TEXT | True | 'D' | 0 |
| 7 | decision_action | TEXT | True | 'PASS' | 0 |
| 8 | actionability_score | REAL | True | 0 | 0 |
| 9 | confidence | REAL | True | 0 | 0 |
| 10 | confidence_grade | TEXT | True | 'VERY LOW' | 0 |
| 11 | master_quality_score | REAL | True | 0 | 0 |
| 12 | consensus_quality_score | REAL | True | 0 | 0 |
| 13 | wallet_quality_score | REAL | True | 0 | 0 |
| 14 | trust_quality_score | REAL | True | 50 | 0 |
| 15 | entry_quality_score | REAL | True | 0 | 0 |
| 16 | market_structure_score | REAL | True | 0 | 0 |
| 17 | evolution_quality_score | REAL | True | 0 | 0 |
| 18 | timing_quality_score | REAL | True | 0 | 0 |
| 19 | data_quality_score | REAL | True | 0 | 0 |
| 20 | wallet_count | INTEGER | True | 0 | 0 |
| 21 | elite_wallet_count | INTEGER | True | 0 | 0 |
| 22 | supporting_wallet_count | INTEGER | True | 0 | 0 |
| 23 | trusted_wallet_count | INTEGER | True | 0 | 0 |
| 24 | weighted_trust_score | REAL | True | 50 | 0 |
| 25 | trust_confidence | REAL | True | 0 | 0 |
| 26 | average_consensus_multiplier | REAL | True | 1 | 0 |
| 27 | combined_current_value | REAL | True | 0 | 0 |
| 28 | chase_risk_score | REAL | True | 0 | 0 |
| 29 | conflict_ratio | REAL | True | 0 | 0 |
| 30 | reversal_score | REAL | True | 0 | 0 |
| 31 | weakening_score | REAL | True | 0 | 0 |
| 32 | edge_remaining_score | REAL | True | 0 | 0 |
| 33 | lifecycle_status | TEXT | False | — | 0 |
| 34 | seconds_to_start | INTEGER | False | — | 0 |
| 35 | data_completeness_score | REAL | True | 0 | 0 |
| 36 | source_coverage_score | REAL | True | 0 | 0 |
| 37 | data_confidence | TEXT | True | 'LOW' | 0 |
| 38 | canonical_match | INTEGER | True | 0 | 0 |
| 39 | is_tradable | INTEGER | True | 0 | 0 |
| 40 | polymarket_url | TEXT | False | — | 0 |
| 41 | liquidity | REAL | True | 0 | 0 |
| 42 | volume | REAL | True | 0 | 0 |
| 43 | hard_veto | INTEGER | True | 0 | 0 |
| 44 | veto_reasons_json | TEXT | False | — | 0 |
| 45 | positive_reasons_json | TEXT | False | — | 0 |
| 46 | risk_flags_json | TEXT | False | — | 0 |
| 47 | explanation | TEXT | True | — | 0 |
| 48 | calculated_at | TEXT | True | — | 0 |
| 49 | updated_at | TEXT | True | — | 0 |
| 50 | methodology_version | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_institutional_decisions_rank | False | c | False | decision_action, actionability_score, decision_score |
| sqlite_autoindex_institutional_decisions_1 | True | pk | False | opportunity_key |

#### Source References

- `src/decision_diagnostics_engine.py:1168,1172,1208`
- `src/institutional_decision_engine.py:43`
- `src/institutional_decision_intelligence_dashboard.py:223,697`

#### Create SQL

```sql
CREATE TABLE institutional_decisions (
                opportunity_key TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                market_type TEXT,

                decision_score REAL NOT NULL DEFAULT 0,
                decision_grade TEXT NOT NULL DEFAULT 'D',
                decision_action TEXT NOT NULL DEFAULT 'PASS',
                actionability_score REAL NOT NULL DEFAULT 0,

                confidence REAL NOT NULL DEFAULT 0,
                confidence_grade TEXT NOT NULL DEFAULT 'VERY LOW',

                master_quality_score REAL NOT NULL DEFAULT 0,
                consensus_quality_score REAL NOT NULL DEFAULT 0,
                wallet_quality_score REAL NOT NULL DEFAULT 0,
                trust_quality_score REAL NOT NULL DEFAULT 50,
                entry_quality_score REAL NOT NULL DEFAULT 0,
                market_structure_score REAL NOT NULL DEFAULT 0,
                evolution_quality_score REAL NOT NULL DEFAULT 0,
                timing_quality_score REAL NOT NULL DEFAULT 0,
                data_quality_score REAL NOT NULL DEFAULT 0,

                wallet_count INTEGER NOT NULL DEFAULT 0,
                elite_wallet_count INTEGER NOT NULL DEFAULT 0,
                supporting_wallet_count INTEGER NOT NULL DEFAULT 0,
                trusted_wallet_count INTEGER NOT NULL DEFAULT 0,

                weighted_trust_score REAL NOT NULL DEFAULT 50,
                trust_confidence REAL NOT NULL DEFAULT 0,
                average_consensus_multiplier REAL NOT NULL DEFAULT 1,

                combined_current_value REAL NOT NULL DEFAULT 0,

                chase_risk_score REAL NOT NULL DEFAULT 0,
                conflict_ratio REAL NOT NULL DEFAULT 0,
                reversal_score REAL NOT NULL DEFAULT 0,
                weakening_score REAL NOT NULL DEFAULT 0,
                edge_remaining_score REAL NOT NULL DEFAULT 0,

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                data_completeness_score REAL NOT NULL DEFAULT 0,
                source_coverage_score REAL NOT NULL DEFAULT 0,
                data_confidence TEXT NOT NULL DEFAULT 'LOW',

                canonical_match INTEGER NOT NULL DEFAULT 0,
                is_tradable INTEGER NOT NULL DEFAULT 0,
                polymarket_url TEXT,
                liquidity REAL NOT NULL DEFAULT 0,
                volume REAL NOT NULL DEFAULT 0,

                hard_veto INTEGER NOT NULL DEFAULT 0,
                veto_reasons_json TEXT,
                positive_reasons_json TEXT,
                risk_flags_json TEXT,
                explanation TEXT NOT NULL,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                methodology_version TEXT NOT NULL
            )
```

### `institutional_decisions_v2`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | opportunity_key | TEXT | False | — | 1 |
| 1 | market_id | TEXT | True | — | 0 |
| 2 | title | TEXT | True | — | 0 |
| 3 | outcome | TEXT | True | — | 0 |
| 4 | market_type | TEXT | False | — | 0 |
| 5 | decision_score | REAL | True | 0 | 0 |
| 6 | decision_grade | TEXT | True | 'D' | 0 |
| 7 | decision_action | TEXT | True | 'PASS' | 0 |
| 8 | actionability_score | REAL | True | 0 | 0 |
| 9 | confidence | REAL | True | 0 | 0 |
| 10 | confidence_grade | TEXT | True | 'VERY LOW' | 0 |
| 11 | master_quality_score | REAL | True | 0 | 0 |
| 12 | consensus_quality_score | REAL | True | 0 | 0 |
| 13 | wallet_quality_score | REAL | True | 0 | 0 |
| 14 | trust_quality_score | REAL | True | 50 | 0 |
| 15 | entry_quality_score | REAL | True | 0 | 0 |
| 16 | market_structure_score | REAL | True | 0 | 0 |
| 17 | evolution_quality_score | REAL | True | 0 | 0 |
| 18 | timing_quality_score | REAL | True | 0 | 0 |
| 19 | data_quality_score | REAL | True | 0 | 0 |
| 20 | wallet_count | INTEGER | True | 0 | 0 |
| 21 | elite_wallet_count | INTEGER | True | 0 | 0 |
| 22 | supporting_wallet_count | INTEGER | True | 0 | 0 |
| 23 | trusted_wallet_count | INTEGER | True | 0 | 0 |
| 24 | weighted_trust_score | REAL | True | 50 | 0 |
| 25 | trust_confidence | REAL | True | 0 | 0 |
| 26 | average_consensus_multiplier | REAL | True | 1 | 0 |
| 27 | combined_current_value | REAL | True | 0 | 0 |
| 28 | chase_risk_score | REAL | True | 0 | 0 |
| 29 | conflict_ratio | REAL | True | 0 | 0 |
| 30 | reversal_score | REAL | True | 0 | 0 |
| 31 | weakening_score | REAL | True | 0 | 0 |
| 32 | edge_remaining_score | REAL | True | 0 | 0 |
| 33 | lifecycle_status | TEXT | False | — | 0 |
| 34 | seconds_to_start | INTEGER | False | — | 0 |
| 35 | data_completeness_score | REAL | True | 0 | 0 |
| 36 | source_coverage_score | REAL | True | 0 | 0 |
| 37 | data_confidence | TEXT | True | 'LOW' | 0 |
| 38 | canonical_match | INTEGER | True | 0 | 0 |
| 39 | is_tradable | INTEGER | True | 0 | 0 |
| 40 | polymarket_url | TEXT | False | — | 0 |
| 41 | liquidity | REAL | True | 0 | 0 |
| 42 | volume | REAL | True | 0 | 0 |
| 43 | hard_veto | INTEGER | True | 0 | 0 |
| 44 | veto_reasons_json | TEXT | False | — | 0 |
| 45 | positive_reasons_json | TEXT | False | — | 0 |
| 46 | risk_flags_json | TEXT | False | — | 0 |
| 47 | explanation | TEXT | True | — | 0 |
| 48 | calculated_at | TEXT | True | — | 0 |
| 49 | updated_at | TEXT | True | — | 0 |
| 50 | methodology_version | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_institutional_decisions_v2_1 | True | pk | False | opportunity_key |

#### Source References

- `src/institutional_decision_engine_v2.py:58`
- `src/institutional_decision_engine_v2_baseline.py:58`
- `src/institutional_decision_engine_v2_v20_backup.py:58`
- `src/institutional_decision_engine_v2_v21_backup.py:58`

#### Create SQL

```sql
CREATE TABLE institutional_decisions_v2 (
                opportunity_key TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                market_type TEXT,

                decision_score REAL NOT NULL DEFAULT 0,
                decision_grade TEXT NOT NULL DEFAULT 'D',
                decision_action TEXT NOT NULL DEFAULT 'PASS',
                actionability_score REAL NOT NULL DEFAULT 0,

                confidence REAL NOT NULL DEFAULT 0,
                confidence_grade TEXT NOT NULL DEFAULT 'VERY LOW',

                master_quality_score REAL NOT NULL DEFAULT 0,
                consensus_quality_score REAL NOT NULL DEFAULT 0,
                wallet_quality_score REAL NOT NULL DEFAULT 0,
                trust_quality_score REAL NOT NULL DEFAULT 50,
                entry_quality_score REAL NOT NULL DEFAULT 0,
                market_structure_score REAL NOT NULL DEFAULT 0,
                evolution_quality_score REAL NOT NULL DEFAULT 0,
                timing_quality_score REAL NOT NULL DEFAULT 0,
                data_quality_score REAL NOT NULL DEFAULT 0,

                wallet_count INTEGER NOT NULL DEFAULT 0,
                elite_wallet_count INTEGER NOT NULL DEFAULT 0,
                supporting_wallet_count INTEGER NOT NULL DEFAULT 0,
                trusted_wallet_count INTEGER NOT NULL DEFAULT 0,

                weighted_trust_score REAL NOT NULL DEFAULT 50,
                trust_confidence REAL NOT NULL DEFAULT 0,
                average_consensus_multiplier REAL NOT NULL DEFAULT 1,

                combined_current_value REAL NOT NULL DEFAULT 0,

                chase_risk_score REAL NOT NULL DEFAULT 0,
                conflict_ratio REAL NOT NULL DEFAULT 0,
                reversal_score REAL NOT NULL DEFAULT 0,
                weakening_score REAL NOT NULL DEFAULT 0,
                edge_remaining_score REAL NOT NULL DEFAULT 0,

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                data_completeness_score REAL NOT NULL DEFAULT 0,
                source_coverage_score REAL NOT NULL DEFAULT 0,
                data_confidence TEXT NOT NULL DEFAULT 'LOW',

                canonical_match INTEGER NOT NULL DEFAULT 0,
                is_tradable INTEGER NOT NULL DEFAULT 0,
                polymarket_url TEXT,
                liquidity REAL NOT NULL DEFAULT 0,
                volume REAL NOT NULL DEFAULT 0,

                hard_veto INTEGER NOT NULL DEFAULT 0,
                veto_reasons_json TEXT,
                positive_reasons_json TEXT,
                risk_flags_json TEXT,
                explanation TEXT NOT NULL,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                methodology_version TEXT NOT NULL
            )
```

### `institutional_learning_evaluations`

- Row count: `26`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | evaluation_key | TEXT | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | evaluation_type | TEXT | True | — | 0 |
| 3 | evaluation_group | TEXT | True | — | 0 |
| 4 | methodology_version | TEXT | True | — | 0 |
| 5 | sample_count | INTEGER | True | — | 0 |
| 6 | resolved_count | INTEGER | True | — | 0 |
| 7 | correct_count | INTEGER | True | — | 0 |
| 8 | incorrect_count | INTEGER | True | — | 0 |
| 9 | unresolved_count | INTEGER | True | — | 0 |
| 10 | accuracy | REAL | False | — | 0 |
| 11 | average_confidence | REAL | False | — | 0 |
| 12 | calibration_gap | REAL | False | — | 0 |
| 13 | brier_score | REAL | False | — | 0 |
| 14 | total_hypothetical_profit | REAL | False | — | 0 |
| 15 | average_return_pct | REAL | False | — | 0 |
| 16 | sample_warning | TEXT | True | — | 0 |
| 17 | calculated_at | TEXT | True | — | 0 |
| 18 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_learning_evaluations_group | False | c | False | evaluation_type, evaluation_group, methodology_version |
| sqlite_autoindex_institutional_learning_evaluations_1 | True | pk | False | evaluation_key |

#### Source References

- `src/institutional_learning_engine.py:394,425,1573`
- `src/institutional_learning_engine_v10_scoring_backup.py:394,425,1553`

#### Create SQL

```sql
CREATE TABLE institutional_learning_evaluations (
            evaluation_key TEXT PRIMARY KEY,

            run_id TEXT NOT NULL,

            evaluation_type TEXT NOT NULL,
            evaluation_group TEXT NOT NULL,
            methodology_version TEXT NOT NULL,

            sample_count INTEGER NOT NULL,
            resolved_count INTEGER NOT NULL,
            correct_count INTEGER NOT NULL,
            incorrect_count INTEGER NOT NULL,
            unresolved_count INTEGER NOT NULL,

            accuracy REAL,
            average_confidence REAL,
            calibration_gap REAL,
            brier_score REAL,

            total_hypothetical_profit REAL,
            average_return_pct REAL,

            sample_warning TEXT NOT NULL,

            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
```

### `institutional_learning_observations`

- Row count: `131`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | observation_key | TEXT | False | — | 1 |
| 1 | source_history_id | INTEGER | True | — | 0 |
| 2 | source_run_id | TEXT | True | — | 0 |
| 3 | opportunity_key | TEXT | True | — | 0 |
| 4 | market_id | TEXT | True | — | 0 |
| 5 | title | TEXT | True | — | 0 |
| 6 | selected_outcome | TEXT | True | — | 0 |
| 7 | decision_action | TEXT | True | — | 0 |
| 8 | decision_grade | TEXT | True | — | 0 |
| 9 | decision_score | REAL | True | — | 0 |
| 10 | actionability_score | REAL | True | — | 0 |
| 11 | confidence | REAL | True | — | 0 |
| 12 | weighted_trust_score | REAL | True | — | 0 |
| 13 | entry_quality_score | REAL | True | — | 0 |
| 14 | market_structure_score | REAL | True | — | 0 |
| 15 | data_quality_score | REAL | True | — | 0 |
| 16 | hard_veto | INTEGER | True | — | 0 |
| 17 | methodology_version | TEXT | True | — | 0 |
| 18 | observed_at | TEXT | True | — | 0 |
| 19 | resolution_status | TEXT | True | 'UNRESOLVED' | 0 |
| 20 | resolution_evidence | TEXT | True | 'NONE' | 0 |
| 21 | winning_outcome | TEXT | False | — | 0 |
| 22 | source_outcome_won | INTEGER | False | — | 0 |
| 23 | source_outcome_lost | INTEGER | False | — | 0 |
| 24 | settlement_price | REAL | False | — | 0 |
| 25 | resolved_at | TEXT | False | — | 0 |
| 26 | match_method | TEXT | False | — | 0 |
| 27 | match_confidence | REAL | True | 0 | 0 |
| 28 | prediction_probability | REAL | True | — | 0 |
| 29 | actual_result | INTEGER | False | — | 0 |
| 30 | is_correct | INTEGER | False | — | 0 |
| 31 | brier_score | REAL | False | — | 0 |
| 32 | hypothetical_stake | REAL | True | — | 0 |
| 33 | hypothetical_profit | REAL | False | — | 0 |
| 34 | hypothetical_return_pct | REAL | False | — | 0 |
| 35 | evaluated_at | TEXT | True | — | 0 |
| 36 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_learning_observations_resolution | False | c | False | resolution_status, actual_result |
| idx_learning_observations_action | False | c | False | decision_action, methodology_version, is_correct |
| idx_learning_observations_market | False | c | False | market_id, selected_outcome |
| sqlite_autoindex_institutional_learning_observations_2 | True | u | False | source_history_id, methodology_version |
| sqlite_autoindex_institutional_learning_observations_1 | True | pk | False | observation_key |

#### Source References

- `src/institutional_decision_action_audit.py:41`
- `src/institutional_decision_action_audit_backup_20260719_065154.py:41`
- `src/institutional_learning_engine.py:311,373,380,388,1469`
- `src/institutional_learning_engine_v10_scoring_backup.py:311,373,380,388,1449`
- `src/institutional_learning_outcome_engine.py:173,213,387,934`
- `src/institutional_methodology_optimization_engine.py:369,372,556`
- `src/institutional_methodology_optimization_engine_v10_backup.py:369,372,556`
- `src/institutional_resolution_intelligence_engine.py:148,375,2199`
- `src/institutional_resolution_intelligence_engine_backup_20260719_061600.py:148,375,2199`
- `src/institutional_resolution_intelligence_engine_v1_backup.py:148,375,2214`
- `src/institutional_settlement_intelligence_engine.py:203,430,2259`
- `src/institutional_settlement_intelligence_engine_backup_20260719_062517.py:203,430,2254`
- `src/institutional_signal_weight_learning_engine.py:46`
- `src/institutional_signal_weight_learning_engine_v10_backup.py:46`
- `src/model_evaluation_calibration_engine.py:344,347,588,641`
- `src/model_evaluation_calibration_engine_v10_backup.py:342,345,586,639`

#### Create SQL

```sql
CREATE TABLE institutional_learning_observations (
            observation_key TEXT PRIMARY KEY,

            source_history_id INTEGER NOT NULL,
            source_run_id TEXT NOT NULL,

            opportunity_key TEXT NOT NULL,
            market_id TEXT NOT NULL,
            title TEXT NOT NULL,
            selected_outcome TEXT NOT NULL,

            decision_action TEXT NOT NULL,
            decision_grade TEXT NOT NULL,
            decision_score REAL NOT NULL,
            actionability_score REAL NOT NULL,
            confidence REAL NOT NULL,
            weighted_trust_score REAL NOT NULL,
            entry_quality_score REAL NOT NULL,
            market_structure_score REAL NOT NULL,
            data_quality_score REAL NOT NULL,
            hard_veto INTEGER NOT NULL,

            methodology_version TEXT NOT NULL,
            observed_at TEXT NOT NULL,

            resolution_status TEXT
                NOT NULL DEFAULT 'UNRESOLVED',

            resolution_evidence TEXT
                NOT NULL DEFAULT 'NONE',

            winning_outcome TEXT,

            source_outcome_won INTEGER,
            source_outcome_lost INTEGER,

            settlement_price REAL,
            resolved_at TEXT,

            match_method TEXT,
            match_confidence REAL NOT NULL DEFAULT 0,

            prediction_probability REAL NOT NULL,
            actual_result INTEGER,
            is_correct INTEGER,
            brier_score REAL,

            hypothetical_stake REAL NOT NULL,
            hypothetical_profit REAL,
            hypothetical_return_pct REAL,

            evaluated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            UNIQUE(
                source_history_id,
                methodology_version
            )
        )
```

### `institutional_learning_runs`

- Row count: `2`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | engine_version | TEXT | True | — | 0 |
| 2 | mode | TEXT | True | — | 0 |
| 3 | started_at | TEXT | True | — | 0 |
| 4 | completed_at | TEXT | False | — | 0 |
| 5 | history_rows_loaded | INTEGER | True | 0 | 0 |
| 6 | mapped_resolution_matches | INTEGER | True | 0 | 0 |
| 7 | fallback_resolution_matches | INTEGER | True | 0 | 0 |
| 8 | resolved_observations | INTEGER | True | 0 | 0 |
| 9 | unresolved_observations | INTEGER | True | 0 | 0 |
| 10 | correct_observations | INTEGER | True | 0 | 0 |
| 11 | incorrect_observations | INTEGER | True | 0 | 0 |
| 12 | observation_rows_saved | INTEGER | True | 0 | 0 |
| 13 | evaluation_rows_saved | INTEGER | True | 0 | 0 |
| 14 | duration_seconds | REAL | False | — | 0 |
| 15 | status | TEXT | True | — | 0 |
| 16 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_institutional_learning_runs_1 | True | pk | False | run_id |

#### Source References

- `src/institutional_learning_engine.py:432,1674,1704,1746`
- `src/institutional_learning_engine_v10_scoring_backup.py:432,1654,1684,1726`

#### Create SQL

```sql
CREATE TABLE institutional_learning_runs (
            run_id TEXT PRIMARY KEY,

            engine_version TEXT NOT NULL,
            mode TEXT NOT NULL,

            started_at TEXT NOT NULL,
            completed_at TEXT,

            history_rows_loaded INTEGER
                NOT NULL DEFAULT 0,

            mapped_resolution_matches INTEGER
                NOT NULL DEFAULT 0,

            fallback_resolution_matches INTEGER
                NOT NULL DEFAULT 0,

            resolved_observations INTEGER
                NOT NULL DEFAULT 0,

            unresolved_observations INTEGER
                NOT NULL DEFAULT 0,

            correct_observations INTEGER
                NOT NULL DEFAULT 0,

            incorrect_observations INTEGER
                NOT NULL DEFAULT 0,

            observation_rows_saved INTEGER
                NOT NULL DEFAULT 0,

            evaluation_rows_saved INTEGER
                NOT NULL DEFAULT 0,

            duration_seconds REAL,
            status TEXT NOT NULL,
            error_message TEXT
        )
```

### `institutional_settlement_intelligence_audit`

- Row count: `48`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | audit_key | TEXT | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | observation_key | TEXT | True | — | 0 |
| 3 | market_id | TEXT | True | — | 0 |
| 4 | title | TEXT | True | — | 0 |
| 5 | selected_outcome | TEXT | True | — | 0 |
| 6 | decision_action | TEXT | True | — | 0 |
| 7 | settlement_status | TEXT | True | — | 0 |
| 8 | settlement_source | TEXT | True | — | 0 |
| 9 | winning_outcome | TEXT | False | — | 0 |
| 10 | selected_settlement_price | REAL | False | — | 0 |
| 11 | source_outcome_won | INTEGER | False | — | 0 |
| 12 | source_outcome_lost | INTEGER | False | — | 0 |
| 13 | resolved_at | TEXT | False | — | 0 |
| 14 | match_method | TEXT | False | — | 0 |
| 15 | match_confidence | REAL | True | — | 0 |
| 16 | evidence_json | TEXT | True | — | 0 |
| 17 | conflict_reason | TEXT | False | — | 0 |
| 18 | external_request_made | INTEGER | True | 0 | 0 |
| 19 | created_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_settlement_audit_observation | False | c | False | observation_key, created_at |
| idx_settlement_audit_status | False | c | False | settlement_status, market_id |
| sqlite_autoindex_institutional_settlement_intelligence_audit_1 | True | pk | False | audit_key |

#### Source References

- `src/institutional_resolution_intelligence_engine.py:225,271,279,1978`
- `src/institutional_resolution_intelligence_engine_backup_20260719_061600.py:225,271,279,1978`
- `src/institutional_resolution_intelligence_engine_v1_backup.py:225,271,279,1993`
- `src/institutional_settlement_intelligence_engine.py:280,326,334,2038`
- `src/institutional_settlement_intelligence_engine_backup_20260719_062517.py:280,326,334,2033`

#### Create SQL

```sql
CREATE TABLE institutional_settlement_intelligence_audit (
            audit_key TEXT PRIMARY KEY,

            run_id TEXT NOT NULL,

            observation_key TEXT NOT NULL,

            market_id TEXT NOT NULL,

            title TEXT NOT NULL,

            selected_outcome TEXT NOT NULL,

            decision_action TEXT NOT NULL,

            settlement_status TEXT NOT NULL,

            settlement_source TEXT NOT NULL,

            winning_outcome TEXT,

            selected_settlement_price REAL,

            source_outcome_won INTEGER,

            source_outcome_lost INTEGER,

            resolved_at TEXT,

            match_method TEXT,

            match_confidence REAL NOT NULL,

            evidence_json TEXT NOT NULL,

            conflict_reason TEXT,

            external_request_made INTEGER
                NOT NULL DEFAULT 0,

            created_at TEXT NOT NULL
        )
```

### `institutional_settlement_intelligence_runs`

- Row count: `3`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | engine_version | TEXT | True | — | 0 |
| 2 | mode | TEXT | True | — | 0 |
| 3 | started_at | TEXT | True | — | 0 |
| 4 | completed_at | TEXT | False | — | 0 |
| 5 | observations_loaded | INTEGER | True | 0 | 0 |
| 6 | local_verified | INTEGER | True | 0 | 0 |
| 7 | clob_verified | INTEGER | True | 0 | 0 |
| 8 | pending_count | INTEGER | True | 0 | 0 |
| 9 | unavailable_count | INTEGER | True | 0 | 0 |
| 10 | quarantined_count | INTEGER | True | 0 | 0 |
| 11 | api_error_count | INTEGER | True | 0 | 0 |
| 12 | external_requests | INTEGER | True | 0 | 0 |
| 13 | learning_rows_updated | INTEGER | True | 0 | 0 |
| 14 | duration_seconds | REAL | False | — | 0 |
| 15 | status | TEXT | True | — | 0 |
| 16 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_institutional_settlement_intelligence_runs_1 | True | pk | False | run_id |

#### Source References

- `src/institutional_resolution_intelligence_engine.py:182,2686,2788,2907`
- `src/institutional_resolution_intelligence_engine_backup_20260719_061600.py:182,2686,2788,2907`
- `src/institutional_resolution_intelligence_engine_v1_backup.py:182,2699,2801,2920`
- `src/institutional_settlement_intelligence_engine.py:237,2746,2848,2967`
- `src/institutional_settlement_intelligence_engine_backup_20260719_062517.py:237,2741,2843,2962`

#### Create SQL

```sql
CREATE TABLE institutional_settlement_intelligence_runs (
            run_id TEXT PRIMARY KEY,
            engine_version TEXT NOT NULL,
            mode TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,

            observations_loaded INTEGER
                NOT NULL DEFAULT 0,

            local_verified INTEGER
                NOT NULL DEFAULT 0,

            clob_verified INTEGER
                NOT NULL DEFAULT 0,

            pending_count INTEGER
                NOT NULL DEFAULT 0,

            unavailable_count INTEGER
                NOT NULL DEFAULT 0,

            quarantined_count INTEGER
                NOT NULL DEFAULT 0,

            api_error_count INTEGER
                NOT NULL DEFAULT 0,

            external_requests INTEGER
                NOT NULL DEFAULT 0,

            learning_rows_updated INTEGER
                NOT NULL DEFAULT 0,

            duration_seconds REAL,

            status TEXT NOT NULL,

            error_message TEXT
        )
```

### `institutional_settlement_quarantine`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | quarantine_key | TEXT | False | — | 1 |
| 1 | observation_key | TEXT | True | — | 0 |
| 2 | market_id | TEXT | True | — | 0 |
| 3 | title | TEXT | True | — | 0 |
| 4 | selected_outcome | TEXT | True | — | 0 |
| 5 | quarantine_reason | TEXT | True | — | 0 |
| 6 | evidence_json | TEXT | True | — | 0 |
| 7 | first_seen_at | TEXT | True | — | 0 |
| 8 | last_seen_at | TEXT | True | — | 0 |
| 9 | occurrence_count | INTEGER | True | 1 | 0 |
| 10 | resolved_from_quarantine | INTEGER | True | 0 | 0 |
| 11 | resolution_note | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_settlement_quarantine_market | False | c | False | market_id, resolved_from_quarantine |
| sqlite_autoindex_institutional_settlement_quarantine_1 | True | pk | False | quarantine_key |

#### Source References

- `src/institutional_resolution_intelligence_engine.py:286,317,2115`
- `src/institutional_resolution_intelligence_engine_backup_20260719_061600.py:286,317,2115`
- `src/institutional_resolution_intelligence_engine_v1_backup.py:286,317,2130`
- `src/institutional_settlement_intelligence_engine.py:341,372,2175`
- `src/institutional_settlement_intelligence_engine_backup_20260719_062517.py:341,372,2170`

#### Create SQL

```sql
CREATE TABLE institutional_settlement_quarantine (
            quarantine_key TEXT PRIMARY KEY,

            observation_key TEXT NOT NULL,

            market_id TEXT NOT NULL,

            title TEXT NOT NULL,

            selected_outcome TEXT NOT NULL,

            quarantine_reason TEXT NOT NULL,

            evidence_json TEXT NOT NULL,

            first_seen_at TEXT NOT NULL,

            last_seen_at TEXT NOT NULL,

            occurrence_count INTEGER
                NOT NULL DEFAULT 1,

            resolved_from_quarantine INTEGER
                NOT NULL DEFAULT 0,

            resolution_note TEXT
        )
```

### `institutional_signal_feature_evaluations`

- Row count: `6`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | evaluation_key | TEXT | False | — | 1 |
| 1 | feature_name | TEXT | True | — | 0 |
| 2 | total_observations | INTEGER | True | 0 | 0 |
| 3 | available_observations | INTEGER | True | 0 | 0 |
| 4 | missing_observations | INTEGER | True | 0 | 0 |
| 5 | coverage_rate | REAL | True | 0 | 0 |
| 6 | mean_value | REAL | True | 0 | 0 |
| 7 | standard_deviation | REAL | True | 0 | 0 |
| 8 | minimum_value | REAL | True | 0 | 0 |
| 9 | maximum_value | REAL | True | 0 | 0 |
| 10 | successful_count | INTEGER | True | 0 | 0 |
| 11 | unsuccessful_count | INTEGER | True | 0 | 0 |
| 12 | successful_mean | REAL | True | 0 | 0 |
| 13 | unsuccessful_mean | REAL | True | 0 | 0 |
| 14 | mean_difference | REAL | True | 0 | 0 |
| 15 | point_biserial_correlation | REAL | True | 0 | 0 |
| 16 | absolute_correlation | REAL | True | 0 | 0 |
| 17 | predictive_strength | REAL | True | 0 | 0 |
| 18 | raw_importance_score | REAL | True | 0 | 0 |
| 19 | normalized_importance | REAL | False | — | 0 |
| 20 | relationship_direction | TEXT | True | — | 0 |
| 21 | evidence_status | TEXT | True | — | 0 |
| 22 | recommendation_status | TEXT | True | — | 0 |
| 23 | recommendation_reason | TEXT | False | — | 0 |
| 24 | rank_position | INTEGER | True | 0 | 0 |
| 25 | engine_version | TEXT | True | — | 0 |
| 26 | calculated_at | TEXT | True | — | 0 |
| 27 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_signal_feature_rank | False | c | False | recommendation_status, rank_position, raw_importance_score |
| sqlite_autoindex_institutional_signal_feature_evaluations_1 | True | pk | False | evaluation_key |

#### Source References

- `src/institutional_signal_weight_learning_engine.py:1082,1161,1248`
- `src/institutional_signal_weight_learning_engine_v10_backup.py:1057,1136,1223`

#### Create SQL

```sql
CREATE TABLE institutional_signal_feature_evaluations (
            evaluation_key TEXT PRIMARY KEY,

            feature_name TEXT NOT NULL,

            total_observations INTEGER
                NOT NULL DEFAULT 0,

            available_observations INTEGER
                NOT NULL DEFAULT 0,

            missing_observations INTEGER
                NOT NULL DEFAULT 0,

            coverage_rate REAL
                NOT NULL DEFAULT 0,

            mean_value REAL
                NOT NULL DEFAULT 0,

            standard_deviation REAL
                NOT NULL DEFAULT 0,

            minimum_value REAL
                NOT NULL DEFAULT 0,

            maximum_value REAL
                NOT NULL DEFAULT 0,

            successful_count INTEGER
                NOT NULL DEFAULT 0,

            unsuccessful_count INTEGER
                NOT NULL DEFAULT 0,

            successful_mean REAL
                NOT NULL DEFAULT 0,

            unsuccessful_mean REAL
                NOT NULL DEFAULT 0,

            mean_difference REAL
                NOT NULL DEFAULT 0,

            point_biserial_correlation REAL
                NOT NULL DEFAULT 0,

            absolute_correlation REAL
                NOT NULL DEFAULT 0,

            predictive_strength REAL
                NOT NULL DEFAULT 0,

            raw_importance_score REAL
                NOT NULL DEFAULT 0,

            normalized_importance REAL,

            relationship_direction TEXT
                NOT NULL,

            evidence_status TEXT
                NOT NULL,

            recommendation_status TEXT
                NOT NULL,

            recommendation_reason TEXT,

            rank_position INTEGER
                NOT NULL DEFAULT 0,

            engine_version TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
```

### `institutional_signal_learning_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | engine_version | TEXT | True | — | 0 |
| 2 | mode | TEXT | True | — | 0 |
| 3 | started_at | TEXT | True | — | 0 |
| 4 | completed_at | TEXT | False | — | 0 |
| 5 | resolved_observations | INTEGER | True | 0 | 0 |
| 6 | discovered_features | INTEGER | True | 0 | 0 |
| 7 | evaluated_features | INTEGER | True | 0 | 0 |
| 8 | redundancy_pairs | INTEGER | True | 0 | 0 |
| 9 | saved_feature_rows | INTEGER | True | 0 | 0 |
| 10 | saved_redundancy_rows | INTEGER | True | 0 | 0 |
| 11 | learning_status | TEXT | True | — | 0 |
| 12 | status | TEXT | True | — | 0 |
| 13 | duration_seconds | REAL | False | — | 0 |
| 14 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_institutional_signal_learning_runs_1 | True | pk | False | run_id |

#### Source References

- `src/institutional_signal_weight_learning_engine.py:1201,1515,1564`
- `src/institutional_signal_weight_learning_engine_v10_backup.py:1176,1490,1539`

#### Create SQL

```sql
CREATE TABLE institutional_signal_learning_runs (
            run_id TEXT PRIMARY KEY,

            engine_version TEXT NOT NULL,
            mode TEXT NOT NULL,

            started_at TEXT NOT NULL,
            completed_at TEXT,

            resolved_observations INTEGER
                NOT NULL DEFAULT 0,

            discovered_features INTEGER
                NOT NULL DEFAULT 0,

            evaluated_features INTEGER
                NOT NULL DEFAULT 0,

            redundancy_pairs INTEGER
                NOT NULL DEFAULT 0,

            saved_feature_rows INTEGER
                NOT NULL DEFAULT 0,

            saved_redundancy_rows INTEGER
                NOT NULL DEFAULT 0,

            learning_status TEXT NOT NULL,
            status TEXT NOT NULL,

            duration_seconds REAL,
            error_message TEXT
        )
```

### `institutional_signal_redundancy`

- Row count: `15`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | redundancy_key | TEXT | False | — | 1 |
| 1 | feature_a | TEXT | True | — | 0 |
| 2 | feature_b | TEXT | True | — | 0 |
| 3 | paired_observations | INTEGER | True | 0 | 0 |
| 4 | correlation | REAL | True | 0 | 0 |
| 5 | absolute_correlation | REAL | True | 0 | 0 |
| 6 | redundancy_status | TEXT | True | — | 0 |
| 7 | recommendation | TEXT | False | — | 0 |
| 8 | engine_version | TEXT | True | — | 0 |
| 9 | calculated_at | TEXT | True | — | 0 |
| 10 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_signal_redundancy_strength | False | c | False | redundancy_status, absolute_correlation |
| sqlite_autoindex_institutional_signal_redundancy_1 | True | pk | False | redundancy_key |

#### Source References

- `src/institutional_signal_weight_learning_engine.py:1168,1195,1432`
- `src/institutional_signal_weight_learning_engine_v10_backup.py:1143,1170,1407`

#### Create SQL

```sql
CREATE TABLE institutional_signal_redundancy (
            redundancy_key TEXT PRIMARY KEY,

            feature_a TEXT NOT NULL,
            feature_b TEXT NOT NULL,

            paired_observations INTEGER
                NOT NULL DEFAULT 0,

            correlation REAL
                NOT NULL DEFAULT 0,

            absolute_correlation REAL
                NOT NULL DEFAULT 0,

            redundancy_status TEXT
                NOT NULL,

            recommendation TEXT,

            engine_version TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
```

### `leaderboard_entries`

- Row count: `4496`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | entry_key | TEXT | False | — | 1 |
| 1 | snapshot_id | INTEGER | True | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | rank | INTEGER | False | — | 0 |
| 4 | username | TEXT | False | — | 0 |
| 5 | pnl | REAL | True | 0 | 0 |
| 6 | volume | REAL | True | 0 | 0 |
| 7 | profile_image | TEXT | False | — | 0 |
| 8 | x_username | TEXT | False | — | 0 |
| 9 | verified_badge | INTEGER | True | 0 | 0 |
| 10 | category | TEXT | True | — | 0 |
| 11 | time_period | TEXT | True | — | 0 |
| 12 | order_by | TEXT | True | — | 0 |
| 13 | raw_json | TEXT | False | — | 0 |
| 14 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| snapshot_id | leaderboard_snapshots | id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_leaderboard_entries_wallet | False | c | False | wallet, observed_at |
| sqlite_autoindex_leaderboard_entries_1 | True | pk | False | entry_key |

#### Source References

- `src/weekly_wallet_discovery.py:200,278,585,1247`

#### Create SQL

```sql
CREATE TABLE leaderboard_entries (
                entry_key TEXT PRIMARY KEY,
                snapshot_id INTEGER NOT NULL,
                wallet TEXT NOT NULL,
                rank INTEGER,
                username TEXT,
                pnl REAL NOT NULL DEFAULT 0,
                volume REAL NOT NULL DEFAULT 0,
                profile_image TEXT,
                x_username TEXT,
                verified_badge INTEGER NOT NULL DEFAULT 0,
                category TEXT NOT NULL,
                time_period TEXT NOT NULL,
                order_by TEXT NOT NULL,
                raw_json TEXT,
                observed_at TEXT NOT NULL,
                FOREIGN KEY(snapshot_id)
                    REFERENCES leaderboard_snapshots(id)
                    ON DELETE CASCADE
            )
```

### `leaderboard_snapshots`

- Row count: `18`
- Referenced by: `leaderboard_entries`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | snapshot_key | TEXT | True | — | 0 |
| 2 | category | TEXT | True | — | 0 |
| 3 | time_period | TEXT | True | — | 0 |
| 4 | order_by | TEXT | True | — | 0 |
| 5 | requested_limit | INTEGER | True | 50 | 0 |
| 6 | requested_max_results | INTEGER | True | 0 | 0 |
| 7 | entries_received | INTEGER | True | 0 | 0 |
| 8 | pages_requested | INTEGER | True | 0 | 0 |
| 9 | api_url | TEXT | True | — | 0 |
| 10 | started_at | TEXT | True | — | 0 |
| 11 | completed_at | TEXT | False | — | 0 |
| 12 | status | TEXT | True | — | 0 |
| 13 | error_message | TEXT | False | — | 0 |
| 14 | metadata_json | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_leaderboard_snapshots_1 | True | u | False | snapshot_key |

#### Source References

- `src/weekly_wallet_discovery.py:182,217,477,519,1246`

#### Create SQL

```sql
CREATE TABLE leaderboard_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_key TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                time_period TEXT NOT NULL,
                order_by TEXT NOT NULL,
                requested_limit INTEGER NOT NULL DEFAULT 50,
                requested_max_results INTEGER NOT NULL DEFAULT 0,
                entries_received INTEGER NOT NULL DEFAULT 0,
                pages_requested INTEGER NOT NULL DEFAULT 0,
                api_url TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                error_message TEXT,
                metadata_json TEXT
            )
```

### `mapped_market_results`

- Row count: `116`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | mapped_result_key | TEXT | False | — | 1 |
| 1 | mapping_key | TEXT | True | — | 0 |
| 2 | source_table | TEXT | True | — | 0 |
| 3 | source_market_id | TEXT | True | — | 0 |
| 4 | source_title | TEXT | False | — | 0 |
| 5 | source_outcome | TEXT | False | — | 0 |
| 6 | gamma_market_id | TEXT | True | — | 0 |
| 7 | condition_id | TEXT | False | — | 0 |
| 8 | resolution_status | TEXT | True | 'UNRESOLVED' | 0 |
| 9 | winning_outcome_name | TEXT | False | — | 0 |
| 10 | winning_token_id | TEXT | False | — | 0 |
| 11 | source_outcome_normalized | TEXT | False | — | 0 |
| 12 | winning_outcome_normalized | TEXT | False | — | 0 |
| 13 | source_outcome_won | INTEGER | False | — | 0 |
| 14 | source_outcome_lost | INTEGER | False | — | 0 |
| 15 | settlement_price | REAL | False | — | 0 |
| 16 | match_method | TEXT | False | — | 0 |
| 17 | match_confidence | REAL | False | — | 0 |
| 18 | resolved_at_detected | TEXT | False | — | 0 |
| 19 | calculated_at | TEXT | True | — | 0 |
| 20 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_mapped_market_results_mapping | False | c | False | mapping_key |
| idx_mapped_market_results_resolution | False | c | False | resolution_status, source_outcome_won |
| sqlite_autoindex_mapped_market_results_1 | True | pk | False | mapped_result_key |

#### Source References

- `src/decision_price_attribution_engine.py:1080,1096`
- `src/decision_price_attribution_engine_v10_backup.py:1080,1096`
- `src/decision_price_attribution_engine_v11_backup.py:1080,1096`
- `src/institutional_learning_engine.py:12,285,539`
- `src/institutional_learning_engine_v10_scoring_backup.py:12,285,539`
- `src/institutional_resolution_intelligence_engine.py:149,528,676,976`
- `src/institutional_resolution_intelligence_engine_backup_20260719_061600.py:149,528,676,976`
- `src/institutional_resolution_intelligence_engine_v1_backup.py:149,532,680,982`
- `src/institutional_settlement_intelligence_engine.py:204,588,736,1036`
- `src/institutional_settlement_intelligence_engine_backup_20260719_062517.py:204,583,731,1031`
- `src/market_resolution_engine.py:282,319,326,1234,1731`
- `src/wallet_performance_engine.py:472,479`

#### Create SQL

```sql
CREATE TABLE mapped_market_results (
                mapped_result_key TEXT PRIMARY KEY,

                mapping_key TEXT NOT NULL,

                source_table TEXT NOT NULL,
                source_market_id TEXT NOT NULL,
                source_title TEXT,
                source_outcome TEXT,

                gamma_market_id TEXT NOT NULL,
                condition_id TEXT,

                resolution_status TEXT
                    NOT NULL DEFAULT 'UNRESOLVED',

                winning_outcome_name TEXT,
                winning_token_id TEXT,

                source_outcome_normalized TEXT,
                winning_outcome_normalized TEXT,

                source_outcome_won INTEGER,
                source_outcome_lost INTEGER,

                settlement_price REAL,

                match_method TEXT,
                match_confidence REAL,

                resolved_at_detected TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `market_category_classifications`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | market_id | TEXT | False | — | 1 |
| 1 | title | TEXT | False | — | 0 |
| 2 | primary_category | TEXT | True | 'uncategorized' | 0 |
| 3 | secondary_category | TEXT | False | — | 0 |
| 4 | sport | TEXT | False | — | 0 |
| 5 | league | TEXT | False | — | 0 |
| 6 | event_type | TEXT | False | — | 0 |
| 7 | classification_confidence | REAL | True | 0 | 0 |
| 8 | classification_method | TEXT | False | — | 0 |
| 9 | classified_at | TEXT | True | — | 0 |
| 10 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_categories_sport | False | c | False | sport |
| idx_market_categories_category | False | c | False | primary_category |
| sqlite_autoindex_market_category_classifications_1 | True | pk | False | market_id |

#### Source References

- `src/elite_wallet_intelligence_database.py:195,222,223,369`
- `src/market_classifier.py:404,406,410,421,428,434,440,472,484`

#### Create SQL

```sql
CREATE TABLE market_category_classifications (
        market_id TEXT PRIMARY KEY,
        title TEXT,
        primary_category TEXT NOT NULL DEFAULT 'uncategorized',
        secondary_category TEXT,
        sport TEXT,
        league TEXT,
        event_type TEXT,
        classification_confidence REAL NOT NULL DEFAULT 0,
        classification_method TEXT,
        classified_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
```

### `market_identifier_aliases`

- Row count: `7320`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | alias_key | TEXT | False | — | 1 |
| 1 | condition_id | TEXT | True | — | 0 |
| 2 | alias_type | TEXT | True | — | 0 |
| 3 | alias_value | TEXT | True | — | 0 |
| 4 | normalized_alias_value | TEXT | False | — | 0 |
| 5 | source_table | TEXT | True | — | 0 |
| 6 | source_column | TEXT | False | — | 0 |
| 7 | confidence | REAL | True | 0 | 0 |
| 8 | verified | INTEGER | True | 0 | 0 |
| 9 | first_seen_at | TEXT | True | — | 0 |
| 10 | last_seen_at | TEXT | True | — | 0 |
| 11 | metadata_json | TEXT | False | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| condition_id | market_identifier_registry | condition_id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_identifier_aliases_condition | False | c | False | condition_id |
| idx_market_identifier_aliases_lookup | False | c | False | alias_type, normalized_alias_value |
| sqlite_autoindex_market_identifier_aliases_1 | True | pk | False | alias_key |

#### Source References

- `src/canonical_market_identity_engine.py:554,561`
- `src/market_identifier_registry_engine.py:422,449,456,2490,2505,3001`
- `src/market_identity_enrichment_engine.py:200,446`

#### Create SQL

```sql
CREATE TABLE market_identifier_aliases (
                alias_key TEXT PRIMARY KEY,

                condition_id TEXT NOT NULL,

                alias_type TEXT NOT NULL,
                alias_value TEXT NOT NULL,
                normalized_alias_value TEXT,

                source_table TEXT NOT NULL,
                source_column TEXT,

                confidence REAL NOT NULL DEFAULT 0,
                verified INTEGER NOT NULL DEFAULT 0,

                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,

                metadata_json TEXT,

                FOREIGN KEY(condition_id)
                    REFERENCES market_identifier_registry(condition_id)
                    ON DELETE CASCADE
            )
```

### `market_identifier_registry`

- Row count: `20590`
- Referenced by: `market_identifier_aliases`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | condition_id | TEXT | False | — | 1 |
| 1 | gamma_market_id | TEXT | False | — | 0 |
| 2 | gamma_event_id | TEXT | False | — | 0 |
| 3 | market_slug | TEXT | False | — | 0 |
| 4 | event_slug | TEXT | False | — | 0 |
| 5 | question | TEXT | False | — | 0 |
| 6 | category | TEXT | False | — | 0 |
| 7 | token_id_yes | TEXT | False | — | 0 |
| 8 | token_id_no | TEXT | False | — | 0 |
| 9 | outcome_yes | TEXT | False | — | 0 |
| 10 | outcome_no | TEXT | False | — | 0 |
| 11 | market_start_at | TEXT | False | — | 0 |
| 12 | market_end_at | TEXT | False | — | 0 |
| 13 | active | INTEGER | True | 0 | 0 |
| 14 | closed | INTEGER | True | 0 | 0 |
| 15 | archived | INTEGER | True | 0 | 0 |
| 16 | exact_condition_match | INTEGER | True | 0 | 0 |
| 17 | exact_token_match | INTEGER | True | 0 | 0 |
| 18 | exact_market_id_match | INTEGER | True | 0 | 0 |
| 19 | exact_slug_match | INTEGER | True | 0 | 0 |
| 20 | inferred_title_match | INTEGER | True | 0 | 0 |
| 21 | mapping_method | TEXT | True | 'UNMAPPED' | 0 |
| 22 | mapping_confidence | REAL | True | 0 | 0 |
| 23 | verified | INTEGER | True | 0 | 0 |
| 24 | verification_reason | TEXT | False | — | 0 |
| 25 | source_tables_json | TEXT | False | — | 0 |
| 26 | alternate_identifiers_json | TEXT | False | — | 0 |
| 27 | metadata_json | TEXT | False | — | 0 |
| 28 | first_seen_at | TEXT | True | — | 0 |
| 29 | last_seen_at | TEXT | True | — | 0 |
| 30 | last_verified_at | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_identifier_registry_verified | False | c | False | verified, mapping_confidence |
| idx_market_identifier_registry_token_no | False | c | False | token_id_no |
| idx_market_identifier_registry_token_yes | False | c | False | token_id_yes |
| idx_market_identifier_registry_event_slug | False | c | False | event_slug |
| idx_market_identifier_registry_market_slug | False | c | False | market_slug |
| idx_market_identifier_registry_event | False | c | False | gamma_event_id |
| idx_market_identifier_registry_gamma_market | False | c | False | gamma_market_id |
| sqlite_autoindex_market_identifier_registry_1 | True | pk | False | condition_id |

#### Source References

- `src/canonical_market_identity_engine.py:298,474`
- `src/market_identifier_registry_engine.py:319,381,387,393,399,405,411,417,443,2485,2513,2996`
- `src/market_identity_enrichment_engine.py:195,425`

#### Create SQL

```sql
CREATE TABLE market_identifier_registry (
                condition_id TEXT PRIMARY KEY,

                gamma_market_id TEXT,
                gamma_event_id TEXT,

                market_slug TEXT,
                event_slug TEXT,

                question TEXT,
                category TEXT,

                token_id_yes TEXT,
                token_id_no TEXT,

                outcome_yes TEXT,
                outcome_no TEXT,

                market_start_at TEXT,
                market_end_at TEXT,

                active INTEGER NOT NULL DEFAULT 0,
                closed INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,

                exact_condition_match INTEGER
                    NOT NULL DEFAULT 0,

                exact_token_match INTEGER
                    NOT NULL DEFAULT 0,

                exact_market_id_match INTEGER
                    NOT NULL DEFAULT 0,

                exact_slug_match INTEGER
                    NOT NULL DEFAULT 0,

                inferred_title_match INTEGER
                    NOT NULL DEFAULT 0,

                mapping_method TEXT
                    NOT NULL DEFAULT 'UNMAPPED',

                mapping_confidence REAL
                    NOT NULL DEFAULT 0,

                verified INTEGER
                    NOT NULL DEFAULT 0,

                verification_reason TEXT,

                source_tables_json TEXT,
                alternate_identifiers_json TEXT,
                metadata_json TEXT,

                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                last_verified_at TEXT
            )
```

### `market_identifier_runs`

- Row count: `2`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | gamma_markets_loaded | INTEGER | True | 0 | 0 |
| 5 | gamma_outcomes_loaded | INTEGER | True | 0 | 0 |
| 6 | source_rows_scanned | INTEGER | True | 0 | 0 |
| 7 | registry_rows_saved | INTEGER | True | 0 | 0 |
| 8 | aliases_saved | INTEGER | True | 0 | 0 |
| 9 | exact_condition_matches | INTEGER | True | 0 | 0 |
| 10 | exact_token_matches | INTEGER | True | 0 | 0 |
| 11 | exact_market_id_matches | INTEGER | True | 0 | 0 |
| 12 | exact_slug_matches | INTEGER | True | 0 | 0 |
| 13 | inferred_title_matches | INTEGER | True | 0 | 0 |
| 14 | unmapped_rows_saved | INTEGER | True | 0 | 0 |
| 15 | status | TEXT | True | — | 0 |
| 16 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/market_identifier_registry_engine.py:490,2577,2615,3011`

#### Create SQL

```sql
CREATE TABLE market_identifier_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                gamma_markets_loaded INTEGER
                    NOT NULL DEFAULT 0,

                gamma_outcomes_loaded INTEGER
                    NOT NULL DEFAULT 0,

                source_rows_scanned INTEGER
                    NOT NULL DEFAULT 0,

                registry_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                aliases_saved INTEGER
                    NOT NULL DEFAULT 0,

                exact_condition_matches INTEGER
                    NOT NULL DEFAULT 0,

                exact_token_matches INTEGER
                    NOT NULL DEFAULT 0,

                exact_market_id_matches INTEGER
                    NOT NULL DEFAULT 0,

                exact_slug_matches INTEGER
                    NOT NULL DEFAULT 0,

                inferred_title_matches INTEGER
                    NOT NULL DEFAULT 0,

                unmapped_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `market_identifier_unmapped`

- Row count: `32480`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | unmapped_key | TEXT | False | — | 1 |
| 1 | source_table | TEXT | True | — | 0 |
| 2 | source_row_identifier | TEXT | False | — | 0 |
| 3 | source_condition_id | TEXT | False | — | 0 |
| 4 | source_market_id | TEXT | False | — | 0 |
| 5 | source_asset_id | TEXT | False | — | 0 |
| 6 | source_slug | TEXT | False | — | 0 |
| 7 | source_event_slug | TEXT | False | — | 0 |
| 8 | source_title | TEXT | False | — | 0 |
| 9 | best_candidate_condition_id | TEXT | False | — | 0 |
| 10 | best_candidate_title | TEXT | False | — | 0 |
| 11 | best_candidate_confidence | REAL | True | 0 | 0 |
| 12 | failure_reason | TEXT | True | — | 0 |
| 13 | observed_at | TEXT | True | — | 0 |
| 14 | metadata_json | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_identifier_unmapped_source | False | c | False | source_table, best_candidate_confidence |
| sqlite_autoindex_market_identifier_unmapped_1 | True | pk | False | unmapped_key |

#### Source References

- `src/gamma_registry_expansion_engine.py:651,656`
- `src/market_identifier_registry_engine.py:460,485,2495,2509,3006`

#### Create SQL

```sql
CREATE TABLE market_identifier_unmapped (
                unmapped_key TEXT PRIMARY KEY,

                source_table TEXT NOT NULL,
                source_row_identifier TEXT,
                source_condition_id TEXT,
                source_market_id TEXT,
                source_asset_id TEXT,
                source_slug TEXT,
                source_event_slug TEXT,
                source_title TEXT,

                best_candidate_condition_id TEXT,
                best_candidate_title TEXT,
                best_candidate_confidence REAL
                    NOT NULL DEFAULT 0,

                failure_reason TEXT NOT NULL,

                observed_at TEXT NOT NULL,
                metadata_json TEXT
            )
```

### `market_identities`

- Row count: `1237`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | canonical_key | TEXT | False | — | 1 |
| 1 | canonical_condition_id | TEXT | False | — | 0 |
| 2 | gamma_market_id | TEXT | False | — | 0 |
| 3 | gamma_event_id | TEXT | False | — | 0 |
| 4 | market_slug | TEXT | False | — | 0 |
| 5 | event_slug | TEXT | False | — | 0 |
| 6 | canonical_title | TEXT | True | — | 0 |
| 7 | normalized_title | TEXT | True | — | 0 |
| 8 | outcome | TEXT | False | — | 0 |
| 9 | normalized_outcome | TEXT | False | — | 0 |
| 10 | market_type | TEXT | False | — | 0 |
| 11 | participant_one | TEXT | False | — | 0 |
| 12 | participant_two | TEXT | False | — | 0 |
| 13 | game_start_time | TEXT | False | — | 0 |
| 14 | active | INTEGER | False | — | 0 |
| 15 | closed | INTEGER | False | — | 0 |
| 16 | resolved | INTEGER | False | — | 0 |
| 17 | payload_json | TEXT | False | — | 0 |
| 18 | first_seen_at | TEXT | True | — | 0 |
| 19 | last_seen_at | TEXT | True | — | 0 |
| 20 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_identities_title | False | c | False | normalized_title |
| idx_market_identities_condition | False | c | False | canonical_condition_id |
| sqlite_autoindex_market_identities_1 | True | pk | False | canonical_key |

#### Source References

- `src/market_identity_engine.py:166,191,194,370,542,946`

#### Create SQL

```sql
CREATE TABLE market_identities (
                canonical_key TEXT PRIMARY KEY,
                canonical_condition_id TEXT,
                gamma_market_id TEXT,
                gamma_event_id TEXT,
                market_slug TEXT,
                event_slug TEXT,
                canonical_title TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                outcome TEXT,
                normalized_outcome TEXT,
                market_type TEXT,
                participant_one TEXT,
                participant_two TEXT,
                game_start_time TEXT,
                active INTEGER,
                closed INTEGER,
                resolved INTEGER,
                payload_json TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `market_identity_aliases`

- Row count: `6181`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | alias_key | TEXT | False | — | 1 |
| 1 | canonical_key | TEXT | True | — | 0 |
| 2 | alias_type | TEXT | True | — | 0 |
| 3 | alias_value | TEXT | True | — | 0 |
| 4 | normalized_alias | TEXT | True | — | 0 |
| 5 | confidence | REAL | True | 100 | 0 |
| 6 | source_name | TEXT | True | — | 0 |
| 7 | created_at | TEXT | True | — | 0 |
| 8 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_identity_aliases_lookup | False | c | False | alias_type, normalized_alias |
| sqlite_autoindex_market_identity_aliases_1 | True | pk | False | alias_key |

#### Source References

- `src/market_identity_engine.py:196,209,428,947`

#### Create SQL

```sql
CREATE TABLE market_identity_aliases (
                alias_key TEXT PRIMARY KEY,
                canonical_key TEXT NOT NULL,
                alias_type TEXT NOT NULL,
                alias_value TEXT NOT NULL,
                normalized_alias TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 100,
                source_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `market_identity_enrichment_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | source_rows_scanned | INTEGER | True | 0 | 0 |
| 5 | enriched_rows | INTEGER | True | 0 | 0 |
| 6 | verified_rows | INTEGER | True | 0 | 0 |
| 7 | actionable_identity_rows | INTEGER | True | 0 | 0 |
| 8 | unresolved_rows | INTEGER | True | 0 | 0 |
| 9 | status | TEXT | True | — | 0 |
| 10 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/market_identity_enrichment_engine.py:320,1473,1503,1818`

#### Create SQL

```sql
CREATE TABLE market_identity_enrichment_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                source_rows_scanned INTEGER
                    NOT NULL DEFAULT 0,

                enriched_rows INTEGER
                    NOT NULL DEFAULT 0,

                verified_rows INTEGER
                    NOT NULL DEFAULT 0,

                actionable_identity_rows INTEGER
                    NOT NULL DEFAULT 0,

                unresolved_rows INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `market_identity_enrichments`

- Row count: `8358`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | enrichment_key | TEXT | False | — | 1 |
| 1 | source_table | TEXT | True | — | 0 |
| 2 | source_row_identifier | TEXT | True | — | 0 |
| 3 | source_condition_id | TEXT | False | — | 0 |
| 4 | source_market_id | TEXT | False | — | 0 |
| 5 | source_asset_id | TEXT | False | — | 0 |
| 6 | source_market_slug | TEXT | False | — | 0 |
| 7 | source_event_slug | TEXT | False | — | 0 |
| 8 | source_title | TEXT | False | — | 0 |
| 9 | canonical_condition_id | TEXT | False | — | 0 |
| 10 | gamma_market_id | TEXT | False | — | 0 |
| 11 | gamma_event_id | TEXT | False | — | 0 |
| 12 | market_slug | TEXT | False | — | 0 |
| 13 | event_slug | TEXT | False | — | 0 |
| 14 | question | TEXT | False | — | 0 |
| 15 | category | TEXT | False | — | 0 |
| 16 | token_id_yes | TEXT | False | — | 0 |
| 17 | token_id_no | TEXT | False | — | 0 |
| 18 | outcome_yes | TEXT | False | — | 0 |
| 19 | outcome_no | TEXT | False | — | 0 |
| 20 | market_start_at | TEXT | False | — | 0 |
| 21 | market_end_at | TEXT | False | — | 0 |
| 22 | mapping_method | TEXT | True | 'UNMAPPED' | 0 |
| 23 | mapping_confidence | REAL | True | 0 | 0 |
| 24 | verified | INTEGER | True | 0 | 0 |
| 25 | actionable_identity | INTEGER | True | 0 | 0 |
| 26 | enrichment_status | TEXT | True | 'UNRESOLVED' | 0 |
| 27 | resolution_reason | TEXT | False | — | 0 |
| 28 | source_identity_json | TEXT | False | — | 0 |
| 29 | canonical_identity_json | TEXT | False | — | 0 |
| 30 | metadata_json | TEXT | False | — | 0 |
| 31 | enriched_at | TEXT | True | — | 0 |
| 32 | created_at | TEXT | True | — | 0 |
| 33 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_identity_enrichments_status | False | c | False | enrichment_status, mapping_confidence |
| idx_market_identity_enrichments_condition | False | c | False | canonical_condition_id, verified |
| idx_market_identity_enrichments_source | False | c | False | source_table, source_row_identifier |
| sqlite_autoindex_market_identity_enrichments_1 | True | pk | False | enrichment_key |

#### Source References

- `src/gamma_registry_expansion_engine.py:627,632`
- `src/market_identity_enrichment_engine.py:205,265,272,279,1354,1366,1808,1824`

#### Create SQL

```sql
CREATE TABLE market_identity_enrichments (
                enrichment_key TEXT PRIMARY KEY,

                source_table TEXT NOT NULL,
                source_row_identifier TEXT NOT NULL,

                source_condition_id TEXT,
                source_market_id TEXT,
                source_asset_id TEXT,
                source_market_slug TEXT,
                source_event_slug TEXT,
                source_title TEXT,

                canonical_condition_id TEXT,
                gamma_market_id TEXT,
                gamma_event_id TEXT,

                market_slug TEXT,
                event_slug TEXT,

                question TEXT,
                category TEXT,

                token_id_yes TEXT,
                token_id_no TEXT,

                outcome_yes TEXT,
                outcome_no TEXT,

                market_start_at TEXT,
                market_end_at TEXT,

                mapping_method TEXT
                    NOT NULL DEFAULT 'UNMAPPED',

                mapping_confidence REAL
                    NOT NULL DEFAULT 0,

                verified INTEGER
                    NOT NULL DEFAULT 0,

                actionable_identity INTEGER
                    NOT NULL DEFAULT 0,

                enrichment_status TEXT
                    NOT NULL DEFAULT 'UNRESOLVED',

                resolution_reason TEXT,

                source_identity_json TEXT,
                canonical_identity_json TEXT,
                metadata_json TEXT,

                enriched_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `market_identity_matches`

- Row count: `862`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | source_key | TEXT | False | — | 1 |
| 1 | source_name | TEXT | True | — | 0 |
| 2 | source_market_id | TEXT | False | — | 0 |
| 3 | source_title | TEXT | True | — | 0 |
| 4 | source_outcome | TEXT | False | — | 0 |
| 5 | canonical_key | TEXT | False | — | 0 |
| 6 | matched_condition_id | TEXT | False | — | 0 |
| 7 | matched_title | TEXT | False | — | 0 |
| 8 | match_method | TEXT | True | — | 0 |
| 9 | match_confidence | REAL | True | 0 | 0 |
| 10 | accepted | INTEGER | True | 0 | 0 |
| 11 | review_required | INTEGER | True | 0 | 0 |
| 12 | rejection_reason | TEXT | False | — | 0 |
| 13 | details_json | TEXT | False | — | 0 |
| 14 | calculated_at | TEXT | True | — | 0 |
| 15 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_identity_matches_result | False | c | False | accepted, match_method, match_confidence |
| sqlite_autoindex_market_identity_matches_1 | True | pk | False | source_key |

#### Source References

- `src/market_identity_engine.py:211,231,725,948`

#### Create SQL

```sql
CREATE TABLE market_identity_matches (
                source_key TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                source_market_id TEXT,
                source_title TEXT NOT NULL,
                source_outcome TEXT,
                canonical_key TEXT,
                matched_condition_id TEXT,
                matched_title TEXT,
                match_method TEXT NOT NULL,
                match_confidence REAL NOT NULL DEFAULT 0,
                accepted INTEGER NOT NULL DEFAULT 0,
                review_required INTEGER NOT NULL DEFAULT 0,
                rejection_reason TEXT,
                details_json TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `market_identity_runs`

- Row count: `3`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | gamma_events_loaded | INTEGER | True | 0 | 0 |
| 5 | gamma_markets_loaded | INTEGER | True | 0 | 0 |
| 6 | local_sources_loaded | INTEGER | True | 0 | 0 |
| 7 | accepted_matches | INTEGER | True | 0 | 0 |
| 8 | review_matches | INTEGER | True | 0 | 0 |
| 9 | unresolved_sources | INTEGER | True | 0 | 0 |
| 10 | status | TEXT | True | — | 0 |
| 11 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/market_identity_engine.py:233,756,791,949`

#### Create SQL

```sql
CREATE TABLE market_identity_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,
                gamma_events_loaded INTEGER NOT NULL DEFAULT 0,
                gamma_markets_loaded INTEGER NOT NULL DEFAULT 0,
                local_sources_loaded INTEGER NOT NULL DEFAULT 0,
                accepted_matches INTEGER NOT NULL DEFAULT 0,
                review_matches INTEGER NOT NULL DEFAULT 0,
                unresolved_sources INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `market_identity_source_summary`

- Row count: `3`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | source_table | TEXT | False | — | 1 |
| 1 | source_rows_scanned | INTEGER | True | 0 | 0 |
| 2 | enriched_rows | INTEGER | True | 0 | 0 |
| 3 | verified_rows | INTEGER | True | 0 | 0 |
| 4 | actionable_identity_rows | INTEGER | True | 0 | 0 |
| 5 | unresolved_rows | INTEGER | True | 0 | 0 |
| 6 | exact_condition_matches | INTEGER | True | 0 | 0 |
| 7 | exact_token_matches | INTEGER | True | 0 | 0 |
| 8 | exact_market_id_matches | INTEGER | True | 0 | 0 |
| 9 | exact_slug_matches | INTEGER | True | 0 | 0 |
| 10 | title_matches | INTEGER | True | 0 | 0 |
| 11 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_market_identity_source_summary_1 | True | pk | False | source_table |

#### Source References

- `src/market_identity_enrichment_engine.py:284,1370,1385,1813`

#### Create SQL

```sql
CREATE TABLE market_identity_source_summary (
                source_table TEXT PRIMARY KEY,

                source_rows_scanned INTEGER
                    NOT NULL DEFAULT 0,

                enriched_rows INTEGER
                    NOT NULL DEFAULT 0,

                verified_rows INTEGER
                    NOT NULL DEFAULT 0,

                actionable_identity_rows INTEGER
                    NOT NULL DEFAULT 0,

                unresolved_rows INTEGER
                    NOT NULL DEFAULT 0,

                exact_condition_matches INTEGER
                    NOT NULL DEFAULT 0,

                exact_token_matches INTEGER
                    NOT NULL DEFAULT 0,

                exact_market_id_matches INTEGER
                    NOT NULL DEFAULT 0,

                exact_slug_matches INTEGER
                    NOT NULL DEFAULT 0,

                title_matches INTEGER
                    NOT NULL DEFAULT 0,

                updated_at TEXT NOT NULL
            )
```

### `market_leaders`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | market_id | TEXT | True | — | 0 |
| 2 | title | TEXT | True | — | 0 |
| 3 | outcome | TEXT | True | — | 0 |
| 4 | wallet | TEXT | True | — | 0 |
| 5 | leadership_rank | INTEGER | True | — | 0 |
| 6 | leadership_score | REAL | True | 0 | 0 |
| 7 | wallet_score | REAL | True | 0 | 0 |
| 8 | wallet_grade | TEXT | True | 'UNRATED' | 0 |
| 9 | current_value | REAL | True | 0 | 0 |
| 10 | current_shares | REAL | True | 0 | 0 |
| 11 | capital_share | REAL | True | 0 | 0 |
| 12 | recent_value_change | REAL | True | 0 | 0 |
| 13 | recent_share_change | REAL | True | 0 | 0 |
| 14 | average_entry_price | REAL | True | 0 | 0 |
| 15 | current_price | REAL | True | 0 | 0 |
| 16 | open_pnl | REAL | True | 0 | 0 |
| 17 | first_observed_at | TEXT | False | — | 0 |
| 18 | latest_observed_at | TEXT | False | — | 0 |
| 19 | calculated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_leaders_rank | False | c | False | market_id, outcome, leadership_rank |
| idx_market_leaders_wallet | False | c | False | wallet |
| idx_market_leaders_market | False | c | False | market_id, outcome |

#### Source References

- `src/intelligence_database.py:350,386,394,402,629`

#### Create SQL

```sql
CREATE TABLE market_leaders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            market_id TEXT NOT NULL,
            title TEXT NOT NULL,
            outcome TEXT NOT NULL,

            wallet TEXT NOT NULL,
            leadership_rank INTEGER NOT NULL,

            leadership_score REAL NOT NULL DEFAULT 0,
            wallet_score REAL NOT NULL DEFAULT 0,
            wallet_grade TEXT NOT NULL DEFAULT 'UNRATED',

            current_value REAL NOT NULL DEFAULT 0,
            current_shares REAL NOT NULL DEFAULT 0,
            capital_share REAL NOT NULL DEFAULT 0,

            recent_value_change REAL NOT NULL DEFAULT 0,
            recent_share_change REAL NOT NULL DEFAULT 0,

            average_entry_price REAL NOT NULL DEFAULT 0,
            current_price REAL NOT NULL DEFAULT 0,
            open_pnl REAL NOT NULL DEFAULT 0,

            first_observed_at TEXT,
            latest_observed_at TEXT,
            calculated_at TEXT NOT NULL
        )
```

### `market_lifecycle_manager_audit`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | market_id | TEXT | True | — | 0 |
| 3 | title | TEXT | False | — | 0 |
| 4 | lifecycle_status | TEXT | True | — | 0 |
| 5 | action | TEXT | True | — | 0 |
| 6 | reason_code | TEXT | True | — | 0 |
| 7 | reason_detail | TEXT | False | — | 0 |
| 8 | canonical_present | INTEGER | True | 0 | 0 |
| 9 | legacy_present | INTEGER | True | 0 | 0 |
| 10 | active | INTEGER | True | 0 | 0 |
| 11 | closed | INTEGER | True | 0 | 0 |
| 12 | archived | INTEGER | True | 0 | 0 |
| 13 | accepting_orders | INTEGER | True | 0 | 0 |
| 14 | restricted | INTEGER | True | 0 | 0 |
| 15 | tradable | INTEGER | True | 0 | 0 |
| 16 | source_updated_at | TEXT | False | — | 0 |
| 17 | audited_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| run_id | market_lifecycle_manager_runs | run_id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_lifecycle_audit_status | False | c | False | lifecycle_status, audited_at |
| idx_market_lifecycle_audit_market | False | c | False | market_id, audited_at |

#### Source References

- `src/market_lifecycle_manager.py:25`

#### Create SQL

```sql
CREATE TABLE "market_lifecycle_manager_audit" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    title TEXT,
                    lifecycle_status TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    reason_detail TEXT,
                    canonical_present INTEGER NOT NULL DEFAULT 0,
                    legacy_present INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 0,
                    closed INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 0,
                    accepting_orders INTEGER NOT NULL DEFAULT 0,
                    restricted INTEGER NOT NULL DEFAULT 0,
                    tradable INTEGER NOT NULL DEFAULT 0,
                    source_updated_at TEXT,
                    audited_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES "market_lifecycle_manager_runs"(run_id)
                        ON DELETE CASCADE
                )
```

### `market_lifecycle_manager_runs`

- Row count: `2`
- Referenced by: `market_lifecycle_manager_audit`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | mode | TEXT | True | — | 0 |
| 5 | canonical_rows | INTEGER | True | 0 | 0 |
| 6 | legacy_rows | INTEGER | True | 0 | 0 |
| 7 | decisions | INTEGER | True | 0 | 0 |
| 8 | actionable_changes | INTEGER | True | 0 | 0 |
| 9 | canonical_updates | INTEGER | True | 0 | 0 |
| 10 | legacy_only | INTEGER | True | 0 | 0 |
| 11 | canonical_only | INTEGER | True | 0 | 0 |
| 12 | tradable | INTEGER | True | 0 | 0 |
| 13 | non_tradable | INTEGER | True | 0 | 0 |
| 14 | status | TEXT | True | — | 0 |
| 15 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_market_lifecycle_manager_runs_1 | True | pk | False | run_id |

#### Source References

- `src/market_lifecycle_manager.py:24`

#### Create SQL

```sql
CREATE TABLE "market_lifecycle_manager_runs" (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    elapsed_seconds REAL,
                    mode TEXT NOT NULL,
                    canonical_rows INTEGER NOT NULL DEFAULT 0,
                    legacy_rows INTEGER NOT NULL DEFAULT 0,
                    decisions INTEGER NOT NULL DEFAULT 0,
                    actionable_changes INTEGER NOT NULL DEFAULT 0,
                    canonical_updates INTEGER NOT NULL DEFAULT 0,
                    legacy_only INTEGER NOT NULL DEFAULT 0,
                    canonical_only INTEGER NOT NULL DEFAULT 0,
                    tradable INTEGER NOT NULL DEFAULT 0,
                    non_tradable INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
```

### `market_mapper_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | source_rows_loaded | INTEGER | True | 0 | 0 |
| 5 | exact_condition_matches | INTEGER | True | 0 | 0 |
| 6 | unresolved_rows | INTEGER | True | 0 | 0 |
| 7 | mappings_saved | INTEGER | True | 0 | 0 |
| 8 | outcomes_saved | INTEGER | True | 0 | 0 |
| 9 | status | TEXT | True | — | 0 |
| 10 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/market_mapper_engine.py:255,1035,1075`

#### Create SQL

```sql
CREATE TABLE market_mapper_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                source_rows_loaded INTEGER
                    NOT NULL DEFAULT 0,

                exact_condition_matches INTEGER
                    NOT NULL DEFAULT 0,

                unresolved_rows INTEGER
                    NOT NULL DEFAULT 0,

                mappings_saved INTEGER
                    NOT NULL DEFAULT 0,

                outcomes_saved INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `market_mapping_outcomes`

- Row count: `232`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | mapping_outcome_key | TEXT | False | — | 1 |
| 1 | mapping_key | TEXT | True | — | 0 |
| 2 | gamma_market_id | TEXT | True | — | 0 |
| 3 | gamma_event_id | TEXT | False | — | 0 |
| 4 | condition_id | TEXT | False | — | 0 |
| 5 | outcome_index | INTEGER | True | — | 0 |
| 6 | outcome_name | TEXT | True | — | 0 |
| 7 | token_id | TEXT | False | — | 0 |
| 8 | implied_price | REAL | False | — | 0 |
| 9 | winner | INTEGER | True | 0 | 0 |
| 10 | created_at | TEXT | True | — | 0 |
| 11 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| mapping_key | market_mappings | mapping_key | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_mapping_outcomes_token | False | c | False | token_id |
| idx_market_mapping_outcomes_mapping | False | c | False | mapping_key, outcome_index |
| sqlite_autoindex_market_mapping_outcomes_1 | True | pk | False | mapping_outcome_key |

#### Source References

- `src/market_mapper_engine.py:215,244,251,927,951,1326`

#### Create SQL

```sql
CREATE TABLE market_mapping_outcomes (
                mapping_outcome_key TEXT PRIMARY KEY,

                mapping_key TEXT NOT NULL,
                gamma_market_id TEXT NOT NULL,
                gamma_event_id TEXT,
                condition_id TEXT,

                outcome_index INTEGER NOT NULL,
                outcome_name TEXT NOT NULL,
                token_id TEXT,
                implied_price REAL,
                winner INTEGER
                    NOT NULL DEFAULT 0,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(
                    mapping_key
                )
                REFERENCES market_mappings(
                    mapping_key
                )
                ON DELETE CASCADE
            )
```

### `market_mappings`

- Row count: `882`
- Referenced by: `market_mapping_outcomes`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | mapping_key | TEXT | False | — | 1 |
| 1 | source_table | TEXT | True | — | 0 |
| 2 | source_market_id | TEXT | True | — | 0 |
| 3 | source_title | TEXT | False | — | 0 |
| 4 | source_outcome | TEXT | False | — | 0 |
| 5 | gamma_market_id | TEXT | False | — | 0 |
| 6 | gamma_event_id | TEXT | False | — | 0 |
| 7 | condition_id | TEXT | False | — | 0 |
| 8 | canonical_question | TEXT | False | — | 0 |
| 9 | canonical_slug | TEXT | False | — | 0 |
| 10 | match_method | TEXT | True | — | 0 |
| 11 | match_confidence | REAL | True | 0 | 0 |
| 12 | mapping_status | TEXT | True | — | 0 |
| 13 | outcome_count | INTEGER | True | 0 | 0 |
| 14 | token_count | INTEGER | True | 0 | 0 |
| 15 | source_payload_json | TEXT | False | — | 0 |
| 16 | registry_payload_json | TEXT | False | — | 0 |
| 17 | first_mapped_at | TEXT | True | — | 0 |
| 18 | last_mapped_at | TEXT | True | — | 0 |
| 19 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_mappings_status | False | c | False | mapping_status, match_confidence |
| idx_market_mappings_condition | False | c | False | condition_id |
| idx_market_mappings_source | False | c | False | source_table, source_market_id |
| sqlite_autoindex_market_mappings_1 | True | pk | False | mapping_key |

#### Source References

- `src/market_mapper_engine.py:160,197,204,210,236,847,896,1321`
- `src/market_resolution_engine.py:457,464`
- `src/signal_fusion_engine.py:763,770`
- `src/wallet_performance_engine.py:532,541`

#### Create SQL

```sql
CREATE TABLE market_mappings (
                mapping_key TEXT PRIMARY KEY,

                source_table TEXT NOT NULL,
                source_market_id TEXT NOT NULL,
                source_title TEXT,
                source_outcome TEXT,

                gamma_market_id TEXT,
                gamma_event_id TEXT,
                condition_id TEXT,

                canonical_question TEXT,
                canonical_slug TEXT,

                match_method TEXT NOT NULL,
                match_confidence REAL
                    NOT NULL DEFAULT 0,

                mapping_status TEXT NOT NULL,

                outcome_count INTEGER
                    NOT NULL DEFAULT 0,

                token_count INTEGER
                    NOT NULL DEFAULT 0,

                source_payload_json TEXT,
                registry_payload_json TEXT,

                first_mapped_at TEXT NOT NULL,
                last_mapped_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `market_memory_runs`

- Row count: `3`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | lookback_hours | INTEGER | True | — | 0 |
| 5 | trades_loaded | INTEGER | True | 0 | 0 |
| 6 | markets_observed | INTEGER | True | 0 | 0 |
| 7 | snapshots_saved | INTEGER | True | 0 | 0 |
| 8 | wallet_flows_saved | INTEGER | True | 0 | 0 |
| 9 | status | TEXT | True | — | 0 |
| 10 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/market_memory_engine.py:359,1937,1979,2276`

#### Create SQL

```sql
CREATE TABLE market_memory_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                lookback_hours INTEGER NOT NULL,

                trades_loaded INTEGER NOT NULL DEFAULT 0,
                markets_observed INTEGER NOT NULL DEFAULT 0,
                snapshots_saved INTEGER NOT NULL DEFAULT 0,
                wallet_flows_saved INTEGER NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `market_memory_snapshots`

- Row count: `8282`
- Referenced by: `market_memory_wallet_flows`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | snapshot_key | TEXT | False | — | 1 |
| 1 | condition_id | TEXT | True | — | 0 |
| 2 | market_id | TEXT | False | — | 0 |
| 3 | event_id | TEXT | False | — | 0 |
| 4 | title | TEXT | False | — | 0 |
| 5 | slug | TEXT | False | — | 0 |
| 6 | event_slug | TEXT | False | — | 0 |
| 7 | category | TEXT | False | — | 0 |
| 8 | snapshot_at | TEXT | True | — | 0 |
| 9 | lookback_hours | INTEGER | True | — | 0 |
| 10 | current_price | REAL | False | — | 0 |
| 11 | average_trade_price | REAL | False | — | 0 |
| 12 | weighted_average_buy_price | REAL | False | — | 0 |
| 13 | weighted_average_sell_price | REAL | False | — | 0 |
| 14 | trade_count | INTEGER | True | 0 | 0 |
| 15 | unique_wallet_count | INTEGER | True | 0 | 0 |
| 16 | buy_trade_count | INTEGER | True | 0 | 0 |
| 17 | sell_trade_count | INTEGER | True | 0 | 0 |
| 18 | buy_notional | REAL | True | 0 | 0 |
| 19 | sell_notional | REAL | True | 0 | 0 |
| 20 | net_flow | REAL | True | 0 | 0 |
| 21 | gross_flow | REAL | True | 0 | 0 |
| 22 | elite_wallet_count | INTEGER | True | 0 | 0 |
| 23 | qualified_wallet_count | INTEGER | True | 0 | 0 |
| 24 | watchlist_wallet_count | INTEGER | True | 0 | 0 |
| 25 | candidate_wallet_count | INTEGER | True | 0 | 0 |
| 26 | elite_buy_notional | REAL | True | 0 | 0 |
| 27 | elite_sell_notional | REAL | True | 0 | 0 |
| 28 | qualified_buy_notional | REAL | True | 0 | 0 |
| 29 | qualified_sell_notional | REAL | True | 0 | 0 |
| 30 | watchlist_buy_notional | REAL | True | 0 | 0 |
| 31 | watchlist_sell_notional | REAL | True | 0 | 0 |
| 32 | bullish_wallet_count | INTEGER | True | 0 | 0 |
| 33 | bearish_wallet_count | INTEGER | True | 0 | 0 |
| 34 | neutral_wallet_count | INTEGER | True | 0 | 0 |
| 35 | bullish_wallet_share | REAL | True | 0 | 0 |
| 36 | bearish_wallet_share | REAL | True | 0 | 0 |
| 37 | largest_buyer_wallet | TEXT | False | — | 0 |
| 38 | largest_buyer_notional | REAL | True | 0 | 0 |
| 39 | largest_seller_wallet | TEXT | False | — | 0 |
| 40 | largest_seller_notional | REAL | True | 0 | 0 |
| 41 | strongest_wallet | TEXT | False | — | 0 |
| 42 | strongest_wallet_weight | REAL | True | 0 | 0 |
| 43 | smart_money_weight | REAL | True | 0 | 0 |
| 44 | consensus_strength | REAL | True | 0 | 0 |
| 45 | concentration_risk | REAL | True | 0 | 0 |
| 46 | market_memory_score | REAL | True | 0 | 0 |
| 47 | market_memory_grade | TEXT | True | 'PASS' | 0 |
| 48 | resolved | INTEGER | True | 0 | 0 |
| 49 | winning_outcome | TEXT | False | — | 0 |
| 50 | metadata_json | TEXT | False | — | 0 |
| 51 | created_at | TEXT | True | — | 0 |
| 52 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_memory_snapshots_score | False | c | False | market_memory_score, snapshot_at |
| idx_market_memory_snapshots_condition | False | c | False | condition_id, snapshot_at |
| sqlite_autoindex_market_memory_snapshots_1 | True | pk | False | snapshot_key |

#### Source References

- `src/condition_id_lineage_audit.py:32`
- `src/historical_market_reconciliation_engine.py:31`
- `src/market_identifier_registry_engine.py:1064`
- `src/market_identity_enrichment_engine.py:381`
- `src/market_memory_engine.py:221,297,304,341,1876,2266`
- `src/opportunity_ranking_engine.py:371,757,769`
- `src/prediction_engine.py:192,463,475`
- `src/registry_validation_gate.py:37`
- `src/smart_money_flow_engine.py:226,540,573`

#### Create SQL

```sql
CREATE TABLE market_memory_snapshots (
                snapshot_key TEXT PRIMARY KEY,

                condition_id TEXT NOT NULL,
                market_id TEXT,
                event_id TEXT,

                title TEXT,
                slug TEXT,
                event_slug TEXT,
                category TEXT,

                snapshot_at TEXT NOT NULL,
                lookback_hours INTEGER NOT NULL,

                current_price REAL,
                average_trade_price REAL,
                weighted_average_buy_price REAL,
                weighted_average_sell_price REAL,

                trade_count INTEGER NOT NULL DEFAULT 0,
                unique_wallet_count INTEGER NOT NULL DEFAULT 0,

                buy_trade_count INTEGER NOT NULL DEFAULT 0,
                sell_trade_count INTEGER NOT NULL DEFAULT 0,

                buy_notional REAL NOT NULL DEFAULT 0,
                sell_notional REAL NOT NULL DEFAULT 0,
                net_flow REAL NOT NULL DEFAULT 0,
                gross_flow REAL NOT NULL DEFAULT 0,

                elite_wallet_count INTEGER NOT NULL DEFAULT 0,
                qualified_wallet_count INTEGER NOT NULL DEFAULT 0,
                watchlist_wallet_count INTEGER NOT NULL DEFAULT 0,
                candidate_wallet_count INTEGER NOT NULL DEFAULT 0,

                elite_buy_notional REAL NOT NULL DEFAULT 0,
                elite_sell_notional REAL NOT NULL DEFAULT 0,
                qualified_buy_notional REAL NOT NULL DEFAULT 0,
                qualified_sell_notional REAL NOT NULL DEFAULT 0,
                watchlist_buy_notional REAL NOT NULL DEFAULT 0,
                watchlist_sell_notional REAL NOT NULL DEFAULT 0,

                bullish_wallet_count INTEGER NOT NULL DEFAULT 0,
                bearish_wallet_count INTEGER NOT NULL DEFAULT 0,
                neutral_wallet_count INTEGER NOT NULL DEFAULT 0,

                bullish_wallet_share REAL NOT NULL DEFAULT 0,
                bearish_wallet_share REAL NOT NULL DEFAULT 0,

                largest_buyer_wallet TEXT,
                largest_buyer_notional REAL NOT NULL DEFAULT 0,

                largest_seller_wallet TEXT,
                largest_seller_notional REAL NOT NULL DEFAULT 0,

                strongest_wallet TEXT,
                strongest_wallet_weight REAL NOT NULL DEFAULT 0,

                smart_money_weight REAL NOT NULL DEFAULT 0,
                consensus_strength REAL NOT NULL DEFAULT 0,
                concentration_risk REAL NOT NULL DEFAULT 0,
                market_memory_score REAL NOT NULL DEFAULT 0,
                market_memory_grade TEXT NOT NULL DEFAULT 'PASS',

                resolved INTEGER NOT NULL DEFAULT 0,
                winning_outcome TEXT,

                metadata_json TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `market_memory_wallet_flows`

- Row count: `8875`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | flow_key | TEXT | False | — | 1 |
| 1 | snapshot_key | TEXT | True | — | 0 |
| 2 | condition_id | TEXT | True | — | 0 |
| 3 | wallet | TEXT | True | — | 0 |
| 4 | wallet_status | TEXT | False | — | 0 |
| 5 | elite_tier | TEXT | False | — | 0 |
| 6 | wallet_influence_score | REAL | True | 0 | 0 |
| 7 | consensus_weight | REAL | True | 0 | 0 |
| 8 | prediction_weight | REAL | True | 0 | 0 |
| 9 | buy_trade_count | INTEGER | True | 0 | 0 |
| 10 | sell_trade_count | INTEGER | True | 0 | 0 |
| 11 | buy_notional | REAL | True | 0 | 0 |
| 12 | sell_notional | REAL | True | 0 | 0 |
| 13 | net_flow | REAL | True | 0 | 0 |
| 14 | average_buy_price | REAL | False | — | 0 |
| 15 | average_sell_price | REAL | False | — | 0 |
| 16 | directional_label | TEXT | True | 'NEUTRAL' | 0 |
| 17 | first_trade_timestamp | INTEGER | False | — | 0 |
| 18 | last_trade_timestamp | INTEGER | False | — | 0 |
| 19 | created_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| snapshot_key | market_memory_snapshots | snapshot_key | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_memory_wallet_flows_wallet | False | c | False | wallet, condition_id |
| idx_market_memory_wallet_flows_market | False | c | False | condition_id, net_flow |
| sqlite_autoindex_market_memory_wallet_flows_1 | True | pk | False | flow_key |

#### Source References

- `src/market_memory_engine.py:309,347,354,1881,2271`
- `src/smart_money_flow_engine.py:231,606`

#### Create SQL

```sql
CREATE TABLE market_memory_wallet_flows (
                flow_key TEXT PRIMARY KEY,

                snapshot_key TEXT NOT NULL,
                condition_id TEXT NOT NULL,
                wallet TEXT NOT NULL,

                wallet_status TEXT,
                elite_tier TEXT,

                wallet_influence_score REAL NOT NULL DEFAULT 0,
                consensus_weight REAL NOT NULL DEFAULT 0,
                prediction_weight REAL NOT NULL DEFAULT 0,

                buy_trade_count INTEGER NOT NULL DEFAULT 0,
                sell_trade_count INTEGER NOT NULL DEFAULT 0,

                buy_notional REAL NOT NULL DEFAULT 0,
                sell_notional REAL NOT NULL DEFAULT 0,
                net_flow REAL NOT NULL DEFAULT 0,

                average_buy_price REAL,
                average_sell_price REAL,

                directional_label TEXT NOT NULL DEFAULT 'NEUTRAL',

                first_trade_timestamp INTEGER,
                last_trade_timestamp INTEGER,

                created_at TEXT NOT NULL,

                FOREIGN KEY(snapshot_key)
                    REFERENCES market_memory_snapshots(snapshot_key)
                    ON DELETE CASCADE
            )
```

### `market_metadata`

- Row count: `102`
- Referenced by: `market_status_history`, `monitor_alerts`, `tracked_markets`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | market_id | TEXT | False | — | 1 |
| 1 | gamma_market_id | TEXT | False | — | 0 |
| 2 | condition_id | TEXT | False | — | 0 |
| 3 | event_id | TEXT | False | — | 0 |
| 4 | title | TEXT | True | — | 0 |
| 5 | event_title | TEXT | False | — | 0 |
| 6 | outcome | TEXT | False | — | 0 |
| 7 | market_slug | TEXT | False | — | 0 |
| 8 | event_slug | TEXT | False | — | 0 |
| 9 | sports_slug | TEXT | False | — | 0 |
| 10 | category | TEXT | False | — | 0 |
| 11 | sport | TEXT | False | — | 0 |
| 12 | league | TEXT | False | — | 0 |
| 13 | start_time | TEXT | False | — | 0 |
| 14 | game_start_time | TEXT | False | — | 0 |
| 15 | end_time | TEXT | False | — | 0 |
| 16 | lifecycle_status | TEXT | True | 'UNKNOWN' | 0 |
| 17 | is_pregame | INTEGER | True | 0 | 0 |
| 18 | is_live | INTEGER | True | 0 | 0 |
| 19 | is_ended | INTEGER | True | 0 | 0 |
| 20 | is_closed | INTEGER | True | 0 | 0 |
| 21 | is_resolved | INTEGER | True | 0 | 0 |
| 22 | score | TEXT | False | — | 0 |
| 23 | period | TEXT | False | — | 0 |
| 24 | elapsed | TEXT | False | — | 0 |
| 25 | winning_outcome | TEXT | False | — | 0 |
| 26 | resolution_status | TEXT | True | 'UNRESOLVED' | 0 |
| 27 | active | INTEGER | True | 0 | 0 |
| 28 | accepting_orders | INTEGER | True | 0 | 0 |
| 29 | current_price | REAL | False | — | 0 |
| 30 | outcome_prices_json | TEXT | False | — | 0 |
| 31 | seconds_to_start | INTEGER | False | — | 0 |
| 32 | seconds_since_start | INTEGER | False | — | 0 |
| 33 | source_updated_at | TEXT | False | — | 0 |
| 34 | first_seen_at | TEXT | True | — | 0 |
| 35 | last_checked_at | TEXT | True | — | 0 |
| 36 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_metadata_resolution | False | c | False | is_resolved, resolution_status |
| idx_market_metadata_live | False | c | False | is_live, is_ended |
| idx_market_metadata_sports_slug | False | c | False | sports_slug |
| idx_market_metadata_start_time | False | c | False | game_start_time |
| idx_market_metadata_status | False | c | False | lifecycle_status |
| sqlite_autoindex_market_metadata_1 | True | pk | False | market_id |

#### Source References

- `src/architecture_registry.py:434`
- `src/closing_line_engine.py:363,1151`
- `src/dashboard_schema_audit.py:13`
- `src/data_access.py:366,374,791`
- `src/inspect_master_inputs.py:18,154,225,297,373,398,399,471,515,516,536,537`
- `src/institutional_consensus_engine.py:748,2212`
- `src/market_identity_engine.py:467`
- `src/market_mapper_engine.py:23`
- `src/market_memory_engine.py:682,1056`
- `src/market_monitor_database.py:42,103,111,119,127,135,179,261,413,583`
- `src/market_status_engine.py:1184,1257`
- `src/master_opportunity_engine.py:894,2201`
- `src/opportunity_engine.py:446,1174`
- `src/position_evolution_engine.py:588,1920`
- `src/price_history_engine.py:548,551,557,1647`
- `src/sports_live_listener.py:262,407`

#### Create SQL

```sql
CREATE TABLE market_metadata (
            market_id TEXT PRIMARY KEY,

            gamma_market_id TEXT,
            condition_id TEXT,
            event_id TEXT,

            title TEXT NOT NULL,
            event_title TEXT,
            outcome TEXT,

            market_slug TEXT,
            event_slug TEXT,
            sports_slug TEXT,

            category TEXT,
            sport TEXT,
            league TEXT,

            start_time TEXT,
            game_start_time TEXT,
            end_time TEXT,

            lifecycle_status TEXT NOT NULL
                DEFAULT 'UNKNOWN',

            is_pregame INTEGER NOT NULL DEFAULT 0,
            is_live INTEGER NOT NULL DEFAULT 0,
            is_ended INTEGER NOT NULL DEFAULT 0,
            is_closed INTEGER NOT NULL DEFAULT 0,
            is_resolved INTEGER NOT NULL DEFAULT 0,

            score TEXT,
            period TEXT,
            elapsed TEXT,

            winning_outcome TEXT,
            resolution_status TEXT
                NOT NULL DEFAULT 'UNRESOLVED',

            active INTEGER NOT NULL DEFAULT 0,
            accepting_orders INTEGER NOT NULL DEFAULT 0,

            current_price REAL,
            outcome_prices_json TEXT,

            seconds_to_start INTEGER,
            seconds_since_start INTEGER,

            source_updated_at TEXT,
            first_seen_at TEXT NOT NULL,
            last_checked_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
```

### `market_opportunity_history`

- Row count: `5`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | opportunity_key | TEXT | True | — | 0 |
| 2 | condition_id | TEXT | True | — | 0 |
| 3 | rank_number | INTEGER | False | — | 0 |
| 4 | opportunity_score | REAL | False | — | 0 |
| 5 | opportunity_grade | TEXT | False | — | 0 |
| 6 | recommendation | TEXT | False | — | 0 |
| 7 | is_actionable | INTEGER | False | — | 0 |
| 8 | research_probability | REAL | False | — | 0 |
| 9 | prediction_confidence | REAL | False | — | 0 |
| 10 | current_net_flow | REAL | False | — | 0 |
| 11 | wallet_count | INTEGER | False | — | 0 |
| 12 | polymarket_url | TEXT | False | — | 0 |
| 13 | t_minus_target_at | TEXT | False | — | 0 |
| 14 | t_minus_seconds | INTEGER | False | — | 0 |
| 15 | t_minus_display | TEXT | False | — | 0 |
| 16 | time_status | TEXT | False | — | 0 |
| 17 | resolved | INTEGER | True | 0 | 0 |
| 18 | winning_outcome | TEXT | False | — | 0 |
| 19 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_opportunity_history_condition | False | c | False | condition_id, observed_at |

#### Source References

- `src/opportunity_ranking_engine.py:565,598,2820,3436`

#### Create SQL

```sql
CREATE TABLE market_opportunity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                opportunity_key TEXT NOT NULL,
                condition_id TEXT NOT NULL,

                rank_number INTEGER,
                opportunity_score REAL,
                opportunity_grade TEXT,
                recommendation TEXT,
                is_actionable INTEGER,

                research_probability REAL,
                prediction_confidence REAL,
                current_net_flow REAL,
                wallet_count INTEGER,

                polymarket_url TEXT,
                t_minus_target_at TEXT,
                t_minus_seconds INTEGER,
                t_minus_display TEXT,
                time_status TEXT,

                resolved INTEGER
                    NOT NULL DEFAULT 0,

                winning_outcome TEXT,

                observed_at TEXT NOT NULL
            )
```

### `market_opportunity_runs`

- Row count: `4`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | lookback_hours | INTEGER | True | — | 0 |
| 5 | predictions_loaded | INTEGER | True | 0 | 0 |
| 6 | exact_mappings | INTEGER | True | 0 | 0 |
| 7 | links_created | INTEGER | True | 0 | 0 |
| 8 | opportunities_saved | INTEGER | True | 0 | 0 |
| 9 | actionable_opportunities | INTEGER | True | 0 | 0 |
| 10 | open_opportunities | INTEGER | True | 0 | 0 |
| 11 | live_opportunities | INTEGER | True | 0 | 0 |
| 12 | closed_opportunities | INTEGER | True | 0 | 0 |
| 13 | missing_link_count | INTEGER | True | 0 | 0 |
| 14 | unknown_time_count | INTEGER | True | 0 | 0 |
| 15 | status | TEXT | True | — | 0 |
| 16 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/opportunity_ranking_engine.py:603,2934,2975,3441`

#### Create SQL

```sql
CREATE TABLE market_opportunity_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                lookback_hours INTEGER NOT NULL,

                predictions_loaded INTEGER
                    NOT NULL DEFAULT 0,

                exact_mappings INTEGER
                    NOT NULL DEFAULT 0,

                links_created INTEGER
                    NOT NULL DEFAULT 0,

                opportunities_saved INTEGER
                    NOT NULL DEFAULT 0,

                actionable_opportunities INTEGER
                    NOT NULL DEFAULT 0,

                open_opportunities INTEGER
                    NOT NULL DEFAULT 0,

                live_opportunities INTEGER
                    NOT NULL DEFAULT 0,

                closed_opportunities INTEGER
                    NOT NULL DEFAULT 0,

                missing_link_count INTEGER
                    NOT NULL DEFAULT 0,

                unknown_time_count INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `market_prediction_history`

- Row count: `38`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | prediction_key | TEXT | True | — | 0 |
| 2 | condition_id | TEXT | True | — | 0 |
| 3 | predicted_direction | TEXT | False | — | 0 |
| 4 | research_probability | REAL | False | — | 0 |
| 5 | probability_edge | REAL | False | — | 0 |
| 6 | confidence_score | REAL | False | — | 0 |
| 7 | confidence_grade | TEXT | False | — | 0 |
| 8 | prediction_grade | TEXT | False | — | 0 |
| 9 | recommended_action | TEXT | False | — | 0 |
| 10 | smart_money_flow_score | REAL | False | — | 0 |
| 11 | market_memory_score | REAL | False | — | 0 |
| 12 | resolved | INTEGER | False | — | 0 |
| 13 | winning_outcome | TEXT | False | — | 0 |
| 14 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_prediction_history_condition | False | c | False | condition_id, observed_at |

#### Source References

- `src/prediction_engine.py:336,361,1571,2074`

#### Create SQL

```sql
CREATE TABLE market_prediction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                prediction_key TEXT NOT NULL,
                condition_id TEXT NOT NULL,

                predicted_direction TEXT,
                research_probability REAL,
                probability_edge REAL,
                confidence_score REAL,
                confidence_grade TEXT,
                prediction_grade TEXT,
                recommended_action TEXT,

                smart_money_flow_score REAL,
                market_memory_score REAL,

                resolved INTEGER,
                winning_outcome TEXT,

                observed_at TEXT NOT NULL
            )
```

### `market_prediction_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | lookback_hours | INTEGER | True | — | 0 |
| 5 | flow_signals_loaded | INTEGER | True | 0 | 0 |
| 6 | predictions_saved | INTEGER | True | 0 | 0 |
| 7 | actionable_predictions | INTEGER | True | 0 | 0 |
| 8 | bullish_predictions | INTEGER | True | 0 | 0 |
| 9 | bearish_predictions | INTEGER | True | 0 | 0 |
| 10 | neutral_predictions | INTEGER | True | 0 | 0 |
| 11 | status | TEXT | True | — | 0 |
| 12 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/prediction_engine.py:366,1641,1680,2079`

#### Create SQL

```sql
CREATE TABLE market_prediction_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                lookback_hours INTEGER NOT NULL,

                flow_signals_loaded INTEGER
                    NOT NULL DEFAULT 0,

                predictions_saved INTEGER
                    NOT NULL DEFAULT 0,

                actionable_predictions INTEGER
                    NOT NULL DEFAULT 0,

                bullish_predictions INTEGER
                    NOT NULL DEFAULT 0,

                bearish_predictions INTEGER
                    NOT NULL DEFAULT 0,

                neutral_predictions INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `market_predictions`

- Row count: `38`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | prediction_key | TEXT | False | — | 1 |
| 1 | condition_id | TEXT | True | — | 0 |
| 2 | market_id | TEXT | False | — | 0 |
| 3 | event_id | TEXT | False | — | 0 |
| 4 | title | TEXT | False | — | 0 |
| 5 | slug | TEXT | False | — | 0 |
| 6 | event_slug | TEXT | False | — | 0 |
| 7 | category | TEXT | False | — | 0 |
| 8 | lookback_hours | INTEGER | True | — | 0 |
| 9 | source_signal_key | TEXT | False | — | 0 |
| 10 | source_snapshot_key | TEXT | False | — | 0 |
| 11 | predicted_direction | TEXT | True | 'NEUTRAL' | 0 |
| 12 | research_probability | REAL | True | 50 | 0 |
| 13 | probability_edge | REAL | True | 0 | 0 |
| 14 | confidence_score | REAL | True | 0 | 0 |
| 15 | confidence_grade | TEXT | True | 'LOW' | 0 |
| 16 | prediction_grade | TEXT | True | 'PASS' | 0 |
| 17 | recommended_action | TEXT | True | 'PASS' | 0 |
| 18 | smart_money_flow_score | REAL | True | 0 | 0 |
| 19 | market_memory_score | REAL | True | 0 | 0 |
| 20 | accumulation_score | REAL | True | 0 | 0 |
| 21 | distribution_score | REAL | True | 0 | 0 |
| 22 | consensus_strength | REAL | True | 0 | 0 |
| 23 | trusted_flow_score | REAL | True | 0 | 0 |
| 24 | persistence_score | REAL | True | 0 | 0 |
| 25 | breadth_score | REAL | True | 0 | 0 |
| 26 | velocity_score | REAL | True | 0 | 0 |
| 27 | acceleration_score | REAL | True | 0 | 0 |
| 28 | rotation_score | REAL | True | 0 | 0 |
| 29 | concentration_risk | REAL | True | 0 | 0 |
| 30 | whale_concentration | REAL | True | 0 | 0 |
| 31 | current_net_flow | REAL | True | 0 | 0 |
| 32 | current_gross_flow | REAL | True | 0 | 0 |
| 33 | current_wallet_count | INTEGER | True | 0 | 0 |
| 34 | elite_wallet_count | INTEGER | True | 0 | 0 |
| 35 | qualified_wallet_count | INTEGER | True | 0 | 0 |
| 36 | watchlist_wallet_count | INTEGER | True | 0 | 0 |
| 37 | current_price | REAL | False | — | 0 |
| 38 | average_trade_price | REAL | False | — | 0 |
| 39 | data_completeness_score | REAL | True | 0 | 0 |
| 40 | model_disagreement_score | REAL | True | 0 | 0 |
| 41 | is_actionable | INTEGER | True | 0 | 0 |
| 42 | resolved | INTEGER | True | 0 | 0 |
| 43 | winning_outcome | TEXT | False | — | 0 |
| 44 | positive_evidence_json | TEXT | False | — | 0 |
| 45 | risk_flags_json | TEXT | False | — | 0 |
| 46 | component_scores_json | TEXT | False | — | 0 |
| 47 | metadata_json | TEXT | False | — | 0 |
| 48 | predicted_at | TEXT | True | — | 0 |
| 49 | created_at | TEXT | True | — | 0 |
| 50 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_predictions_condition | False | c | False | condition_id, lookback_hours, predicted_at |
| idx_market_predictions_rank | False | c | False | is_actionable, confidence_score, research_probability, predicted_at |
| sqlite_autoindex_market_predictions_1 | True | pk | False | prediction_key |

#### Source References

- `src/condition_id_lineage_audit.py:30`
- `src/historical_market_reconciliation_engine.py:33`
- `src/market_identifier_registry_engine.py:1010`
- `src/market_identity_enrichment_engine.py:361,1824`
- `src/opportunity_ranking_engine.py:361,668,680`
- `src/prediction_engine.py:197,321,330,1549,2069`
- `src/registry_validation_gate.py:39`

#### Create SQL

```sql
CREATE TABLE market_predictions (
                prediction_key TEXT PRIMARY KEY,

                condition_id TEXT NOT NULL,
                market_id TEXT,
                event_id TEXT,

                title TEXT,
                slug TEXT,
                event_slug TEXT,
                category TEXT,

                lookback_hours INTEGER NOT NULL,

                source_signal_key TEXT,
                source_snapshot_key TEXT,

                predicted_direction TEXT
                    NOT NULL DEFAULT 'NEUTRAL',

                research_probability REAL
                    NOT NULL DEFAULT 50,

                probability_edge REAL
                    NOT NULL DEFAULT 0,

                confidence_score REAL
                    NOT NULL DEFAULT 0,

                confidence_grade TEXT
                    NOT NULL DEFAULT 'LOW',

                prediction_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                recommended_action TEXT
                    NOT NULL DEFAULT 'PASS',

                smart_money_flow_score REAL
                    NOT NULL DEFAULT 0,

                market_memory_score REAL
                    NOT NULL DEFAULT 0,

                accumulation_score REAL
                    NOT NULL DEFAULT 0,

                distribution_score REAL
                    NOT NULL DEFAULT 0,

                consensus_strength REAL
                    NOT NULL DEFAULT 0,

                trusted_flow_score REAL
                    NOT NULL DEFAULT 0,

                persistence_score REAL
                    NOT NULL DEFAULT 0,

                breadth_score REAL
                    NOT NULL DEFAULT 0,

                velocity_score REAL
                    NOT NULL DEFAULT 0,

                acceleration_score REAL
                    NOT NULL DEFAULT 0,

                rotation_score REAL
                    NOT NULL DEFAULT 0,

                concentration_risk REAL
                    NOT NULL DEFAULT 0,

                whale_concentration REAL
                    NOT NULL DEFAULT 0,

                current_net_flow REAL
                    NOT NULL DEFAULT 0,

                current_gross_flow REAL
                    NOT NULL DEFAULT 0,

                current_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                qualified_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                watchlist_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                current_price REAL,
                average_trade_price REAL,

                data_completeness_score REAL
                    NOT NULL DEFAULT 0,

                model_disagreement_score REAL
                    NOT NULL DEFAULT 0,

                is_actionable INTEGER
                    NOT NULL DEFAULT 0,

                resolved INTEGER
                    NOT NULL DEFAULT 0,

                winning_outcome TEXT,

                positive_evidence_json TEXT,
                risk_flags_json TEXT,
                component_scores_json TEXT,
                metadata_json TEXT,

                predicted_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `market_price_history`

- Row count: `86`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | market_id | TEXT | True | — | 0 |
| 2 | title | TEXT | True | — | 0 |
| 3 | outcome | TEXT | False | — | 0 |
| 4 | market_type | TEXT | False | — | 0 |
| 5 | category | TEXT | False | — | 0 |
| 6 | sport | TEXT | False | — | 0 |
| 7 | league | TEXT | False | — | 0 |
| 8 | current_price | REAL | True | — | 0 |
| 9 | lifecycle_status | TEXT | False | — | 0 |
| 10 | seconds_to_start | INTEGER | False | — | 0 |
| 11 | source_updated_at | TEXT | False | — | 0 |
| 12 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_price_history_observed | False | c | False | observed_at |
| idx_market_price_history_market_time | False | c | False | market_id, observed_at |
| sqlite_autoindex_market_price_history_1 | True | u | False | market_id, observed_at |

#### Source References

- `src/closing_line_engine.py:391,398,1152`
- `src/decision_price_attribution_engine.py:10,54,637,649,674,677`
- `src/decision_price_attribution_engine_v10_backup.py:10,54,637,649,674,677`
- `src/decision_price_attribution_engine_v11_backup.py:10,54,637,649,674,677`
- `src/price_history_engine.py:260,290,301,682,763,1147,1519,1648,1983`

#### Create SQL

```sql
CREATE TABLE market_price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT,
                market_type TEXT,
                category TEXT,
                sport TEXT,
                league TEXT,

                current_price REAL NOT NULL,
                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                source_updated_at TEXT,
                observed_at TEXT NOT NULL,

                UNIQUE(
                    market_id,
                    observed_at
                )
            )
```

### `market_price_metrics`

- Row count: `86`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | market_id | TEXT | False | — | 1 |
| 1 | title | TEXT | True | — | 0 |
| 2 | outcome | TEXT | False | — | 0 |
| 3 | current_price | REAL | True | — | 0 |
| 4 | price_5m_ago | REAL | False | — | 0 |
| 5 | price_15m_ago | REAL | False | — | 0 |
| 6 | price_1h_ago | REAL | False | — | 0 |
| 7 | price_6h_ago | REAL | False | — | 0 |
| 8 | price_24h_ago | REAL | False | — | 0 |
| 9 | move_5m | REAL | False | — | 0 |
| 10 | move_15m | REAL | False | — | 0 |
| 11 | move_1h | REAL | False | — | 0 |
| 12 | move_6h | REAL | False | — | 0 |
| 13 | move_24h | REAL | False | — | 0 |
| 14 | move_5m_pct | REAL | False | — | 0 |
| 15 | move_15m_pct | REAL | False | — | 0 |
| 16 | move_1h_pct | REAL | False | — | 0 |
| 17 | move_6h_pct | REAL | False | — | 0 |
| 18 | move_24h_pct | REAL | False | — | 0 |
| 19 | high_24h | REAL | False | — | 0 |
| 20 | low_24h | REAL | False | — | 0 |
| 21 | range_24h | REAL | False | — | 0 |
| 22 | snapshot_count_24h | INTEGER | True | 0 | 0 |
| 23 | steam_score | REAL | True | 0 | 0 |
| 24 | reversal_score | REAL | True | 0 | 0 |
| 25 | volatility_score | REAL | True | 0 | 0 |
| 26 | move_status | TEXT | True | 'INSUFFICIENT_DATA' | 0 |
| 27 | lifecycle_status | TEXT | False | — | 0 |
| 28 | seconds_to_start | INTEGER | False | — | 0 |
| 29 | latest_observed_at | TEXT | False | — | 0 |
| 30 | calculated_at | TEXT | True | — | 0 |
| 31 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_price_metrics_status | False | c | False | move_status, steam_score |
| idx_market_price_metrics_steam | False | c | False | steam_score |
| sqlite_autoindex_market_price_metrics_1 | True | pk | False | market_id |

#### Source References

- `src/closing_line_engine.py:376,378,1153`
- `src/dashboard_schema_audit.py:14`
- `src/data_access.py:386,394,792`
- `src/inspect_master_inputs.py:17,153,221,296,364,394,395,470,511,512,513,532,533`
- `src/master_opportunity_engine.py:890,2200`
- `src/price_history_engine.py:309,367,377,1314,1649,1988`
- `src/signal_fusion_engine.py:1570`

#### Create SQL

```sql
CREATE TABLE market_price_metrics (
                market_id TEXT PRIMARY KEY,

                title TEXT NOT NULL,
                outcome TEXT,
                current_price REAL NOT NULL,

                price_5m_ago REAL,
                price_15m_ago REAL,
                price_1h_ago REAL,
                price_6h_ago REAL,
                price_24h_ago REAL,

                move_5m REAL,
                move_15m REAL,
                move_1h REAL,
                move_6h REAL,
                move_24h REAL,

                move_5m_pct REAL,
                move_15m_pct REAL,
                move_1h_pct REAL,
                move_6h_pct REAL,
                move_24h_pct REAL,

                high_24h REAL,
                low_24h REAL,
                range_24h REAL,

                snapshot_count_24h INTEGER
                    NOT NULL DEFAULT 0,

                steam_score REAL
                    NOT NULL DEFAULT 0,

                reversal_score REAL
                    NOT NULL DEFAULT 0,

                volatility_score REAL
                    NOT NULL DEFAULT 0,

                move_status TEXT
                    NOT NULL DEFAULT 'INSUFFICIENT_DATA',

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                latest_observed_at TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `market_resolution_outcomes`

- Row count: `41206`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | resolution_outcome_key | TEXT | False | — | 1 |
| 1 | resolution_key | TEXT | True | — | 0 |
| 2 | gamma_market_id | TEXT | True | — | 0 |
| 3 | condition_id | TEXT | False | — | 0 |
| 4 | outcome_index | INTEGER | True | — | 0 |
| 5 | outcome_name | TEXT | True | — | 0 |
| 6 | token_id | TEXT | False | — | 0 |
| 7 | implied_price | REAL | False | — | 0 |
| 8 | winner | INTEGER | True | 0 | 0 |
| 9 | settlement_price | REAL | False | — | 0 |
| 10 | resolution_status | TEXT | True | 'UNRESOLVED' | 0 |
| 11 | first_seen_at | TEXT | True | — | 0 |
| 12 | last_checked_at | TEXT | True | — | 0 |
| 13 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| resolution_key | market_resolutions | resolution_key | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_resolution_outcomes_token | False | c | False | token_id |
| idx_market_resolution_outcomes_market | False | c | False | gamma_market_id, outcome_index |
| sqlite_autoindex_market_resolution_outcomes_1 | True | pk | False | resolution_outcome_key |

#### Source References

- `src/institutional_learning_engine.py:13,286,602`
- `src/institutional_learning_engine_v10_scoring_backup.py:13,286,602`
- `src/market_resolution_engine.py:232,271,278,1228,1294,1726`

#### Create SQL

```sql
CREATE TABLE market_resolution_outcomes (
                resolution_outcome_key TEXT PRIMARY KEY,

                resolution_key TEXT NOT NULL,

                gamma_market_id TEXT NOT NULL,
                condition_id TEXT,

                outcome_index INTEGER
                    NOT NULL,

                outcome_name TEXT NOT NULL,
                token_id TEXT,

                implied_price REAL,

                winner INTEGER
                    NOT NULL DEFAULT 0,

                settlement_price REAL,

                resolution_status TEXT
                    NOT NULL DEFAULT 'UNRESOLVED',

                first_seen_at TEXT NOT NULL,
                last_checked_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(
                    resolution_key
                )
                REFERENCES market_resolutions(
                    resolution_key
                )
                ON DELETE CASCADE
            )
```

### `market_resolution_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | registry_markets_checked | INTEGER | True | 0 | 0 |
| 5 | resolved_markets_found | INTEGER | True | 0 | 0 |
| 6 | ambiguous_markets | INTEGER | True | 0 | 0 |
| 7 | unresolved_markets | INTEGER | True | 0 | 0 |
| 8 | resolution_rows_saved | INTEGER | True | 0 | 0 |
| 9 | outcome_rows_saved | INTEGER | True | 0 | 0 |
| 10 | mapped_results_saved | INTEGER | True | 0 | 0 |
| 11 | status | TEXT | True | — | 0 |
| 12 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/market_resolution_engine.py:330,1358,1400`

#### Create SQL

```sql
CREATE TABLE market_resolution_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                registry_markets_checked INTEGER
                    NOT NULL DEFAULT 0,

                resolved_markets_found INTEGER
                    NOT NULL DEFAULT 0,

                ambiguous_markets INTEGER
                    NOT NULL DEFAULT 0,

                unresolved_markets INTEGER
                    NOT NULL DEFAULT 0,

                resolution_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                outcome_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                mapped_results_saved INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `market_resolutions`

- Row count: `20603`
- Referenced by: `market_resolution_outcomes`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | resolution_key | TEXT | False | — | 1 |
| 1 | gamma_market_id | TEXT | True | — | 0 |
| 2 | gamma_event_id | TEXT | False | — | 0 |
| 3 | condition_id | TEXT | False | — | 0 |
| 4 | question | TEXT | True | — | 0 |
| 5 | slug | TEXT | False | — | 0 |
| 6 | resolved | INTEGER | True | 0 | 0 |
| 7 | resolution_status | TEXT | True | 'UNRESOLVED' | 0 |
| 8 | winning_outcome_index | INTEGER | False | — | 0 |
| 9 | winning_outcome_name | TEXT | False | — | 0 |
| 10 | winning_token_id | TEXT | False | — | 0 |
| 11 | settlement_price | REAL | False | — | 0 |
| 12 | outcome_count | INTEGER | True | 0 | 0 |
| 13 | resolved_outcome_count | INTEGER | True | 0 | 0 |
| 14 | closed | INTEGER | True | 0 | 0 |
| 15 | active | INTEGER | True | 0 | 0 |
| 16 | end_time | TEXT | False | — | 0 |
| 17 | updated_at_gamma | TEXT | False | — | 0 |
| 18 | resolution_source | TEXT | False | — | 0 |
| 19 | resolved_by | TEXT | False | — | 0 |
| 20 | confidence_score | REAL | True | 0 | 0 |
| 21 | source_payload_json | TEXT | False | — | 0 |
| 22 | explanation_json | TEXT | False | — | 0 |
| 23 | first_seen_at | TEXT | True | — | 0 |
| 24 | last_checked_at | TEXT | True | — | 0 |
| 25 | resolved_at_detected | TEXT | False | — | 0 |
| 26 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_resolutions_condition | False | c | False | condition_id |
| idx_market_resolutions_status | False | c | False | resolution_status, resolved, last_checked_at |
| sqlite_autoindex_market_resolutions_1 | True | pk | False | resolution_key |

#### Source References

- `src/institutional_resolution_intelligence_engine.py:150,621,680,950,977`
- `src/institutional_resolution_intelligence_engine_backup_20260719_061600.py:150,621,680,950,977`
- `src/institutional_resolution_intelligence_engine_v1_backup.py:150,625,684,956,983`
- `src/institutional_settlement_intelligence_engine.py:205,681,740,1010,1037`
- `src/institutional_settlement_intelligence_engine_backup_20260719_062517.py:205,676,735,1005,1032`
- `src/market_resolution_engine.py:166,220,228,263,1222,1250,1721`

#### Create SQL

```sql
CREATE TABLE market_resolutions (
                resolution_key TEXT PRIMARY KEY,

                gamma_market_id TEXT NOT NULL,
                gamma_event_id TEXT,
                condition_id TEXT,

                question TEXT NOT NULL,
                slug TEXT,

                resolved INTEGER
                    NOT NULL DEFAULT 0,

                resolution_status TEXT
                    NOT NULL DEFAULT 'UNRESOLVED',

                winning_outcome_index INTEGER,
                winning_outcome_name TEXT,
                winning_token_id TEXT,

                settlement_price REAL,

                outcome_count INTEGER
                    NOT NULL DEFAULT 0,

                resolved_outcome_count INTEGER
                    NOT NULL DEFAULT 0,

                closed INTEGER
                    NOT NULL DEFAULT 0,

                active INTEGER
                    NOT NULL DEFAULT 0,

                end_time TEXT,
                updated_at_gamma TEXT,

                resolution_source TEXT,
                resolved_by TEXT,

                confidence_score REAL
                    NOT NULL DEFAULT 0,

                source_payload_json TEXT,
                explanation_json TEXT,

                first_seen_at TEXT NOT NULL,
                last_checked_at TEXT NOT NULL,
                resolved_at_detected TEXT,
                updated_at TEXT NOT NULL
            )
```

### `market_status_history`

- Row count: `141`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | market_id | TEXT | True | — | 0 |
| 2 | lifecycle_status | TEXT | True | — | 0 |
| 3 | is_pregame | INTEGER | True | 0 | 0 |
| 4 | is_live | INTEGER | True | 0 | 0 |
| 5 | is_ended | INTEGER | True | 0 | 0 |
| 6 | is_closed | INTEGER | True | 0 | 0 |
| 7 | is_resolved | INTEGER | True | 0 | 0 |
| 8 | start_time | TEXT | False | — | 0 |
| 9 | game_start_time | TEXT | False | — | 0 |
| 10 | score | TEXT | False | — | 0 |
| 11 | period | TEXT | False | — | 0 |
| 12 | elapsed | TEXT | False | — | 0 |
| 13 | winning_outcome | TEXT | False | — | 0 |
| 14 | resolution_status | TEXT | False | — | 0 |
| 15 | seconds_to_start | INTEGER | False | — | 0 |
| 16 | current_price | REAL | False | — | 0 |
| 17 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| market_id | market_metadata | market_id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_market_status_history_status | False | c | False | lifecycle_status, observed_at |
| idx_market_status_history_market | False | c | False | market_id, observed_at |

#### Source References

- `src/market_monitor_database.py:150,189,200,584`
- `src/market_status_engine.py:1377`
- `src/sports_live_listener.py:496`

#### Create SQL

```sql
CREATE TABLE market_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            market_id TEXT NOT NULL,

            lifecycle_status TEXT NOT NULL,

            is_pregame INTEGER NOT NULL DEFAULT 0,
            is_live INTEGER NOT NULL DEFAULT 0,
            is_ended INTEGER NOT NULL DEFAULT 0,
            is_closed INTEGER NOT NULL DEFAULT 0,
            is_resolved INTEGER NOT NULL DEFAULT 0,

            start_time TEXT,
            game_start_time TEXT,

            score TEXT,
            period TEXT,
            elapsed TEXT,

            winning_outcome TEXT,
            resolution_status TEXT,

            seconds_to_start INTEGER,
            current_price REAL,

            observed_at TEXT NOT NULL,

            FOREIGN KEY (market_id)
                REFERENCES market_metadata(market_id)
                ON DELETE CASCADE
        )
```

### `master_alerts`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | opportunity_key | TEXT | True | — | 0 |
| 2 | market_id | TEXT | True | — | 0 |
| 3 | title | TEXT | True | — | 0 |
| 4 | outcome | TEXT | True | — | 0 |
| 5 | alert_type | TEXT | True | — | 0 |
| 6 | severity | TEXT | True | — | 0 |
| 7 | master_score | REAL | False | — | 0 |
| 8 | master_grade | TEXT | False | — | 0 |
| 9 | recommendation | TEXT | False | — | 0 |
| 10 | lifecycle_status | TEXT | False | — | 0 |
| 11 | seconds_to_start | INTEGER | False | — | 0 |
| 12 | message | TEXT | True | — | 0 |
| 13 | details_json | TEXT | False | — | 0 |
| 14 | created_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_master_alerts_created | False | c | False | created_at |
| sqlite_autoindex_master_alerts_1 | True | u | False | opportunity_key, alert_type, created_at |

#### Source References

- `src/dashboard_schema_audit.py:26`
- `src/data_access.py:712,729,799`
- `src/master_opportunity_engine.py:464,496,2045,2204,2586`

#### Create SQL

```sql
CREATE TABLE master_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                opportunity_key TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,

                master_score REAL,
                master_grade TEXT,
                recommendation TEXT,

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                message TEXT NOT NULL,
                details_json TEXT,

                created_at TEXT NOT NULL,

                UNIQUE(
                    opportunity_key,
                    alert_type,
                    created_at
                )
            )
```

### `master_intelligence_dashboard`

- Row count: `40`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | condition_id | TEXT | True | — | 0 |
| 2 | outcome | TEXT | True | 'UNKNOWN' | 0 |
| 3 | gamma_market_id | TEXT | False | — | 0 |
| 4 | event_id | TEXT | False | — | 0 |
| 5 | question | TEXT | False | — | 0 |
| 6 | market_slug | TEXT | False | — | 0 |
| 7 | event_slug | TEXT | False | — | 0 |
| 8 | polymarket_url | TEXT | False | — | 0 |
| 9 | category | TEXT | False | — | 0 |
| 10 | market_type | TEXT | False | — | 0 |
| 11 | lifecycle_status | TEXT | False | — | 0 |
| 12 | active | INTEGER | True | 0 | 0 |
| 13 | closed | INTEGER | True | 0 | 0 |
| 14 | archived | INTEGER | True | 0 | 0 |
| 15 | resolved | INTEGER | True | 0 | 0 |
| 16 | tradable_identity | INTEGER | True | 0 | 0 |
| 17 | restricted | INTEGER | True | 0 | 0 |
| 18 | start_time | TEXT | False | — | 0 |
| 19 | end_time | TEXT | False | — | 0 |
| 20 | seconds_to_start | REAL | False | — | 0 |
| 21 | current_price | REAL | False | — | 0 |
| 22 | yes_price | REAL | False | — | 0 |
| 23 | no_price | REAL | False | — | 0 |
| 24 | best_bid | REAL | False | — | 0 |
| 25 | best_ask | REAL | False | — | 0 |
| 26 | spread | REAL | False | — | 0 |
| 27 | liquidity | REAL | False | — | 0 |
| 28 | volume | REAL | False | — | 0 |
| 29 | volume_24h | REAL | False | — | 0 |
| 30 | open_interest | REAL | False | — | 0 |
| 31 | wallet_count | INTEGER | False | — | 0 |
| 32 | effective_wallet_count | REAL | False | — | 0 |
| 33 | combined_value | REAL | False | — | 0 |
| 34 | combined_shares | REAL | False | — | 0 |
| 35 | consensus_strength | REAL | False | — | 0 |
| 36 | conviction_score | REAL | False | — | 0 |
| 37 | average_entry_price | REAL | False | — | 0 |
| 38 | accumulation_score | REAL | False | — | 0 |
| 39 | distribution_score | REAL | False | — | 0 |
| 40 | position_trend | TEXT | False | — | 0 |
| 41 | price_move_5m | REAL | False | — | 0 |
| 42 | price_move_15m | REAL | False | — | 0 |
| 43 | price_move_1h | REAL | False | — | 0 |
| 44 | steam_score | REAL | False | — | 0 |
| 45 | reversal_score | REAL | False | — | 0 |
| 46 | volatility_score | REAL | False | — | 0 |
| 47 | closing_line_value | REAL | False | — | 0 |
| 48 | closing_line_score | REAL | False | — | 0 |
| 49 | master_score | REAL | False | — | 0 |
| 50 | opportunity_grade | TEXT | False | — | 0 |
| 51 | opportunity_recommendation | TEXT | False | — | 0 |
| 52 | opportunity_confidence | REAL | False | — | 0 |
| 53 | edge_score | REAL | False | — | 0 |
| 54 | data_completeness_score | REAL | False | — | 0 |
| 55 | alert_count | INTEGER | True | 0 | 0 |
| 56 | has_active_alert | INTEGER | True | 0 | 0 |
| 57 | latest_alert_type | TEXT | False | — | 0 |
| 58 | latest_alert_created_at | TEXT | False | — | 0 |
| 59 | intelligence_score | REAL | False | — | 0 |
| 60 | intelligence_grade | TEXT | False | — | 0 |
| 61 | confidence_score | REAL | False | — | 0 |
| 62 | risk_score | REAL | False | — | 0 |
| 63 | final_recommendation | TEXT | False | — | 0 |
| 64 | risk_flags_json | TEXT | True | '[]' | 0 |
| 65 | canonical_json | TEXT | True | '{}' | 0 |
| 66 | status_json | TEXT | True | '{}' | 0 |
| 67 | price_metrics_json | TEXT | True | '{}' | 0 |
| 68 | consensus_json | TEXT | True | '[]' | 0 |
| 69 | evolution_json | TEXT | True | '[]' | 0 |
| 70 | closing_line_json | TEXT | True | '[]' | 0 |
| 71 | opportunity_json | TEXT | True | '{}' | 0 |
| 72 | alerts_json | TEXT | True | '[]' | 0 |
| 73 | positions_json | TEXT | True | '[]' | 0 |
| 74 | source_snapshot_json | TEXT | True | '{}' | 0 |
| 75 | source_updated_at | TEXT | False | — | 0 |
| 76 | built_at | TEXT | True | — | 0 |
| 77 | run_id | TEXT | False | — | 0 |
| 78 | schema_version | INTEGER | True | 1 | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_dashboard_lifecycle | False | c | False | lifecycle_status |
| idx_dashboard_category | False | c | False | category |
| idx_dashboard_intelligence_score | False | c | False | intelligence_score |
| idx_dashboard_master_score | False | c | False | master_score |
| idx_dashboard_identity | True | c | False | condition_id, outcome |
| sqlite_autoindex_master_intelligence_dashboard_1 | True | u | False | condition_id, outcome |

#### Source References

- `src/dashboard_repository.py:17`

#### Create SQL

```sql
CREATE TABLE master_intelligence_dashboard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_id TEXT NOT NULL,
                outcome TEXT NOT NULL DEFAULT 'UNKNOWN',
                gamma_market_id TEXT,
                event_id TEXT,
                question TEXT,
                market_slug TEXT,
                event_slug TEXT,
                polymarket_url TEXT,
                category TEXT,
                market_type TEXT,
                lifecycle_status TEXT,
                active INTEGER NOT NULL DEFAULT 0,
                closed INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                resolved INTEGER NOT NULL DEFAULT 0,
                tradable_identity INTEGER NOT NULL DEFAULT 0,
                restricted INTEGER NOT NULL DEFAULT 0,
                start_time TEXT,
                end_time TEXT,
                seconds_to_start REAL,
                current_price REAL,
                yes_price REAL,
                no_price REAL,
                best_bid REAL,
                best_ask REAL,
                spread REAL,
                liquidity REAL,
                volume REAL,
                volume_24h REAL,
                open_interest REAL,
                wallet_count INTEGER,
                effective_wallet_count REAL,
                combined_value REAL,
                combined_shares REAL,
                consensus_strength REAL,
                conviction_score REAL,
                average_entry_price REAL,
                accumulation_score REAL,
                distribution_score REAL,
                position_trend TEXT,
                price_move_5m REAL,
                price_move_15m REAL,
                price_move_1h REAL,
                steam_score REAL,
                reversal_score REAL,
                volatility_score REAL,
                closing_line_value REAL,
                closing_line_score REAL,
                master_score REAL,
                opportunity_grade TEXT,
                opportunity_recommendation TEXT,
                opportunity_confidence REAL,
                edge_score REAL,
                data_completeness_score REAL,
                alert_count INTEGER NOT NULL DEFAULT 0,
                has_active_alert INTEGER NOT NULL DEFAULT 0,
                latest_alert_type TEXT,
                latest_alert_created_at TEXT,
                intelligence_score REAL,
                intelligence_grade TEXT,
                confidence_score REAL,
                risk_score REAL,
                final_recommendation TEXT,
                risk_flags_json TEXT NOT NULL DEFAULT '[]',
                canonical_json TEXT NOT NULL DEFAULT '{}',
                status_json TEXT NOT NULL DEFAULT '{}',
                price_metrics_json TEXT NOT NULL DEFAULT '{}',
                consensus_json TEXT NOT NULL DEFAULT '[]',
                evolution_json TEXT NOT NULL DEFAULT '[]',
                closing_line_json TEXT NOT NULL DEFAULT '[]',
                opportunity_json TEXT NOT NULL DEFAULT '{}',
                alerts_json TEXT NOT NULL DEFAULT '[]',
                positions_json TEXT NOT NULL DEFAULT '[]',
                source_snapshot_json TEXT NOT NULL DEFAULT '{}',
                source_updated_at TEXT,
                built_at TEXT NOT NULL,
                run_id TEXT,
                schema_version INTEGER NOT NULL DEFAULT 1,
                UNIQUE(condition_id, outcome)
            )
```

### `master_intelligence_dashboard_history`

- Row count: `122`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | condition_id | TEXT | True | — | 0 |
| 2 | outcome | TEXT | True | 'UNKNOWN' | 0 |
| 3 | run_id | TEXT | False | — | 0 |
| 4 | question | TEXT | False | — | 0 |
| 5 | lifecycle_status | TEXT | False | — | 0 |
| 6 | current_price | REAL | False | — | 0 |
| 7 | liquidity | REAL | False | — | 0 |
| 8 | volume_24h | REAL | False | — | 0 |
| 9 | spread | REAL | False | — | 0 |
| 10 | wallet_count | INTEGER | False | — | 0 |
| 11 | consensus_strength | REAL | False | — | 0 |
| 12 | conviction_score | REAL | False | — | 0 |
| 13 | master_score | REAL | False | — | 0 |
| 14 | intelligence_score | REAL | False | — | 0 |
| 15 | intelligence_grade | TEXT | False | — | 0 |
| 16 | confidence_score | REAL | False | — | 0 |
| 17 | risk_score | REAL | False | — | 0 |
| 18 | final_recommendation | TEXT | False | — | 0 |
| 19 | alert_count | INTEGER | True | 0 | 0 |
| 20 | snapshot_json | TEXT | True | — | 0 |
| 21 | captured_at | TEXT | True | — | 0 |
| 22 | schema_version | INTEGER | True | 1 | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_dashboard_history_market | False | c | False | condition_id, outcome, captured_at |

#### Source References

- `src/dashboard_repository.py:18`

#### Create SQL

```sql
CREATE TABLE master_intelligence_dashboard_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_id TEXT NOT NULL,
                outcome TEXT NOT NULL DEFAULT 'UNKNOWN',
                run_id TEXT,
                question TEXT,
                lifecycle_status TEXT,
                current_price REAL,
                liquidity REAL,
                volume_24h REAL,
                spread REAL,
                wallet_count INTEGER,
                consensus_strength REAL,
                conviction_score REAL,
                master_score REAL,
                intelligence_score REAL,
                intelligence_grade TEXT,
                confidence_score REAL,
                risk_score REAL,
                final_recommendation TEXT,
                alert_count INTEGER NOT NULL DEFAULT 0,
                snapshot_json TEXT NOT NULL,
                captured_at TEXT NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 1
            )
```

### `master_intelligence_dashboard_runs`

- Row count: `4`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | mode | TEXT | True | 'focused' | 0 |
| 3 | started_at | TEXT | True | — | 0 |
| 4 | finished_at | TEXT | False | — | 0 |
| 5 | duration_seconds | REAL | False | — | 0 |
| 6 | source_markets | INTEGER | True | 0 | 0 |
| 7 | processed_rows | INTEGER | True | 0 | 0 |
| 8 | inserted_rows | INTEGER | True | 0 | 0 |
| 9 | updated_rows | INTEGER | True | 0 | 0 |
| 10 | history_rows | INTEGER | True | 0 | 0 |
| 11 | skipped_rows | INTEGER | True | 0 | 0 |
| 12 | unmatched_rows | INTEGER | True | 0 | 0 |
| 13 | error_count | INTEGER | True | 0 | 0 |
| 14 | success | INTEGER | False | — | 0 |
| 15 | status | TEXT | True | 'RUNNING' | 0 |
| 16 | error_message | TEXT | False | — | 0 |
| 17 | details_json | TEXT | True | '{}' | 0 |
| 18 | schema_version | INTEGER | True | 1 | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_dashboard_runs_started | False | c | False | started_at |
| sqlite_autoindex_master_intelligence_dashboard_runs_1 | True | u | False | run_id |

#### Source References

- `src/dashboard_repository.py:19`

#### Create SQL

```sql
CREATE TABLE master_intelligence_dashboard_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                mode TEXT NOT NULL DEFAULT 'focused',
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL,
                source_markets INTEGER NOT NULL DEFAULT 0,
                processed_rows INTEGER NOT NULL DEFAULT 0,
                inserted_rows INTEGER NOT NULL DEFAULT 0,
                updated_rows INTEGER NOT NULL DEFAULT 0,
                history_rows INTEGER NOT NULL DEFAULT 0,
                skipped_rows INTEGER NOT NULL DEFAULT 0,
                unmatched_rows INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                success INTEGER,
                status TEXT NOT NULL DEFAULT 'RUNNING',
                error_message TEXT,
                details_json TEXT NOT NULL DEFAULT '{}',
                schema_version INTEGER NOT NULL DEFAULT 1
            )
```

### `master_opportunities`

- Row count: `131`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | opportunity_key | TEXT | False | — | 1 |
| 1 | market_id | TEXT | True | — | 0 |
| 2 | title | TEXT | True | — | 0 |
| 3 | outcome | TEXT | True | — | 0 |
| 4 | market_type | TEXT | False | — | 0 |
| 5 | master_score | REAL | True | 0 | 0 |
| 6 | master_grade | TEXT | True | 'PASS' | 0 |
| 7 | master_tier | TEXT | True | 'PASS' | 0 |
| 8 | recommendation | TEXT | True | 'PASS' | 0 |
| 9 | lifecycle_status | TEXT | False | — | 0 |
| 10 | seconds_to_start | INTEGER | False | — | 0 |
| 11 | opportunity_score | REAL | True | 0 | 0 |
| 12 | institutional_score | REAL | True | 0 | 0 |
| 13 | evolution_score | REAL | True | 0 | 0 |
| 14 | closing_line_score | REAL | True | 0 | 0 |
| 15 | price_action_score | REAL | True | 0 | 0 |
| 16 | wallet_quality_score | REAL | True | 0 | 0 |
| 17 | timing_score | REAL | True | 0 | 0 |
| 18 | opportunity_grade | TEXT | False | — | 0 |
| 19 | institutional_grade | TEXT | False | — | 0 |
| 20 | evolution_grade | TEXT | False | — | 0 |
| 21 | institutional_status | TEXT | False | — | 0 |
| 22 | evolution_status | TEXT | False | — | 0 |
| 23 | closing_recommendation | TEXT | False | — | 0 |
| 24 | movement_status | TEXT | False | — | 0 |
| 25 | wallet_count | INTEGER | True | 0 | 0 |
| 26 | elite_wallet_count | INTEGER | True | 0 | 0 |
| 27 | effective_wallet_count | REAL | True | 0 | 0 |
| 28 | combined_current_value | REAL | True | 0 | 0 |
| 29 | weighted_wallet_quality | REAL | True | 0 | 0 |
| 30 | consensus_strength | REAL | True | 0 | 0 |
| 31 | strengthening_score | REAL | True | 0 | 0 |
| 32 | weakening_score | REAL | True | 0 | 0 |
| 33 | net_value_change | REAL | True | 0 | 0 |
| 34 | elite_wallet_count_change | INTEGER | True | 0 | 0 |
| 35 | clv_score | REAL | False | — | 0 |
| 36 | edge_remaining_score | REAL | False | — | 0 |
| 37 | chase_risk_score | REAL | False | — | 0 |
| 38 | steam_score | REAL | False | — | 0 |
| 39 | reversal_score | REAL | False | — | 0 |
| 40 | volatility_score | REAL | False | — | 0 |
| 41 | conflict_ratio | REAL | True | 0 | 0 |
| 42 | portfolio_independence_score | REAL | True | 0 | 0 |
| 43 | remaining_upside | REAL | True | 0 | 0 |
| 44 | is_market_leader | INTEGER | True | 0 | 0 |
| 45 | data_completeness_score | REAL | True | 0 | 0 |
| 46 | data_confidence | TEXT | True | 'LOW' | 0 |
| 47 | source_coverage_score | REAL | True | 0 | 0 |
| 48 | source_count | INTEGER | True | 0 | 0 |
| 49 | live_penalty | REAL | True | 0 | 0 |
| 50 | inactive_penalty | REAL | True | 0 | 0 |
| 51 | single_wallet_penalty | REAL | True | 0 | 0 |
| 52 | weak_consensus_penalty | REAL | True | 0 | 0 |
| 53 | chase_penalty | REAL | True | 0 | 0 |
| 54 | conflict_penalty | REAL | True | 0 | 0 |
| 55 | reversal_penalty | REAL | True | 0 | 0 |
| 56 | low_upside_penalty | REAL | True | 0 | 0 |
| 57 | weakening_penalty | REAL | True | 0 | 0 |
| 58 | incomplete_data_penalty | REAL | True | 0 | 0 |
| 59 | total_penalty | REAL | True | 0 | 0 |
| 60 | reasons_json | TEXT | False | — | 0 |
| 61 | risk_flags_json | TEXT | False | — | 0 |
| 62 | explanation_json | TEXT | False | — | 0 |
| 63 | calculated_at | TEXT | True | — | 0 |
| 64 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_master_opportunities_recommendation | False | c | False | recommendation, master_score |
| idx_master_opportunities_grade | False | c | False | master_grade, master_score |
| idx_master_opportunities_rank | False | c | False | master_score |
| sqlite_autoindex_master_opportunities_1 | True | pk | False | opportunity_key |

#### Source References

- `src/canonical_coverage_audit.py:22,859`
- `src/canonical_identity_synchronizer.py:22`
- `src/condition_id_lineage_audit.py:34,865,868`
- `src/dashboard_schema_audit.py:24`
- `src/data_access.py:413,453,469,483,798`
- `src/historical_market_reconciliation_engine.py:35`
- `src/institutional_decision_engine.py:38`
- `src/institutional_decision_engine_v2.py:53`
- `src/institutional_decision_engine_v2_baseline.py:53`
- `src/institutional_decision_engine_v2_v20_backup.py:53`
- `src/institutional_decision_engine_v2_v21_backup.py:53`
- `src/institutional_decision_intelligence_dashboard.py:225,698`
- `src/master_intelligence_dashboard_builder.py:634`
- `src/master_opportunity_engine.py:225,383,389,396,1881,1890,1910,2202,2576`
- `src/prediction_engine.py:520`
- `src/registry_validation_gate.py:41`
- `src/signal_fusion_engine.py:1544,1550`

#### Create SQL

```sql
CREATE TABLE master_opportunities (
                opportunity_key TEXT PRIMARY KEY,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,
                market_type TEXT,

                master_score REAL
                    NOT NULL DEFAULT 0,

                master_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                master_tier TEXT
                    NOT NULL DEFAULT 'PASS',

                recommendation TEXT
                    NOT NULL DEFAULT 'PASS',

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                opportunity_score REAL
                    NOT NULL DEFAULT 0,

                institutional_score REAL
                    NOT NULL DEFAULT 0,

                evolution_score REAL
                    NOT NULL DEFAULT 0,

                closing_line_score REAL
                    NOT NULL DEFAULT 0,

                price_action_score REAL
                    NOT NULL DEFAULT 0,

                wallet_quality_score REAL
                    NOT NULL DEFAULT 0,

                timing_score REAL
                    NOT NULL DEFAULT 0,

                opportunity_grade TEXT,
                institutional_grade TEXT,
                evolution_grade TEXT,

                institutional_status TEXT,
                evolution_status TEXT,
                closing_recommendation TEXT,
                movement_status TEXT,

                wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                effective_wallet_count REAL
                    NOT NULL DEFAULT 0,

                combined_current_value REAL
                    NOT NULL DEFAULT 0,

                weighted_wallet_quality REAL
                    NOT NULL DEFAULT 0,

                consensus_strength REAL
                    NOT NULL DEFAULT 0,

                strengthening_score REAL
                    NOT NULL DEFAULT 0,

                weakening_score REAL
                    NOT NULL DEFAULT 0,

                net_value_change REAL
                    NOT NULL DEFAULT 0,

                elite_wallet_count_change INTEGER
                    NOT NULL DEFAULT 0,

                clv_score REAL,
                edge_remaining_score REAL,
                chase_risk_score REAL,

                steam_score REAL,
                reversal_score REAL,
                volatility_score REAL,

                conflict_ratio REAL
                    NOT NULL DEFAULT 0,

                portfolio_independence_score REAL
                    NOT NULL DEFAULT 0,

                remaining_upside REAL
                    NOT NULL DEFAULT 0,

                is_market_leader INTEGER
                    NOT NULL DEFAULT 0,

                data_completeness_score REAL
                    NOT NULL DEFAULT 0,

                data_confidence TEXT
                    NOT NULL DEFAULT 'LOW',

                source_coverage_score REAL
                    NOT NULL DEFAULT 0,

                source_count INTEGER
                    NOT NULL DEFAULT 0,

                live_penalty REAL
                    NOT NULL DEFAULT 0,

                inactive_penalty REAL
                    NOT NULL DEFAULT 0,

                single_wallet_penalty REAL
                    NOT NULL DEFAULT 0,

                weak_consensus_penalty REAL
                    NOT NULL DEFAULT 0,

                chase_penalty REAL
                    NOT NULL DEFAULT 0,

                conflict_penalty REAL
                    NOT NULL DEFAULT 0,

                reversal_penalty REAL
                    NOT NULL DEFAULT 0,

                low_upside_penalty REAL
                    NOT NULL DEFAULT 0,

                weakening_penalty REAL
                    NOT NULL DEFAULT 0,

                incomplete_data_penalty REAL
                    NOT NULL DEFAULT 0,

                total_penalty REAL
                    NOT NULL DEFAULT 0,

                reasons_json TEXT,
                risk_flags_json TEXT,
                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `master_opportunity_history`

- Row count: `131`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | opportunity_key | TEXT | True | — | 0 |
| 2 | market_id | TEXT | True | — | 0 |
| 3 | title | TEXT | True | — | 0 |
| 4 | outcome | TEXT | True | — | 0 |
| 5 | master_score | REAL | False | — | 0 |
| 6 | master_grade | TEXT | False | — | 0 |
| 7 | master_tier | TEXT | False | — | 0 |
| 8 | recommendation | TEXT | False | — | 0 |
| 9 | lifecycle_status | TEXT | False | — | 0 |
| 10 | seconds_to_start | INTEGER | False | — | 0 |
| 11 | opportunity_score | REAL | False | — | 0 |
| 12 | institutional_score | REAL | False | — | 0 |
| 13 | evolution_score | REAL | False | — | 0 |
| 14 | closing_line_score | REAL | False | — | 0 |
| 15 | price_action_score | REAL | False | — | 0 |
| 16 | wallet_quality_score | REAL | False | — | 0 |
| 17 | timing_score | REAL | False | — | 0 |
| 18 | wallet_count | INTEGER | False | — | 0 |
| 19 | elite_wallet_count | INTEGER | False | — | 0 |
| 20 | effective_wallet_count | REAL | False | — | 0 |
| 21 | combined_current_value | REAL | False | — | 0 |
| 22 | consensus_strength | REAL | False | — | 0 |
| 23 | strengthening_score | REAL | False | — | 0 |
| 24 | weakening_score | REAL | False | — | 0 |
| 25 | net_value_change | REAL | False | — | 0 |
| 26 | clv_score | REAL | False | — | 0 |
| 27 | edge_remaining_score | REAL | False | — | 0 |
| 28 | chase_risk_score | REAL | False | — | 0 |
| 29 | steam_score | REAL | False | — | 0 |
| 30 | reversal_score | REAL | False | — | 0 |
| 31 | volatility_score | REAL | False | — | 0 |
| 32 | conflict_ratio | REAL | False | — | 0 |
| 33 | portfolio_independence_score | REAL | False | — | 0 |
| 34 | remaining_upside | REAL | False | — | 0 |
| 35 | data_completeness_score | REAL | False | — | 0 |
| 36 | data_confidence | TEXT | False | — | 0 |
| 37 | source_coverage_score | REAL | False | — | 0 |
| 38 | source_count | INTEGER | False | — | 0 |
| 39 | total_penalty | REAL | False | — | 0 |
| 40 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_master_history_key_time | False | c | False | opportunity_key, observed_at |

#### Source References

- `src/dashboard_schema_audit.py:25`
- `src/master_opportunity_engine.py:401,459,1932,2203,2581`

#### Create SQL

```sql
CREATE TABLE master_opportunity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                opportunity_key TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                master_score REAL,
                master_grade TEXT,
                master_tier TEXT,
                recommendation TEXT,

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                opportunity_score REAL,
                institutional_score REAL,
                evolution_score REAL,
                closing_line_score REAL,
                price_action_score REAL,
                wallet_quality_score REAL,
                timing_score REAL,

                wallet_count INTEGER,
                elite_wallet_count INTEGER,
                effective_wallet_count REAL,

                combined_current_value REAL,
                consensus_strength REAL,
                strengthening_score REAL,
                weakening_score REAL,
                net_value_change REAL,

                clv_score REAL,
                edge_remaining_score REAL,
                chase_risk_score REAL,

                steam_score REAL,
                reversal_score REAL,
                volatility_score REAL,

                conflict_ratio REAL,
                portfolio_independence_score REAL,
                remaining_upside REAL,

                data_completeness_score REAL,
                data_confidence TEXT,
                source_coverage_score REAL,
                source_count INTEGER,

                total_penalty REAL,

                observed_at TEXT NOT NULL
            )
```

### `master_opportunity_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | source_rows_seen | INTEGER | True | 0 | 0 |
| 5 | master_rows_saved | INTEGER | True | 0 | 0 |
| 6 | history_rows_created | INTEGER | True | 0 | 0 |
| 7 | alerts_created | INTEGER | True | 0 | 0 |
| 8 | status | TEXT | True | — | 0 |
| 9 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/master_opportunity_engine.py:500,2113,2147,2205`

#### Create SQL

```sql
CREATE TABLE master_opportunity_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                source_rows_seen INTEGER
                    NOT NULL DEFAULT 0,

                master_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                history_rows_created INTEGER
                    NOT NULL DEFAULT 0,

                alerts_created INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `master_pipeline_runs`

- Row count: `5`
- Referenced by: `master_pipeline_step_runs`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | mode | TEXT | True | — | 0 |
| 2 | started_at | TEXT | True | — | 0 |
| 3 | finished_at | TEXT | False | — | 0 |
| 4 | elapsed_seconds | REAL | False | — | 0 |
| 5 | successful_steps | INTEGER | True | 0 | 0 |
| 6 | failed_steps | INTEGER | True | 0 | 0 |
| 7 | skipped_steps | INTEGER | True | 0 | 0 |
| 8 | required_failures | INTEGER | True | 0 | 0 |
| 9 | optional_failures | INTEGER | True | 0 | 0 |
| 10 | status | TEXT | True | — | 0 |
| 11 | summary_log_path | TEXT | False | — | 0 |
| 12 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_master_pipeline_runs_started | False | c | False | started_at |

#### Source References

- `src/architecture_registry.py:476`
- `src/continuous_master_pipeline.py:439,471,501,531,617`

#### Create SQL

```sql
CREATE TABLE master_pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                mode TEXT NOT NULL,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                successful_steps INTEGER
                    NOT NULL DEFAULT 0,

                failed_steps INTEGER
                    NOT NULL DEFAULT 0,

                skipped_steps INTEGER
                    NOT NULL DEFAULT 0,

                required_failures INTEGER
                    NOT NULL DEFAULT 0,

                optional_failures INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,

                summary_log_path TEXT,
                error_message TEXT
            )
```

### `master_pipeline_step_runs`

- Row count: `17`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | pipeline_run_id | INTEGER | True | — | 0 |
| 2 | step_name | TEXT | True | — | 0 |
| 3 | step_key | TEXT | True | — | 0 |
| 4 | stage | TEXT | True | — | 0 |
| 5 | script_path | TEXT | False | — | 0 |
| 6 | required | INTEGER | True | 0 | 0 |
| 7 | status | TEXT | True | — | 0 |
| 8 | return_code | INTEGER | False | — | 0 |
| 9 | started_at | TEXT | True | — | 0 |
| 10 | finished_at | TEXT | False | — | 0 |
| 11 | elapsed_seconds | REAL | False | — | 0 |
| 12 | log_path | TEXT | False | — | 0 |
| 13 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| pipeline_run_id | master_pipeline_runs | id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_master_pipeline_step_runs_parent | False | c | False | pipeline_run_id, id |

#### Source References

- `src/continuous_master_pipeline.py:475,507,565`

#### Create SQL

```sql
CREATE TABLE master_pipeline_step_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                pipeline_run_id INTEGER NOT NULL,

                step_name TEXT NOT NULL,
                step_key TEXT NOT NULL,
                stage TEXT NOT NULL,

                script_path TEXT,
                required INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                return_code INTEGER,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                log_path TEXT,
                error_message TEXT,

                FOREIGN KEY(
                    pipeline_run_id
                )
                REFERENCES master_pipeline_runs(id)
                ON DELETE CASCADE
            )
```

### `methodology_optimization_candidates`

- Row count: `162`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | evaluation_key | TEXT | False | — | 1 |
| 1 | candidate_key | TEXT | True | — | 0 |
| 2 | candidate_name | TEXT | True | — | 0 |
| 3 | minimum_confidence | REAL | True | 0 | 0 |
| 4 | minimum_decision_score | REAL | True | 0 | 0 |
| 5 | minimum_actionability_score | REAL | True | 0 | 0 |
| 6 | minimum_trust_score | REAL | True | 0 | 0 |
| 7 | minimum_entry_quality_score | REAL | True | 0 | 0 |
| 8 | minimum_market_structure_score | REAL | True | 0 | 0 |
| 9 | minimum_data_quality_score | REAL | True | 0 | 0 |
| 10 | is_baseline | INTEGER | True | 0 | 0 |
| 11 | total_resolved_pool | INTEGER | True | 0 | 0 |
| 12 | selected_sample_size | INTEGER | True | 0 | 0 |
| 13 | excluded_sample_size | INTEGER | True | 0 | 0 |
| 14 | retention_rate | REAL | True | 0 | 0 |
| 15 | correct_count | INTEGER | True | 0 | 0 |
| 16 | incorrect_count | INTEGER | True | 0 | 0 |
| 17 | accuracy | REAL | True | 0 | 0 |
| 18 | average_confidence | REAL | True | 0 | 0 |
| 19 | calibration_gap | REAL | True | 0 | 0 |
| 20 | brier_score | REAL | True | 0 | 0 |
| 21 | log_loss | REAL | True | 0 | 0 |
| 22 | roi_sample_size | INTEGER | True | 0 | 0 |
| 23 | total_hypothetical_profit | REAL | True | 0 | 0 |
| 24 | average_hypothetical_return_pct | REAL | True | 0 | 0 |
| 25 | composite_score | REAL | True | 0 | 0 |
| 26 | sample_status | TEXT | True | — | 0 |
| 27 | recommendation_status | TEXT | True | — | 0 |
| 28 | recommendation_reason | TEXT | False | — | 0 |
| 29 | rank_position | INTEGER | True | 0 | 0 |
| 30 | engine_version | TEXT | True | — | 0 |
| 31 | calculated_at | TEXT | True | — | 0 |
| 32 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_methodology_optimization_candidate | False | c | False | candidate_key |
| idx_methodology_optimization_rank | False | c | False | recommendation_status, rank_position, composite_score |
| sqlite_autoindex_methodology_optimization_candidates_1 | True | pk | False | evaluation_key |

#### Source References

- `src/institutional_methodology_optimization_engine.py:384,473,481,1454`
- `src/institutional_methodology_optimization_engine_v10_backup.py:384,473,481,1454`

#### Create SQL

```sql
CREATE TABLE methodology_optimization_candidates (
            evaluation_key TEXT PRIMARY KEY,

            candidate_key TEXT NOT NULL,
            candidate_name TEXT NOT NULL,

            minimum_confidence REAL
                NOT NULL DEFAULT 0,

            minimum_decision_score REAL
                NOT NULL DEFAULT 0,

            minimum_actionability_score REAL
                NOT NULL DEFAULT 0,

            minimum_trust_score REAL
                NOT NULL DEFAULT 0,

            minimum_entry_quality_score REAL
                NOT NULL DEFAULT 0,

            minimum_market_structure_score REAL
                NOT NULL DEFAULT 0,

            minimum_data_quality_score REAL
                NOT NULL DEFAULT 0,

            is_baseline INTEGER
                NOT NULL DEFAULT 0,

            total_resolved_pool INTEGER
                NOT NULL DEFAULT 0,

            selected_sample_size INTEGER
                NOT NULL DEFAULT 0,

            excluded_sample_size INTEGER
                NOT NULL DEFAULT 0,

            retention_rate REAL
                NOT NULL DEFAULT 0,

            correct_count INTEGER
                NOT NULL DEFAULT 0,

            incorrect_count INTEGER
                NOT NULL DEFAULT 0,

            accuracy REAL
                NOT NULL DEFAULT 0,

            average_confidence REAL
                NOT NULL DEFAULT 0,

            calibration_gap REAL
                NOT NULL DEFAULT 0,

            brier_score REAL
                NOT NULL DEFAULT 0,

            log_loss REAL
                NOT NULL DEFAULT 0,

            roi_sample_size INTEGER
                NOT NULL DEFAULT 0,

            total_hypothetical_profit REAL
                NOT NULL DEFAULT 0,

            average_hypothetical_return_pct REAL
                NOT NULL DEFAULT 0,

            composite_score REAL
                NOT NULL DEFAULT 0,

            sample_status TEXT NOT NULL,
            recommendation_status TEXT NOT NULL,
            recommendation_reason TEXT,

            rank_position INTEGER
                NOT NULL DEFAULT 0,

            engine_version TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
```

### `methodology_optimization_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | engine_version | TEXT | True | — | 0 |
| 2 | mode | TEXT | True | — | 0 |
| 3 | started_at | TEXT | True | — | 0 |
| 4 | completed_at | TEXT | False | — | 0 |
| 5 | resolved_observations | INTEGER | True | 0 | 0 |
| 6 | candidate_definitions | INTEGER | True | 0 | 0 |
| 7 | candidate_evaluations | INTEGER | True | 0 | 0 |
| 8 | eligible_candidates | INTEGER | True | 0 | 0 |
| 9 | saved_candidates | INTEGER | True | 0 | 0 |
| 10 | duration_seconds | REAL | False | — | 0 |
| 11 | optimization_status | TEXT | True | — | 0 |
| 12 | status | TEXT | True | — | 0 |
| 13 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_methodology_optimization_runs_1 | True | pk | False | run_id |

#### Source References

- `src/institutional_methodology_optimization_engine.py:486,1641,1698`
- `src/institutional_methodology_optimization_engine_v10_backup.py:486,1641,1698`

#### Create SQL

```sql
CREATE TABLE methodology_optimization_runs (
            run_id TEXT PRIMARY KEY,

            engine_version TEXT NOT NULL,
            mode TEXT NOT NULL,

            started_at TEXT NOT NULL,
            completed_at TEXT,

            resolved_observations INTEGER
                NOT NULL DEFAULT 0,

            candidate_definitions INTEGER
                NOT NULL DEFAULT 0,

            candidate_evaluations INTEGER
                NOT NULL DEFAULT 0,

            eligible_candidates INTEGER
                NOT NULL DEFAULT 0,

            saved_candidates INTEGER
                NOT NULL DEFAULT 0,

            duration_seconds REAL,

            optimization_status TEXT NOT NULL,
            status TEXT NOT NULL,

            error_message TEXT
        )
```

### `model_calibration_buckets`

- Row count: `30`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | bucket_key | TEXT | False | — | 1 |
| 1 | group_type | TEXT | True | — | 0 |
| 2 | group_value | TEXT | True | — | 0 |
| 3 | bucket_number | INTEGER | True | — | 0 |
| 4 | lower_bound | REAL | True | — | 0 |
| 5 | upper_bound | REAL | True | — | 0 |
| 6 | bucket_label | TEXT | True | — | 0 |
| 7 | sample_size | INTEGER | True | 0 | 0 |
| 8 | correct_count | INTEGER | True | 0 | 0 |
| 9 | incorrect_count | INTEGER | True | 0 | 0 |
| 10 | average_confidence | REAL | False | — | 0 |
| 11 | empirical_accuracy | REAL | False | — | 0 |
| 12 | calibration_gap | REAL | False | — | 0 |
| 13 | absolute_calibration_gap | REAL | False | — | 0 |
| 14 | brier_score | REAL | False | — | 0 |
| 15 | log_loss | REAL | False | — | 0 |
| 16 | sample_status | TEXT | True | — | 0 |
| 17 | engine_version | TEXT | True | — | 0 |
| 18 | calculated_at | TEXT | True | — | 0 |
| 19 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_model_calibration_group | False | c | False | group_type, group_value, bucket_number |
| sqlite_autoindex_model_calibration_buckets_2 | True | u | False | group_type, group_value, bucket_number |
| sqlite_autoindex_model_calibration_buckets_1 | True | pk | False | bucket_key |

#### Source References

- `src/model_evaluation_calibration_engine.py:461,503,1562`
- `src/model_evaluation_calibration_engine_v10_backup.py:459,501,1560`

#### Create SQL

```sql
CREATE TABLE model_calibration_buckets (
            bucket_key TEXT PRIMARY KEY,

            group_type TEXT NOT NULL,
            group_value TEXT NOT NULL,

            bucket_number INTEGER NOT NULL,
            lower_bound REAL NOT NULL,
            upper_bound REAL NOT NULL,
            bucket_label TEXT NOT NULL,

            sample_size INTEGER
                NOT NULL DEFAULT 0,

            correct_count INTEGER
                NOT NULL DEFAULT 0,

            incorrect_count INTEGER
                NOT NULL DEFAULT 0,

            average_confidence REAL,
            empirical_accuracy REAL,
            calibration_gap REAL,
            absolute_calibration_gap REAL,
            brier_score REAL,
            log_loss REAL,

            sample_status TEXT NOT NULL,

            engine_version TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            UNIQUE(
                group_type,
                group_value,
                bucket_number
            )
        )
```

### `model_evaluation_metrics`

- Row count: `6`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | evaluation_key | TEXT | False | — | 1 |
| 1 | group_type | TEXT | True | — | 0 |
| 2 | group_value | TEXT | True | — | 0 |
| 3 | methodology_version | TEXT | False | — | 0 |
| 4 | decision_action | TEXT | False | — | 0 |
| 5 | decision_grade | TEXT | False | — | 0 |
| 6 | sample_size | INTEGER | True | 0 | 0 |
| 7 | correct_count | INTEGER | True | 0 | 0 |
| 8 | incorrect_count | INTEGER | True | 0 | 0 |
| 9 | accuracy | REAL | True | 0 | 0 |
| 10 | average_confidence | REAL | True | 0 | 0 |
| 11 | median_confidence | REAL | True | 0 | 0 |
| 12 | calibration_gap | REAL | True | 0 | 0 |
| 13 | absolute_calibration_gap | REAL | True | 0 | 0 |
| 14 | brier_score | REAL | True | 0 | 0 |
| 15 | log_loss | REAL | True | 0 | 0 |
| 16 | expected_calibration_error | REAL | True | 0 | 0 |
| 17 | maximum_calibration_error | REAL | True | 0 | 0 |
| 18 | overconfidence_rate | REAL | True | 0 | 0 |
| 19 | underconfidence_rate | REAL | True | 0 | 0 |
| 20 | average_decision_score | REAL | True | 0 | 0 |
| 21 | average_actionability_score | REAL | True | 0 | 0 |
| 22 | average_trust_score | REAL | True | 0 | 0 |
| 23 | average_entry_quality_score | REAL | True | 0 | 0 |
| 24 | average_market_structure_score | REAL | True | 0 | 0 |
| 25 | average_data_quality_score | REAL | True | 0 | 0 |
| 26 | sample_status | TEXT | True | — | 0 |
| 27 | reliability_grade | TEXT | True | — | 0 |
| 28 | evaluation_warning | TEXT | False | — | 0 |
| 29 | engine_version | TEXT | True | — | 0 |
| 30 | calculated_at | TEXT | True | — | 0 |
| 31 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_model_evaluation_sample | False | c | False | sample_size, reliability_grade |
| idx_model_evaluation_group | False | c | False | group_type, group_value |
| sqlite_autoindex_model_evaluation_metrics_2 | True | u | False | group_type, group_value, methodology_version, decision_action, decision_grade |
| sqlite_autoindex_model_evaluation_metrics_1 | True | pk | False | evaluation_key |

#### Source References

- `src/model_evaluation_calibration_engine.py:359,448,455,1413`
- `src/model_evaluation_calibration_engine_v10_backup.py:357,446,453,1411`

#### Create SQL

```sql
CREATE TABLE model_evaluation_metrics (
            evaluation_key TEXT PRIMARY KEY,

            group_type TEXT NOT NULL,
            group_value TEXT NOT NULL,

            methodology_version TEXT,
            decision_action TEXT,
            decision_grade TEXT,

            sample_size INTEGER
                NOT NULL DEFAULT 0,

            correct_count INTEGER
                NOT NULL DEFAULT 0,

            incorrect_count INTEGER
                NOT NULL DEFAULT 0,

            accuracy REAL
                NOT NULL DEFAULT 0,

            average_confidence REAL
                NOT NULL DEFAULT 0,

            median_confidence REAL
                NOT NULL DEFAULT 0,

            calibration_gap REAL
                NOT NULL DEFAULT 0,

            absolute_calibration_gap REAL
                NOT NULL DEFAULT 0,

            brier_score REAL
                NOT NULL DEFAULT 0,

            log_loss REAL
                NOT NULL DEFAULT 0,

            expected_calibration_error REAL
                NOT NULL DEFAULT 0,

            maximum_calibration_error REAL
                NOT NULL DEFAULT 0,

            overconfidence_rate REAL
                NOT NULL DEFAULT 0,

            underconfidence_rate REAL
                NOT NULL DEFAULT 0,

            average_decision_score REAL
                NOT NULL DEFAULT 0,

            average_actionability_score REAL
                NOT NULL DEFAULT 0,

            average_trust_score REAL
                NOT NULL DEFAULT 0,

            average_entry_quality_score REAL
                NOT NULL DEFAULT 0,

            average_market_structure_score REAL
                NOT NULL DEFAULT 0,

            average_data_quality_score REAL
                NOT NULL DEFAULT 0,

            sample_status TEXT NOT NULL,
            reliability_grade TEXT NOT NULL,
            evaluation_warning TEXT,

            engine_version TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            UNIQUE(
                group_type,
                group_value,
                methodology_version,
                decision_action,
                decision_grade
            )
        )
```

### `model_evaluation_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | engine_version | TEXT | True | — | 0 |
| 2 | mode | TEXT | True | — | 0 |
| 3 | started_at | TEXT | True | — | 0 |
| 4 | completed_at | TEXT | False | — | 0 |
| 5 | source_rows_loaded | INTEGER | True | 0 | 0 |
| 6 | resolved_rows_loaded | INTEGER | True | 0 | 0 |
| 7 | scorable_rows_loaded | INTEGER | True | 0 | 0 |
| 8 | excluded_abstentions | INTEGER | True | 0 | 0 |
| 9 | evaluation_groups_created | INTEGER | True | 0 | 0 |
| 10 | calibration_buckets_created | INTEGER | True | 0 | 0 |
| 11 | metrics_saved | INTEGER | True | 0 | 0 |
| 12 | buckets_saved | INTEGER | True | 0 | 0 |
| 13 | duration_seconds | REAL | False | — | 0 |
| 14 | status | TEXT | True | — | 0 |
| 15 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_model_evaluation_runs_1 | True | pk | False | run_id |

#### Source References

- `src/model_evaluation_calibration_engine.py:510,1660,1690`
- `src/model_evaluation_calibration_engine_v10_backup.py:508,1658,1688`

#### Create SQL

```sql
CREATE TABLE model_evaluation_runs (
            run_id TEXT PRIMARY KEY,

            engine_version TEXT NOT NULL,
            mode TEXT NOT NULL,

            started_at TEXT NOT NULL,
            completed_at TEXT,

            source_rows_loaded INTEGER
                NOT NULL DEFAULT 0,

            resolved_rows_loaded INTEGER
                NOT NULL DEFAULT 0,

            scorable_rows_loaded INTEGER
                NOT NULL DEFAULT 0,

            excluded_abstentions INTEGER
                NOT NULL DEFAULT 0,

            evaluation_groups_created INTEGER
                NOT NULL DEFAULT 0,

            calibration_buckets_created INTEGER
                NOT NULL DEFAULT 0,

            metrics_saved INTEGER
                NOT NULL DEFAULT 0,

            buckets_saved INTEGER
                NOT NULL DEFAULT 0,

            duration_seconds REAL,

            status TEXT NOT NULL,
            error_message TEXT
        )
```

### `monitor_alerts`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | alert_key | TEXT | True | — | 0 |
| 2 | alert_type | TEXT | True | — | 0 |
| 3 | severity | TEXT | True | — | 0 |
| 4 | market_id | TEXT | False | — | 0 |
| 5 | wallet | TEXT | False | — | 0 |
| 6 | title | TEXT | True | — | 0 |
| 7 | outcome | TEXT | False | — | 0 |
| 8 | message | TEXT | True | — | 0 |
| 9 | lifecycle_status | TEXT | False | — | 0 |
| 10 | seconds_to_start | INTEGER | False | — | 0 |
| 11 | wallet_count | INTEGER | False | — | 0 |
| 12 | conviction_score | REAL | False | — | 0 |
| 13 | capital_change | REAL | False | — | 0 |
| 14 | wallet_change | INTEGER | False | — | 0 |
| 15 | conviction_change | REAL | False | — | 0 |
| 16 | price_change | REAL | False | — | 0 |
| 17 | score | TEXT | False | — | 0 |
| 18 | period | TEXT | False | — | 0 |
| 19 | elapsed | TEXT | False | — | 0 |
| 20 | source_time | TEXT | False | — | 0 |
| 21 | created_at | TEXT | True | — | 0 |
| 22 | acknowledged | INTEGER | True | 0 | 0 |
| 23 | delivered_dashboard | INTEGER | True | 0 | 0 |
| 24 | delivered_discord | INTEGER | True | 0 | 0 |
| 25 | delivered_email | INTEGER | True | 0 | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| market_id | market_metadata | market_id | NO ACTION | SET NULL | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_monitor_alerts_unacknowledged | False | c | False | acknowledged, created_at |
| idx_monitor_alerts_market | False | c | False | market_id |
| idx_monitor_alerts_created | False | c | False | created_at |
| sqlite_autoindex_monitor_alerts_1 | True | u | False | alert_key |

#### Source References

- `src/market_monitor_database.py:215,271,279,287,586`
- `src/sports_live_listener.py:605,635`

#### Create SQL

```sql
CREATE TABLE monitor_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            alert_key TEXT NOT NULL UNIQUE,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL,

            market_id TEXT,
            wallet TEXT,

            title TEXT NOT NULL,
            outcome TEXT,

            message TEXT NOT NULL,

            lifecycle_status TEXT,

            seconds_to_start INTEGER,
            wallet_count INTEGER,
            conviction_score REAL,

            capital_change REAL,
            wallet_change INTEGER,
            conviction_change REAL,
            price_change REAL,

            score TEXT,
            period TEXT,
            elapsed TEXT,

            source_time TEXT,
            created_at TEXT NOT NULL,

            acknowledged INTEGER
                NOT NULL DEFAULT 0,

            delivered_dashboard INTEGER
                NOT NULL DEFAULT 0,

            delivered_discord INTEGER
                NOT NULL DEFAULT 0,

            delivered_email INTEGER
                NOT NULL DEFAULT 0,

            FOREIGN KEY (market_id)
                REFERENCES market_metadata(market_id)
                ON DELETE SET NULL
        )
```

### `monitor_locks`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | lock_name | TEXT | False | — | 1 |
| 1 | process_id | INTEGER | False | — | 0 |
| 2 | acquired_at | TEXT | True | — | 0 |
| 3 | expires_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_monitor_locks_1 | True | pk | False | lock_name |

#### Source References

- `src/continuous_monitor.py:290,327,335,375,409`
- `src/market_monitor_database.py:440,589`

#### Create SQL

```sql
CREATE TABLE monitor_locks (
            lock_name TEXT PRIMARY KEY,
            process_id INTEGER,
            acquired_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
```

### `monitor_runs`

- Row count: `10`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | status | TEXT | True | — | 0 |
| 3 | started_at | TEXT | True | — | 0 |
| 4 | finished_at | TEXT | False | — | 0 |
| 5 | elapsed_seconds | REAL | False | — | 0 |
| 6 | markets_checked | INTEGER | True | 0 | 0 |
| 7 | markets_updated | INTEGER | True | 0 | 0 |
| 8 | live_games | INTEGER | True | 0 | 0 |
| 9 | ended_games | INTEGER | True | 0 | 0 |
| 10 | resolved_markets | INTEGER | True | 0 | 0 |
| 11 | wallets_scanned | INTEGER | True | 0 | 0 |
| 12 | activities_created | INTEGER | True | 0 | 0 |
| 13 | alerts_created | INTEGER | True | 0 | 0 |
| 14 | error_type | TEXT | False | — | 0 |
| 15 | error_message | TEXT | False | — | 0 |
| 16 | log_path | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_monitor_runs_status | False | c | False | status |
| idx_monitor_runs_started | False | c | False | started_at |
| sqlite_autoindex_monitor_runs_1 | True | u | False | run_id |

#### Source References

- `src/market_monitor_database.py:302,348,356,587`
- `src/market_status_engine.py:1444,1485`

#### Create SQL

```sql
CREATE TABLE monitor_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            run_id TEXT NOT NULL UNIQUE,

            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,

            elapsed_seconds REAL,

            markets_checked INTEGER
                NOT NULL DEFAULT 0,

            markets_updated INTEGER
                NOT NULL DEFAULT 0,

            live_games INTEGER
                NOT NULL DEFAULT 0,

            ended_games INTEGER
                NOT NULL DEFAULT 0,

            resolved_markets INTEGER
                NOT NULL DEFAULT 0,

            wallets_scanned INTEGER
                NOT NULL DEFAULT 0,

            activities_created INTEGER
                NOT NULL DEFAULT 0,

            alerts_created INTEGER
                NOT NULL DEFAULT 0,

            error_type TEXT,
            error_message TEXT,
            log_path TEXT
        )
```

### `monitor_settings`

- Row count: `12`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | setting_key | TEXT | False | — | 1 |
| 1 | setting_value | TEXT | True | — | 0 |
| 2 | description | TEXT | False | — | 0 |
| 3 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_monitor_settings_1 | True | pk | False | setting_key |

#### Source References

- `src/continuous_monitor.py:202,234,248`
- `src/market_monitor_database.py:368,520,588`

#### Create SQL

```sql
CREATE TABLE monitor_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            description TEXT,
            updated_at TEXT NOT NULL
        )
```

### `official_wallet_activity`

- Row count: `141569`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | activity_key | TEXT | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | timestamp | INTEGER | True | 0 | 0 |
| 3 | observed_at | TEXT | False | — | 0 |
| 4 | condition_id | TEXT | False | — | 0 |
| 5 | activity_type | TEXT | False | — | 0 |
| 6 | side | TEXT | False | — | 0 |
| 7 | asset | TEXT | False | — | 0 |
| 8 | outcome | TEXT | False | — | 0 |
| 9 | outcome_index | INTEGER | False | — | 0 |
| 10 | size | REAL | True | 0 | 0 |
| 11 | usdc_size | REAL | True | 0 | 0 |
| 12 | price | REAL | True | 0 | 0 |
| 13 | transaction_hash | TEXT | False | — | 0 |
| 14 | title | TEXT | False | — | 0 |
| 15 | slug | TEXT | False | — | 0 |
| 16 | event_slug | TEXT | False | — | 0 |
| 17 | name | TEXT | False | — | 0 |
| 18 | pseudonym | TEXT | False | — | 0 |
| 19 | raw_json | TEXT | True | — | 0 |
| 20 | first_ingested_at | TEXT | True | — | 0 |
| 21 | last_seen_at | TEXT | True | — | 0 |
| 22 | is_combo | INTEGER | True | 0 | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_official_activity_market | False | c | False | condition_id, timestamp |
| idx_official_activity_wallet_time | False | c | False | wallet, timestamp |
| sqlite_autoindex_official_wallet_activity_1 | True | pk | False | activity_key |

#### Source References

- `src/decision_price_attribution_engine.py:12,56,1448,2273,2275`
- `src/decision_price_attribution_engine_v10_backup.py:12,56,1406,2203,2205`
- `src/decision_price_attribution_engine_v11_backup.py:12,56,1448,2258,2260`
- `src/market_identifier_registry_engine.py:978`
- `src/market_identity_enrichment_engine.py:401`
- `src/official_wallet_activity_engine.py:119,145,148,434,736`
- `src/official_wallet_activity_engine_v2.py:219,247,254,362,1031,1039,1678`

#### Create SQL

```sql
CREATE TABLE official_wallet_activity (
                activity_key TEXT PRIMARY KEY,
                wallet TEXT NOT NULL,
                timestamp INTEGER NOT NULL DEFAULT 0,
                observed_at TEXT,
                condition_id TEXT,
                activity_type TEXT,
                side TEXT,
                asset TEXT,
                outcome TEXT,
                outcome_index INTEGER,
                size REAL NOT NULL DEFAULT 0,
                usdc_size REAL NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0,
                transaction_hash TEXT,
                title TEXT,
                slug TEXT,
                event_slug TEXT,
                name TEXT,
                pseudonym TEXT,
                raw_json TEXT NOT NULL,
                first_ingested_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            , "is_combo" INTEGER NOT NULL DEFAULT 0)
```

### `official_wallet_trades`

- Row count: `151182`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | trade_key | TEXT | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | timestamp | INTEGER | True | 0 | 0 |
| 3 | observed_at | TEXT | False | — | 0 |
| 4 | condition_id | TEXT | False | — | 0 |
| 5 | side | TEXT | False | — | 0 |
| 6 | asset | TEXT | False | — | 0 |
| 7 | outcome | TEXT | False | — | 0 |
| 8 | outcome_index | INTEGER | False | — | 0 |
| 9 | size | REAL | True | 0 | 0 |
| 10 | price | REAL | True | 0 | 0 |
| 11 | notional | REAL | True | 0 | 0 |
| 12 | transaction_hash | TEXT | False | — | 0 |
| 13 | title | TEXT | False | — | 0 |
| 14 | slug | TEXT | False | — | 0 |
| 15 | event_slug | TEXT | False | — | 0 |
| 16 | raw_json | TEXT | True | — | 0 |
| 17 | first_ingested_at | TEXT | True | — | 0 |
| 18 | last_seen_at | TEXT | True | — | 0 |
| 19 | trade_source | TEXT | True | 'TRADES_ENDPOINT' | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_official_trades_market | False | c | False | condition_id, timestamp |
| idx_official_trades_wallet_time | False | c | False | wallet, timestamp |
| sqlite_autoindex_official_wallet_trades_1 | True | pk | False | trade_key |

#### Source References

- `src/decision_price_attribution_engine.py:11,55,745,1435,2262,2264`
- `src/decision_price_attribution_engine_v10_backup.py:11,55,745,1393,2192,2194`
- `src/decision_price_attribution_engine_v11_backup.py:11,55,745,1435,2247,2249`
- `src/market_identifier_registry_engine.py:946`
- `src/market_identity_enrichment_engine.py:391`
- `src/market_memory_engine.py:212,215,572,588,597`
- `src/official_wallet_activity_engine.py:150,173,176,515,523,739`
- `src/official_wallet_activity_engine_v2.py:259,284,291,365,1190,1206,1237,1239,1685`

#### Create SQL

```sql
CREATE TABLE official_wallet_trades (
                trade_key TEXT PRIMARY KEY,
                wallet TEXT NOT NULL,
                timestamp INTEGER NOT NULL DEFAULT 0,
                observed_at TEXT,
                condition_id TEXT,
                side TEXT,
                asset TEXT,
                outcome TEXT,
                outcome_index INTEGER,
                size REAL NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0,
                notional REAL NOT NULL DEFAULT 0,
                transaction_hash TEXT,
                title TEXT,
                slug TEXT,
                event_slug TEXT,
                raw_json TEXT NOT NULL,
                first_ingested_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            , "trade_source" TEXT NOT NULL DEFAULT 'TRADES_ENDPOINT')
```

### `opportunity_score_history`

- Row count: `501`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | opportunity_key | TEXT | True | — | 0 |
| 2 | market_id | TEXT | True | — | 0 |
| 3 | title | TEXT | True | — | 0 |
| 4 | outcome | TEXT | True | — | 0 |
| 5 | opportunity_score | REAL | True | — | 0 |
| 6 | opportunity_tier | TEXT | True | — | 0 |
| 7 | opportunity_grade | TEXT | True | — | 0 |
| 8 | recommended_action | TEXT | True | — | 0 |
| 9 | wallet_count | INTEGER | True | 0 | 0 |
| 10 | average_wallet_quality | REAL | True | 0 | 0 |
| 11 | combined_current_value | REAL | True | 0 | 0 |
| 12 | combined_open_pnl | REAL | True | 0 | 0 |
| 13 | open_pnl_ratio | REAL | True | 0 | 0 |
| 14 | average_entry_price | REAL | True | 0 | 0 |
| 15 | average_current_price | REAL | True | 0 | 0 |
| 16 | observed_price_move | REAL | True | 0 | 0 |
| 17 | average_wallet_concentration | REAL | True | 0 | 0 |
| 18 | conviction_score | REAL | True | 0 | 0 |
| 19 | consensus_component | REAL | True | 0 | 0 |
| 20 | wallet_quality_component | REAL | True | 0 | 0 |
| 21 | capital_component | REAL | True | 0 | 0 |
| 22 | profitability_component | REAL | True | 0 | 0 |
| 23 | momentum_component | REAL | True | 0 | 0 |
| 24 | timing_component | REAL | True | 0 | 0 |
| 25 | freshness_component | REAL | True | 0 | 0 |
| 26 | concentration_penalty | REAL | True | 0 | 0 |
| 27 | lifecycle_status | TEXT | False | — | 0 |
| 28 | game_start_time | TEXT | False | — | 0 |
| 29 | seconds_to_start | INTEGER | False | — | 0 |
| 30 | signal_observed_at | TEXT | False | — | 0 |
| 31 | explanation_json | TEXT | False | — | 0 |
| 32 | calculated_at | TEXT | True | — | 0 |
| 33 | is_pregame | INTEGER | True | 0 | 0 |
| 34 | is_live | INTEGER | True | 0 | 0 |
| 35 | is_ended | INTEGER | True | 0 | 0 |
| 36 | is_closed | INTEGER | True | 0 | 0 |
| 37 | is_resolved | INTEGER | True | 0 | 0 |
| 38 | score | TEXT | False | — | 0 |
| 39 | period | TEXT | False | — | 0 |
| 40 | elapsed | TEXT | False | — | 0 |
| 41 | metadata_updated_at | TEXT | False | — | 0 |
| 42 | updated_at | TEXT | False | — | 0 |
| 43 | market_type | TEXT | False | — | 0 |
| 44 | weighted_wallet_quality | REAL | False | 0 | 0 |
| 45 | average_dna_score | REAL | False | 0 | 0 |
| 46 | weighted_dna_score | REAL | False | 0 | 0 |
| 47 | average_leader_score | REAL | False | 0 | 0 |
| 48 | weighted_leader_score | REAL | False | 0 | 0 |
| 49 | average_activity_score | REAL | False | 0 | 0 |
| 50 | profitable_wallet_rate | REAL | False | 0 | 0 |
| 51 | elite_wallet_count | INTEGER | False | 0 | 0 |
| 52 | elite_wallet_value | REAL | False | 0 | 0 |
| 53 | elite_wallet_value_share | REAL | False | 0 | 0 |
| 54 | largest_wallet_share | REAL | False | 0 | 0 |
| 55 | top_three_wallet_share | REAL | False | 0 | 0 |
| 56 | effective_wallet_count | REAL | False | 0 | 0 |
| 57 | average_pair_overlap | REAL | False | 0 | 0 |
| 58 | portfolio_independence_score | REAL | False | 0 | 0 |
| 59 | overlap_pair_coverage | REAL | False | 0 | 0 |
| 60 | opposing_wallet_count | INTEGER | False | 0 | 0 |
| 61 | opposing_value | REAL | False | 0 | 0 |
| 62 | market_total_value | REAL | False | 0 | 0 |
| 63 | market_value_share | REAL | False | 0 | 0 |
| 64 | conflict_ratio | REAL | False | 0 | 0 |
| 65 | backtest_sample_size | INTEGER | False | 0 | 0 |
| 66 | backtest_win_rate | REAL | False | 0 | 0 |
| 67 | backtest_average_return | REAL | False | 0 | 0 |
| 68 | backtest_component | REAL | False | 50 | 0 |
| 69 | data_completeness_score | REAL | False | 0 | 0 |
| 70 | data_confidence | TEXT | False | 'LOW' | 0 |
| 71 | overlap_penalty | REAL | False | 0 | 0 |
| 72 | conflict_penalty | REAL | False | 0 | 0 |
| 73 | extreme_price_penalty | REAL | False | 0 | 0 |
| 74 | low_upside_penalty | REAL | False | 0 | 0 |
| 75 | chase_penalty | REAL | False | 0 | 0 |
| 76 | stale_penalty | REAL | False | 0 | 0 |
| 77 | total_penalty | REAL | False | 0 | 0 |
| 78 | remaining_upside | REAL | False | 0 | 0 |
| 79 | is_market_leader | INTEGER | False | 0 | 0 |
| 80 | wallets_json | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_opportunity_history_rank | False | c | False | calculated_at, opportunity_score |
| idx_opportunity_history_key | False | c | False | opportunity_key, calculated_at |

#### Source References

- `src/opportunity_engine.py:329,337,344,355,1120,1144,1177,1257`

#### Create SQL

```sql
CREATE TABLE opportunity_score_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                opportunity_key TEXT NOT NULL,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                opportunity_score REAL NOT NULL,
                opportunity_tier TEXT NOT NULL,
                opportunity_grade TEXT NOT NULL,
                recommended_action TEXT NOT NULL,

                wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                average_wallet_quality REAL
                    NOT NULL DEFAULT 0,

                combined_current_value REAL
                    NOT NULL DEFAULT 0,

                combined_open_pnl REAL
                    NOT NULL DEFAULT 0,

                open_pnl_ratio REAL
                    NOT NULL DEFAULT 0,

                average_entry_price REAL
                    NOT NULL DEFAULT 0,

                average_current_price REAL
                    NOT NULL DEFAULT 0,

                observed_price_move REAL
                    NOT NULL DEFAULT 0,

                average_wallet_concentration REAL
                    NOT NULL DEFAULT 0,

                conviction_score REAL
                    NOT NULL DEFAULT 0,

                consensus_component REAL
                    NOT NULL DEFAULT 0,

                wallet_quality_component REAL
                    NOT NULL DEFAULT 0,

                capital_component REAL
                    NOT NULL DEFAULT 0,

                profitability_component REAL
                    NOT NULL DEFAULT 0,

                momentum_component REAL
                    NOT NULL DEFAULT 0,

                timing_component REAL
                    NOT NULL DEFAULT 0,

                freshness_component REAL
                    NOT NULL DEFAULT 0,

                concentration_penalty REAL
                    NOT NULL DEFAULT 0,

                lifecycle_status TEXT,
                game_start_time TEXT,
                seconds_to_start INTEGER,

                signal_observed_at TEXT,
                explanation_json TEXT,

                calculated_at TEXT NOT NULL
            , "is_pregame" INTEGER NOT NULL DEFAULT 0, "is_live" INTEGER NOT NULL DEFAULT 0, "is_ended" INTEGER NOT NULL DEFAULT 0, "is_closed" INTEGER NOT NULL DEFAULT 0, "is_resolved" INTEGER NOT NULL DEFAULT 0, "score" TEXT, "period" TEXT, "elapsed" TEXT, "metadata_updated_at" TEXT, "updated_at" TEXT, "market_type" TEXT, "weighted_wallet_quality" REAL DEFAULT 0, "average_dna_score" REAL DEFAULT 0, "weighted_dna_score" REAL DEFAULT 0, "average_leader_score" REAL DEFAULT 0, "weighted_leader_score" REAL DEFAULT 0, "average_activity_score" REAL DEFAULT 0, "profitable_wallet_rate" REAL DEFAULT 0, "elite_wallet_count" INTEGER DEFAULT 0, "elite_wallet_value" REAL DEFAULT 0, "elite_wallet_value_share" REAL DEFAULT 0, "largest_wallet_share" REAL DEFAULT 0, "top_three_wallet_share" REAL DEFAULT 0, "effective_wallet_count" REAL DEFAULT 0, "average_pair_overlap" REAL DEFAULT 0, "portfolio_independence_score" REAL DEFAULT 0, "overlap_pair_coverage" REAL DEFAULT 0, "opposing_wallet_count" INTEGER DEFAULT 0, "opposing_value" REAL DEFAULT 0, "market_total_value" REAL DEFAULT 0, "market_value_share" REAL DEFAULT 0, "conflict_ratio" REAL DEFAULT 0, "backtest_sample_size" INTEGER DEFAULT 0, "backtest_win_rate" REAL DEFAULT 0, "backtest_average_return" REAL DEFAULT 0, "backtest_component" REAL DEFAULT 50, "data_completeness_score" REAL DEFAULT 0, "data_confidence" TEXT DEFAULT 'LOW', "overlap_penalty" REAL DEFAULT 0, "conflict_penalty" REAL DEFAULT 0, "extreme_price_penalty" REAL DEFAULT 0, "low_upside_penalty" REAL DEFAULT 0, "chase_penalty" REAL DEFAULT 0, "stale_penalty" REAL DEFAULT 0, "total_penalty" REAL DEFAULT 0, "remaining_upside" REAL DEFAULT 0, "is_market_leader" INTEGER DEFAULT 0, "wallets_json" TEXT)
```

### `opportunity_scores`

- Row count: `131`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | opportunity_key | TEXT | False | — | 1 |
| 1 | market_id | TEXT | True | — | 0 |
| 2 | title | TEXT | True | — | 0 |
| 3 | outcome | TEXT | True | — | 0 |
| 4 | opportunity_score | REAL | True | — | 0 |
| 5 | opportunity_tier | TEXT | True | — | 0 |
| 6 | opportunity_grade | TEXT | True | — | 0 |
| 7 | recommended_action | TEXT | True | — | 0 |
| 8 | wallet_count | INTEGER | True | 0 | 0 |
| 9 | average_wallet_quality | REAL | True | 0 | 0 |
| 10 | combined_current_value | REAL | True | 0 | 0 |
| 11 | combined_open_pnl | REAL | True | 0 | 0 |
| 12 | open_pnl_ratio | REAL | True | 0 | 0 |
| 13 | average_entry_price | REAL | True | 0 | 0 |
| 14 | average_current_price | REAL | True | 0 | 0 |
| 15 | observed_price_move | REAL | True | 0 | 0 |
| 16 | average_wallet_concentration | REAL | True | 0 | 0 |
| 17 | conviction_score | REAL | True | 0 | 0 |
| 18 | consensus_component | REAL | True | 0 | 0 |
| 19 | wallet_quality_component | REAL | True | 0 | 0 |
| 20 | capital_component | REAL | True | 0 | 0 |
| 21 | profitability_component | REAL | True | 0 | 0 |
| 22 | momentum_component | REAL | True | 0 | 0 |
| 23 | timing_component | REAL | True | 0 | 0 |
| 24 | freshness_component | REAL | True | 0 | 0 |
| 25 | concentration_penalty | REAL | True | 0 | 0 |
| 26 | lifecycle_status | TEXT | False | — | 0 |
| 27 | game_start_time | TEXT | False | — | 0 |
| 28 | seconds_to_start | INTEGER | False | — | 0 |
| 29 | is_pregame | INTEGER | True | 0 | 0 |
| 30 | is_live | INTEGER | True | 0 | 0 |
| 31 | is_ended | INTEGER | True | 0 | 0 |
| 32 | is_closed | INTEGER | True | 0 | 0 |
| 33 | is_resolved | INTEGER | True | 0 | 0 |
| 34 | score | TEXT | False | — | 0 |
| 35 | period | TEXT | False | — | 0 |
| 36 | elapsed | TEXT | False | — | 0 |
| 37 | signal_observed_at | TEXT | False | — | 0 |
| 38 | metadata_updated_at | TEXT | False | — | 0 |
| 39 | explanation_json | TEXT | False | — | 0 |
| 40 | calculated_at | TEXT | True | — | 0 |
| 41 | updated_at | TEXT | True | — | 0 |
| 42 | market_type | TEXT | False | — | 0 |
| 43 | weighted_wallet_quality | REAL | True | 0 | 0 |
| 44 | average_dna_score | REAL | True | 0 | 0 |
| 45 | weighted_dna_score | REAL | True | 0 | 0 |
| 46 | average_leader_score | REAL | True | 0 | 0 |
| 47 | weighted_leader_score | REAL | True | 0 | 0 |
| 48 | average_activity_score | REAL | True | 0 | 0 |
| 49 | profitable_wallet_rate | REAL | True | 0 | 0 |
| 50 | elite_wallet_count | INTEGER | True | 0 | 0 |
| 51 | elite_wallet_value | REAL | True | 0 | 0 |
| 52 | elite_wallet_value_share | REAL | True | 0 | 0 |
| 53 | largest_wallet_share | REAL | True | 0 | 0 |
| 54 | top_three_wallet_share | REAL | True | 0 | 0 |
| 55 | effective_wallet_count | REAL | True | 0 | 0 |
| 56 | average_pair_overlap | REAL | True | 0 | 0 |
| 57 | portfolio_independence_score | REAL | True | 0 | 0 |
| 58 | overlap_pair_coverage | REAL | True | 0 | 0 |
| 59 | opposing_wallet_count | INTEGER | True | 0 | 0 |
| 60 | opposing_value | REAL | True | 0 | 0 |
| 61 | market_total_value | REAL | True | 0 | 0 |
| 62 | market_value_share | REAL | True | 0 | 0 |
| 63 | conflict_ratio | REAL | True | 0 | 0 |
| 64 | backtest_sample_size | INTEGER | True | 0 | 0 |
| 65 | backtest_win_rate | REAL | True | 0 | 0 |
| 66 | backtest_average_return | REAL | True | 0 | 0 |
| 67 | backtest_component | REAL | True | 50 | 0 |
| 68 | data_completeness_score | REAL | True | 0 | 0 |
| 69 | data_confidence | TEXT | True | 'LOW' | 0 |
| 70 | overlap_penalty | REAL | True | 0 | 0 |
| 71 | conflict_penalty | REAL | True | 0 | 0 |
| 72 | extreme_price_penalty | REAL | True | 0 | 0 |
| 73 | low_upside_penalty | REAL | True | 0 | 0 |
| 74 | chase_penalty | REAL | True | 0 | 0 |
| 75 | stale_penalty | REAL | True | 0 | 0 |
| 76 | total_penalty | REAL | True | 0 | 0 |
| 77 | remaining_upside | REAL | True | 0 | 0 |
| 78 | is_market_leader | INTEGER | True | 0 | 0 |
| 79 | wallets_json | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_opportunity_scores_status | False | c | False | lifecycle_status, opportunity_score |
| idx_opportunity_scores_market | False | c | False | market_id |
| idx_opportunity_scores_rank | False | c | False | opportunity_score |
| sqlite_autoindex_opportunity_scores_1 | True | pk | False | opportunity_key |

#### Source References

- `src/dashboard_schema_audit.py:15`
- `src/data_access.py:793`
- `src/inspect_master_inputs.py:13,149,205,292,320,327,380,384,388,392,396,400,466,490,491,492,493,518,522,526,530,534,538,541`
- `src/market_identity_engine.py:466`
- `src/market_mapper_engine.py:21`
- `src/master_opportunity_engine.py:870,2196`
- `src/opportunity_engine.py:314,318,324,351,1119,1126,1130,1138,1176,1256`

#### Create SQL

```sql
CREATE TABLE opportunity_scores (
                opportunity_key TEXT PRIMARY KEY,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                opportunity_score REAL NOT NULL,
                opportunity_tier TEXT NOT NULL,
                opportunity_grade TEXT NOT NULL,
                recommended_action TEXT NOT NULL,

                wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                average_wallet_quality REAL
                    NOT NULL DEFAULT 0,

                combined_current_value REAL
                    NOT NULL DEFAULT 0,

                combined_open_pnl REAL
                    NOT NULL DEFAULT 0,

                open_pnl_ratio REAL
                    NOT NULL DEFAULT 0,

                average_entry_price REAL
                    NOT NULL DEFAULT 0,

                average_current_price REAL
                    NOT NULL DEFAULT 0,

                observed_price_move REAL
                    NOT NULL DEFAULT 0,

                average_wallet_concentration REAL
                    NOT NULL DEFAULT 0,

                conviction_score REAL
                    NOT NULL DEFAULT 0,

                consensus_component REAL
                    NOT NULL DEFAULT 0,

                wallet_quality_component REAL
                    NOT NULL DEFAULT 0,

                capital_component REAL
                    NOT NULL DEFAULT 0,

                profitability_component REAL
                    NOT NULL DEFAULT 0,

                momentum_component REAL
                    NOT NULL DEFAULT 0,

                timing_component REAL
                    NOT NULL DEFAULT 0,

                freshness_component REAL
                    NOT NULL DEFAULT 0,

                concentration_penalty REAL
                    NOT NULL DEFAULT 0,

                lifecycle_status TEXT,
                game_start_time TEXT,
                seconds_to_start INTEGER,

                is_pregame INTEGER
                    NOT NULL DEFAULT 0,

                is_live INTEGER
                    NOT NULL DEFAULT 0,

                is_ended INTEGER
                    NOT NULL DEFAULT 0,

                is_closed INTEGER
                    NOT NULL DEFAULT 0,

                is_resolved INTEGER
                    NOT NULL DEFAULT 0,

                score TEXT,
                period TEXT,
                elapsed TEXT,

                signal_observed_at TEXT,
                metadata_updated_at TEXT,

                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            , "market_type" TEXT, "weighted_wallet_quality" REAL NOT NULL DEFAULT 0, "average_dna_score" REAL NOT NULL DEFAULT 0, "weighted_dna_score" REAL NOT NULL DEFAULT 0, "average_leader_score" REAL NOT NULL DEFAULT 0, "weighted_leader_score" REAL NOT NULL DEFAULT 0, "average_activity_score" REAL NOT NULL DEFAULT 0, "profitable_wallet_rate" REAL NOT NULL DEFAULT 0, "elite_wallet_count" INTEGER NOT NULL DEFAULT 0, "elite_wallet_value" REAL NOT NULL DEFAULT 0, "elite_wallet_value_share" REAL NOT NULL DEFAULT 0, "largest_wallet_share" REAL NOT NULL DEFAULT 0, "top_three_wallet_share" REAL NOT NULL DEFAULT 0, "effective_wallet_count" REAL NOT NULL DEFAULT 0, "average_pair_overlap" REAL NOT NULL DEFAULT 0, "portfolio_independence_score" REAL NOT NULL DEFAULT 0, "overlap_pair_coverage" REAL NOT NULL DEFAULT 0, "opposing_wallet_count" INTEGER NOT NULL DEFAULT 0, "opposing_value" REAL NOT NULL DEFAULT 0, "market_total_value" REAL NOT NULL DEFAULT 0, "market_value_share" REAL NOT NULL DEFAULT 0, "conflict_ratio" REAL NOT NULL DEFAULT 0, "backtest_sample_size" INTEGER NOT NULL DEFAULT 0, "backtest_win_rate" REAL NOT NULL DEFAULT 0, "backtest_average_return" REAL NOT NULL DEFAULT 0, "backtest_component" REAL NOT NULL DEFAULT 50, "data_completeness_score" REAL NOT NULL DEFAULT 0, "data_confidence" TEXT NOT NULL DEFAULT 'LOW', "overlap_penalty" REAL NOT NULL DEFAULT 0, "conflict_penalty" REAL NOT NULL DEFAULT 0, "extreme_price_penalty" REAL NOT NULL DEFAULT 0, "low_upside_penalty" REAL NOT NULL DEFAULT 0, "chase_penalty" REAL NOT NULL DEFAULT 0, "stale_penalty" REAL NOT NULL DEFAULT 0, "total_penalty" REAL NOT NULL DEFAULT 0, "remaining_upside" REAL NOT NULL DEFAULT 0, "is_market_leader" INTEGER NOT NULL DEFAULT 0, "wallets_json" TEXT)
```

### `performance_analytics_runs`

- Row count: `2`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | mode | TEXT | True | — | 0 |
| 4 | wallet_limit | INTEGER | True | — | 0 |
| 5 | min_elite_score | REAL | True | — | 0 |
| 6 | min_closed_sample | INTEGER | True | — | 0 |
| 7 | wallets_selected | INTEGER | True | 0 | 0 |
| 8 | wallets_analyzed | INTEGER | True | 0 | 0 |
| 9 | wallets_failed | INTEGER | True | 0 | 0 |
| 10 | metrics_upserted | INTEGER | True | 0 | 0 |
| 11 | summaries_upserted | INTEGER | True | 0 | 0 |
| 12 | duration_seconds | REAL | True | 0 | 0 |
| 13 | status | TEXT | True | — | 0 |
| 14 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_performance_analytics_runs_1 | True | pk | False | run_id |

#### Source References

- `src/performance_analytics_engine.py:53`

#### Create SQL

```sql
CREATE TABLE "performance_analytics_runs" (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    mode TEXT NOT NULL,
                    wallet_limit INTEGER NOT NULL,
                    min_elite_score REAL NOT NULL,
                    min_closed_sample INTEGER NOT NULL,
                    wallets_selected INTEGER NOT NULL DEFAULT 0,
                    wallets_analyzed INTEGER NOT NULL DEFAULT 0,
                    wallets_failed INTEGER NOT NULL DEFAULT 0,
                    metrics_upserted INTEGER NOT NULL DEFAULT 0,
                    summaries_upserted INTEGER NOT NULL DEFAULT 0,
                    duration_seconds REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
```

### `platform_schema_migrations`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | migration_id | TEXT | False | — | 1 |
| 1 | applied_at | TEXT | True | — | 0 |
| 2 | description | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_platform_schema_migrations_1 | True | pk | False | migration_id |

#### Source References

- `src/elite_wallet_intelligence_database.py:23,419`

#### Create SQL

```sql
CREATE TABLE platform_schema_migrations (
        migration_id TEXT PRIMARY KEY,
        applied_at TEXT NOT NULL,
        description TEXT NOT NULL
    )
```

### `portfolio_overlap`

- Row count: `1763`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | wallet_a | TEXT | True | — | 0 |
| 2 | wallet_b | TEXT | True | — | 0 |
| 3 | wallet_a_market_count | INTEGER | True | 0 | 0 |
| 4 | wallet_b_market_count | INTEGER | True | 0 | 0 |
| 5 | shared_market_count | INTEGER | True | 0 | 0 |
| 6 | jaccard_similarity | REAL | True | 0 | 0 |
| 7 | weighted_overlap_score | REAL | True | 0 | 0 |
| 8 | shared_current_value | REAL | True | 0 | 0 |
| 9 | combined_current_value | REAL | True | 0 | 0 |
| 10 | same_direction_count | INTEGER | True | 0 | 0 |
| 11 | opposing_direction_count | INTEGER | True | 0 | 0 |
| 12 | calculated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_portfolio_overlap_unique_pair | True | c | False | wallet_a, wallet_b, calculated_at |
| idx_portfolio_overlap_similarity | False | c | False | weighted_overlap_score |
| idx_portfolio_overlap_wallet_b | False | c | False | wallet_b |
| idx_portfolio_overlap_wallet_a | False | c | False | wallet_a |

#### Source References

- `src/continuous_master_pipeline.py:87,90`
- `src/dashboard_schema_audit.py:22`
- `src/inspect_master_inputs.py:20`
- `src/institutional_consensus_engine.py:714,718,2211`
- `src/intelligence_database.py:418,446,454,462,472,630`
- `src/opportunity_engine.py:459,1012,1172`
- `src/portfolio_overlap_engine.py:643,654,1002`
- `src/wallet_dna_engine_backup.py:625,631,653,676`

#### Create SQL

```sql
CREATE TABLE portfolio_overlap (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            wallet_a TEXT NOT NULL,
            wallet_b TEXT NOT NULL,

            wallet_a_market_count INTEGER NOT NULL DEFAULT 0,
            wallet_b_market_count INTEGER NOT NULL DEFAULT 0,
            shared_market_count INTEGER NOT NULL DEFAULT 0,

            jaccard_similarity REAL NOT NULL DEFAULT 0,
            weighted_overlap_score REAL NOT NULL DEFAULT 0,

            shared_current_value REAL NOT NULL DEFAULT 0,
            combined_current_value REAL NOT NULL DEFAULT 0,

            same_direction_count INTEGER NOT NULL DEFAULT 0,
            opposing_direction_count INTEGER NOT NULL DEFAULT 0,

            calculated_at TEXT NOT NULL
        )
```

### `position_evolution`

- Row count: `345`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | evolution_key | TEXT | False | — | 1 |
| 1 | market_id | TEXT | True | — | 0 |
| 2 | title | TEXT | True | — | 0 |
| 3 | outcome | TEXT | True | — | 0 |
| 4 | prior_wallet_count | INTEGER | True | 0 | 0 |
| 5 | current_wallet_count | INTEGER | True | 0 | 0 |
| 6 | wallet_count_change | INTEGER | True | 0 | 0 |
| 7 | prior_elite_wallet_count | INTEGER | True | 0 | 0 |
| 8 | current_elite_wallet_count | INTEGER | True | 0 | 0 |
| 9 | elite_wallet_count_change | INTEGER | True | 0 | 0 |
| 10 | new_wallet_count | INTEGER | True | 0 | 0 |
| 11 | exited_wallet_count | INTEGER | True | 0 | 0 |
| 12 | increased_wallet_count | INTEGER | True | 0 | 0 |
| 13 | reduced_wallet_count | INTEGER | True | 0 | 0 |
| 14 | unchanged_wallet_count | INTEGER | True | 0 | 0 |
| 15 | new_elite_wallet_count | INTEGER | True | 0 | 0 |
| 16 | exited_elite_wallet_count | INTEGER | True | 0 | 0 |
| 17 | prior_total_value | REAL | True | 0 | 0 |
| 18 | current_total_value | REAL | True | 0 | 0 |
| 19 | net_value_change | REAL | True | 0 | 0 |
| 20 | gross_inflow | REAL | True | 0 | 0 |
| 21 | gross_outflow | REAL | True | 0 | 0 |
| 22 | prior_total_shares | REAL | True | 0 | 0 |
| 23 | current_total_shares | REAL | True | 0 | 0 |
| 24 | net_share_change | REAL | True | 0 | 0 |
| 25 | capital_growth_ratio | REAL | True | 0 | 0 |
| 26 | elite_capital_change | REAL | True | 0 | 0 |
| 27 | new_wallet_score | REAL | True | 0 | 0 |
| 28 | retention_score | REAL | True | 0 | 0 |
| 29 | elite_change_score | REAL | True | 0 | 0 |
| 30 | capital_flow_score | REAL | True | 0 | 0 |
| 31 | strengthening_score | REAL | True | 0 | 0 |
| 32 | weakening_score | REAL | True | 0 | 0 |
| 33 | evolution_score | REAL | True | 0 | 0 |
| 34 | evolution_grade | TEXT | True | 'PASS' | 0 |
| 35 | evolution_status | TEXT | True | 'NO CHANGE' | 0 |
| 36 | lifecycle_status | TEXT | False | — | 0 |
| 37 | seconds_to_start | INTEGER | False | — | 0 |
| 38 | prior_scan_at | TEXT | False | — | 0 |
| 39 | current_scan_at | TEXT | False | — | 0 |
| 40 | data_completeness_score | REAL | True | 0 | 0 |
| 41 | data_confidence | TEXT | True | 'LOW' | 0 |
| 42 | wallet_changes_json | TEXT | False | — | 0 |
| 43 | explanation_json | TEXT | False | — | 0 |
| 44 | calculated_at | TEXT | True | — | 0 |
| 45 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_position_evolution_status | False | c | False | evolution_status, evolution_score |
| idx_position_evolution_rank | False | c | False | evolution_score |
| sqlite_autoindex_position_evolution_1 | True | pk | False | evolution_key |

#### Source References

- `src/architecture_registry.py:458`
- `src/condition_id_lineage_audit.py:38`
- `src/dashboard_repository.py:362`
- `src/dashboard_schema_audit.py:18`
- `src/data_access.py:522,536,544,768,795`
- `src/historical_market_reconciliation_engine.py:30`
- `src/inspect_master_inputs.py:15,151,213,294,346,386,387,468,501,502,503,524,525,543`
- `src/master_intelligence_dashboard_builder.py:251`
- `src/master_opportunity_engine.py:880,2198`
- `src/position_evolution_engine.py:192,316,322,1728,1737,1757,1921,2251`
- `src/registry_validation_gate.py:36`
- `src/signal_fusion_engine.py:23,1560,1996,2362`

#### Create SQL

```sql
CREATE TABLE position_evolution (
                evolution_key TEXT PRIMARY KEY,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                prior_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                current_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                wallet_count_change INTEGER
                    NOT NULL DEFAULT 0,

                prior_elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                current_elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                elite_wallet_count_change INTEGER
                    NOT NULL DEFAULT 0,

                new_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                exited_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                increased_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                reduced_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                unchanged_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                new_elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                exited_elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                prior_total_value REAL
                    NOT NULL DEFAULT 0,

                current_total_value REAL
                    NOT NULL DEFAULT 0,

                net_value_change REAL
                    NOT NULL DEFAULT 0,

                gross_inflow REAL
                    NOT NULL DEFAULT 0,

                gross_outflow REAL
                    NOT NULL DEFAULT 0,

                prior_total_shares REAL
                    NOT NULL DEFAULT 0,

                current_total_shares REAL
                    NOT NULL DEFAULT 0,

                net_share_change REAL
                    NOT NULL DEFAULT 0,

                capital_growth_ratio REAL
                    NOT NULL DEFAULT 0,

                elite_capital_change REAL
                    NOT NULL DEFAULT 0,

                new_wallet_score REAL
                    NOT NULL DEFAULT 0,

                retention_score REAL
                    NOT NULL DEFAULT 0,

                elite_change_score REAL
                    NOT NULL DEFAULT 0,

                capital_flow_score REAL
                    NOT NULL DEFAULT 0,

                strengthening_score REAL
                    NOT NULL DEFAULT 0,

                weakening_score REAL
                    NOT NULL DEFAULT 0,

                evolution_score REAL
                    NOT NULL DEFAULT 0,

                evolution_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                evolution_status TEXT
                    NOT NULL DEFAULT 'NO CHANGE',

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                prior_scan_at TEXT,
                current_scan_at TEXT,

                data_completeness_score REAL
                    NOT NULL DEFAULT 0,

                data_confidence TEXT
                    NOT NULL DEFAULT 'LOW',

                wallet_changes_json TEXT,
                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `position_evolution_history`

- Row count: `345`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | evolution_key | TEXT | True | — | 0 |
| 2 | market_id | TEXT | True | — | 0 |
| 3 | title | TEXT | True | — | 0 |
| 4 | outcome | TEXT | True | — | 0 |
| 5 | prior_wallet_count | INTEGER | False | — | 0 |
| 6 | current_wallet_count | INTEGER | False | — | 0 |
| 7 | wallet_count_change | INTEGER | False | — | 0 |
| 8 | prior_elite_wallet_count | INTEGER | False | — | 0 |
| 9 | current_elite_wallet_count | INTEGER | False | — | 0 |
| 10 | elite_wallet_count_change | INTEGER | False | — | 0 |
| 11 | new_wallet_count | INTEGER | False | — | 0 |
| 12 | exited_wallet_count | INTEGER | False | — | 0 |
| 13 | increased_wallet_count | INTEGER | False | — | 0 |
| 14 | reduced_wallet_count | INTEGER | False | — | 0 |
| 15 | unchanged_wallet_count | INTEGER | False | — | 0 |
| 16 | new_elite_wallet_count | INTEGER | False | — | 0 |
| 17 | exited_elite_wallet_count | INTEGER | False | — | 0 |
| 18 | prior_total_value | REAL | False | — | 0 |
| 19 | current_total_value | REAL | False | — | 0 |
| 20 | net_value_change | REAL | False | — | 0 |
| 21 | gross_inflow | REAL | False | — | 0 |
| 22 | gross_outflow | REAL | False | — | 0 |
| 23 | prior_total_shares | REAL | False | — | 0 |
| 24 | current_total_shares | REAL | False | — | 0 |
| 25 | net_share_change | REAL | False | — | 0 |
| 26 | capital_growth_ratio | REAL | False | — | 0 |
| 27 | elite_capital_change | REAL | False | — | 0 |
| 28 | new_wallet_score | REAL | False | — | 0 |
| 29 | retention_score | REAL | False | — | 0 |
| 30 | elite_change_score | REAL | False | — | 0 |
| 31 | capital_flow_score | REAL | False | — | 0 |
| 32 | strengthening_score | REAL | False | — | 0 |
| 33 | weakening_score | REAL | False | — | 0 |
| 34 | evolution_score | REAL | False | — | 0 |
| 35 | evolution_grade | TEXT | False | — | 0 |
| 36 | evolution_status | TEXT | False | — | 0 |
| 37 | lifecycle_status | TEXT | False | — | 0 |
| 38 | seconds_to_start | INTEGER | False | — | 0 |
| 39 | prior_scan_at | TEXT | False | — | 0 |
| 40 | current_scan_at | TEXT | False | — | 0 |
| 41 | data_completeness_score | REAL | False | — | 0 |
| 42 | data_confidence | TEXT | False | — | 0 |
| 43 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_position_evolution_history_key | False | c | False | evolution_key, observed_at |

#### Source References

- `src/position_evolution_engine.py:327,391,1779,1922,2256`

#### Create SQL

```sql
CREATE TABLE position_evolution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                evolution_key TEXT NOT NULL,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                prior_wallet_count INTEGER,
                current_wallet_count INTEGER,
                wallet_count_change INTEGER,

                prior_elite_wallet_count INTEGER,
                current_elite_wallet_count INTEGER,
                elite_wallet_count_change INTEGER,

                new_wallet_count INTEGER,
                exited_wallet_count INTEGER,
                increased_wallet_count INTEGER,
                reduced_wallet_count INTEGER,
                unchanged_wallet_count INTEGER,

                new_elite_wallet_count INTEGER,
                exited_elite_wallet_count INTEGER,

                prior_total_value REAL,
                current_total_value REAL,
                net_value_change REAL,
                gross_inflow REAL,
                gross_outflow REAL,

                prior_total_shares REAL,
                current_total_shares REAL,
                net_share_change REAL,

                capital_growth_ratio REAL,
                elite_capital_change REAL,

                new_wallet_score REAL,
                retention_score REAL,
                elite_change_score REAL,
                capital_flow_score REAL,
                strengthening_score REAL,
                weakening_score REAL,

                evolution_score REAL,
                evolution_grade TEXT,
                evolution_status TEXT,

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                prior_scan_at TEXT,
                current_scan_at TEXT,

                data_completeness_score REAL,
                data_confidence TEXT,

                observed_at TEXT NOT NULL
            )
```

### `position_evolution_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | wallet_pairs_compared | INTEGER | True | 0 | 0 |
| 5 | market_groups_calculated | INTEGER | True | 0 | 0 |
| 6 | current_rows_saved | INTEGER | True | 0 | 0 |
| 7 | history_rows_created | INTEGER | True | 0 | 0 |
| 8 | status | TEXT | True | — | 0 |
| 9 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/position_evolution_engine.py:396,1834,1868,1923`

#### Create SQL

```sql
CREATE TABLE position_evolution_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                wallet_pairs_compared INTEGER
                    NOT NULL DEFAULT 0,

                market_groups_calculated INTEGER
                    NOT NULL DEFAULT 0,

                current_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                history_rows_created INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `positions`

- Row count: `23609`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | scan_id | INTEGER | True | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | market_id | TEXT | False | — | 0 |
| 4 | title | TEXT | True | — | 0 |
| 5 | outcome | TEXT | False | — | 0 |
| 6 | shares | REAL | False | 0 | 0 |
| 7 | average_price | REAL | False | 0 | 0 |
| 8 | current_price | REAL | False | 0 | 0 |
| 9 | current_value | REAL | False | 0 | 0 |
| 10 | cash_pnl | REAL | False | 0 | 0 |
| 11 | percent_pnl | REAL | False | 0 | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| scan_id | wallet_scans | id | NO ACTION | NO ACTION | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_positions_market_outcome | False | c | False | market_id, outcome |
| idx_positions_scan_id | False | c | False | scan_id |

#### Source References

- `src/ai_research_engine.py:170,191`
- `src/backtesting_engine.py:452`
- `src/candidate_qualification_engine.py:1254,2064`
- `src/change_detector.py:59,104`
- `src/closing_line_engine.py:333,416,419,1149`
- `src/command_center.py:583`
- `src/condition_id_lineage_audit.py:35`
- `src/consensus_diagnostics.py:29,57`
- `src/consensus_engine.py:46,66,91,94,102,222,230,264,265`
- `src/conviction_engine.py:44,70,94,97,108,402,413,528,532,556`
- `src/dashboard.py:588,589,611,900,901`
- `src/dashboard_repository.py:365,375`
- `src/dashboard_schema_audit.py:28`
- `src/data_access.py:587,605,606,608,609,611,613,614,622,637,649,664,778,800`
- `src/database.py:46,143,150,387,545,586,600,700,717`
- `src/elite_wallet_intelligence_database.py:249,252,272,291,462`
- `src/elite_wallet_ranking_engine.py:1941`
- `src/institutional_consensus_engine.py:601,602,604,606,608,611,660,661,662,663,664,665,666,671,672,673,676,678,680,682,685,767,777,2209`
- `src/intelligence_database.py:682`
- `src/market_classifier.py:359`
- `src/market_identity_engine.py:469`
- `src/market_intelligence_engine.py:316,319,356,391,412`
- `src/market_mapper_engine.py:20`
- `src/market_monitor_database.py:637`
- `src/market_status_engine.py:277,288,289,290,291,294,298,300,301,303,304,305`
- `src/master_intelligence_dashboard_builder.py:263`
- `src/ml_ranking_engine.py:195`
- `src/official_api_validator.py:52,53,59`
- `src/opportunity_engine.py:391,717,725,1170`
- `src/pages/1_Market_Intelligence_Timeline.py:168,181,182,183,184,185,186,187,188,190,191,192,193,195`
- `src/pages/2_Smart_Money_Radar.py:193,195,208,209,210,211,212,214,215,216,217,218,219,220,228,233,236,238,242,528,633,1090,1095`
- `src/pages/4_Market_leadership.py:126,128,141,142,143,144,145,146,148,149,150,151,152,153,154,156,157,158,159,207,208,210,211,212,213`
- `src/pages/5_Wallet_Intelligence.py:269,271,283,284,285,286,287,288,289,290,291,292,294,295,297,298,468,651,663,670,744,842,971,973,977`
- `src/performance_analytics_engine.py:24`
- `src/platform_health.py:308,309,556,557`
- `src/portfolio_overlap_engine.py:92,94,110,111,112,113,114,115,116,117,118,119,120,122,123,124,125,126,127,128,130,131,155,158,165`
- `src/position_evolution_engine.py:566,607,614,1918`
- `src/signal_fusion_engine.py:717,740,984,994,1027,1071,1084,1104,1105,1579,1582,1672,2712,3295`
- `src/wallet_alpha_engine.py:635,642,656,665,674,683,688,855,985,1906`
- `src/wallet_coverage.py:38,65,66`
- `src/wallet_dna_engine_backup.py:516,535,986,1002,1878,2261,2338`
- `src/wallet_intelligence_engine.py:271,286,287,289,290,292,293,349,366,671,684,820,829,966,974,1106,1117,1148,1481,1486,1506,1560`
- `src/wallet_intelligence_source.py:22,110,115,122,265,366,393,412,485,508,524,530,544`
- `src/wallet_metrics.py:89,90,93,98,102,106,111,115,120,125,130,135,187,228,234,254,256,334,339,367,385`
- `src/wallet_performance_engine.py:429,448,1665,1730,1765`
- `src/wallet_profile_collector.py:622,638,1218,1222,1308,1311`
- `src/wallet_profiler.py:72,147,185,698,753,857`
- `src/wallet_rating_engine.py:132,148,162,166,178,182,235,443,445,449,538`
- `src/wallet_scoring.py:121,171`
- `src/wallet_tracker.py:90,98,109,111,114,135,136,143,146,147,153,223,227,231,238,250,362,383,423,428`
- `src/wallet_trade_ledger.py:264,279,284,290,359,371,783,894,919,965,1046,1060,1086,1090,1145,1157,1168,1185,1197`
- `src/watchlist_scanner.py:23,26,27,38,40,41,44,48,187`
- `src/weighted_consensus_engine.py:120,145,169,173,184,540,573,576,598`

#### Create SQL

```sql
CREATE TABLE positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            wallet TEXT NOT NULL,
            market_id TEXT,
            title TEXT NOT NULL,
            outcome TEXT,
            shares REAL DEFAULT 0,
            average_price REAL DEFAULT 0,
            current_price REAL DEFAULT 0,
            current_value REAL DEFAULT 0,
            cash_pnl REAL DEFAULT 0,
            percent_pnl REAL DEFAULT 0,
            FOREIGN KEY (scan_id) REFERENCES wallet_scans(id)
        )
```

### `price_history_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | markets_seen | INTEGER | True | 0 | 0 |
| 5 | snapshots_inserted | INTEGER | True | 0 | 0 |
| 6 | snapshots_skipped | INTEGER | True | 0 | 0 |
| 7 | metrics_updated | INTEGER | True | 0 | 0 |
| 8 | rows_deleted | INTEGER | True | 0 | 0 |
| 9 | status | TEXT | True | — | 0 |
| 10 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/price_history_engine.py:386,1553,1597,1650`

#### Create SQL

```sql
CREATE TABLE price_history_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                markets_seen INTEGER
                    NOT NULL DEFAULT 0,

                snapshots_inserted INTEGER
                    NOT NULL DEFAULT 0,

                snapshots_skipped INTEGER
                    NOT NULL DEFAULT 0,

                metrics_updated INTEGER
                    NOT NULL DEFAULT 0,

                rows_deleted INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `ranked_market_opportunities`

- Row count: `5`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | opportunity_key | TEXT | False | — | 1 |
| 1 | rank_number | INTEGER | False | — | 0 |
| 2 | condition_id | TEXT | True | — | 0 |
| 3 | market_id | TEXT | False | — | 0 |
| 4 | event_id | TEXT | False | — | 0 |
| 5 | title | TEXT | False | — | 0 |
| 6 | outcome | TEXT | False | — | 0 |
| 7 | event_slug | TEXT | False | — | 0 |
| 8 | market_slug | TEXT | False | — | 0 |
| 9 | polymarket_url | TEXT | False | — | 0 |
| 10 | url_source | TEXT | False | — | 0 |
| 11 | link_verified | INTEGER | True | 0 | 0 |
| 12 | category | TEXT | False | — | 0 |
| 13 | lookback_hours | INTEGER | True | 24 | 0 |
| 14 | prediction_key | TEXT | False | — | 0 |
| 15 | flow_signal_key | TEXT | False | — | 0 |
| 16 | memory_snapshot_key | TEXT | False | — | 0 |
| 17 | predicted_direction | TEXT | False | — | 0 |
| 18 | research_probability | REAL | True | 50 | 0 |
| 19 | prediction_confidence | REAL | True | 0 | 0 |
| 20 | prediction_grade | TEXT | False | — | 0 |
| 21 | prediction_action | TEXT | False | — | 0 |
| 22 | smart_money_flow_score | REAL | True | 0 | 0 |
| 23 | market_memory_score | REAL | True | 0 | 0 |
| 24 | consensus_strength | REAL | True | 0 | 0 |
| 25 | persistence_score | REAL | True | 0 | 0 |
| 26 | trusted_flow_score | REAL | True | 0 | 0 |
| 27 | accumulation_score | REAL | True | 0 | 0 |
| 28 | distribution_score | REAL | True | 0 | 0 |
| 29 | current_net_flow | REAL | True | 0 | 0 |
| 30 | current_gross_flow | REAL | True | 0 | 0 |
| 31 | wallet_count | INTEGER | True | 0 | 0 |
| 32 | elite_wallet_count | INTEGER | True | 0 | 0 |
| 33 | qualified_wallet_count | INTEGER | True | 0 | 0 |
| 34 | watchlist_wallet_count | INTEGER | True | 0 | 0 |
| 35 | concentration_risk | REAL | True | 0 | 0 |
| 36 | whale_concentration | REAL | True | 0 | 0 |
| 37 | data_completeness_score | REAL | True | 0 | 0 |
| 38 | model_disagreement_score | REAL | True | 0 | 0 |
| 39 | current_price | REAL | False | — | 0 |
| 40 | probability_edge | REAL | True | 0 | 0 |
| 41 | liquidity | REAL | True | 0 | 0 |
| 42 | volume | REAL | True | 0 | 0 |
| 43 | open_interest | REAL | True | 0 | 0 |
| 44 | spread | REAL | False | — | 0 |
| 45 | market_start_at | TEXT | False | — | 0 |
| 46 | market_end_at | TEXT | False | — | 0 |
| 47 | event_start_at | TEXT | False | — | 0 |
| 48 | event_end_at | TEXT | False | — | 0 |
| 49 | resolution_at | TEXT | False | — | 0 |
| 50 | t_minus_target_at | TEXT | False | — | 0 |
| 51 | t_minus_target_type | TEXT | False | — | 0 |
| 52 | t_minus_seconds | INTEGER | False | — | 0 |
| 53 | t_minus_display | TEXT | False | — | 0 |
| 54 | time_status | TEXT | True | 'UNKNOWN' | 0 |
| 55 | is_open | INTEGER | True | 0 | 0 |
| 56 | is_live | INTEGER | True | 0 | 0 |
| 57 | is_closed | INTEGER | True | 0 | 0 |
| 58 | is_expired | INTEGER | True | 0 | 0 |
| 59 | resolution_pending | INTEGER | True | 0 | 0 |
| 60 | starts_too_soon | INTEGER | True | 0 | 0 |
| 61 | exact_mapping | INTEGER | True | 0 | 0 |
| 62 | opportunity_score | REAL | True | 0 | 0 |
| 63 | opportunity_grade | TEXT | True | 'PASS' | 0 |
| 64 | recommendation | TEXT | True | 'PASS' | 0 |
| 65 | is_actionable | INTEGER | True | 0 | 0 |
| 66 | positive_evidence_json | TEXT | False | — | 0 |
| 67 | risk_flags_json | TEXT | False | — | 0 |
| 68 | component_scores_json | TEXT | False | — | 0 |
| 69 | metadata_json | TEXT | False | — | 0 |
| 70 | observed_at | TEXT | True | — | 0 |
| 71 | created_at | TEXT | True | — | 0 |
| 72 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_ranked_market_opportunities_time | False | c | False | time_status, t_minus_seconds |
| idx_ranked_market_opportunities_condition | False | c | False | condition_id, observed_at |
| idx_ranked_market_opportunities_rank | False | c | False | is_actionable, opportunity_score, rank_number |
| sqlite_autoindex_ranked_market_opportunities_1 | True | pk | False | opportunity_key |

#### Source References

- `src/architecture_registry.py:470`
- `src/condition_id_lineage_audit.py:33`
- `src/historical_market_reconciliation_engine.py:34`
- `src/opportunity_ranking_engine.py:381,545,553,560,2797,3431`
- `src/registry_validation_gate.py:40`

#### Create SQL

```sql
CREATE TABLE ranked_market_opportunities (
                opportunity_key TEXT PRIMARY KEY,

                rank_number INTEGER,

                condition_id TEXT NOT NULL,
                market_id TEXT,
                event_id TEXT,

                title TEXT,
                outcome TEXT,

                event_slug TEXT,
                market_slug TEXT,

                polymarket_url TEXT,
                url_source TEXT,
                link_verified INTEGER
                    NOT NULL DEFAULT 0,

                category TEXT,

                lookback_hours INTEGER
                    NOT NULL DEFAULT 24,

                prediction_key TEXT,
                flow_signal_key TEXT,
                memory_snapshot_key TEXT,

                predicted_direction TEXT,
                research_probability REAL
                    NOT NULL DEFAULT 50,

                prediction_confidence REAL
                    NOT NULL DEFAULT 0,

                prediction_grade TEXT,
                prediction_action TEXT,

                smart_money_flow_score REAL
                    NOT NULL DEFAULT 0,

                market_memory_score REAL
                    NOT NULL DEFAULT 0,

                consensus_strength REAL
                    NOT NULL DEFAULT 0,

                persistence_score REAL
                    NOT NULL DEFAULT 0,

                trusted_flow_score REAL
                    NOT NULL DEFAULT 0,

                accumulation_score REAL
                    NOT NULL DEFAULT 0,

                distribution_score REAL
                    NOT NULL DEFAULT 0,

                current_net_flow REAL
                    NOT NULL DEFAULT 0,

                current_gross_flow REAL
                    NOT NULL DEFAULT 0,

                wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                elite_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                qualified_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                watchlist_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                concentration_risk REAL
                    NOT NULL DEFAULT 0,

                whale_concentration REAL
                    NOT NULL DEFAULT 0,

                data_completeness_score REAL
                    NOT NULL DEFAULT 0,

                model_disagreement_score REAL
                    NOT NULL DEFAULT 0,

                current_price REAL,
                probability_edge REAL
                    NOT NULL DEFAULT 0,

                liquidity REAL
                    NOT NULL DEFAULT 0,

                volume REAL
                    NOT NULL DEFAULT 0,

                open_interest REAL
                    NOT NULL DEFAULT 0,

                spread REAL,

                market_start_at TEXT,
                market_end_at TEXT,
                event_start_at TEXT,
                event_end_at TEXT,
                resolution_at TEXT,

                t_minus_target_at TEXT,
                t_minus_target_type TEXT,
                t_minus_seconds INTEGER,
                t_minus_display TEXT,

                time_status TEXT
                    NOT NULL DEFAULT 'UNKNOWN',

                is_open INTEGER
                    NOT NULL DEFAULT 0,

                is_live INTEGER
                    NOT NULL DEFAULT 0,

                is_closed INTEGER
                    NOT NULL DEFAULT 0,

                is_expired INTEGER
                    NOT NULL DEFAULT 0,

                resolution_pending INTEGER
                    NOT NULL DEFAULT 0,

                starts_too_soon INTEGER
                    NOT NULL DEFAULT 0,

                exact_mapping INTEGER
                    NOT NULL DEFAULT 0,

                opportunity_score REAL
                    NOT NULL DEFAULT 0,

                opportunity_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                recommendation TEXT
                    NOT NULL DEFAULT 'PASS',

                is_actionable INTEGER
                    NOT NULL DEFAULT 0,

                positive_evidence_json TEXT,
                risk_flags_json TEXT,
                component_scores_json TEXT,
                metadata_json TEXT,

                observed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `registry_validation_gate_results`

- Row count: `29196`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | source_table | TEXT | True | — | 0 |
| 3 | source_rowid | INTEGER | False | — | 0 |
| 4 | market_id | TEXT | False | — | 0 |
| 5 | title | TEXT | False | — | 0 |
| 6 | outcome | TEXT | False | — | 0 |
| 7 | observed_at | TEXT | False | — | 0 |
| 8 | validation_status | TEXT | True | — | 0 |
| 9 | registry_source | TEXT | False | — | 0 |
| 10 | canonical_market_id | TEXT | False | — | 0 |
| 11 | tradable_identity | INTEGER | True | 0 | 0 |
| 12 | active | INTEGER | True | 0 | 0 |
| 13 | closed | INTEGER | True | 0 | 0 |
| 14 | archived | INTEGER | True | 0 | 0 |
| 15 | restricted | INTEGER | True | 0 | 0 |
| 16 | accepting_orders | INTEGER | True | 0 | 0 |
| 17 | polymarket_url | TEXT | False | — | 0 |
| 18 | reason_code | TEXT | True | — | 0 |
| 19 | reason_detail | TEXT | False | — | 0 |
| 20 | validated_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| run_id | registry_validation_gate_runs | run_id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_registry_validation_results_status | False | c | False | validation_status, validated_at |
| idx_registry_validation_results_market | False | c | False | market_id, validated_at |

#### Source References

- `src/registry_validation_gate.py:30`

#### Create SQL

```sql
CREATE TABLE "registry_validation_gate_results" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    source_table TEXT NOT NULL,
                    source_rowid INTEGER,
                    market_id TEXT,
                    title TEXT,
                    outcome TEXT,
                    observed_at TEXT,
                    validation_status TEXT NOT NULL,
                    registry_source TEXT,
                    canonical_market_id TEXT,
                    tradable_identity INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 0,
                    closed INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 0,
                    restricted INTEGER NOT NULL DEFAULT 0,
                    accepting_orders INTEGER NOT NULL DEFAULT 0,
                    polymarket_url TEXT,
                    reason_code TEXT NOT NULL,
                    reason_detail TEXT,
                    validated_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES "registry_validation_gate_runs"(run_id)
                        ON DELETE CASCADE
                )
```

### `registry_validation_gate_runs`

- Row count: `5`
- Referenced by: `registry_validation_gate_results`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | mode | TEXT | True | — | 0 |
| 5 | source_tables_json | TEXT | True | — | 0 |
| 6 | rows_scanned | INTEGER | True | 0 | 0 |
| 7 | valid_tradable | INTEGER | True | 0 | 0 |
| 8 | valid_non_tradable | INTEGER | True | 0 | 0 |
| 9 | legacy_only | INTEGER | True | 0 | 0 |
| 10 | malformed | INTEGER | True | 0 | 0 |
| 11 | missing_market_id | INTEGER | True | 0 | 0 |
| 12 | unknown_market | INTEGER | True | 0 | 0 |
| 13 | quarantined | INTEGER | True | 0 | 0 |
| 14 | status | TEXT | True | — | 0 |
| 15 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_registry_validation_gate_runs_1 | True | pk | False | run_id |

#### Source References

- `src/registry_validation_gate.py:29`

#### Create SQL

```sql
CREATE TABLE "registry_validation_gate_runs" (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    elapsed_seconds REAL,
                    mode TEXT NOT NULL,
                    source_tables_json TEXT NOT NULL,
                    rows_scanned INTEGER NOT NULL DEFAULT 0,
                    valid_tradable INTEGER NOT NULL DEFAULT 0,
                    valid_non_tradable INTEGER NOT NULL DEFAULT 0,
                    legacy_only INTEGER NOT NULL DEFAULT 0,
                    malformed INTEGER NOT NULL DEFAULT 0,
                    missing_market_id INTEGER NOT NULL DEFAULT 0,
                    unknown_market INTEGER NOT NULL DEFAULT 0,
                    quarantined INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
```

### `registry_validation_quarantine`

- Row count: `8872`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | first_run_id | TEXT | True | — | 0 |
| 2 | latest_run_id | TEXT | True | — | 0 |
| 3 | source_table | TEXT | True | — | 0 |
| 4 | source_rowid | INTEGER | False | — | 0 |
| 5 | market_id | TEXT | False | — | 0 |
| 6 | title | TEXT | False | — | 0 |
| 7 | outcome | TEXT | False | — | 0 |
| 8 | observed_at | TEXT | False | — | 0 |
| 9 | validation_status | TEXT | True | — | 0 |
| 10 | reason_code | TEXT | True | — | 0 |
| 11 | reason_detail | TEXT | False | — | 0 |
| 12 | first_seen_at | TEXT | True | — | 0 |
| 13 | last_seen_at | TEXT | True | — | 0 |
| 14 | occurrence_count | INTEGER | True | 1 | 0 |
| 15 | resolved | INTEGER | True | 0 | 0 |
| 16 | resolved_at | TEXT | False | — | 0 |
| 17 | resolution_note | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_registry_validation_quarantine_open | False | c | False | resolved, validation_status, last_seen_at |
| sqlite_autoindex_registry_validation_quarantine_1 | True | u | False | source_table, source_rowid, market_id, validation_status |

#### Source References

- `src/registry_validation_gate.py:31`

#### Create SQL

```sql
CREATE TABLE "registry_validation_quarantine" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    first_run_id TEXT NOT NULL,
                    latest_run_id TEXT NOT NULL,
                    source_table TEXT NOT NULL,
                    source_rowid INTEGER,
                    market_id TEXT,
                    title TEXT,
                    outcome TEXT,
                    observed_at TEXT,
                    validation_status TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    reason_detail TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    occurrence_count INTEGER NOT NULL DEFAULT 1,
                    resolved INTEGER NOT NULL DEFAULT 0,
                    resolved_at TEXT,
                    resolution_note TEXT,
                    UNIQUE(
                        source_table,
                        source_rowid,
                        market_id,
                        validation_status
                    )
                )
```

### `signal_fusion_alerts`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | opportunity_key | TEXT | True | — | 0 |
| 2 | market_id | TEXT | True | — | 0 |
| 3 | title | TEXT | True | — | 0 |
| 4 | outcome | TEXT | True | — | 0 |
| 5 | alert_type | TEXT | True | — | 0 |
| 6 | severity | TEXT | True | — | 0 |
| 7 | fusion_score | REAL | False | — | 0 |
| 8 | fusion_grade | TEXT | False | — | 0 |
| 9 | recommendation | TEXT | False | — | 0 |
| 10 | message | TEXT | True | — | 0 |
| 11 | details_json | TEXT | False | — | 0 |
| 12 | created_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_signal_fusion_alerts_created | False | c | False | created_at |

#### Source References

- `src/signal_fusion_engine.py:544,567,2930,3600`

#### Create SQL

```sql
CREATE TABLE signal_fusion_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                opportunity_key TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,

                fusion_score REAL,
                fusion_grade TEXT,
                recommendation TEXT,

                message TEXT NOT NULL,
                details_json TEXT,

                created_at TEXT NOT NULL
            )
```

### `signal_fusion_history`

- Row count: `131`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | opportunity_key | TEXT | True | — | 0 |
| 2 | market_id | TEXT | True | — | 0 |
| 3 | title | TEXT | True | — | 0 |
| 4 | outcome | TEXT | True | — | 0 |
| 5 | fusion_score | REAL | False | — | 0 |
| 6 | fusion_grade | TEXT | False | — | 0 |
| 7 | confidence_tier | TEXT | False | — | 0 |
| 8 | signal_strength | TEXT | False | — | 0 |
| 9 | recommendation | TEXT | False | — | 0 |
| 10 | agreeing_wallets | INTEGER | False | — | 0 |
| 11 | elite_wallets | INTEGER | False | — | 0 |
| 12 | combined_current_value | REAL | False | — | 0 |
| 13 | master_score | REAL | False | — | 0 |
| 14 | institutional_score | REAL | False | — | 0 |
| 15 | evolution_score | REAL | False | — | 0 |
| 16 | wallet_dna_score | REAL | False | — | 0 |
| 17 | wallet_performance_score | REAL | False | — | 0 |
| 18 | closing_line_score | REAL | False | — | 0 |
| 19 | price_action_score | REAL | False | — | 0 |
| 20 | mapping_quality_score | REAL | False | — | 0 |
| 21 | timing_score | REAL | False | — | 0 |
| 22 | total_penalty | REAL | False | — | 0 |
| 23 | data_completeness_score | REAL | False | — | 0 |
| 24 | data_confidence | TEXT | False | — | 0 |
| 25 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_signal_fusion_history_key | False | c | False | opportunity_key, observed_at |

#### Source References

- `src/signal_fusion_engine.py:502,539,3023,3595`

#### Create SQL

```sql
CREATE TABLE signal_fusion_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                opportunity_key TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                fusion_score REAL,
                fusion_grade TEXT,
                confidence_tier TEXT,
                signal_strength TEXT,
                recommendation TEXT,

                agreeing_wallets INTEGER,
                elite_wallets INTEGER,
                combined_current_value REAL,

                master_score REAL,
                institutional_score REAL,
                evolution_score REAL,
                wallet_dna_score REAL,
                wallet_performance_score REAL,
                closing_line_score REAL,
                price_action_score REAL,
                mapping_quality_score REAL,
                timing_score REAL,

                total_penalty REAL,
                data_completeness_score REAL,
                data_confidence TEXT,

                observed_at TEXT NOT NULL
            )
```

### `signal_fusion_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | opportunities_loaded | INTEGER | True | 0 | 0 |
| 5 | wallet_rows_loaded | INTEGER | True | 0 | 0 |
| 6 | fusion_rows_saved | INTEGER | True | 0 | 0 |
| 7 | fusion_wallet_rows_saved | INTEGER | True | 0 | 0 |
| 8 | history_rows_saved | INTEGER | True | 0 | 0 |
| 9 | alerts_saved | INTEGER | True | 0 | 0 |
| 10 | status | TEXT | True | — | 0 |
| 11 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/signal_fusion_engine.py:571,3179,3220`

#### Create SQL

```sql
CREATE TABLE signal_fusion_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                opportunities_loaded INTEGER
                    NOT NULL DEFAULT 0,

                wallet_rows_loaded INTEGER
                    NOT NULL DEFAULT 0,

                fusion_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                fusion_wallet_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                history_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                alerts_saved INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `signal_fusion_scores`

- Row count: `131`
- Referenced by: `signal_fusion_wallets`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | opportunity_key | TEXT | False | — | 1 |
| 1 | market_id | TEXT | True | — | 0 |
| 2 | title | TEXT | True | — | 0 |
| 3 | outcome | TEXT | True | — | 0 |
| 4 | gamma_market_id | TEXT | False | — | 0 |
| 5 | gamma_event_id | TEXT | False | — | 0 |
| 6 | condition_id | TEXT | False | — | 0 |
| 7 | fusion_score | REAL | True | 0 | 0 |
| 8 | fusion_grade | TEXT | True | 'PASS' | 0 |
| 9 | confidence_tier | TEXT | True | 'LOW' | 0 |
| 10 | signal_strength | TEXT | True | 'WEAK' | 0 |
| 11 | recommendation | TEXT | True | 'PASS' | 0 |
| 12 | lifecycle_status | TEXT | False | — | 0 |
| 13 | seconds_to_start | INTEGER | False | — | 0 |
| 14 | master_score | REAL | True | 0 | 0 |
| 15 | institutional_score | REAL | True | 0 | 0 |
| 16 | evolution_score | REAL | True | 0 | 0 |
| 17 | wallet_dna_score | REAL | True | 0 | 0 |
| 18 | wallet_performance_score | REAL | True | 0 | 0 |
| 19 | closing_line_score | REAL | True | 0 | 0 |
| 20 | price_action_score | REAL | True | 0 | 0 |
| 21 | mapping_quality_score | REAL | True | 0 | 0 |
| 22 | timing_score | REAL | True | 0 | 0 |
| 23 | agreeing_wallets | INTEGER | True | 0 | 0 |
| 24 | elite_wallets | INTEGER | True | 0 | 0 |
| 25 | effective_wallets | REAL | True | 0 | 0 |
| 26 | combined_current_value | REAL | True | 0 | 0 |
| 27 | average_wallet_dna | REAL | True | 0 | 0 |
| 28 | average_wallet_performance | REAL | True | 0 | 0 |
| 29 | specialist_wallet_share | REAL | True | 0 | 0 |
| 30 | independent_wallet_share | REAL | True | 0 | 0 |
| 31 | conflict_ratio | REAL | True | 0 | 0 |
| 32 | portfolio_independence_score | REAL | True | 0 | 0 |
| 33 | strengthening_score | REAL | True | 0 | 0 |
| 34 | weakening_score | REAL | True | 0 | 0 |
| 35 | net_value_change | REAL | True | 0 | 0 |
| 36 | clv_score | REAL | False | — | 0 |
| 37 | edge_remaining_score | REAL | False | — | 0 |
| 38 | chase_risk_score | REAL | False | — | 0 |
| 39 | steam_score | REAL | False | — | 0 |
| 40 | reversal_score | REAL | False | — | 0 |
| 41 | volatility_score | REAL | False | — | 0 |
| 42 | mapping_status | TEXT | False | — | 0 |
| 43 | match_method | TEXT | False | — | 0 |
| 44 | match_confidence | REAL | False | — | 0 |
| 45 | source_count | INTEGER | True | 0 | 0 |
| 46 | data_completeness_score | REAL | True | 0 | 0 |
| 47 | data_confidence | TEXT | True | 'LOW' | 0 |
| 48 | live_penalty | REAL | True | 0 | 0 |
| 49 | inactive_penalty | REAL | True | 0 | 0 |
| 50 | conflict_penalty | REAL | True | 0 | 0 |
| 51 | chase_penalty | REAL | True | 0 | 0 |
| 52 | reversal_penalty | REAL | True | 0 | 0 |
| 53 | weakening_penalty | REAL | True | 0 | 0 |
| 54 | low_sample_penalty | REAL | True | 0 | 0 |
| 55 | mapping_penalty | REAL | True | 0 | 0 |
| 56 | total_penalty | REAL | True | 0 | 0 |
| 57 | positive_signals_json | TEXT | False | — | 0 |
| 58 | negative_signals_json | TEXT | False | — | 0 |
| 59 | explanation_json | TEXT | False | — | 0 |
| 60 | calculated_at | TEXT | True | — | 0 |
| 61 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_signal_fusion_scores_recommendation | False | c | False | recommendation, fusion_score |
| idx_signal_fusion_scores_grade | False | c | False | fusion_grade, fusion_score |
| idx_signal_fusion_scores_rank | False | c | False | fusion_score |
| sqlite_autoindex_signal_fusion_scores_1 | True | pk | False | opportunity_key |

#### Source References

- `src/architecture_registry.py:464`
- `src/institutional_decision_intelligence_dashboard.py:227,699`
- `src/signal_fusion_engine.py:251,404,410,417,482,2985,3004,3585`

#### Create SQL

```sql
CREATE TABLE signal_fusion_scores (
                opportunity_key TEXT PRIMARY KEY,

                market_id TEXT NOT NULL,
                title TEXT NOT NULL,
                outcome TEXT NOT NULL,

                gamma_market_id TEXT,
                gamma_event_id TEXT,
                condition_id TEXT,

                fusion_score REAL
                    NOT NULL DEFAULT 0,

                fusion_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                confidence_tier TEXT
                    NOT NULL DEFAULT 'LOW',

                signal_strength TEXT
                    NOT NULL DEFAULT 'WEAK',

                recommendation TEXT
                    NOT NULL DEFAULT 'PASS',

                lifecycle_status TEXT,
                seconds_to_start INTEGER,

                master_score REAL
                    NOT NULL DEFAULT 0,

                institutional_score REAL
                    NOT NULL DEFAULT 0,

                evolution_score REAL
                    NOT NULL DEFAULT 0,

                wallet_dna_score REAL
                    NOT NULL DEFAULT 0,

                wallet_performance_score REAL
                    NOT NULL DEFAULT 0,

                closing_line_score REAL
                    NOT NULL DEFAULT 0,

                price_action_score REAL
                    NOT NULL DEFAULT 0,

                mapping_quality_score REAL
                    NOT NULL DEFAULT 0,

                timing_score REAL
                    NOT NULL DEFAULT 0,

                agreeing_wallets INTEGER
                    NOT NULL DEFAULT 0,

                elite_wallets INTEGER
                    NOT NULL DEFAULT 0,

                effective_wallets REAL
                    NOT NULL DEFAULT 0,

                combined_current_value REAL
                    NOT NULL DEFAULT 0,

                average_wallet_dna REAL
                    NOT NULL DEFAULT 0,

                average_wallet_performance REAL
                    NOT NULL DEFAULT 0,

                specialist_wallet_share REAL
                    NOT NULL DEFAULT 0,

                independent_wallet_share REAL
                    NOT NULL DEFAULT 0,

                conflict_ratio REAL
                    NOT NULL DEFAULT 0,

                portfolio_independence_score REAL
                    NOT NULL DEFAULT 0,

                strengthening_score REAL
                    NOT NULL DEFAULT 0,

                weakening_score REAL
                    NOT NULL DEFAULT 0,

                net_value_change REAL
                    NOT NULL DEFAULT 0,

                clv_score REAL,
                edge_remaining_score REAL,
                chase_risk_score REAL,

                steam_score REAL,
                reversal_score REAL,
                volatility_score REAL,

                mapping_status TEXT,
                match_method TEXT,
                match_confidence REAL,

                source_count INTEGER
                    NOT NULL DEFAULT 0,

                data_completeness_score REAL
                    NOT NULL DEFAULT 0,

                data_confidence TEXT
                    NOT NULL DEFAULT 'LOW',

                live_penalty REAL
                    NOT NULL DEFAULT 0,

                inactive_penalty REAL
                    NOT NULL DEFAULT 0,

                conflict_penalty REAL
                    NOT NULL DEFAULT 0,

                chase_penalty REAL
                    NOT NULL DEFAULT 0,

                reversal_penalty REAL
                    NOT NULL DEFAULT 0,

                weakening_penalty REAL
                    NOT NULL DEFAULT 0,

                low_sample_penalty REAL
                    NOT NULL DEFAULT 0,

                mapping_penalty REAL
                    NOT NULL DEFAULT 0,

                total_penalty REAL
                    NOT NULL DEFAULT 0,

                positive_signals_json TEXT,
                negative_signals_json TEXT,
                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `signal_fusion_wallets`

- Row count: `179`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | fusion_wallet_key | TEXT | False | — | 1 |
| 1 | opportunity_key | TEXT | True | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | wallet_current_value | REAL | True | 0 | 0 |
| 4 | wallet_share_of_signal | REAL | True | 0 | 0 |
| 5 | dna_score | REAL | True | 50 | 0 |
| 6 | dna_grade | TEXT | True | 'UNRATED' | 0 |
| 7 | primary_archetype | TEXT | False | — | 0 |
| 8 | primary_category | TEXT | False | — | 0 |
| 9 | primary_category_share | REAL | True | 0 | 0 |
| 10 | sports_specialty | TEXT | False | — | 0 |
| 11 | market_type_specialty | TEXT | False | — | 0 |
| 12 | performance_score | REAL | True | 50 | 0 |
| 13 | performance_grade | TEXT | True | 'UNRATED' | 0 |
| 14 | resolved_positions | INTEGER | True | 0 | 0 |
| 15 | win_rate | REAL | True | 0 | 0 |
| 16 | estimated_roi | REAL | True | 0 | 0 |
| 17 | portfolio_independence_score | REAL | True | 50 | 0 |
| 18 | specialist_match | INTEGER | True | 0 | 0 |
| 19 | elite_wallet | INTEGER | True | 0 | 0 |
| 20 | contribution_score | REAL | True | 0 | 0 |
| 21 | calculated_at | TEXT | True | — | 0 |
| 22 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| opportunity_key | signal_fusion_scores | opportunity_key | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_signal_fusion_wallets_wallet | False | c | False | wallet, opportunity_key |
| idx_signal_fusion_wallets_opportunity | False | c | False | opportunity_key, contribution_score |
| sqlite_autoindex_signal_fusion_wallets_1 | True | pk | False | fusion_wallet_key |

#### Source References

- `src/signal_fusion_engine.py:422,490,497,2991,3008,3590`

#### Create SQL

```sql
CREATE TABLE signal_fusion_wallets (
                fusion_wallet_key TEXT PRIMARY KEY,

                opportunity_key TEXT NOT NULL,
                wallet TEXT NOT NULL,

                wallet_current_value REAL
                    NOT NULL DEFAULT 0,

                wallet_share_of_signal REAL
                    NOT NULL DEFAULT 0,

                dna_score REAL
                    NOT NULL DEFAULT 50,

                dna_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                primary_archetype TEXT,

                primary_category TEXT,
                primary_category_share REAL
                    NOT NULL DEFAULT 0,

                sports_specialty TEXT,
                market_type_specialty TEXT,

                performance_score REAL
                    NOT NULL DEFAULT 50,

                performance_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                resolved_positions INTEGER
                    NOT NULL DEFAULT 0,

                win_rate REAL
                    NOT NULL DEFAULT 0,

                estimated_roi REAL
                    NOT NULL DEFAULT 0,

                portfolio_independence_score REAL
                    NOT NULL DEFAULT 50,

                specialist_match INTEGER
                    NOT NULL DEFAULT 0,

                elite_wallet INTEGER
                    NOT NULL DEFAULT 0,

                contribution_score REAL
                    NOT NULL DEFAULT 0,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(
                    opportunity_key
                )
                REFERENCES signal_fusion_scores(
                    opportunity_key
                )
                ON DELETE CASCADE
            )
```

### `smart_money_flow_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | lookback_hours | INTEGER | True | — | 0 |
| 5 | current_snapshot_at | TEXT | False | — | 0 |
| 6 | previous_snapshot_at | TEXT | False | — | 0 |
| 7 | current_markets_loaded | INTEGER | True | 0 | 0 |
| 8 | previous_markets_loaded | INTEGER | True | 0 | 0 |
| 9 | signals_saved | INTEGER | True | 0 | 0 |
| 10 | wallet_events_saved | INTEGER | True | 0 | 0 |
| 11 | actionable_signals | INTEGER | True | 0 | 0 |
| 12 | status | TEXT | True | — | 0 |
| 13 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/smart_money_flow_engine.py:487,2121,2166,2591`

#### Create SQL

```sql
CREATE TABLE smart_money_flow_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                lookback_hours INTEGER NOT NULL,

                current_snapshot_at TEXT,
                previous_snapshot_at TEXT,

                current_markets_loaded INTEGER
                    NOT NULL DEFAULT 0,

                previous_markets_loaded INTEGER
                    NOT NULL DEFAULT 0,

                signals_saved INTEGER
                    NOT NULL DEFAULT 0,

                wallet_events_saved INTEGER
                    NOT NULL DEFAULT 0,

                actionable_signals INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `smart_money_flow_signals`

- Row count: `38`
- Referenced by: `smart_money_flow_wallet_events`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | signal_key | TEXT | False | — | 1 |
| 1 | condition_id | TEXT | True | — | 0 |
| 2 | market_id | TEXT | False | — | 0 |
| 3 | event_id | TEXT | False | — | 0 |
| 4 | title | TEXT | False | — | 0 |
| 5 | slug | TEXT | False | — | 0 |
| 6 | event_slug | TEXT | False | — | 0 |
| 7 | category | TEXT | False | — | 0 |
| 8 | lookback_hours | INTEGER | True | — | 0 |
| 9 | current_snapshot_key | TEXT | True | — | 0 |
| 10 | previous_snapshot_key | TEXT | False | — | 0 |
| 11 | current_snapshot_at | TEXT | True | — | 0 |
| 12 | previous_snapshot_at | TEXT | False | — | 0 |
| 13 | elapsed_hours | REAL | False | — | 0 |
| 14 | current_trade_count | INTEGER | True | 0 | 0 |
| 15 | previous_trade_count | INTEGER | True | 0 | 0 |
| 16 | trade_count_change | INTEGER | True | 0 | 0 |
| 17 | current_unique_wallet_count | INTEGER | True | 0 | 0 |
| 18 | previous_unique_wallet_count | INTEGER | True | 0 | 0 |
| 19 | wallet_count_change | INTEGER | True | 0 | 0 |
| 20 | new_wallet_count | INTEGER | True | 0 | 0 |
| 21 | exited_wallet_count | INTEGER | True | 0 | 0 |
| 22 | persistent_wallet_count | INTEGER | True | 0 | 0 |
| 23 | bullish_wallet_count | INTEGER | True | 0 | 0 |
| 24 | bearish_wallet_count | INTEGER | True | 0 | 0 |
| 25 | current_buy_notional | REAL | True | 0 | 0 |
| 26 | current_sell_notional | REAL | True | 0 | 0 |
| 27 | current_net_flow | REAL | True | 0 | 0 |
| 28 | previous_net_flow | REAL | True | 0 | 0 |
| 29 | net_flow_change | REAL | True | 0 | 0 |
| 30 | current_gross_flow | REAL | True | 0 | 0 |
| 31 | previous_gross_flow | REAL | True | 0 | 0 |
| 32 | gross_flow_change | REAL | True | 0 | 0 |
| 33 | net_flow_velocity | REAL | True | 0 | 0 |
| 34 | gross_flow_velocity | REAL | True | 0 | 0 |
| 35 | flow_acceleration | REAL | True | 0 | 0 |
| 36 | buy_sell_imbalance | REAL | True | 0 | 0 |
| 37 | trusted_buy_notional | REAL | True | 0 | 0 |
| 38 | trusted_sell_notional | REAL | True | 0 | 0 |
| 39 | trusted_net_flow | REAL | True | 0 | 0 |
| 40 | elite_net_flow | REAL | True | 0 | 0 |
| 41 | qualified_net_flow | REAL | True | 0 | 0 |
| 42 | watchlist_net_flow | REAL | True | 0 | 0 |
| 43 | largest_buyer_wallet | TEXT | False | — | 0 |
| 44 | largest_buyer_notional | REAL | True | 0 | 0 |
| 45 | largest_seller_wallet | TEXT | False | — | 0 |
| 46 | largest_seller_notional | REAL | True | 0 | 0 |
| 47 | whale_concentration | REAL | True | 0 | 0 |
| 48 | consensus_strength | REAL | True | 0 | 0 |
| 49 | concentration_risk | REAL | True | 0 | 0 |
| 50 | persistence_score | REAL | True | 0 | 0 |
| 51 | breadth_score | REAL | True | 0 | 0 |
| 52 | velocity_score | REAL | True | 0 | 0 |
| 53 | acceleration_score | REAL | True | 0 | 0 |
| 54 | imbalance_score | REAL | True | 0 | 0 |
| 55 | trusted_flow_score | REAL | True | 0 | 0 |
| 56 | accumulation_score | REAL | True | 0 | 0 |
| 57 | distribution_score | REAL | True | 0 | 0 |
| 58 | rotation_score | REAL | True | 0 | 0 |
| 59 | smart_money_flow_score | REAL | True | 0 | 0 |
| 60 | smart_money_flow_grade | TEXT | True | 'PASS' | 0 |
| 61 | flow_direction | TEXT | True | 'NEUTRAL' | 0 |
| 62 | recommended_action | TEXT | True | 'IGNORE' | 0 |
| 63 | data_confidence | TEXT | True | 'LOW' | 0 |
| 64 | is_actionable | INTEGER | True | 0 | 0 |
| 65 | resolved | INTEGER | True | 0 | 0 |
| 66 | winning_outcome | TEXT | False | — | 0 |
| 67 | positive_evidence_json | TEXT | False | — | 0 |
| 68 | risk_flags_json | TEXT | False | — | 0 |
| 69 | metadata_json | TEXT | False | — | 0 |
| 70 | observed_at | TEXT | True | — | 0 |
| 71 | created_at | TEXT | True | — | 0 |
| 72 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_smart_money_flow_condition | False | c | False | condition_id, lookback_hours, observed_at |
| idx_smart_money_flow_score | False | c | False | smart_money_flow_score, observed_at |
| sqlite_autoindex_smart_money_flow_signals_1 | True | pk | False | signal_key |

#### Source References

- `src/architecture_registry.py:452`
- `src/condition_id_lineage_audit.py:31`
- `src/historical_market_reconciliation_engine.py:32`
- `src/market_identifier_registry_engine.py:1037`
- `src/market_identity_enrichment_engine.py:371`
- `src/opportunity_ranking_engine.py:366,712,724`
- `src/prediction_engine.py:187,419,431`
- `src/registry_validation_gate.py:38`
- `src/smart_money_flow_engine.py:236,423,430,475,2060,2581`

#### Create SQL

```sql
CREATE TABLE smart_money_flow_signals (
                signal_key TEXT PRIMARY KEY,

                condition_id TEXT NOT NULL,
                market_id TEXT,
                event_id TEXT,

                title TEXT,
                slug TEXT,
                event_slug TEXT,
                category TEXT,

                lookback_hours INTEGER NOT NULL,

                current_snapshot_key TEXT NOT NULL,
                previous_snapshot_key TEXT,

                current_snapshot_at TEXT NOT NULL,
                previous_snapshot_at TEXT,

                elapsed_hours REAL,

                current_trade_count INTEGER
                    NOT NULL DEFAULT 0,

                previous_trade_count INTEGER
                    NOT NULL DEFAULT 0,

                trade_count_change INTEGER
                    NOT NULL DEFAULT 0,

                current_unique_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                previous_unique_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                wallet_count_change INTEGER
                    NOT NULL DEFAULT 0,

                new_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                exited_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                persistent_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                bullish_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                bearish_wallet_count INTEGER
                    NOT NULL DEFAULT 0,

                current_buy_notional REAL
                    NOT NULL DEFAULT 0,

                current_sell_notional REAL
                    NOT NULL DEFAULT 0,

                current_net_flow REAL
                    NOT NULL DEFAULT 0,

                previous_net_flow REAL
                    NOT NULL DEFAULT 0,

                net_flow_change REAL
                    NOT NULL DEFAULT 0,

                current_gross_flow REAL
                    NOT NULL DEFAULT 0,

                previous_gross_flow REAL
                    NOT NULL DEFAULT 0,

                gross_flow_change REAL
                    NOT NULL DEFAULT 0,

                net_flow_velocity REAL
                    NOT NULL DEFAULT 0,

                gross_flow_velocity REAL
                    NOT NULL DEFAULT 0,

                flow_acceleration REAL
                    NOT NULL DEFAULT 0,

                buy_sell_imbalance REAL
                    NOT NULL DEFAULT 0,

                trusted_buy_notional REAL
                    NOT NULL DEFAULT 0,

                trusted_sell_notional REAL
                    NOT NULL DEFAULT 0,

                trusted_net_flow REAL
                    NOT NULL DEFAULT 0,

                elite_net_flow REAL
                    NOT NULL DEFAULT 0,

                qualified_net_flow REAL
                    NOT NULL DEFAULT 0,

                watchlist_net_flow REAL
                    NOT NULL DEFAULT 0,

                largest_buyer_wallet TEXT,
                largest_buyer_notional REAL
                    NOT NULL DEFAULT 0,

                largest_seller_wallet TEXT,
                largest_seller_notional REAL
                    NOT NULL DEFAULT 0,

                whale_concentration REAL
                    NOT NULL DEFAULT 0,

                consensus_strength REAL
                    NOT NULL DEFAULT 0,

                concentration_risk REAL
                    NOT NULL DEFAULT 0,

                persistence_score REAL
                    NOT NULL DEFAULT 0,

                breadth_score REAL
                    NOT NULL DEFAULT 0,

                velocity_score REAL
                    NOT NULL DEFAULT 0,

                acceleration_score REAL
                    NOT NULL DEFAULT 0,

                imbalance_score REAL
                    NOT NULL DEFAULT 0,

                trusted_flow_score REAL
                    NOT NULL DEFAULT 0,

                accumulation_score REAL
                    NOT NULL DEFAULT 0,

                distribution_score REAL
                    NOT NULL DEFAULT 0,

                rotation_score REAL
                    NOT NULL DEFAULT 0,

                smart_money_flow_score REAL
                    NOT NULL DEFAULT 0,

                smart_money_flow_grade TEXT
                    NOT NULL DEFAULT 'PASS',

                flow_direction TEXT
                    NOT NULL DEFAULT 'NEUTRAL',

                recommended_action TEXT
                    NOT NULL DEFAULT 'IGNORE',

                data_confidence TEXT
                    NOT NULL DEFAULT 'LOW',

                is_actionable INTEGER
                    NOT NULL DEFAULT 0,

                resolved INTEGER
                    NOT NULL DEFAULT 0,

                winning_outcome TEXT,

                positive_evidence_json TEXT,
                risk_flags_json TEXT,
                metadata_json TEXT,

                observed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `smart_money_flow_wallet_events`

- Row count: `89`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | event_key | TEXT | False | — | 1 |
| 1 | signal_key | TEXT | True | — | 0 |
| 2 | condition_id | TEXT | True | — | 0 |
| 3 | wallet | TEXT | True | — | 0 |
| 4 | event_type | TEXT | True | — | 0 |
| 5 | previous_direction | TEXT | False | — | 0 |
| 6 | current_direction | TEXT | False | — | 0 |
| 7 | previous_net_flow | REAL | True | 0 | 0 |
| 8 | current_net_flow | REAL | True | 0 | 0 |
| 9 | net_flow_change | REAL | True | 0 | 0 |
| 10 | wallet_status | TEXT | False | — | 0 |
| 11 | elite_tier | TEXT | False | — | 0 |
| 12 | consensus_weight | REAL | True | 0 | 0 |
| 13 | prediction_weight | REAL | True | 0 | 0 |
| 14 | wallet_influence_score | REAL | True | 0 | 0 |
| 15 | first_trade_timestamp | INTEGER | False | — | 0 |
| 16 | last_trade_timestamp | INTEGER | False | — | 0 |
| 17 | created_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| signal_key | smart_money_flow_signals | signal_key | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_smart_money_flow_wallet_events_market | False | c | False | condition_id, event_type, net_flow_change |
| sqlite_autoindex_smart_money_flow_wallet_events_1 | True | pk | False | event_key |

#### Source References

- `src/smart_money_flow_engine.py:436,481,2065,2586`

#### Create SQL

```sql
CREATE TABLE smart_money_flow_wallet_events (
                event_key TEXT PRIMARY KEY,

                signal_key TEXT NOT NULL,
                condition_id TEXT NOT NULL,
                wallet TEXT NOT NULL,

                event_type TEXT NOT NULL,

                previous_direction TEXT,
                current_direction TEXT,

                previous_net_flow REAL
                    NOT NULL DEFAULT 0,

                current_net_flow REAL
                    NOT NULL DEFAULT 0,

                net_flow_change REAL
                    NOT NULL DEFAULT 0,

                wallet_status TEXT,
                elite_tier TEXT,

                consensus_weight REAL
                    NOT NULL DEFAULT 0,

                prediction_weight REAL
                    NOT NULL DEFAULT 0,

                wallet_influence_score REAL
                    NOT NULL DEFAULT 0,

                first_trade_timestamp INTEGER,
                last_trade_timestamp INTEGER,

                created_at TEXT NOT NULL,

                FOREIGN KEY(signal_key)
                    REFERENCES smart_money_flow_signals(signal_key)
                    ON DELETE CASCADE
            )
```

### `tracked_markets`

- Row count: `102`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | market_id | TEXT | False | — | 1 |
| 1 | title | TEXT | True | — | 0 |
| 2 | outcome | TEXT | False | — | 0 |
| 3 | priority | INTEGER | True | 5 | 0 |
| 4 | monitor_wallets | INTEGER | True | 1 | 0 |
| 5 | monitor_status | INTEGER | True | 1 | 0 |
| 6 | monitor_price | INTEGER | True | 1 | 0 |
| 7 | monitor_resolution | INTEGER | True | 1 | 0 |
| 8 | enabled | INTEGER | True | 1 | 0 |
| 9 | source | TEXT | True | 'AUTO' | 0 |
| 10 | added_at | TEXT | True | — | 0 |
| 11 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| market_id | market_metadata | market_id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_tracked_markets_enabled | False | c | False | enabled, priority |
| sqlite_autoindex_tracked_markets_1 | True | pk | False | market_id |

#### Source References

- `src/dashboard_schema_audit.py:27`
- `src/market_mapper_engine.py:24`
- `src/market_monitor_database.py:385,423,585`
- `src/market_status_engine.py:1296`

#### Create SQL

```sql
CREATE TABLE tracked_markets (
            market_id TEXT PRIMARY KEY,

            title TEXT NOT NULL,
            outcome TEXT,

            priority INTEGER NOT NULL DEFAULT 5,

            monitor_wallets INTEGER
                NOT NULL DEFAULT 1,

            monitor_status INTEGER
                NOT NULL DEFAULT 1,

            monitor_price INTEGER
                NOT NULL DEFAULT 1,

            monitor_resolution INTEGER
                NOT NULL DEFAULT 1,

            enabled INTEGER NOT NULL DEFAULT 1,

            source TEXT NOT NULL DEFAULT 'AUTO',

            added_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            FOREIGN KEY (market_id)
                REFERENCES market_metadata(market_id)
                ON DELETE CASCADE
        )
```

### `tracked_wallets`

- Row count: `26`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | nickname | TEXT | False | — | 0 |
| 3 | category | TEXT | False | — | 0 |
| 4 | notes | TEXT | False | — | 0 |
| 5 | active | INTEGER | True | 1 | 0 |
| 6 | created_at | TEXT | True | — | 0 |
| 7 | updated_at | TEXT | True | — | 0 |
| 8 | last_scanned_at | TEXT | False | — | 0 |
| 9 | last_scan_status | TEXT | False | — | 0 |
| 10 | last_error | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_tracked_wallets_category | False | c | False | category |
| idx_tracked_wallets_active | False | c | False | active |
| sqlite_autoindex_tracked_wallets_1 | True | u | False | wallet |

#### Source References

- `src/database.py:87,109,164,171,227,238,239,240,258,301,324,359,401,438`
- `src/wallet_tracker.py:315,321,325,339,346,407`

#### Create SQL

```sql
CREATE TABLE tracked_wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL COLLATE NOCASE UNIQUE,
                nickname TEXT,
                category TEXT,
                notes TEXT,
                active INTEGER NOT NULL DEFAULT 1
                    CHECK (active IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_scanned_at TEXT,
                last_scan_status TEXT,
                last_error TEXT
            )
```

### `wallet_activity`

- Row count: `1148`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | scan_id | INTEGER | False | — | 0 |
| 3 | previous_scan_id | INTEGER | False | — | 0 |
| 4 | market_id | TEXT | False | — | 0 |
| 5 | title | TEXT | True | — | 0 |
| 6 | outcome | TEXT | False | — | 0 |
| 7 | activity_type | TEXT | True | — | 0 |
| 8 | previous_shares | REAL | True | 0 | 0 |
| 9 | current_shares | REAL | True | 0 | 0 |
| 10 | share_change | REAL | True | 0 | 0 |
| 11 | previous_value | REAL | True | 0 | 0 |
| 12 | current_value | REAL | True | 0 | 0 |
| 13 | value_change | REAL | True | 0 | 0 |
| 14 | previous_price | REAL | True | 0 | 0 |
| 15 | current_price | REAL | True | 0 | 0 |
| 16 | price_change | REAL | True | 0 | 0 |
| 17 | detected_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| previous_scan_id | wallet_scans | id | NO ACTION | NO ACTION | NONE |
| scan_id | wallet_scans | id | NO ACTION | NO ACTION | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_activity_unique_change | True | c | False | wallet, scan_id, market_id, outcome, activity_type |
| idx_wallet_activity_detected_at | False | c | False | detected_at |
| idx_wallet_activity_type | False | c | False | activity_type |
| idx_wallet_activity_market | False | c | False | market_id |
| idx_wallet_activity_wallet | False | c | False | wallet |

#### Source References

- `src/intelligence_database.py:172,212,220,228,236,244,626`
- `src/pages/5_Wallet_Intelligence.py:231,254`
- `src/wallet_intelligence_engine.py:578,652,1621`

#### Create SQL

```sql
CREATE TABLE wallet_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            wallet TEXT NOT NULL,
            scan_id INTEGER,
            previous_scan_id INTEGER,

            market_id TEXT,
            title TEXT NOT NULL,
            outcome TEXT,

            activity_type TEXT NOT NULL,

            previous_shares REAL NOT NULL DEFAULT 0,
            current_shares REAL NOT NULL DEFAULT 0,
            share_change REAL NOT NULL DEFAULT 0,

            previous_value REAL NOT NULL DEFAULT 0,
            current_value REAL NOT NULL DEFAULT 0,
            value_change REAL NOT NULL DEFAULT 0,

            previous_price REAL NOT NULL DEFAULT 0,
            current_price REAL NOT NULL DEFAULT 0,
            price_change REAL NOT NULL DEFAULT 0,

            detected_at TEXT NOT NULL,

            FOREIGN KEY (scan_id)
                REFERENCES wallet_scans(id),

            FOREIGN KEY (previous_scan_id)
                REFERENCES wallet_scans(id)
        )
```

### `wallet_activity_checkpoints`

- Row count: `10`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | last_activity_timestamp | INTEGER | True | 0 | 0 |
| 2 | last_trade_timestamp | INTEGER | True | 0 | 0 |
| 3 | activity_records | INTEGER | True | 0 | 0 |
| 4 | trade_records | INTEGER | True | 0 | 0 |
| 5 | last_success_at | TEXT | False | — | 0 |
| 6 | last_error_at | TEXT | False | — | 0 |
| 7 | last_error_message | TEXT | False | — | 0 |
| 8 | updated_at | TEXT | True | — | 0 |
| 9 | oldest_activity_timestamp | INTEGER | True | 0 | 0 |
| 10 | oldest_trade_timestamp | INTEGER | True | 0 | 0 |
| 11 | activity_complete | INTEGER | True | 0 | 0 |
| 12 | trades_complete | INTEGER | True | 0 | 0 |
| 13 | activity_truncated | INTEGER | True | 0 | 0 |
| 14 | trades_truncated | INTEGER | True | 0 | 0 |
| 15 | activity_windows | INTEGER | True | 0 | 0 |
| 16 | activity_pages | INTEGER | True | 0 | 0 |
| 17 | trade_pages | INTEGER | True | 0 | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_wallet_activity_checkpoints_1 | True | pk | False | wallet |

#### Source References

- `src/official_api_validator.py:514`
- `src/official_wallet_activity_engine.py:178,597,742,755`
- `src/official_wallet_activity_engine_v2.py:296,370,944,1344,1704`

#### Create SQL

```sql
CREATE TABLE wallet_activity_checkpoints (
                wallet TEXT PRIMARY KEY,
                last_activity_timestamp INTEGER NOT NULL DEFAULT 0,
                last_trade_timestamp INTEGER NOT NULL DEFAULT 0,
                activity_records INTEGER NOT NULL DEFAULT 0,
                trade_records INTEGER NOT NULL DEFAULT 0,
                last_success_at TEXT,
                last_error_at TEXT,
                last_error_message TEXT,
                updated_at TEXT NOT NULL
            , "oldest_activity_timestamp" INTEGER NOT NULL DEFAULT 0, "oldest_trade_timestamp" INTEGER NOT NULL DEFAULT 0, "activity_complete" INTEGER NOT NULL DEFAULT 0, "trades_complete" INTEGER NOT NULL DEFAULT 0, "activity_truncated" INTEGER NOT NULL DEFAULT 0, "trades_truncated" INTEGER NOT NULL DEFAULT 0, "activity_windows" INTEGER NOT NULL DEFAULT 0, "activity_pages" INTEGER NOT NULL DEFAULT 0, "trade_pages" INTEGER NOT NULL DEFAULT 0)
```

### `wallet_activity_errors`

- Row count: `9`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | INTEGER | False | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | endpoint | TEXT | True | — | 0 |
| 4 | error_type | TEXT | True | — | 0 |
| 5 | error_message | TEXT | True | — | 0 |
| 6 | created_at | TEXT | True | — | 0 |
| 7 | requested_offset | INTEGER | False | — | 0 |
| 8 | requested_start | INTEGER | False | — | 0 |
| 9 | requested_end | INTEGER | False | — | 0 |
| 10 | http_status | INTEGER | False | — | 0 |
| 11 | response_body_preview | TEXT | False | — | 0 |
| 12 | terminal_page | INTEGER | True | 0 | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_activity_errors_wallet | False | c | False | wallet, created_at |

#### Source References

- `src/official_wallet_activity_engine.py:190,201,644`
- `src/official_wallet_activity_engine_v2.py:317,335,399,1520`

#### Create SQL

```sql
CREATE TABLE wallet_activity_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                wallet TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                created_at TEXT NOT NULL
            , "requested_offset" INTEGER, "requested_start" INTEGER, "requested_end" INTEGER, "http_status" INTEGER, "response_body_preview" TEXT, "terminal_page" INTEGER NOT NULL DEFAULT 0)
```

### `wallet_activity_ingestion_runs`

- Row count: `2`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | wallets_selected | INTEGER | True | 0 | 0 |
| 5 | wallets_succeeded | INTEGER | True | 0 | 0 |
| 6 | wallets_failed | INTEGER | True | 0 | 0 |
| 7 | activity_rows_received | INTEGER | True | 0 | 0 |
| 8 | activity_rows_inserted | INTEGER | True | 0 | 0 |
| 9 | trade_rows_received | INTEGER | True | 0 | 0 |
| 10 | trade_rows_inserted | INTEGER | True | 0 | 0 |
| 11 | status | TEXT | True | — | 0 |
| 12 | error_message | TEXT | False | — | 0 |
| 13 | engine_version | TEXT | True | '2.0' | 0 |
| 14 | activity_terminal_400s | INTEGER | True | 0 | 0 |
| 15 | trade_terminal_400s | INTEGER | True | 0 | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/official_wallet_activity_engine.py:203,670,700`
- `src/official_wallet_activity_engine_v2.py:340,409,1580,1627`

#### Create SQL

```sql
CREATE TABLE wallet_activity_ingestion_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,
                wallets_selected INTEGER NOT NULL DEFAULT 0,
                wallets_succeeded INTEGER NOT NULL DEFAULT 0,
                wallets_failed INTEGER NOT NULL DEFAULT 0,
                activity_rows_received INTEGER NOT NULL DEFAULT 0,
                activity_rows_inserted INTEGER NOT NULL DEFAULT 0,
                trade_rows_received INTEGER NOT NULL DEFAULT 0,
                trade_rows_inserted INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            , "engine_version" TEXT NOT NULL DEFAULT '2.0', "activity_terminal_400s" INTEGER NOT NULL DEFAULT 0, "trade_terminal_400s" INTEGER NOT NULL DEFAULT 0)
```

### `wallet_activity_snapshots`

- Row count: `1700`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | activity_timestamp | INTEGER | False | — | 0 |
| 4 | condition_id | TEXT | False | — | 0 |
| 5 | activity_type | TEXT | False | — | 0 |
| 6 | size | REAL | True | 0 | 0 |
| 7 | usdc_size | REAL | True | 0 | 0 |
| 8 | transaction_hash | TEXT | False | — | 0 |
| 9 | price | REAL | True | 0 | 0 |
| 10 | asset | TEXT | False | — | 0 |
| 11 | side | TEXT | False | — | 0 |
| 12 | outcome_index | INTEGER | False | — | 0 |
| 13 | title | TEXT | False | — | 0 |
| 14 | slug | TEXT | False | — | 0 |
| 15 | event_slug | TEXT | False | — | 0 |
| 16 | outcome | TEXT | False | — | 0 |
| 17 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| run_id | wallet_profile_collection_runs | run_id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_activity_snapshots_wallet | False | c | False | wallet, activity_timestamp |

#### Source References

- `src/performance_analytics_engine.py:17,51`
- `src/wallet_intelligence_source.py:19`
- `src/wallet_profile_collector.py:34`

#### Create SQL

```sql
CREATE TABLE "wallet_activity_snapshots" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    wallet TEXT NOT NULL,
                    activity_timestamp INTEGER,
                    condition_id TEXT,
                    activity_type TEXT,
                    size REAL NOT NULL DEFAULT 0,
                    usdc_size REAL NOT NULL DEFAULT 0,
                    transaction_hash TEXT,
                    price REAL NOT NULL DEFAULT 0,
                    asset TEXT,
                    side TEXT,
                    outcome_index INTEGER,
                    title TEXT,
                    slug TEXT,
                    event_slug TEXT,
                    outcome TEXT,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES "wallet_profile_collection_runs"(run_id)
                        ON DELETE CASCADE
                )
```

### `wallet_alpha_components`

- Row count: `312`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | component_key | TEXT | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | component_name | TEXT | True | — | 0 |
| 3 | raw_value | REAL | False | — | 0 |
| 4 | normalized_score | REAL | True | 0 | 0 |
| 5 | weight | REAL | True | 0 | 0 |
| 6 | weighted_contribution | REAL | True | 0 | 0 |
| 7 | explanation | TEXT | False | — | 0 |
| 8 | calculated_at | TEXT | True | — | 0 |
| 9 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| wallet | wallet_alpha_profiles | wallet | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_alpha_components_wallet | False | c | False | wallet, weighted_contribution |
| sqlite_autoindex_wallet_alpha_components_1 | True | pk | False | component_key |

#### Source References

- `src/wallet_alpha_engine.py:342,374,1632,1645,2079`

#### Create SQL

```sql
CREATE TABLE wallet_alpha_components (
                component_key TEXT PRIMARY KEY,

                wallet TEXT NOT NULL,
                component_name TEXT NOT NULL,

                raw_value REAL,
                normalized_score REAL
                    NOT NULL DEFAULT 0,

                weight REAL
                    NOT NULL DEFAULT 0,

                weighted_contribution REAL
                    NOT NULL DEFAULT 0,

                explanation TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(
                    wallet
                )
                REFERENCES wallet_alpha_profiles(
                    wallet
                )
                ON DELETE CASCADE
            )
```

### `wallet_alpha_history`

- Row count: `26`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | alpha_score | REAL | False | — | 0 |
| 3 | alpha_grade | TEXT | False | — | 0 |
| 4 | data_confidence | TEXT | False | — | 0 |
| 5 | realized_roi | REAL | False | — | 0 |
| 6 | total_roi | REAL | False | — | 0 |
| 7 | performance_score | REAL | False | — | 0 |
| 8 | dna_score | REAL | False | — | 0 |
| 9 | timing_score | REAL | False | — | 0 |
| 10 | entry_quality_score | REAL | False | — | 0 |
| 11 | exit_quality_score | REAL | False | — | 0 |
| 12 | risk_adjusted_score | REAL | False | — | 0 |
| 13 | ledger_quality_score | REAL | False | — | 0 |
| 14 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_alpha_history_wallet | False | c | False | wallet, observed_at |

#### Source References

- `src/wallet_alpha_engine.py:379,403,1661,2084`

#### Create SQL

```sql
CREATE TABLE wallet_alpha_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                wallet TEXT NOT NULL,

                alpha_score REAL,
                alpha_grade TEXT,
                data_confidence TEXT,

                realized_roi REAL,
                total_roi REAL,
                performance_score REAL,
                dna_score REAL,
                timing_score REAL,
                entry_quality_score REAL,
                exit_quality_score REAL,
                risk_adjusted_score REAL,
                ledger_quality_score REAL,

                observed_at TEXT NOT NULL
            )
```

### `wallet_alpha_profiles`

- Row count: `26`
- Referenced by: `wallet_alpha_components`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | alpha_score | REAL | True | 0 | 0 |
| 2 | alpha_grade | TEXT | True | 'UNRATED' | 0 |
| 3 | data_confidence | TEXT | True | 'VERY LOW' | 0 |
| 4 | trade_event_count | INTEGER | True | 0 | 0 |
| 5 | reconstructed_position_count | INTEGER | True | 0 | 0 |
| 6 | closed_position_count | INTEGER | True | 0 | 0 |
| 7 | open_position_count | INTEGER | True | 0 | 0 |
| 8 | estimated_realized_pnl | REAL | True | 0 | 0 |
| 9 | estimated_unrealized_pnl | REAL | True | 0 | 0 |
| 10 | total_estimated_pnl | REAL | True | 0 | 0 |
| 11 | estimated_buy_cost | REAL | True | 0 | 0 |
| 12 | estimated_sell_proceeds | REAL | True | 0 | 0 |
| 13 | realized_roi | REAL | True | 0 | 0 |
| 14 | total_roi | REAL | True | 0 | 0 |
| 15 | win_rate | REAL | True | 0 | 0 |
| 16 | resolved_positions | INTEGER | True | 0 | 0 |
| 17 | performance_score | REAL | True | 50 | 0 |
| 18 | dna_score | REAL | True | 50 | 0 |
| 19 | consistency_score | REAL | True | 0 | 0 |
| 20 | calibration_score | REAL | True | 0 | 0 |
| 21 | timing_score | REAL | True | 50 | 0 |
| 22 | entry_quality_score | REAL | True | 50 | 0 |
| 23 | exit_quality_score | REAL | True | 50 | 0 |
| 24 | position_management_score | REAL | True | 50 | 0 |
| 25 | conviction_quality_score | REAL | True | 50 | 0 |
| 26 | risk_adjusted_score | REAL | True | 50 | 0 |
| 27 | drawdown_control_score | REAL | True | 50 | 0 |
| 28 | scale_in_quality_score | REAL | True | 50 | 0 |
| 29 | scale_out_quality_score | REAL | True | 50 | 0 |
| 30 | specialization_bonus | REAL | True | 0 | 0 |
| 31 | independence_bonus | REAL | True | 0 | 0 |
| 32 | ledger_quality_score | REAL | True | 0 | 0 |
| 33 | sample_size_score | REAL | True | 0 | 0 |
| 34 | negative_pnl_penalty | REAL | True | 0 | 0 |
| 35 | low_sample_penalty | REAL | True | 0 | 0 |
| 36 | incomplete_ledger_penalty | REAL | True | 0 | 0 |
| 37 | total_penalty | REAL | True | 0 | 0 |
| 38 | primary_archetype | TEXT | False | — | 0 |
| 39 | primary_category | TEXT | False | — | 0 |
| 40 | sports_specialty | TEXT | False | — | 0 |
| 41 | market_type_specialty | TEXT | False | — | 0 |
| 42 | alpha_label | TEXT | False | — | 0 |
| 43 | strengths_json | TEXT | False | — | 0 |
| 44 | risks_json | TEXT | False | — | 0 |
| 45 | explanation_json | TEXT | False | — | 0 |
| 46 | calculated_at | TEXT | True | — | 0 |
| 47 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_alpha_profiles_grade | False | c | False | alpha_grade, alpha_score |
| idx_wallet_alpha_profiles_rank | False | c | False | alpha_score |
| sqlite_autoindex_wallet_alpha_profiles_1 | True | pk | False | wallet |

#### Source References

- `src/candidate_qualification_engine.py:794`
- `src/elite_wallet_ranking_engine.py:637,642`
- `src/wallet_alpha_engine.py:201,331,337,366,1636,1640,2074`

#### Create SQL

```sql
CREATE TABLE wallet_alpha_profiles (
                wallet TEXT PRIMARY KEY,

                alpha_score REAL
                    NOT NULL DEFAULT 0,

                alpha_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                data_confidence TEXT
                    NOT NULL DEFAULT 'VERY LOW',

                trade_event_count INTEGER
                    NOT NULL DEFAULT 0,

                reconstructed_position_count INTEGER
                    NOT NULL DEFAULT 0,

                closed_position_count INTEGER
                    NOT NULL DEFAULT 0,

                open_position_count INTEGER
                    NOT NULL DEFAULT 0,

                estimated_realized_pnl REAL
                    NOT NULL DEFAULT 0,

                estimated_unrealized_pnl REAL
                    NOT NULL DEFAULT 0,

                total_estimated_pnl REAL
                    NOT NULL DEFAULT 0,

                estimated_buy_cost REAL
                    NOT NULL DEFAULT 0,

                estimated_sell_proceeds REAL
                    NOT NULL DEFAULT 0,

                realized_roi REAL
                    NOT NULL DEFAULT 0,

                total_roi REAL
                    NOT NULL DEFAULT 0,

                win_rate REAL
                    NOT NULL DEFAULT 0,

                resolved_positions INTEGER
                    NOT NULL DEFAULT 0,

                performance_score REAL
                    NOT NULL DEFAULT 50,

                dna_score REAL
                    NOT NULL DEFAULT 50,

                consistency_score REAL
                    NOT NULL DEFAULT 0,

                calibration_score REAL
                    NOT NULL DEFAULT 0,

                timing_score REAL
                    NOT NULL DEFAULT 50,

                entry_quality_score REAL
                    NOT NULL DEFAULT 50,

                exit_quality_score REAL
                    NOT NULL DEFAULT 50,

                position_management_score REAL
                    NOT NULL DEFAULT 50,

                conviction_quality_score REAL
                    NOT NULL DEFAULT 50,

                risk_adjusted_score REAL
                    NOT NULL DEFAULT 50,

                drawdown_control_score REAL
                    NOT NULL DEFAULT 50,

                scale_in_quality_score REAL
                    NOT NULL DEFAULT 50,

                scale_out_quality_score REAL
                    NOT NULL DEFAULT 50,

                specialization_bonus REAL
                    NOT NULL DEFAULT 0,

                independence_bonus REAL
                    NOT NULL DEFAULT 0,

                ledger_quality_score REAL
                    NOT NULL DEFAULT 0,

                sample_size_score REAL
                    NOT NULL DEFAULT 0,

                negative_pnl_penalty REAL
                    NOT NULL DEFAULT 0,

                low_sample_penalty REAL
                    NOT NULL DEFAULT 0,

                incomplete_ledger_penalty REAL
                    NOT NULL DEFAULT 0,

                total_penalty REAL
                    NOT NULL DEFAULT 0,

                primary_archetype TEXT,
                primary_category TEXT,
                sports_specialty TEXT,
                market_type_specialty TEXT,

                alpha_label TEXT,
                strengths_json TEXT,
                risks_json TEXT,
                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `wallet_alpha_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | wallets_loaded | INTEGER | True | 0 | 0 |
| 5 | profiles_saved | INTEGER | True | 0 | 0 |
| 6 | component_rows_saved | INTEGER | True | 0 | 0 |
| 7 | history_rows_saved | INTEGER | True | 0 | 0 |
| 8 | status | TEXT | True | — | 0 |
| 9 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/wallet_alpha_engine.py:408,1750,1789`

#### Create SQL

```sql
CREATE TABLE wallet_alpha_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                wallets_loaded INTEGER
                    NOT NULL DEFAULT 0,

                profiles_saved INTEGER
                    NOT NULL DEFAULT 0,

                component_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                history_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `wallet_category_performance`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | True | — | 1 |
| 1 | category | TEXT | True | — | 2 |
| 2 | category_score | REAL | True | 0 | 0 |
| 3 | category_grade | TEXT | True | 'UNRATED' | 0 |
| 4 | confidence_score | REAL | True | 0 | 0 |
| 5 | category_rank | INTEGER | False | — | 0 |
| 6 | markets_tracked | INTEGER | True | 0 | 0 |
| 7 | resolved_markets | INTEGER | True | 0 | 0 |
| 8 | wins | INTEGER | True | 0 | 0 |
| 9 | losses | INTEGER | True | 0 | 0 |
| 10 | win_rate | REAL | True | 0 | 0 |
| 11 | realized_pnl | REAL | True | 0 | 0 |
| 12 | total_pnl | REAL | True | 0 | 0 |
| 13 | roi | REAL | True | 0 | 0 |
| 14 | average_position_value | REAL | True | 0 | 0 |
| 15 | average_entry_edge | REAL | True | 0 | 0 |
| 16 | average_holding_hours | REAL | True | 0 | 0 |
| 17 | timing_score | REAL | True | 0 | 0 |
| 18 | consistency_score | REAL | True | 0 | 0 |
| 19 | recent_form_score | REAL | True | 0 | 0 |
| 20 | first_market_at | TEXT | False | — | 0 |
| 21 | last_market_at | TEXT | False | — | 0 |
| 22 | calculated_at | TEXT | False | — | 0 |
| 23 | created_at | TEXT | True | — | 0 |
| 24 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| wallet | wallet_intelligence_profiles | wallet | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_category_wallet | False | c | False | wallet |
| idx_wallet_category_category_score | False | c | False | category, category_score |
| sqlite_autoindex_wallet_category_performance_1 | True | pk | False | wallet, category |

#### Source References

- `src/elite_wallet_intelligence_database.py:77,216,217,365`

#### Create SQL

```sql
CREATE TABLE wallet_category_performance (
        wallet TEXT NOT NULL,
        category TEXT NOT NULL,

        category_score REAL NOT NULL DEFAULT 0,
        category_grade TEXT NOT NULL DEFAULT 'UNRATED',
        confidence_score REAL NOT NULL DEFAULT 0,
        category_rank INTEGER,

        markets_tracked INTEGER NOT NULL DEFAULT 0,
        resolved_markets INTEGER NOT NULL DEFAULT 0,
        wins INTEGER NOT NULL DEFAULT 0,
        losses INTEGER NOT NULL DEFAULT 0,

        win_rate REAL NOT NULL DEFAULT 0,
        realized_pnl REAL NOT NULL DEFAULT 0,
        total_pnl REAL NOT NULL DEFAULT 0,
        roi REAL NOT NULL DEFAULT 0,

        average_position_value REAL NOT NULL DEFAULT 0,
        average_entry_edge REAL NOT NULL DEFAULT 0,
        average_holding_hours REAL NOT NULL DEFAULT 0,
        timing_score REAL NOT NULL DEFAULT 0,
        consistency_score REAL NOT NULL DEFAULT 0,
        recent_form_score REAL NOT NULL DEFAULT 0,

        first_market_at TEXT,
        last_market_at TEXT,
        calculated_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,

        PRIMARY KEY (wallet, category),
        FOREIGN KEY (wallet)
            REFERENCES wallet_intelligence_profiles(wallet)
            ON DELETE CASCADE
    )
```

### `wallet_category_specialties`

- Row count: `48`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | True | — | 1 |
| 1 | category | TEXT | True | — | 2 |
| 2 | appearances | INTEGER | True | 0 | 0 |
| 3 | best_rank | INTEGER | False | — | 0 |
| 4 | pnl_signal | REAL | True | 0 | 0 |
| 5 | volume_signal | REAL | True | 0 | 0 |
| 6 | specialty_score | REAL | True | 0 | 0 |
| 7 | specialty_grade | TEXT | False | — | 0 |
| 8 | last_seen_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| wallet | discovered_wallets | wallet | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_specialties_category | False | c | False | category, specialty_score |
| sqlite_autoindex_wallet_category_specialties_1 | True | pk | False | wallet, category |

#### Source References

- `src/elite_wallet_discovery_engine.py:52`

#### Create SQL

```sql
CREATE TABLE "wallet_category_specialties" (
                    wallet TEXT NOT NULL,
                    category TEXT NOT NULL,
                    appearances INTEGER NOT NULL DEFAULT 0,
                    best_rank INTEGER,
                    pnl_signal REAL NOT NULL DEFAULT 0,
                    volume_signal REAL NOT NULL DEFAULT 0,
                    specialty_score REAL NOT NULL DEFAULT 0,
                    specialty_grade TEXT,
                    last_seen_at TEXT NOT NULL,
                    PRIMARY KEY(wallet, category),
                    FOREIGN KEY(wallet)
                        REFERENCES "discovered_wallets"(wallet)
                        ON DELETE CASCADE
                )
```

### `wallet_closed_position_snapshots`

- Row count: `876`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | asset | TEXT | False | — | 0 |
| 4 | condition_id | TEXT | False | — | 0 |
| 5 | avg_price | REAL | True | 0 | 0 |
| 6 | total_bought | REAL | True | 0 | 0 |
| 7 | realized_pnl | REAL | True | 0 | 0 |
| 8 | current_price | REAL | True | 0 | 0 |
| 9 | closed_timestamp | INTEGER | False | — | 0 |
| 10 | title | TEXT | False | — | 0 |
| 11 | slug | TEXT | False | — | 0 |
| 12 | event_slug | TEXT | False | — | 0 |
| 13 | outcome | TEXT | False | — | 0 |
| 14 | outcome_index | INTEGER | False | — | 0 |
| 15 | opposite_outcome | TEXT | False | — | 0 |
| 16 | opposite_asset | TEXT | False | — | 0 |
| 17 | end_date | TEXT | False | — | 0 |
| 18 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| run_id | wallet_profile_collection_runs | run_id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_closed_positions_wallet | False | c | False | wallet, closed_timestamp |

#### Source References

- `src/performance_analytics_engine.py:15,49`
- `src/wallet_intelligence_source.py:17`
- `src/wallet_profile_collector.py:32`

#### Create SQL

```sql
CREATE TABLE "wallet_closed_position_snapshots" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    wallet TEXT NOT NULL,
                    asset TEXT,
                    condition_id TEXT,
                    avg_price REAL NOT NULL DEFAULT 0,
                    total_bought REAL NOT NULL DEFAULT 0,
                    realized_pnl REAL NOT NULL DEFAULT 0,
                    current_price REAL NOT NULL DEFAULT 0,
                    closed_timestamp INTEGER,
                    title TEXT,
                    slug TEXT,
                    event_slug TEXT,
                    outcome TEXT,
                    outcome_index INTEGER,
                    opposite_outcome TEXT,
                    opposite_asset TEXT,
                    end_date TEXT,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES "wallet_profile_collection_runs"(run_id)
                        ON DELETE CASCADE
                )
```

### `wallet_cluster_members`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | cluster_id | INTEGER | True | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | overlap_score | REAL | True | 0 | 0 |
| 4 | wallet_score | REAL | True | 0 | 0 |
| 5 | cluster_capital_share | REAL | True | 0 | 0 |
| 6 | calculated_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| cluster_id | wallet_clusters | id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_cluster_members_wallet | False | c | False | wallet |
| idx_wallet_cluster_members_cluster | False | c | False | cluster_id |

#### Source References

- `src/intelligence_database.py:307,330,338,628`

#### Create SQL

```sql
CREATE TABLE wallet_cluster_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            cluster_id INTEGER NOT NULL,
            wallet TEXT NOT NULL,

            overlap_score REAL NOT NULL DEFAULT 0,
            wallet_score REAL NOT NULL DEFAULT 0,
            cluster_capital_share REAL NOT NULL DEFAULT 0,

            calculated_at TEXT NOT NULL,

            FOREIGN KEY (cluster_id)
                REFERENCES wallet_clusters(id)
                ON DELETE CASCADE
        )
```

### `wallet_clusters`

- Row count: `0`
- Referenced by: `wallet_cluster_members`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | cluster_key | TEXT | True | — | 0 |
| 2 | cluster_name | TEXT | True | — | 0 |
| 3 | wallet_count | INTEGER | True | 0 | 0 |
| 4 | shared_market_count | INTEGER | True | 0 | 0 |
| 5 | average_overlap_score | REAL | True | 0 | 0 |
| 6 | average_wallet_score | REAL | True | 0 | 0 |
| 7 | combined_current_value | REAL | True | 0 | 0 |
| 8 | dominant_category | TEXT | True | 'Unknown' | 0 |
| 9 | cluster_grade | TEXT | True | 'UNRATED' | 0 |
| 10 | calculated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_clusters_score | False | c | False | average_overlap_score |
| idx_wallet_clusters_key | False | c | False | cluster_key |

#### Source References

- `src/intelligence_database.py:262,287,295,320,627`

#### Create SQL

```sql
CREATE TABLE wallet_clusters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            cluster_key TEXT NOT NULL,
            cluster_name TEXT NOT NULL,

            wallet_count INTEGER NOT NULL DEFAULT 0,
            shared_market_count INTEGER NOT NULL DEFAULT 0,

            average_overlap_score REAL NOT NULL DEFAULT 0,
            average_wallet_score REAL NOT NULL DEFAULT 0,
            combined_current_value REAL NOT NULL DEFAULT 0,

            dominant_category TEXT NOT NULL DEFAULT 'Unknown',
            cluster_grade TEXT NOT NULL DEFAULT 'UNRATED',

            calculated_at TEXT NOT NULL
        )
```

### `wallet_current_position_snapshots`

- Row count: `2310`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | asset | TEXT | False | — | 0 |
| 4 | condition_id | TEXT | False | — | 0 |
| 5 | size | REAL | True | 0 | 0 |
| 6 | avg_price | REAL | True | 0 | 0 |
| 7 | initial_value | REAL | True | 0 | 0 |
| 8 | current_value | REAL | True | 0 | 0 |
| 9 | cash_pnl | REAL | True | 0 | 0 |
| 10 | percent_pnl | REAL | True | 0 | 0 |
| 11 | total_bought | REAL | True | 0 | 0 |
| 12 | realized_pnl | REAL | True | 0 | 0 |
| 13 | percent_realized_pnl | REAL | True | 0 | 0 |
| 14 | current_price | REAL | True | 0 | 0 |
| 15 | redeemable | INTEGER | True | 0 | 0 |
| 16 | mergeable | INTEGER | True | 0 | 0 |
| 17 | title | TEXT | False | — | 0 |
| 18 | slug | TEXT | False | — | 0 |
| 19 | event_slug | TEXT | False | — | 0 |
| 20 | outcome | TEXT | False | — | 0 |
| 21 | outcome_index | INTEGER | False | — | 0 |
| 22 | opposite_outcome | TEXT | False | — | 0 |
| 23 | opposite_asset | TEXT | False | — | 0 |
| 24 | end_date | TEXT | False | — | 0 |
| 25 | negative_risk | INTEGER | True | 0 | 0 |
| 26 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| run_id | wallet_profile_collection_runs | run_id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_current_positions_wallet | False | c | False | wallet, observed_at |

#### Source References

- `src/performance_analytics_engine.py:14,48`
- `src/wallet_intelligence_source.py:16`
- `src/wallet_profile_collector.py:31`

#### Create SQL

```sql
CREATE TABLE "wallet_current_position_snapshots" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    wallet TEXT NOT NULL,
                    asset TEXT,
                    condition_id TEXT,
                    size REAL NOT NULL DEFAULT 0,
                    avg_price REAL NOT NULL DEFAULT 0,
                    initial_value REAL NOT NULL DEFAULT 0,
                    current_value REAL NOT NULL DEFAULT 0,
                    cash_pnl REAL NOT NULL DEFAULT 0,
                    percent_pnl REAL NOT NULL DEFAULT 0,
                    total_bought REAL NOT NULL DEFAULT 0,
                    realized_pnl REAL NOT NULL DEFAULT 0,
                    percent_realized_pnl REAL NOT NULL DEFAULT 0,
                    current_price REAL NOT NULL DEFAULT 0,
                    redeemable INTEGER NOT NULL DEFAULT 0,
                    mergeable INTEGER NOT NULL DEFAULT 0,
                    title TEXT,
                    slug TEXT,
                    event_slug TEXT,
                    outcome TEXT,
                    outcome_index INTEGER,
                    opposite_outcome TEXT,
                    opposite_asset TEXT,
                    end_date TEXT,
                    negative_risk INTEGER NOT NULL DEFAULT 0,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES "wallet_profile_collection_runs"(run_id)
                        ON DELETE CASCADE
                )
```

### `wallet_discovery_events`

- Row count: `4496`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | event_key | TEXT | True | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | event_type | TEXT | True | — | 0 |
| 4 | discovery_source | TEXT | True | — | 0 |
| 5 | snapshot_id | INTEGER | False | — | 0 |
| 6 | previous_status | TEXT | False | — | 0 |
| 7 | resulting_status | TEXT | False | — | 0 |
| 8 | category | TEXT | False | — | 0 |
| 9 | time_period | TEXT | False | — | 0 |
| 10 | order_by | TEXT | False | — | 0 |
| 11 | rank | INTEGER | False | — | 0 |
| 12 | pnl | REAL | False | — | 0 |
| 13 | volume | REAL | False | — | 0 |
| 14 | explanation_json | TEXT | False | — | 0 |
| 15 | discovered_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_wallet_discovery_events_1 | True | u | False | event_key |

#### Source References

- `src/weekly_wallet_discovery.py:221,816,1248`

#### Create SQL

```sql
CREATE TABLE wallet_discovery_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_key TEXT UNIQUE NOT NULL,
                wallet TEXT NOT NULL,
                event_type TEXT NOT NULL,
                discovery_source TEXT NOT NULL,
                snapshot_id INTEGER,
                previous_status TEXT,
                resulting_status TEXT,
                category TEXT,
                time_period TEXT,
                order_by TEXT,
                rank INTEGER,
                pnl REAL,
                volume REAL,
                explanation_json TEXT,
                discovered_at TEXT NOT NULL
            )
```

### `wallet_discovery_runs`

- Row count: `2`
- Referenced by: `wallet_leaderboard_snapshots`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | mode | TEXT | True | — | 0 |
| 4 | categories_scanned | INTEGER | True | 0 | 0 |
| 5 | periods_scanned | INTEGER | True | 0 | 0 |
| 6 | API_queries | INTEGER | True | 0 | 0 |
| 7 | leaderboard_rows | INTEGER | True | 0 | 0 |
| 8 | unique_wallets | INTEGER | True | 0 | 0 |
| 9 | wallet_rows_upserted | INTEGER | True | 0 | 0 |
| 10 | snapshot_rows_inserted | INTEGER | True | 0 | 0 |
| 11 | status | TEXT | True | — | 0 |
| 12 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_wallet_discovery_runs_1 | True | pk | False | run_id |

#### Source References

- `src/elite_wallet_discovery_engine.py:49`
- `src/migrate_wallet_discovery_schema.py:14,171,191`
- `src/weekly_wallet_discovery.py:250,870,913,1250`

#### Create SQL

```sql
CREATE TABLE "wallet_discovery_runs" (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            mode TEXT NOT NULL,
            categories_scanned INTEGER NOT NULL DEFAULT 0,
            periods_scanned INTEGER NOT NULL DEFAULT 0,
            API_queries INTEGER NOT NULL DEFAULT 0,
            leaderboard_rows INTEGER NOT NULL DEFAULT 0,
            unique_wallets INTEGER NOT NULL DEFAULT 0,
            wallet_rows_upserted INTEGER NOT NULL DEFAULT 0,
            snapshot_rows_inserted INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            error_message TEXT
        )
```

### `wallet_discovery_runs_legacy_20260719_050932`

- Row count: `2`
- Referenced by: `wallet_leaderboard_snapshots_backup_20260719_050932`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | board_count | INTEGER | True | 0 | 0 |
| 5 | successful_boards | INTEGER | True | 0 | 0 |
| 6 | failed_boards | INTEGER | True | 0 | 0 |
| 7 | entries_received | INTEGER | True | 0 | 0 |
| 8 | valid_entries | INTEGER | True | 0 | 0 |
| 9 | invalid_entries | INTEGER | True | 0 | 0 |
| 10 | unique_wallets_seen | INTEGER | True | 0 | 0 |
| 11 | new_wallets_added | INTEGER | True | 0 | 0 |
| 12 | existing_wallets_updated | INTEGER | True | 0 | 0 |
| 13 | protected_wallets_preserved | INTEGER | True | 0 | 0 |
| 14 | qualification_candidates | INTEGER | True | 0 | 0 |
| 15 | status | TEXT | True | — | 0 |
| 16 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

No direct table-name references were detected under `src/`.

#### Create SQL

```sql
CREATE TABLE "wallet_discovery_runs_legacy_20260719_050932" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,
                board_count INTEGER NOT NULL DEFAULT 0,
                successful_boards INTEGER NOT NULL DEFAULT 0,
                failed_boards INTEGER NOT NULL DEFAULT 0,
                entries_received INTEGER NOT NULL DEFAULT 0,
                valid_entries INTEGER NOT NULL DEFAULT 0,
                invalid_entries INTEGER NOT NULL DEFAULT 0,
                unique_wallets_seen INTEGER NOT NULL DEFAULT 0,
                new_wallets_added INTEGER NOT NULL DEFAULT 0,
                existing_wallets_updated INTEGER NOT NULL DEFAULT 0,
                protected_wallets_preserved INTEGER NOT NULL DEFAULT 0,
                qualification_candidates INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `wallet_dna_categories`

- Row count: `51`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | category_key | TEXT | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | category | TEXT | True | — | 0 |
| 3 | position_count | INTEGER | True | 0 | 0 |
| 4 | market_count | INTEGER | True | 0 | 0 |
| 5 | current_value | REAL | True | 0 | 0 |
| 6 | portfolio_share | REAL | True | 0 | 0 |
| 7 | specialty_score | REAL | True | 0 | 0 |
| 8 | calculated_at | TEXT | True | — | 0 |
| 9 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| wallet | wallet_dna_profiles_legacy_v1 | wallet | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_dna_categories_wallet | False | c | False | wallet, portfolio_share |
| sqlite_autoindex_wallet_dna_categories_1 | True | pk | False | category_key |

#### Source References

- `src/elite_wallet_ranking_engine.py:513,520`
- `src/wallet_dna_engine_backup.py:365,400,2014,2035,2512`

#### Create SQL

```sql
CREATE TABLE wallet_dna_categories (
                category_key TEXT PRIMARY KEY,

                wallet TEXT NOT NULL,
                category TEXT NOT NULL,

                position_count INTEGER
                    NOT NULL DEFAULT 0,

                market_count INTEGER
                    NOT NULL DEFAULT 0,

                current_value REAL
                    NOT NULL DEFAULT 0,

                portfolio_share REAL
                    NOT NULL DEFAULT 0,

                specialty_score REAL
                    NOT NULL DEFAULT 0,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(
                    wallet
                )
                REFERENCES "wallet_dna_profiles_legacy_v1"(
                    wallet
                )
                ON DELETE CASCADE
            )
```

### `wallet_dna_history`

- Row count: `26`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | dna_score | REAL | False | — | 0 |
| 3 | dna_grade | TEXT | False | — | 0 |
| 4 | data_confidence | TEXT | False | — | 0 |
| 5 | primary_archetype | TEXT | False | — | 0 |
| 6 | secondary_archetype | TEXT | False | — | 0 |
| 7 | primary_category | TEXT | False | — | 0 |
| 8 | primary_category_share | REAL | False | — | 0 |
| 9 | current_value | REAL | False | — | 0 |
| 10 | concentration_score | REAL | False | — | 0 |
| 11 | diversification_score | REAL | False | — | 0 |
| 12 | conviction_score | REAL | False | — | 0 |
| 13 | performance_score | REAL | False | — | 0 |
| 14 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_dna_history_wallet | False | c | False | wallet, observed_at |

#### Source References

- `src/wallet_dna_engine_backup.py:435,461,2058,2522`

#### Create SQL

```sql
CREATE TABLE wallet_dna_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                wallet TEXT NOT NULL,

                dna_score REAL,
                dna_grade TEXT,
                data_confidence TEXT,

                primary_archetype TEXT,
                secondary_archetype TEXT,

                primary_category TEXT,
                primary_category_share REAL,

                current_value REAL,
                concentration_score REAL,
                diversification_score REAL,
                conviction_score REAL,
                performance_score REAL,

                observed_at TEXT NOT NULL
            )
```

### `wallet_dna_market_types`

- Row count: `100`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | market_type_key | TEXT | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | market_type | TEXT | True | — | 0 |
| 3 | position_count | INTEGER | True | 0 | 0 |
| 4 | current_value | REAL | True | 0 | 0 |
| 5 | portfolio_share | REAL | True | 0 | 0 |
| 6 | specialty_score | REAL | True | 0 | 0 |
| 7 | calculated_at | TEXT | True | — | 0 |
| 8 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| wallet | wallet_dna_profiles_legacy_v1 | wallet | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_wallet_dna_market_types_1 | True | pk | False | market_type_key |

#### Source References

- `src/wallet_dna_engine_backup.py:405,2021,2039,2517`

#### Create SQL

```sql
CREATE TABLE wallet_dna_market_types (
                market_type_key TEXT PRIMARY KEY,

                wallet TEXT NOT NULL,
                market_type TEXT NOT NULL,

                position_count INTEGER
                    NOT NULL DEFAULT 0,

                current_value REAL
                    NOT NULL DEFAULT 0,

                portfolio_share REAL
                    NOT NULL DEFAULT 0,

                specialty_score REAL
                    NOT NULL DEFAULT 0,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY(
                    wallet
                )
                REFERENCES "wallet_dna_profiles_legacy_v1"(
                    wallet
                )
                ON DELETE CASCADE
            )
```

### `wallet_dna_profiles`

- Row count: `5`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | username | TEXT | False | — | 0 |
| 2 | calculated_at | TEXT | True | — | 0 |
| 3 | methodology_version | TEXT | True | — | 0 |
| 4 | primary_archetype | TEXT | True | — | 0 |
| 5 | secondary_archetype | TEXT | True | — | 0 |
| 6 | archetype_confidence | REAL | True | 0 | 0 |
| 7 | conviction_score | REAL | True | 0 | 0 |
| 8 | specialization_score | REAL | True | 0 | 0 |
| 9 | activity_intensity_score | REAL | True | 0 | 0 |
| 10 | diversification_score | REAL | True | 0 | 0 |
| 11 | capital_scale_score | REAL | True | 0 | 0 |
| 12 | profitability_quality_score | REAL | True | 0 | 0 |
| 13 | consistency_score | REAL | True | 0 | 0 |
| 14 | risk_control_score | REAL | True | 0 | 0 |
| 15 | evidence_quality_score | REAL | True | 0 | 0 |
| 16 | whale_score | REAL | True | 0 | 0 |
| 17 | specialist_score | REAL | True | 0 | 0 |
| 18 | selective_bettor_score | REAL | True | 0 | 0 |
| 19 | active_trader_score | REAL | True | 0 | 0 |
| 20 | diversified_portfolio_score | REAL | True | 0 | 0 |
| 21 | aggressive_risk_taker_score | REAL | True | 0 | 0 |
| 22 | disciplined_operator_score | REAL | True | 0 | 0 |
| 23 | high_frequency_score | REAL | True | 0 | 0 |
| 24 | dna_score | REAL | True | 0 | 0 |
| 25 | dna_grade | TEXT | True | 'UNRATED' | 0 |
| 26 | trust_tier | TEXT | True | 'UNRATED' | 0 |
| 27 | follow_priority | TEXT | True | 'WATCH' | 0 |
| 28 | consensus_weight | REAL | True | 0 | 0 |
| 29 | sample_limited | INTEGER | True | 1 | 0 |
| 30 | warning_flags | TEXT | True | '[]' | 0 |
| 31 | explanation | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_dna_archetype | False | c | False | primary_archetype, dna_score |
| idx_wallet_dna_score | False | c | False | dna_score, consensus_weight |
| sqlite_autoindex_wallet_dna_profiles_1 | True | pk | False | wallet |

#### Source References

- `src/candidate_qualification_engine.py:806`
- `src/elite_wallet_ranking_engine.py:651`
- `src/signal_fusion_engine.py:658,665`
- `src/wallet_alpha_engine.py:825`
- `src/wallet_dna_engine.py:20`
- `src/wallet_dna_engine_backup.py:223,354,360,392,429,2008,2043,2507`

#### Create SQL

```sql
CREATE TABLE "wallet_dna_profiles" (
                    wallet TEXT PRIMARY KEY,
                    username TEXT,
                    calculated_at TEXT NOT NULL,
                    methodology_version TEXT NOT NULL,
                    primary_archetype TEXT NOT NULL,
                    secondary_archetype TEXT NOT NULL,
                    archetype_confidence REAL NOT NULL DEFAULT 0,
                    conviction_score REAL NOT NULL DEFAULT 0,
                    specialization_score REAL NOT NULL DEFAULT 0,
                    activity_intensity_score REAL NOT NULL DEFAULT 0,
                    diversification_score REAL NOT NULL DEFAULT 0,
                    capital_scale_score REAL NOT NULL DEFAULT 0,
                    profitability_quality_score REAL NOT NULL DEFAULT 0,
                    consistency_score REAL NOT NULL DEFAULT 0,
                    risk_control_score REAL NOT NULL DEFAULT 0,
                    evidence_quality_score REAL NOT NULL DEFAULT 0,
                    whale_score REAL NOT NULL DEFAULT 0,
                    specialist_score REAL NOT NULL DEFAULT 0,
                    selective_bettor_score REAL NOT NULL DEFAULT 0,
                    active_trader_score REAL NOT NULL DEFAULT 0,
                    diversified_portfolio_score REAL NOT NULL DEFAULT 0,
                    aggressive_risk_taker_score REAL NOT NULL DEFAULT 0,
                    disciplined_operator_score REAL NOT NULL DEFAULT 0,
                    high_frequency_score REAL NOT NULL DEFAULT 0,
                    dna_score REAL NOT NULL DEFAULT 0,
                    dna_grade TEXT NOT NULL DEFAULT 'UNRATED',
                    trust_tier TEXT NOT NULL DEFAULT 'UNRATED',
                    follow_priority TEXT NOT NULL DEFAULT 'WATCH',
                    consensus_weight REAL NOT NULL DEFAULT 0,
                    sample_limited INTEGER NOT NULL DEFAULT 1,
                    warning_flags TEXT NOT NULL DEFAULT '[]',
                    explanation TEXT NOT NULL
                )
```

### `wallet_dna_profiles_legacy_v1`

- Row count: `26`
- Referenced by: `wallet_dna_categories`, `wallet_dna_market_types`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | dna_score | REAL | True | 0 | 0 |
| 2 | dna_grade | TEXT | True | 'UNRATED' | 0 |
| 3 | data_confidence | TEXT | True | 'VERY LOW' | 0 |
| 4 | primary_archetype | TEXT | True | 'INSUFFICIENT DATA' | 0 |
| 5 | secondary_archetype | TEXT | False | — | 0 |
| 6 | specialization_label | TEXT | False | — | 0 |
| 7 | risk_label | TEXT | False | — | 0 |
| 8 | conviction_label | TEXT | False | — | 0 |
| 9 | diversification_label | TEXT | False | — | 0 |
| 10 | performance_label | TEXT | False | — | 0 |
| 11 | current_position_count | INTEGER | True | 0 | 0 |
| 12 | current_market_count | INTEGER | True | 0 | 0 |
| 13 | current_value | REAL | True | 0 | 0 |
| 14 | average_position_value | REAL | True | 0 | 0 |
| 15 | largest_position_value | REAL | True | 0 | 0 |
| 16 | largest_position_share | REAL | True | 0 | 0 |
| 17 | top_three_concentration | REAL | True | 0 | 0 |
| 18 | herfindahl_index | REAL | True | 0 | 0 |
| 19 | effective_market_count | REAL | True | 0 | 0 |
| 20 | concentration_score | REAL | True | 0 | 0 |
| 21 | diversification_score | REAL | True | 0 | 0 |
| 22 | conviction_score | REAL | True | 0 | 0 |
| 23 | whale_score | REAL | True | 0 | 0 |
| 24 | specialization_score | REAL | True | 0 | 0 |
| 25 | category_diversity | INTEGER | True | 0 | 0 |
| 26 | primary_category | TEXT | False | — | 0 |
| 27 | primary_category_share | REAL | True | 0 | 0 |
| 28 | sports_share | REAL | True | 0 | 0 |
| 29 | politics_share | REAL | True | 0 | 0 |
| 30 | crypto_share | REAL | True | 0 | 0 |
| 31 | entertainment_share | REAL | True | 0 | 0 |
| 32 | other_share | REAL | True | 0 | 0 |
| 33 | sports_specialty | TEXT | False | — | 0 |
| 34 | market_type_specialty | TEXT | False | — | 0 |
| 35 | resolved_positions | INTEGER | True | 0 | 0 |
| 36 | win_rate | REAL | True | 0 | 0 |
| 37 | estimated_roi | REAL | True | 0 | 0 |
| 38 | estimated_profit | REAL | True | 0 | 0 |
| 39 | performance_score | REAL | True | 50 | 0 |
| 40 | performance_grade | TEXT | True | 'UNRATED' | 0 |
| 41 | calibration_score | REAL | True | 0 | 0 |
| 42 | consistency_score | REAL | True | 0 | 0 |
| 43 | portfolio_independence_score | REAL | True | 50 | 0 |
| 44 | overlap_risk_score | REAL | True | 50 | 0 |
| 45 | traits_json | TEXT | False | — | 0 |
| 46 | specialties_json | TEXT | False | — | 0 |
| 47 | risks_json | TEXT | False | — | 0 |
| 48 | explanation_json | TEXT | False | — | 0 |
| 49 | calculated_at | TEXT | True | — | 0 |
| 50 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_dna_profiles_archetype | False | c | False | primary_archetype, dna_score |
| idx_wallet_dna_profiles_rank | False | c | False | dna_score |
| sqlite_autoindex_wallet_dna_profiles_legacy_v1_1 | True | pk | False | wallet |

#### Source References

No direct table-name references were detected under `src/`.

#### Create SQL

```sql
CREATE TABLE "wallet_dna_profiles_legacy_v1" (
                wallet TEXT PRIMARY KEY,

                dna_score REAL
                    NOT NULL DEFAULT 0,

                dna_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                data_confidence TEXT
                    NOT NULL DEFAULT 'VERY LOW',

                primary_archetype TEXT
                    NOT NULL DEFAULT 'INSUFFICIENT DATA',

                secondary_archetype TEXT,

                specialization_label TEXT,
                risk_label TEXT,
                conviction_label TEXT,
                diversification_label TEXT,
                performance_label TEXT,

                current_position_count INTEGER
                    NOT NULL DEFAULT 0,

                current_market_count INTEGER
                    NOT NULL DEFAULT 0,

                current_value REAL
                    NOT NULL DEFAULT 0,

                average_position_value REAL
                    NOT NULL DEFAULT 0,

                largest_position_value REAL
                    NOT NULL DEFAULT 0,

                largest_position_share REAL
                    NOT NULL DEFAULT 0,

                top_three_concentration REAL
                    NOT NULL DEFAULT 0,

                herfindahl_index REAL
                    NOT NULL DEFAULT 0,

                effective_market_count REAL
                    NOT NULL DEFAULT 0,

                concentration_score REAL
                    NOT NULL DEFAULT 0,

                diversification_score REAL
                    NOT NULL DEFAULT 0,

                conviction_score REAL
                    NOT NULL DEFAULT 0,

                whale_score REAL
                    NOT NULL DEFAULT 0,

                specialization_score REAL
                    NOT NULL DEFAULT 0,

                category_diversity INTEGER
                    NOT NULL DEFAULT 0,

                primary_category TEXT,
                primary_category_share REAL
                    NOT NULL DEFAULT 0,

                sports_share REAL
                    NOT NULL DEFAULT 0,

                politics_share REAL
                    NOT NULL DEFAULT 0,

                crypto_share REAL
                    NOT NULL DEFAULT 0,

                entertainment_share REAL
                    NOT NULL DEFAULT 0,

                other_share REAL
                    NOT NULL DEFAULT 0,

                sports_specialty TEXT,
                market_type_specialty TEXT,

                resolved_positions INTEGER
                    NOT NULL DEFAULT 0,

                win_rate REAL
                    NOT NULL DEFAULT 0,

                estimated_roi REAL
                    NOT NULL DEFAULT 0,

                estimated_profit REAL
                    NOT NULL DEFAULT 0,

                performance_score REAL
                    NOT NULL DEFAULT 50,

                performance_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                calibration_score REAL
                    NOT NULL DEFAULT 0,

                consistency_score REAL
                    NOT NULL DEFAULT 0,

                portfolio_independence_score REAL
                    NOT NULL DEFAULT 50,

                overlap_risk_score REAL
                    NOT NULL DEFAULT 50,

                traits_json TEXT,
                specialties_json TEXT,
                risks_json TEXT,
                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `wallet_dna_runs`

- Row count: `2`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | mode | TEXT | True | — | 0 |
| 4 | wallet_limit | INTEGER | True | — | 0 |
| 5 | min_institutional_score | REAL | True | — | 0 |
| 6 | wallets_selected | INTEGER | True | 0 | 0 |
| 7 | wallets_analyzed | INTEGER | True | 0 | 0 |
| 8 | wallets_failed | INTEGER | True | 0 | 0 |
| 9 | dna_rows_upserted | INTEGER | True | 0 | 0 |
| 10 | summaries_updated | INTEGER | True | 0 | 0 |
| 11 | duration_seconds | REAL | True | 0 | 0 |
| 12 | status | TEXT | True | — | 0 |
| 13 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_wallet_dna_runs_1 | True | pk | False | run_id |

#### Source References

- `src/wallet_dna_engine.py:21`
- `src/wallet_dna_engine_backup.py:466,2164,2205`

#### Create SQL

```sql
CREATE TABLE "wallet_dna_runs" (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    mode TEXT NOT NULL,
                    wallet_limit INTEGER NOT NULL,
                    min_institutional_score REAL NOT NULL,
                    wallets_selected INTEGER NOT NULL DEFAULT 0,
                    wallets_analyzed INTEGER NOT NULL DEFAULT 0,
                    wallets_failed INTEGER NOT NULL DEFAULT 0,
                    dna_rows_upserted INTEGER NOT NULL DEFAULT 0,
                    summaries_updated INTEGER NOT NULL DEFAULT 0,
                    duration_seconds REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
```

### `wallet_dna_runs_legacy_v1`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | latest_positions_loaded | INTEGER | True | 0 | 0 |
| 5 | wallets_analyzed | INTEGER | True | 0 | 0 |
| 6 | profiles_saved | INTEGER | True | 0 | 0 |
| 7 | category_rows_saved | INTEGER | True | 0 | 0 |
| 8 | market_type_rows_saved | INTEGER | True | 0 | 0 |
| 9 | history_rows_saved | INTEGER | True | 0 | 0 |
| 10 | status | TEXT | True | — | 0 |
| 11 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

No direct table-name references were detected under `src/`.

#### Create SQL

```sql
CREATE TABLE "wallet_dna_runs_legacy_v1" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                latest_positions_loaded INTEGER
                    NOT NULL DEFAULT 0,

                wallets_analyzed INTEGER
                    NOT NULL DEFAULT 0,

                profiles_saved INTEGER
                    NOT NULL DEFAULT 0,

                category_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                market_type_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                history_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `wallet_endpoint_support`

- Row count: `18`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | support_key | TEXT | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | endpoint_path | TEXT | True | — | 0 |
| 3 | minimal_request_supported | INTEGER | True | 0 | 0 |
| 4 | large_page_supported | INTEGER | True | 0 | 0 |
| 5 | pagination_supported | INTEGER | True | 0 | 0 |
| 6 | maximum_successful_offset | INTEGER | False | — | 0 |
| 7 | first_failed_offset | INTEGER | False | — | 0 |
| 8 | latest_http_status | INTEGER | False | — | 0 |
| 9 | latest_response_count | INTEGER | False | — | 0 |
| 10 | latest_error_message | TEXT | False | — | 0 |
| 11 | support_status | TEXT | True | 'UNKNOWN' | 0 |
| 12 | first_tested_at | TEXT | True | — | 0 |
| 13 | last_tested_at | TEXT | True | — | 0 |
| 14 | metadata_json | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_endpoint_support_status | False | c | False | endpoint_path, support_status, wallet |
| sqlite_autoindex_wallet_endpoint_support_1 | True | pk | False | support_key |

#### Source References

- `src/official_api_validator.py:213,232,813,827,988,1025`

#### Create SQL

```sql
CREATE TABLE wallet_endpoint_support (
                support_key TEXT PRIMARY KEY,
                wallet TEXT NOT NULL,
                endpoint_path TEXT NOT NULL,
                minimal_request_supported INTEGER NOT NULL DEFAULT 0,
                large_page_supported INTEGER NOT NULL DEFAULT 0,
                pagination_supported INTEGER NOT NULL DEFAULT 0,
                maximum_successful_offset INTEGER,
                first_failed_offset INTEGER,
                latest_http_status INTEGER,
                latest_response_count INTEGER,
                latest_error_message TEXT,
                support_status TEXT NOT NULL DEFAULT 'UNKNOWN',
                first_tested_at TEXT NOT NULL,
                last_tested_at TEXT NOT NULL,
                metadata_json TEXT
            )
```

### `wallet_influence_metrics`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | observations | INTEGER | True | 0 | 0 |
| 2 | markets_led | INTEGER | True | 0 | 0 |
| 3 | followers_observed | INTEGER | True | 0 | 0 |
| 4 | average_lead_minutes | REAL | True | 0 | 0 |
| 5 | median_lead_minutes | REAL | True | 0 | 0 |
| 6 | average_price_move_after_entry | REAL | True | 0 | 0 |
| 7 | median_price_move_after_entry | REAL | True | 0 | 0 |
| 8 | consensus_participation_rate | REAL | True | 0 | 0 |
| 9 | consensus_lead_rate | REAL | True | 0 | 0 |
| 10 | signal_success_rate | REAL | True | 0 | 0 |
| 11 | influence_score | REAL | True | 0 | 0 |
| 12 | confidence_score | REAL | True | 0 | 0 |
| 13 | calculated_at | TEXT | False | — | 0 |
| 14 | created_at | TEXT | True | — | 0 |
| 15 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| wallet | wallet_intelligence_profiles | wallet | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_wallet_influence_metrics_1 | True | pk | False | wallet |

#### Source References

- `src/elite_wallet_intelligence_database.py:116,366`

#### Create SQL

```sql
CREATE TABLE wallet_influence_metrics (
        wallet TEXT PRIMARY KEY,

        observations INTEGER NOT NULL DEFAULT 0,
        markets_led INTEGER NOT NULL DEFAULT 0,
        followers_observed INTEGER NOT NULL DEFAULT 0,

        average_lead_minutes REAL NOT NULL DEFAULT 0,
        median_lead_minutes REAL NOT NULL DEFAULT 0,
        average_price_move_after_entry REAL NOT NULL DEFAULT 0,
        median_price_move_after_entry REAL NOT NULL DEFAULT 0,

        consensus_participation_rate REAL NOT NULL DEFAULT 0,
        consensus_lead_rate REAL NOT NULL DEFAULT 0,
        signal_success_rate REAL NOT NULL DEFAULT 0,

        influence_score REAL NOT NULL DEFAULT 0,
        confidence_score REAL NOT NULL DEFAULT 0,

        calculated_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,

        FOREIGN KEY (wallet)
            REFERENCES wallet_intelligence_profiles(wallet)
            ON DELETE CASCADE
    )
```

### `wallet_intelligence_profiles`

- Row count: `26`
- Referenced by: `wallet_category_performance`, `wallet_influence_metrics`, `wallet_intelligence_snapshots`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | first_seen_at | TEXT | False | — | 0 |
| 2 | last_seen_at | TEXT | False | — | 0 |
| 3 | status | TEXT | True | 'ACTIVE' | 0 |
| 4 | overall_score | REAL | True | 0 | 0 |
| 5 | overall_grade | TEXT | True | 'UNRATED' | 0 |
| 6 | confidence_score | REAL | True | 0 | 0 |
| 7 | current_rank | INTEGER | False | — | 0 |
| 8 | markets_tracked | INTEGER | True | 0 | 0 |
| 9 | resolved_markets | INTEGER | True | 0 | 0 |
| 10 | wins | INTEGER | True | 0 | 0 |
| 11 | losses | INTEGER | True | 0 | 0 |
| 12 | win_rate | REAL | True | 0 | 0 |
| 13 | realized_pnl | REAL | True | 0 | 0 |
| 14 | unrealized_pnl | REAL | True | 0 | 0 |
| 15 | total_pnl | REAL | True | 0 | 0 |
| 16 | roi | REAL | True | 0 | 0 |
| 17 | average_position_value | REAL | True | 0 | 0 |
| 18 | median_position_value | REAL | True | 0 | 0 |
| 19 | average_entry_price | REAL | True | 0 | 0 |
| 20 | average_current_price | REAL | True | 0 | 0 |
| 21 | average_entry_edge | REAL | True | 0 | 0 |
| 22 | average_holding_hours | REAL | True | 0 | 0 |
| 23 | timing_score | REAL | True | 0 | 0 |
| 24 | conviction_score | REAL | True | 0 | 0 |
| 25 | consistency_score | REAL | True | 0 | 0 |
| 26 | risk_score | REAL | True | 0 | 0 |
| 27 | influence_score | REAL | True | 0 | 0 |
| 28 | specialization_score | REAL | True | 0 | 0 |
| 29 | recent_form_score | REAL | True | 0 | 0 |
| 30 | strongest_category | TEXT | False | — | 0 |
| 31 | weakest_category | TEXT | False | — | 0 |
| 32 | profile_version | INTEGER | True | 1 | 0 |
| 33 | calculated_at | TEXT | False | — | 0 |
| 34 | created_at | TEXT | True | — | 0 |
| 35 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_profiles_last_seen | False | c | False | last_seen_at |
| idx_wallet_profiles_grade | False | c | False | overall_grade |
| idx_wallet_profiles_rank | False | c | False | current_rank |
| sqlite_autoindex_wallet_intelligence_profiles_1 | True | pk | False | wallet |

#### Source References

- `src/elite_wallet_intelligence_database.py:30,111,140,174,212,213,214,215,311,325,327,330,332,335,337,364`
- `src/wallet_profiler.py:69,461`

#### Create SQL

```sql
CREATE TABLE wallet_intelligence_profiles (
        wallet TEXT PRIMARY KEY,
        first_seen_at TEXT,
        last_seen_at TEXT,
        status TEXT NOT NULL DEFAULT 'ACTIVE',

        overall_score REAL NOT NULL DEFAULT 0,
        overall_grade TEXT NOT NULL DEFAULT 'UNRATED',
        confidence_score REAL NOT NULL DEFAULT 0,
        current_rank INTEGER,

        markets_tracked INTEGER NOT NULL DEFAULT 0,
        resolved_markets INTEGER NOT NULL DEFAULT 0,
        wins INTEGER NOT NULL DEFAULT 0,
        losses INTEGER NOT NULL DEFAULT 0,

        win_rate REAL NOT NULL DEFAULT 0,
        realized_pnl REAL NOT NULL DEFAULT 0,
        unrealized_pnl REAL NOT NULL DEFAULT 0,
        total_pnl REAL NOT NULL DEFAULT 0,
        roi REAL NOT NULL DEFAULT 0,

        average_position_value REAL NOT NULL DEFAULT 0,
        median_position_value REAL NOT NULL DEFAULT 0,
        average_entry_price REAL NOT NULL DEFAULT 0,
        average_current_price REAL NOT NULL DEFAULT 0,
        average_entry_edge REAL NOT NULL DEFAULT 0,
        average_holding_hours REAL NOT NULL DEFAULT 0,

        timing_score REAL NOT NULL DEFAULT 0,
        conviction_score REAL NOT NULL DEFAULT 0,
        consistency_score REAL NOT NULL DEFAULT 0,
        risk_score REAL NOT NULL DEFAULT 0,
        influence_score REAL NOT NULL DEFAULT 0,
        specialization_score REAL NOT NULL DEFAULT 0,
        recent_form_score REAL NOT NULL DEFAULT 0,

        strongest_category TEXT,
        weakest_category TEXT,

        profile_version INTEGER NOT NULL DEFAULT 1,
        calculated_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
```

### `wallet_intelligence_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | completed_at | TEXT | False | — | 0 |
| 3 | status | TEXT | True | — | 0 |
| 4 | source_rows | INTEGER | True | 0 | 0 |
| 5 | wallets_seen | INTEGER | True | 0 | 0 |
| 6 | wallets_profiled | INTEGER | True | 0 | 0 |
| 7 | category_records | INTEGER | True | 0 | 0 |
| 8 | snapshots_written | INTEGER | True | 0 | 0 |
| 9 | configuration_json | TEXT | False | — | 0 |
| 10 | diagnostics_json | TEXT | False | — | 0 |
| 11 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_runs_started | False | c | False | started_at |

#### Source References

- `src/elite_wallet_intelligence_database.py:179,221,368`
- `src/wallet_profiler.py:71,439,620`

#### Create SQL

```sql
CREATE TABLE wallet_intelligence_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        status TEXT NOT NULL,
        source_rows INTEGER NOT NULL DEFAULT 0,
        wallets_seen INTEGER NOT NULL DEFAULT 0,
        wallets_profiled INTEGER NOT NULL DEFAULT 0,
        category_records INTEGER NOT NULL DEFAULT 0,
        snapshots_written INTEGER NOT NULL DEFAULT 0,
        configuration_json TEXT,
        diagnostics_json TEXT,
        error_message TEXT
    )
```

### `wallet_intelligence_snapshots`

- Row count: `26`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | INTEGER | False | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | category | TEXT | False | — | 0 |
| 4 | overall_rank | INTEGER | False | — | 0 |
| 5 | overall_score | REAL | True | 0 | 0 |
| 6 | overall_grade | TEXT | True | 'UNRATED' | 0 |
| 7 | category_rank | INTEGER | False | — | 0 |
| 8 | category_score | REAL | False | — | 0 |
| 9 | category_grade | TEXT | False | — | 0 |
| 10 | confidence_score | REAL | True | 0 | 0 |
| 11 | win_rate | REAL | True | 0 | 0 |
| 12 | roi | REAL | True | 0 | 0 |
| 13 | total_pnl | REAL | True | 0 | 0 |
| 14 | timing_score | REAL | True | 0 | 0 |
| 15 | conviction_score | REAL | True | 0 | 0 |
| 16 | consistency_score | REAL | True | 0 | 0 |
| 17 | risk_score | REAL | True | 0 | 0 |
| 18 | influence_score | REAL | True | 0 | 0 |
| 19 | recent_form_score | REAL | True | 0 | 0 |
| 20 | metrics_json | TEXT | False | — | 0 |
| 21 | snapshot_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| wallet | wallet_intelligence_profiles | wallet | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_snapshots_run | False | c | False | run_id |
| idx_wallet_snapshots_category_time | False | c | False | category, snapshot_at |

#### Source References

- `src/elite_wallet_intelligence_database.py:145,218,219,220,367`
- `src/wallet_profiler.py:70,576`

#### Create SQL

```sql
CREATE TABLE wallet_intelligence_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        wallet TEXT NOT NULL,
        category TEXT,

        overall_rank INTEGER,
        overall_score REAL NOT NULL DEFAULT 0,
        overall_grade TEXT NOT NULL DEFAULT 'UNRATED',
        category_rank INTEGER,
        category_score REAL,
        category_grade TEXT,

        confidence_score REAL NOT NULL DEFAULT 0,
        win_rate REAL NOT NULL DEFAULT 0,
        roi REAL NOT NULL DEFAULT 0,
        total_pnl REAL NOT NULL DEFAULT 0,

        timing_score REAL NOT NULL DEFAULT 0,
        conviction_score REAL NOT NULL DEFAULT 0,
        consistency_score REAL NOT NULL DEFAULT 0,
        risk_score REAL NOT NULL DEFAULT 0,
        influence_score REAL NOT NULL DEFAULT 0,
        recent_form_score REAL NOT NULL DEFAULT 0,

        metrics_json TEXT,
        snapshot_at TEXT NOT NULL,

        FOREIGN KEY (wallet)
            REFERENCES wallet_intelligence_profiles(wallet)
            ON DELETE CASCADE
    )
```

### `wallet_leaderboard_snapshots`

- Row count: `60`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | username | TEXT | False | — | 0 |
| 4 | category | TEXT | True | — | 0 |
| 5 | time_period | TEXT | True | — | 0 |
| 6 | order_by | TEXT | True | — | 0 |
| 7 | leaderboard_rank | INTEGER | False | — | 0 |
| 8 | pnl | REAL | True | 0 | 0 |
| 9 | volume | REAL | True | 0 | 0 |
| 10 | roi_proxy | REAL | True | 0 | 0 |
| 11 | verified_badge | INTEGER | True | 0 | 0 |
| 12 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| run_id | wallet_discovery_runs | run_id | NO ACTION | CASCADE | NONE |

#### Indexes

None.

#### Source References

- `src/elite_wallet_discovery_engine.py:50`
- `src/migrate_wallet_discovery_schema.py:15`

#### Create SQL

```sql
CREATE TABLE "wallet_leaderboard_snapshots" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            wallet TEXT NOT NULL,
            username TEXT,
            category TEXT NOT NULL,
            time_period TEXT NOT NULL,
            order_by TEXT NOT NULL,
            leaderboard_rank INTEGER,
            pnl REAL NOT NULL DEFAULT 0,
            volume REAL NOT NULL DEFAULT 0,
            roi_proxy REAL NOT NULL DEFAULT 0,
            verified_badge INTEGER NOT NULL DEFAULT 0,
            observed_at TEXT NOT NULL,
            FOREIGN KEY(run_id)
                REFERENCES "wallet_discovery_runs"(run_id)
                ON DELETE CASCADE
        )
```

### `wallet_leaderboard_snapshots_backup_20260719_050932`

- Row count: `0`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | username | TEXT | False | — | 0 |
| 4 | category | TEXT | True | — | 0 |
| 5 | time_period | TEXT | True | — | 0 |
| 6 | order_by | TEXT | True | — | 0 |
| 7 | leaderboard_rank | INTEGER | False | — | 0 |
| 8 | pnl | REAL | True | 0 | 0 |
| 9 | volume | REAL | True | 0 | 0 |
| 10 | roi_proxy | REAL | True | 0 | 0 |
| 11 | verified_badge | INTEGER | True | 0 | 0 |
| 12 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| run_id | wallet_discovery_runs_legacy_20260719_050932 | run_id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_snapshots_category_period | False | c | False | category, time_period, leaderboard_rank |
| idx_wallet_snapshots_wallet_time | False | c | False | wallet, observed_at |

#### Source References

No direct table-name references were detected under `src/`.

#### Create SQL

```sql
CREATE TABLE "wallet_leaderboard_snapshots_backup_20260719_050932" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    wallet TEXT NOT NULL,
                    username TEXT,
                    category TEXT NOT NULL,
                    time_period TEXT NOT NULL,
                    order_by TEXT NOT NULL,
                    leaderboard_rank INTEGER,
                    pnl REAL NOT NULL DEFAULT 0,
                    volume REAL NOT NULL DEFAULT 0,
                    roi_proxy REAL NOT NULL DEFAULT 0,
                    verified_badge INTEGER NOT NULL DEFAULT 0,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES "wallet_discovery_runs_legacy_20260719_050932"(run_id)
                        ON DELETE CASCADE
                )
```

### `wallet_performance`

- Row count: `26`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | resolved_positions | INTEGER | True | 0 | 0 |
| 2 | wins | INTEGER | True | 0 | 0 |
| 3 | losses | INTEGER | True | 0 | 0 |
| 4 | unresolved_mapped_positions | INTEGER | True | 0 | 0 |
| 5 | win_rate | REAL | True | 0 | 0 |
| 6 | total_cost_basis | REAL | True | 0 | 0 |
| 7 | total_settlement_value | REAL | True | 0 | 0 |
| 8 | estimated_profit | REAL | True | 0 | 0 |
| 9 | estimated_roi | REAL | True | 0 | 0 |
| 10 | average_entry_price | REAL | True | 0 | 0 |
| 11 | average_winning_entry | REAL | False | — | 0 |
| 12 | average_losing_entry | REAL | False | — | 0 |
| 13 | average_edge_at_entry | REAL | True | 0 | 0 |
| 14 | profit_factor | REAL | False | — | 0 |
| 15 | payoff_ratio | REAL | False | — | 0 |
| 16 | weighted_brier_score | REAL | False | — | 0 |
| 17 | calibration_score | REAL | False | — | 0 |
| 18 | consistency_score | REAL | True | 0 | 0 |
| 19 | sample_size_score | REAL | True | 0 | 0 |
| 20 | profitability_score | REAL | True | 0 | 0 |
| 21 | accuracy_score | REAL | True | 0 | 0 |
| 22 | entry_quality_score | REAL | True | 0 | 0 |
| 23 | performance_score | REAL | True | 0 | 0 |
| 24 | performance_grade | TEXT | True | 'UNRATED' | 0 |
| 25 | data_confidence | TEXT | True | 'VERY LOW' | 0 |
| 26 | mapped_market_count | INTEGER | True | 0 | 0 |
| 27 | first_resolved_scan_at | TEXT | False | — | 0 |
| 28 | last_resolved_scan_at | TEXT | False | — | 0 |
| 29 | explanation_json | TEXT | False | — | 0 |
| 30 | calculated_at | TEXT | True | — | 0 |
| 31 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_performance_rank | False | c | False | performance_score |
| sqlite_autoindex_wallet_performance_1 | True | pk | False | wallet |

#### Source References

- `src/architecture_registry.py:440`
- `src/candidate_qualification_engine.py:802`
- `src/elite_wallet_ranking_engine.py:647`
- `src/signal_fusion_engine.py:25,689,696,1929,2004,2370`
- `src/wallet_alpha_engine.py:821`
- `src/wallet_dna_engine_backup.py:558,565`
- `src/wallet_performance_engine.py:205,288,1442,1461,1895`

#### Create SQL

```sql
CREATE TABLE wallet_performance (
                wallet TEXT PRIMARY KEY,

                resolved_positions INTEGER
                    NOT NULL DEFAULT 0,

                wins INTEGER
                    NOT NULL DEFAULT 0,

                losses INTEGER
                    NOT NULL DEFAULT 0,

                unresolved_mapped_positions INTEGER
                    NOT NULL DEFAULT 0,

                win_rate REAL
                    NOT NULL DEFAULT 0,

                total_cost_basis REAL
                    NOT NULL DEFAULT 0,

                total_settlement_value REAL
                    NOT NULL DEFAULT 0,

                estimated_profit REAL
                    NOT NULL DEFAULT 0,

                estimated_roi REAL
                    NOT NULL DEFAULT 0,

                average_entry_price REAL
                    NOT NULL DEFAULT 0,

                average_winning_entry REAL,
                average_losing_entry REAL,

                average_edge_at_entry REAL
                    NOT NULL DEFAULT 0,

                profit_factor REAL,
                payoff_ratio REAL,

                weighted_brier_score REAL,
                calibration_score REAL,

                consistency_score REAL
                    NOT NULL DEFAULT 0,

                sample_size_score REAL
                    NOT NULL DEFAULT 0,

                profitability_score REAL
                    NOT NULL DEFAULT 0,

                accuracy_score REAL
                    NOT NULL DEFAULT 0,

                entry_quality_score REAL
                    NOT NULL DEFAULT 0,

                performance_score REAL
                    NOT NULL DEFAULT 0,

                performance_grade TEXT
                    NOT NULL DEFAULT 'UNRATED',

                data_confidence TEXT
                    NOT NULL DEFAULT 'VERY LOW',

                mapped_market_count INTEGER
                    NOT NULL DEFAULT 0,

                first_resolved_scan_at TEXT,
                last_resolved_scan_at TEXT,

                explanation_json TEXT,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `wallet_performance_history`

- Row count: `52`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | resolved_positions | INTEGER | False | — | 0 |
| 3 | wins | INTEGER | False | — | 0 |
| 4 | losses | INTEGER | False | — | 0 |
| 5 | win_rate | REAL | False | — | 0 |
| 6 | total_cost_basis | REAL | False | — | 0 |
| 7 | total_settlement_value | REAL | False | — | 0 |
| 8 | estimated_profit | REAL | False | — | 0 |
| 9 | estimated_roi | REAL | False | — | 0 |
| 10 | performance_score | REAL | False | — | 0 |
| 11 | performance_grade | TEXT | False | — | 0 |
| 12 | data_confidence | TEXT | False | — | 0 |
| 13 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_performance_history_wallet | False | c | False | wallet, observed_at |

#### Source References

- `src/wallet_performance_engine.py:350,374,1480,1905`

#### Create SQL

```sql
CREATE TABLE wallet_performance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                wallet TEXT NOT NULL,

                resolved_positions INTEGER,
                wins INTEGER,
                losses INTEGER,

                win_rate REAL,
                total_cost_basis REAL,
                total_settlement_value REAL,
                estimated_profit REAL,
                estimated_roi REAL,

                performance_score REAL,
                performance_grade TEXT,
                data_confidence TEXT,

                observed_at TEXT NOT NULL
            )
```

### `wallet_performance_markets`

- Row count: `16`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | performance_market_key | TEXT | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | scan_id | INTEGER | False | — | 0 |
| 3 | scanned_at | TEXT | False | — | 0 |
| 4 | market_id | TEXT | True | — | 0 |
| 5 | title | TEXT | False | — | 0 |
| 6 | selected_outcome | TEXT | False | — | 0 |
| 7 | gamma_market_id | TEXT | False | — | 0 |
| 8 | condition_id | TEXT | False | — | 0 |
| 9 | resolution_status | TEXT | False | — | 0 |
| 10 | winning_outcome_name | TEXT | False | — | 0 |
| 11 | source_outcome_won | INTEGER | False | — | 0 |
| 12 | source_outcome_lost | INTEGER | False | — | 0 |
| 13 | shares | REAL | True | 0 | 0 |
| 14 | average_entry_price | REAL | True | 0 | 0 |
| 15 | cost_basis | REAL | True | 0 | 0 |
| 16 | settlement_price | REAL | False | — | 0 |
| 17 | settlement_value | REAL | False | — | 0 |
| 18 | estimated_profit | REAL | False | — | 0 |
| 19 | estimated_roi | REAL | False | — | 0 |
| 20 | brier_score | REAL | False | — | 0 |
| 21 | match_method | TEXT | False | — | 0 |
| 22 | match_confidence | REAL | False | — | 0 |
| 23 | calculated_at | TEXT | True | — | 0 |
| 24 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_performance_markets_market | False | c | False | market_id |
| idx_wallet_performance_markets_wallet | False | c | False | wallet, source_outcome_won |
| sqlite_autoindex_wallet_performance_markets_1 | True | pk | False | performance_market_key |

#### Source References

- `src/wallet_performance_engine.py:292,339,346,1448,1465,1900`

#### Create SQL

```sql
CREATE TABLE wallet_performance_markets (
                performance_market_key TEXT PRIMARY KEY,

                wallet TEXT NOT NULL,

                scan_id INTEGER,
                scanned_at TEXT,

                market_id TEXT NOT NULL,
                title TEXT,
                selected_outcome TEXT,

                gamma_market_id TEXT,
                condition_id TEXT,

                resolution_status TEXT,
                winning_outcome_name TEXT,

                source_outcome_won INTEGER,
                source_outcome_lost INTEGER,

                shares REAL
                    NOT NULL DEFAULT 0,

                average_entry_price REAL
                    NOT NULL DEFAULT 0,

                cost_basis REAL
                    NOT NULL DEFAULT 0,

                settlement_price REAL,

                settlement_value REAL,
                estimated_profit REAL,
                estimated_roi REAL,

                brier_score REAL,

                match_method TEXT,
                match_confidence REAL,

                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `wallet_performance_metrics`

- Row count: `6`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | username | TEXT | False | — | 0 |
| 2 | source_run_id | TEXT | True | — | 0 |
| 3 | calculated_at | TEXT | True | — | 0 |
| 4 | source_elite_score | REAL | True | 0 | 0 |
| 5 | source_elite_grade | TEXT | False | — | 0 |
| 6 | primary_category | TEXT | False | — | 0 |
| 7 | current_position_count | INTEGER | True | 0 | 0 |
| 8 | closed_position_count | INTEGER | True | 0 | 0 |
| 9 | trade_sample_count | INTEGER | True | 0 | 0 |
| 10 | activity_sample_count | INTEGER | True | 0 | 0 |
| 11 | total_markets_traded | INTEGER | True | 0 | 0 |
| 12 | total_current_value | REAL | True | 0 | 0 |
| 13 | total_open_pnl | REAL | True | 0 | 0 |
| 14 | realized_pnl_sample | REAL | True | 0 | 0 |
| 15 | gross_closed_cost_sample | REAL | True | 0 | 0 |
| 16 | realized_roi_sample | REAL | True | 0 | 0 |
| 17 | closed_win_count | INTEGER | True | 0 | 0 |
| 18 | closed_loss_count | INTEGER | True | 0 | 0 |
| 19 | closed_flat_count | INTEGER | True | 0 | 0 |
| 20 | closed_win_rate | REAL | True | 0 | 0 |
| 21 | profit_factor | REAL | True | 0 | 0 |
| 22 | average_closed_pnl | REAL | True | 0 | 0 |
| 23 | median_closed_pnl | REAL | True | 0 | 0 |
| 24 | closed_pnl_volatility | REAL | True | 0 | 0 |
| 25 | max_sample_drawdown | REAL | True | 0 | 0 |
| 26 | profitable_open_position_rate | REAL | True | 0 | 0 |
| 27 | average_position_value | REAL | True | 0 | 0 |
| 28 | median_position_value | REAL | True | 0 | 0 |
| 29 | largest_position_value | REAL | True | 0 | 0 |
| 30 | concentration_ratio | REAL | True | 0 | 0 |
| 31 | open_pnl_ratio | REAL | True | 0 | 0 |
| 32 | buy_trade_count | INTEGER | True | 0 | 0 |
| 33 | sell_trade_count | INTEGER | True | 0 | 0 |
| 34 | trade_buy_ratio | REAL | True | 0 | 0 |
| 35 | average_trade_notional | REAL | True | 0 | 0 |
| 36 | median_trade_notional | REAL | True | 0 | 0 |
| 37 | activity_notional_sample | REAL | True | 0 | 0 |
| 38 | sports_exposure | REAL | True | 0 | 0 |
| 39 | politics_exposure | REAL | True | 0 | 0 |
| 40 | crypto_exposure | REAL | True | 0 | 0 |
| 41 | macro_exposure | REAL | True | 0 | 0 |
| 42 | entertainment_exposure | REAL | True | 0 | 0 |
| 43 | other_exposure | REAL | True | 0 | 0 |
| 44 | favorite_category | TEXT | True | 'OTHER' | 0 |
| 45 | specialization_score | REAL | True | 0 | 0 |
| 46 | profitability_score | REAL | True | 0 | 0 |
| 47 | consistency_score | REAL | True | 0 | 0 |
| 48 | risk_control_score | REAL | True | 0 | 0 |
| 49 | activity_score | REAL | True | 0 | 0 |
| 50 | scale_score | REAL | True | 0 | 0 |
| 51 | data_quality_score | REAL | True | 0 | 0 |
| 52 | institutional_score | REAL | True | 0 | 0 |
| 53 | institutional_grade | TEXT | True | 'UNRATED' | 0 |
| 54 | risk_profile | TEXT | True | 'UNKNOWN' | 0 |
| 55 | activity_style | TEXT | True | 'UNKNOWN' | 0 |
| 56 | sample_limited | INTEGER | True | 1 | 0 |
| 57 | methodology_version | TEXT | True | '1.0' | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_performance_category | False | c | False | favorite_category, specialization_score |
| idx_wallet_performance_rating | False | c | False | institutional_score, closed_win_rate |
| sqlite_autoindex_wallet_performance_metrics_1 | True | pk | False | wallet |

#### Source References

- `src/performance_analytics_engine.py:18,54`
- `src/wallet_dna_engine.py:19,130`

#### Create SQL

```sql
CREATE TABLE "wallet_performance_metrics" (
                    wallet TEXT PRIMARY KEY,
                    username TEXT,
                    source_run_id TEXT NOT NULL,
                    calculated_at TEXT NOT NULL,
                    source_elite_score REAL NOT NULL DEFAULT 0,
                    source_elite_grade TEXT,
                    primary_category TEXT,

                    current_position_count INTEGER NOT NULL DEFAULT 0,
                    closed_position_count INTEGER NOT NULL DEFAULT 0,
                    trade_sample_count INTEGER NOT NULL DEFAULT 0,
                    activity_sample_count INTEGER NOT NULL DEFAULT 0,
                    total_markets_traded INTEGER NOT NULL DEFAULT 0,

                    total_current_value REAL NOT NULL DEFAULT 0,
                    total_open_pnl REAL NOT NULL DEFAULT 0,
                    realized_pnl_sample REAL NOT NULL DEFAULT 0,
                    gross_closed_cost_sample REAL NOT NULL DEFAULT 0,
                    realized_roi_sample REAL NOT NULL DEFAULT 0,

                    closed_win_count INTEGER NOT NULL DEFAULT 0,
                    closed_loss_count INTEGER NOT NULL DEFAULT 0,
                    closed_flat_count INTEGER NOT NULL DEFAULT 0,
                    closed_win_rate REAL NOT NULL DEFAULT 0,
                    profit_factor REAL NOT NULL DEFAULT 0,
                    average_closed_pnl REAL NOT NULL DEFAULT 0,
                    median_closed_pnl REAL NOT NULL DEFAULT 0,
                    closed_pnl_volatility REAL NOT NULL DEFAULT 0,
                    max_sample_drawdown REAL NOT NULL DEFAULT 0,

                    profitable_open_position_rate REAL NOT NULL DEFAULT 0,
                    average_position_value REAL NOT NULL DEFAULT 0,
                    median_position_value REAL NOT NULL DEFAULT 0,
                    largest_position_value REAL NOT NULL DEFAULT 0,
                    concentration_ratio REAL NOT NULL DEFAULT 0,
                    open_pnl_ratio REAL NOT NULL DEFAULT 0,

                    buy_trade_count INTEGER NOT NULL DEFAULT 0,
                    sell_trade_count INTEGER NOT NULL DEFAULT 0,
                    trade_buy_ratio REAL NOT NULL DEFAULT 0,
                    average_trade_notional REAL NOT NULL DEFAULT 0,
                    median_trade_notional REAL NOT NULL DEFAULT 0,
                    activity_notional_sample REAL NOT NULL DEFAULT 0,

                    sports_exposure REAL NOT NULL DEFAULT 0,
                    politics_exposure REAL NOT NULL DEFAULT 0,
                    crypto_exposure REAL NOT NULL DEFAULT 0,
                    macro_exposure REAL NOT NULL DEFAULT 0,
                    entertainment_exposure REAL NOT NULL DEFAULT 0,
                    other_exposure REAL NOT NULL DEFAULT 0,
                    favorite_category TEXT NOT NULL DEFAULT 'OTHER',
                    specialization_score REAL NOT NULL DEFAULT 0,

                    profitability_score REAL NOT NULL DEFAULT 0,
                    consistency_score REAL NOT NULL DEFAULT 0,
                    risk_control_score REAL NOT NULL DEFAULT 0,
                    activity_score REAL NOT NULL DEFAULT 0,
                    scale_score REAL NOT NULL DEFAULT 0,
                    data_quality_score REAL NOT NULL DEFAULT 0,
                    institutional_score REAL NOT NULL DEFAULT 0,
                    institutional_grade TEXT NOT NULL DEFAULT 'UNRATED',
                    risk_profile TEXT NOT NULL DEFAULT 'UNKNOWN',
                    activity_style TEXT NOT NULL DEFAULT 'UNKNOWN',
                    sample_limited INTEGER NOT NULL DEFAULT 1,
                    methodology_version TEXT NOT NULL DEFAULT '1.0'
                )
```

### `wallet_performance_runs`

- Row count: `2`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | latest_positions_loaded | INTEGER | True | 0 | 0 |
| 5 | resolved_position_rows | INTEGER | True | 0 | 0 |
| 6 | wallets_scored | INTEGER | True | 0 | 0 |
| 7 | performance_rows_saved | INTEGER | True | 0 | 0 |
| 8 | market_rows_saved | INTEGER | True | 0 | 0 |
| 9 | history_rows_saved | INTEGER | True | 0 | 0 |
| 10 | status | TEXT | True | — | 0 |
| 11 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/wallet_performance_engine.py:379,1569,1610`

#### Create SQL

```sql
CREATE TABLE wallet_performance_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,

                latest_positions_loaded INTEGER
                    NOT NULL DEFAULT 0,

                resolved_position_rows INTEGER
                    NOT NULL DEFAULT 0,

                wallets_scored INTEGER
                    NOT NULL DEFAULT 0,

                performance_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                market_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                history_rows_saved INTEGER
                    NOT NULL DEFAULT 0,

                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `wallet_profile_collection_runs`

- Row count: `3`
- Referenced by: `wallet_activity_snapshots`, `wallet_closed_position_snapshots`, `wallet_current_position_snapshots`, `wallet_profiles_raw`, `wallet_trade_snapshots`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | mode | TEXT | True | — | 0 |
| 4 | candidate_limit | INTEGER | True | — | 0 |
| 5 | min_elite_score | REAL | True | — | 0 |
| 6 | wallets_selected | INTEGER | True | 0 | 0 |
| 7 | wallets_completed | INTEGER | True | 0 | 0 |
| 8 | wallets_failed | INTEGER | True | 0 | 0 |
| 9 | API_queries | INTEGER | True | 0 | 0 |
| 10 | current_positions_collected | INTEGER | True | 0 | 0 |
| 11 | closed_positions_collected | INTEGER | True | 0 | 0 |
| 12 | trades_collected | INTEGER | True | 0 | 0 |
| 13 | activity_rows_collected | INTEGER | True | 0 | 0 |
| 14 | profile_rows_upserted | INTEGER | True | 0 | 0 |
| 15 | status | TEXT | True | — | 0 |
| 16 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_wallet_profile_collection_runs_1 | True | pk | False | run_id |

#### Source References

- `src/wallet_intelligence_source.py:14`
- `src/wallet_profile_collector.py:29`

#### Create SQL

```sql
CREATE TABLE "wallet_profile_collection_runs" (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    mode TEXT NOT NULL,
                    candidate_limit INTEGER NOT NULL,
                    min_elite_score REAL NOT NULL,
                    wallets_selected INTEGER NOT NULL DEFAULT 0,
                    wallets_completed INTEGER NOT NULL DEFAULT 0,
                    wallets_failed INTEGER NOT NULL DEFAULT 0,
                    API_queries INTEGER NOT NULL DEFAULT 0,
                    current_positions_collected INTEGER NOT NULL DEFAULT 0,
                    closed_positions_collected INTEGER NOT NULL DEFAULT 0,
                    trades_collected INTEGER NOT NULL DEFAULT 0,
                    activity_rows_collected INTEGER NOT NULL DEFAULT 0,
                    profile_rows_upserted INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
```

### `wallet_profile_history`

- Row count: `529`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | wallet_score | REAL | True | 0 | 0 |
| 3 | wallet_grade | TEXT | True | 'UNRATED' | 0 |
| 4 | total_current_value | REAL | True | 0 | 0 |
| 5 | total_open_pnl | REAL | True | 0 | 0 |
| 6 | open_pnl_ratio | REAL | True | 0 | 0 |
| 7 | active_position_count | INTEGER | True | 0 | 0 |
| 8 | meaningful_position_count | INTEGER | True | 0 | 0 |
| 9 | profitable_position_rate | REAL | True | 0 | 0 |
| 10 | concentration_ratio | REAL | True | 0 | 0 |
| 11 | favorite_category | TEXT | True | 'Unknown' | 0 |
| 12 | activity_style | TEXT | True | 'Unknown' | 0 |
| 13 | risk_profile | TEXT | True | 'Unknown' | 0 |
| 14 | leader_score | REAL | True | 0 | 0 |
| 15 | activity_score | REAL | True | 0 | 0 |
| 16 | specialization_score | REAL | True | 0 | 0 |
| 17 | dna_score | REAL | True | 0 | 0 |
| 18 | dna_grade | TEXT | True | 'UNRATED' | 0 |
| 19 | calculated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_profile_history_calculated_at | False | c | False | calculated_at |
| idx_wallet_profile_history_wallet | False | c | False | wallet |

#### Source References

- `src/intelligence_database.py:117,152,160,625`
- `src/pages/5_Wallet_Intelligence.py:192,217`
- `src/wallet_intelligence_engine.py:1338,1616`

#### Create SQL

```sql
CREATE TABLE wallet_profile_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,

            wallet_score REAL NOT NULL DEFAULT 0,
            wallet_grade TEXT NOT NULL DEFAULT 'UNRATED',

            total_current_value REAL NOT NULL DEFAULT 0,
            total_open_pnl REAL NOT NULL DEFAULT 0,
            open_pnl_ratio REAL NOT NULL DEFAULT 0,

            active_position_count INTEGER NOT NULL DEFAULT 0,
            meaningful_position_count INTEGER NOT NULL DEFAULT 0,
            profitable_position_rate REAL NOT NULL DEFAULT 0,
            concentration_ratio REAL NOT NULL DEFAULT 0,

            favorite_category TEXT NOT NULL DEFAULT 'Unknown',
            activity_style TEXT NOT NULL DEFAULT 'Unknown',
            risk_profile TEXT NOT NULL DEFAULT 'Unknown',

            leader_score REAL NOT NULL DEFAULT 0,
            activity_score REAL NOT NULL DEFAULT 0,
            specialization_score REAL NOT NULL DEFAULT 0,
            dna_score REAL NOT NULL DEFAULT 0,
            dna_grade TEXT NOT NULL DEFAULT 'UNRATED',

            calculated_at TEXT NOT NULL
        )
```

### `wallet_profiles`

- Row count: `29`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | wallet_score | REAL | True | 0 | 0 |
| 2 | wallet_grade | TEXT | True | 'UNRATED' | 0 |
| 3 | scan_count | INTEGER | True | 0 | 0 |
| 4 | active_position_count | INTEGER | True | 0 | 0 |
| 5 | meaningful_position_count | INTEGER | True | 0 | 0 |
| 6 | total_current_value | REAL | True | 0 | 0 |
| 7 | total_open_pnl | REAL | True | 0 | 0 |
| 8 | open_pnl_ratio | REAL | True | 0 | 0 |
| 9 | profitable_position_rate | REAL | True | 0 | 0 |
| 10 | average_position_value | REAL | True | 0 | 0 |
| 11 | median_position_value | REAL | True | 0 | 0 |
| 12 | largest_position_value | REAL | True | 0 | 0 |
| 13 | concentration_ratio | REAL | True | 0 | 0 |
| 14 | average_entry_price | REAL | True | 0 | 0 |
| 15 | average_current_price | REAL | True | 0 | 0 |
| 16 | average_observed_move | REAL | True | 0 | 0 |
| 17 | sports_exposure | REAL | True | 0 | 0 |
| 18 | politics_exposure | REAL | True | 0 | 0 |
| 19 | crypto_exposure | REAL | True | 0 | 0 |
| 20 | macro_exposure | REAL | True | 0 | 0 |
| 21 | entertainment_exposure | REAL | True | 0 | 0 |
| 22 | other_exposure | REAL | True | 0 | 0 |
| 23 | favorite_category | TEXT | True | 'Unknown' | 0 |
| 24 | activity_style | TEXT | True | 'Unknown' | 0 |
| 25 | risk_profile | TEXT | True | 'Unknown' | 0 |
| 26 | leader_score | REAL | True | 0 | 0 |
| 27 | activity_score | REAL | True | 0 | 0 |
| 28 | specialization_score | REAL | True | 0 | 0 |
| 29 | dna_score | REAL | True | 0 | 0 |
| 30 | dna_grade | TEXT | True | 'UNRATED' | 0 |
| 31 | first_observed_at | TEXT | False | — | 0 |
| 32 | latest_observed_at | TEXT | False | — | 0 |
| 33 | calculated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_profiles_favorite_category | False | c | False | favorite_category |
| idx_wallet_profiles_wallet_score | False | c | False | wallet_score |
| idx_wallet_profiles_dna_score | False | c | False | dna_score |
| sqlite_autoindex_wallet_profiles_1 | True | pk | False | wallet |

#### Source References

- `src/closing_line_engine.py:299,1150`
- `src/inspect_master_inputs.py:19`
- `src/institutional_consensus_engine.py:572,2210`
- `src/intelligence_database.py:37,89,97,105,624`
- `src/opportunity_engine.py:368,379,405,1171`
- `src/pages/5_Wallet_Intelligence.py:138,178`
- `src/performance_analytics_engine.py:19,55,1152`
- `src/position_evolution_engine.py:472,1919`
- `src/wallet_dna_engine.py:22`
- `src/wallet_dna_engine_backup.py:589,595,604`
- `src/wallet_intelligence_engine.py:1238,1611`

#### Create SQL

```sql
CREATE TABLE wallet_profiles (
            wallet TEXT PRIMARY KEY,

            wallet_score REAL NOT NULL DEFAULT 0,
            wallet_grade TEXT NOT NULL DEFAULT 'UNRATED',

            scan_count INTEGER NOT NULL DEFAULT 0,
            active_position_count INTEGER NOT NULL DEFAULT 0,
            meaningful_position_count INTEGER NOT NULL DEFAULT 0,

            total_current_value REAL NOT NULL DEFAULT 0,
            total_open_pnl REAL NOT NULL DEFAULT 0,
            open_pnl_ratio REAL NOT NULL DEFAULT 0,

            profitable_position_rate REAL NOT NULL DEFAULT 0,
            average_position_value REAL NOT NULL DEFAULT 0,
            median_position_value REAL NOT NULL DEFAULT 0,
            largest_position_value REAL NOT NULL DEFAULT 0,
            concentration_ratio REAL NOT NULL DEFAULT 0,

            average_entry_price REAL NOT NULL DEFAULT 0,
            average_current_price REAL NOT NULL DEFAULT 0,
            average_observed_move REAL NOT NULL DEFAULT 0,

            sports_exposure REAL NOT NULL DEFAULT 0,
            politics_exposure REAL NOT NULL DEFAULT 0,
            crypto_exposure REAL NOT NULL DEFAULT 0,
            macro_exposure REAL NOT NULL DEFAULT 0,
            entertainment_exposure REAL NOT NULL DEFAULT 0,
            other_exposure REAL NOT NULL DEFAULT 0,

            favorite_category TEXT NOT NULL DEFAULT 'Unknown',
            activity_style TEXT NOT NULL DEFAULT 'Unknown',
            risk_profile TEXT NOT NULL DEFAULT 'Unknown',

            leader_score REAL NOT NULL DEFAULT 0,
            activity_score REAL NOT NULL DEFAULT 0,
            specialization_score REAL NOT NULL DEFAULT 0,
            dna_score REAL NOT NULL DEFAULT 0,
            dna_grade TEXT NOT NULL DEFAULT 'UNRATED',

            first_observed_at TEXT,
            latest_observed_at TEXT,
            calculated_at TEXT NOT NULL
        )
```

### `wallet_profiles_raw`

- Row count: `6`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | username | TEXT | False | — | 0 |
| 2 | source_elite_score | REAL | True | 0 | 0 |
| 3 | source_elite_grade | TEXT | False | — | 0 |
| 4 | primary_category | TEXT | False | — | 0 |
| 5 | first_profiled_at | TEXT | True | — | 0 |
| 6 | last_profiled_at | TEXT | True | — | 0 |
| 7 | profile_scan_count | INTEGER | True | 1 | 0 |
| 8 | position_value | REAL | True | 0 | 0 |
| 9 | total_markets_traded | INTEGER | True | 0 | 0 |
| 10 | current_position_count | INTEGER | True | 0 | 0 |
| 11 | closed_position_count | INTEGER | True | 0 | 0 |
| 12 | trade_sample_count | INTEGER | True | 0 | 0 |
| 13 | activity_sample_count | INTEGER | True | 0 | 0 |
| 14 | latest_collection_status | TEXT | True | — | 0 |
| 15 | latest_error_message | TEXT | False | — | 0 |
| 16 | last_run_id | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| last_run_id | wallet_profile_collection_runs | run_id | NO ACTION | RESTRICT | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_profiles_score | False | c | False | source_elite_score, total_markets_traded |
| sqlite_autoindex_wallet_profiles_raw_1 | True | pk | False | wallet |

#### Source References

- `src/performance_analytics_engine.py:13,47`
- `src/wallet_intelligence_source.py:15`
- `src/wallet_profile_collector.py:30`

#### Create SQL

```sql
CREATE TABLE "wallet_profiles_raw" (
                    wallet TEXT PRIMARY KEY,
                    username TEXT,
                    source_elite_score REAL NOT NULL DEFAULT 0,
                    source_elite_grade TEXT,
                    primary_category TEXT,
                    first_profiled_at TEXT NOT NULL,
                    last_profiled_at TEXT NOT NULL,
                    profile_scan_count INTEGER NOT NULL DEFAULT 1,
                    position_value REAL NOT NULL DEFAULT 0,
                    total_markets_traded INTEGER NOT NULL DEFAULT 0,
                    current_position_count INTEGER NOT NULL DEFAULT 0,
                    closed_position_count INTEGER NOT NULL DEFAULT 0,
                    trade_sample_count INTEGER NOT NULL DEFAULT 0,
                    activity_sample_count INTEGER NOT NULL DEFAULT 0,
                    latest_collection_status TEXT NOT NULL,
                    latest_error_message TEXT,
                    last_run_id TEXT NOT NULL,
                    FOREIGN KEY(last_run_id)
                        REFERENCES "wallet_profile_collection_runs"(run_id)
                        ON DELETE RESTRICT
                )
```

### `wallet_rating_history`

- Row count: `1120`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | scan_count | INTEGER | True | — | 0 |
| 3 | position_count | INTEGER | True | — | 0 |
| 4 | meaningful_position_count | INTEGER | True | — | 0 |
| 5 | profitable_position_count | INTEGER | True | — | 0 |
| 6 | profitable_position_rate | REAL | True | — | 0 |
| 7 | total_current_value | REAL | True | — | 0 |
| 8 | total_open_pnl | REAL | True | — | 0 |
| 9 | open_pnl_ratio | REAL | True | — | 0 |
| 10 | largest_position_value | REAL | True | — | 0 |
| 11 | concentration_ratio | REAL | True | — | 0 |
| 12 | median_position_value | REAL | True | — | 0 |
| 13 | wallet_score | REAL | True | — | 0 |
| 14 | wallet_grade | TEXT | True | — | 0 |
| 15 | rated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_rating_history_rated_at | False | c | False | rated_at |
| idx_wallet_rating_history_wallet | False | c | False | wallet |

#### Source References

- `src/ai_research_engine.py:131,145`
- `src/command_center.py:173,182,195`
- `src/dashboard.py:158,170,185,911`
- `src/ml_ranking_engine.py:133,142,152`
- `src/pages/2_Smart_Money_Radar.py:161,170,176`
- `src/pages/4_Market_leadership.py:170,179,191`
- `src/platform_health.py:319`
- `src/wallet_intelligence_engine.py:222,227`
- `src/wallet_rating_engine.py:56,81,89,371`
- `src/weighted_consensus_engine.py:83,95`

#### Create SQL

```sql
CREATE TABLE wallet_rating_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                scan_count INTEGER NOT NULL,
                position_count INTEGER NOT NULL,
                meaningful_position_count INTEGER NOT NULL,
                profitable_position_count INTEGER NOT NULL,
                profitable_position_rate REAL NOT NULL,
                total_current_value REAL NOT NULL,
                total_open_pnl REAL NOT NULL,
                open_pnl_ratio REAL NOT NULL,
                largest_position_value REAL NOT NULL,
                concentration_ratio REAL NOT NULL,
                median_position_value REAL NOT NULL,
                wallet_score REAL NOT NULL,
                wallet_grade TEXT NOT NULL,
                rated_at TEXT NOT NULL
            )
```

### `wallet_registry`

- Row count: `923`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | status | TEXT | True | 'CANDIDATE' | 0 |
| 2 | first_discovered_at | TEXT | False | — | 0 |
| 3 | last_discovered_at | TEXT | False | — | 0 |
| 4 | first_discovery_source | TEXT | False | — | 0 |
| 5 | latest_discovery_source | TEXT | False | — | 0 |
| 6 | discovery_count | INTEGER | True | 0 | 0 |
| 7 | leaderboard_appearance_count | INTEGER | True | 0 | 0 |
| 8 | best_rank | INTEGER | False | — | 0 |
| 9 | latest_rank | INTEGER | False | — | 0 |
| 10 | latest_username | TEXT | False | — | 0 |
| 11 | latest_x_username | TEXT | False | — | 0 |
| 12 | latest_profile_image | TEXT | False | — | 0 |
| 13 | latest_verified_badge | INTEGER | True | 0 | 0 |
| 14 | latest_category | TEXT | False | — | 0 |
| 15 | latest_time_period | TEXT | False | — | 0 |
| 16 | latest_order_by | TEXT | False | — | 0 |
| 17 | latest_pnl | REAL | True | 0 | 0 |
| 18 | latest_volume | REAL | True | 0 | 0 |
| 19 | best_observed_pnl | REAL | True | 0 | 0 |
| 20 | highest_observed_volume | REAL | True | 0 | 0 |
| 21 | weekly_pnl_appearances | INTEGER | True | 0 | 0 |
| 22 | weekly_volume_appearances | INTEGER | True | 0 | 0 |
| 23 | monthly_pnl_appearances | INTEGER | True | 0 | 0 |
| 24 | all_time_pnl_appearances | INTEGER | True | 0 | 0 |
| 25 | sports_appearances | INTEGER | True | 0 | 0 |
| 26 | active_for_scanning | INTEGER | True | 0 | 0 |
| 27 | qualification_eligible | INTEGER | True | 0 | 0 |
| 28 | metadata_json | TEXT | False | — | 0 |
| 29 | created_at | TEXT | False | — | 0 |
| 30 | updated_at | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_registry_status | False | c | False | status, qualification_eligible, leaderboard_appearance_count |
| sqlite_autoindex_wallet_registry_1 | True | pk | False | wallet |

#### Source References

- `src/candidate_qualification_engine.py:215,490,495,789,1628,2126,2257,2262`
- `src/market_memory_engine.py:396,405,680,895`
- `src/official_api_validator.py:489,491,511`
- `src/official_wallet_activity_engine.py:112,114,366`
- `src/official_wallet_activity_engine_v2.py:210,213,942`
- `src/weekly_wallet_discovery.py:148,271,282,317,613,634,749,905,957,963,972,1245`

#### Create SQL

```sql
CREATE TABLE wallet_registry (
                wallet TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'CANDIDATE',
                first_discovered_at TEXT,
                last_discovered_at TEXT,
                first_discovery_source TEXT,
                latest_discovery_source TEXT,
                discovery_count INTEGER NOT NULL DEFAULT 0,
                leaderboard_appearance_count INTEGER NOT NULL DEFAULT 0,
                best_rank INTEGER,
                latest_rank INTEGER,
                latest_username TEXT,
                latest_x_username TEXT,
                latest_profile_image TEXT,
                latest_verified_badge INTEGER NOT NULL DEFAULT 0,
                latest_category TEXT,
                latest_time_period TEXT,
                latest_order_by TEXT,
                latest_pnl REAL NOT NULL DEFAULT 0,
                latest_volume REAL NOT NULL DEFAULT 0,
                best_observed_pnl REAL NOT NULL DEFAULT 0,
                highest_observed_volume REAL NOT NULL DEFAULT 0,
                weekly_pnl_appearances INTEGER NOT NULL DEFAULT 0,
                weekly_volume_appearances INTEGER NOT NULL DEFAULT 0,
                monthly_pnl_appearances INTEGER NOT NULL DEFAULT 0,
                all_time_pnl_appearances INTEGER NOT NULL DEFAULT 0,
                sports_appearances INTEGER NOT NULL DEFAULT 0,
                active_for_scanning INTEGER NOT NULL DEFAULT 0,
                qualification_eligible INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT,
                created_at TEXT,
                updated_at TEXT
            )
```

### `wallet_scans`

- Row count: `1134`
- Referenced by: `positions`, `wallet_activity`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | scanned_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_scans_wallet | False | c | False | wallet |

#### Source References

- `src/ai_research_engine.py:180`
- `src/closing_line_engine.py:313,329,1148`
- `src/consensus_diagnostics.py:18`
- `src/consensus_engine.py:71`
- `src/conviction_engine.py:56`
- `src/dashboard.py:896`
- `src/dashboard_schema_audit.py:29`
- `src/data_access.py:594,602,644,653,801`
- `src/database.py:36,59,122,126,136,387,569,651,676`
- `src/elite_wallet_intelligence_database.py:257,258,273`
- `src/institutional_consensus_engine.py:597,667,675,679,681,2208`
- `src/intelligence_database.py:200,203`
- `src/market_status_engine.py:284`
- `src/ml_ranking_engine.py:181`
- `src/opportunity_engine.py:387,1169`
- `src/pages/1_Market_Intelligence_Timeline.py:177`
- `src/pages/2_Smart_Money_Radar.py:204`
- `src/pages/4_Market_leadership.py:137,209,217,218,223`
- `src/pages/5_Wallet_Intelligence.py:279,312,320`
- `src/platform_health.py:304,337,532,537`
- `src/portfolio_overlap_engine.py:106`
- `src/position_evolution_engine.py:503,1917`
- `src/signal_fusion_engine.py:722,731,738`
- `src/wallet_coverage.py:21`
- `src/wallet_dna_engine_backup.py:515,526,533`
- `src/wallet_intelligence_engine.py:256,282,329`
- `src/wallet_intelligence_source.py:21`
- `src/wallet_performance_engine.py:428,439,446`
- `src/wallet_profiler.py:176,177,179`
- `src/wallet_rating_engine.py:115`
- `src/wallet_trade_ledger.py:264,273,380,381,392,395,604,606,608,650,676,759,760`
- `src/weighted_consensus_engine.py:131`

#### Create SQL

```sql
CREATE TABLE wallet_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,
            scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
```

### `wallet_status_history`

- Row count: `1308`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | previous_status | TEXT | False | — | 0 |
| 3 | new_status | TEXT | True | — | 0 |
| 4 | reason | TEXT | True | — | 0 |
| 5 | source_module | TEXT | True | — | 0 |
| 6 | changed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/candidate_qualification_engine.py:1651`
- `src/weekly_wallet_discovery.py:240,691,1249`

#### Create SQL

```sql
CREATE TABLE wallet_status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                previous_status TEXT,
                new_status TEXT NOT NULL,
                reason TEXT NOT NULL,
                source_module TEXT NOT NULL,
                changed_at TEXT NOT NULL
            )
```

### `wallet_trade_events`

- Row count: `17715`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | trade_event_key | TEXT | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | previous_scan_id | INTEGER | False | — | 0 |
| 3 | current_scan_id | INTEGER | True | — | 0 |
| 4 | previous_scanned_at | TEXT | False | — | 0 |
| 5 | current_scanned_at | TEXT | True | — | 0 |
| 6 | market_id | TEXT | True | — | 0 |
| 7 | title | TEXT | False | — | 0 |
| 8 | outcome | TEXT | False | — | 0 |
| 9 | event_type | TEXT | True | — | 0 |
| 10 | event_sequence | INTEGER | True | — | 0 |
| 11 | previous_shares | REAL | True | 0 | 0 |
| 12 | current_shares | REAL | True | 0 | 0 |
| 13 | share_change | REAL | True | 0 | 0 |
| 14 | previous_average_price | REAL | False | — | 0 |
| 15 | current_average_price | REAL | False | — | 0 |
| 16 | inferred_trade_price | REAL | False | — | 0 |
| 17 | previous_current_price | REAL | False | — | 0 |
| 18 | current_current_price | REAL | False | — | 0 |
| 19 | previous_current_value | REAL | True | 0 | 0 |
| 20 | current_current_value | REAL | True | 0 | 0 |
| 21 | value_change | REAL | True | 0 | 0 |
| 22 | estimated_cash_flow | REAL | True | 0 | 0 |
| 23 | estimated_realized_pnl | REAL | False | — | 0 |
| 24 | confidence_score | REAL | True | 0 | 0 |
| 25 | explanation_json | TEXT | False | — | 0 |
| 26 | calculated_at | TEXT | True | — | 0 |
| 27 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_trade_events_market | False | c | False | wallet, market_id, outcome, current_scanned_at |
| idx_wallet_trade_events_wallet | False | c | False | wallet, current_scanned_at |
| sqlite_autoindex_wallet_trade_events_1 | True | pk | False | trade_event_key |

#### Source References

- `src/wallet_trade_ledger.py:115,147,150,902,906,1196`

#### Create SQL

```sql
CREATE TABLE wallet_trade_events (
                trade_event_key TEXT PRIMARY KEY,
                wallet TEXT NOT NULL,
                previous_scan_id INTEGER,
                current_scan_id INTEGER NOT NULL,
                previous_scanned_at TEXT,
                current_scanned_at TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT,
                outcome TEXT,
                event_type TEXT NOT NULL,
                event_sequence INTEGER NOT NULL,
                previous_shares REAL NOT NULL DEFAULT 0,
                current_shares REAL NOT NULL DEFAULT 0,
                share_change REAL NOT NULL DEFAULT 0,
                previous_average_price REAL,
                current_average_price REAL,
                inferred_trade_price REAL,
                previous_current_price REAL,
                current_current_price REAL,
                previous_current_value REAL NOT NULL DEFAULT 0,
                current_current_value REAL NOT NULL DEFAULT 0,
                value_change REAL NOT NULL DEFAULT 0,
                estimated_cash_flow REAL NOT NULL DEFAULT 0,
                estimated_realized_pnl REAL,
                confidence_score REAL NOT NULL DEFAULT 0,
                explanation_json TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `wallet_trade_ledger_history`

- Row count: `26`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | scan_count | INTEGER | False | — | 0 |
| 3 | reconstructed_position_count | INTEGER | False | — | 0 |
| 4 | open_position_count | INTEGER | False | — | 0 |
| 5 | closed_position_count | INTEGER | False | — | 0 |
| 6 | trade_event_count | INTEGER | False | — | 0 |
| 7 | estimated_realized_pnl | REAL | False | — | 0 |
| 8 | estimated_unrealized_pnl | REAL | False | — | 0 |
| 9 | total_estimated_pnl | REAL | False | — | 0 |
| 10 | complete_history_score | REAL | False | — | 0 |
| 11 | ledger_confidence | TEXT | False | — | 0 |
| 12 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/wallet_trade_ledger.py:223,932,1199`

#### Create SQL

```sql
CREATE TABLE wallet_trade_ledger_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                scan_count INTEGER,
                reconstructed_position_count INTEGER,
                open_position_count INTEGER,
                closed_position_count INTEGER,
                trade_event_count INTEGER,
                estimated_realized_pnl REAL,
                estimated_unrealized_pnl REAL,
                total_estimated_pnl REAL,
                complete_history_score REAL,
                ledger_confidence TEXT,
                observed_at TEXT NOT NULL
            )
```

### `wallet_trade_ledger_runs`

- Row count: `1`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | elapsed_seconds | REAL | False | — | 0 |
| 4 | scans_loaded | INTEGER | True | 0 | 0 |
| 5 | positions_loaded | INTEGER | True | 0 | 0 |
| 6 | wallets_processed | INTEGER | True | 0 | 0 |
| 7 | trade_events_saved | INTEGER | True | 0 | 0 |
| 8 | reconstructed_positions_saved | INTEGER | True | 0 | 0 |
| 9 | summary_rows_saved | INTEGER | True | 0 | 0 |
| 10 | history_rows_saved | INTEGER | True | 0 | 0 |
| 11 | status | TEXT | True | — | 0 |
| 12 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

None.

#### Source References

- `src/wallet_trade_ledger.py:239,981,1010`

#### Create SQL

```sql
CREATE TABLE wallet_trade_ledger_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                elapsed_seconds REAL,
                scans_loaded INTEGER NOT NULL DEFAULT 0,
                positions_loaded INTEGER NOT NULL DEFAULT 0,
                wallets_processed INTEGER NOT NULL DEFAULT 0,
                trade_events_saved INTEGER NOT NULL DEFAULT 0,
                reconstructed_positions_saved INTEGER NOT NULL DEFAULT 0,
                summary_rows_saved INTEGER NOT NULL DEFAULT 0,
                history_rows_saved INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            )
```

### `wallet_trade_ledger_summary`

- Row count: `26`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | scan_count | INTEGER | True | 0 | 0 |
| 2 | reconstructed_position_count | INTEGER | True | 0 | 0 |
| 3 | open_position_count | INTEGER | True | 0 | 0 |
| 4 | closed_position_count | INTEGER | True | 0 | 0 |
| 5 | trade_event_count | INTEGER | True | 0 | 0 |
| 6 | open_event_count | INTEGER | True | 0 | 0 |
| 7 | add_event_count | INTEGER | True | 0 | 0 |
| 8 | trim_event_count | INTEGER | True | 0 | 0 |
| 9 | close_event_count | INTEGER | True | 0 | 0 |
| 10 | estimated_buy_cost | REAL | True | 0 | 0 |
| 11 | estimated_sell_proceeds | REAL | True | 0 | 0 |
| 12 | estimated_realized_pnl | REAL | True | 0 | 0 |
| 13 | estimated_unrealized_pnl | REAL | True | 0 | 0 |
| 14 | total_estimated_pnl | REAL | True | 0 | 0 |
| 15 | average_hold_seconds | REAL | False | — | 0 |
| 16 | average_trade_size | REAL | True | 0 | 0 |
| 17 | scale_in_rate | REAL | True | 0 | 0 |
| 18 | scale_out_rate | REAL | True | 0 | 0 |
| 19 | complete_history_score | REAL | True | 0 | 0 |
| 20 | ledger_confidence | TEXT | True | 'VERY LOW' | 0 |
| 21 | first_scan_at | TEXT | False | — | 0 |
| 22 | last_scan_at | TEXT | False | — | 0 |
| 23 | explanation_json | TEXT | False | — | 0 |
| 24 | calculated_at | TEXT | True | — | 0 |
| 25 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_wallet_trade_ledger_summary_1 | True | pk | False | wallet |

#### Source References

- `src/candidate_qualification_engine.py:810`
- `src/elite_wallet_ranking_engine.py:655`
- `src/wallet_alpha_engine.py:811,816`
- `src/wallet_trade_ledger.py:194,904,909,1198`

#### Create SQL

```sql
CREATE TABLE wallet_trade_ledger_summary (
                wallet TEXT PRIMARY KEY,
                scan_count INTEGER NOT NULL DEFAULT 0,
                reconstructed_position_count INTEGER NOT NULL DEFAULT 0,
                open_position_count INTEGER NOT NULL DEFAULT 0,
                closed_position_count INTEGER NOT NULL DEFAULT 0,
                trade_event_count INTEGER NOT NULL DEFAULT 0,
                open_event_count INTEGER NOT NULL DEFAULT 0,
                add_event_count INTEGER NOT NULL DEFAULT 0,
                trim_event_count INTEGER NOT NULL DEFAULT 0,
                close_event_count INTEGER NOT NULL DEFAULT 0,
                estimated_buy_cost REAL NOT NULL DEFAULT 0,
                estimated_sell_proceeds REAL NOT NULL DEFAULT 0,
                estimated_realized_pnl REAL NOT NULL DEFAULT 0,
                estimated_unrealized_pnl REAL NOT NULL DEFAULT 0,
                total_estimated_pnl REAL NOT NULL DEFAULT 0,
                average_hold_seconds REAL,
                average_trade_size REAL NOT NULL DEFAULT 0,
                scale_in_rate REAL NOT NULL DEFAULT 0,
                scale_out_rate REAL NOT NULL DEFAULT 0,
                complete_history_score REAL NOT NULL DEFAULT 0,
                ledger_confidence TEXT NOT NULL DEFAULT 'VERY LOW',
                first_scan_at TEXT,
                last_scan_at TEXT,
                explanation_json TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `wallet_trade_positions`

- Row count: `724`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | position_key | TEXT | False | — | 1 |
| 1 | wallet | TEXT | True | — | 0 |
| 2 | market_id | TEXT | True | — | 0 |
| 3 | title | TEXT | False | — | 0 |
| 4 | outcome | TEXT | False | — | 0 |
| 5 | first_scan_id | INTEGER | False | — | 0 |
| 6 | last_scan_id | INTEGER | False | — | 0 |
| 7 | first_seen_at | TEXT | False | — | 0 |
| 8 | last_seen_at | TEXT | False | — | 0 |
| 9 | opened_at | TEXT | False | — | 0 |
| 10 | closed_at | TEXT | False | — | 0 |
| 11 | event_count | INTEGER | True | 0 | 0 |
| 12 | buy_event_count | INTEGER | True | 0 | 0 |
| 13 | sell_event_count | INTEGER | True | 0 | 0 |
| 14 | scale_in_count | INTEGER | True | 0 | 0 |
| 15 | scale_out_count | INTEGER | True | 0 | 0 |
| 16 | initial_shares | REAL | True | 0 | 0 |
| 17 | peak_shares | REAL | True | 0 | 0 |
| 18 | final_shares | REAL | True | 0 | 0 |
| 19 | total_shares_added | REAL | True | 0 | 0 |
| 20 | total_shares_removed | REAL | True | 0 | 0 |
| 21 | initial_average_price | REAL | False | — | 0 |
| 22 | latest_average_price | REAL | False | — | 0 |
| 23 | estimated_buy_cost | REAL | True | 0 | 0 |
| 24 | estimated_sell_proceeds | REAL | True | 0 | 0 |
| 25 | estimated_realized_pnl | REAL | True | 0 | 0 |
| 26 | latest_current_price | REAL | False | — | 0 |
| 27 | latest_current_value | REAL | True | 0 | 0 |
| 28 | estimated_unrealized_pnl | REAL | True | 0 | 0 |
| 29 | total_estimated_pnl | REAL | True | 0 | 0 |
| 30 | holding_seconds | INTEGER | False | — | 0 |
| 31 | position_status | TEXT | True | 'OPEN' | 0 |
| 32 | data_confidence | TEXT | True | 'LOW' | 0 |
| 33 | explanation_json | TEXT | False | — | 0 |
| 34 | calculated_at | TEXT | True | — | 0 |
| 35 | updated_at | TEXT | True | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_trade_positions_wallet | False | c | False | wallet, position_status |
| sqlite_autoindex_wallet_trade_positions_1 | True | pk | False | position_key |

#### Source References

- `src/wallet_alpha_engine.py:488,495`
- `src/wallet_trade_ledger.py:152,192,903,907,1197`

#### Create SQL

```sql
CREATE TABLE wallet_trade_positions (
                position_key TEXT PRIMARY KEY,
                wallet TEXT NOT NULL,
                market_id TEXT NOT NULL,
                title TEXT,
                outcome TEXT,
                first_scan_id INTEGER,
                last_scan_id INTEGER,
                first_seen_at TEXT,
                last_seen_at TEXT,
                opened_at TEXT,
                closed_at TEXT,
                event_count INTEGER NOT NULL DEFAULT 0,
                buy_event_count INTEGER NOT NULL DEFAULT 0,
                sell_event_count INTEGER NOT NULL DEFAULT 0,
                scale_in_count INTEGER NOT NULL DEFAULT 0,
                scale_out_count INTEGER NOT NULL DEFAULT 0,
                initial_shares REAL NOT NULL DEFAULT 0,
                peak_shares REAL NOT NULL DEFAULT 0,
                final_shares REAL NOT NULL DEFAULT 0,
                total_shares_added REAL NOT NULL DEFAULT 0,
                total_shares_removed REAL NOT NULL DEFAULT 0,
                initial_average_price REAL,
                latest_average_price REAL,
                estimated_buy_cost REAL NOT NULL DEFAULT 0,
                estimated_sell_proceeds REAL NOT NULL DEFAULT 0,
                estimated_realized_pnl REAL NOT NULL DEFAULT 0,
                latest_current_price REAL,
                latest_current_value REAL NOT NULL DEFAULT 0,
                estimated_unrealized_pnl REAL NOT NULL DEFAULT 0,
                total_estimated_pnl REAL NOT NULL DEFAULT 0,
                holding_seconds INTEGER,
                position_status TEXT NOT NULL DEFAULT 'OPEN',
                data_confidence TEXT NOT NULL DEFAULT 'LOW',
                explanation_json TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
```

### `wallet_trade_snapshots`

- Row count: `1700`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | side | TEXT | False | — | 0 |
| 4 | asset | TEXT | False | — | 0 |
| 5 | condition_id | TEXT | False | — | 0 |
| 6 | size | REAL | True | 0 | 0 |
| 7 | price | REAL | True | 0 | 0 |
| 8 | trade_timestamp | INTEGER | False | — | 0 |
| 9 | title | TEXT | False | — | 0 |
| 10 | slug | TEXT | False | — | 0 |
| 11 | event_slug | TEXT | False | — | 0 |
| 12 | outcome | TEXT | False | — | 0 |
| 13 | outcome_index | INTEGER | False | — | 0 |
| 14 | transaction_hash | TEXT | False | — | 0 |
| 15 | observed_at | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| run_id | wallet_profile_collection_runs | run_id | NO ACTION | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_trade_snapshots_wallet | False | c | False | wallet, trade_timestamp |

#### Source References

- `src/performance_analytics_engine.py:16,50`
- `src/wallet_intelligence_source.py:18`
- `src/wallet_profile_collector.py:33`

#### Create SQL

```sql
CREATE TABLE "wallet_trade_snapshots" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    wallet TEXT NOT NULL,
                    side TEXT,
                    asset TEXT,
                    condition_id TEXT,
                    size REAL NOT NULL DEFAULT 0,
                    price REAL NOT NULL DEFAULT 0,
                    trade_timestamp INTEGER,
                    title TEXT,
                    slug TEXT,
                    event_slug TEXT,
                    outcome TEXT,
                    outcome_index INTEGER,
                    transaction_hash TEXT,
                    observed_at TEXT NOT NULL,
                    FOREIGN KEY(run_id)
                        REFERENCES "wallet_profile_collection_runs"(run_id)
                        ON DELETE CASCADE
                )
```

### `wallet_trust_history`

- Row count: `10`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | id | INTEGER | False | — | 1 |
| 1 | run_id | TEXT | True | — | 0 |
| 2 | wallet | TEXT | True | — | 0 |
| 3 | trust_score | REAL | True | — | 0 |
| 4 | consensus_multiplier | REAL | True | — | 0 |
| 5 | trust_grade | TEXT | True | — | 0 |
| 6 | confidence | REAL | True | — | 0 |
| 7 | confidence_grade | TEXT | True | — | 0 |
| 8 | calculated_at | TEXT | True | — | 0 |
| 9 | methodology_version | TEXT | True | — | 0 |

#### Foreign Keys

| From | Referenced table | To | On update | On delete | Match |
|---|---|---|---|---|---|
| wallet | wallet_trust_profiles | wallet | CASCADE | CASCADE | NONE |

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_trust_history_wallet_time | False | c | False | wallet, calculated_at |

#### Source References

- `src/institutional_trust_engine.py:33`

#### Create SQL

```sql
CREATE TABLE wallet_trust_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                wallet TEXT NOT NULL,
                trust_score REAL NOT NULL,
                consensus_multiplier REAL NOT NULL,
                trust_grade TEXT NOT NULL,
                confidence REAL NOT NULL,
                confidence_grade TEXT NOT NULL,
                calculated_at TEXT NOT NULL,
                methodology_version TEXT NOT NULL,
                FOREIGN KEY(wallet) REFERENCES wallet_trust_profiles(wallet)
                    ON UPDATE CASCADE ON DELETE CASCADE
            )
```

### `wallet_trust_profiles`

- Row count: `10`
- Referenced by: `wallet_trust_history`

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | wallet | TEXT | False | — | 1 |
| 1 | username | TEXT | False | — | 0 |
| 2 | trust_score | REAL | True | 0 | 0 |
| 3 | trust_grade | TEXT | True | 'UNRATED' | 0 |
| 4 | historical_reliability | REAL | True | 0 | 0 |
| 5 | performance_quality | REAL | True | 0 | 0 |
| 6 | behavioral_discipline | REAL | True | 0 | 0 |
| 7 | predictive_timing | REAL | True | 0 | 0 |
| 8 | leadership_score | REAL | True | 0 | 0 |
| 9 | market_influence_score | REAL | True | 0 | 0 |
| 10 | evidence_quality | REAL | True | 0 | 0 |
| 11 | recent_activity_score | REAL | True | 0 | 0 |
| 12 | consensus_multiplier | REAL | True | 1 | 0 |
| 13 | confidence | REAL | True | 0 | 0 |
| 14 | confidence_grade | TEXT | True | 'VERY LOW' | 0 |
| 15 | warning_flags | TEXT | False | — | 0 |
| 16 | strengths_json | TEXT | False | — | 0 |
| 17 | explanation | TEXT | False | — | 0 |
| 18 | source_elite_rank | INTEGER | False | — | 0 |
| 19 | source_elite_tier | TEXT | False | — | 0 |
| 20 | source_influence_score | REAL | True | 0 | 0 |
| 21 | source_calculated_at | TEXT | False | — | 0 |
| 22 | calculated_at | TEXT | True | — | 0 |
| 23 | updated_at | TEXT | True | — | 0 |
| 24 | methodology_version | TEXT | True | '2.0' | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| idx_wallet_trust_multiplier | False | c | False | consensus_multiplier |
| idx_wallet_trust_score | False | c | False | trust_score, confidence |
| sqlite_autoindex_wallet_trust_profiles_1 | True | pk | False | wallet |

#### Source References

- `src/institutional_decision_engine.py:40`
- `src/institutional_decision_engine_v2.py:55`
- `src/institutional_decision_engine_v2_baseline.py:55`
- `src/institutional_decision_engine_v2_v20_backup.py:55`
- `src/institutional_decision_engine_v2_v21_backup.py:55`
- `src/institutional_trust_engine.py:32`

#### Create SQL

```sql
CREATE TABLE wallet_trust_profiles (
                wallet TEXT PRIMARY KEY,
                username TEXT,
                trust_score REAL NOT NULL DEFAULT 0,
                trust_grade TEXT NOT NULL DEFAULT 'UNRATED',
                historical_reliability REAL NOT NULL DEFAULT 0,
                performance_quality REAL NOT NULL DEFAULT 0,
                behavioral_discipline REAL NOT NULL DEFAULT 0,
                predictive_timing REAL NOT NULL DEFAULT 0,
                leadership_score REAL NOT NULL DEFAULT 0,
                market_influence_score REAL NOT NULL DEFAULT 0,
                evidence_quality REAL NOT NULL DEFAULT 0,
                recent_activity_score REAL NOT NULL DEFAULT 0,
                consensus_multiplier REAL NOT NULL DEFAULT 1,
                confidence REAL NOT NULL DEFAULT 0,
                confidence_grade TEXT NOT NULL DEFAULT 'VERY LOW',
                warning_flags TEXT,
                strengths_json TEXT,
                explanation TEXT,
                source_elite_rank INTEGER,
                source_elite_tier TEXT,
                source_influence_score REAL NOT NULL DEFAULT 0,
                source_calculated_at TEXT,
                calculated_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                methodology_version TEXT NOT NULL DEFAULT '2.0'
            )
```

### `wallet_trust_runs`

- Row count: `3`
- Referenced by: None detected

#### Columns

| Position | Name | Declared type | Not null | Default | PK position |
|---:|---|---|---|---|---:|
| 0 | run_id | TEXT | False | — | 1 |
| 1 | started_at | TEXT | True | — | 0 |
| 2 | finished_at | TEXT | False | — | 0 |
| 3 | mode | TEXT | True | — | 0 |
| 4 | methodology_version | TEXT | True | — | 0 |
| 5 | wallet_limit | INTEGER | True | — | 0 |
| 6 | min_trust_input_score | REAL | True | — | 0 |
| 7 | wallets_selected | INTEGER | True | 0 | 0 |
| 8 | wallets_analyzed | INTEGER | True | 0 | 0 |
| 9 | wallets_skipped | INTEGER | True | 0 | 0 |
| 10 | profiles_saved | INTEGER | True | 0 | 0 |
| 11 | history_saved | INTEGER | True | 0 | 0 |
| 12 | status | TEXT | True | — | 0 |
| 13 | duration_seconds | REAL | True | 0 | 0 |
| 14 | error_message | TEXT | False | — | 0 |

#### Foreign Keys

None.

#### Indexes

| Name | Unique | Origin | Partial | Columns |
|---|---|---|---|---|
| sqlite_autoindex_wallet_trust_runs_1 | True | pk | False | run_id |

#### Source References

- `src/institutional_trust_engine.py:34`

#### Create SQL

```sql
CREATE TABLE wallet_trust_runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                mode TEXT NOT NULL,
                methodology_version TEXT NOT NULL,
                wallet_limit INTEGER NOT NULL,
                min_trust_input_score REAL NOT NULL,
                wallets_selected INTEGER NOT NULL DEFAULT 0,
                wallets_analyzed INTEGER NOT NULL DEFAULT 0,
                wallets_skipped INTEGER NOT NULL DEFAULT 0,
                profiles_saved INTEGER NOT NULL DEFAULT 0,
                history_saved INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                duration_seconds REAL NOT NULL DEFAULT 0,
                error_message TEXT
            )
```

## Repository Implementation Gate

Repository classes must be generated from this specification rather than from assumed table or column names.
