"""在《史记》《资治通鉴》全文中检索，返回卷名+上下文。用于：核对原文、找案例库以外的新案例、给推演补证据。

用法：
  python grep_source.py 陈婴                   # 两书都搜
  python grep_source.py 暴得大名 --book 史记    # 只搜一本（史记 / 资治通鉴）
  python grep_source.py "功.{0,4}身退" --regex  # 正则
  可选：--ctx 120（上下文字数，默认 80）  --max 20（最多条数，默认 12）
"""
import re
import sys

from caselib import FETCH_HINT, corpus_ready, load_corpus


def arg(name, default):
    if name in sys.argv:
        i = sys.argv.index(name)
        return sys.argv[i + 1]
    return default


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    if not corpus_ready():
        print(f"还没有下载两书原文，全文检索用不了（案例库照常可用）。下载：{FETCH_HINT}")
        sys.exit(2)
    pat = sys.argv[1]
    books = [arg("--book", None)] if "--book" in sys.argv else ["史记", "资治通鉴"]
    ctx, cap = int(arg("--ctx", 80)), int(arg("--max", 12))
    rx = re.compile(pat if "--regex" in sys.argv else re.escape(pat))
    n = 0
    for book in books:
        for name, text in load_corpus(book):
            flat = text.replace("\n", " ")
            for m in rx.finditer(flat):
                n += 1
                if n <= cap:
                    s, e = max(0, m.start() - ctx), min(len(flat), m.end() + ctx)
                    print(f"[{book}/{name}] …{flat[s:m.start()]}【{m.group(0)}】{flat[m.end():e]}…\n")
    print(f"共命中 {n} 处" + (f"（仅显示前 {cap} 处，用 --max 调整）" if n > cap else ""))


if __name__ == "__main__":
    main()
