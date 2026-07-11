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
    WHY-comments, and the JOURNAL.md entry itself) AND, for every file category
    touched (frontend/backend/infra), the matching reviewer-* subagent was called
    since the last edit in that category AND its verdict reads as APPROUVE (this
    used to be a Stop hook -- moved here so it gates PR creation specifically,
    instead of blocking the session from ending at all)

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
#
# Tokenized rather than a raw substring regex on the whole command string --
# `echo "please don't git merge here"` or `grep "git merge" file.py` would
# otherwise false-positive, since \bgit\s+merge\b matches anywhere in the
# string regardless of quoting. Scanning for an actual 'git' token (bare or
# path-qualified) followed by 'merge' (skipping global git flags in between)
# only matches a real invocation. Not a full shell parser -- an unquoted
# `echo git merge` as a literal argument would still match, same imprecision
# check_terraform_destructive/check_azure_cli/check_powershell still have.
# ---------------------------------------------------------------------------
def check_merge(command: str):
    tokens = shlex.split(command)
    for i, t in enumerate(tokens):
        if t != "git" and not t.endswith(("/git", "\\git")):
            continue
        j = i + 1
        while j < len(tokens) and tokens[j].startswith("-"):
            j += 1
        if j < len(tokens) and tokens[j] == "merge":
            if "--ff-only" not in tokens:
                block(
                    "Bloque par hook (CLAUDE.md > Git Workflow > Rules) : 'git merge' est interdit "
                    "pour rattraper une base -- utilise 'git rebase origin/<base>'. "
                    "(--ff-only reste autorise pour synchroniser main/dev en local avec origin.)"
                )
            return


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


def check_azure_cli(command: str):
    """Anchored to the actual `az <group> [<subgroup>...] <verb>` positional
    chain (tokens up to the first flag), not a bare word search across the
    whole command -- a prior regex-based version matched a mutating verb
    appearing anywhere, including as a flag VALUE: `az storage blob list
    --prefix create` is a read-only listing filtered to blobs whose name
    starts with "create", but the old regex flagged it as a mutating command.

    Known gap, accepted rather than fully solving az's grammar: if a global
    option appears immediately after `az` (e.g. `az --output json vm
    create ...`), there's no positional token to anchor on before hitting
    that flag. This is uncommon in how commands are actually issued in this
    project (flags conventionally come after the command, not before), so
    it's treated the same as check_merge's `-C <path>` gap -- a documented,
    accepted imprecision rather than a full command-line parser.
    """
    tokens = shlex.split(command)
    n = len(tokens)
    i = 0
    while i < n:
        if tokens[i] != "az" and not tokens[i].endswith(("/az", "\\az")):
            i += 1
            continue
        j = i + 1
        verb = None
        while j < n and not tokens[j].startswith("-"):
            verb = tokens[j]
            j += 1
        if verb in AZ_MUTATING_VERBS:
            block(
                "Bloque par hook (CLAUDE.md > Code Review Standards / Terraform Conventions) : "
                f"commande Azure CLI mutante detectee ('{' '.join(tokens[i:j])}'). Les commandes "
                "az qui creent/modifient/suppriment une ressource ne s'executent jamais en "
                "local ni depuis un agent -- seules les commandes de lecture (show/list/get...) "
                "sont autorisees."
            )
        i = max(j, i + 1)


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
# doc-writer must have run since the last edit, and every touched category
# (frontend/backend/infra) must have its reviewer-* subagent called since the
# last edit in that category, with a verdict that reads as APPROUVE.
#
# This used to be split across two hooks: doc-writer was already gated here,
# reviewer-* approval was a Stop hook (require_reviewer.py) blocking the
# session from ending. Moved onto this single gh-pr-create gate for
# consistency -- both are "must be true before this PR opens", not "must be
# true before Claude can stop talking", so this is a more precise fit and
# removes an entire hook + its per-agent cycle-limit/give-up machinery (that
# machinery existed specifically to avoid a Stop hook leaving the agent
# permanently unable to end a response; that risk doesn't apply here since
# Claude can always choose not to run `gh pr create` and report to the user
# instead, so no equivalent escape valve was carried over).
# ---------------------------------------------------------------------------
CONVENTIONAL_PREFIX = re.compile(r"^(feat|fix|chore|docs|refactor)(\([\w\-/.]+\))?:\s+\S")
WIP_MARKER = re.compile(r"(?i)(^wip\b|\bwip\b|^fixup!|^squash!|^temp[: ]|^tmp[: ])")

FRONTEND_RE = re.compile(r"JobFinder/frontend/.*\.(tsx?|jsx?|css)$")
BACKEND_RE = re.compile(r"JobFinder/python/(?!migrations/).*\.py$")
INFRA_RE = re.compile(
    r"(JobFinder/Terraform/.*\.tf$|JobFinder/python/migrations/.*\.py$|"
    r"JobFinder/powershell/.*\.ps1$|\.sql$)"
)
CATEGORY_AGENT = {
    "frontend": "reviewer-frontend",
    "backend": "reviewer-backend",
    "infra": "reviewer-infra",
}
# Both names are checked because the subagent-launching tool is called
# "Task" in Claude Code CLI transcripts and "Agent" in some Cowork contexts.
SUBAGENT_TOOL_NAMES = ("Task", "Agent")


def categorize(path: str):
    cats = set()
    if FRONTEND_RE.search(path):
        cats.add("frontend")
    if BACKEND_RE.search(path):
        cats.add("backend")
    if INFRA_RE.search(path):
        cats.add("infra")
    return cats


def extract_text(content):
    """Pull plain text out of an Anthropic-style content field, which may be
    a bare string or a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict) and isinstance(c.get("text"), str):
                parts.append(c["text"])
        return "\n".join(parts)
    return ""


def verdict_ok(report_text: str):
    """True = approved, False = changes required, None = can't tell."""
    t = report_text.upper()
    if "CHANGEMENTS REQUIS" in t:
        return False
    if "APPROUV" in t:  # matches APPROUVE / APPROUVÉ
        return True
    return None


# Reviewer subagents are required to always include a "Remarques non-bloquantes :"
# line (see .claude/agents/reviewer-*.md), even on an APPROUVE verdict, precisely
# so this can be parsed mechanically instead of relying on free-text prose.
NON_BLOCKING_REMARKS_RE = re.compile(r"remarques non-bloquantes\s*:\s*(.+)", re.IGNORECASE)
MAX_WARNING_ATTEMPTS = 3


def has_warnings(report_text: str):
    """True/False/None (line missing -- treated the same as an unclear verdict:
    conservatively counted as 'has warnings' by the caller) for whether the
    reviewer flagged non-blocking remarks on an otherwise-approved report."""
    m = NON_BLOCKING_REMARKS_RE.search(report_text)
    if not m:
        return None
    return not m.group(1).strip().lower().startswith("aucune")


def state_path_for(transcript_path: str) -> Path:
    p = Path(transcript_path)
    return p.parent / f".pr_create_warning_state.{p.stem}.json"


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(path: Path, state: dict):
    try:
        if state:
            path.write_text(json.dumps(state), encoding="utf-8")
        else:
            path.unlink(missing_ok=True)
    except Exception as e:
        # Best-effort, but NOT silent: a one-off failure just looks like a
        # reset (fine, matches the comment this used to have). A *persistent*
        # failure (e.g. permissions on the transcript's directory) means the
        # counter can never be written, so state.get(agent, 0) reads 0 on
        # every call and MAX_WARNING_ATTEMPTS is never reached -- gh pr
        # create would then block indefinitely instead of ever giving up,
        # the opposite of "just resets to 0". Surface it so that failure
        # mode is visible instead of silently assumed benign.
        sys.stderr.write(f"pre_bash_guard: impossible d'ecrire l'etat des tentatives ({e}).\n")


def docs_and_reviews_readiness(transcript_path: str):
    """Single pass over the transcript: is doc-writer up to date, and is
    every touched reviewer category approved, since the last edit?

    Returns (problems, warning_by_agent):
      - problems: list of human-readable strings for anything unconditionally
        blocking (missing doc-writer call, reviewer not recalled, or a verdict
        that isn't APPROUVE) -- empty means those hard requirements are clear.
      - warning_by_agent: {agent_name: True/False/None} for every reviewer
        whose category was touched AND whose verdict is APPROUVE -- i.e. only
        for agents where a non-blocking-remarks decision is even meaningful.
        The caller applies the capped-retry logic on top of this.

    Fails OPEN (returns ([], {})) on any structural parsing issue -- a schema
    mismatch or unreadable transcript should never leave the agent stuck,
    only a genuinely missing/stale/unapproved call should block.
    """
    if not transcript_path:
        return [], {}
    try:
        if not Path(transcript_path).exists():
            return [], {}
    except Exception:
        return [], {}

    last_edit_line = -1                  # any Edit/Write/NotebookEdit -- for doc-writer
    last_touch = {}                      # category -> (line_no, file_path) of last edit in it
    last_call_line = {"doc-writer": -1}   # subagent -> line_no of last call
    last_call_id = {"doc-writer": None}   # subagent -> tool_use id of last call
    results_by_id = {}                    # tool_use id -> result text

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
                    if not isinstance(c_block, dict):
                        continue
                    btype = c_block.get("type")

                    if btype == "tool_use":
                        name = c_block.get("name")
                        tool_input = c_block.get("input", {}) or {}

                        if name in ("Edit", "Write", "NotebookEdit"):
                            last_edit_line = line_no
                            fp = tool_input.get("file_path") or tool_input.get("notebook_path")
                            if fp:
                                for cat in categorize(fp):
                                    last_touch[cat] = (line_no, fp)

                        if name in SUBAGENT_TOOL_NAMES:
                            # Coupled to the current Task/Agent tool_use schema using
                            # exactly this key. If a future Claude Code version (or a
                            # different harness) identifies the called subagent under a
                            # different key, this silently finds nothing here -- which
                            # falls through to the same documented fail-open behaviour
                            # as an unparseable transcript, not a hard crash, but it
                            # does mean the whole gh-pr-create gate goes quiet rather
                            # than erroring loudly if that ever happens.
                            subagent = tool_input.get("subagent_type")
                            if subagent:
                                last_call_line[subagent] = line_no
                                last_call_id[subagent] = c_block.get("id")

                    elif btype == "tool_result":
                        tuid = c_block.get("tool_use_id")
                        if tuid:
                            results_by_id[tuid] = extract_text(c_block.get("content"))
    except Exception:
        return [], {}

    problems = []
    warning_by_agent = {}

    if last_call_line.get("doc-writer", -1) <= last_edit_line:
        problems.append(
            "doc-writer n'a pas tourne depuis la derniere edition (docstrings, "
            "commentaires WHY, docs/JOURNAL.md)."
        )

    for cat, agent in CATEGORY_AGENT.items():
        if cat not in last_touch:
            continue
        touch_line, touch_path = last_touch[cat]
        review_line = last_call_line.get(agent, -1)
        if review_line < touch_line:
            problems.append(
                f"{agent} n'a pas ete rappele depuis la derniere edition ({cat}) -- "
                f"dernier fichier touche : {touch_path}."
            )
            continue
        report_text = results_by_id.get(last_call_id.get(agent), "")
        if verdict_ok(report_text) is not True:
            problems.append(
                f"{agent} n'a pas rendu un verdict APPROUVE (CHANGEMENTS REQUIS, ou "
                f"indetermine) sur son dernier passage ({cat}) -- dernier fichier "
                f"touche : {touch_path}."
            )
            continue
        warning_by_agent[agent] = has_warnings(report_text)

    return problems, warning_by_agent


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
            "Bloque par hook (CLAUDE.md > Git Workflow > Enforcement via hooks) : docs/JOURNAL.md doit etre "
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
            f"Voir 'git log --oneline {base_ref}..HEAD' pour les retrouver. "
            f"Nettoie l'historique avec 'git rebase -i {base_ref}' (commits atomiques) avant "
            "d'ouvrir la PR."
        )

    # --- doc-writer up to date, and every touched category's reviewer approved ---
    problems, warning_by_agent = docs_and_reviews_readiness(transcript_path)

    # --- non-blocking remarks on an otherwise-approved reviewer: nudge up to
    # MAX_WARNING_ATTEMPTS times, then give up and let the PR open anyway ---
    state_path = state_path_for(transcript_path) if transcript_path else None
    state = load_state(state_path) if state_path else {}

    # w is True (has warnings) or None (line missing -- ambiguous, same
    # conservative stance as verdict_ok) -- only an explicit "aucune" (False)
    # clears an agent from needing another pass.
    currently_warning = {a for a, w in warning_by_agent.items() if w is not False}

    for agent in currently_warning:
        count = state.get(agent, 0) + 1
        if count > MAX_WARNING_ATTEMPTS:
            state.pop(agent, None)  # give up -- let this PR open, fresh budget next time
            continue
        state[agent] = count
        problems.append(
            f"{agent} a signale des remarques non-bloquantes sur un verdict APPROUVE -- "
            f"adresse-les puis relance 'gh pr create' (tentative {count}/{MAX_WARNING_ATTEMPTS} "
            "avant abandon de cette relance)."
        )

    for agent in list(state.keys()):
        if agent not in currently_warning:
            state.pop(agent, None)  # resolved, or no longer touched -- fresh budget next time

    if state_path:
        save_state(state_path, state)

    if problems:
        listing = "\n".join(f"  - {p}" for p in problems)
        block(
            "Bloque par hook (CLAUDE.md > Code Review Standards) : documentation/reviews pas "
            f"a jour avant l'ouverture de cette PR :\n{listing}\n"
            "Corrige puis relance 'gh pr create'."
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
