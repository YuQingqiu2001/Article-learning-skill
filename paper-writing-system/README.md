# paper-writing-system (v0.1 skeleton)

一个可安装、可扩展、可手动调用的科研论文学习 skill。目标不是“批量PDF处理”，而是把文献中的**SCI写作结构、推理链和知识模式**沉淀为可复用能力。

> 当前版本：**v0.1 skeleton**（已可手动运行，便于后续扩展）

## 功能说明
- 扫描目录中的 PDF（默认 `D:\sci文献数据`）
- 筛选最近 N 天新增/修改文献
- 去重处理（`runtime/processed_files.json`）
- 基于规则识别文献类型（Article / Review / Uncertain）
- 一篇一篇学习（单篇处理后再进入下一篇）
- 解析结构并抽象写作模式
- 每篇学习后执行 AI 偏差复核；若存在偏差，生成人工问题清单
- 产出 daily memory 与能力沉淀文件
- 生成训练样本（Original Article 风格 + Review 风格）
- 增加“类人学习演化”机制：重复出现模式自动升置信，形成学习状态与次日关注点

## 目录结构
```text
paper-writing-system/
├─ SKILL.md
├─ README.md
├─ requirements.txt
├─ prompts/
│  ├─ article_parse.md
│  ├─ review_parse.md
│  ├─ abstraction_rules.md
│  └─ qc_rules.md
├─ schemas/
│  ├─ processed_file.schema.json
│  └─ paper_analysis.schema.json
├─ scripts/
│  ├─ learn_papers.py
│  ├─ pdf_classifier.py
│  ├─ parser_article.py
│  ├─ parser_review.py
│  ├─ pattern_extractor.py
│  ├─ knowledge_extractor.py
│  ├─ output_writer.py
│  └─ utils.py
├─ examples/
│  ├─ sample_daily_memory.md
│  ├─ sample_generated_examples.md
│  └─ sample_skill_outputs.md
└─ runtime/
   ├─ processed_files.json
   ├─ memory/
   └─ skills/
      ├─ generated_examples/
      ├─ learning_state.json
      ├─ evolution_log.md
      ├─ abstract_patterns.md
      ├─ results_logic_patterns.md
      ├─ discussion_patterns.md
      ├─ review_structures.md
      └─ scientific_phrases.md
```

## 安装方式
```bash
cd paper-writing-system
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
```

## 手动运行方式
```bash
cd paper-writing-system
python scripts/learn_papers.py --input-dir "D:\sci文献数据" --days 1 --verbose
```

推荐首次运行：
```bash
python scripts/learn_papers.py --dry-run --verbose
```

## 参数说明
- `--input-dir`：输入目录，默认 `D:\sci文献数据`
- `--days`：筛选最近几天修改文献，默认 `1`
- `--dry-run`：仅分析，不写入核心能力沉淀
- `--force`：忽略 `processed_files.json`，强制重处理
- `--verbose`：输出详细日志
- `--max-files`：最多处理多少篇 PDF（默认 `0` 表示不限制）
- `--stop-on-bias`：任一文献被AI复核判定有偏差时立刻停止

## 输出说明
- `runtime/memory/YYYY-MM-DD.md`：当日学习总结
- `runtime/skills/*.md`：能力模式沉淀（自动去重）
- `runtime/skills/generated_examples/YYYY-MM-DD.md`：训练样本
- `runtime/skills/learning_state.json`：模式暴露次数/加权分/状态（observing/candidate/high_conf）
- `runtime/skills/evolution_log.md`：每日学习反思（新学到/被强化/仍不确定/下一步关注）
- `runtime/processed_files.json`：处理状态索引
- `runtime/memory/human_questions_YYYY-MM-DD.md`：AI复核发现偏差后自动生成的人类澄清问题
- 当输入目录不存在时，当日 memory 会明确记录 `输入目录不存在: <path>`，便于排错

## 当前实现边界
- 已实现规则驱动骨架（结构识别、基础分类、占位抽取、Markdown输出）
- 未实现深度语义理解模型与复杂表格/图像解析
- 未实现调度系统（刻意保持手动触发）

## 后续扩展建议
1. 替换 PDF 文本抽取层（如 OCR / 布局感知解析）
2. 接入 LLM 实现段落级 claim-evidence-synthesis 提取
3. 引入置信度校准与文献质量评分模型
4. 增加单元测试与回归测试数据集


## 逻辑校验（建议每次改动后执行）
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```


## Openclaw 安装与调用
- 该目录可直接作为 Openclaw skill 安装。
- Openclaw 元数据文件：`agents/openai.yaml`。
- Openclaw 入口脚本：`scripts/openclaw_entry.py`（通过环境变量转为 CLI 参数并调用 `learn_papers.py`）。

示例（Windows / PowerShell）：
```powershell
$env:OPENCLAW_INPUT_DIR = "D:\sci文献数据"
$env:OPENCLAW_DAYS = "1"
$env:OPENCLAW_DRY_RUN = "1"
python scripts/openclaw_entry.py
```

支持的环境变量：
- `OPENCLAW_INPUT_DIR`
- `OPENCLAW_DAYS`
- `OPENCLAW_DRY_RUN`
- `OPENCLAW_FORCE`
- `OPENCLAW_VERBOSE`
- `OPENCLAW_MAX_FILES`
- `OPENCLAW_STOP_ON_BIAS`
