from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.workspace import RunWorkspace
from ..runtime.claude import ClaudeRuntime
from ..tools.web_sources import (
    fetch_visible_text,
    parse_query_plan,
    search_duckduckgo_html,
)
from .llm_stage import build_context


def run_web_research_stage(
    project_root: Path,
    workspace: RunWorkspace,
    runtime: ClaudeRuntime,
    stage: dict[str, Any],
    context_config: dict[str, Any],
    research_config: dict[str, Any],
) -> tuple[Path, str]:
    common = (project_root / "prompts" / "00_common.md").read_text(
        encoding="utf-8"
    )
    planning = (project_root / "prompts" / stage["query_prompt"]).read_text(
        encoding="utf-8"
    )
    context = build_context(
        workspace,
        stage["inputs"],
        int(context_config["max_total_chars"]),
        int(context_config["max_artifact_chars"]),
    )
    plan_response = runtime.invoke(
        f"{stage['id']}_query_planning",
        common + "\n\n" + planning + "\n\n# 输入\n\n" + context,
        allowed_tools=[],
    )
    queries = parse_query_plan(
        plan_response.text, int(research_config["max_queries"])
    )

    records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for query in queries:
        try:
            results = search_duckduckgo_html(
                query,
                max_results=int(research_config["results_per_query"]),
                timeout_seconds=int(research_config["timeout_seconds"]),
            )
        except Exception as exc:
            records.append({"query": query, "search_error": str(exc)})
            continue
        for result in results:
            url = result["url"]
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            record: dict[str, Any] = {"query": query, **result}
            try:
                record["page_text"] = fetch_visible_text(
                    url,
                    timeout_seconds=int(research_config["timeout_seconds"]),
                    max_chars=int(research_config["max_page_chars"]),
                )
                record["fetch_status"] = "fetched"
            except Exception as exc:
                record["fetch_status"] = "failed"
                record["fetch_error"] = str(exc)
            records.append(record)
            if len(seen_urls) >= int(research_config["max_pages"]):
                break
        if len(seen_urls) >= int(research_config["max_pages"]):
            break

    evidence_path = workspace.write_json(
        "artifacts/02_research_evidence.json",
        {"queries": queries, "records": records},
    )
    workspace.register_artifact(
        "artifacts/02_research_evidence.json",
        "web_evidence",
        "local_web_source_tool",
        parents=stage["inputs"],
    )

    synthesis = (
        project_root / "prompts" / stage["synthesis_prompt"]
    ).read_text(encoding="utf-8")
    synthesis_context = build_context(
        workspace,
        [*stage["inputs"], "artifacts/02_research_evidence.json"],
        int(context_config["max_total_chars"]),
        int(context_config["max_artifact_chars"]),
    )
    synthesis_response = runtime.invoke(
        f"{stage['id']}_synthesis",
        common + "\n\n" + synthesis + "\n\n# 输入\n\n" + synthesis_context,
        allowed_tools=[],
    )
    output = workspace.write_text(stage["output"], synthesis_response.text)
    workspace.register_artifact(
        stage["output"],
        stage.get("kind", "source_ledger"),
        stage["id"],
        parents=[
            *stage["inputs"],
            evidence_path.relative_to(workspace.root).as_posix(),
        ],
    )
    return output, synthesis_response.model
