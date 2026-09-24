"""生成展示页 docs/index.html 与示范文件 examples/示范-*.md。

数据源：references/cases/（案例库）、examples/demos.json（推演示范）、site/errata.json（引文勘误）；
页面脚本：site/template.html 内嵌 site/engine.js（提示词、模型调用、引文校验）与 site/dialog.js（对话框）。
用法：python build_site.py        # 任何一项校验失败都会中止，不产出页面
校验：示范和勘误引用的案例必须存在；示范里的古文、勘误里的"原文"必须逐字见于已校验的案例引文。
"""
import json
import re
import sys
from pathlib import Path

from caselib import CASES_DIR, SKILL, load_cases, norm, quotes_of

REPO = "https://github.com/gavincao6313-jpg/shijian-tuiyan"


def load_themes():
    themes = []
    for f in sorted(CASES_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        head = re.search(r"^# 母题(\d{2}) (\S+?)：(.+)$", text, re.M)
        modern = re.search(r"^> 现代问题：(.+)$", text, re.M)
        themes.append({"code": head.group(1), "name": head.group(2), "sub": head.group(3).strip(),
                       "modern": modern.group(1).strip() if modern else ""})
    return themes


def check(cond, msg, errors):
    if not cond:
        errors.append(msg)


def demo_markdown(d, cases):
    t = lambda i: cases[i]["title"]  # noqa: E731
    lines = [f"# 示范：{d['tab']}", "",
             "> 由 examples/demos.json 生成（python scripts/build_site.py），请改 JSON，不要直接改这个文件。", "",
             f"**来问的人说**：{d['question']}", "", f"**所求为何**：{d['goal']}", "", "## 追问"]
    lines += [f"- {q['q']}　回答：{q['pick']}" for q in d["questions"]]
    lines += ["", "## 局面卡"]
    lines += [f"- **{b['k']}**：{b['v']}" + ("（假设）" if b.get("assume") else "") for b in d["board"]]
    lines += ["", "## 母题：" + " + ".join(d["themes"]), "", "## 历史镜像",
              "| 选项 | 案例 | 正/反 | 像在哪里 | 不像的地方 | 结论 |", "|---|---|---|---|---|---|"]
    lines += [f"| {m['option']} | {m['case']} {t(m['case'])} | {m['role']} | {m['same']} | {m['diff']} | {m['use']} |"
              for m in d["mirrors"]]
    lines += ["", "## 推演"]
    for o in d["options"]:
        lines += [f"### {o['name']}" + ("（推荐）" if o.get("pick") else ""),
                  f"- 近期（0–6 个月）：{o['near']}", f"- 中期（1–2 年）：{o['mid']}", f"- 远期（3–5 年）：{o['far']}",
                  f"- **会怎么翻车**：{o['fail']}", f"- **看到这个信号就调整**：{o['signal']}", ""]
    lines += ["## 换位"] + [f"- **{s['who']}**：{s['v']}" for s in d["swap"]]
    v = d["verdict"]
    lines += ["", "## 太史公曰", f"推荐 **{v['pick']}**。「{v['quote']}」（{t(v['quote_case'])}）{v['why']}",
              f"- 前提：{v['premise']}", f"- 止损线：{v['stop']}", "", "## 行动卡",
              "- **本周做**：" + "；".join(f"{i + 1}. {x}" for i, x in enumerate(d["actions"]["do"])),
              "- **盯住的信号**：" + "；".join(d["actions"]["watch"]), f"- **底线**：{d['actions']['line']}", ""]
    return "\n".join(lines)


def main():
    cases = load_cases()
    by_id = {c["id"]: c for c in cases}
    themes = load_themes()
    codes = {t["code"] for t in themes}
    demos = json.loads((SKILL / "examples" / "demos.json").read_text(encoding="utf-8"))
    errata = json.loads((SKILL / "site" / "errata.json").read_text(encoding="utf-8"))
    quotes = {c["id"]: [norm(q) for q in quotes_of(c)] for c in cases}
    errors = []

    for d in demos:
        name = d["id"]
        for k in ("question", "goal", "summary"):
            check(bool(d.get(k)), f"[{name}] 缺少 {k}", errors)
        qs = d.get("questions", [])
        check(1 <= len(qs) <= 3, f"[{name}] 追问应为 1 到 3 个", errors)
        for q in qs:
            check(2 <= len(q["options"]) <= 4 and q.get("pick") in q["options"], f"[{name}] 追问「{q['q']}」的选项或预设回答不对", errors)
        for code in d["themes"]:
            check(code in codes, f"[{name}] 母题 {code} 不存在", errors)
        for m in d["mirrors"]:
            check(m["case"] in by_id, f"[{name}] 镜像案例 {m['case']} 不存在", errors)
            check(m["role"] in ("正例", "反例"), f"[{name}] role 只能是 正例/反例：{m['role']}", errors)
        check(sum(1 for o in d["options"] if o.get("pick")) == 1, f"[{name}] 必须恰好有一个推荐选项", errors)
        v = d["verdict"]
        qc = v["quote_case"]
        check(qc in by_id and any(norm(v["quote"]) in q for q in quotes.get(qc, [])),
              f"[{name}] 太史公曰的引文「{v['quote']}」不在案例 {qc} 的已校验原文里", errors)
    for e in errata:
        qs = quotes.get(e["case"], [])
        check(any(norm(e["right"]) in q for q in qs), f"勘误 {e['who']}：「{e['right']}」不在案例 {e['case']} 的原文里", errors)
        check(not any(norm(e["wrong"]) in q for q in qs), f"勘误 {e['who']}：错误写法竟然和原文一致，请检查", errors)
    if errors:
        print("构建中止：\n  - " + "\n  - ".join(errors))
        sys.exit(1)

    data = {
        "stats": {"cases": len(cases), "quotes": sum(len(q) for q in quotes.values()), "themes": len(themes),
                  "shiji_juan": 130, "tongjian_juan": 294},
        "themes": themes,
        "cases": [{"id": c["id"], "title": c["title"], "theme": c["file"][:2],
                   "src": c["fields"].get("出处", ""), "fields": c["fields"]} for c in cases],
        "demos": demos, "errata": errata,
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = (SKILL / "site" / "template.html").read_text(encoding="utf-8")
    html = html.replace("/*__DATA__*/null", payload).replace("__REPO__", REPO)
    for tag, name in (("/*__ENGINE_JS__*/", "engine.js"), ("/*__DIALOG_JS__*/", "dialog.js")):
        js = (SKILL / "site" / name).read_text(encoding="utf-8")
        assert "</script" not in js.lower(), f"{name} 里不能出现 </script>"
        html = html.replace(tag, js)
    out = SKILL / "docs"
    out.mkdir(exist_ok=True)
    (out / "index.html").write_text(html, encoding="utf-8", newline="\n")  # 固定 LF，跨平台生成结果一致
    (out / ".nojekyll").write_text("", encoding="utf-8")

    ex = SKILL / "examples"
    for old in ex.glob("示范-*.md"):
        old.unlink()
    for d in demos:
        fname = "示范-" + re.sub(r"[\s，,]", "", d["tab"]) + ".md"
        (ex / fname).write_text(demo_markdown(d, by_id), encoding="utf-8", newline="\n")
    print(f"已生成 docs/index.html（{len(html) // 1024} KB）与 {len(demos)} 份示范；"
          f"案例 {len(cases)}，引文 {data['stats']['quotes']}，勘误 {len(errata)}。")


if __name__ == "__main__":
    main()
