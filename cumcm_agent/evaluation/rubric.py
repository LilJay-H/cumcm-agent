from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..core.workspace import RunWorkspace


def _numeric_leaves(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return 1
    if isinstance(value, dict):
        return sum(_numeric_leaves(item) for item in value.values())
    if isinstance(value, list):
        return sum(_numeric_leaves(item) for item in value)
    return 0


def _chinese_ratio(text: str) -> float:
    visible = re.sub(r"\s+", "", text)
    if not visible:
        return 0.0
    chinese = len(re.findall(r"[\u4e00-\u9fff]", visible))
    return chinese / len(visible)


def evaluate_run(workspace: RunWorkspace) -> dict[str, Any]:
    manifest = workspace.read_manifest()
    stage_records = manifest.get("stages", [])
    completed_stages = [
        item["stage"] for item in stage_records if item["status"] == "completed"
    ]
    failed_stages = [
        item["stage"] for item in stage_records if item["status"] == "failed"
    ]
    recovered_failures = set()
    if "solver_recovery" in completed_stages:
        recovered_failures.add("solver")
    if "paper_finalize" in completed_stages:
        recovered_failures.add("paper_final")
    blocking_failed_stages = [
        stage for stage in failed_stages if stage not in recovered_failures
    ]
    results_path = workspace.path("results/results.json")
    results = (
        json.loads(results_path.read_text(encoding="utf-8"))
        if results_path.exists()
        else {}
    )
    solver_run_path = workspace.path("results/solver_run.json")
    solver_run = (
        json.loads(solver_run_path.read_text(encoding="utf-8"))
        if solver_run_path.exists()
        else {}
    )
    paper_path = workspace.path("paper/draft.md")
    paper = (
        paper_path.read_text(encoding="utf-8", errors="replace")
        if paper_path.exists()
        else ""
    )
    required_sections = {
        "摘要": "摘要" in paper,
        "问题重述": "问题重述" in paper,
        "模型假设": "模型假设" in paper,
        "模型建立": any(term in paper for term in ("模型建立", "模型构建")),
        "求解": "求解" in paper,
        "结果分析": "结果分析" in paper,
        "敏感性或稳健性": any(term in paper for term in ("敏感性", "稳健性")),
        "模型评价": "模型评价" in paper,
        "参考文献": "参考文献" in paper,
    }
    figures = sorted(workspace.path("figures").glob("*.png"))
    numeric_count = _numeric_leaves(results)
    citations = len(re.findall(r"https?://", paper))
    score_items = {
        "pipeline_complete": (
            len(blocking_failed_stages) == 0 and len(completed_stages) >= 8
        ),
        "solver_reproducible": solver_run.get("returncode") == 0,
        "numeric_evidence": numeric_count >= 12,
        "figures": len(figures) >= 2,
        "paper_sections": all(required_sections.values()),
        "paper_is_chinese": _chinese_ratio(paper) >= 0.35,
        "no_table_of_contents": "目录" not in paper[:1500],
        "citations_present": citations >= 3,
        "pdf_rendered": workspace.path("paper/draft.pdf").exists(),
    }
    return {
        "schema": 1,
        "run_id": manifest["run_id"],
        "actual_models": sorted(
            {
                item["model"]
                for item in stage_records
                if item.get("model")
            }
        ),
        "stage_count": len(completed_stages),
        "completed_stages": completed_stages,
        "failed_stages": failed_stages,
        "recovered_failures": sorted(recovered_failures),
        "blocking_failed_stages": blocking_failed_stages,
        "solver_returncode": solver_run.get("returncode"),
        "numeric_leaf_count": numeric_count,
        "figure_count": len(figures),
        "paper_characters": len(paper),
        "paper_chinese_ratio": round(_chinese_ratio(paper), 4),
        "paper_url_count": citations,
        "required_sections": required_sections,
        "checks": score_items,
        "passed_checks": sum(score_items.values()),
        "total_checks": len(score_items),
        "pass": all(score_items.values()),
    }
