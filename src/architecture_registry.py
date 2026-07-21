from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable


ARCHITECTURE_REGISTRY_VERSION = "0.6.0"
ARCHITECTURE_CONFIGURATION_SOURCE = "NOT_BUILT"
ARCHITECTURE_CONFIGURATION_ERROR: str | None = None


class ServiceName(str, Enum):
    INGESTION = "INGESTION"
    IDENTITY = "IDENTITY"
    MARKET_STATE = "MARKET_STATE"
    WALLET_INTELLIGENCE = "WALLET_INTELLIGENCE"
    MARKET_INTELLIGENCE = "MARKET_INTELLIGENCE"
    DECISION = "DECISION"
    LEARNING = "LEARNING"
    DELIVERY = "DELIVERY"
    ORCHESTRATION = "ORCHESTRATION"
    LEGACY = "LEGACY"


class EngineStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEVELOPMENT = "DEVELOPMENT"
    PAUSED = "PAUSED"
    LEGACY = "LEGACY"
    RETIRED = "RETIRED"


class WritePolicy(str, Enum):
    SINGLE_OWNER = "SINGLE_OWNER"
    APPEND_ONLY = "APPEND_ONLY"
    CURRENT_SNAPSHOT = "CURRENT_SNAPSHOT"
    READ_ONLY = "READ_ONLY"
    LEGACY_FROZEN = "LEGACY_FROZEN"


@dataclass(frozen=True)
class ServiceDefinition:
    name: ServiceName
    description: str


@dataclass(frozen=True)
class EngineDefinition:
    name: str
    service: ServiceName
    module: str
    version: str
    status: EngineStatus
    description: str = ""


@dataclass(frozen=True)
class TableDefinition:
    name: str
    owner_service: ServiceName
    writer_module: str
    write_policy: WritePolicy
    description: str = ""


@dataclass(frozen=True)
class ContractDefinition:
    name: str
    version: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...] = ()
    description: str = ""


class ArchitectureRegistry:
    """
    Central read-only registry for platform architecture definitions.

    The initial version stores definitions in memory. Later releases
    will load the same definitions from version-controlled JSON files.
    """

    def __init__(self) -> None:
        self._services: dict[ServiceName, ServiceDefinition] = {}
        self._engines: dict[str, EngineDefinition] = {}
        self._tables: dict[str, TableDefinition] = {}
        self._contracts: dict[str, ContractDefinition] = {}

    @staticmethod
    def _normalize_name(value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("Registry names cannot be empty.")

        return normalized

    def register_service(
        self,
        service: ServiceDefinition,
    ) -> None:
        if service.name in self._services:
            raise ValueError(
                f"Service already registered: {service.name.value}"
            )

        self._services[service.name] = service

    def register_engine(
        self,
        engine: EngineDefinition,
    ) -> None:
        engine_name = self._normalize_name(engine.name)

        if engine.service not in self._services:
            raise ValueError(
                f"Engine service is not registered: "
                f"{engine.service.value}"
            )

        if engine_name in self._engines:
            raise ValueError(
                f"Engine already registered: {engine_name}"
            )

        self._engines[engine_name] = engine

    def register_table(
        self,
        table: TableDefinition,
    ) -> None:
        table_name = self._normalize_name(table.name)

        if table.owner_service not in self._services:
            raise ValueError(
                f"Table owner service is not registered: "
                f"{table.owner_service.value}"
            )

        if table_name in self._tables:
            raise ValueError(
                f"Table already registered: {table_name}"
            )

        self._tables[table_name] = table

    def register_contract(
        self,
        contract: ContractDefinition,
    ) -> None:
        contract_name = self._normalize_name(contract.name)

        if contract_name in self._contracts:
            raise ValueError(
                f"Contract already registered: {contract_name}"
            )

        required_fields = set(contract.required_fields)
        optional_fields = set(contract.optional_fields)

        if not required_fields:
            raise ValueError(
                f"Contract must have required fields: "
                f"{contract_name}"
            )

        overlap = required_fields & optional_fields

        if overlap:
            raise ValueError(
                "Contract fields cannot be both required and "
                f"optional: {sorted(overlap)}"
            )

        self._contracts[contract_name] = contract

    def services(self) -> tuple[ServiceDefinition, ...]:
        return tuple(
            self._services[name]
            for name in sorted(
                self._services,
                key=lambda item: item.value,
            )
        )

    def engines(self) -> tuple[EngineDefinition, ...]:
        return tuple(
            self._engines[name]
            for name in sorted(self._engines)
        )

    def tables(self) -> tuple[TableDefinition, ...]:
        return tuple(
            self._tables[name]
            for name in sorted(self._tables)
        )

    def contracts(self) -> tuple[ContractDefinition, ...]:
        return tuple(
            self._contracts[name]
            for name in sorted(self._contracts)
        )

    def get_service(
        self,
        service_name: ServiceName | str,
    ) -> ServiceDefinition | None:
        try:
            normalized = (
                service_name
                if isinstance(service_name, ServiceName)
                else ServiceName(service_name.strip().upper())
            )
        except ValueError:
            return None

        return self._services.get(normalized)

    def get_engine(
        self,
        engine_name: str,
    ) -> EngineDefinition | None:
        return self._engines.get(engine_name.strip())

    def get_table(
        self,
        table_name: str,
    ) -> TableDefinition | None:
        return self._tables.get(table_name.strip())

    def get_contract(
        self,
        contract_name: str,
    ) -> ContractDefinition | None:
        return self._contracts.get(contract_name.strip())

    def engines_for_service(
        self,
        service_name: ServiceName | str,
    ) -> tuple[EngineDefinition, ...]:
        service = self.get_service(service_name)

        if service is None:
            return ()

        return tuple(
            engine
            for engine in self.engines()
            if engine.service == service.name
        )

    def tables_for_service(
        self,
        service_name: ServiceName | str,
    ) -> tuple[TableDefinition, ...]:
        service = self.get_service(service_name)

        if service is None:
            return ()

        return tuple(
            table
            for table in self.tables()
            if table.owner_service == service.name
        )

    def validate_contract_payload(
        self,
        contract_name: str,
        payload: dict[str, object],
    ) -> tuple[bool, tuple[str, ...]]:
        contract = self.get_contract(contract_name)

        if contract is None:
            return False, (
                f"Unknown contract: {contract_name}",
            )

        missing_fields = tuple(
            field
            for field in contract.required_fields
            if field not in payload
        )

        return not missing_fields, missing_fields


def _register_default_services(
    registry: ArchitectureRegistry,
) -> None:
    service_definitions = (
        ServiceDefinition(
            ServiceName.INGESTION,
            "Collects raw data from official and approved sources.",
        ),
        ServiceDefinition(
            ServiceName.IDENTITY,
            "Resolves source identifiers into canonical identities.",
        ),
        ServiceDefinition(
            ServiceName.MARKET_STATE,
            "Maintains normalized market status, prices and lifecycle.",
        ),
        ServiceDefinition(
            ServiceName.WALLET_INTELLIGENCE,
            "Measures wallet behavior, performance and specialization.",
        ),
        ServiceDefinition(
            ServiceName.MARKET_INTELLIGENCE,
            "Produces consensus, flow, evolution and prediction features.",
        ),
        ServiceDefinition(
            ServiceName.DECISION,
            "Combines evidence into explainable recommendations.",
        ),
        ServiceDefinition(
            ServiceName.LEARNING,
            "Evaluates outcomes, calibration and methodology changes.",
        ),
        ServiceDefinition(
            ServiceName.DELIVERY,
            "Publishes dashboards, alerts, reports and API results.",
        ),
        ServiceDefinition(
            ServiceName.ORCHESTRATION,
            "Coordinates the end-to-end platform pipeline.",
        ),
        ServiceDefinition(
            ServiceName.LEGACY,
            "Contains frozen or pending-migration components.",
        ),
    )

    for service in service_definitions:
        registry.register_service(service)


def _register_initial_engines(
    registry: ArchitectureRegistry,
) -> None:
    engines = (
        EngineDefinition(
            name="Canonical Market Identity",
            service=ServiceName.IDENTITY,
            module="canonical_market_identity_engine",
            version="1.0",
            status=EngineStatus.ACTIVE,
            description="Creates canonical market identities.",
        ),
        EngineDefinition(
            name="Market Status",
            service=ServiceName.MARKET_STATE,
            module="market_status_engine",
            version="1.0",
            status=EngineStatus.ACTIVE,
            description="Maintains normalized market lifecycle state.",
        ),
        EngineDefinition(
            name="Wallet Performance",
            service=ServiceName.WALLET_INTELLIGENCE,
            module="wallet_performance_engine",
            version="1.0",
            status=EngineStatus.ACTIVE,
            description="Measures historical wallet performance.",
        ),
        EngineDefinition(
            name="Institutional Consensus",
            service=ServiceName.MARKET_INTELLIGENCE,
            module="institutional_consensus_engine",
            version="1.0",
            status=EngineStatus.ACTIVE,
            description="Measures trusted wallet agreement.",
        ),
        EngineDefinition(
            name="Smart Money Flow",
            service=ServiceName.MARKET_INTELLIGENCE,
            module="smart_money_flow_engine",
            version="1.0",
            status=EngineStatus.ACTIVE,
            description="Measures trusted capital movement.",
        ),
        EngineDefinition(
            name="Position Evolution",
            service=ServiceName.MARKET_INTELLIGENCE,
            module="position_evolution_engine",
            version="1.0",
            status=EngineStatus.ACTIVE,
            description="Measures strengthening and weakening conviction.",
        ),
        EngineDefinition(
            name="Signal Fusion",
            service=ServiceName.DECISION,
            module="signal_fusion_engine",
            version="1.0",
            status=EngineStatus.ACTIVE,
            description="Combines independent intelligence signals.",
        ),
        EngineDefinition(
            name="Opportunity Ranking",
            service=ServiceName.DELIVERY,
            module="opportunity_ranking_engine",
            version="1.0",
            status=EngineStatus.ACTIVE,
            description="Ranks delivery-ready market opportunities.",
        ),
        EngineDefinition(
            name="Master Pipeline",
            service=ServiceName.ORCHESTRATION,
            module="continuous_master_pipeline",
            version="1.0",
            status=EngineStatus.ACTIVE,
            description="Coordinates the intelligence pipeline.",
        ),
    )

    for engine in engines:
        registry.register_engine(engine)


def _register_initial_tables(
    registry: ArchitectureRegistry,
) -> None:
    tables = (
        TableDefinition(
            name="canonical_market_identities",
            owner_service=ServiceName.IDENTITY,
            writer_module="canonical_market_identity_engine",
            write_policy=WritePolicy.SINGLE_OWNER,
        ),
        TableDefinition(
            name="market_metadata",
            owner_service=ServiceName.MARKET_STATE,
            writer_module="market_status_engine",
            write_policy=WritePolicy.SINGLE_OWNER,
        ),
        TableDefinition(
            name="wallet_performance",
            owner_service=ServiceName.WALLET_INTELLIGENCE,
            writer_module="wallet_performance_engine",
            write_policy=WritePolicy.SINGLE_OWNER,
        ),
        TableDefinition(
            name="institutional_consensus",
            owner_service=ServiceName.MARKET_INTELLIGENCE,
            writer_module="institutional_consensus_engine",
            write_policy=WritePolicy.SINGLE_OWNER,
        ),
        TableDefinition(
            name="smart_money_flow_signals",
            owner_service=ServiceName.MARKET_INTELLIGENCE,
            writer_module="smart_money_flow_engine",
            write_policy=WritePolicy.SINGLE_OWNER,
        ),
        TableDefinition(
            name="position_evolution",
            owner_service=ServiceName.MARKET_INTELLIGENCE,
            writer_module="position_evolution_engine",
            write_policy=WritePolicy.SINGLE_OWNER,
        ),
        TableDefinition(
            name="signal_fusion_scores",
            owner_service=ServiceName.DECISION,
            writer_module="signal_fusion_engine",
            write_policy=WritePolicy.SINGLE_OWNER,
        ),
        TableDefinition(
            name="ranked_market_opportunities",
            owner_service=ServiceName.DELIVERY,
            writer_module="opportunity_ranking_engine",
            write_policy=WritePolicy.CURRENT_SNAPSHOT,
        ),
        TableDefinition(
            name="master_pipeline_runs",
            owner_service=ServiceName.ORCHESTRATION,
            writer_module="continuous_master_pipeline",
            write_policy=WritePolicy.APPEND_ONLY,
        ),
    )

    for table in tables:
        registry.register_table(table)


def _register_initial_contracts(
    registry: ArchitectureRegistry,
) -> None:
    registry.register_contract(
        ContractDefinition(
            name="institutional_decision",
            version="1.0",
            required_fields=(
                "decision_id",
                "canonical_market_id",
                "canonical_outcome_id",
                "decision_action",
                "decision_score",
                "decision_grade",
                "confidence",
                "methodology_version",
                "observed_at",
            ),
            optional_fields=(
                "research_probability",
                "market_probability",
                "estimated_edge",
                "primary_reason",
                "primary_blocker",
                "risk_flags_json",
                "evidence_json",
            ),
            description="Canonical final decision contract.",
        )
    )


def build_registry_from_configuration(
    configuration: object,
) -> ArchitectureRegistry:
    """
    Build the active registry from validated JSON configuration.

    Services and engines come from configuration files. Tables and
    contracts remain built-in until their migration is completed.
    """
    registry = ArchitectureRegistry()

    services = getattr(configuration, "services")
    engines = getattr(configuration, "engines")

    for service in services:
        registry.register_service(service)

    for engine in engines:
        registry.register_engine(engine)

    _register_initial_tables(registry)
    _register_initial_contracts(registry)

    return registry


def build_default_registry(
    config_directory: Path | str | None = None,
) -> ArchitectureRegistry:
    """
    Load services and engines from JSON configuration.

    If configuration loading or validation fails, safely build the
    complete registry from the existing built-in definitions.
    """
    global ARCHITECTURE_CONFIGURATION_SOURCE
    global ARCHITECTURE_CONFIGURATION_ERROR

    try:
        sys.modules.setdefault(
            "architecture_registry",
            sys.modules[__name__],
        )

        from architecture_loader import (
            load_architecture_configuration,
        )

        configuration = load_architecture_configuration(
            config_directory
        )

        registry = build_registry_from_configuration(
            configuration
        )

        ARCHITECTURE_CONFIGURATION_SOURCE = (
            "JSON configuration"
        )
        ARCHITECTURE_CONFIGURATION_ERROR = None

        return registry

    except Exception as error:
        registry = ArchitectureRegistry()

        _register_default_services(registry)
        _register_initial_engines(registry)
        _register_initial_tables(registry)
        _register_initial_contracts(registry)

        ARCHITECTURE_CONFIGURATION_SOURCE = (
            "Built-in defaults (fallback)"
        )
        ARCHITECTURE_CONFIGURATION_ERROR = (
            f"{type(error).__name__}: {error}"
        )

        return registry


def registry_summary(
    registry: ArchitectureRegistry,
) -> dict[str, int | str]:
    return {
        "architecture_registry_version": ARCHITECTURE_REGISTRY_VERSION,
        "services": len(registry.services()),
        "engines": len(registry.engines()),
        "tables": len(registry.tables()),
        "contracts": len(registry.contracts()),
    }


if __name__ == "__main__":
    architecture_registry = build_default_registry()

    print("Architecture Registry")
    print("=" * 50)
    print(
        "configuration_source: "
        f"{ARCHITECTURE_CONFIGURATION_SOURCE}"
    )

    if ARCHITECTURE_CONFIGURATION_ERROR is not None:
        print(
            "configuration_error: "
            f"{ARCHITECTURE_CONFIGURATION_ERROR}"
        )

    for key, value in registry_summary(
        architecture_registry
    ).items():
        print(f"{key}: {value}")
