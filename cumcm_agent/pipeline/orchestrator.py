from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from ..core.models import StageRecord
from ..core.workspace import RunWorkspace, now_iso
from ..evaluation.rubric import evaluate_run
from ..runtime.claude import ClaudeRuntime
from ..stages.llm_stage import run_llm_stage
from ..stages.solver import run_solver_stage
from ..stages.web_research import run_web_research_stage
from ..tools.paper_renderer import render_paper, render_pdf_preview
from ..tools.paper_finalizer import finalize_paper


class Orchestrator:
    def __init__(
        self,
        project_root: Path,
        config: dict[str, Any],
        run_id: str,
        auto_approve: bool = False,
    ):
        self.project_root = project_root.resolve()
        self.config = config
        self.workspace = RunWorkspace(self.project_root, run_id)
        self.runtime = ClaudeRuntime(config["runtime"], self.workspace)
        self.auto_approve = auto_approve

    def initialize(self, problem: Path) -> None:
        source = problem.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = self.workspace.path("input/problem.md")
        shutil.copyfile(source, destination)
        self.workspace.register_artifact(
            "input/problem.md", "problem_statement", "intake"
        )
        self._prepare_problem_context(destination)
        self.workspace.update_manifest(
            source_problem=str(source),
            runtime={
                "command": self.config["runtime"]["command"],
                "requested_model": self.config["runtime"]["model"],
            },
            config=self.config,
        )

    def _prepare_problem_context(self, source: Path) -> None:
        text = source.read_text(encoding="utf-8", errors="replace")
        context_config = self.config["context"]
        threshold = int(context_config["chunk_threshold_chars"])
        if len(text) <= threshold:
            self.workspace.write_text("input/problem_context.md", text)
            producer = "intake_exact"
        else:
            chunk_size = int(context_config["chunk_chars"])
            overlap = int(context_config["chunk_overlap_chars"])
            summaries: list[str] = []
            start = 0
            index = 1
            while start < len(text):
                chunk = text[start : start + chunk_size]
                prompt = (
                    "将以下赛题片段压缩成中文事实清单。保留所有任务、数字、"
                    "单位、约束和交付要求；不得求解、不得补充外部知识。"
                    f"\n\n片段 {index}：\n\n{chunk}"
                )
                response = self.runtime.invoke(
                    f"context_chunk_{index}", prompt, allowed_tools=[]
                )
                summaries.append(f"## 片段 {index}\n\n{response.text}")
                if start + chunk_size >= len(text):
                    break
                start += chunk_size - overlap
                index += 1
            self.workspace.write_text(
                "input/problem_context.md",
                "# 长题面分块摘要\n\n"
                "以下摘要仅用于控制上下文；原文保存在 problem.md，冲突时以原文为准。\n\n"
                + "\n\n".join(summaries),
            )
            producer = "context_chunk_summarizer"
        self.workspace.register_artifact(
            "input/problem_context.md",
            "problem_context",
            producer,
            parents=["input/problem.md"],
        )

    def checkpoint(self, stage_id: str) -> None:
        configured = set(self.config["checkpoints"].get("stages", []))
        if stage_id not in configured:
            return
        mode = "auto" if self.auto_approve else self.config["checkpoints"]["mode"]
        if mode == "auto":
            decision = "approved"
        else:
            answer = input(
                f"\n检查点 {stage_id} 已完成。输入 y 批准继续，其他内容终止："
            ).strip()
            decision = "approved" if answer.lower() == "y" else "rejected"
        self.workspace.record_checkpoint(stage_id, decision, mode)
        if decision != "approved":
            raise RuntimeError(f"human checkpoint rejected at {stage_id}")

    def _record(
        self,
        stage: str,
        status: str,
        started_at: str,
        elapsed: float,
        outputs: list[str],
        model: str | None = None,
        notes: str = "",
    ) -> None:
        self.workspace.record_stage(
            StageRecord(
                stage=stage,
                status=status,
                started_at=started_at,
                ended_at=now_iso(),
                duration_seconds=round(elapsed, 3),
                outputs=outputs,
                model=model,
                notes=notes,
            ).to_dict()
        )

    def run(self, problem: Path) -> Path:
        self.initialize(problem)
        return self._execute_pipeline()

    def resume(self) -> Path:
        if not self.workspace.path("input/problem.md").exists():
            raise RuntimeError("cannot resume: input/problem.md is missing")
        return self._execute_pipeline()

    def _execute_pipeline(self) -> Path:
        for stage in self.config["pipeline"]:
            if not stage.get("enabled", True):
                continue
            if stage.get("ablation_flag") and not self.config["ablation"].get(
                stage["ablation_flag"], True
            ):
                outputs: list[str] = []
                if stage.get("output"):
                    placeholder = self.workspace.write_text(
                        stage["output"],
                        f"# 已消融：{stage['id']}\n\n"
                        f"配置关闭 `{stage['ablation_flag']}`，本工件为空占位，"
                        "供下游显式识别该模块缺失。",
                    )
                    self.workspace.register_artifact(
                        stage["output"],
                        "ablation_placeholder",
                        "orchestrator",
                        parents=stage.get("inputs", []),
                    )
                    outputs.append(
                        placeholder.relative_to(self.workspace.root).as_posix()
                    )
                self._record(
                    stage["id"],
                    "skipped",
                    now_iso(),
                    0.0,
                    outputs,
                    notes=f"ablation_flag={stage['ablation_flag']}",
                )
                continue
            started_at = now_iso()
            started = time.perf_counter()
            try:
                if stage["type"] == "llm":
                    output, model = run_llm_stage(
                        self.project_root,
                        self.workspace,
                        self.runtime,
                        stage,
                        self.config["context"],
                    )
                    outputs = [output.relative_to(self.workspace.root).as_posix()]
                    self._record(
                        stage["id"],
                        "completed",
                        started_at,
                        time.perf_counter() - started,
                        outputs,
                        model=model,
                    )
                elif stage["type"] == "solver":
                    produced, model, solver_seconds = run_solver_stage(
                        self.project_root,
                        self.workspace,
                        self.runtime,
                        stage,
                        self.config["context"],
                        self.config["solver"],
                    )
                    outputs = [
                        path.relative_to(self.workspace.root).as_posix()
                        for path in produced
                    ]
                    self._record(
                        stage["id"],
                        "completed",
                        started_at,
                        time.perf_counter() - started,
                        outputs,
                        model=model,
                        notes=f"solver_execution_seconds={solver_seconds:.3f}",
                    )
                elif stage["type"] == "web_research":
                    output, model = run_web_research_stage(
                        self.project_root,
                        self.workspace,
                        self.runtime,
                        stage,
                        self.config["context"],
                        self.config["research"],
                    )
                    self._record(
                        stage["id"],
                        "completed",
                        started_at,
                        time.perf_counter() - started,
                        [
                            output.relative_to(self.workspace.root).as_posix(),
                            "artifacts/02_research_evidence.json",
                        ],
                        model=model,
                    )
                elif stage["type"] == "paper_finalize":
                    output, changes = finalize_paper(
                        self.workspace, self.config["paper_finalize"]
                    )
                    self._record(
                        stage["id"],
                        "completed",
                        started_at,
                        time.perf_counter() - started,
                        [output, "artifacts/07_paper_finalize_report.json"],
                        notes=f"changes={len(changes)}",
                    )
                else:
                    raise ValueError(f"unknown stage type: {stage['type']}")
                self.checkpoint(stage["id"])
            except Exception as exc:
                self._record(
                    stage["id"],
                    "failed",
                    started_at,
                    time.perf_counter() - started,
                    [],
                    notes=str(exc),
                )
                raise

        render_started = time.perf_counter()
        render_at = now_iso()
        try:
            pdf = render_paper(self.workspace, self.config["render"])
            preview = render_pdf_preview(self.workspace)
            self._record(
                "render",
                "completed",
                render_at,
                time.perf_counter() - render_started,
                [
                    pdf.relative_to(self.workspace.root).as_posix(),
                    preview.relative_to(self.workspace.root).as_posix(),
                ],
            )
        except Exception as exc:
            self._record(
                "render",
                "failed",
                render_at,
                time.perf_counter() - render_started,
                [],
                notes=str(exc),
            )
            raise
        evaluation = evaluate_run(self.workspace)
        self.workspace.write_json("evaluation/evaluation.json", evaluation)
        self.workspace.register_artifact(
            "evaluation/evaluation.json",
            "evaluation",
            "mechanical_evaluator",
        )
        self.workspace.update_manifest(completed_at=now_iso())
        return self.workspace.root
