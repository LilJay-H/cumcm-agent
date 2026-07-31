# 任务：超时后的紧凑求解器恢复

上一次长代码生成已超时。请生成一个 **不超过 280 行** 的完整 Python 程序；回复只能包含一个 `python` 代码块，不作解释。

保留数学含义但主动压缩工程量：

1. 职业任务向量固定为情景输入：
   - Software Developer: `[0.50, 0.15, 0.05, 0.30]`
   - Electrician: `[0.15, 0.20, 0.60, 0.05]`
   - Graphic Designer: `[0.20, 0.15, 0.05, 0.60]`
   四维依次为认知、社交、身体、创意；明确标记为待数据校准的情景参数。
2. 对 conservative/base/aggressive 三情景，用 Logistic 函数生成四类 AI 能力。
3. 替代率和增强率按职业分别计算；就业指数只使用替代/增强的年度增量，另设无 AI 反事实，避免水平重复复利。
4. 输出的是以 2026=100 的“就业需求指数”，不得伪装成就业人数预测。
5. 招生建议由 10 年指数映射：`>105` 扩招、`95–105` 稳定、`<95` 缩招。
6. 每个项目总学分统一为 120。用固定候选比例或小型网格搜索，在六类课程间分配学分：专业核心、AI 工具、AI 原理、伦理人文、实践实习、跨领域。三职业必须使用不同贡献矩阵。
7. 比较仅就业目标与加入公平性、韧性后的配置。
8. 做二维敏感性扫描：替代弹性乘数 `[0.5,1.5]` 与增强弹性乘数 `[0.5,1.5]`。
9. 固定随机种子；机械检查所有指数非负、比例范围有效、每组学分和为 120。
10. 仅写当前目录下：
    - `results/results.json`
    - `figures/career_scenarios.png`
    - `figures/curriculum_allocations.png`
    - `figures/sensitivity_heatmap.png`
11. `results.json` 必须含：
    `metadata`、`parameters`、`career_outlook`、`capacity_decisions`、
    `curriculum_allocations`、`scenario_analysis`、`sensitivity_analysis`、
    `non_employment_objectives`、`validation_checks`、`limitations`。
12. 只使用标准库、NumPy、Matplotlib；`matplotlib.use("Agg")`；图片英文标签、300 dpi。

对审核指出但因数据缺失无法修复的问题，写进 `limitations`，不要补造 BLS、O*NET 或机构数值。

