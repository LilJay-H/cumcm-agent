from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .core.config import load_config
from .core.workspace import RunWorkspace
from .evaluation.rubric import evaluate_run
from .pipeline.orchestrator import Orchestrator
from .tools.paper_renderer import render_paper, render_pdf_preview


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _safe_run_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", value):
        raise argparse.ArgumentTypeError(
            "run id must use letters, digits, dot, underscore or hyphen"
        )
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CUMCM modeling agent v0")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run the end-to-end pipeline")
    run.add_argument("--problem", type=Path, required=True)
    run.add_argument("--run-id", type=_safe_run_id, required=True)
    run.add_argument("--config", type=Path)
    run.add_argument("--auto-approve", action="store_true")

    resume = sub.add_parser("resume", help="resume an existing run with a config")
    resume.add_argument("--run-id", type=_safe_run_id, required=True)
    resume.add_argument("--config", type=Path, required=True)
    resume.add_argument("--auto-approve", action="store_true")

    evaluate = sub.add_parser("evaluate", help="evaluate an existing run")
    evaluate.add_argument("--run-id", type=_safe_run_id, required=True)

    render = sub.add_parser("render", help="render an existing paper")
    render.add_argument("--run-id", type=_safe_run_id, required=True)
    render.add_argument("--config", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = project_root()
    if args.command == "run":
        run_path = root / "runs" / args.run_id
        if run_path.exists() and any(run_path.iterdir()):
            raise SystemExit(f"run already exists and is not empty: {run_path}")
        config = load_config(root, args.config)
        output = Orchestrator(
            root,
            config,
            args.run_id,
            auto_approve=args.auto_approve,
        ).run(args.problem)
        print(output)
        return 0
    if args.command == "resume":
        run_path = root / "runs" / args.run_id
        if not run_path.exists():
            raise SystemExit(f"run does not exist: {run_path}")
        config = load_config(root, args.config)
        output = Orchestrator(
            root,
            config,
            args.run_id,
            auto_approve=args.auto_approve,
        ).resume()
        print(output)
        return 0
    if args.command == "evaluate":
        workspace = RunWorkspace(root, args.run_id)
        report = evaluate_run(workspace)
        workspace.write_json("evaluation/evaluation.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["pass"] else 1
    if args.command == "render":
        config = load_config(root, args.config)
        workspace = RunWorkspace(root, args.run_id)
        print(render_paper(workspace, config["render"]))
        print(render_pdf_preview(workspace))
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
