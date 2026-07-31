from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from ..core.workspace import RunWorkspace


def render_paper(
    workspace: RunWorkspace,
    config: dict[str, Any],
) -> Path:
    source = workspace.path("paper/draft.md")
    output = workspace.path("paper/draft.pdf")
    command = [
        config.get("pandoc_command", "pandoc"),
        str(source),
        "-o",
        str(output),
        "--pdf-engine",
        config.get("pdf_engine", "xelatex"),
        "--resource-path",
        str(workspace.root),
        "-V",
        f"CJKmainfont={config.get('cjk_font', 'SimSun')}",
        "-V",
        "geometry:margin=2.5cm",
        "-V",
        "fontsize=11pt",
    ]
    completed = subprocess.run(
        command,
        cwd=workspace.root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=int(config.get("timeout_seconds", 180)),
        check=False,
    )
    workspace.write_text("logs/pandoc_stdout.txt", completed.stdout)
    workspace.write_text("logs/pandoc_stderr.txt", completed.stderr)
    if completed.returncode != 0 or not output.exists():
        raise RuntimeError("paper rendering failed: " + completed.stderr[-3000:])
    workspace.register_artifact(
        "paper/draft.pdf",
        "paper_pdf",
        "paper_renderer",
        parents=["paper/draft.md"],
    )
    return output


def render_pdf_preview(workspace: RunWorkspace) -> Path:
    pdf = workspace.path("paper/draft.pdf")
    target_prefix = workspace.path("rendered/paper-preview")
    command = [
        "pdftoppm",
        "-png",
        "-f",
        "1",
        "-singlefile",
        "-r",
        "120",
        str(pdf),
        str(target_prefix),
    ]
    completed = subprocess.run(
        command,
        cwd=workspace.root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
        check=False,
    )
    preview = workspace.path("rendered/paper-preview.png")
    if completed.returncode != 0 or not preview.exists():
        raise RuntimeError("PDF preview failed: " + completed.stderr[-2000:])
    workspace.register_artifact(
        "rendered/paper-preview.png",
        "render_preview",
        "paper_renderer",
        parents=["paper/draft.pdf"],
    )
    return preview
