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


def get(host: str, token: str, path: str, query: dict[str, Any]) -> dict[str, Any]:
    auth = base64.b64encode(f"{token}:".encode()).decode()
    url = f"{host}{path}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})  # noqa: S310
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        body: dict[str, Any] = json.load(response)
        return body


def pages(host: str, token: str, path: str, query: dict[str, str], key: str) -> list[Any]:
    found: list[Any] = []
    page = 1
    while True:
        body = get(host, token, path, {**query, "p": page, "ps": PAGE})
        total = body["paging"]["total"]
        if total > LIMIT:
            raise SystemExit(f"{path} has {total} results; SonarQube returns at most {LIMIT}")
        found.extend(body[key])
        if not body[key] or len(found) >= total:
            return found
        page += 1


def files(host: str, token: str, project: str) -> list[dict[str, Any]]:
    tree = {"component": project, "qualifiers": "FIL"}
    return pages(host, token, "/api/components/tree", tree, "components")


def vulnerabilities(host: str, token: str, project: str) -> list[Any]:
    """Rule by rule, and a rule with more than one search returns file by file:
    BenchmarkJava has ~18,000, ~16,700 of them from a single rule."""
    query = {"components": project, "types": "VULNERABILITY"}
    summary = get(host, token, "/api/issues/search", {**query, "ps": 1, "facets": "rules"})
    rules = {
        value["val"]: value["count"]
        for facet in summary["facets"]
        if facet["property"] == "rules"
        for value in facet["values"]
    }
    if sum(rules.values()) != summary["paging"]["total"]:
        raise SystemExit("the rules facet does not cover every issue; some would be missed")
    issues: list[Any] = []
    for rule, count in sorted(rules.items()):
        print(f"  {rule}: {count}")
        if count <= LIMIT:
            issues += pages(host, token, "/api/issues/search", {**query, "rules": rule}, "issues")
            continue
        for file in files(host, token, project):
            issues += pages(
                host,
                token,
                "/api/issues/search",
                {**query, "components": file["key"], "rules": rule},
                "issues",
            )
    if len(issues) != summary["paging"]["total"]:
        raise SystemExit(f"fetched {len(issues)} of {summary['paging']['total']} issues")
    return issues


def hotspots(host: str, token: str, project: str) -> list[Any]:
    """All at once, or file by file when there are more than one search returns."""
    first = get(host, token, "/api/hotspots/search", {"project": project, "ps": 1})
    if first["paging"]["total"] <= LIMIT:
        return pages(host, token, "/api/hotspots/search", {"project": project}, "hotspots")
    found: list[Any] = []
    for file in files(host, token, project):
        found += pages(
            host,
            token,
            "/api/hotspots/search",
            {"project": project, "files": file["path"]},
            "hotspots",
        )
    return found


def main() -> None:
    host, token, project, out = sys.argv[1:5]
    issues = vulnerabilities(host, token, project)
    hotspots_found = hotspots(host, token, project)
    Path(out).write_text(
        json.dumps({"issues": issues, "hotspots": hotspots_found}, indent=2), encoding="utf-8"
    )
    print(f"{len(issues)} issues, {len(hotspots_found)} hotspots -> {out}")


if __name__ == "__main__":
    main()
