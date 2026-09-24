"""按关键词/母题/ID 检索案例库，输出精简卡片，避免把整个案例库读进上下文。

用法：
  python find_cases.py 辞职 老板              # 多关键词：命中越多排越前（任一字段）
  python find_cases.py --theme 05             # 列出某母题全部案例（05 或 功高）
  python find_cases.py --id 03-01 09-03       # 输出完整案例
  python find_cases.py --list                 # 母题总览（每个母题的案例标题）
  加 --full 输出完整字段；默认只输出 标题/出处/可迁移/边界/现代映射。
"""
import sys

from caselib import load_cases

BRIEF = ["出处", "可迁移", "边界", "现代映射"]
WEIGHT = {"现代映射": 3, "可迁移": 2, "决定变量": 2, "处境": 1, "选项": 1}


def show(c, full=False):
    print(f"## {c['id']} {c['title']}  〔{c['theme']}〕")
    for k, v in c["fields"].items():
        if full or k in BRIEF:
            print(f"- {k}：{v}")
    print()


def main():
    argv = sys.argv[1:]
    full = "--full" in argv
    argv = [a for a in argv if a != "--full"]
    cases = load_cases()
    if not argv or argv[0] == "--list":
        theme = None
        for c in cases:
            if c["theme"] != theme:
                theme = c["theme"]
                print(f"\n{theme}")
            print(f"  {c['id']} {c['title']}  | {c['fields'].get('现代映射', '')[:40]}")
        return
    if argv[0] == "--id":
        for c in cases:
            if c["id"] in argv[1:]:
                show(c, full=True)
        return
    if argv[0] == "--theme":
        key = argv[1]
        for c in cases:
            if c["theme"].startswith(key) or key in c["theme"]:
                show(c, full)
        return
    scored = []
    for c in cases:
        blob_title = c["title"]
        score = 0
        for kw in argv:
            if kw in blob_title:
                score += 3
            for k, v in c["fields"].items():
                if kw in v:
                    score += WEIGHT.get(k, 1)
        if score:
            scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        print("无命中。换同义词，或用 --list 看母题总览。")
    for _, c in scored[:8]:
        show(c, full)


if __name__ == "__main__":
    main()
