"""案例库质检：字段完整性 + 引文逐字对原文 + 对照ID存在。可判定，零人工。

用法：python verify_quotes.py            # 全量检查，失败时退出码 1
      python verify_quotes.py 05-03     # 只查某些案例
      python verify_quotes.py --hint    # 失败引文附上原文中最接近的片段，便于修正
规则：
  - 每条引文「…」去标点后须在出处所列书中逐字出现（史记/资治通鉴）。
  - 标注"（大意…）"的引文若未命中只记 WARN，不算失败。
  - 引文所在卷（史记篇名 / 通鉴"汉纪三十三"式卷名）必须写进「出处」，保证出处可追溯到卷。
"""
import re
import sys

from caselib import REQUIRED, books_of, load_cases, load_corpus, norm, norm_corpus, quotes_of


def locate(q: str, corpora) -> str | None:
    nq = norm(q)
    for book, vols in corpora.items():
        for name, text in vols:
            if nq in text:
                return f"{book}/{name}"
    return None


def hint(q: str, normed) -> str:
    """找引文中最长的、能在原文里命中的分句，打印其（去标点的）上下文，便于人工改正。"""
    clauses = sorted((norm(c) for c in re.split(r"[，。；：？！、]", q)), key=len, reverse=True)
    for nc in (c for c in clauses if len(c) >= 4):
        for book, vols in normed.items():
            for name, text in vols:
                i = text.find(nc)
                if i >= 0:
                    return f"    ↳ 近似于 {book}/{name}: …{text[max(0, i - 40): i + len(nc) + 60]}…"
    return "    ↳ 原文中未找到任何分句（可能出处书名错了，或引文非该书）"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    want_hint = "--hint" in sys.argv
    cases = load_cases()
    ids = {c["id"] for c in cases}
    raw = {b: load_corpus(b) for b in ("史记", "资治通鉴")}
    if not all(raw.values()):
        print("语料缺失：先运行 python fetch_corpus.py")
        sys.exit(2)
    normed = {b: [(n, norm_corpus(t)) for n, t in vols] for b, vols in raw.items()}

    fails = warns = checked = 0
    seen = set()
    for c in cases:
        if args and c["id"] not in args:
            continue
        problems, notes = [], []
        if c["id"] in seen:
            problems.append("ID 重复")
        seen.add(c["id"])
        for k in REQUIRED:
            v = c["fields"].get(k, "")
            if not v or v in ("——", "-", "无"):
                problems.append(f"缺字段/空字段：{k}")
        books = books_of(c)
        if not books:
            problems.append("出处须写明 史记· 或 资治通鉴·")
        for ref in re.findall(r"\d{2}-\d{2}", c["fields"].get("对照", "")):
            if ref not in ids:
                problems.append(f"对照ID不存在：{ref}")
        loose = "大意" in c["fields"].get("原文", "")
        for q in quotes_of(c):
            checked += 1
            where = locate(q, {b: normed[b] for b in books})
            if where:
                notes.append(f"  ✓ 「{q[:24]}…」→ {where}")
                vol = where.split("_", 1)[1]
                if vol not in c["fields"].get("出处", ""):
                    problems.append(f"出处未写明引文所在卷：应包含「{vol}」（引文「{q[:12]}…」在 {where}）")
            elif loose:
                warns += 1
                problems.append(f"WARN 大意引文未逐字命中：「{q}」" + ("\n" + hint(q, {b: normed[b] for b in books}) if want_hint else ""))
            else:
                problems.append(f"引文未命中：「{q}」" + ("\n" + hint(q, {b: normed[b] for b in books}) if want_hint else ""))
        hard = [p for p in problems if not p.startswith("WARN")]
        if hard:
            fails += 1
        status = "FAIL" if hard else ("WARN" if problems else "PASS")
        if problems or args:
            print(f"[{status}] {c['id']} {c['title']}")
            for p in problems:
                print("  - " + p)
            if args:
                print("\n".join(notes))
    total = len([c for c in cases if not args or c["id"] in args])
    print(f"\n案例 {total} 条，引文 {checked} 句；FAIL {fails} 条，WARN {warns} 句。")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
