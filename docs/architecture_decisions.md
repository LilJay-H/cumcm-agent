# 架构决策与代码映射

| 架构模块 | 代码/配置 | 决策理由 |
|---|---|---|
| Intake 与路径边界 | `core/workspace.py` | 所有写入限定在单次 run；工件记录哈希、来源和父依赖 |
| 长上下文管理 | `pipeline/orchestrator.py::_prepare_problem_context`、`stages/llm_stage.py` | 长题面分块摘要，原文保留；阶段输入有字符预算 |
| 编排与检查点 | `pipeline/orchestrator.py`、`config/default.json` | 流程可复现，人工裁决和自动测试共用同一接口 |
| Claude Code 运行时 | `runtime/claude.py` | 调用、模型、用量、费用、提示词与回复统一留痕 |
| 本地来源工具 | `tools/web_sources.py`、`stages/web_research.py` | 适配后端不支持 WebSearch 时，检索、抓取与证据综合仍保持显式边界；正文、摘要与失败分级记录 |
| 提示词层 | `prompts/*.md` | 角色与产物契约独立于编排代码，便于替换和消融 |
| 方案审核 | `prompts/04_strategy_review.md` | 生成者与审核目标分离，优先找会改变结论的缺陷 |
| 代码执行 | `stages/solver.py` | 只执行单一生成脚本，固定运行目录并验证结果契约 |
| 图表与论文 | `prompts/07_paper.md`、`tools/paper_finalizer.py`、`tools/paper_renderer.py` | 论文只消费已有证据；审计后使用确定性小修订，避免整篇重写超时或内容漂移 |
| 机械评测 | `evaluation/rubric.py` | 竞赛完整性和系统运行质量可以独立测量 |
| 消融接口 | `config/default.json::ablation` | 调研、方案审核、论文审核可独立关闭 |

## v0 边界

v0 是今晚可运行的线性闭环，不是完整自治科研系统。它没有并行代理、因果级证据撤销、自动代码修复循环和跨题 benchmark；但所有阶段都有稳定输入输出路径，因此后续可以把线性列表替换为 DAG，而不改提示词和工具契约。
