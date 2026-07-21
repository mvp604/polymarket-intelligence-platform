from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from classification_v2.market_type_tests import (
    run_tests as run_market_type_tests,
)
from classification_v2.matching_engine import (
    RegistryMatcher,
)
from classification_v2.registry.loader import (
    registry_manifest,
    registry_sources,
    registry_summary,
)
from classification_v2.registry_plugin_tests import (
    run_tests as run_plugin_tests,
)
from classification_v2.registry_tests import (
    run_tests as run_registry_tests,
)
from classification_v2.registry_version_tests import (
    run_tests as run_version_tests,
)
from classification_v2.unified_classifier import (
    classify_market,
)
from classification_v2.unified_classifier_tests import (
    run_tests as run_unified_tests,
)
from platform_version import version_info


MODULE_VERSION = "2.6.0-unified-classifier"


def print_json(
    result: dict[str, object],
) -> None:
    result["module_version"] = MODULE_VERSION

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Classification v2 Plugin-Based "
            "Registry and Unified Classifier"
        )
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
    )

    parser.add_argument(
        "--market-type-test",
        action="store_true",
    )

    parser.add_argument(
        "--plugin-test",
        action="store_true",
    )

    parser.add_argument(
        "--version-test",
        action="store_true",
    )

    parser.add_argument(
        "--unified-test",
        action="store_true",
    )

    parser.add_argument(
        "--classify",
        action="store_true",
    )

    parser.add_argument(
        "--summary",
        action="store_true",
    )

    parser.add_argument(
        "--manifest",
        action="store_true",
    )

    parser.add_argument(
        "--sources",
        action="store_true",
    )

    parser.add_argument(
        "--version",
        action="store_true",
    )

    parser.add_argument("--type")
    parser.add_argument("--title")

    args = parser.parse_args()

    if args.self_test:
        run_registry_tests()
        run_plugin_tests()
        run_market_type_tests()
        run_unified_tests()
        run_version_tests()
        return

    if args.market_type_test:
        run_market_type_tests()
        return

    if args.plugin_test:
        run_plugin_tests()
        return

    if args.version_test:
        run_version_tests()
        return

    if args.unified_test:
        run_unified_tests()
        return

    if args.classify:
        if not args.title:
            parser.error(
                "--title is required with --classify"
            )

        print_json(
            asdict(
                classify_market(
                    args.title,
                )
            )
        )

        return

    if args.summary:
        print_json(
            registry_summary()
        )

        return

    if args.manifest:
        print_json(
            registry_manifest()
        )

        return

    if args.sources:
        print_json(
            {
                "plugins": registry_sources(),
            }
        )

        return

    if args.version:
        print_json(
            version_info()
        )

        return

    if not args.type or not args.title:
        parser.error(
            "--type and --title are required "
            "unless a control flag is used"
        )

    matcher = RegistryMatcher()

    print_json(
        asdict(
            matcher.match(
                args.title,
                args.type,
            )
        )
    )


if __name__ == "__main__":
    main()
