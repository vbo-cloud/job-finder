#!/usr/bin/env python3
"""
PostToolUse auto-formatter for Edit/Write.

Keeps Terraform and frontend code aligned with what CI already checks
(terraform fmt -check, next lint) so a PR doesn't fail on formatting alone.

PostToolUse hooks run AFTER the edit already happened -- they can't block or undo
it, only react. This hook never blocks; every branch fails silently (best effort)
if the underlying tool (terraform, npx/eslint) isn't available, so it's safe to
run in any environment, including one where node_modules hasn't been installed.
"""
import json
import subprocess
import sys
from pathlib import Path


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if payload.get("tool_name") not in ("Edit", "Write"):
        sys.exit(0)

    file_path = payload.get("tool_input", {}).get("file_path")
    if not file_path:
        sys.exit(0)

    path = Path(file_path)

    if path.suffix == ".tf":
        try:
            subprocess.run(["terraform", "fmt", str(path)], capture_output=True, timeout=15)
        except Exception:
            pass
        sys.exit(0)

    if path.suffix in (".ts", ".tsx", ".js", ".jsx"):
        frontend_dir = None
        for parent in path.parents:
            if parent.name == "frontend":
                frontend_dir = parent
                break
        if frontend_dir and (frontend_dir / "node_modules").exists():
            try:
                subprocess.run(
                    ["npx", "eslint", "--fix", str(path)],
                    cwd=str(frontend_dir),
                    capture_output=True,
                    timeout=30,
                )
            except Exception:
                pass

    sys.exit(0)


if __name__ == "__main__":
    main()
