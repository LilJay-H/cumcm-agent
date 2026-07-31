from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.workspace import RunWorkspace
from ..runtime.claude import ClaudeRuntime


def _bounded(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = int(limit * 0.7)
    tail = limit - head
    return (
        text[:head]
        + "\n\n[中间内容因上下文预算省略；不得据此臆造。]\n\n"
        + text[-tail:]
    )


def build_context(
    workspace: RunWorkspace,
    inputs: list[str],
    max_total_chars: int,
    max_artifact_chars: int,
) -> str:
    sections: list[str] = []
    remaining = max_total_chars
    for relative in inputs:
        path = workspace.path(relative)
        if not path.exists():
            raise FileNotFoundError(f"stage input missing: {relative}")
        text = path.read_text(encoding="utf-8", errors="replace")
        text = _bounded(text, min(max_artifact_chars, remaining))
        sections.append(f"### 工件：{relative}\n\n{text}")
        remaining -= len(text)
        if remaining <= 0:
            break
    return "\n\n".join(sections)


def run_llm_stage(
    project_root: Path,
    workspace: RunWorkspace,
    runtime: ClaudeRuntime,
    stage: dict[str, Any],
    context_config: dict[str, Any],
) -> tuple[Path, str]:
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
    prompt = (
        common
        + "\n\n"
        + instruction
        + "\n\n# 本阶段输入工件\n\n"
        + context
    )
    response = runtime.invoke(
        stage["id"],
        prompt,
        allowed_tools=stage.get("allowed_tools", []),
    )
    output = workspace.write_text(stage["output"], response.text)
    workspace.register_artifact(
        stage["output"],
        stage.get("kind", "analysis"),
        stage["id"],
        parents=stage["inputs"],
    )
    return output, response.model

