from __future__ import annotations

import re
from typing import Any

from ..core.workspace import RunWorkspace


def finalize_paper(
    workspace: RunWorkspace,
    config: dict[str, Any],
) -> tuple[str, list[str]]:
    source_relative = config.get("source", "paper/draft_v1.md")
    output_relative = config.get("output", "paper/draft.md")
    text = workspace.path(source_relative).read_text(encoding="utf-8")
    changes: list[str] = []

    first_heading = text.find("# ")
    if first_heading > 0:
        text = text[first_heading:]
        changes.append("removed_non_markdown_preamble")
    trailer = "\n---\n\nPaper draft complete."
    if trailer in text:
        text = text.split(trailer, 1)[0].rstrip() + "\n"
        changes.append("removed_generation_trailer")

    for item in config.get("replacements", []):
        old = item["find"]
        new = item["replace"]
        if old in text:
            text = text.replace(old, new, int(item.get("count", -1)))
            changes.append(item.get("name", old[:40]))

    for item in config.get("figure_insertions", []):
        image = item["path"]
        markdown = (
            f"\n\n![{item['caption']}]({image})\n\n"
            f"*{item['label']}：{item['caption']}*\n\n"
        )
        if f"]({image})" in text:
            continue
        marker = item["before"]
        if marker in text:
            text = text.replace(marker, markdown + marker, 1)
            changes.append(f"inserted_{image}")

    if config.get("auto_insert_unreferenced_figures", False):
        unreferenced: list[str] = []
        figures_dir = workspace.path("figures")
        if figures_dir.exists():
            for figure in sorted(figures_dir.glob("*.png")):
                relative = figure.relative_to(workspace.root).as_posix()
                if f"]({relative})" not in text:
                    unreferenced.append(relative)
        if unreferenced:
            block = "\n\n### 补充图表\n\n" + "\n\n".join(
                f"![]({path})\n\n*补充图：{path.rsplit('/', 1)[-1]}*"
                for path in unreferenced
            )
            appendix = text.find("\n## 附录")
            if appendix == -1:
                text = text.rstrip() + block + "\n"
            else:
                text = text[:appendix] + block + "\n" + text[appendix:]
            changes.append(f"inserted_{len(unreferenced)}_unreferenced_figures")

    # Pandoc treats non-empty image alt text as a figure caption. When the
    # generated paper already contains an explicit italic caption, clear the
    # alt text to avoid rendering two captions.
    text, caption_fixes = re.subn(
        r"!\[[^\]]+\]\(([^)]+)\)(\s+\*图\s*\d+：[^\n]+\*)",
        r"![](\1)\2",
        text,
    )
    if caption_fixes:
        changes.append(f"removed_{caption_fixes}_duplicate_figure_captions")

    workspace.write_text(output_relative, text)
    workspace.register_artifact(
        output_relative,
        "paper_final",
        "paper_finalizer",
        parents=[source_relative, "artifacts/06_paper_audit.md"],
    )
    workspace.write_json(
        "artifacts/07_paper_finalize_report.json",
        {
            "source": source_relative,
            "output": output_relative,
            "changes": changes,
        },
    )
    workspace.register_artifact(
        "artifacts/07_paper_finalize_report.json",
        "paper_revision_record",
        "paper_finalizer",
        parents=[source_relative, "artifacts/06_paper_audit.md"],
    )
    return output_relative, changes
