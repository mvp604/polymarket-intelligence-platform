from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict

from .models import Capability, HealthCheckResult, HealthStatus


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability, *, replace: bool = False) -> None:
        capability.validate()
        if capability.capability_id in self._capabilities and not replace:
            raise ValueError(f"Capability already registered: {capability.capability_id}")
        self._capabilities[capability.capability_id] = capability

    def get(self, capability_id: str) -> Capability:
        try:
            return self._capabilities[capability_id]
        except KeyError as exc:
            raise KeyError(f"Unknown capability: {capability_id}") from exc

    def list(self, *, enabled_only: bool = False) -> tuple[Capability, ...]:
        values = self._capabilities.values()
        if enabled_only:
            values = (item for item in values if item.enabled)
        return tuple(sorted(values, key=lambda item: item.capability_id))

    def validate_dependencies(self) -> dict[str, tuple[str, ...]]:
        installed = set(self._capabilities)
        missing = {}
        for capability in self.list(enabled_only=True):
            unresolved = tuple(d for d in capability.dependencies if d not in installed)
            if unresolved:
                missing[capability.capability_id] = unresolved
        return missing

    def dependency_order(self) -> tuple[str, ...]:
        missing = self.validate_dependencies()
        if missing:
            detail = "; ".join(f"{k}: {', '.join(v)}" for k, v in missing.items())
            raise RuntimeError(f"Missing dependencies: {detail}")
        graph = {item.capability_id: set(item.dependencies) for item in self.list(enabled_only=True)}
        reverse = defaultdict(set)
        indegree = {node: len(deps) for node, deps in graph.items()}
        for node, deps in graph.items():
            for dep in deps:
                reverse[dep].add(node)
        ready = sorted(node for node, degree in indegree.items() if degree == 0)
        order = []
        while ready:
            node = ready.pop(0)
            order.append(node)
            for dependent in sorted(reverse[node]):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
                    ready.sort()
        if len(order) != len(graph):
            cyclic = sorted(node for node, degree in indegree.items() if degree > 0)
            raise RuntimeError(f"Dependency cycle detected: {', '.join(cyclic)}")
        return tuple(order)

    def run_health_checks(self) -> dict[str, tuple[HealthCheckResult, ...]]:
        results = {}
        for capability_id in self.dependency_order():
            capability = self.get(capability_id)
            checks = []
            for check in capability.health_checks:
                try:
                    checks.append(check())
                except Exception as exc:
                    checks.append(HealthCheckResult(getattr(check, "__name__", "health_check"), HealthStatus.UNHEALTHY, f"Unhandled error: {exc}"))
            results[capability_id] = tuple(checks)
        return results

    def overall_status(self) -> HealthStatus:
        statuses = [r.status for values in self.run_health_checks().values() for r in values]
        if not statuses:
            return HealthStatus.UNKNOWN
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def to_dict(self) -> dict:
        capabilities = []
        for capability in self.list():
            data = asdict(capability)
            data.pop("health_checks", None)
            capabilities.append(data)
        return {"capabilities": capabilities, "missing_dependencies": self.validate_dependencies()}
