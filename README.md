# CUMCM Agent v0

一个以 Claude Code 为推理运行时、面向全国大学生数学建模竞赛（CUMCM）的端到端建模代理。v0 目标是用最小但清晰的架构跑通：

> 读题 → 问题分析 → 受控调研 → 候选方案竞争 → 独立审核 → 代码求解 → 图表 → 结果解释 → 中文论文 → 论文审核 → 确定性终稿整理

## 设计重点

- **代码、配置、提示词分离**：编排逻辑在 `cumcm_agent/`，阶段配置在 `config/`，提示词在 `prompts/`。
- **受控写入**：每次运行只能写入 `runs/<run-id>/`。
- **证据工件**：`manifest.json` 记录工件哈希、生产阶段和依赖。
- **Human-in-the-loop**：问题分析、方案选择和论文审核后有检查点；测试可用 `--auto-approve`。
- **可复现求解**：生成脚本固定随机种子，输出统一 `results.json` 和 PNG。
- **可评测、可消融**：调研、方案审核、论文审核均可单独关闭。
- **完整 AI 留痕**：`logs/llm_calls.jsonl` 保存实际模型、提示词、回复、耗时、用量和费用。
- **联网降级边界清晰**：Claude WebSearch 不可用时，由本地检索/抓取工具生成证据 JSON，并明确区分正文、搜索结果和失败来源。

## 环境要求

- Python 3.11+
- Claude Code CLI，并已配置可调用的模型
- NumPy、Pandas、Matplotlib
- Pandoc、XeLaTeX（用于中文 PDF）
- Poppler 的 `pdftoppm`（用于首面预览）

本机校准环境：

- Claude Code `2.1.220`
- 请求与实际返回模型：`claude-opus-4-6`
- Python `3.14.2`

## 目录导航

```text
cumcm-agent/
├─ cumcm_agent/
│  ├─ core/          # 配置、工件清单、路径边界
│  ├─ pipeline/      # 编排与人工检查点
│  ├─ runtime/       # Claude Code 适配器与调用留痕
│  ├─ stages/        # LLM 阶段、代码生成与执行
│  ├─ tools/         # 来源检索、终稿整理、论文渲染
│  └─ evaluation/    # 机械质量检查
├─ config/           # 默认配置与 F 题测试覆盖
├─ prompts/          # 分阶段提示词
├─ docs/             # 调研、架构图和决策说明
├─ examples/         # 可公开复核的精选运行成果
├─ scripts/          # 一键运行脚本
├─ tests/            # 最小单元测试
└─ runs/             # 本地运行产物（不纳入 Git）
```

## 运行 F 题测试

在本目录执行，并将 `$problemPath` 替换为本机题面文件的实际路径：

```powershell
$problemPath = "path\to\2026_ICM_Problem_F.md"

python -m cumcm_agent run `
  --problem $problemPath `
  --run-id "2026-icm-f-v0" `
  --config "config\f_test.json" `
  --auto-approve
```

`run-id` 必须对应一个尚不存在的目录；上面的编号是本次已完成基线。重新测试时请换新编号，或使用下方脚本自动生成带时间戳的编号。

也可让脚本自动生成带时间戳的运行编号：

```powershell
.\scripts\run_f_test.ps1 -ProblemPath $problemPath
```

不加 `--auto-approve` 时，在 `analysis`、`strategy` 和 `paper_audit` 后要求人工输入 `y`。论文审核检查点可用于人工修改 `paper/draft_v1.md`，再继续本地终稿整理。

## 主要运行产物

```text
runs/<run-id>/
├─ manifest.json
├─ input/                 # 原题与长上下文摘要
├─ artifacts/             # 分析、调研、方案、审核、结果解释
├─ generated/solver.py
├─ results/results.json
├─ figures/*.png
├─ paper/draft.md
├─ paper/draft.pdf
├─ rendered/paper-preview.png
├─ logs/llm_calls.jsonl
└─ evaluation/evaluation.json
```

若长代码生成超时，可从现有方案工件局部恢复：

```powershell
python -m cumcm_agent resume `
  --run-id "2026-icm-f-v0" `
  --config "config\f_recovery.json" `
  --auto-approve
```

本次 F 题基线曾发生整篇论文重写超时；现默认流程已改为审核后的确定性终稿整理。对该基线重新应用审核修订可执行：

```powershell
python -m cumcm_agent resume `
  --run-id "2026-icm-f-v0" `
  --config "config\f_finalize.json" `
  --auto-approve
```

## 消融

复制 `config/f_test.json`，按需关闭：

```json
{
  "ablation": {
    "web_research": false,
    "independent_review": false,
    "paper_audit": false
  }
}
```

被关闭的模块会生成显式占位工件，避免下游误以为该证据存在。可比较最终机械评测、论文内容、运行时间和 API 成本。

## 已知边界

- v0 是线性流水线，不是完整 Problem/Evidence DAG。
- 代码执行器检查路径与产物契约，但还没有操作系统级沙箱。
- 本地来源工具依赖公共搜索页和目标站点的可访问性；403、PDF 或反爬限制会逐条记为失败，不能保证取得所需数据。
- 机械评测只能检查完整性和部分一致性，不能替代队员对模型合理性与结论的最终判断。

详细架构见 [docs/architecture_decisions.md](docs/architecture_decisions.md)。

## 本次交付导航

- 框架图源文件：`docs/architecture.mmd`
- 框架图图片：`docs/architecture.png`
- F 题测试报告：`docs/test_report.md`
- F 题精选示例：`examples/2026-icm-f-v0/`
- F 题论文：`examples/2026-icm-f-v0/paper.pdf`
- F 题求解程序：`examples/2026-icm-f-v0/solver.py`

`runs/` 保存完整模型调用、费用和中间工件，仅在本地保留；公开仓库只收录经过筛选的示例成果。
