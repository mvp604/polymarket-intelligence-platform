"""Deterministic text-template rendering for the PDK."""

from __future__ import annotations

import re
from collections.abc import Mapping


class TemplateRendererError(RuntimeError):
    """Base error raised by template rendering."""


class MissingTemplateValueError(TemplateRendererError):
    """Raised when a required template value is missing."""


class UnresolvedPlaceholderError(TemplateRendererError):
    """Raised when rendered output still contains placeholders."""


class TemplateRenderer:
    """Render simple double-brace placeholders."""

    PLACEHOLDER_PATTERN = re.compile(
        r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}"
    )

    def render(
        self,
        template: str,
        values: Mapping[str, object],
    ) -> str:
        """Render a template using the supplied values."""

        if not isinstance(template, str):
            raise TypeError(
                "template must be a string."
            )

        if not isinstance(values, Mapping):
            raise TypeError(
                "values must be a mapping."
            )

        def replace(
            match: re.Match[str],
        ) -> str:
            key = match.group(1)

            if key not in values:
                raise MissingTemplateValueError(
                    f"Missing template value: {key}"
                )

            value = values[key]

            if value is None:
                raise MissingTemplateValueError(
                    f"Template value cannot be None: {key}"
                )

            return str(value)

        rendered = self.PLACEHOLDER_PATTERN.sub(
            replace,
            template,
        )

        unresolved = sorted(
            set(
                self.PLACEHOLDER_PATTERN.findall(
                    rendered
                )
            )
        )

        if unresolved:
            raise UnresolvedPlaceholderError(
                "Unresolved placeholders: "
                + ", ".join(unresolved)
            )

        return rendered