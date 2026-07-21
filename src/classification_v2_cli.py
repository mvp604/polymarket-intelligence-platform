from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from classification_v2.classifier import classify_phase1
from classification_v2.tests import run_tests
from classification_v2.taxonomy import CLASSIFIER_VERSION


def main() -> None:
    parser = argparse.ArgumentParser(description="Market Classification Engine v2 Phase 1")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--title")
    args = parser.parse_args()

    if args.self_test:
        run_tests()
        return

    if not args.title:
        parser.error("--title is required unless --self-test is used")

    result = classify_phase1(args.title)
    payload = asdict(result)
    payload["classifier_version"] = CLASSIFIER_VERSION
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

