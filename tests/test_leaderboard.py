"""leaderboard.html: rows copied off scorecards, merged run over run."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from owasp_benchmark_comparator import leaderboard
from owasp_benchmark_comparator.benchmarks import BENCHMARKS, ROOT
from owasp_benchmark_comparator.scorecard import Row

if TYPE_CHECKING:
    from pathlib import Path

JAVA = BENCHMARKS["java"]


def _row(tool: str, score: str) -> Row:
    return Row(tool=tool, kind="SAST", tpr="50.00%", fpr="10.00%", score=score)


def test_a_run_keeps_the_rows_it_did_not_score() -> None:
    first = leaderboard.merge(
        {}, JAVA, "abc", [_row("A v1", "40.00%"), _row("Ref v1", "10.00%")], {"Ref v1"}, "d1"
    )
    second = leaderboard.merge(first, JAVA, "abc", [_row("B v2", "20.00%")], set(), "d2")
    rows = second["java"]["rows"]
    assert [row["tool"] for row in rows] == ["A v1", "B v2", "Ref v1"]
    assert {row["tool"]: row["source"] for row in rows} == {
        "A v1": "run",
        "B v2": "run",
        "Ref v1": "reference",
    }
    assert second["java"]["updated"] == "d2"


def test_a_rerun_with_the_same_score_keeps_its_date() -> None:
    data = leaderboard.merge({}, JAVA, "abc", [_row("A v1", "40.00%")], set(), "d1")
    data = leaderboard.merge(data, JAVA, "abc", [_row("A v1", "40.00%")], set(), "d2")
    assert data["java"]["rows"][0]["scored"] == "d1"
    data = leaderboard.merge(data, JAVA, "abc", [_row("A v1", "41.00%")], set(), "d3")
    assert data["java"]["rows"][0]["scored"] == "d3"


def test_each_row_links_the_report_benchmarkutils_wrote(tmp_path: Path) -> None:
    (tmp_path / "Benchmark_v1.2_Scorecard_for_SonarQube_v26.10.html").write_text("x")
    data = leaderboard.merge(
        {},
        JAVA,
        "abc",
        [_row("SonarQube v26.10", "31.43%"), _row("Gone", "1.00%")],
        set(),
        "d1",
        tmp_path,
    )
    reports = {row["tool"]: row["report"] for row in data["java"]["rows"]}
    assert reports == {
        "SonarQube v26.10": "scorecards/java/Benchmark_v1.2_Scorecard_for_SonarQube_v26.10.html",
        "Gone": None,
    }


def test_update_rewrites_only_the_data_block(tmp_path: Path) -> None:
    page = tmp_path / "leaderboard.html"
    page.write_text(
        '<p>keep</p><script id="leaderboard-data" type="application/json">\n{}\n</script><p>me</p>',
        encoding="utf-8",
    )
    scorecard = tmp_path / "scorecard"
    scorecard.mkdir()
    (scorecard / "Scorecard_Home.html").write_text("home")
    leaderboard.update(page, JAVA, "abc", [_row("A v1", "40.00%")], set(), scorecard)
    html = page.read_text(encoding="utf-8")
    assert html.startswith("<p>keep</p>")
    assert html.endswith("</script><p>me</p>")
    data = json.loads(leaderboard.BLOCK.search(html).group(2))  # type: ignore[union-attr]
    assert data["java"]["rows"][0]["tool"] == "A v1"
    assert (tmp_path / "scorecards" / "java" / "Scorecard_Home.html").exists()


def test_the_shipped_page_has_a_data_block() -> None:
    assert leaderboard.BLOCK.search((ROOT / "leaderboard.html").read_text(encoding="utf-8"))
