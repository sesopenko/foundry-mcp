"""Container liveness: a GM connection is not required for server health."""
import json
import os
from urllib.request import ProxyHandler, build_opener


def main():
    port = int(os.environ.get("FOUNDRY_MCP_PORT", "8000"))
    with build_opener(ProxyHandler({})).open(f"http://127.0.0.1:{port}/health", timeout=2) as response:
        if response.status != 200 or json.load(response).get("status") != "ok":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
