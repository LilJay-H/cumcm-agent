from __future__ import annotations

import json
import unittest
from pathlib import Path

from cumcm_agent.core.config import load_config
from cumcm_agent.core.workspace import RunWorkspace
from cumcm_agent.stages.solver import extract_python
from cumcm_agent.runtime.claude import ClaudeRuntime
from cumcm_agent.tools.web_sources import parse_query_plan


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project = Path(__file__).resolve().parents[1]

    def test_config_merge(self) -> None:
        config = load_config(self.project, self.project / "config" / "f_test.json")
        self.assertEqual(config["runtime"]["model"], "claude-opus-4-6")
        self.assertEqual(config["checkpoints"]["mode"], "auto")
        self.assertGreaterEqual(len(config["pipeline"]), 8)

    def test_workspace_rejects_escape(self) -> None:
        workspace = RunWorkspace(self.project, "unit-test")
        with self.assertRaises(ValueError):
            workspace.path("../../outside.txt")

    def test_artifact_manifest(self) -> None:
        workspace = RunWorkspace(self.project, "unit-test")
        workspace.write_text("artifacts/example.md", "hello")
        record = workspace.register_artifact(
            "artifacts/example.md", "test", "unit"
        )
        self.assertEqual(len(record["sha256"]), 64)
        manifest = json.loads(
            workspace.manifest_path.read_text(encoding="utf-8")
        )
        self.assertTrue(
            any(item["path"] == "artifacts/example.md" for item in manifest["artifacts"])
        )

    def test_python_fence_extraction(self) -> None:
        text = "说明\n```python\nprint('ok')\n```\n"
        self.assertEqual(extract_python(text), "print('ok')\n")

    def test_inert_tool_xml_normalization(self) -> None:
        text = (
            "preamble<tool_use><tool_name>write_file</tool_name>"
            "<content># 标题\n正文</content></tool_use>tail"
        )
        self.assertEqual(ClaudeRuntime._normalize_text(text), "# 标题\n正文")
        tool_trace = (
            "准备读取\n<tool_use>{}</tool_use>\n"
            "<tool_result>{}</tool_result>\n# 最终台账"
        )
        self.assertEqual(
            ClaudeRuntime._normalize_text(tool_trace),
            "准备读取\n\n\n# 最终台账",
        )

    def test_research_query_plan_parsing(self) -> None:
        text = '```json\n{"queries":["site:stats.gov.cn 人口","模型 参数"]}\n```'
        self.assertEqual(
            parse_query_plan(text, 1), ["site:stats.gov.cn 人口"]
        )


if __name__ == "__main__":
    unittest.main()
