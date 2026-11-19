# Copilot instructions

Copilot has no workspace hook API. Use the git hooks in `.githooks` and `python3 capture/hk-capture.py test -- <command>` so commits and test runs still emit derived features.

Call practice.register_task before implementation. Do not put prompt text or secrets in tool arguments. IDE event consent is required. Hook events are not scored.

Activate `.githooks`, then run `python3 capture/hk-capture.py status`, `python3 capture/hk-capture.py sync-sessions --all`, and `python3 capture/hk-capture.py test -- <command>`. Keep sessions grounded in `specs/`.
