"""生成展示页 docs/index.html 与示范文件 examples/示范-*.md。

数据源：references/cases/（案例库）、examples/demos.json（推演示范）、site/errata.json（引文勘误）；
页面脚本：site/template.html 内嵌 site/engine.js（提示词、模型调用、引文校验）与 site/dialog.js（对话框）。
用法：python build_site.py        # 任何一项校验失败都会中止，不产出页面
校验：示范和勘误引用的案例必须存在；示范里的古文（「」）、勘误里的"原文"必须逐字见于已校验的案例引文；
      每个案例都要有史料等级，示范照镜用到 C 级案例时只能"降为参考"。
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

from caselib import CASES_DIR, GRADES, SKILL, all_quotes_of, grade_of, load_cases, norm, quotes_of
from check_plain import BANNED, DEMO_CAP, SCARY

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


def strings(o, skip=()):
    """示范 JSON 里的所有文本（跳过指定键）"""
    if isinstance(o, str):
        yield o
    elif isinstance(o, list):
        for x in o:
            yield from strings(x, skip)
    elif isinstance(o, dict):
        for k, x in o.items():
            if k not in skip:
                yield from strings(x, skip)


def demo_markdown(d, cases, yijing):
    t = lambda i: cases[i]["title"]  # noqa: E731
    g = lambda i: grade_of(cases[i])  # noqa: E731
    lines = [f"# 示范：{d['tab']}", "",
             "> 由 examples/demos.json 生成（python scripts/build_site.py），请改 JSON，不要直接改这个文件。", "",
             f"**来问的人说**：{d['question']}", "", f"**所求为何**：{d['goal']}", "", "## 追问"]
    lines += [f"- {q['q']}　回答：{q['pick']}" for q in d["questions"]]
    lines += ["", "## 局面卡"]
    lines += [f"- **{b['k']}**：{b['v']}" + ("（假设）" if b.get("assume") else "") for b in d["board"]]
    lines += ["", "## 母题：" + " + ".join(d["themes"]), "", "## 历史镜像",
              "| 选项 | 案例 | 正/反 | 像在哪里 | 不像的地方 | 结论 |", "|---|---|---|---|---|---|"]
    lines += [f"| {m['option']} | {m['case']} {t(m['case'])}（史料 {g(m['case'])}） | {m['role']} | {m['same']} | {m['diff']} | {m['use']} |"
              for m in d["mirrors"]]
    lines += ["", "## 推演"]
    for o in d["options"]:
        lines += [f"### {o['name']}" + ("（推荐）" if o.get("pick") else ""),
                  f"- 近期（0–6 个月）：{o['near']}", f"- 中期（1–2 年）：{o['mid']}", f"- 远期（3–5 年）：{o['far']}",
                  f"- **会怎么翻车**：{o['fail']}", f"- **看到这个信号就调整**：{o['signal']}", ""]
    lines += ["## 换位"] + [f"- **{s['who']}**：{s['v']}" for s in d["swap"]]
    lines += ["", "## 易经决策方法：本案复核", "本方法是项目基于经传材料形成的现代综合，不是古代固定步骤。"]
    apps = {a["case"]: a for a in yijing["caseApplications"]}
    app = apps[d["id"]]
    principle_map = {step["id"]: step for step in yijing["principles"]}
    lines += [f"**案例应用：{app['title']}**：{app['application']}", "", "| 易经方法 | 本案分析 | 本案行动 |", "|---|---|---|"]
    for item in app["checks"]:
        methods = "、".join(principle_map[sid]["name"].split("：", 1)[0] for sid in item["principles"])
        lines += [f"| {methods} | {item['analysis']} | {item['action']} |"]
    lines += ["", f"> 完整九步方法与原典出处见易经决策方法数据；方法边界：{yijing['methodBoundary']}"]
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
    yijing = json.loads((SKILL / "references" / "yijing" / "decision-method.json").read_text(encoding="utf-8"))
    errata = json.loads((SKILL / "site" / "errata.json").read_text(encoding="utf-8"))
    quotes = {c["id"]: [norm(q) for q in quotes_of(c)] for c in cases}
    verified = [norm(q) for c in cases for _, q in all_quotes_of(c)]  # verify_quotes 已逐字对过原文
    errors = []
    principles = {item["id"]: item for item in yijing["principles"]}
    check(len(principles) == len(yijing["principles"]) and len(principles) >= 8,
          "易经原则 ID 须唯一，至少八项", errors)
    essentials = {item["id"]: item for item in yijing.get("essentials", [])}
    check(len(essentials) == 6 and len(essentials) == len(yijing.get("essentials", [])),
          "易经思想精要需保留六条且 ID 唯一", errors)
    for item in yijing.get("essentials", []):
        for key in ("id", "name", "phrase", "source", "url", "method", "question", "boundary", "example", "case"):
            check(bool(item.get(key)), f"易经精要 {item.get('id', '?')} 缺少 {key}", errors)
        check(item.get("url", "").startswith("https://"), f"易经精要 {item.get('id')} 来源须为 HTTPS 链接", errors)
        check(any(d.get("id") == item.get("case") for d in demos), f"易经精要 {item.get('id')} 的案例不存在", errors)
    for item in yijing["principles"]:
        for key in ("id", "name", "phrase", "source", "url", "reading", "question", "boundary"):
            check(bool(item.get(key)), f"易经原则 {item.get('id', '?')} 缺少 {key}", errors)
        check(item.get("url", "").startswith("https://"), f"易经原则 {item.get('id')} 来源须为 HTTPS 链接", errors)
        check(len(norm(item.get("phrase", ""))) >= 4, f"易经原则 {item.get('id')} 引句太短或为空", errors)
    check(len(yijing["workflow"]) == len(set(yijing["workflow"])) and set(yijing["workflow"]) == set(principles),
          "工作流必须覆盖全部唯一原则", errors)
    check(yijing.get("workflowMeaning") == "→".join(principles[s]["name"].split("：")[0].split("：")[0] for s in yijing["workflow"]),
          "易经工作流摘要需与实际步骤一致", errors)
    check(bool(yijing.get("methodBoundary")), "易经方法须声明现代综合与使用边界", errors)
    for step in yijing["workflow"]:
        item = principles.get(step, {})
        url = item.get("url", "")
        check(url.startswith("https://") and bool(norm(item.get("phrase", ""))),
              f"易经步骤 {step} 缺少有效原文数据", errors)
        check(item.get("source") and item.get("reading") and item.get("question") and item.get("boundary"),
              f"易经步骤 {step} 缺少出处、转译、自检问题或边界", errors)
    check(len({a["case"] for a in yijing["caseApplications"]}) == len(yijing["caseApplications"])
          and {a["case"] for a in yijing["caseApplications"]} == {d["id"] for d in demos},
          "每个示范都必须且只能对应一个易经综合应用", errors)
    for a in yijing["caseApplications"]:
        check(bool(a.get("title") and a.get("application")), f"案例 {a.get('case')} 缺少易经综合应用", errors)
        checks = a.get("checks", [])
        check(len(checks) == 3, f"案例 {a.get('case')} 的易经复核应有 3 条案例分析", errors)
        for item in checks:
            check(bool(item.get("principles")) and all(pid in principles for pid in item.get("principles", [])),
                  f"案例 {a.get('case')} 易经分析引用了不存在的方法步骤", errors)
            check(bool(item.get("analysis") and item.get("action")),
                  f"案例 {a.get('case')} 易经分析必须写明本案分析和行动", errors)

    for c in cases:
        check(grade_of(c) in GRADES, f"[{c['id']}] 缺少史料等级（「史料：A｜理由」），先跑 verify_quotes.py", errors)
    for d in demos:
        name = d["id"]
        for k in ("question", "goal", "summary"):
            check(bool(d.get(k)), f"[{name}] 缺少 {k}", errors)
        check(d.get("id") in {a["case"] for a in yijing["caseApplications"]},
              f"[{name}] 缺少易经综合案例应用", errors)
        qs = d.get("questions", [])
        check(1 <= len(qs) <= 3, f"[{name}] 追问应为 1 到 3 个", errors)
        for q in qs:
            check(2 <= len(q["options"]) <= 4 and q.get("pick") in q["options"], f"[{name}] 追问「{q['q']}」的选项或预设回答不对", errors)
        for code in d["themes"]:
            check(code in codes, f"[{name}] 母题 {code} 不存在", errors)
        for m in d["mirrors"]:
            check(m["case"] in by_id, f"[{name}] 镜像案例 {m['case']} 不存在", errors)
            check(m["role"] in ("正例", "反例"), f"[{name}] role 只能是 正例/反例：{m['role']}", errors)
            if m["case"] in by_id and grade_of(by_id[m["case"]]) == "C":
                check(str(m["use"]).startswith("降为参考"), f"[{name}] {m['case']} 是 C 级（只作参照），use 只能写「降为参考」", errors)
        for s in strings(d, skip=("quote",)):  # 太史公曰的 quote 不带「」，上面单独校验
            for q in re.findall(r"「(.+?)」", s):
                check(any(norm(q) in v for v in verified), f"[{name}] 古文「{q}」不在任何案例已校验的引文里", errors)
        check(sum(1 for o in d["options"] if o.get("pick")) == 1, f"[{name}] 必须恰好有一个推荐选项", errors)
        v = d["verdict"]
        qc = v["quote_case"]
        check(qc in by_id and any(norm(v["quote"]) in q for q in quotes.get(qc, [])),
              f"[{name}] 太史公曰的引文「{v['quote']}」不在案例 {qc} 的已校验原文里", errors)
    for e in errata:
        qs = [norm(q) for _, q in all_quotes_of(by_id[e["case"]])] if e["case"] in by_id else []
        check(any(norm(e["right"]) in q for q in qs), f"勘误 {e['who']}：「{e['right']}」不在案例 {e['case']} 已校验的引文里", errors)
        check(not any(norm(e["wrong"]) in q for q in qs), f"勘误 {e['who']}：错误写法竟然和原文一致，请检查", errors)
    if errors:
        print("构建中止：\n  - " + "\n  - ".join(errors))
        sys.exit(1)

    grades = Counter(grade_of(c) for c in cases)
    data = {
        "stats": {"cases": len(cases), "quotes": len(verified), "themes": len(themes),
                  "shiji_juan": 130, "tongjian_juan": 294, "grades": {k: grades[k] for k in GRADES}},
        "themes": themes,
        "grades": GRADES,
        "plain": {"banned": BANNED, "scary": SCARY, "cap": DEMO_CAP},
        "cases": [{"id": c["id"], "title": c["title"], "theme": c["file"][:2], "grade": grade_of(c),
                   "src": c["fields"].get("出处", ""), "fields": c["fields"]} for c in cases],
        "demos": demos, "errata": errata,
        "yijing": yijing,
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = (SKILL / "site" / "template.html").read_text(encoding="utf-8")
    html = html.replace("/*__DATA__*/null", payload).replace("__REPO__", REPO)
    html = html.replace("${esc(DATA.stats.cases)}", str(data["stats"]["cases"]))
    html = html.replace("${esc(DATA.yijing.workflowMeaning)}", data["yijing"]["workflowMeaning"])
    html = html.replace("${esc(DATA.yijing.methodBoundary)}", data["yijing"]["methodBoundary"])
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
        (ex / fname).write_text(demo_markdown(d, by_id, yijing), encoding="utf-8", newline="\n")
    print(f"已生成 docs/index.html（{len(html) // 1024} KB）与 {len(demos)} 份示范；"
          f"案例 {len(cases)}（史料 " + " / ".join(f"{k} {grades[k]}" for k in GRADES) + "），"
          f"引文 {data['stats']['quotes']}，勘误 {len(errata)}。")


if __name__ == "__main__":
    main()
