#!/usr/bin/env python3
"""UserPromptSubmit hook: append every submitted prompt to docs/PROMPT_LOG.raw.md.

Claude Code invokes this with the hook payload as JSON on stdin; we pull out the
prompt text and append it, timestamped, to an append-only raw capture log. This
guarantees the verbatim prompt is never lost even when the curated, hand-written
narrative in docs/PROMPT_LOG.md isn't updated that turn (the gap that prompted
this hook). The curated log stays the human-readable story; this is the source.

Failures are swallowed and we always exit 0 — a logging hook must never block a
prompt from being submitted.
"""
from __future__ import annotations

import datetime
import json
import os
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    prompt = (payload.get("prompt") or "").strip("\n")
    if not prompt:
        return 0

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    log_path = os.path.join(project_dir, "docs", "PROMPT_LOG.raw.md")
    ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    quoted = "\n".join("> " + line for line in prompt.splitlines())
    entry = f"\n## {ts}\n\n{quoted}\n"

    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(entry)
    except Exception:
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
