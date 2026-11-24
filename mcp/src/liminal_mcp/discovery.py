import json
import os
import socket
from pathlib import Path

DIR_ENV_VAR = "LIMINAL_SESSIONS_DIR"


class NoSession(RuntimeError):
    pass


def sessions_dir() -> Path:
    override = os.environ.get(DIR_ENV_VAR, "")
    return Path(override) if override else Path.home() / ".liminal" / "sessions"


def _reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5) as s:
            s.sendall(b'{"type":"ping"}\n')
            s.settimeout(1.0)
            return s.recv(64).startswith(b'{"type": "pong"}')
    except OSError:
        return False


def list_sessions() -> list[dict]:
    d = sessions_dir()
    if not d.is_dir():
        return []
    found = []
    for f in sorted(d.glob("*.json")):
        try:
            info = json.loads(f.read_text(encoding="utf-8"))
            port = int(info.get("port", 0))
        except (OSError, ValueError, TypeError):
            continue
        if not port or not _reachable(info.get("host", "127.0.0.1"), port):
            try:
                f.unlink()
            except OSError:
                pass
            continue
        found.append(info)
    found.sort(key=lambda s: s.get("started_at", 0), reverse=True)
    return found


def _inside(child: str, parent: Path) -> bool:
    try:
        Path(child).resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def _workspace_dirs(project_root: Path) -> list[Path]:
    out = []
    try:
        for marker in project_root.rglob(".lmworkspace"):
            if "node_modules" in marker.parts or ".git" in marker.parts:
                continue
            out.append(marker.parent)
    except OSError:
        pass
    return out


def choose_session(project_root: Path, pinned_pid: int | None = None) -> dict:
    sessions = list_sessions()
    if pinned_pid is not None:
        for s in sessions:
            if s.get("pid") == pinned_pid:
                return s
        raise NoSession(f"The pinned Blender session (pid {pinned_pid}) is gone. Call lm_sessions to pick another.")
    if not sessions:
        raise NoSession(
            "No Blender with the Liminal Bridge add-on is running. Start Blender, make sure "
            "both Liminal Editor and Liminal Bridge are enabled, and check the LM Bridge panel "
            "in the LM Toolkit sidebar shows a port."
        )
    matching = [s for s in sessions if s.get("project_dir") and _inside(s["project_dir"], project_root)]
    if len(matching) == 1:
        return matching[0]
    if len(matching) > 1:
        return matching[0]
    if len(sessions) == 1:
        return sessions[0]
    lines = [f"  pid {s.get('pid')}: {s.get('blend_file') or '(unsaved)'}  workspace={s.get('project_dir') or '(none)'}"
             for s in sessions]
    raise NoSession(
        "Several Blenders are running and none has a workspace inside this project. "
        "Call lm_use_session with the pid you want:\n" + "\n".join(lines)
    )


def describe_sessions(project_root: Path) -> list[dict]:
    workspaces = _workspace_dirs(project_root)
    out = []
    for s in list_sessions():
        pd = s.get("project_dir") or ""
        out.append({
            **s,
            "matches_project": bool(pd) and _inside(pd, project_root),
        })
    return out
