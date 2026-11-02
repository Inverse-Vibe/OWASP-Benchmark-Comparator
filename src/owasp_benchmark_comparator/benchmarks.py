"""The benchmarks, the tools, and running OWASP's scripts against fresh clones.

Every script runs in a working clone under `work/`, never in a submodule: tool
scripts write into `results/`, and `createScorecards.sh` empties `scorecard/`
before writing its own. The clone is reset to the pinned commit before each run,
so it holds exactly what OWASP published at that commit and nothing else.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Final

#: The repository root: src/owasp_benchmark_comparator/ -> src/ -> root.
ROOT: Final[Path] = Path(__file__).resolve().parents[2]
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


BENCHMARKS: Final[dict[str, Benchmark]] = {
    "java": Benchmark("java", "OWASP Benchmark for Java", "BenchmarkJava"),
    "python": Benchmark("python", "OWASP Benchmark for Python", "BenchmarkPython"),
}


@dataclass(frozen=True, slots=True)
class Tool:
    id: str
    name: str
    #: Language -> the script, inside that benchmark's repository, that runs it.
    scripts: dict[str, str]


def load_tools() -> list[Tool]:
    data = tomllib.loads(
        resources.files(__package__).joinpath("tools.toml").read_text(encoding="utf-8")
    )
    tools = []
    for tool_id, entry in data.items():
        scripts = {key: value for key, value in entry.items() if key in BENCHMARKS}
        tools.append(Tool(id=tool_id, name=entry.get("name", tool_id), scripts=scripts))
    return sorted(tools, key=lambda tool: tool.id)


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

    def run(self, command: list[str], cwd: Path, log: Path) -> None:
        """Run to completion, keeping everything it printed in `log`."""
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("w", encoding="utf-8") as out:
            done = subprocess.run(
                command,
                cwd=cwd,
                env=self.variables,
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


def install_scorer(work: Path, env: Environment) -> str:
    """BenchmarkUtils, built and installed from its pin the way its README says:
    `mvn install`. Skipped when that commit is what was last installed."""
    submodule = ROOT / SCORER
    commit = pinned(submodule, env)
    stamp = work / f"{SCORER}.installed"
    if stamp.exists() and stamp.read_text().strip() == commit:
        return commit
    clone = work / SCORER
    fresh_clone(submodule, clone, env)
    # Through bash, as OWASP's own scripts call it: Maven's launcher is a shell
    # script, which a Windows PATH lookup does not see.
    env.run(
        [env.which("bash"), "-c", "mvn -B -DskipTests install"],
        clone,
        work / "logs" / "scorer.log",
    )
    stamp.write_text(commit + "\n")
    return commit
