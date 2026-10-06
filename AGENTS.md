# 史鉴推演 — Agent 工作指南

## 这是什么项目

本项目把现实中的多选人生决策映射到《史记》《资治通鉴》的结构化案例，输出带来源、反例、边界和止损线的推演。它是决策辅助工具，不代替用户判断或专业意见。

## 快速定向

- **技术栈**：Python 3.10+ 脚本；语料下载需要 `opencc-python-reimplemented`；网页为 HTML/CSS/JavaScript，无前端构建框架。
- **主要入口**：`SKILL.md`（推演规则）；`scripts/find_cases.py`（案例检索）；`scripts/serve_local.py`（本地网页服务）。
- **本地网页**：先运行 `python scripts/build_site.py` 生成展示页，再运行 `python scripts/serve_local.py`；Windows 用户也可双击 `启动本地推演.bat`。
- **新会话环境检查**：Bash 环境运行 `bash init.sh`；Windows PowerShell 运行 `./init.ps1`。
- **快速质检**：`python scripts/check_plain.py`；完整引文检查需先安装依赖并运行 `python scripts/fetch_corpus.py`，再运行 `python scripts/verify_quotes.py`。
- **当前检出**：这是下载的源码快照，当前目录没有 `.git` 元数据；需要 Git 历史或提交操作时，先在正式克隆仓库中工作。

## 知识库地图

| 我想了解... | 去读这个文件 |
|---|---|
| 产品用户、任务和能力边界 | `docs/business-solution.md` |
| 模块划分、依赖与数据流 | `docs/ARCHITECTURE.md` |
| 命名与文件约定 | `docs/CONVENTIONS.md` |
| 技术选择及未知原因 | `docs/TECH_DECISIONS.md` |
| 验收和质检标准 | `docs/QUALITY.md` |
| 易经决策方法及原文出处 | `references/yijing/README.md`、`references/yijing/decision-method.json` |
| 本轮系统评分 | `docs/PROJECT_REVIEW.md` |
| 当前执行计划 | `docs/exec-plans/active/` |
| 待办与技术债务 | `docs/exec-plans/backlog.md`、`docs/exec-plans/tech-debt-tracker.md` |
| 会话任务与进度 | `tasks.json`、`progress.md` |

## 工作规范

1. 修改前读本指南及相关知识库文档；涉及推演行为时遵循 `SKILL.md`。
2. 案例、示范或引文发生变化时，运行对应质检；不要凭记忆补写古文。
3. `docs/index.html` 和 `examples/示范-*.md` 是生成文件；改源文件后运行 `python scripts/build_site.py`，不要直接编辑生成结果。
4. 改变架构、行为、安全约束或维护命令时，同步更新相关文档。
5. 按 `tasks.json` 的顺序工作：每轮只处理第一条 `pending` 任务，不得顺手开始后续任务。
6. 任务验证通过后，先在 `progress.md` 顶部追加本次工作记录；再检查记录确实存在且描述了本次改动和验证结果，最后才能把任务标记为 `done`。
7. 完成第一条任务并完成版本管理动作后，停止工作，等待用户明确确认后再开始下一条任务。确认前不执行后续任务。
8. 首条任务完成后执行 Git 版本管理：确认工作区、生成清晰提交并推送 GitHub。若本地尚无 Git 仓库或 GitHub 远程仓库尚未创建，先记录本地 Git 初始化/提交结果；推送必须等待用户提供或确认 GitHub 仓库地址及可用访问权限，不得猜测仓库地址或可见性。

### 新增任务时

1. 填写 `tasks.json` 的全部字段，包括可执行的 `verify` 和 `requires_eval`。
2. 新功能、安全/权限/数据校验改动、预计修改 3 个以上文件或重构，`requires_eval` 设为 `true`；纯文档更新、配置调整、明确的小型 bug 修复可设为 `false`。

### 每次完成任务后

1. 运行该任务 `verify` 字段中的步骤；不得跳过验证自行标记完成。
2. 在 `progress.md` 顶部追加本次工作记录，包含任务 ID、改动、验证结果和未解决事项；随后由执行任务的 AI Coding 工具重新读取该文件并核对本次记录，再标记为 `done`。
3. `requires_eval: true` 的任务须先提供 `sprint_output.md` 供独立评审，评审通过后才能标为 `done`；`false` 的任务通过验证与进度记录核对后才能标为 `done`。
4. 按本指南的首条任务版本管理规则处理提交和 GitHub 推送。
5. 本轮只完成这一条任务；汇报结果并等待用户确认后续工作。

当前下载快照未包含 `.git`，且未发现现成 Evaluator 流程；仓库初始化、远程地址和评审安排需要维护者按实际情况确认。

## 常用命令

```powershell
python scripts/find_cases.py --list
python scripts/find_cases.py --theme 05
python scripts/check_plain.py
python scripts/build_site.py
python scripts/fetch_corpus.py
python scripts/verify_quotes.py
python scripts/serve_local.py
```

`fetch_corpus.py` 会联网从维基文库下载语料；仅在需要全文搜索或逐字引文核验时运行。`verify_quotes.py` 没有语料时只能做结构检查，不能声称引文已核实。

## 禁止事项

- 不得把推演建议描述成历史必然或现代决策的确定答案。
- 不得把未验证的案例、引文或模型生成的古文写成史料事实。
- 不得把用户输入、API Key 或本地日志提交到仓库。
- 不得直接修改由 `scripts/build_site.py` 生成的文件。
- 涉及自伤危机以及医疗、法律、税务、具体投资问题时，遵循 `SKILL.md` 的安全边界。
