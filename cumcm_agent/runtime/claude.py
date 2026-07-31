from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from ..core.models import LLMResponse
from ..core.workspace import RunWorkspace, now_iso


class ClaudeRuntime:
    def __init__(
        self,
        config: dict[str, Any],
        workspace: RunWorkspace,
    ):
        self.config = config
        self.workspace = workspace
        self.log_path = workspace.path("logs/llm_calls.jsonl")

    def invoke(
        self,
        stage: str,
        prompt: str,
        allowed_tools: list[str] | None = None,
    ) -> LLMResponse:
        executable_name = self.config.get("command", "claude")
        executable = shutil.which(executable_name) or executable_name
        cli_arguments = [
            "--print",
            "--output-format",
            "json",
            "--model",
            self.config["model"],
            "--no-session-persistence",
            "--disable-slash-commands",
            "--permission-mode",
            "bypassPermissions" if allowed_tools else "dontAsk",
            "--tools",
            ",".join(allowed_tools or []),
        ]
        if os.name == "nt" and Path(executable).suffix.lower() in {
            ".cmd",
            ".bat",
        }:
            command = [
                os.environ.get("COMSPEC", "cmd.exe"),
                "/d",
                "/s",
                "/c",
                executable,
                *cli_arguments,
            ]
        else:
            command = [executable, *cli_arguments]
        if self.config.get("max_budget_usd") is not None:
            command.extend(
                ["--max-budget-usd", str(self.config["max_budget_usd"])]
            )
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                cwd=self.workspace.root,
                env=env,
                timeout=int(self.config.get("timeout_seconds", 900)),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Claude stage {stage} timed out") from exc
        duration = time.perf_counter() - started
        if completed.returncode != 0:
            raise RuntimeError(
                f"Claude stage {stage} failed ({completed.returncode}): "
                f"{completed.stderr[-2000:]}"
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Claude stage {stage} returned invalid JSON: "
                f"{completed.stdout[-2000:]}"
            ) from exc
        if payload.get("is_error"):
            raise RuntimeError(f"Claude stage {stage}: {payload.get('result')}")
        model_usage = payload.get("modelUsage") or {}
        actual_model = next(iter(model_usage), self.config["model"])
        usage = payload.get("usage") or {}
        raw_text = payload.get("result", "")
        normalized_text = self._normalize_text(raw_text)
        record = {
            "timestamp": now_iso(),
            "stage": stage,
            "requested_model": self.config["model"],
            "actual_model": actual_model,
            "duration_seconds": round(duration, 3),
            "cost_usd": payload.get("total_cost_usd"),
            "usage": usage,
            "prompt": prompt,
            "raw_response": raw_text,
            "response": normalized_text,
            "stderr": completed.stderr,
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return LLMResponse(
            text=normalized_text,
            model=actual_model,
            duration_seconds=duration,
            usage=usage,
            cost_usd=payload.get("total_cost_usd"),
            stderr=completed.stderr,
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Recover content when a compatible backend emits inert tool XML."""
        write_blocks = re.findall(
            r"<tool_use>.*?<tool_name>write_file</tool_name>.*?"
            r"<content>(.*?)</content>.*?</tool_use>",
            text,
            flags=re.DOTALL,
        )
        if write_blocks:
            return write_blocks[-1].strip()
        text = re.sub(
            r"<tool_use>.*?</tool_use>",
            "",
            text,
            flags=re.DOTALL,
        )
        text = re.sub(
            r"<tool_result>.*?</tool_result>",
            "",
            text,
            flags=re.DOTALL,
        )
        return text.strip()
