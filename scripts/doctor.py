import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

RELEASES = "https://github.com/liminal-lv/liminal-claude/releases/latest"
BUY = "https://liminal.lv"


def check(name, status, detail, fix=""):
    return {"check": name, "status": status, "detail": detail, "fix": fix}


def run(cmd, timeout=20):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.returncode, (out.stdout or out.stderr).strip()
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def python_check():
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 10)
    return check("python", "ok" if ok else "fail", f"Python {v.major}.{v.minor}.{v.micro} at {sys.executable}",
                 "" if ok else "Install Python 3.10 or newer from python.org.")


def node_check():
    node = shutil.which("node")
    if not node:
        return check("node", "fail", "node is not on PATH",
                     "Install Node 22 or newer from nodejs.org; the Web SDK and `liminal sync` run on it.")
    code, out = run([node, "--version"])
    major = 0
    try:
        major = int(out.lstrip("v").split(".")[0])
    except ValueError:
        pass
    ok = major >= 22
    return check("node", "ok" if ok else "warn", f"{out} at {node}",
                 "" if ok else "Node 22 or newer runs liminal.config.ts natively; older Node needs `tsx`.")


def mcp_check():
    exe = shutil.which("liminal-mcp")
    if exe:
        code, out = run([exe, "--version"])
        return check("liminal_mcp", "ok" if code == 0 else "warn", f"{out or 'liminal-mcp'} at {exe}",
                     "" if code == 0 else "liminal-mcp is installed but did not start; reinstall it with pip.")
    plugin_mcp = Path(__file__).resolve().parent.parent / "mcp"
    return check("liminal_mcp", "fail", "liminal-mcp is not on PATH",
                 f'Run `"{sys.executable}" -m pip install "{plugin_mcp}"` (or `pip install liminal-mcp`), '
                 "then make sure pip's scripts directory is on PATH. Restart Claude Code afterwards so it "
                 "starts the MCP server.")


def blender_check():
    candidates = []
    if shutil.which("blender"):
        candidates.append(shutil.which("blender"))
    if os.name == "nt":
        for base in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""),
                     os.environ.get("LOCALAPPDATA", "") + r"\Programs"):
            root = Path(base) / "Blender Foundation"
            if root.is_dir():
                candidates += [str(p) for p in sorted(root.glob("Blender */blender.exe"), reverse=True)]
    elif sys.platform == "darwin":
        for p in Path("/Applications").glob("Blender*.app/Contents/MacOS/Blender"):
            candidates.append(str(p))
    else:
        for p in ("/usr/bin/blender", "/snap/bin/blender", "/usr/local/bin/blender"):
            if Path(p).exists():
                candidates.append(p)
    if not candidates:
        return check("blender", "fail", "No Blender installation found",
                     "Install Blender 4.5 or newer from blender.org.")
    code, out = run([candidates[0], "--version"], timeout=40)
    first = out.splitlines()[0] if out else "Blender"
    return check("blender", "ok", f"{first} at {candidates[0]}")


def sessions_dir():
    override = os.environ.get("LIMINAL_SESSIONS_DIR", "")
    return Path(override) if override else Path.home() / ".liminal" / "sessions"


def reachable(host, port):
    try:
        with socket.create_connection((host, port), timeout=0.5) as s:
            s.sendall(b'{"type":"ping"}\n')
            s.settimeout(1.0)
            return s.recv(64).startswith(b'{"type": "pong"}')
    except OSError:
        return False


def bridge_health(info):
    try:
        with socket.create_connection((info.get("host", "127.0.0.1"), int(info["port"])), timeout=3) as s:
            s.sendall(b'{"type":"health"}\n')
            buf = b""
            while b"\n" not in buf:
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
        return json.loads(buf.split(b"\n", 1)[0] or b"{}")
    except (OSError, ValueError):
        return {}


def bridge_checks():
    d = sessions_dir()
    live = []
    for f in d.glob("*.json") if d.is_dir() else []:
        try:
            info = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if reachable(info.get("host", "127.0.0.1"), int(info.get("port", 0) or 0)):
            live.append(info)
    if not live:
        return [check("bridge", "warn", "No running Blender with the Liminal Bridge add-on was found",
                      "Start Blender. If the LM Toolkit sidebar (press N) has no 'LM Bridge' panel, install the bridge: "
                      f"download liminal_bridge-*-blender.zip from {RELEASES}, then in Blender use Edit > Preferences > "
                      "Get Extensions > the dropdown arrow > Install from Disk, and enable 'Liminal Bridge'.")]
    out = []
    for info in live:
        health = bridge_health(info)
        pid = info.get("pid")
        out.append(check("bridge", "ok", f"Blender pid {pid} on port {info.get('port')} ({info.get('blender_version')}), "
                                          f"bridge {info.get('bridge_version')}, "
                                          f"developer mode {'on' if health.get('developer_mode') else 'off'}"))
        if info.get("editor_loaded"):
            out.append(check("editor_loaded", "ok", f"Liminal Editor {info.get('editor_version')} is enabled in pid {pid}"))
        else:
            out.append(check("editor_loaded", "fail", f"Liminal Editor is not enabled in Blender pid {pid}",
                             f"Liminal Editor is the paid add-on from {BUY}. Install the zip you downloaded after purchase via "
                             "Edit > Preferences > Get Extensions > Install from Disk, enable it, then restart Blender."))
        if info.get("project_dir"):
            out.append(check("workspace_bound", "ok", f"Blender pid {pid} is bound to workspace {info['project_dir']}"))
        else:
            out.append(check("workspace_bound", "warn", f"Blender pid {pid} has no game configuration selected",
                             "In Blender: Edit > Preferences > Add-ons > Liminal Editor > add a Game Configuration whose "
                             "Workspace Folder is this project's synced _blender folder; then pick it in the LM Toolkit sidebar."))
    return out


def project_checks(root: Path):
    out = []
    pkg = root / "package.json"
    if not pkg.exists():
        out.append(check("project", "warn", f"No package.json in {root}",
                         "If this is a new game, create it first (for example `npm create vite@latest`), then come back."))
        return out
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except ValueError:
        data = {}
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    has_core = "@liminal-lv/core" in deps
    has_cli = "@liminal-lv/cli" in deps
    out.append(check("sdk_installed", "ok" if has_core and has_cli else "fail",
                     f"@liminal-lv/core {'present' if has_core else 'missing'}, @liminal-lv/cli {'present' if has_cli else 'missing'}",
                     "" if has_core and has_cli else "Run `npm install @liminal-lv/core` and `npm install -D @liminal-lv/cli` "
                     "(pnpm and yarn equivalents are fine)."))
    config = next((root / n for n in ("liminal.config.ts", "liminal.config.js", "liminal.config.mjs") if (root / n).exists()), None)
    out.append(check("liminal_config", "ok" if config else "fail",
                     f"{config.name} found" if config else "No liminal.config.ts",
                     "" if config else "Create liminal.config.ts exporting { registry, workspace: '_blender' }; the liminal-web skill has the template."))
    workspaces = [m.parent for m in root.rglob(".lmworkspace")
                  if "node_modules" not in m.parts and ".git" not in m.parts]
    if workspaces:
        ws = workspaces[0]
        manifest = ws / "entities.json"
        detail = f"workspace {ws}"
        if manifest.exists():
            try:
                m = json.loads(manifest.read_text(encoding="utf-8"))
                detail += f", {len(m.get('entities', []))} entities, revision {m.get('revision')}"
            except ValueError:
                detail += ", entities.json is not valid JSON"
        out.append(check("workspace", "ok" if manifest.exists() else "warn", detail,
                         "" if manifest.exists() else "Run `npx liminal sync` to write entities.json."))
        levels = sorted((ws / "levels").glob("*.lm")) if (ws / "levels").is_dir() else []
        out.append(check("levels", "ok" if levels else "warn",
                         f"{len(levels)} level(s) in {ws / 'levels'}" if levels else "No exported levels yet",
                         "" if levels else "Build one in Blender and export it; the liminal-levels skill walks through it."))
    else:
        out.append(check("workspace", "fail", "No Liminal workspace (.lmworkspace marker) in this project",
                         "Run `npx liminal sync` once the registry and liminal.config.ts exist; it creates _blender/."))
    return out


def main():
    parser = argparse.ArgumentParser(description="Liminal environment doctor")
    parser.add_argument("--project", default=os.getcwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.project).resolve()
    results = [python_check(), node_check(), mcp_check(), blender_check()]
    results += bridge_checks()
    results += project_checks(root)
    if args.json:
        print(json.dumps({"project": str(root), "checks": results}, indent=2))
    else:
        width = max(len(r["check"]) for r in results)
        for r in results:
            print(f"[{r['status']:4}] {r['check']:<{width}}  {r['detail']}")
            if r["fix"]:
                print(f"       -> {r['fix']}")
    sys.exit(1 if any(r["status"] == "fail" for r in results) else 0)


if __name__ == "__main__":
    main()
