"""The tool list, the working clones, and reading the scorecard."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from owasp_benchmark_comparator import compare
from owasp_benchmark_comparator.benchmarks import (
    BENCHMARKS,
    ROOT,
    SCORER,
    Environment,
    fresh_clone,
    load_tools,
)
from owasp_benchmark_comparator.scorecard import leaderboard, render

if TYPE_CHECKING:
    from pathlib import Path

HOME = """
<html><body>
<table>
  <tr><th>Tool</th><th>Type</th><th>TPR*</th><th>FPR*</th><th>Score*</th></tr>
  <tr><td>FindBugs v3.0.1</td><td>SAST</td><td>5.12%</td><td>5.19%</td><td>-0.07%</td></tr>
  <tr><td>SonarQube Java Plugin v3.14</td><td>SAST</td><td>50.36%</td><td>17.02%</td>
      <td>33.34%</td></tr>
</table>
<table>
  <tr><th>True Positive (TP)</th><th>Tests with real vulnerabilities reported.</th></tr>
</table>
</body></html>
"""


def _checked_out(name: str) -> bool:
    path = ROOT / name
    return path.exists() and any(path.iterdir())


def test_the_leaderboard_is_the_tool_table_best_first() -> None:
    rows = leaderboard(HOME)
    assert [row.tool for row in rows] == ["SonarQube Java Plugin v3.14", "FindBugs v3.0.1"]
    assert (rows[0].tpr, rows[0].fpr, rows[0].score) == ("50.36%", "17.02%", "33.34%")
    assert "33.34%" in render("t", rows)


def test_the_glossary_table_is_not_mistaken_for_tools() -> None:
    assert all("Positive" not in row.tool for row in leaderboard(HOME))


def test_every_tool_script_is_one_its_benchmark_ships() -> None:
    """A tool is only ever an OWASP script - never something of ours."""
    tools = load_tools()
    assert tools
    for tool in tools:
        assert tool.scripts
        for language, script in tool.scripts.items():
            directory = ROOT / BENCHMARKS[language].directory
            if not _checked_out(BENCHMARKS[language].directory):
                pytest.skip(f"{directory.name} not checked out")
            assert (directory / script).is_file(), f"{tool.id}: {script} not in {directory.name}"


@pytest.mark.parametrize("name", [b.directory for b in BENCHMARKS.values()] + [SCORER])
def test_each_submodule_is_pristine(name: str) -> None:
    if not _checked_out(name):
        pytest.skip(f"{name} not checked out")
    done = subprocess.run(
        ["git", "-C", str(ROOT / name), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout == ""


def test_a_clone_is_reset_to_the_pin_every_time(tmp_path: Path) -> None:
    origin = tmp_path / "origin"
    origin.mkdir()
    git = ["git", "-C", str(origin)]
    subprocess.run([*git, "init", "-q"], check=True)
    (origin / "results").mkdir()
    (origin / "results" / "shipped.json").write_text("{}")
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run(
        [*git, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "pin"], check=True
    )

    env = Environment.build()
    clone = tmp_path / "work" / "origin"
    fresh_clone(origin, clone, env)
    (clone / "results" / "from-a-tool.json").write_text("{}")
    (clone / "results" / "shipped.json").write_text("edited")

    fresh_clone(origin, clone, env)
    assert sorted(path.name for path in (clone / "results").iterdir()) == ["shipped.json"]
    assert (clone / "results" / "shipped.json").read_text() == "{}"


def test_an_unknown_tool_is_refused_before_anything_runs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert compare.main(["java", "--tool", "no-such-tool"]) == 1
    assert "no java tool called no-such-tool" in capsys.readouterr().err


def test_the_language_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        compare.main([])
    assert "language" in capsys.readouterr().err
