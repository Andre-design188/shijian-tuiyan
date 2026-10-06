# 架构说明

## 整体结构

项目分为内容源、Python 工具和静态网页三个部分。案例 Markdown 与示范 JSON 是主要内容源；Python 脚本读取这些内容，完成检索、校验和页面生成；网页将生成的数据与模板、浏览器端推演代码组合。可选的本机 HTTP 服务提供静态文件，并通过受限的 Codex CLI 调用本地已登录账户。

```text
SKILL.md ───────────── Agent 推演流程
references/cases/*.md ─┐
examples/demos.json ───┼→ scripts/caselib.py → 检索 / 校验 / 页面生成
site/template.html + engine.js + dialog.js + errata.json ─┘
                                         ↓
                                   docs/index.html
                                         ↓
                           browser demo / Anthropic API（可选）
                                         ↓
                         optional scripts/serve_local.py
                                         ↓
                                 local Codex CLI
```

目录职责：

- `references/cases/`：按母题组织的结构化案例，含出处、史料等级、原文、决定变量和边界。
- `scripts/`：Python 标准库为主的读取、检索、引用核验、文本检查、语料下载、构建和本地服务。
- `site/`：静态页面模板、浏览器端引擎/对话交互和勘误信息。
- `examples/`：演示推演 JSON（源）及由构建脚本生成的 Markdown。
- `docs/index.html`：GitHub Pages 发布目录中的生成页面；页面按顺序展示三源决策法、史鉴方法论、易经九步和按需打开的案例示范；历史案例库及其他知识文档保存在 `docs/`。
- `corpus/`：由下载脚本产生的维基文库原文，按 `.gitignore` 不入库。

## 依赖方向规则

- `scripts` 内多个工具从 `caselib.py` 读取共享路径、案例和语料函数；`build_site.py` 还导入 `check_plain.py` 中的规则。
- `site/engine.js` 使用生成页面内嵌的案例数据，不直接请求 Python 服务来检索案例。
- `serve_local.py` 提供可选静态文件服务和 `/api/codex`，通过 `codex exec` 的只读沙箱和 JSON Schema 调用本机 Codex；浏览器页面不直接访问本地进程。
- 内容源 → 构建脚本 → `docs/index.html` / 示例 Markdown 为单向生成关系，禁止编辑生成文件作为唯一修改。
- GitHub Actions 的 `plain.yml` 运行文本检查；`verify.yml` 安装依赖、下载语料并运行引文核验。

关键约束：

- `caselib.py` 是案例字段解析、简繁异体归一和路径定位的共享实现；浏览器侧 `engine.js` 维护与之对应的引文归一规则，改规则时需同步。
- 案例引文及示范引文必须经过逐字来源校验；语料不在仓库中，完整校验要求联网下载。
- `serve_local.py` 仅绑定 `127.0.0.1`，要求 Host/Origin 与自定义请求头，并限制请求体大小；改本机接口时需保留这些限制。
- 发布页文件由 `build_site.py` 输出到 `docs/`，该目录也是 GitHub Pages 的输出目录；知识文档不要覆盖 `index.html` 或 `.nojekyll`。

## 主要数据流

### 案例维护和发布

维护者编辑案例 Markdown、示范 JSON 或网页源文件 → `verify_quotes.py` / `check_plain.py` 检查 → `build_site.py` 验证数据并嵌入模板及 JavaScript → 更新 `docs/index.html` 和示范 Markdown → GitHub Pages 发布。

### 用户推演

用户输入 → `dialog.js` 发起追问 → `engine.js` 按母题筛选《史记》《资治通鉴》案例（尽可能确保两书都有相关案例时各纳入一条），并要求模型按两书不同史料视角比较正反先例 → 模型再完成《易经》九步决策复核 → 输出经过案例编号、史料等级和引文清理 → `dialog.js` 展示本次三源依据、推演和行动卡。示范模式回放预设内容；自带 Anthropic Key 模式由浏览器调用 Anthropic SDK；本机模式调用本地 `/api/codex`，再由 Python 服务调用 Codex CLI。

## 待补充

## 易经方法数据

`references/yijing/decision-method.json` 同时保存原有六条易经思想精要和新增决策工作流，包括原句、来源、现代转译、边界和案例应用。`scripts/build_site.py` 将其嵌入生成页并验证六条精要、原则 ID、九步流程、字段和示范映射。实时模型按固定顺序逐步返回分析；网页按原则 ID 补入固定原句和出处。工作流是当代项目综合，不是古代固定程序。结构校验不等于原典校勘。

三源协同的产品逻辑：史记案例主要用来辨认人物位置、关系、选择及得失；资治通鉴案例主要用来辨认事件时序、局势变化及连锁后果；易经九步用来检查现实决策中的位势、早期信号、时机、责任、风险、调整和复盘。实时输出显式列出本次实际用到的两书案例和九步方法；某书没有匹配案例时会说明不作为该次直接历史依据。模型不得虚构缺失史料。

首页顺序固定为「三源决策法 → 史鉴方法论 → 易经九步」。案例示范默认只显示入口卡片；用户选中一张后才在详情区域渲染对应完整示范，易经方法在示范详情里压缩为三组检查，完整九步、原典与边界集中展示在易经方法专区。

- [ ] 当前没有独立的浏览器端自动化测试或 Python 单元测试框架；维护者可补充期望的覆盖层级。
- [ ] GitHub Pages 的发布分支/配置和线上监控策略需要项目维护者确认。
