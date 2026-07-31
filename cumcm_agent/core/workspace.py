from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class RunWorkspace:
    DIRECTORIES = (
        "input",
        "artifacts",
        "generated",
        "results",
        "figures",
        "paper",
        "logs",
        "evaluation",
        "rendered",
    )

    def __init__(self, project_root: Path, run_id: str):
        self.project_root = project_root.resolve()
        runs_root = (self.project_root / "runs").resolve()
        self.root = (runs_root / run_id).resolve()
        if runs_root not in self.root.parents:
            raise ValueError("run directory must stay inside project/runs")
        self.root.mkdir(parents=True, exist_ok=True)
        for name in self.DIRECTORIES:
            (self.root / name).mkdir(exist_ok=True)
        self.manifest_path = self.root / "manifest.json"
        if not self.manifest_path.exists():
            self._write_json(
                self.manifest_path,
                {
                    "schema": 1,
                    "run_id": run_id,
                    "created_at": now_iso(),
                    "artifacts": [],
                    "stages": [],
                    "checkpoints": [],
                },
            )

    def path(self, relative: str | Path) -> Path:
        target = (self.root / relative).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError(f"path escaped run directory: {relative}")
        return target

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def write_text(self, relative: str | Path, text: str) -> Path:
        target = self.path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text.rstrip() + "\n", encoding="utf-8")
        return target

    def write_json(self, relative: str | Path, data: Any) -> Path:
        target = self.path(relative)
        self._write_json(target, data)
        return target

    def read_manifest(self) -> dict[str, Any]:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def update_manifest(self, **updates: Any) -> None:
        manifest = self.read_manifest()
        manifest.update(updates)
        self._write_json(self.manifest_path, manifest)

    def register_artifact(
        self,
        relative: str | Path,
        kind: str,
        producer: str,
        parents: list[str] | None = None,
    ) -> dict[str, Any]:
        path = self.path(relative)
        if not path.exists():
            raise FileNotFoundError(path)
        record = {
            "path": path.relative_to(self.root).as_posix(),
            "kind": kind,
            "producer": producer,
            "parents": parents or [],
            "sha256": sha256_file(path),
            "created_at": now_iso(),
        }
        manifest = self.read_manifest()
        manifest["artifacts"] = [
            item for item in manifest["artifacts"] if item["path"] != record["path"]
        ]
        manifest["artifacts"].append(record)
        self._write_json(self.manifest_path, manifest)
        return record

    def record_stage(self, record: dict[str, Any]) -> None:
        manifest = self.read_manifest()
        manifest["stages"].append(record)
        self._write_json(self.manifest_path, manifest)

    def record_checkpoint(self, stage: str, decision: str, mode: str) -> None:
        manifest = self.read_manifest()
        manifest["checkpoints"].append(
            {
                "stage": stage,
                "decision": decision,
                "mode": mode,
                "at": now_iso(),
            }
        )
        self._write_json(self.manifest_path, manifest)

