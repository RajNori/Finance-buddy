# Change Review

Compared the working tree with the last commit (`43e6e7d`), including untracked files.

## Findings

- **[P1] Fix the plugin hook manifest path** — [neo-review/.claude-plugin/plugin.json](/Users/rajnori/Desktop/financebuddy/neo-review/.claude-plugin/plugin.json:5) uses `"hooks": "hooks/hooks.json"`. Claude Code requires this manifest path to start with `./`. `claude plugin validate neo-review --json` rejects the plugin, and validating [.claude-plugin/marketplace.json](/Users/rajnori/Desktop/financebuddy/.claude-plugin/marketplace.json:10) also fails because its listed plugin has the same invalid hook path. As a result, the marketplace cannot validate/install this plugin and its Stop hook will not run. Change the value to `"./hooks/hooks.json"`.

- **[P3] Use the recognized marketplace author field** — [.claude-plugin/marketplace.json](/Users/rajnori/Desktop/financebuddy/.claude-plugin/marketplace.json:14) uses `"authors"`, which Claude Code reports as an unknown field and ignores. Use the singular `"author"` field if this attribution should appear in marketplace metadata.

## Scope and checks

Reviewed `.claude/settings.json`, `.gitignore`, `.claude-plugin/marketplace.json`, `.claude/agents/codex-reviewer.md`, `neo-review/.claude-plugin/plugin.json`, `neo-review/hooks/hooks.json`, and `infra/bootstrap/.terraform.lock.hcl`. `infra/bootstrap/main.tf` is unchanged from the last commit. All reviewed JSON files parse successfully, and `git diff --check HEAD` reports no whitespace errors. `claude plugin validate` found the plugin hook path error above and the ignored author field. No tests were run; this was a change review.
