# AGENTS.md

这个仓库是「史鉴推演」：用《史记》《资治通鉴》的案例库，给纠结中的人生抉择做推演。

- **用它推演**（有人纠结要不要辞职、跳槽、创业、合伙、回老家接班、给老板提意见等）：完全按 [SKILL.md](SKILL.md) 执行。先用 `python scripts/find_cases.py` 查案例，不要把案例库整个读进来；古文只能逐字摘自案例的「原文」字段。
- **改案例库或脚本**：规则也在 SKILL.md 的「史料等级」「维护」两节。改完跑 `python scripts/verify_quotes.py` 和 `python scripts/check_plain.py`，都通过才算完成。

Claude Code 用户把仓库克隆到 `~/.claude/skills/shijian-tuiyan` 即可，不需要这个文件。
