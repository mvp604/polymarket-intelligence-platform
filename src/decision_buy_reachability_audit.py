
from __future__ import annotations

import argparse
import ast
import textwrap
from dataclasses import dataclass
from pathlib import Path


EXCLUDED_NAME_PARTS = (
    "_backup",
    "_audit",
    "__pycache__",
)


@dataclass(frozen=True)
class BuyReference:
    file_path: Path
    line_number: int
    end_line_number: int
    function_name: str
    class_name: str
    reference_type: str
    source_text: str


def should_scan(path: Path) -> bool:
    name_lower = path.name.lower()

    if path.suffix.lower() != ".py":
        return False

    return not any(
        part in name_lower
        for part in EXCLUDED_NAME_PARTS
    )


def get_source_segment(
    lines: list[str],
    start_line: int,
    end_line: int,
    context_lines: int,
) -> str:
    first = max(
        1,
        start_line - context_lines,
    )

    last = min(
        len(lines),
        end_line + context_lines,
    )

    output: list[str] = []

    for line_number in range(
        first,
        last + 1,
    ):
        marker = ">>" if (
            start_line
            <= line_number
            <= end_line
        ) else "  "

        output.append(
            f"{marker} {line_number:5d} | "
            f"{lines[line_number - 1]}"
        )

    return "\n".join(output)


def contains_buy_string(
    node: ast.AST,
) -> bool:
    for child in ast.walk(node):
        if (
            isinstance(
                child,
                ast.Constant,
            )
            and isinstance(
                child.value,
                str,
            )
            and child.value.upper() == "BUY"
        ):
            return True

    return False


def classify_reference(
    node: ast.AST,
) -> str:
    if isinstance(
        node,
        ast.Return,
    ):
        return "RETURN"

    if isinstance(
        node,
        ast.Assign,
    ):
        return "ASSIGNMENT"

    if isinstance(
        node,
        ast.AnnAssign,
    ):
        return "ANNOTATED_ASSIGNMENT"

    if isinstance(
        node,
        ast.NamedExpr,
    ):
        return "WALRUS_ASSIGNMENT"

    if isinstance(
        node,
        ast.Dict,
    ):
        return "DICTIONARY_MAPPING"

    if isinstance(
        node,
        ast.Compare,
    ):
        return "COMPARISON"

    if isinstance(
        node,
        ast.If,
    ):
        return "IF_BRANCH"

    if isinstance(
        node,
        ast.Call,
    ):
        return "FUNCTION_CALL"

    if isinstance(
        node,
        ast.MatchCase,
    ):
        return "MATCH_CASE"

    if isinstance(
        node,
        ast.Expr,
    ):
        return "EXPRESSION"

    return type(node).__name__.upper()


class BuyVisitor(ast.NodeVisitor):
    def __init__(
        self,
        file_path: Path,
        lines: list[str],
        context_lines: int,
    ) -> None:
        self.file_path = file_path
        self.lines = lines
        self.context_lines = context_lines

        self.function_stack: list[str] = []
        self.class_stack: list[str] = []

        self.references: list[
            BuyReference
        ] = []

        self.seen_locations: set[
            tuple[
                int,
                int,
                str,
            ]
        ] = set()

    def current_function(
        self,
    ) -> str:
        if not self.function_stack:
            return "<module>"

        return self.function_stack[-1]

    def current_class(
        self,
    ) -> str:
        if not self.class_stack:
            return "<none>"

        return self.class_stack[-1]

    def record(
        self,
        node: ast.AST,
        reference_type: str | None = None,
    ) -> None:
        start_line = getattr(
            node,
            "lineno",
            1,
        )

        end_line = getattr(
            node,
            "end_lineno",
            start_line,
        )

        resolved_type = (
            reference_type
            or classify_reference(node)
        )

        location_key = (
            start_line,
            end_line,
            resolved_type,
        )

        if location_key in self.seen_locations:
            return

        self.seen_locations.add(
            location_key
        )

        self.references.append(
            BuyReference(
                file_path=self.file_path,
                line_number=start_line,
                end_line_number=end_line,
                function_name=(
                    self.current_function()
                ),
                class_name=(
                    self.current_class()
                ),
                reference_type=resolved_type,
                source_text=(
                    get_source_segment(
                        self.lines,
                        start_line,
                        end_line,
                        self.context_lines,
                    )
                ),
            )
        )

    def visit_ClassDef(
        self,
        node: ast.ClassDef,
    ) -> None:
        self.class_stack.append(
            node.name
        )

        self.generic_visit(node)

        self.class_stack.pop()

    def visit_FunctionDef(
        self,
        node: ast.FunctionDef,
    ) -> None:
        self.function_stack.append(
            node.name
        )

        self.generic_visit(node)

        self.function_stack.pop()

    def visit_AsyncFunctionDef(
        self,
        node: ast.AsyncFunctionDef,
    ) -> None:
        self.function_stack.append(
            node.name
        )

        self.generic_visit(node)

        self.function_stack.pop()

    def visit_Return(
        self,
        node: ast.Return,
    ) -> None:
        if contains_buy_string(node):
            self.record(
                node,
                "DIRECT_OR_INDIRECT_RETURN",
            )

        self.generic_visit(node)

    def visit_Assign(
        self,
        node: ast.Assign,
    ) -> None:
        if contains_buy_string(node):
            self.record(
                node,
                "ASSIGNMENT_OR_MAPPING",
            )

        self.generic_visit(node)

    def visit_AnnAssign(
        self,
        node: ast.AnnAssign,
    ) -> None:
        if contains_buy_string(node):
            self.record(
                node,
                "ANNOTATED_ASSIGNMENT",
            )

        self.generic_visit(node)

    def visit_Dict(
        self,
        node: ast.Dict,
    ) -> None:
        if contains_buy_string(node):
            self.record(
                node,
                "DICTIONARY_MAPPING",
            )

        self.generic_visit(node)

    def visit_Compare(
        self,
        node: ast.Compare,
    ) -> None:
        if contains_buy_string(node):
            self.record(
                node,
                "BUY_COMPARISON",
            )

        self.generic_visit(node)

    def visit_If(
        self,
        node: ast.If,
    ) -> None:
        if contains_buy_string(
            node.test
        ):
            self.record(
                node,
                "BUY_IF_CONDITION",
            )

        self.generic_visit(node)

    def visit_Call(
        self,
        node: ast.Call,
    ) -> None:
        if contains_buy_string(node):
            self.record(
                node,
                "BUY_FUNCTION_ARGUMENT",
            )

        self.generic_visit(node)

    def visit_Constant(
        self,
        node: ast.Constant,
    ) -> None:
        if (
            isinstance(
                node.value,
                str,
            )
            and node.value.upper() == "BUY"
        ):
            self.record(
                node,
                "BUY_STRING_LITERAL",
            )


def scan_file(
    path: Path,
    context_lines: int,
) -> tuple[
    list[BuyReference],
    str | None,
]:
    source = path.read_text(
        encoding="utf-8",
    )

    lines = source.splitlines()

    try:
        tree = ast.parse(
            source,
            filename=str(path),
        )

    except SyntaxError as error:
        return [], (
            f"{path}: "
            f"{error.msg} "
            f"at line {error.lineno}"
        )

    visitor = BuyVisitor(
        file_path=path,
        lines=lines,
        context_lines=context_lines,
    )

    visitor.visit(tree)

    return (
        visitor.references,
        None,
    )


def print_reference(
    number: int,
    reference: BuyReference,
) -> None:
    print()
    print("-" * 140)

    print(
        f"[{number}] "
        f"{reference.file_path}:"
        f"{reference.line_number}"
    )

    print(
        f"Type:      "
        f"{reference.reference_type}"
    )

    print(
        f"Class:     "
        f"{reference.class_name}"
    )

    print(
        f"Function:  "
        f"{reference.function_name}"
    )

    print()

    print(
        textwrap.dedent(
            reference.source_text
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only BUY reachability audit "
            "for the Institutional Decision "
            "Engine."
        )
    )

    parser.add_argument(
        "--src",
        default="src",
        help=(
            "Source directory to scan."
        ),
    )

    parser.add_argument(
        "--context-lines",
        type=int,
        default=10,
        help=(
            "Number of source lines to show "
            "before and after each reference."
        ),
    )

    parser.add_argument(
        "--display-limit",
        type=int,
        default=200,
        help=(
            "Maximum number of BUY "
            "references to display."
        ),
    )

    args = parser.parse_args()

    src_path = Path(
        args.src
    )

    if not src_path.exists():
        raise FileNotFoundError(
            f"Source directory not found: "
            f"{src_path.resolve()}"
        )

    files = sorted(
        path
        for path in src_path.rglob(
            "*.py"
        )
        if should_scan(path)
    )

    all_references: list[
        BuyReference
    ] = []

    syntax_errors: list[str] = []

    for path in files:
        references, syntax_error = (
            scan_file(
                path,
                context_lines=max(
                    0,
                    args.context_lines,
                ),
            )
        )

        all_references.extend(
            references
        )

        if syntax_error:
            syntax_errors.append(
                syntax_error
            )

    priority = {
        "DIRECT_OR_INDIRECT_RETURN": 1,
        "ASSIGNMENT_OR_MAPPING": 2,
        "ANNOTATED_ASSIGNMENT": 3,
        "DICTIONARY_MAPPING": 4,
        "BUY_IF_CONDITION": 5,
        "BUY_COMPARISON": 6,
        "BUY_FUNCTION_ARGUMENT": 7,
        "BUY_STRING_LITERAL": 8,
    }

    all_references.sort(
        key=lambda item: (
            priority.get(
                item.reference_type,
                99,
            ),
            str(item.file_path),
            item.line_number,
        )
    )

    type_counts: dict[
        str,
        int,
    ] = {}

    for reference in all_references:
        type_counts[
            reference.reference_type
        ] = (
            type_counts.get(
                reference.reference_type,
                0,
            )
            + 1
        )

    function_locations = sorted(
        {
            (
                str(
                    reference.file_path
                ),
                reference.class_name,
                reference.function_name,
            )
            for reference
            in all_references
        }
    )

    print()
    print("=" * 140)
    print(
        "INSTITUTIONAL DECISION "
        "BUY REACHABILITY AUDIT"
    )
    print("=" * 140)

    print(
        f"Source directory:       "
        f"{src_path.resolve()}"
    )

    print(
        f"Python files scanned:   "
        f"{len(files):,}"
    )

    print(
        f"BUY references found:   "
        f"{len(all_references):,}"
    )

    print(
        f"Functions/classes:      "
        f"{len(function_locations):,}"
    )

    print(
        f"Syntax errors:          "
        f"{len(syntax_errors):,}"
    )

    print(
        "Source files modified: NO"
    )

    print(
        "Database modified:     NO"
    )

    print(
        "Thresholds modified:   NO"
    )

    print(
        "Actions modified:      NO"
    )

    print()
    print(
        "REFERENCE TYPE COUNTS"
    )
    print("-" * 140)

    if not type_counts:
        print(
            "No BUY string references "
            "were detected in active "
            "source files."
        )

    else:
        for (
            reference_type,
            count,
        ) in sorted(
            type_counts.items(),
            key=lambda item: (
                priority.get(
                    item[0],
                    99,
                ),
                item[0],
            ),
        ):
            print(
                f"{reference_type:<35} "
                f"{count:>6,}"
            )

    print()
    print(
        "FUNCTIONS AND CLASSES "
        "CONTAINING BUY"
    )
    print("-" * 140)

    if not function_locations:
        print(
            "No active function or class "
            "contains a BUY reference."
        )

    else:
        for (
            file_name,
            class_name,
            function_name,
        ) in function_locations:
            print(
                f"{file_name} | "
                f"class={class_name} | "
                f"function={function_name}"
            )

    display_limit = max(
        0,
        args.display_limit,
    )

    displayed_references = (
        all_references[
            :display_limit
        ]
    )

    print()
    print(
        "DETAILED BUY REFERENCES"
    )
    print("=" * 140)

    for (
        number,
        reference,
    ) in enumerate(
        displayed_references,
        start=1,
    ):
        print_reference(
            number,
            reference,
        )

    omitted = (
        len(all_references)
        - len(
            displayed_references
        )
    )

    if omitted > 0:
        print()

        print(
            f"{omitted:,} additional "
            f"references were omitted "
            f"by --display-limit."
        )

    print()
    print(
        "SYNTAX ERRORS"
    )
    print("-" * 140)

    if not syntax_errors:
        print(
            "No Python syntax errors "
            "detected in scanned active "
            "source files."
        )

    else:
        for syntax_error in syntax_errors:
            print(
                syntax_error
            )

    direct_returns = type_counts.get(
        "DIRECT_OR_INDIRECT_RETURN",
        0,
    )

    assignments = (
        type_counts.get(
            "ASSIGNMENT_OR_MAPPING",
            0,
        )
        + type_counts.get(
            "ANNOTATED_ASSIGNMENT",
            0,
        )
    )

    mappings = type_counts.get(
        "DICTIONARY_MAPPING",
        0,
    )

    print()
    print(
        "AUDIT INTERPRETATION"
    )
    print("-" * 140)

    if direct_returns > 0:
        print(
            "BUY appears in at least "
            "one return statement."
        )

        print(
            "Review the surrounding "
            "branch conditions shown "
            "above to determine "
            "reachability."
        )

    elif assignments > 0:
        print(
            "BUY appears to be assigned "
            "or stored, but no return "
            "containing BUY was found."
        )

        print(
            "Review how the assigned "
            "value reaches the final "
            "decision output."
        )

    elif mappings > 0:
        print(
            "BUY appears in a mapping, "
            "but no direct return or "
            "assignment path was found."
        )

        print(
            "Review which lookup key "
            "selects BUY and whether "
            "that key can be produced."
        )

    elif all_references:
        print(
            "BUY appears only in "
            "comparisons, function "
            "arguments, or string "
            "references."
        )

        print(
            "The active decision path "
            "may not currently construct "
            "or return BUY."
        )

    else:
        print(
            "No BUY reference exists in "
            "active source files after "
            "excluding backups and audits."
        )

        print(
            "BUY thresholds may exist "
            "without an active decision "
            "action implementation."
        )

    print()

    print(
        "No changes were made. "
        "This audit is read-only."
    )

    print("=" * 140)


if __name__ == "__main__":
    main()
