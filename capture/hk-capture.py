#!/usr/bin/env python3
"""Local derived-feature capture. Raw prompt text stays on this machine."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SPEC_REF = re.compile(r"specs/[A-Za-z0-9_./-]+\.md")
_CO_AUTHORED = re.compile(r"^\s*co-authored-by:\s*.+\s*$", re.IGNORECASE)
_MADE_WITH_CURSOR = re.compile(r"^\s*made-with:\s*cursor\b.*$", re.IGNORECASE)


def _drop_commit_trailer_line(line: str) -> bool:
    return bool(_CO_AUTHORED.match(line) or _MADE_WITH_CURSOR.match(line))
_SOURCES = {"cursor", "claude_code", "copilot", "git", "local_extractor"}
_KINDS = {
    "prompt_submit",
    "file_edit",
    "shell_exec",
    "tool_use",
    "agent_stop",
    "commit",
    "test_run",
    "session_summary",
}
_CURSOR_KINDS = {
    "beforeSubmitPrompt": "prompt_submit",
    "afterFileEdit": "file_edit",
    "beforeShellExecution": "shell_exec",
    "afterShellExecution": "shell_exec",
    "postToolUse": "tool_use",
    "stop": "agent_stop",
}
_CLAUDE_KINDS = {
    "UserPromptSubmit": "prompt_submit",
    "PostToolUse": "tool_use",
    "Stop": "agent_stop",
}
_DOTENV = "." + "env"
PostFn = Callable[[str, str, str], int]


def derive_prompt(text: str) -> dict[str, Any]:
    """Hash and classify a prompt. The returned dict never contains the text."""
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in _SPEC_REF.finditer(text):
        path = match.group(0)
        if path not in seen:
            seen.add(path)
            refs.append({"path": path})
    lowered = text.lower()
    if "pytest" in lowered or "vitest" in lowered or "npm test" in lowered:
        category = "test"
    elif "auth" in lowered or "login" in lowered:
        category = "auth"
    elif "spec" in lowered:
        category = "spec"
    else:
        category = "other"
    return {
        "prompt_len": len(text),
        "prompt_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "prompt_category": category,
        "refs": refs,
    }


def hook_from_ide_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Map one IDE hook body onto a derived event."""
    name = str(payload.get("hook_event_name") or payload.get("hook") or "")
    kind = _CURSOR_KINDS.get(name) or _CLAUDE_KINDS.get(name)
    explicit = payload.get("hook_kind")
    if isinstance(explicit, str) and explicit in _KINDS:
        kind = explicit
    if kind is None:
        return None
    command = payload.get("command")
    if kind == "shell_exec" and isinstance(command, str):
        kind = _shell_kind(command)
    source = payload.get("source")
    if source not in _SOURCES:
        source = "claude_code" if name in _CLAUDE_KINDS else "cursor"
    event: dict[str, Any] = {
        "source": source,
        "hook_kind": kind,
        "idempotency_key": _idempotency(payload, kind),
        "occurred_at": _now(),
    }
    prompt = payload.get("prompt")
    if isinstance(prompt, str):
        event.update(derive_prompt(prompt))
    if kind == "test_run":
        code = payload.get("exit_code")
        if isinstance(code, int):
            event["exit_code"] = code
            event["passed"] = code == 0
            event["count_failed"] = 0 if code == 0 else 1
    task_id = payload.get("task_id")
    if isinstance(task_id, str) and task_id:
        event["task_id"] = task_id
    return event


def strip_cursor_attribution(message: str) -> str:
    """Remove co-authored-by and Cursor Made-with trailers from commit messages."""
    kept = [line for line in message.splitlines() if not _drop_commit_trailer_line(line)]
    if not kept:
        return message
    body = "\n".join(kept)
    if message.endswith("\n"):
        body += "\n"
    return body


def append_commit_trailers(message: str, active: dict[str, Any]) -> str:
    """Append Spec and Practice trailers once."""
    extra: list[str] = []
    for key, prefix in (("spec_trailer", "Spec:"), ("practice_trailer", "Practice:")):
        raw = active.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        line = raw.strip()
        if not line.startswith(prefix):
            line = f"{prefix} {line}"
        if line not in message:
            extra.append(line)
    if not extra:
        return message
    body = message if message.endswith("\n") else f"{message}\n"
    return body + "\n".join(extra) + "\n"


def commit_features_from_numstat(
    numstat: str,
    *,
    sha: str,
    spec_trailer: str | None,
    task_id: str | None,
) -> dict[str, Any]:
    added = 0
    removed = 0
    files: list[str] = []
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        plus, minus, path = parts
        if plus.isdigit():
            added += int(plus)
        if minus.isdigit():
            removed += int(minus)
        files.append(path)
    event: dict[str, Any] = {
        "source": "git",
        "hook_kind": "commit",
        "idempotency_key": f"commit-{sha[:12]}",
        "occurred_at": _now(),
        "commit_sha": sha,
        "files_changed": files,
        "lines_added": added,
        "lines_removed": removed,
    }
    if spec_trailer:
        event["spec_trailer"] = spec_trailer
    if task_id:
        event["task_id"] = task_id
    return event


def summarize_transcript(
    lines: list[str],
    *,
    source: str = "local_extractor",
    session_key: str = "",
) -> dict[str, Any]:
    """Count session features. Prompt and assistant text are discarded."""
    turns = 0
    reprompts = 0
    tool_calls = 0
    accepted = 0
    rejected = 0
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    no_spec = 0
    test_runs = 0
    user_streak = 0
    reprompt_loop = 0
    first_at: str | None = None
    last_at: str | None = None
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or item.get("type") or "")
        text = item.get("text") if isinstance(item.get("text"), str) else ""
        if not text and isinstance(item.get("content"), str):
            text = item["content"]
        stamp = item.get("timestamp") or item.get("occurred_at")
        if isinstance(stamp, str) and stamp:
            if first_at is None:
                first_at = stamp
            last_at = stamp
        if role in {"user", "human"}:
            turns += 1
            if turns > 1:
                reprompts += 1
            user_streak += 1
            if user_streak >= 3:
                reprompt_loop += 1
                user_streak = 0
            if not _SPEC_REF.search(text):
                no_spec += 1
        elif role in {"tool", "tool_use", "tool_result"}:
            tool_calls += 1
            user_streak = 0
            tool_name = str(item.get("name") or item.get("tool") or "")
            if "test" in tool_name.lower() or "pytest" in tool_name.lower():
                test_runs += 1
        else:
            user_streak = 0
        edit = item.get("edit")
        if edit == "accepted":
            accepted += 1
        elif edit == "rejected":
            rejected += 1
        if isinstance(text, str):
            for match in _SPEC_REF.finditer(text):
                path = match.group(0)
                if path not in seen:
                    seen.add(path)
                    refs.append({"path": path})
    edit_count = accepted + rejected
    harness = source if source in _SOURCES else "local_extractor"
    identity = session_key or "session"
    return {
        "source": harness,
        "hook_kind": "session_summary",
        "idempotency_key": "session-summary",
        "occurred_at": _now(),
        "session_id_hash": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        "started_at": first_at or _now(),
        "duration_seconds": _duration_seconds(first_at, last_at),
        "turns": turns,
        "reprompt_count": reprompts,
        "tool_call_count": tool_calls,
        "edits_accepted": accepted,
        "edits_rejected": rejected,
        "refs": refs,
        "anti_pattern_counts": {
            "no_spec_ref_turns": no_spec,
            "edits_without_test_run": edit_count if test_runs == 0 and edit_count else 0,
            "reprompt_loop_count": reprompt_loop,
        },
    }


def _duration_seconds(started: str | None, ended: str | None) -> int:
    if not started or not ended:
        return 0
    try:
        start = datetime.fromisoformat(started.replace("Z", "+00:00"))
        finish = datetime.fromisoformat(ended.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, int((finish - start).total_seconds()))


def discover_session_files(
    root: Path,
    *,
    home: Path | None = None,
    extra_roots: list[Path] | None = None,
) -> list[Path]:
    """Read-only session logs for this repo. Source files are never modified."""
    found: list[Path] = []
    local = root / ".hk-capture" / "sessions"
    if local.is_dir():
        found.extend(sorted(path for path in local.glob("*.jsonl") if path.is_file()))
    base = home if home is not None else Path.home()
    repo_name = root.name
    candidates = (
        base / ".cursor" / "projects",
        base / ".claude" / "projects",
        base / ".copilot" / "session-history",
    )
    for folder in candidates:
        if not folder.is_dir():
            continue
        for path in folder.glob("**/*.jsonl"):
            if path.is_file() and repo_name in str(path):
                found.append(path)
    for extra in extra_roots or []:
        if extra.is_dir():
            found.extend(sorted(path for path in extra.glob("**/*.jsonl") if path.is_file()))
        elif extra.is_file() and extra.suffix == ".jsonl":
            found.append(extra)
    unique = sorted(set(found))
    return unique


def session_source_for(path: Path) -> str:
    text = str(path)
    if ".cursor" in text:
        return "cursor"
    if ".claude" in text:
        return "claude_code"
    if "copilot" in text:
        return "copilot"
    return "local_extractor"


def plan_hooks_path(existing: str | None) -> tuple[str, str | None]:
    target = ".githooks"
    if existing and existing.strip() and existing.strip() != target:
        return target, "hooks_path_would_be_overwritten"
    return target, None


def deliver_event(
    event: dict[str, Any],
    *,
    endpoint: str,
    token: str,
    post: PostFn,
    spool_path: Path,
) -> int:
    if not token:
        _append_jsonl(spool_path, event)
        return 0
    body = json.dumps(event, sort_keys=True, separators=(",", ":"))
    try:
        status = post(endpoint, body, token)
    except OSError:
        _append_jsonl(spool_path, event)
        return 0
    if status == 429 or status >= 500:
        _append_jsonl(spool_path, event)
    return 0


def flush_spool(spool_path: Path, *, endpoint: str, token: str, post: PostFn) -> int:
    if not spool_path.is_file():
        return 0
    if not token:
        return 0
    kept: list[str] = []
    sent: set[str] = set()
    for line in spool_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        key = str(event.get("idempotency_key") or "")
        if key and key in sent:
            continue
        try:
            status = post(endpoint, line, token)
        except OSError:
            kept.append(line)
            continue
        if status == 429 or status >= 500:
            kept.append(line)
            continue
        if key:
            sent.add(key)
    payload = ("\n".join(kept) + "\n") if kept else ""
    spool_path.write_text(payload, encoding="utf-8")
    return 0


def run_observed_command(argv: list[str]) -> tuple[int, dict[str, Any]]:
    completed = subprocess.run(argv, check=False)
    code = int(completed.returncode)
    return code, {
        "source": "local_extractor",
        "hook_kind": "test_run",
        "idempotency_key": f"test-{_now_compact()}",
        "occurred_at": _now(),
        "exit_code": code,
        "passed": code == 0,
        "count_failed": 0 if code == 0 else 1,
    }


def submit_bundle(
    *,
    bundle: bytes,
    checksum: str,
    post: PostFn,
    endpoint: str,
    token: str,
) -> int:
    """Upload then confirm. A failed upload does not confirm."""
    body = json.dumps({"checksum": checksum, "size": len(bundle)})
    try:
        status = post(endpoint, body, token)
    except OSError:
        return 1
    if status < 200 or status >= 300:
        return 1
    try:
        confirmed = post(endpoint + "/confirm", body, token)
    except OSError:
        return 1
    if confirmed < 200 or confirmed >= 300:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else "hook"
    try:
        if command == "init":
            return _cmd_init()
        if command == "prepare-commit-msg" and len(args) >= 2:
            return _cmd_prepare(Path(args[1]))
        if command == "commit-msg" and len(args) >= 2:
            return _cmd_commit_msg(Path(args[1]))
        if command == "post-commit":
            return _cmd_post_commit()
        if command == "test":
            return _cmd_test(args[1:])
        if command == "sync-sessions":
            return _cmd_sync(from_start="--all" in args)
        if command == "replay-sessions":
            return _cmd_sync(from_start=True)
        if command == "status":
            return _cmd_status()
        if command == "flush":
            return _cmd_flush()
        if command == "replay-commits":
            return _cmd_replay_commits()
        if command == "submit":
            return _cmd_submit()
        if command == "hook":
            return _cmd_hook()
    except (OSError, ValueError, json.JSONDecodeError, TypeError, KeyError):
        return 0
    return 0


def _cmd_hook() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    event = hook_from_ide_payload(payload)
    if event is None:
        return 0
    sent = _send(event)
    if event.get("hook_kind") == "agent_stop":
        _cmd_sync(from_start=False)
    return sent


def _cmd_init() -> int:
    root = _repo_root()
    git_hooks = ""
    if (root / ".git").exists():
        git_hooks = _git_output(["config", "--get", "core.hooksPath"]).strip()
    existing = os.environ.get("HK_GIT_HOOKS_PATH") or git_hooks
    _target, warning = plan_hooks_path(existing)
    capture = _capture_dir()
    capture.mkdir(parents=True, exist_ok=True)
    if warning:
        print("warning: existing hook path would be overwritten", file=sys.stderr)
    elif (root / ".git").exists():
        _git_output(["config", "core.hooksPath", ".githooks"])
        print("Set core.hooksPath to .githooks")
    else:
        print("Set core.hooksPath to .githooks")
    for name in ("post-commit", "prepare-commit-msg", "commit-msg"):
        hook = root / ".githooks" / name
        if hook.is_file() and not os.access(hook, os.X_OK):
            hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        if hook.is_file():
            print(f"{name} executable: {'yes' if os.access(hook, os.X_OK) else 'no'}")
    return 0


def _cmd_prepare(path: Path) -> int:
    active_path = _capture_dir() / "active_task.json"
    active: dict[str, Any] = {}
    if active_path.is_file():
        loaded = json.loads(active_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            active = loaded
    message = path.read_text(encoding="utf-8") if path.is_file() else ""
    message = strip_cursor_attribution(message)
    path.write_text(append_commit_trailers(message, active), encoding="utf-8")
    return 0


def _cmd_commit_msg(path: Path) -> int:
    message = path.read_text(encoding="utf-8") if path.is_file() else ""
    cleaned = strip_cursor_attribution(message)
    if cleaned != message:
        path.write_text(cleaned, encoding="utf-8")
    return 0


def _cmd_post_commit() -> int:
    sha = _git_output(["rev-parse", "HEAD"]).strip()
    if not sha:
        return 0
    event = commit_event_for_sha(
        sha,
        numstat=_git_output(["diff-tree", "--no-commit-id", "--numstat", "-r", "HEAD"]),
        message=_git_output(["log", "-1", "--format=%B"]),
        task_id=_active_task_id(),
    )
    sent = _send(event)
    _cmd_sync(from_start=False)
    return sent


def commit_event_for_sha(
    sha: str,
    *,
    numstat: str,
    message: str,
    task_id: str | None,
) -> dict[str, Any]:
    """Derived commit features. The commit message body is not stored."""
    trailer = None
    for line in message.splitlines():
        if line.startswith("Spec:"):
            trailer = line.removeprefix("Spec:").strip()
    return commit_features_from_numstat(
        numstat,
        sha=sha,
        spec_trailer=trailer,
        task_id=task_id,
    )


def replay_commit_events(
    shas: list[str],
    *,
    numstat_for: Callable[[str], str],
    message_for: Callable[[str], str],
    task_id: str | None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for sha in shas:
        if not sha:
            continue
        events.append(
            commit_event_for_sha(
                sha,
                numstat=numstat_for(sha),
                message=message_for(sha),
                task_id=task_id,
            )
        )
    return events


def _cmd_replay_commits() -> int:
    listed = _git_output(["rev-list", "HEAD"])
    shas = [line.strip() for line in listed.splitlines() if line.strip()]
    task_id = _active_task_id()
    for event in replay_commit_events(
        shas,
        numstat_for=lambda sha: _git_output(
            ["diff-tree", "--no-commit-id", "--numstat", "-r", sha]
        ),
        message_for=lambda sha: _git_output(["log", "-1", "--format=%B", sha]),
        task_id=task_id,
    ):
        _send(event)
    return 0


def _cmd_test(args: list[str]) -> int:
    if args and args[0] == "--":
        args = args[1:]
    if not args:
        return 2
    code, event = run_observed_command(args)
    task_id = _active_task_id()
    if task_id:
        event["task_id"] = task_id
    _send(event)
    return code


def _cmd_sync(*, from_start: bool = False) -> int:
    root = _repo_root()
    cursor_file = _capture_dir() / "cursors.json"
    cursors: dict[str, int] = {}
    if cursor_file.is_file():
        loaded = json.loads(cursor_file.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            cursors = {str(key): int(value) for key, value in loaded.items()}
    emitted = False
    for path in _session_files(root):
        lines = path.read_text(encoding="utf-8").splitlines()
        offset = 0 if from_start else cursors.get(str(path), 0)
        fresh = lines[offset:]
        if not fresh:
            continue
        event = summarize_transcript(
            fresh,
            source=session_source_for(path),
            session_key=str(path),
        )
        digest = hashlib.sha256("\n".join(fresh).encode("utf-8")).hexdigest()[:12]
        event["idempotency_key"] = f"session-{digest}"
        _send(event)
        cursors[str(path)] = len(lines)
        emitted = True
    if emitted or cursors:
        cursor_file.parent.mkdir(parents=True, exist_ok=True)
        cursor_file.write_text(json.dumps(cursors, sort_keys=True), encoding="utf-8")
    return 0


def _cmd_status() -> int:
    spool = _capture_dir() / "spool.jsonl"
    depth = 0
    if spool.is_file():
        depth = len([line for line in spool.read_text(encoding="utf-8").splitlines() if line])
    print(f"spool {depth}")
    root = _repo_root()
    _, token = resolve_capture_config(root)
    print("configured" if token else "unconfigured")
    for name, present in context_health_report(root).items():
        print(f"context {name} {'yes' if present else 'no'}")
    print("hint: hk-capture status")
    return 0


def _cmd_flush() -> int:
    return flush_spool(
        _capture_dir() / "spool.jsonl",
        endpoint=_endpoint(),
        token=_token(),
        post=_post,
    )


def _cmd_submit() -> int:
    bundle = _git_bytes(["bundle", "create", "-", "--all"])
    if bundle is None:
        return 1
    checksum = hashlib.sha256(bundle).hexdigest()
    return submit_bundle(
        bundle=bundle,
        checksum=checksum,
        post=_plain_post,
        endpoint=_endpoint() + "/submission-bundles",
        token=_token(),
    )


def _send(event: dict[str, Any]) -> int:
    return deliver_event(
        event,
        endpoint=_endpoint(),
        token=_token(),
        post=_post,
        spool_path=_capture_dir() / "spool.jsonl",
    )


def tools_call_body(event: dict[str, Any], request_id: int = 2) -> str:
    envelope = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": "practice.record_hook_event", "arguments": event},
    }
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"))


def initialize_body() -> str:
    envelope = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "hk-capture", "version": "1"},
        },
    }
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"))


def initialized_body() -> str:
    return json.dumps(
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        sort_keys=True,
        separators=(",", ":"),
    )


def session_missing(status: int, body: str) -> bool:
    if status not in {400, 404}:
        return False
    return "session" in body.lower()


def post_record_hook_event(
    endpoint: str,
    body: str,
    token: str,
    *,
    exchange: Callable[[str, str, str, str | None], tuple[int, dict[str, str], str]],
    session_id: str | None,
    save_session: Callable[[str], None],
) -> int:
    """Send one derived event as tools/call, opening a session when needed."""
    parsed = json.loads(body)
    if isinstance(parsed, dict) and parsed.get("method") == "tools/call":
        call = body
    elif isinstance(parsed, dict):
        call = tools_call_body(parsed)
    else:
        return 400
    current = session_id
    if not current:
        current, opened = _open_mcp_session(endpoint, token, exchange)
        if current is None:
            return opened
        save_session(current)
    status, _headers, text = exchange(endpoint, call, token, current)
    if session_missing(status, text):
        current, opened = _open_mcp_session(endpoint, token, exchange)
        if current is None:
            return opened
        save_session(current)
        status, _headers, text = exchange(endpoint, call, token, current)
    return status


def _open_mcp_session(
    endpoint: str,
    token: str,
    exchange: Callable[[str, str, str, str | None], tuple[int, dict[str, str], str]],
) -> tuple[str | None, int]:
    status, headers, _text = exchange(endpoint, initialize_body(), token, None)
    if status < 200 or status >= 300:
        return None, status
    session_id = headers.get("mcp-session-id")
    if not session_id:
        return None, 502
    exchange(endpoint, initialized_body(), token, session_id)
    return session_id, status


def _plain_post(endpoint: str, body: str, token: str) -> int:
    request = urllib.request.Request(
        endpoint,
        data=body.encode("utf-8"),
        headers={"content-type": "application/json", "authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return int(response.status)
    except urllib.error.HTTPError as error:
        return int(error.code)


def _post(endpoint: str, body: str, token: str) -> int:
    return post_record_hook_event(
        endpoint,
        body,
        token,
        exchange=_urllib_exchange,
        session_id=_load_mcp_session(endpoint),
        save_session=lambda session_id: _save_mcp_session(endpoint, session_id),
    )


def _urllib_exchange(
    endpoint: str,
    body: str,
    token: str,
    session_id: str | None,
) -> tuple[int, dict[str, str], str]:
    headers = {
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "authorization": f"Bearer {token}",
        "mcp-protocol-version": "2024-11-05",
    }
    if session_id:
        headers["mcp-session-id"] = session_id
    request = urllib.request.Request(
        endpoint,
        data=body.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = response.read().decode("utf-8", errors="replace")
            found = {key.lower(): value for key, value in response.headers.items()}
            return int(response.status), found, payload
    except urllib.error.HTTPError as error:
        payload = error.read().decode("utf-8", errors="replace")
        raw_headers = error.headers.items() if error.headers is not None else ()
        found = {key.lower(): value for key, value in raw_headers}
        return int(error.code), found, payload


def _session_file() -> Path:
    return _capture_dir() / "mcp_session.json"


def _load_mcp_session(endpoint: str) -> str | None:
    path = _session_file()
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(loaded, dict) or loaded.get("endpoint") != endpoint:
        return None
    session_id = loaded.get("session_id")
    return session_id if isinstance(session_id, str) and session_id else None


def _save_mcp_session(endpoint: str, session_id: str) -> None:
    path = _session_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"endpoint": endpoint, "session_id": session_id}, sort_keys=True),
        encoding="utf-8",
    )


def context_health_report(root: Path) -> dict[str, bool]:
    """Repo readiness checks. The bearer value is not included."""
    specs_dir = root / "specs"
    has_spec = False
    if specs_dir.is_dir():
        for path in specs_dir.glob("*.md"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if "FILL:" not in text and text.strip():
                has_spec = True
                break
    hook = root / ".githooks" / "post-commit"
    _, token = resolve_capture_config(root)
    return {
        "specs": has_spec,
        "agents_md": (root / "AGENTS.md").is_file(),
        "hooks_executable": hook.is_file() and os.access(hook, os.X_OK),
        "mcp_config": bool(token),
    }


def resolve_capture_config(
    root: Path,
    environ: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Endpoint and bearer. Environment overrides dotenv, which overrides MCP JSON."""
    source = os.environ if environ is None else environ
    endpoint = source.get("HK_CAPTURE_ENDPOINT", "").rstrip("/")
    token = source.get("HK_CAPTURE_TOKEN", "")
    if not token:
        token = _dotenv_token(root / _DOTENV)
    mcp_url, mcp_token = mcp_server_config(root / ".cursor" / "mcp.json")
    if not endpoint:
        endpoint = mcp_url or "http://127.0.0.1:8000/api/v1/mcp"
    if not token:
        token = mcp_token
    return endpoint, token


def mcp_server_config(path: Path) -> tuple[str, str]:
    """Read the hackathon-event URL and bearer. Missing files yield empty strings."""
    if not path.is_file():
        return "", ""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "", ""
    servers = loaded.get("mcpServers") if isinstance(loaded, dict) else None
    if not isinstance(servers, dict):
        return "", ""
    entry = servers.get("hackathon-event")
    if not isinstance(entry, dict):
        return "", ""
    url = entry.get("url")
    headers = entry.get("headers")
    token = ""
    if isinstance(headers, dict):
        auth = headers.get("Authorization")
        if not isinstance(auth, str):
            auth = headers.get("authorization")
        if isinstance(auth, str) and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
    endpoint = url.rstrip("/") if isinstance(url, str) else ""
    return endpoint, token


def _dotenv_token(path: Path) -> str:
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("HK_CAPTURE_TOKEN="):
            return line.split("=", 1)[1].strip()
    return ""


def _repo_root() -> Path:
    output = _git_output(["rev-parse", "--show-toplevel"]).strip()
    if output:
        return Path(output)
    return Path.cwd()


def _endpoint() -> str:
    endpoint, _token_value = resolve_capture_config(_repo_root())
    return endpoint


def _token() -> str:
    _endpoint_value, token = resolve_capture_config(_repo_root())
    return token


def _capture_dir() -> Path:
    override = os.environ.get("HK_CAPTURE_DIR", "").strip()
    if override:
        return Path(override)
    return _repo_root() / ".hk-capture"


def _active_task_id() -> str | None:
    path = _capture_dir() / "active_task.json"
    if not path.is_file():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, dict) and isinstance(loaded.get("task_id"), str):
        return loaded["task_id"]
    return None


def _session_files(root: Path) -> list[Path]:
    raw = os.environ.get("HK_CAPTURE_SESSION_ROOTS", "")
    extra = [Path(part) for part in raw.split(os.pathsep) if part]
    return discover_session_files(root, extra_roots=extra)


def _append_jsonl(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")


def _idempotency(payload: dict[str, Any], kind: str) -> str:
    supplied = payload.get("idempotency_key")
    if isinstance(supplied, str) and supplied:
        return supplied
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return f"{kind}-{digest[:16]}"


def _shell_kind(command: str) -> str:
    lowered = command.lower()
    if "pytest" in lowered or "vitest" in lowered or "npm test" in lowered:
        return "test_run"
    return "shell_exec"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_compact() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S")


def _git_output(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout


def _git_bytes(args: list[str]) -> bytes | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            check=False,
            capture_output=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


if __name__ == "__main__":
    raise SystemExit(main())
