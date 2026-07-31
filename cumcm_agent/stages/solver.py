from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from ..core.workspace import RunWorkspace
from ..runtime.claude import ClaudeRuntime
from .llm_stage import build_context


def extract_python(text: str) -> str:
    match = re.search(r"```python\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip() + "\n"
    match = re.search(r"```\s*(.*?)```", text, flags=re.DOTALL)
    if match:
        return match.group(1).strip() + "\n"
    return text.strip() + "\n"


def run_solver_stage(
    project_root: Path,
    workspace: RunWorkspace,
    runtime: ClaudeRuntime,
    stage: dict[str, Any],
    context_config: dict[str, Any],
    solver_config: dict[str, Any],
) -> tuple[list[Path], str, float]:
    common = (project_root / "prompts" / "00_common.md").read_text(
        encoding="utf-8"
    )
    instruction = (project_root / "prompts" / stage["prompt"]).read_text(
        encoding="utf-8"
    )
    context = build_context(
        workspace,
        stage["inputs"],
        int(context_config["max_total_chars"]),
        int(context_config["max_artifact_chars"]),
    )
    response = runtime.invoke(
        stage["id"],
        common + "\n\n" + instruction + "\n\n# 输入工件\n\n" + context,
        allowed_tools=[],
    )
    raw_path = workspace.write_text("artifacts/04_solver_response.md", response.text)
    workspace.register_artifact(
        "artifacts/04_solver_response.md",
        "llm_response",
        stage["id"],
        parents=stage["inputs"],
    )
    code = extract_python(response.text)
    code_path = workspace.write_text("generated/solver.py", code)
    workspace.register_artifact(
        "generated/solver.py",
        "source_code",
        stage["id"],
        parents=stage["inputs"],
    )

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["MPLBACKEND"] = "Agg"
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, str(code_path)],
        cwd=workspace.root,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=int(solver_config.get("timeout_seconds", 300)),
        check=False,
    )
    duration = time.perf_counter() - started
    workspace.write_text("logs/solver_stdout.txt", completed.stdout)
    workspace.write_text("logs/solver_stderr.txt", completed.stderr)
    run_record = {
        "command": [sys.executable, "generated/solver.py"],
        "returncode": completed.returncode,
        "duration_seconds": round(duration, 3),
        "stdout": "logs/solver_stdout.txt",
        "stderr": "logs/solver_stderr.txt",
    }
    workspace.write_json("results/solver_run.json", run_record)
    if completed.returncode != 0:
        raise RuntimeError(
            "generated solver failed: " + completed.stderr[-2000:]
        )
    results_path = workspace.path("results/results.json")
    if not results_path.exists():
        raise RuntimeError("generated solver did not create results/results.json")
    json.loads(results_path.read_text(encoding="utf-8"))
    figures = sorted(workspace.path("figures").glob("*.png"))
    minimum = int(solver_config.get("minimum_figures", 2))
    if len(figures) < minimum:
        raise RuntimeError(
            f"generated solver produced {len(figures)} figures; need {minimum}"
        )
    workspace.register_artifact(
        "results/results.json",
        "numeric_results",
        "solver_execution",
        parents=["generated/solver.py"],
    )
    workspace.register_artifact(
        "results/solver_run.json",
        "execution_record",
        "solver_execution",
        parents=["generated/solver.py"],
    )
    for figure in figures:
        workspace.register_artifact(
            figure.relative_to(workspace.root),
            "figure",
            "solver_execution",
            parents=["results/results.json"],
        )
    return [raw_path, code_path, results_path, *figures], response.model, duration

