#!/usr/bin/env python3
"""PreToolUse hook — block git commits authored as Claude or carrying claude.ai/code links.

Reads the Claude Code hook JSON from stdin. Decisions are returned as JSON on stdout
per the PreToolUse contract (`hookSpecificOutput.permissionDecision = "deny"`).
Exits 0 unconditionally so unrelated bash invocations are never disrupted.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys


def _current_git_identity() -> tuple[str, str]:
    try:
        name = subprocess.check_output(
            ["git", "config", "user.name"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        name = ""
    try:
        email = subprocess.check_output(
            ["git", "config", "user.email"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        email = ""
    return name, email


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cmd = ((payload.get("tool_input") or {}).get("command")) or ""
    if not isinstance(cmd, str) or "git" not in cmd:
        sys.exit(0)

    denials: list[str] = []

    if re.search(
        r"\bgit\s+config\s+(?:--\S+\s+)*user\.(?:name|email)\s+['\"]?"
        r"(?:Claude|noreply@anthropic\.com)\b",
        cmd, re.IGNORECASE,
    ):
        denials.append("setting git config user.name/email to Claude is forbidden")

    if re.search(
        r"--author=['\"]?[^'\"]*(?:Claude|noreply@anthropic\.com)",
        cmd, re.IGNORECASE,
    ):
        denials.append("git commit --author= must not reference Claude or anthropic.com")

    is_commit = bool(re.search(r"\bgit\s+commit\b", cmd, re.IGNORECASE))

    if is_commit and "claude.ai/code" in cmd.lower():
        denials.append("commit message must not contain a claude.ai/code link")

    if is_commit:
        has_override = (
            "--author=" in cmd
            or "GIT_AUTHOR_NAME=" in cmd
            or "GIT_AUTHOR_EMAIL=" in cmd
        )
        if not has_override:
            name, email = _current_git_identity()
            if name.lower() == "claude" or email.lower() == "noreply@anthropic.com":
                denials.append(
                    f"git config identity is '{name} <{email}>'. "
                    "Pass --author=..., set GIT_AUTHOR_NAME/EMAIL, or change git config first."
                )

    if denials:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "Commit-author policy violation: " + "; ".join(denials)
                ),
            }
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
