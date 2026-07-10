#!/usr/bin/env python3
"""
Stop hook -- best-effort enforcement of "a reviewer subagent must be called
AFTER the last edit, AND must have actually returned APPROUVE, before a task
touching frontend/backend/infra files is considered done"
(see CLAUDE.md > Code Review Standards > Reviewer subagents).

How it works: when Claude is about to stop responding, this hook walks the
session transcript in order and tracks, per category (frontend/backend/infra):
  - the line number of the LAST Edit/Write/NotebookEdit touching that category
  - the line number AND tool_use id of the LAST Task/Agent call to the
    matching reviewer-* subagent
  - the tool_result text returned for every tool_use id seen (reviewer
    subagents are instructed to always start their report with a
    "Verdict: APPROUVE / CHANGEMENTS REQUIS" line)

The stop is blocked if, for any touched category:
  (a) the reviewer was never called after the last edit in that category, or
  (b) it WAS called after the last edit, but its returned report does not
      read as APPROUVE (contains "CHANGEMENTS REQUIS", or the verdict can't
      be identified at all -- ambiguous is treated as "not approved").

Cycle limit (edit -> review -> changes required -> edit -> ...): each
reviewer gets MAX_CONSECUTIVE_BLOCKS consecutive blocks before this hook
gives up enforcing it and lets the stop through with a loud (non-blocking)
warning instead. A small per-agent counter is persisted next to the
transcript file across hook invocations for that purpose. This replaces
relying on the `stop_hook_active` flag: that flag would let a single retry
through unconditionally regardless of whether anything was actually fixed,
which defeats the point of checking the verdict at all -- an explicit,
self-owned counter is more precise than trusting an external flag whose
exact semantics aren't something this hook controls. The counter resets to
zero for a reviewer as soon as it comes back APPROUVE (or stops being
touched), so it only measures *consecutive* unresolved cycles, not a
lifetime total.

This is still best-effort, not a hard guarantee:
  - It's a keyword match on the reviewer's own report text, not semantic
    understanding of whether the underlying issues were actually fixed.
  - Ordering is at message (JSONL line) granularity.
  - Transcript parsing depends on the current JSONL schema; if that schema
    differs from what's assumed here, or a line fails to parse, this hook
    fails OPEN (allows the stop) rather than getting the session stuck. This
    fail-open only covers structural parsing failures (unreadable file,
    unexpected shape) -- an ambiguous or negative verdict on a
    successfully-parsed reviewer report is NOT treated as one of those
    failures, and still counts toward the block/cycle-limit logic above.
"""
import json
import re
import sys
from pathlib import Path

MAX_CONSECUTIVE_BLOCKS = 3

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


def state_path_for(transcript_path: str) -> Path:
    p = Path(transcript_path)
    return p.parent / f".require_reviewer_state.{p.stem}.json"


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
    except Exception:
        pass  # best-effort persistence -- a lost counter just resets to 0, not a hang


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    transcript_path = payload.get("transcript_path")
    if not transcript_path or not Path(transcript_path).exists():
        sys.exit(0)

    last_touch = {}        # category -> line_no of the most recent edit in it
    last_review_line = {}  # subagent_type -> line_no of the most recent call
    last_review_id = {}    # subagent_type -> tool_use id of the most recent call
    results_by_id = {}     # tool_use id -> result text

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

                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")

                    if btype == "tool_use":
                        name = block.get("name")
                        tool_input = block.get("input", {}) or {}

                        if name in ("Edit", "Write", "NotebookEdit"):
                            fp = tool_input.get("file_path") or tool_input.get("notebook_path")
                            if fp:
                                for cat in categorize(fp):
                                    last_touch[cat] = line_no

                        if name in SUBAGENT_TOOL_NAMES:
                            subagent = tool_input.get("subagent_type")
                            if subagent:
                                last_review_line[subagent] = line_no
                                last_review_id[subagent] = block.get("id")

                    elif btype == "tool_result":
                        tuid = block.get("tool_use_id")
                        if tuid:
                            results_by_id[tuid] = extract_text(block.get("content"))
    except Exception:
        sys.exit(0)  # fail open -- structural parsing failure, don't get the session stuck

    # Which reviewers are currently blocking, and why.
    blocking = {}  # agent -> "not_recalled" | "not_approved"
    for cat, agent in CATEGORY_AGENT.items():
        if cat not in last_touch:
            continue
        review_line = last_review_line.get(agent, -1)
        if review_line < last_touch[cat]:
            blocking[agent] = "not_recalled"
            continue
        report_text = results_by_id.get(last_review_id.get(agent), "")
        if verdict_ok(report_text) is not True:
            blocking[agent] = "not_approved"

    state_path = state_path_for(transcript_path)
    state = load_state(state_path)

    given_up = []
    still_blocking = {}
    for agent, reason in blocking.items():
        count = state.get(agent, 0) + 1
        if count > MAX_CONSECUTIVE_BLOCKS:
            given_up.append(agent)
            state.pop(agent, None)  # reset -- a future fresh failure gets its own budget
        else:
            state[agent] = count
            still_blocking[agent] = reason

    # Any agent that stopped blocking (resolved, or no longer touched) drops its counter.
    for agent in list(state.keys()):
        if agent not in blocking:
            state.pop(agent, None)

    save_state(state_path, state)

    if given_up:
        names = ", ".join(sorted(given_up))
        sys.stderr.write(
            f"AVERTISSEMENT (non bloquant) : {names} n'a pas obtenu de verdict APPROUVE apres "
            f"{MAX_CONSECUTIVE_BLOCKS} cycles consecutifs edit->review sur cette tache. Le hook "
            f"cesse de forcer une nouvelle iteration pour eviter une boucle infinie -- une "
            f"verification manuelle est necessaire avant de faire confiance a ce travail.\n"
        )

    if still_blocking:
        not_recalled = sorted(a for a, r in still_blocking.items() if r == "not_recalled")
        not_approved = sorted(a for a, r in still_blocking.items() if r == "not_approved")
        msg = "Bloque par hook (CLAUDE.md > Code Review Standards) :\n"
        if not_recalled:
            msg += (
                f"- Pas rappele depuis la derniere edition : {', '.join(not_recalled)}. "
                f"Relance-le.\n"
            )
        if not_approved:
            msg += (
                f"- Dernier verdict pas APPROUVE (CHANGEMENTS REQUIS ou indetermine) : "
                f"{', '.join(not_approved)}. Adresse les points souleves puis relance-le.\n"
            )
        msg += f"(tentative {max(state.get(a, 1) for a in still_blocking)}/{MAX_CONSECUTIVE_BLOCKS} avant abandon de l'enforcement pour ce(s) reviewer(s))\n"
        sys.stderr.write(msg)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
