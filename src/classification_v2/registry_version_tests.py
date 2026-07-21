from __future__ import annotations

from platform_version import version_info

from .registry.loader import registry_manifest


def assert_equal(
    actual,
    expected,
    message: str,
) -> None:
    if actual != expected:
        raise AssertionError(
            f"{message}: expected {expected!r}, "
            f"got {actual!r}"
        )


def assert_true(
    value: bool,
    message: str,
) -> None:
    if not value:
        raise AssertionError(message)


def run_tests() -> None:
    platform = version_info()
    manifest = registry_manifest()

    assert_equal(
        platform["platform_version"],
        "0.5.0",
        "Platform version",
    )

    assert_equal(
        platform["classification_engine_version"],
        "2.6.0",
        "Classification Engine version",
    )

    assert_equal(
        manifest["registry_version"],
        "1.2.0",
        "Registry version",
    )

    assert_equal(
        manifest["registry_schema_version"],
        "1",
        "Registry schema version",
    )

    assert_equal(
        manifest["registry_loader_type"],
        "plugin_discovery",
        "Registry loader type",
    )

    assert_equal(
        manifest["rule_counts"]["total"],
        53,
        "Registry total",
    )

    assert_true(
        "league" in manifest["rule_types"],
        "League rule type missing",
    )

    assert_true(
        "sport" in manifest["rule_types"],
        "Sport rule type missing",
    )

    assert_true(
        "market_type" in manifest["rule_types"],
        "Market type rule type missing",
    )

    print(
        "Versioned registry foundation tests "
        "passed: 9"
    )


if __name__ == "__main__":
    run_tests()


