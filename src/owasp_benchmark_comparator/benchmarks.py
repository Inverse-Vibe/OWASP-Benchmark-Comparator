"""The benchmarks, the tools, and running OWASP's scripts against fresh clones.

Every script runs in a working clone under `work/`, never in a submodule: tool
scripts write into `results/`, and `createScorecards.sh` empties `scorecard/`
before writing its own. The clone is reset to the pinned commit before each run,
so it holds exactly what OWASP published at that commit and nothing else.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

#: The repository root: src/owasp_benchmark_comparator/ -> src/ -> root.
ROOT: Final[Path] = Path(__file__).resolve().parents[2]
#: One folder per tool, holding everything that tool needs.
TOOLS: Final[Path] = ROOT / "tools"
SCORER: Final[str] = "BenchmarkUtils"
PLUGIN: Final[str] = "org.owasp:benchmarkutils-maven-plugin"


class RunError(RuntimeError):
    """A script or command that failed, and the tail of what it printed."""


@dataclass(frozen=True, slots=True)
class Benchmark:
    id: str
    title: str
    #: The submodule, at the repository root.
    directory: str
    #: How OWASP names a results file for this benchmark.
    results_prefix: str


BENCHMARKS: Final[dict[str, Benchmark]] = {
    "java": Benchmark("java", "OWASP Benchmark for Java", "BenchmarkJava", "Benchmark_1.2-"),
    "python": Benchmark(
        "python", "OWASP Benchmark for Python", "BenchmarkPython", "BenchmarkPython-"
    ),
}


@dataclass(frozen=True, slots=True)
class Tool:
    """A folder under tools/: its `tool.toml` and everything its scripts use."""

    id: str
    name: str
    directory: Path
    #: Language -> the script that runs it: `./x` in the tool's folder, anything
    #: else a script the benchmark repository ships.
    scripts: dict[str, str]
    #: Environment variables it cannot run without - an account token, say.
    requires: tuple[str, ...] = ()

    def script(self, language: str, clone: Path) -> Path:
        script = self.scripts[language]
        if script.startswith("./"):
            return self.directory / script[2:]
        return clone / script


def load_tools(root: Path = TOOLS) -> list[Tool]:
    tools = []
    for manifest in sorted(root.glob("*/tool.toml")):
        entry = tomllib.loads(manifest.read_text(encoding="utf-8"))
        tools.append(
            Tool(
                id=manifest.parent.name,
                name=entry.get("name", manifest.parent.name),
                directory=manifest.parent,
                scripts={key: value for key, value in entry.items() if key in BENCHMARKS},
                requires=tuple(entry.get("requires", ())),
            )
        )
    return tools


@dataclass(frozen=True, slots=True)
class Environment:
    """Where `bash`, `git` and `mvn` come from, and the variables scripts inherit."""

    variables: dict[str, str]

    @classmethod
    def build(cls, java_home: str | None = None, maven_home: str | None = None) -> Environment:
        variables = dict(os.environ)
        prepend = []
        if java_home:
            variables["JAVA_HOME"] = java_home
            prepend.append(str(Path(java_home) / "bin"))
        if maven_home:
            prepend.append(str(Path(maven_home) / "bin"))
        if prepend:
            variables["PATH"] = os.pathsep.join([*prepend, variables.get("PATH", "")])
        return cls(variables)

    def which(self, command: str) -> str:
        found = shutil.which(command, path=self.variables.get("PATH"))
        if found is None:
            raise RunError(f"`{command}` is not on PATH")
        return found

    def run(
        self, command: list[str], cwd: Path, log: Path, extra: dict[str, str] | None = None
    ) -> None:
        """Run to completion, keeping everything it printed in `log`."""
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("w", encoding="utf-8") as out:
            done = subprocess.run(
                command,
                cwd=cwd,
                env={**self.variables, **(extra or {})},
                stdout=out,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if done.returncode != 0:
            tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-15:]
            raise RunError(f"exit {done.returncode} - see {log}\n" + "\n".join(tail))


def pinned(submodule: Path, env: Environment) -> str:
    done = subprocess.run(
        [env.which("git"), "-C", str(submodule), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        env=env.variables,
        check=False,
    )
    if done.returncode != 0:
        raise RunError(f"{submodule.name} is not checked out: git submodule update --init")
    return done.stdout.strip()


def fresh_clone(submodule: Path, clone: Path, env: Environment) -> None:
    """`clone` holds exactly the submodule's pinned commit, nothing added or left over."""
    git = env.which("git")
    commit = pinned(submodule, env)
    if not (clone / ".git").exists():
        if clone.exists():
            shutil.rmtree(clone)
        clone.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [git, "clone", "-q", "--no-checkout", str(submodule), str(clone)],
            env=env.variables,
            check=True,
        )
    subprocess.run(
        [git, "-C", str(clone), "checkout", "-q", "--force", "--detach", commit],
        env=env.variables,
        check=True,
    )
    subprocess.run([git, "-C", str(clone), "clean", "-q", "-fdx"], env=env.variables, check=True)


def _inject_readers(clone: Path) -> list[str]:
    """Copy custom SARIF readers shipped under ``tools/*/benchmarkutils/`` into
    the BenchmarkUtils clone and register them in ``Reader.java`` (one import,
    one ``new X(),``), so a tool OWASP upstream has no reader for - InverseVibe,
    say - scores with no manual edit. Idempotent, and registration order does
    not matter to the scorer."""
    java = clone / "plugin" / "src" / "main" / "java"
    reader_java = java / "org" / "owasp" / "benchmarkutils" / "score" / "parsers" / "Reader.java"
    readers = sorted(TOOLS.glob("*/benchmarkutils/*.java"))
    if not readers or not reader_java.is_file():
        return []
    text = reader_java.read_text(encoding="utf-8")
    done: list[str] = []
    for src in readers:
        cls = src.stem
        body = src.read_text(encoding="utf-8")
        match = re.search(r"package\s+([\w.]+)\s*;", body)
        pkg = match.group(1) if match else "org.owasp.benchmarkutils.score.parsers.sarif"
        dest = java.joinpath(*pkg.split(".")) / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        if f"new {cls}(" in text:
            done.append(cls)
            continue
        out, added_import, added_new = [], False, False
        for line in text.splitlines(keepends=True):
            if not added_import and line.startswith(
                "import org.owasp.benchmarkutils.score.parsers.sarif."
            ):
                out.append(f"import {pkg}.{cls};\n")
                added_import = True
            if not added_new and re.match(r"\s*new [A-Za-z0-9_]+Reader\(\),", line):
                indent = line[: len(line) - len(line.lstrip())]
                out.append(f"{indent}new {cls}(),\n")
                added_new = True
            out.append(line)
        text = "".join(out)
        done.append(cls)
    reader_java.write_text(text, encoding="utf-8")
    return done


def install_scorer(work: Path, env: Environment) -> str:
    """BenchmarkUtils, built and installed from its pin the way its README says:
    `mvn install`, with any custom SARIF readers under `tools/*/benchmarkutils/`
    injected first (see `_inject_readers`). Skipped when the same commit AND the
    same readers were last installed."""
    submodule = ROOT / SCORER
    commit = pinned(submodule, env)
    readers = sorted(TOOLS.glob("*/benchmarkutils/*.java"))
    marker = commit + "".join(
        f"\n{path.relative_to(ROOT).as_posix()}:{hashlib.sha256(path.read_bytes()).hexdigest()}"
        for path in readers
    )
    stamp = work / f"{SCORER}.installed"
    if stamp.exists() and stamp.read_text() == marker:
        return commit
    clone = work / SCORER
    fresh_clone(submodule, clone, env)
    injected = _inject_readers(clone)
    if injected:
        print(f"[scorer] injected reader(s): {', '.join(injected)}", flush=True)
    # Through bash, as OWASP's own scripts call it: Maven's launcher is a shell
    # script, which a Windows PATH lookup does not see.
    env.run(
        [env.which("bash"), "-c", "mvn -B -DskipTests install"],
        clone,
        work / "logs" / "scorer.log",
    )
    stamp.write_text(marker)
    return commit
