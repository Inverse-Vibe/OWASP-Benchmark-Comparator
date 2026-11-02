"""Write a SonarQube project's issues and hotspots as BenchmarkUtils reads them.

    python3 export.py <host> <token> <project> <out.json>

The same file BenchmarkJava's SonarReport writes - `{"issues": [...],
"hotspots": [...]}`, each entry exactly as the API returned it, for
SonarQubeJsonReader to map and score. Issues are the VULNERABILITY type, as
SonarReport asks for. Standard library only.
"""

from __future__ import annotations

import base64
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

PAGE = 500
#: Sonar's search APIs stop at 10,000 results however they are paged.
LIMIT = 10_000


def pages(host: str, token: str, path: str, query: dict[str, str], key: str) -> list[Any]:
    auth = base64.b64encode(f"{token}:".encode()).decode()
    found: list[Any] = []
    page = 1
    while True:
        url = f"{host}{path}?{urllib.parse.urlencode({**query, 'p': page, 'ps': PAGE})}"
        request = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})  # noqa: S310
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
            body = json.load(response)
        total = body["paging"]["total"]
        if total > LIMIT:
            raise SystemExit(f"{path} has {total} results; SonarQube returns at most {LIMIT}")
        found.extend(body[key])
        if not body[key] or len(found) >= total:
            return found
        page += 1


def main() -> None:
    host, token, project, out = sys.argv[1:5]
    issues = pages(
        host,
        token,
        "/api/issues/search",
        {"components": project, "types": "VULNERABILITY"},
        "issues",
    )
    hotspots = pages(host, token, "/api/hotspots/search", {"project": project}, "hotspots")
    Path(out).write_text(
        json.dumps({"issues": issues, "hotspots": hotspots}, indent=2), encoding="utf-8"
    )
    print(f"{len(issues)} issues, {len(hotspots)} hotspots -> {out}")


if __name__ == "__main__":
    main()
