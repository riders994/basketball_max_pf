"""A tiny stderr progress bar for the command-line season report.

The library layer (:func:`max_pf.report.season_report`) stays decoupled from any
terminal: it takes a ``progress`` callback invoked ``(completed, total)`` as each
team finishes and knows nothing about how — or whether — that gets drawn. The
command line supplies this bar as the default callback (see
:mod:`max_pf.__main__`); a programmatic caller can pass its own or leave it
``None``.

The bar is written to *stderr* on a single carriage-return-rewound line, so it
never pollutes the report/CSV on stdout and survives ``> file`` redirection of
the results.
"""
from __future__ import annotations

import sys
from typing import Callable, TextIO


def bar_callback(
    stream: TextIO | None = None, *, width: int = 30, label: str = "teams"
) -> Callable[[int, int], None]:
    """Return a ``(completed, total)`` progress callback that draws a bar.

    Each call rewinds to the start of the line with ``\\r`` and redraws, so
    successive updates animate in place; the final call (``completed >= total``)
    terminates the line with a newline. ``total`` is floored at 1 so a zero-team
    report can't divide by zero.
    """
    out = stream if stream is not None else sys.stderr

    def render(completed: int, total: int) -> None:
        total = max(total, 1)
        filled = round(width * completed / total)
        bar = "#" * filled + "-" * (width - filled)
        out.write(f"\r[{bar}] {completed}/{total} {label}")
        out.write("\n" if completed >= total else "")
        out.flush()

    return render
