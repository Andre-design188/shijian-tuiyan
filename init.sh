#!/usr/bin/env bash
# 快速确认源码快照和无需联网的基础检查可用；不安装依赖、不下载语料。
set -euo pipefail

echo "=== 史鉴推演环境检查 ==="
if [[ ! -f "SKILL.md" || ! -d "scripts" ]]; then
  echo "错误：请从项目根目录运行 init.sh。" >&2
  exit 1
fi
echo "项目目录：$(pwd)"

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "错误：需要 Python 3.10 或更新版本。" >&2
  exit 1
fi

"$PYTHON" -c 'import sys; print("Python:", sys.version.split()[0]); sys.exit(0 if sys.version_info >= (3, 10) else 1)'
"$PYTHON" scripts/check_plain.py
"$PYTHON" scripts/find_cases.py --list >/dev/null
echo "案例索引读取正常。"

if [[ -d .git ]]; then
  echo "最近 Git 历史："
  git log --oneline -5
else
  echo "提示：当前是源码压缩包，没有 Git 历史。"
fi

if compgen -G 'corpus/shiji/*.txt' >/dev/null && compgen -G 'corpus/tongjian/*.txt' >/dev/null; then
  echo "检测到原文语料；如需全量引文核验，运行：$PYTHON scripts/verify_quotes.py"
else
  echo "未检测到完整原文语料；全量引文核验需联网运行：$PYTHON scripts/fetch_corpus.py"
fi
echo "=== 环境检查完成 ==="
