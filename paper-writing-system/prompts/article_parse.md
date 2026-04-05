# Article Parse Rules (Template)

目标：从 Original Article 中提取可复用写作结构与逻辑。

## 输入
- 文本块（title, abstract, introduction, methods, results, discussion）

## 输出字段
- abstract_roles: Background/Objective/Methods/Results/Conclusion
- findings: question/method/result/reasoning/transition
- discussion_logic: result -> mechanism -> literature -> inference

## 约束
- 先保守抽取，再增强。
- 缺失字段允许 `unknown`，不得臆造。
