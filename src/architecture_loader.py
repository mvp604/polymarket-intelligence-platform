from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from architecture_registry import (
    ARCHITECTURE_REGISTRY_VERSION,
    EngineDefinition,
    EngineStatus,
    ServiceDefinition,
    ServiceName,
)


SUPPORTED_SCHEMA_VERSION = "1.0"


class ArchitectureConfigurationError(ValueError):
    """Raised when architecture configuration is invalid."""


@dataclass(frozen=True)
class ArchitectureConfiguration:
    services: tuple[ServiceDefinition, ...]
    engines: tuple[EngineDefinition, ...]
    schema_version: str
    architecture_version: str


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ArchitectureConfigurationError(
            f"Configuration file was not found: {path}"
        )

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as error:
        raise ArchitectureConfigurationError(
            f"Invalid JSON in {path}: "
            f"line {error.lineno}, column {error.colno}"
        ) from error

    if not isinstance(payload, dict):
        raise ArchitectureConfigurationError(
            f"Configuration must contain a JSON object: {path}"
        )

    return payload


def _required_string(
    record: dict[str, Any],
    field: str,
    context: str,
) -> str:
    value = record.get(field)

    if not isinstance(value, str) or not value.strip():
        raise ArchitectureConfigurationError(
            f"{context} requires a non-empty field: {field}"
        )

    return value.strip()


def _validate_header(
    payload: dict[str, Any],
    path: Path,
) -> tuple[str, str]:
    schema_version = payload.get("schema_version")
    architecture_version = payload.get(
        "architecture_version"
    )

    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ArchitectureConfigurationError(
            f"Unsupported schema_version in {path}: "
            f"{schema_version!r}"
        )

    if architecture_version != ARCHITECTURE_REGISTRY_VERSION:
        raise ArchitectureConfigurationError(
            f"architecture_version mismatch in {path}: "
            f"{architecture_version!r}; expected "
            f"{ARCHITECTURE_REGISTRY_VERSION!r}"
        )

    return schema_version, architecture_version


def load_services(
    path: Path,
) -> tuple[ServiceDefinition, ...]:
    payload = _read_json(path)
    _validate_header(payload, path)

    records = payload.get("services")

    if not isinstance(records, list):
        raise ArchitectureConfigurationError(
            "services must be a list."
        )

    services: list[ServiceDefinition] = []
    seen_names: set[ServiceName] = set()

    for index, record in enumerate(records):
        context = f"services[{index}]"

        if not isinstance(record, dict):
            raise ArchitectureConfigurationError(
                f"{context} must be an object."
            )

        raw_name = _required_string(
            record,
            "name",
            context,
        ).upper()

        description = _required_string(
            record,
            "description",
            context,
        )

        try:
            name = ServiceName(raw_name)
        except ValueError as error:
            raise ArchitectureConfigurationError(
                f"Unknown service: {raw_name}"
            ) from error

        if name in seen_names:
            raise ArchitectureConfigurationError(
                f"Duplicate service: {name.value}"
            )

        seen_names.add(name)

        services.append(
            ServiceDefinition(
                name=name,
                description=description,
            )
        )

    if not services:
        raise ArchitectureConfigurationError(
            "At least one service is required."
        )

    return tuple(services)


def load_engines(
    path: Path,
    registered_services: set[ServiceName],
) -> tuple[EngineDefinition, ...]:
    payload = _read_json(path)
    _validate_header(payload, path)

    records = payload.get("engines")

    if not isinstance(records, list):
        raise ArchitectureConfigurationError(
            "engines must be a list."
        )

    engines: list[EngineDefinition] = []
    seen_names: set[str] = set()
    seen_modules: set[str] = set()

    for index, record in enumerate(records):
        context = f"engines[{index}]"

        if not isinstance(record, dict):
            raise ArchitectureConfigurationError(
                f"{context} must be an object."
            )

        name = _required_string(
            record,
            "name",
            context,
        )

        raw_service = _required_string(
            record,
            "service",
            context,
        ).upper()

        module = _required_string(
            record,
            "module",
            context,
        )

        version = _required_string(
            record,
            "version",
            context,
        )

        raw_status = _required_string(
            record,
            "status",
            context,
        ).upper()

        description = record.get("description", "")

        if not isinstance(description, str):
            raise ArchitectureConfigurationError(
                f"{context}.description must be a string."
            )

        try:
            service = ServiceName(raw_service)
        except ValueError as error:
            raise ArchitectureConfigurationError(
                f"Unknown engine service: {raw_service}"
            ) from error

        if service not in registered_services:
            raise ArchitectureConfigurationError(
                f"Engine service is not registered: "
                f"{service.value}"
            )

        try:
            status = EngineStatus(raw_status)
        except ValueError as error:
            raise ArchitectureConfigurationError(
                f"Unknown engine status: {raw_status}"
            ) from error

        if name in seen_names:
            raise ArchitectureConfigurationError(
                f"Duplicate engine name: {name}"
            )

        if module in seen_modules:
            raise ArchitectureConfigurationError(
                f"Duplicate engine module: {module}"
            )

        seen_names.add(name)
        seen_modules.add(module)

        engines.append(
            EngineDefinition(
                name=name,
                service=service,
                module=module,
                version=version,
                status=status,
                description=description.strip(),
            )
        )

    if not engines:
        raise ArchitectureConfigurationError(
            "At least one engine is required."
        )

    return tuple(engines)


def load_architecture_configuration(
    config_directory: Path | str | None = None,
) -> ArchitectureConfiguration:
    if config_directory is None:
        project_root = Path(__file__).resolve().parents[1]

        config_directory = (
            project_root
            / "config"
            / "architecture"
        )
    else:
        config_directory = Path(config_directory)

    services_path = config_directory / "services.json"
    engines_path = config_directory / "engines.json"

    services_payload = _read_json(services_path)

    schema_version, architecture_version = (
        _validate_header(
            services_payload,
            services_path,
        )
    )

    services = load_services(services_path)

    engines = load_engines(
        engines_path,
        {
            service.name
            for service in services
        },
    )

    return ArchitectureConfiguration(
        services=services,
        engines=engines,
        schema_version=schema_version,
        architecture_version=architecture_version,
    )


if __name__ == "__main__":
    configuration = load_architecture_configuration()

    print("Architecture Configuration Loader")
    print("=" * 50)
    print(
        f"schema_version: "
        f"{configuration.schema_version}"
    )
    print(
        f"architecture_version: "
        f"{configuration.architecture_version}"
    )
    print(
        f"services: "
        f"{len(configuration.services)}"
    )
    print(
        f"engines: "
        f"{len(configuration.engines)}"
    )
