# Claude Code project notes

Use the hosted MCP collection tools. Call practice.register_task before the first implementation commit and practice.record_hook_event with derived features only.

IDE event consent is required. Do not place prompt text, completions, or command output in tool arguments. Hook capture is not scored.

The local helper `capture/hk-capture.py` derives hashes and counts before upload and spools transient HTTP failures.

Activate bundled git hooks with `git config core.hooksPath .githooks` and make `.githooks/post-commit` and `.githooks/prepare-commit-msg` executable. Check `python3 capture/hk-capture.py status`, `python3 capture/hk-capture.py sync-sessions --all`, and `python3 capture/hk-capture.py test -- <command>`. Keep sessions grounded in `specs/`.
