# 代码约定

## 文件命名

- Python 脚本使用小写下划线命名，如 `find_cases.py`、`verify_quotes.py`。
- 浏览器脚本使用小写名称，如 `engine.js`、`dialog.js`。
- 案例文件用两位母题序号和中文主题命名，如 `01-去留.md`；案例 ID 为 `NN-NN`。
- 示例 Markdown 使用 `示范-场景名.md`；`examples/demos.json` 是示例内容源。

## 变量和函数命名

- Python 函数与变量采用 `snake_case`，如 `load_cases`、`grade_of`、`CORPUS_DIR`；模块级常量使用大写下划线。
- JavaScript 函数与变量采用 `camelCase`，如 `buildPlanPrompt`、`caseQuotes`；常量使用大写，如 `PLAN_SYSTEM`。
- 案例字段使用中文固定键，如 `决定变量`、`可迁移`、`边界`，变更字段时同步维护 `caselib.REQUIRED` 和生成/检查流程。

## 目录组织

- 内容与执行逻辑分开：案例在 `references/cases/`，运行脚本在 `scripts/`，前端源在 `site/`。
- 原文语料由 `scripts/fetch_corpus.py` 下载至 `corpus/`，不提交生成语料。
- 生成文件在文件头或构建脚本中注明来源；修改其源 JSON、Markdown 或模板后重新生成。

## 文本与引文

- 用户可见文本优先使用简体中文和短句；CI 的具体禁用词、长度规则见 `scripts/check_plain.py`。
- 古文直引用 `「」`，只从案例「原文」字段或已检索原文摘录；不得凭记忆补引文。
- 新案例需有规定的全部字段、A/B/C 史料等级理由、出处卷名和有效对照 ID。

## Git Commit 格式

从公开压缩包无法读取提交历史，项目现有约定**待补充**。建议采用 `type(scope): 描述`，例如 `docs(harness): add project knowledge base`；以维护者约定为准。

## 待补充

- [ ] 是否要求 Conventional Commits、提交语言及 PR 审查规则。
- [ ] 是否对 Python/JavaScript 使用格式化工具或静态检查器。
