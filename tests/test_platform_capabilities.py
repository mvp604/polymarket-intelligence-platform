from pathlib import Path

import pytest

from src.platform_capabilities.builtin import build_registry
from src.platform_capabilities.models import Capability
from src.platform_capabilities.registry import CapabilityRegistry


def test_duplicate_rejected() -> None:
    registry = CapabilityRegistry()
    capability = Capability("example", "Example", "1.0.0", "Example")
    registry.register(capability)
    with pytest.raises(ValueError):
        registry.register(capability)


def test_missing_dependency_reported() -> None:
    registry = CapabilityRegistry()
    registry.register(Capability("dependent", "Dependent", "1.0.0", "Needs dependency", dependencies=("missing",)))
    assert registry.validate_dependencies() == {"dependent": ("missing",)}


def test_dependency_order() -> None:
    registry = CapabilityRegistry()
    registry.register(Capability("base", "Base", "1.0.0", "Base"))
    registry.register(Capability("child", "Child", "1.0.0", "Child", dependencies=("base",)))
    assert registry.dependency_order() == ("base", "child")


def test_builtin_registry(tmp_path: Path) -> None:
    for directory in ("src", "tests", "database", "runtime"):
        (tmp_path / directory).mkdir()
    (tmp_path / "manage.py").write_text("# test", encoding="utf-8")
    package = tmp_path / "src" / "platform_capabilities"
    package.mkdir()
    (package / "registry.py").write_text("# test", encoding="utf-8")
    ids = {item.capability_id for item in build_registry(tmp_path).list()}
    assert "platform.capability_registry" in ids
