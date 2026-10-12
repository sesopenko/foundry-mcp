"""Start a persistent, visible development Chrome and connect its MCP server."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse
from urllib.request import build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / ".browser-dev/chrome-profile"


def development_enabled(path):
    if not path.exists():
        return False
    for line in path.read_text().splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "FOUNDRY_MCP_DEV_EXECUTION":
            return value.strip() == "true"
    return False


def debug_endpoint(profile):
    try:
        port, browser_path = (profile / "DevToolsActivePort").read_text().splitlines()[:2]
        if not 0 < int(port) < 65536 or not browser_path.startswith("/devtools/browser/"):
            return None
        return f"http://127.0.0.1:{int(port)}", browser_path
    except (OSError, ValueError):
        return None


def browser_alive(endpoint):
    if endpoint is None:
        return False
    url, browser_path = endpoint
    try:
        with build_opener(ProxyHandler({})).open(url + "/json/version", timeout=0.5) as response:
            info = json.load(response)
        return urlparse(info.get("webSocketDebuggerUrl", "")).path == browser_path
    except (OSError, ValueError):
        return False


def ensure_browser():
    if not development_enabled(ROOT / ".env.mcp"):
        raise SystemExit("Browser automation requires FOUNDRY_MCP_DEV_EXECUTION=true in .env.mcp")
    endpoint = debug_endpoint(PROFILE)
    if browser_alive(endpoint):
        return endpoint[0]
    executable = shutil.which("google-chrome")
    if not executable:
        raise SystemExit("Install Google Chrome before starting the development browser")
    PROFILE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(PROFILE.parent, 0o700)
    os.chmod(PROFILE, 0o700)
    with (PROFILE.parent / "chrome.log").open("ab") as log:
        process = subprocess.Popen([
            executable, "--remote-debugging-port=0", "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={PROFILE}", "--no-first-run", "--no-default-browser-check",
            "--new-window", "http://localhost:30000/",
        ], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    for _ in range(100):
        endpoint = debug_endpoint(PROFILE)
        if browser_alive(endpoint):
            return endpoint[0]
        if process.poll() is not None:
            break
        time.sleep(0.1)
    raise SystemExit("Development Chrome did not start; inspect .browser-dev/chrome.log")


def main():
    if sys.argv[1:] not in (["start"], ["mcp"]):
        raise SystemExit("Usage: browser_dev.py {start|mcp}")
    url = ensure_browser()
    if sys.argv[1:] == ["start"]:
        print("Development Chrome ready; persistent profile: .browser-dev/chrome-profile")
        return
    executable = ROOT / "node_modules/.bin/chrome-devtools-mcp"
    if not executable.exists():
        raise SystemExit("Missing Chrome DevTools MCP; run npm ci first")
    # Attaching leaves the user's development browser open when MCP disconnects.
    os.environ["CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS"] = "1"
    os.execv(str(executable), [str(executable), f"--browser-url={url}",
        "--no-usage-statistics", "--no-performance-crux"])


if __name__ == "__main__":
    main()
