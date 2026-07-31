# 任务：生成可复现求解程序

根据正式方案和独立审核，输出一个完整 Python 程序。回复只能包含一个 `python` 代码块。

程序必须：

0. 控制在 320 行以内；优先直接、可审计的数组运算，禁止大段硬编码模拟数据或无关封装。
1. 只在当前运行目录的 `results/` 和 `figures/` 写文件，不读取或修改目录之外的内容。
2. 仅使用 Python 标准库、NumPy、Pandas、Matplotlib；设置 `matplotlib.use("Agg")`。
3. 固定随机种子。若无原始微观数据，只能使用来源台账中的聚合量和明确标记的情景参数，不能伪装成观测数据。
4. 实现主模型、基准/乐观/悲观三种情景，以及至少一个二维敏感性扫描。
5. 对每个职业输出 5 年与 10 年前景指标、培养规模建议和课程学分配置。
6. 加入非就业目标并比较加入前后的方案变化。
7. 运行机械自检：权重和为 1、学分预算守恒、结果范围有效、关键排序可解释；失败时抛出异常。
8. 生成 UTF-8 的 `results/results.json`，至少包含：
   `metadata`、`parameters`、`career_outlook`、`capacity_decisions`、
   `curriculum_allocations`、`scenario_analysis`、`sensitivity_analysis`、
   `non_employment_objectives`、`validation_checks`、`limitations`。
9. 生成至少 3 张 300 dpi PNG 图：职业前景情景比较、课程学分配置、敏感性/稳健性。图中文字使用英文，避免字体缺失。
10. 在标准输出中打印简洁的运行摘要和所有验证检查结果。

模型的目标不是制造复杂度，而是让每个结论能被计算结果支持。
