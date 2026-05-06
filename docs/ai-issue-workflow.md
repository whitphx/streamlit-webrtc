# AI Issue Automation Workflow

This repository ships a GitHub Actions–based workflow centered on `anthropics/claude-code-action` to lower the cost of the initial response to incoming issues. It narrows the maintainer's decision surface to a single question — "should we implement this or not?" — and automates triage, requesting missing information, implementation, and the wontfix reply.

## Overview

```
Issue created
    ↓
[claude-issue-triage] ──→ needs-info / triaged / out-of-scope
                                   ↓
                          (maintainer applies a label)
                                   ↓
                       ai-implement ─→ [implement] ─→ PR
                       wontfix      ─→ [wontfix]   ─→ closed
```

### 1. Triage phase (`claude-issue-triage.yml`)

Triggered by `issues.opened`. Claude reads the issue and routes it into one of:

- **`needs-info`**: required information (reproduction steps, expected behavior, environment, etc.) is missing. Claude posts a polite comment listing the missing items in the reporter's language.
- **`triaged`**: the report is already actionable. Claude posts a 3-5 line summary so the maintainer can grasp it at a glance.
- **`out-of-scope`**: the issue belongs to a different project (Streamlit core, aiortc, PyAV) or is a support question better suited for GitHub Discussions. Claude posts a redirection comment.

Bot-authored issues are skipped via `github.event.issue.user.type != 'Bot'`.

### 2. Label-driven implementation phase (`claude-issue-implement.yml`)

Triggered by `issues.labeled`, with two jobs that branch on the label name:

- **`ai-implement`**: the maintainer has approved implementation. Claude creates an implementation branch (`claude/issue-<number>`), runs tests/linters, adds a changelog fragment, and opens a PR.
- **`wontfix`**: the maintainer has decided not to pursue the change. Claude posts a thoughtful explanation with alternatives in the reporter's language, then closes the issue.

External PR review is handled by an existing AI review bot and is out of scope for this workflow.

## Initial setup

### 1. Register the Anthropic API key

Store the API key as a repository secret.

1. Open **Settings → Secrets and variables → Actions** in the repo.
2. Click **New repository secret**.
3. Set the name to `ANTHROPIC_API_KEY` and the value to a key issued from the Anthropic console.

### 2. Create labels

The script provisions the labels used by the workflows idempotently.

```bash
bash scripts/setup-issue-labels.sh
```

The labels created are:

| name           | purpose |
| -------------- | ------- |
| `needs-info`   | Waiting for additional info from the reporter (auto-applied by Claude) |
| `triaged`      | Triaged and awaiting maintainer action (auto-applied by Claude) |
| `out-of-scope` | Out of scope for this project |
| `ai-implement` | Request Claude to implement this issue (applied manually by the maintainer) |
| `wontfix`      | This will not be worked on (applied manually by the maintainer) |

### 3. Action permissions

So the `ai-implement` job can open PRs, confirm the following:

- **Settings → Actions → General → Workflow permissions**
  - "Read and write permissions" is selected.
  - "Allow GitHub Actions to create and approve pull requests" is enabled.

## Operations guide

### The first couple of weeks

Treat **every PR produced by `ai-implement` as a mandatory human-review PR** for at least the first two weeks. Observe how Claude makes decisions and adjust `direct_prompt` or `CLAUDE.md` rules as needed.

Things to watch for:

- Triage classification quality (is the split between `needs-info` / `triaged` / `out-of-scope` reasonable?)
- Whether the missing-info questions are clear to the reporter
- Whether implementation PRs respect the conventions in CLAUDE.md / AGENTS.md
- Whether changelog fragments are added correctly

### Prompt-injection mitigations

- `allowed_tools` is kept minimal: triage/wontfix only use `gh issue:*` / `gh label:*` / `gh search:*`.
- The implementation job is limited to `Bash,Edit,Write,Read,Grep,Glob`.
- The `permissions:` block scopes the `GITHUB_TOKEN` to the bare minimum required.

Treat issue bodies as untrusted: **always review the generated PR**, since malicious instructions could be embedded in the issue body.

### Keeping API spend in check

- Bot-authored issues are skipped via `github.event.issue.user.type != 'Bot'`.
- During noisy periods, cost can rise quickly. Consider adding filters such as:
  - skipping issues that don't follow the issue template
  - reacting only to issues with a specific label
  - routing non-collaborator issues to human review instead of automation

### Debugging

If the workflow does not behave as expected:

1. **Inspect the Actions tab logs** for `Claude Issue Triage` / `Claude Issue Implement` to see the commands Claude ran and their outputs.
2. **Tune `direct_prompt`** in the workflow YAML when triage criteria feel ambiguous.
3. **Add rules under `.claude/`** when you observe recurring mistakes that need a durable guardrail.
4. **Append to `CLAUDE.md`** — project-wide guardrails belong in the "OSS Issue Automation Rules" section.

## Cost expectations

Triage cost per issue is small: it reads the issue body, a few comments, and the labels/related-issue list. Implementation cost varies with the size of the change, so monthly spend tracks the number of `ai-implement` invocations more than triage volume.

During noisy periods costs can climb, so consider tightening the filter — for example by skipping issues that don't use the issue template — when the volume becomes uncomfortable.

<!-- TODO: add this page to the nav in mkdocs.yml -->
