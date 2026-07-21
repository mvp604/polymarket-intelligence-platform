# Changelog

## [0.4.0] - 2026-07-20

### Added

- Market Type Registry plugin.
- Nineteen market-type classification rules.
- Sports betting market structures.
- Political and financial market structures.
- Market type regression tests.
- Automatic discovery of the market-types plugin.

### Market Types

- Moneyline
- Spread
- Total
- Team Total
- Player Prop
- Both Teams to Score
- Exact Score
- To Qualify
- Tournament Winner
- Season Winner
- Election Winner
- Award Winner
- Yes/No Binary
- Above/Below Threshold
- Price Target
- Range
- Resolution Event
- Method of Victory
- Winning Margin

### Changed

- Platform upgraded to 0.4.0.
- Classification Engine upgraded to 2.5.0.
- Registry upgraded to 1.2.0.
- Registry now contains 53 total rules.
- Registry now discovers three plugins.

### Preserved

- All existing sport rules.
- All existing league rules.
- Plugin-based loading architecture.
- Registry schema version 1.
- No database writes.
- No orchestrator activation.

## [0.3.1] - 2026-07-20

### Added

- Automatic registry plugin discovery.
- Dynamic registry module importing.
- Plugin rule validation.
- Plugin source diagnostics.
- Plugin manifest reporting.
- Duplicate rule ID protection.
- Registry plugin-loader tests.

### Changed

- Classification Engine upgraded to 2.4.0.
- Registry upgraded to 1.1.0.
- Registry loader no longer hardcodes sports and league imports.

### Preserved

- All 10 sport rules.
- All 24 league rules.
- Existing matching behavior.
- Existing registry schema.
- No database writes.
- No orchestrator activation.

## [0.3.0] - 2026-07-20

### Added

- Platform semantic version source.
- Classification Engine version source.
- Registry version and schema metadata.
- Registry manifest output.
- Version validation tests.

### Preserved

- Existing sport rules.
- Existing league rules.
- Existing generic matching behavior.
- No database writes.
- No orchestrator activation.



