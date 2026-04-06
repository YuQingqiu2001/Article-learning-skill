---
name: paper-writing-system
version: 0.2
description: 手动触发的科研论文学习与SCI写作能力沉淀skill。用于扫描近N天PDF、识别Article/Review、抽象写作模式、提取知识并沉淀到memory与skills文件，强调质量控制与保守抽取。
---

# paper-writing-system

## 1) 使用场景
- 当用户希望对新增SCI文献执行**标准化学习流程**时使用。
- 当目标是“提炼可复用写作能力与知识结构”，而非仅提取PDF全文时使用。
- 当前仅支持**手动调用**，不包含定时任务。

## 2) 输入
- 默认输入目录：`D:\sci文献数据`（可由 CLI `--input-dir` 覆盖）。
- 文献格式：PDF。
- 时间窗口：默认最近 `1` 天（可由 CLI `--days` 覆盖）。

## 3) 输出
- 日志与日记忆：`runtime/memory/YYYY-MM-DD.md`
- 能力沉淀文件：
  - `runtime/skills/abstract_patterns.md`
  - `runtime/skills/results_logic_patterns.md`
  - `runtime/skills/discussion_patterns.md`
  - `runtime/skills/review_structures.md`
  - `runtime/skills/scientific_phrases.md`
- 训练样本：`runtime/skills/generated_examples/YYYY-MM-DD.md`
- 学习演化状态：`runtime/skills/learning_state.json`
- 学习复盘日志：`runtime/skills/evolution_log.md`
- 状态索引：`runtime/processed_files.json`
- 人工澄清问题：`runtime/memory/human_questions_YYYY-MM-DD.md`

## 4) 核心流程（必须按序执行）
1. 扫描目录并筛选最近N天新增或修改PDF。
2. 与 `processed_files.json` 去重（除非 `--force`）。
3. 无新文件时：写入当日memory“无新增文献”，终止。
4. 逐篇提取基础文本与结构信息（保守抽取）。
   - 读取后端优先 `PyMuPDF`（多栏复杂版式），失败时回退 `pypdf`。
5. 识别文献类型（Article/Review/Uncertain）。
6. 按类型协议解析。
7. 统一执行写作模式抽象、知识提取、质量标注。
8. 生成当日总结与训练样本。
9. 非 dry-run 下更新核心 skills 文件与 processed 索引。
10. 基于重复暴露做“类人学习演化”：pattern 从 observing -> candidate -> high_conf。
11. 每篇学习完成后立即执行AI复核；若发现偏差，生成对人的提问并暂停该篇沉淀。

## 5) Article 解析协议
### 5.1 必提结构
- Title / Abstract / Introduction / Methods / Results / Discussion。

### 5.2 Abstract 深度解析
- 对句子做功能标签：Background / Objective / Methods / Results / Conclusion。
- 提取去实体化模板句（去除疾病、基因、分子、队列、模型名称）。

### 5.3 Results 逻辑建模
- 将 Results 拆分 finding units。
- 每个 unit 尽量抽取：
  - `question`
  - `method`
  - `result`
  - `reasoning`
  - `transition`
- `reasoning` 必须尽量体现“证据信号 -> 推断语句”。
- 明确 Result1 → Result2 → Result3 推进链。

### 5.4 Discussion 推理模式
- 建模链路：`result → mechanism explanation → literature support → inference`。
- 分类标签：
  - 因果解释
  - 对比研究
  - 局限性
  - 生物学意义
  - 临床意义

## 6) Review 解析协议
### 6.1 必提结构
- Abstract / Introduction / Main sections / Subsections / Conclusion。

### 6.2 综述组织方式
- mechanism-based
- disease-based
- method-based
- timeline-based

### 6.3 知识整合建模
- 每段尽量识别：`claim / evidence / synthesis`。
- 构建 `claim → evidence → synthesis` 逻辑。

### 6.4 高级写法提取
- 领域总结方式
- knowledge gap
- future directions
- clinical implications
- 抽象模板：Introduction、小节组织、Conclusion/perspective

## 7) 统一抽象规则
- 跨类型统一输出：
  - Abstract 模板
  - Results 推进模板
  - Review 整合模板
  - 通用句式模板
- 句式按功能分桶：
  - 描述结果 / 表达因果 / 引用文献 / 提出假设 / 强调局限性 / 指出研究意义
- 去实体化规则：尽量替换具体实体为通用占位语（如“关键生物标志物”“目标人群”）。

## 8) 知识提取规则
- 提取对象：新机制、新通路、基因/分子、研究方法、分析框架、研究趋势。
- 每条知识必须含：
  - `confidence`（high/medium/low）
  - `stability`（stable/contested/cautious）
  - `uncertain`（true/false）
- 未明确证据支撑时，必须标记 `uncertain: true`。

## 9) 质量控制规则
- 避免重复写入（去重键：pattern文本 + 来源线索）。
- 低质量PDF（文本过短、结构缺失严重）打 `quality_flag=low`，仅写入memory，不写核心skills。
- 学习优先级：Review > Article，high quality > medium > low。
- Review 学习权重高于普通 Article。
- 模式写入执行“语义去重”：同一模式即便来源不同，也不重复膨胀skills文件。
- 严禁把不确定内容写成确定规律。
- 严禁把解析失败内容写入核心 skills 文件。
- 原则：先保守抽取，再逐步增强；沉淀优先质量，不追求一次提取过多。

## 10) 失败处理策略
- PDF读取失败：记录到memory，状态 `status=failed_extract`。
- 类型不确定：标记 `paper_type=uncertain`，仅输出低置信摘要，不进入高置信模式库。
- 无新增文件：写“无新增文献”，流程正常结束。

## 11) 手动调用建议
```bash
python scripts/learn_papers.py --input-dir "D:\\sci文献数据" --days 1 --verbose
```
- 首次建议 `--dry-run` 先检查输出。
- 需要重跑历史文件时使用 `--force`。

## 12) 目录约定
- `scripts/`: 可执行流程与解析模块
- `prompts/`: 规则模板（可供后续LLM接入）
- `schemas/`: JSON schema 与字段约束
- `examples/`: 输出示例
- `runtime/`: 运行时产物（memory / skills / generated_examples / processed_files）

## 13) 注意事项
- 当前为 v0.2：规则引擎 + 占位抽取，保证可运行与可维护。
- 针对Nature等复杂排版，默认采用 `PyMuPDF` block提取增强鲁棒性。
- 后续可替换文本提取器（如更强PDF parser）与LLM语义解析器（见脚本TODO）。

## 14) 类人学习演化策略
- 核心思想：一次阅读只产生“候选认知”，多次高质量重复观察后才升格为高置信规律。
- 证据累积：
  - 每条模式记录 `count`（出现次数）与 `weighted_score`（按文献质量与类型加权）。
  - Review 与 high-quality article 权重更高。
- 状态机：
  - observing：首次或证据薄弱
  - candidate：重复出现（>=2）
  - high_conf：多次且加权分达阈值（默认 count>=3 且 score>=4.0）
- 每日复盘：输出 `evolution_log.md`，包含“今天学到什么、哪些被强化、哪些仍不确定、明日重点”。


## 15) AI复核规则（单篇学习后立即执行）
- 对每篇文献执行 second-pass 复核（当前为规则模拟，后续可接LLM）。
- 若复核分数过低或存在结构/质量风险，标记 `needs_human_guidance`。
- 复核采用分级风险门控：critical问题必拦截；非critical问题按分数与问题数量联合判断，避免过度拦截。
- 被标记文献不得写入核心skills，只能进入 memory 与 human_questions 文件。
- 必须向人提出最少3个澄清问题（学习重点、文献类型、哪些结论需uncertain）。
- 支持下一轮通过 `--feedback-file` 注入人工反馈，修正学习方向并决定是否允许沉淀。


## 16) ClawHub / Openclaw 集成约定
- 本 skill 设计为可直接安装到 ClawHub / Openclaw。
- UI 元数据文件：`agents/openai.yaml`。
- 推荐入口：`scripts/openclaw_entry.py`（优先读取 `CLAWHUB_*`，兼容 `OPENCLAW_*` 环境变量后调用 `learn_papers.py`）。
- Windows 安装脚本：`install_clawhub_windows.ps1` / `install_clawhub_windows.bat`（底层调用 `scripts/install_openclaw.py`）。
- 安装脚本支持 `--with-venv` 自动配置安装目录依赖环境。
- 入口脚本必须保持“手动触发”语义，不得引入自动定时调度。
