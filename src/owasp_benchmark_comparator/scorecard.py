"""The leaderboard on the scorecard BenchmarkUtils writes - read, not computed."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class Row:
    tool: str
    kind: str
    tpr: str
    fpr: str
    score: str

    @property
    def value(self) -> float:
        try:
            return float(self.score.rstrip("%"))
        except ValueError:
            return float("-inf")


class _Tables(HTMLParser):
    """The rows of every table on a page, as text."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self.tables:
            self.tables[-1].append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def leaderboard(html: str) -> list[Row]:
    """The table headed `Tool | Type | ... | Score`, best score first."""
    parser = _Tables()
    parser.feed(html)
    for table in parser.tables:
        if not table or not table[0] or table[0][0].strip() != "Tool":
            continue
        rows = [
            Row(tool=cells[0], kind=cells[1], tpr=cells[-3], fpr=cells[-2], score=cells[-1])
            for cells in table[1:]
            if len(cells) >= 5 and cells[-1].endswith("%")
        ]
        return sorted(rows, key=lambda row: row.value, reverse=True)
    return []


def read(home: Path) -> list[Row]:
    return leaderboard(home.read_text(encoding="utf-8"))


def render(title: str, rows: list[Row]) -> str:
    lines = [title, f"  {'#':>2}  {'Tool':34s} {'Type':6s} {'TPR':>8s} {'FPR':>8s} {'Score':>8s}"]
    lines += [
        f"  {rank:>2}  {row.tool:34s} {row.kind:6s} {row.tpr:>8s} {row.fpr:>8s} {row.score:>8s}"
        for rank, row in enumerate(rows, start=1)
    ]
    return "\n".join(lines)
