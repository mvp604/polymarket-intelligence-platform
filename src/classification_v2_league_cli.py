from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from classification_v2.league_detector import (
    classify_league,
)
from classification_v2.league_tests import (
    run_tests,
)


VERSION = "2.1.0-phase2a"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Market Classification v2 "
            "Phase 2A League Detector"
        )
    )

    parser.add_argument(
        "--self-test",
        action="store_true",
    )

    parser.add_argument(
        "--title",
    )

    args = parser.parse_args()

    if args.self_test:
        run_tests()
        return

    if not args.title:
        parser.error(
            "--title is required unless "
            "--self-test is supplied"
        )

    result = asdict(
        classify_league(args.title)
    )

    result["module_version"] = VERSION

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
