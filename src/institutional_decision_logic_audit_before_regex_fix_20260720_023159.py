"""
Institutional Decision Logic Audit
Version 1.0

Purpose
-------
Trace how decision_action values are created, changed, filtered, and saved.

This audit searches Python files for:

- decision_action assignments
- BUY, AVOID, PASS, and WAIT branches
- decision thresholds
- hard-veto logic
- actionability and confidence checks
- SQL writes involving decision_action
- functions that may overwrite or normalize actions

This script is read-only.
It never modifies source files or the database.
"""

from __future__ import annotations

import argparse
import ast
import re

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)

SOURCE_ROOT = (
    PROJECT_ROOT
    / "src"
)

DEFAULT_CONTEXT_LINES = 6
DEFAULT_DISPLAY_LIMIT = 300

TARGET_ACTIONS = (
    "BUY",
    "AVOID",
    "PASS",
    "WAIT",
)

SEARCH_TERMS = (
    "decision_action",
    "BUY",
    "AVOID",
    "PASS",
    "WAIT",
    "hard_veto",
    "actionability_score",
    "decision_score",
    "confidence",
    "weighted_trust_score",
    "entry_quality_score",
    "market_structure_score",
    "data_quality_score",
    "threshold",
)

THRESHOLD_PATTERN = re.compile(
    r"""
    (?ix)
    \b(
        buy_threshold
        |avoid_threshold
        |pass_threshold
        |wait_threshold
        |minimum_[a-z0-9_]+
        |min_[a-z0-9_]+
        |maximum_[a-z0-9_]+
        |max_[a-z0-9_]+
        |[a-z0-9_]*threshold[a-z0-9_]*
        |[a-z0-9_]*cutoff[a-z0-9_]*
    )\b
    """
)

ACTION_LITERAL_PATTERN = re.compile(
    r"""(?i)(["'])(BUY|AVOID|PASS|WAIT)\1"""
)

DECISION_ASSIGNMENT_PATTERN = re.compile(
    r"""
    (?ix)
    \bdecision_action\b
    \s*
    (?:
        =
        |
        :=
    )
    """
)

SQL_DECISION_PATTERN = re.compile(
    r"""
    (?ix)
    (
        INSERT\s+INTO[\s\S]{0,800}decision_action
        |
        UPDATE[\s\S]{0,800}decision_action
        |
        decision_action[\s\S]{0,500}(VALUES|SET)
    )
    """
)


@dataclass
class Finding:
    file_path: Path
    line_number: int
    category: str
    line_text: str
    context_start: int
    context_end: int


class DecisionVisitor(
    ast.NodeVisitor
):
    def __init__(
        self,
        file_path: Path,
    ) -> None:
        self.file_path = file_path
        self.assignments: list[
            tuple[int, str]
        ] = []

        self.comparisons: list[
            tuple[int, str]
        ] = []

        self.functions: list[
            tuple[int, str]
        ] = []

        self.constants: list[
            tuple[int, str]
        ] = []

    def visit_FunctionDef(
        self,
        node: ast.FunctionDef,
    ) -> None:
        lowered = node.name.casefold()

        if any(
            term in lowered
            for term in (
                "decision",
                "action",
                "recommend",
                "grade",
                "score",
                "veto",
            )
        ):
            self.functions.append(
                (
                    node.lineno,
                    node.name,
                )
            )

        self.generic_visit(
            node
        )

    def visit_AsyncFunctionDef(
        self,
        node: ast.AsyncFunctionDef,
    ) -> None:
        self.visit_FunctionDef(
            node
        )

    def visit_Assign(
        self,
        node: ast.Assign,
    ) -> None:
        target_names = []

        for target in node.targets:
            target_names.extend(
                extract_target_names(
                    target
                )
            )

        value_text = safe_unparse(
            node.value
        )

        for name in target_names:
            lowered = name.casefold()

            if (
                "decision_action" in lowered
                or lowered in {
                    "action",
                    "recommendation",
                }
            ):
                self.assignments.append(
                    (
                        node.lineno,
                        (
                            f"{name} = "
                            f"{value_text}"
                        ),
                    )
                )

            if THRESHOLD_PATTERN.search(
                name
            ):
                self.constants.append(
                    (
                        node.lineno,
                        (
                            f"{name} = "
                            f"{value_text}"
                        ),
                    )
                )

        self.generic_visit(
            node
        )

    def visit_AnnAssign(
        self,
        node: ast.AnnAssign,
    ) -> None:
        names = extract_target_names(
            node.target
        )

        value_text = safe_unparse(
            node.value
        )

        for name in names:
            lowered = name.casefold()

            if (
                "decision_action" in lowered
                or lowered in {
                    "action",
                    "recommendation",
                }
            ):
                self.assignments.append(
                    (
                        node.lineno,
                        (
                            f"{name} = "
                            f"{value_text}"
                        ),
                    )
                )

            if THRESHOLD_PATTERN.search(
                name
            ):
                self.constants.append(
                    (
                        node.lineno,
                        (
                            f"{name} = "
                            f"{value_text}"
                        ),
                    )
                )

        self.generic_visit(
            node
        )

    def visit_Compare(
        self,
        node: ast.Compare,
    ) -> None:
        text = safe_unparse(
            node
        )

        lowered = text.casefold()

        if any(
            term.casefold() in lowered
            for term in SEARCH_TERMS
        ):
            self.comparisons.append(
                (
                    node.lineno,
                    text,
                )
            )

        self.generic_visit(
            node
        )


def safe_unparse(
    node: ast.AST | None,
) -> str:
    if node is None:
        return "None"

    try:
        return ast.unparse(
            node
        )

    except Exception:
        return (
            f"<{type(node).__name__}>"
        )


def extract_target_names(
    node: ast.AST,
) -> list[str]:
    names: list[str] = []

    if isinstance(
        node,
        ast.Name,
    ):
        names.append(
            node.id
        )

    elif isinstance(
        node,
        ast.Attribute,
    ):
        names.append(
            node.attr
        )

    elif isinstance(
        node,
        (
            ast.Tuple,
            ast.List,
        ),
    ):
        for element in node.elts:
            names.extend(
                extract_target_names(
                    element
                )
            )

    elif isinstance(
        node,
        ast.Subscript,
    ):
        names.append(
            safe_unparse(
                node
            )
        )

    return names


def iter_python_files() -> Iterable[
    Path
]:
    for path in sorted(
        SOURCE_ROOT.rglob(
            "*.py"
        )
    ):
        if (
            path.name
            == Path(__file__).name
        ):
            continue

        if "__pycache__" in path.parts:
            continue

        if "_backup_" in path.stem:
            continue

        yield path


def classify_line(
    line: str,
) -> set[str]:
    categories: set[str] = set()

    if DECISION_ASSIGNMENT_PATTERN.search(
        line
    ):
        categories.add(
            "DECISION_ASSIGNMENT"
        )

    if ACTION_LITERAL_PATTERN.search(
        line
    ):
        categories.add(
            "ACTION_LITERAL"
        )

    if THRESHOLD_PATTERN.search(
        line
    ):
        categories.add(
            "THRESHOLD"
        )

    lowered = line.casefold()

    if "hard_veto" in lowered:
        categories.add(
            "HARD_VETO"
        )

    if "decision_action" in lowered:
        categories.add(
            "DECISION_ACTION_REFERENCE"
        )

    if any(
        term in lowered
        for term in (
            "actionability_score",
            "decision_score",
            "confidence",
            "weighted_trust_score",
            "entry_quality_score",
            "market_structure_score",
            "data_quality_score",
        )
    ):
        categories.add(
            "SCORING_REFERENCE"
        )

    if any(
        term in lowered
        for term in (
            "insert into",
            "update ",
            "on conflict",
            "values",
        )
    ) and "decision_action" in lowered:
        categories.add(
            "SQL_WRITE_REFERENCE"
        )

    return categories


def collect_text_findings(
    file_path: Path,
    lines: list[str],
    context_lines: int,
) -> list[Finding]:
    findings: list[
        Finding
    ] = []

    full_text = "\n".join(
        lines
    )

    sql_related = bool(
        SQL_DECISION_PATTERN.search(
            full_text
        )
    )

    for index, line in enumerate(
        lines,
        start=1,
    ):
        categories = classify_line(
            line
        )

        if (
            sql_related
            and "decision_action" in line.casefold()
        ):
            categories.add(
                "SQL_DECISION_CONTEXT"
            )

        for category in sorted(
            categories
        ):
            findings.append(
                Finding(
                    file_path=file_path,
                    line_number=index,
                    category=category,
                    line_text=line.rstrip(),
                    context_start=max(
                        1,
                        index - context_lines,
                    ),
                    context_end=min(
                        len(lines),
                        index + context_lines,
                    ),
                )
            )

    return findings


def print_context(
    lines: list[str],
    start: int,
    end: int,
    focus_line: int,
) -> None:
    for number in range(
        start,
        end + 1,
    ):
        marker = (
            ">>"
            if number == focus_line
            else "  "
        )

        print(
            f"{marker} {number:>5} | "
            f"{lines[number - 1]}"
        )


def print_section(
    title: str,
) -> None:
    print()
    print(title)
    print("-" * 150)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit institutional decision logic "
            "without modifying source code or data."
        )
    )

    parser.add_argument(
        "--context-lines",
        type=int,
        default=DEFAULT_CONTEXT_LINES,
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=DEFAULT_DISPLAY_LIMIT,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    context_lines = max(
        args.context_lines,
        0,
    )

    display_limit = max(
        args.display_limit,
        1,
    )

    files = list(
        iter_python_files()
    )

    all_findings: list[
        Finding
    ] = []

    ast_assignments = []
    ast_comparisons = []
    ast_functions = []
    ast_constants = []
    syntax_errors = []

    action_counts = Counter()
    files_with_actions = Counter()

    file_lines: dict[
        Path,
        list[str],
    ] = {}

    for file_path in files:
        try:
            text = file_path.read_text(
                encoding="utf-8"
            )

        except UnicodeDecodeError:
            text = file_path.read_text(
                encoding="utf-8",
                errors="replace",
            )

        lines = text.splitlines()

        file_lines[
            file_path
        ] = lines

        findings = collect_text_findings(
            file_path,
            lines,
            context_lines,
        )

        all_findings.extend(
            findings
        )

        file_action_set = set()

        for match in ACTION_LITERAL_PATTERN.finditer(
            text
        ):
            action = match.group(
                2
            ).upper()

            action_counts[
                action
            ] += 1

            file_action_set.add(
                action
            )

        for action in file_action_set:
            files_with_actions[
                action
            ] += 1

        try:
            tree = ast.parse(
                text,
                filename=str(
                    file_path
                ),
            )

            visitor = DecisionVisitor(
                file_path
            )

            visitor.visit(
                tree
            )

            ast_assignments.extend(
                (
                    file_path,
                    line,
                    text_value,
                )
                for line, text_value
                in visitor.assignments
            )

            ast_comparisons.extend(
                (
                    file_path,
                    line,
                    text_value,
                )
                for line, text_value
                in visitor.comparisons
            )

            ast_functions.extend(
                (
                    file_path,
                    line,
                    name,
                )
                for line, name
                in visitor.functions
            )

            ast_constants.extend(
                (
                    file_path,
                    line,
                    text_value,
                )
                for line, text_value
                in visitor.constants
            )

        except SyntaxError as error:
            syntax_errors.append(
                (
                    file_path,
                    error.lineno,
                    error.msg,
                )
            )

    category_counts = Counter(
        finding.category
        for finding in all_findings
    )

    relevant_files = sorted(
        {
            finding.file_path
            for finding in all_findings
        }
    )

    print()
    print("=" * 150)
    print(
        "POLYMARKET INSTITUTIONAL "
        "DECISION LOGIC AUDIT v1.0"
    )
    print("=" * 150)

    print(
        f"Project root:                    "
        f"{PROJECT_ROOT}"
    )

    print(
        f"Source root:                     "
        f"{SOURCE_ROOT}"
    )

    print(
        f"Python files scanned:            "
        f"{len(files):,}"
    )

    print(
        f"Relevant files detected:         "
        f"{len(relevant_files):,}"
    )

    print(
        f"Text findings:                   "
        f"{len(all_findings):,}"
    )

    print(
        f"AST decision assignments:        "
        f"{len(ast_assignments):,}"
    )

    print(
        f"AST decision comparisons:        "
        f"{len(ast_comparisons):,}"
    )

    print(
        f"AST threshold constants:         "
        f"{len(ast_constants):,}"
    )

    print(
        f"Potential decision functions:    "
        f"{len(ast_functions):,}"
    )

    print(
        f"Python syntax errors detected:   "
        f"{len(syntax_errors):,}"
    )

    print_section(
        "ACTION LITERAL DISTRIBUTION IN SOURCE"
    )

    for action in TARGET_ACTIONS:
        print(
            f"{action:<8} "
            f"occurrences={action_counts[action]:<6,} "
            f"files={files_with_actions[action]:,}"
        )

    print_section(
        "FINDING CATEGORY DISTRIBUTION"
    )

    for category, count in sorted(
        category_counts.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    ):
        print(
            f"{category:<36} "
            f"{count:,}"
        )

    print_section(
        "RELEVANT SOURCE FILES"
    )

    if relevant_files:
        for index, file_path in enumerate(
            relevant_files,
            start=1,
        ):
            relative_path = file_path.relative_to(
                PROJECT_ROOT
            )

            file_categories = Counter(
                finding.category
                for finding in all_findings
                if finding.file_path == file_path
            )

            category_summary = ", ".join(
                f"{category}={count}"
                for category, count in sorted(
                    file_categories.items()
                )
            )

            print(
                f"{index:>3}. {relative_path}"
            )

            print(
                f"     {category_summary}"
            )
    else:
        print(
            "No decision-related source files "
            "were detected."
        )

    print_section(
        "AST DECISION ACTION ASSIGNMENTS"
    )

    if ast_assignments:
        for index, (
            file_path,
            line_number,
            expression,
        ) in enumerate(
            ast_assignments[
                :display_limit
            ],
            start=1,
        ):
            print(
                f"{index:>3}. "
                f"{file_path.relative_to(PROJECT_ROOT)}"
                f":{line_number}"
            )

            print(
                f"     {expression}"
            )
    else:
        print(
            "No AST decision assignments found."
        )

    print_section(
        "AST THRESHOLD CONSTANTS"
    )

    if ast_constants:
        for index, (
            file_path,
            line_number,
            expression,
        ) in enumerate(
            ast_constants[
                :display_limit
            ],
            start=1,
        ):
            print(
                f"{index:>3}. "
                f"{file_path.relative_to(PROJECT_ROOT)}"
                f":{line_number}"
            )

            print(
                f"     {expression}"
            )
    else:
        print(
            "No threshold-style constants found."
        )

    print_section(
        "AST DECISION COMPARISONS"
    )

    if ast_comparisons:
        for index, (
            file_path,
            line_number,
            expression,
        ) in enumerate(
            ast_comparisons[
                :display_limit
            ],
            start=1,
        ):
            print(
                f"{index:>3}. "
                f"{file_path.relative_to(PROJECT_ROOT)}"
                f":{line_number}"
            )

            print(
                f"     {expression}"
            )
    else:
        print(
            "No decision-related comparisons found."
        )

    print_section(
        "POTENTIAL DECISION FUNCTIONS"
    )

    if ast_functions:
        for index, (
            file_path,
            line_number,
            function_name,
        ) in enumerate(
            ast_functions[
                :display_limit
            ],
            start=1,
        ):
            print(
                f"{index:>3}. "
                f"{file_path.relative_to(PROJECT_ROOT)}"
                f":{line_number} "
                f"{function_name}()"
            )
    else:
        print(
            "No decision-related function names found."
        )

    print_section(
        "SOURCE CONTEXT FINDINGS"
    )

    grouped_findings = sorted(
        all_findings,
        key=lambda finding: (
            str(
                finding.file_path
            ),
            finding.line_number,
            finding.category,
        ),
    )

    shown = 0
    seen_contexts = set()

    for finding in grouped_findings:
        context_key = (
            finding.file_path,
            finding.line_number,
        )

        if context_key in seen_contexts:
            continue

        seen_contexts.add(
            context_key
        )

        if shown >= display_limit:
            break

        shown += 1

        relative_path = finding.file_path.relative_to(
            PROJECT_ROOT
        )

        same_line_categories = sorted(
            {
                item.category
                for item in all_findings
                if (
                    item.file_path
                    == finding.file_path
                    and item.line_number
                    == finding.line_number
                )
            }
        )

        print()
        print(
            f"[{shown}] "
            f"{relative_path}:"
            f"{finding.line_number}"
        )

        print(
            "Categories: "
            + ", ".join(
                same_line_categories
            )
        )

        print_context(
            file_lines[
                finding.file_path
            ],
            finding.context_start,
            finding.context_end,
            finding.line_number,
        )

    remaining = (
        len(seen_contexts)
        - shown
    )

    if remaining > 0:
        print()
        print(
            f"... {remaining:,} additional "
            f"context locations omitted."
        )

    print_section(
        "SYNTAX ERRORS"
    )

    if syntax_errors:
        for file_path, line_number, message in syntax_errors:
            print(
                f"{file_path.relative_to(PROJECT_ROOT)}"
                f":{line_number or '-'} "
                f"{message}"
            )
    else:
        print(
            "No Python syntax errors detected "
            "in scanned source files."
        )

    print_section(
        "AUDIT INTERPRETATION"
    )

    if action_counts[
        "BUY"
    ] == 0:
        print(
            "CRITICAL: No BUY string literal was "
            "found anywhere in the scanned source."
        )

        print(
            "The current source may not contain "
            "a BUY decision branch."
        )

    elif not any(
        '"BUY"' in expression
        or "'BUY'" in expression
        for _, _, expression
        in ast_assignments
    ):
        print(
            "WARNING: BUY appears in source, but "
            "no direct AST assignment to BUY "
            "was detected."
        )

        print(
            "BUY may be produced indirectly, loaded "
            "from configuration, or never assigned."
        )

    else:
        print(
            "A direct BUY assignment appears to exist."
        )

        print(
            "Review its surrounding comparisons and "
            "thresholds to determine whether the branch "
            "is reachable."
        )

    if action_counts[
        "PASS"
    ] > 0:
        print(
            "PASS logic exists in the source."
        )

    if action_counts[
        "WAIT"
    ] > 0:
        print(
            "WAIT logic exists in the source."
        )

    if action_counts[
        "AVOID"
    ] > 0:
        print(
            "AVOID logic exists in the source."
        )

    print(
        "Source files modified:           NO"
    )

    print(
        "Database modified:               NO"
    )

    print(
        "Decision thresholds modified:    NO"
    )

    print(
        "Decision actions modified:       NO"
    )

    print("=" * 150)


if __name__ == "__main__":
    main()
