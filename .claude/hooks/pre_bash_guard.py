#!/usr/bin/env python3
"""
PreToolUse guard for the Bash tool.

Enforces, mechanically, a handful of rules that CLAUDE.md already states in prose
(Git Workflow, Branch rules, Terraform Conventions, Code Review Standards) but that
previously depended on Claude remembering to follow them on every single command:

  - no direct push to main/dev
  - no force-push without --force-with-lease
  - no `git merge` to catch up a branch (rebase only) -- --ff-only sync is still allowed
  - no local `terraform apply`/`terraform destroy` (CI-only)
  - no mutating Azure CLI command (`az ... create/update/delete/set/remove/assign/deploy/
    restore/purge`) -- read-only verbs (`show`, `list`, `get` and friends) stay allowed
  - no mutating Azure PowerShell cmdlet (`New-Az*`, `Remove-Az*`, `Set-Az*`, `Update-Az*`)
  - `gh pr create` is blocked unless docs/JOURNAL.md was updated on this branch AND
    every commit since the base branch is a clean, WIP-free Conventional Commit AND
    the doc-writer subagent has run since the last edit (checks/fixes docstrings,
    WHY-comments, and the JOURNAL.md entry itself)

This hook runs identically for a local Claude Code session and for a `claude-code-action`
run in CI -- both execute the real Claude Code engine against the checked-out repo, so
both read this same `.claude/settings.json` / `.claude/hooks/`. That's what makes it a
reliable backstop for the "infra changes are never applied automatically" rule even when
Claude is running unattended in a GitHub Actions runner.

Protocol: exit 0 = allow. Exit 2 = block, with the reason on stderr (Claude sees it).
Any internal failure (git not available, can't parse JSON, etc.) fails OPEN (exit 0) --
this hook is a safety net on top of documented process and branch protection, not the
only line of defense, so it should never be the thing that leaves the agent stuck.
"""
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


def run(cmd, timeout=15):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def current_branch():
    r = run(["git", "branch", "--show-current"])
    return r.stdout.strip() if r and r.returncode == 0 and r.stdout.strip() else None


def ref_exists(ref):
    r = run(["git", "rev-parse", "--verify", ref])
    return bool(r and r.returncode == 0)


def block(reason: str):
    sys.stderr.write(reason + "\n")
    sys.exit(2)


# ---------------------------------------------------------------------------
# git push -- direct push to main/dev, and unsafe force-push
# ---------------------------------------------------------------------------
def check_push(command: str):
    tokens = shlex.split(command)
    if "push" not in tokens:
        return
    rest = tokens[tokens.index("push") + 1:]

    has_force = any(t in ("-f", "--force") for t in rest)
    has_lease = any(t == "--force-with-lease" or t.startswith("--force-with-lease=") for t in rest)
    if has_force and not has_lease:
        block(
            "Bloque par hook (CLAUDE.md > Git Workflow > Rules) : un force-push doit "
            "toujours utiliser --force-with-lease, jamais -f/--force nu."
        )

    positional = [t for t in rest if not t.startswith("-")]
    refspecs = positional[1:] if len(positional) > 1 else positional

    targets = []
    if not refspecs:
        cb = current_branch()
        if cb:
            targets.append(cb)
    else:
        for r in refspecs:
            branch = r.split(":")[-1] if ":" in r else r
            if branch == "HEAD":
                cb = current_branch()
                branch = cb or branch
            targets.append(branch)

    if any(t in ("main", "dev") for t in targets):
        block(
            "Bloque par hook (CLAUDE.md > Branch rules) : push direct vers main/dev interdit. "
            "Passe par une feature/hotfix branch puis une PR."
        )


# ---------------------------------------------------------------------------
# git merge -- rebase-only policy (the documented --ff-only sync stays allowed)
# ---------------------------------------------------------------------------
def check_merge(command: str):
    if re.search(r"\bgit\s+merge\b", command) and "--ff-only" not in command:
        block(
            "Bloque par hook (CLAUDE.md > Git Workflow > Rules) : 'git merge' est interdit "
            "pour rattraper une base -- utilise 'git rebase origin/<base>'. "
            "(--ff-only reste autorise pour synchroniser main/dev en local avec origin.)"
        )


# ---------------------------------------------------------------------------
# terraform apply/destroy -- CI-only
# ---------------------------------------------------------------------------
def check_terraform_destructive(command: str):
    m = re.search(r"\bterraform\s+(apply|destroy)\b", command)
    if m:
        verb = m.group(1)
        block(
            f"Bloque par hook (CLAUDE.md > Terraform Conventions) : 'terraform {verb}' ne "
            "s'execute jamais en local ni depuis un agent. Merge une PR -- terraformApply.yml "
            "applique lz_dev puis dev en CI. Aucune infra n'est detruite en dehors de ce pipeline."
        )


# ---------------------------------------------------------------------------
# Azure CLI -- block mutating verbs, read-only verbs stay allowed
# ---------------------------------------------------------------------------
# Not exhaustive by design: covers the common mutating verb families across `az` command
# groups. A verb that isn't in this list but still mutates state would slip through --
# this is a backstop, not a substitute for reviewer-infra's own judgment and for keeping
# real applies confined to CI.
AZ_MUTATING_VERBS = (
    "create", "update", "delete", "set", "remove", "assign",
    "deploy", "restore", "purge", "add", "start", "stop", "restart",
)
AZ_MUTATING_RE = re.compile(
    r"\baz\s+(?:[\w-]+\s+)*(" + "|".join(AZ_MUTATING_VERBS) + r")\b"
)


def check_azure_cli(command: str):
    m = AZ_MUTATING_RE.search(command)
    if m:
        block(
            "Bloque par hook (CLAUDE.md > Code Review Standards / Terraform Conventions) : "
            f"commande Azure CLI mutante detectee ('{m.group(0).strip()}'). Les commandes "
            "az qui creent/modifient/suppriment une ressource ne s'executent jamais en "
            "local ni depuis un agent -- seules les commandes de lecture (show/list/get...) "
            "sont autorisees."
        )


# ---------------------------------------------------------------------------
# Azure PowerShell -- block mutating cmdlets (New-Az*/Remove-Az*/Set-Az*/Update-Az*)
# ---------------------------------------------------------------------------
AZ_CMDLET_RE = re.compile(r"\b(New|Remove|Set|Update)-Az\w*\b", re.IGNORECASE)


def check_powershell(command: str):
    m = AZ_CMDLET_RE.search(command)
    if m:
        block(
            "Bloque par hook (CLAUDE.md > Code Review Standards / Terraform Conventions) : "
            f"cmdlet PowerShell mutant detecte ('{m.group(0)}'). New-Az*/Remove-Az*/Set-Az*/"
            "Update-Az* ne s'executent jamais en local ni depuis un agent."
        )


# ---------------------------------------------------------------------------
# gh pr create -- JOURNAL.md is mandatory, commit history must be clean,
# and the doc-writer subagent must have run since the last edit
# ---------------------------------------------------------------------------
CONVENTIONAL_PREFIX = re.compile(r"^(feat|fix|chore|docs|refactor)(\([\w\-/.]+\))?:\s+\S")
WIP_MARKER = re.compile(r"(?i)(^wip\b|\bwip\b|^fixup!|^squash!|^temp[: ]|^tmp[: ])")


def doc_writer_called_since_last_edit(transcript_path: str) -> bool:
    """True if doc-writer doesn't need to run again (already called after the
    last Edit/Write/NotebookEdit), or if the transcript can't be inspected --
    this check fails OPEN on any structural parsing issue, same reasoning as
    require_reviewer.py's Stop hook: a schema mismatch should never leave the
    agent stuck, only a genuinely missing/stale call should block.
    """
    if not transcript_path:
        return True
    try:
        if not Path(transcript_path).exists():
            return True
    except Exception:
        return True

    last_edit_line = -1
    last_doc_writer_line = -1
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                message = entry.get("message", entry)
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, list):
                    continue
                for c_block in content:
                    if not isinstance(c_block, dict) or c_block.get("type") != "tool_use":
                        continue
                    name = c_block.get("name")
                    tool_input = c_block.get("input", {}) or {}
                    if name in ("Edit", "Write", "NotebookEdit"):
                        last_edit_line = line_no
                    if name in ("Task", "Agent") and tool_input.get("subagent_type") == "doc-writer":
                        last_doc_writer_line = line_no
    except Exception:
        return True

    return last_doc_writer_line > last_edit_line


def check_pr_create(command: str, transcript_path: str = ""):
    if "gh pr create" not in command:
        return

    branch = current_branch()
    if not branch:
        return

    base_match = re.search(r"--base[=\s]+(\S+)", command)
    if base_match:
        base = base_match.group(1)
    elif branch.startswith("hotfix/"):
        base = "main"
    else:
        base = "dev"

    base_ref = f"origin/{base}" if ref_exists(f"origin/{base}") else base
    if not ref_exists(base_ref):
        return  # can't determine range -- don't block on infra failure

    mb = run(["git", "merge-base", "HEAD", base_ref])
    if not mb or mb.returncode != 0:
        return
    merge_base = mb.stdout.strip()

    # --- docs/JOURNAL.md must be part of this PR ---
    diff = run(["git", "diff", "--name-only", merge_base, "HEAD"])
    changed = diff.stdout.splitlines() if diff and diff.returncode == 0 else []
    if "docs/JOURNAL.md" not in changed:
        block(
            "Bloque par hook (CLAUDE.md > Terraform Conventions) : docs/JOURNAL.md doit etre "
            "mis a jour AVANT d'ouvrir cette PR (numero/titre de PR, date, resume, decisions "
            "techniques). Ajoute l'entree puis relance 'gh pr create'."
        )

    # --- commit history must be clean Conventional Commits, no WIP ---
    log = run(["git", "log", "--format=%s", f"{merge_base}..HEAD"])
    subjects = log.stdout.splitlines() if log and log.returncode == 0 else []
    bad = [s for s in subjects if WIP_MARKER.search(s) or not CONVENTIONAL_PREFIX.match(s)]
    if bad:
        listing = "\n".join(f"  - {s}" for s in bad)
        block(
            "Bloque par hook (CLAUDE.md > Commit conventions / Rules) : commits non conformes "
            "sur cette branche (marqueur WIP, ou hors Conventional Commits "
            f"feat/fix/chore/docs/refactor) :\n{listing}\n"
            f"Nettoie l'historique avec 'git rebase -i {base_ref}' (commits atomiques) avant "
            "d'ouvrir la PR."
        )

    # --- doc-writer must have run since the last edit ---
    if not doc_writer_called_since_last_edit(transcript_path):
        block(
            "Bloque par hook (CLAUDE.md > Code Review Standards / Documentation) : le subagent "
            "doc-writer doit avoir tourne depuis la derniere edition avant d'ouvrir cette PR -- "
            "il verifie/corrige la documentation (docstrings, commentaires WHY, docs/JOURNAL.md). "
            "Appelle-le puis relance 'gh pr create'."
        )


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if payload.get("tool_name") != "Bash":
        sys.exit(0)

    command = payload.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    transcript_path = payload.get("transcript_path", "")

    check_push(command)
    check_merge(command)
    check_terraform_destructive(command)
    check_azure_cli(command)
    check_powershell(command)
    check_pr_create(command, transcript_path)
    sys.exit(0)


if __name__ == "__main__":
    main()
