"""Keep `leaderboard.html` in step with the scorecards.

The page carries its data in one JSON block; this rewrites that block and
nothing else. Each run replaces the rows its scorecard has and keeps the rest,
so running one tool does not drop the others. Every number is copied off a
BenchmarkUtils scorecard - nothing here computes one.

The scorecard itself is copied to `scorecards/<language>/`, so each row links to
the full report BenchmarkUtils wrote for that tool. Files are overwritten, never
deleted: a tool from an earlier run keeps its report.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from pathlib import Path

    from owasp_benchmark_comparator.benchmarks import Benchmark
    from owasp_benchmark_comparator.scorecard import Row

BLOCK: Final[re.Pattern[str]] = re.compile(
    r'(<script id="leaderboard-data" type="application/json">)(.*?)(</script>)', re.DOTALL
)


def _percent(text: str) -> float:
    return float(text.rstrip("%"))


def report_name(row: Row, reports: Path) -> str | None:
    """The page BenchmarkUtils wrote for this tool, if it is there."""
    wanted = f"_Scorecard_for_{row.tool.replace(' ', '_')}.html"
    found = sorted(path.name for path in reports.glob("*.html") if path.name.endswith(wanted))
    return found[0] if found else None


def merge(
    data: dict[str, Any],
    benchmark: Benchmark,
    pin: str,
    rows: list[Row],
    today: str,
    reports: Path | None = None,
) -> dict[str, Any]:
    """`data` with this scorecard's rows in place of the ones it already had."""
    entry = data.setdefault(benchmark.id, {})
    previous = {row["tool"]: row for row in entry.get("rows", [])}
    for row in rows:
        unchanged = previous.get(row.tool, {})
        report = report_name(row, reports) if reports else None
        previous[row.tool] = {
            "tool": row.tool,
            "type": row.kind,
            "tpr": _percent(row.tpr),
            "fpr": _percent(row.fpr),
            "score": _percent(row.score),
            # When it was last scored here; a rerun with the same numbers keeps it.
            "scored": unchanged.get("scored", today)
            if unchanged.get("score") == _percent(row.score)
            else today,
            "report": f"scorecards/{benchmark.id}/{report}" if report else None,
        }
    entry.update(
        title=benchmark.title,
        repository=benchmark.directory,
        pin=pin,
        updated=today,
        home=f"scorecards/{benchmark.id}/Scorecard_Home.html",
        rows=sorted(previous.values(), key=lambda row: row["score"], reverse=True),
    )
    return data


def publish(scorecard: Path, reports: Path) -> None:
    """Copy the scorecard BenchmarkUtils wrote next to the page."""
    reports.mkdir(parents=True, exist_ok=True)
    shutil.copytree(scorecard, reports, dirs_exist_ok=True)


def update(
    page: Path,
    benchmark: Benchmark,
    pin: str,
    rows: list[Row],
    scorecard: Path,
) -> None:
    reports = page.parent / "scorecards" / benchmark.id
    publish(scorecard, reports)
    html = page.read_text(encoding="utf-8")
    found = BLOCK.search(html)
    if found is None:
        raise ValueError(f"{page} has no leaderboard-data block")
    data = json.loads(found.group(2) or "{}")
    today = datetime.now(UTC).date().isoformat()
    merged = merge(data, benchmark, pin, rows, today, reports)
    block = "\n" + json.dumps(merged, indent=2) + "\n"
    page.write_text(
        html[: found.start(2)] + block + html[found.end(2) :], encoding="utf-8", newline="\n"
    )
