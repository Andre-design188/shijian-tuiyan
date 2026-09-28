"""案例库质检：字段完整性 + 史料等级格式 + 引文逐字对原文 + 对照ID存在。可判定，零人工。

用法：python verify_quotes.py            # 全量检查，失败时退出码 1；语料没下载时只做结构检查，退出码 2
      python verify_quotes.py 05-03     # 只查某些案例
      python verify_quotes.py --hint    # 失败引文附上原文中最接近的片段，便于修正
规则：
  - 所有字段里用「」标出的古文，去标点后须在出处所列书中逐字出现（史记/资治通鉴）。
    不只查「原文」：处境、结果、可迁移里顺手引的古文同样显示在页面上，2026-09-28 在这些字段里查出 5 处对不上。
    引文中间用"……"省略的，省略号两边各自须见于同一卷。
  - 「原文」字段标注"（大意…）"的引文若未命中只记 WARN，不算失败。
  - 引文所在卷（史记篇名 / 通鉴"汉纪三十三"式卷名）必须写进「出处」，保证出处可追溯到卷。
  - 「史料」写成"A｜理由"，等级只能是 A、B、C。
"""
import re
import sys

from caselib import (FETCH_HINT, GRADE_RE, REQUIRED, all_quotes_of, books_of, corpus_ready, load_cases,
                     load_corpus, norm, norm_corpus)


def parts_of(q: str) -> list[str]:
    return [p for p in (norm(x) for x in re.split(r"…+", q)) if p]


def locate(q: str, src: str, corpora) -> tuple[str | None, bool]:
    """返回 (命中的"书/卷", 该卷是否写进了出处)。先在出处列出的卷里找，找不到再全书找。"""
    parts = parts_of(q)
    if not parts:
        return None, False
    hits = [(book, name) for book, vols in corpora.items() for name, text in vols if all(p in text for p in parts)]
    for book, name in hits:
        if name.split("_", 1)[1] in src:
            return f"{book}/{name}", True
    return (f"{hits[0][0]}/{hits[0][1]}", False) if hits else (None, False)


def hint(q: str, normed) -> str:
    """找引文中最长的、能在原文里命中的分句，打印其（去标点的）上下文，便于人工改正。"""
    clauses = sorted((norm(c) for c in re.split(r"[，。；：？！、…]", q)), key=len, reverse=True)
    for nc in (c for c in clauses if len(c) >= 4):
        for book, vols in normed.items():
            for name, text in vols:
                i = text.find(nc)
                if i >= 0:
                    return f"    ↳ 近似于 {book}/{name}: …{text[max(0, i - 40): i + len(nc) + 60]}…"
    return "    ↳ 原文中未找到任何分句（可能出处书名错了，或引文非该书）"


def structure(c, ids) -> list[str]:
    problems = []
    for k in REQUIRED:
        v = c["fields"].get(k, "")
        if not v or v in ("——", "-", "无"):
            problems.append(f"缺字段/空字段：{k}")
    if c["fields"].get("史料") and not GRADE_RE.match(c["fields"]["史料"]):
        problems.append("史料要写成「A｜理由」，等级只能是 A、B、C")
    if not books_of(c):
        problems.append("出处须写明 史记· 或 资治通鉴·")
    for ref in re.findall(r"\d{2}-\d{2}", c["fields"].get("对照", "")):
        if ref not in ids:
            problems.append(f"对照ID不存在：{ref}")
    return problems


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    want_hint = "--hint" in sys.argv
    cases = load_cases()
    ids = {c["id"] for c in cases}
    have_corpus = corpus_ready()
    normed = {b: [(n, norm_corpus(t)) for n, t in load_corpus(b)] for b in ("史记", "资治通鉴")} if have_corpus else {}

    fails = warns = checked = 0
    seen = set()
    for c in cases:
        if args and c["id"] not in args:
            continue
        problems, notes = structure(c, ids), []
        if c["id"] in seen:
            problems.append("ID 重复")
        seen.add(c["id"])
        books = {b: normed[b] for b in books_of(c)} if have_corpus else {}
        src = c["fields"].get("出处", "")
        loose = "大意" in c["fields"].get("原文", "")
        for field, q in (all_quotes_of(c) if have_corpus else []):
            checked += 1
            where, in_src = locate(q, src, books)
            tip = ("\n" + hint(q, books)) if want_hint else ""
            if where and in_src:
                notes.append(f"  ✓ {field}「{q[:24]}…」→ {where}")
            elif where:
                problems.append(f"出处未写明引文所在卷：{field}「{q[:12]}…」在 {where}，把卷名补进出处")
            elif loose and field == "原文":
                warns += 1
                problems.append(f"WARN 大意引文未逐字命中：「{q}」{tip}")
            else:
                problems.append(f"引文未命中（{field}）：「{q}」{tip}")
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
    if not have_corpus:
        print(f"\n案例 {total} 条，结构检查 FAIL {fails} 条。语料没下载，引文没有校验：先运行 {FETCH_HINT}")
        sys.exit(1 if fails else 2)
    print(f"\n案例 {total} 条，引文 {checked} 句；FAIL {fails} 条，WARN {warns} 句。")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
