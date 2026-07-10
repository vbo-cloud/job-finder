# claude-code-action — manual-only

`.github/workflows/claudeCodeAction.yml` runs [`anthropics/claude-code-action@v1`](https://github.com/anthropics/claude-code-action)
against this repo. It is **manual-only**: it never runs on its own, for any
file domain. The only way to trigger it is a human writing `@claude` in:

- a PR or issue comment
- a PR review comment (inline, on a diff line)
- a PR review body

This applies the same way to frontend, backend, and infra changes — there is
no automatic "frontend/backend auto-fixes itself" path, and consequently no
"one automatic attempt per PR" limit either. Every run was asked for by a
person.

## Why manual-only

An earlier design attempted to auto-trigger a fix commit for frontend/backend
files when the existing review bot (`reviewerAgent.yml`) posted a blocking
`REQUEST_CHANGES` review, while keeping infra gated behind an explicit
`@claude`. It was dropped before implementation: reliably telling "this PR
touches only frontend/backend" apart from "this PR also touches infra" from
workflow-level conditions, tracking a per-PR "already auto-fixed once" state
without conflating it with a later manual fix, and avoiding push races between
an automatic run and a concurrent manual one, added real correctness surface
for a marginal convenience gain. Manual-only removes all of that: nothing
ever happens without a person deciding it should.

## Why infra still can't be applied, even under manual invocation

Since a human can type `@claude` on a PR that touches Terraform, SQL
migrations, or PowerShell/Azure CLI just as easily as on a frontend PR,
staying safe there does **not** rely on this workflow refusing infra files.
It relies on what already runs inside every Claude Code session, local or in
this action, via `.claude/settings.json`:

- **`pre_bash_guard.py`** (`PreToolUse` hook on Bash) blocks `terraform
  apply`/`destroy`, mutating `az ...` commands, and mutating `New-Az*`/
  `Set-Az*`/`Remove-Az*`/`Update-Az*` PowerShell cmdlets, regardless of who
  or what invoked the session. Someone asking `@claude apply the terraform
  change` gets refused by this hook, not by the workflow declining to run.
- **`require_reviewer.py`** (`Stop` hook) still forces the matching
  `reviewer-frontend`/`reviewer-backend`/`reviewer-infra` subagent to approve
  before the session can end, for whatever category of file was actually
  touched.

The workflow passes `settings: .claude/settings.json` and
`claude_args: --allowedTools Bash,Task,Edit,Write,Read,Grep,Glob` explicitly
so both hooks (which need Bash to have anything to intercept) and the
reviewer subagents (invoked via the `Task` tool) are actually usable in CI —
this is not assumed to happen automatically just because the action checks
out the same repo.

## Required setup (manual, repo-admin only — not done by this PR)

- **`ANTHROPIC_API_KEY`** repository (or organization) secret. This is a
  different secret name from the existing `CLAUDE_API_KEY` used by
  `reviewerAgent.yml` — `claude-code-action`'s `anthropic_api_key` input
  expects this exact name. The same underlying Anthropic key can be reused
  under both secret names if that's simpler to manage.
- **The official Claude GitHub App** ([github.com/apps/claude](https://github.com/apps/claude))
  installed on this repository, with Contents/Issues/Pull requests set to
  read & write. This is what gives the action its `claude[bot]` identity for
  commits and comments.

## Known limitations / open verification items

- **Not tested end-to-end yet.** `issue_comment` / `pull_request_review` /
  `pull_request_review_comment` workflows always run the copy of the
  workflow file on the **default branch** (`main`), never the PR branch's
  copy — the same caveat `reviewerAgent.yml` already documents. Real testing
  (comment `@claude` on a frontend PR; comment `@claude apply the terraform
  change` on an infra PR and confirm the hook still blocks it) can only
  happen once this file is merged to `main`.
- **Hook/subagent inheritance in CI is asserted, not yet observed.** The
  `settings` + `--allowedTools` flags above are the mitigation for this, but
  the first real `@claude` run after merge should be treated as the actual
  verification that `pre_bash_guard.py` and `require_reviewer.py` fire as
  expected in the action's environment, not just locally.
- **Push target.** A PR-scoped `@claude` mention is expected to make Claude
  commit and push directly to the PR's existing branch (this is the point of
  responding to a PR comment). `claude-code-action` also supports creating a
  new branch (`branch_prefix`, default `claude/`) for contexts without an
  existing PR — that path shouldn't apply here, but hasn't been observed
  directly yet either.
