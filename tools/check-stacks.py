#!/usr/bin/env python3
"""Check the stack pipelines before they run: every runAtom names an atom that exists and inputs it declares.

A pipeline that names an input the atom does not have fails at build time with a message about the task, which is a
slow way to find a typo. This reads the Jenkinsfiles the way the plugin will — atom code, version, input names — and
compares them with each atom's task.json.

    python3 tools/check-stacks.py
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path

DEMOS = Path(__file__).resolve().parent.parent
SOURCES = Path(os.environ.get("ATOM_SOURCES", Path.home() / "Codes"))

CALL = re.compile(r"runAtom\s*\(")
ATOM = re.compile(r"atom:\s*'([^']+)'")
VERSION = re.compile(r"version:\s*'([^']*)'")
INPUT_KEY = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*'")


def atoms() -> dict[str, dict]:
    found: dict[str, dict] = {}
    for repo in sorted(glob.glob(str(SOURCES / "jenkins-atom-*"))):
        task_file = Path(repo) / "task.json"
        if not task_file.is_file():
            continue
        try:
            task = json.loads(task_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if task.get("atomCode"):
            found[task["atomCode"]] = task
    return found


def calls(text: str) -> list[str]:
    """Each runAtom(...) call, with balanced parentheses (an inputs map can hold nested brackets)."""
    out: list[str] = []
    for match in CALL.finditer(text):
        depth, index = 0, match.end() - 1
        while index < len(text):
            if text[index] == "(":
                depth += 1
            elif text[index] == ")":
                depth -= 1
                if depth == 0:
                    out.append(text[match.start():index + 1])
                    break
            index += 1
    return out


def main() -> int:
    known = atoms()
    problems: list[str] = []
    count = 0
    for path in sorted(DEMOS.glob("stacks/*/Jenkinsfile*")):
        text = path.read_text(encoding="utf-8")
        for call in calls(text):
            count += 1
            code = ATOM.search(call)
            if not code:
                problems.append(f"{path.relative_to(DEMOS)}: runAtom without an atom code")
                continue
            code = code.group(1)
            task = known.get(code)
            if task is None:
                problems.append(f"{path.relative_to(DEMOS)}: no such atom: {code}")
                continue
            version = VERSION.search(call)
            if version is None:
                problems.append(f"{path.relative_to(DEMOS)}: {code} has no version")
            elif not re.fullmatch(r"\d+\.(latest|\*)|\d+\.\d+\.\d+", version.group(1)):
                problems.append(f"{path.relative_to(DEMOS)}: {code} version {version.group(1)!r} is not a version")
            declared = set((task.get("input") or {}).keys())
            inputs = call.split("inputs:", 1)
            if len(inputs) > 1:
                block = inputs[1].split(")", 1)[0]
                for name in INPUT_KEY.findall(block):
                    if name not in declared:
                        problems.append(f"{path.relative_to(DEMOS)}: {code} has no input {name!r} "
                                        f"(declared: {', '.join(sorted(declared))})")

    if problems:
        print("stack pipelines do not match the atoms:", file=sys.stderr)
        for one in problems:
            print("  " + one, file=sys.stderr)
        return 1
    print(f"{count} runAtom call(s) in stacks/* are valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
