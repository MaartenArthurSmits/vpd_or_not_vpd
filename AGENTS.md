# Project instructions

## Workflow

For ordinary improvements in this solo project, implement one step, run relevant tests, review the changes, then commit and push directly to main. Check GitHub Actions afterwards. Do not routinely create branches or pull requests; reserve them for larger experimental changes or explicit requests. Complete any already-active PR before returning to this default.

After pushing, report immediately with the commit hash and the GitHub Actions run link. If CI is still running, say "pending" and finish the response. Do not use sleep/polling loops to wait for CI. Never describe pending CI as passed; report known failures accurately. Include small instruction-file updates in the next normal app-change commit rather than making a separate commit just for them.
