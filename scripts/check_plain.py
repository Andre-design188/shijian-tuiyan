"""说人话检查：案例库的现代文字段和三个示范推演，是页面上读者真正读的文字。

用法：python scripts/check_plain.py          # 列出所有不合格处，有则退出码 1（CI 用）
      python scripts/check_plain.py --stat   # 只按规则计数
不需要原文语料，零依赖，一秒跑完。

为什么要机检：文风靠人审只能凭感觉，写着写着 AI 腔就回来了。参照项目《高性价比人生指南》
2026-09-28 因读者抱怨"AI 味太重"加了同类检查；这里把 SKILL.md 里已有的纪律写成可判定的规则。
「」里的古文是原文，不查；用户的提问也不查。
检查六样：
 ① 长度：每个字段有上限（CAPS），示范里每一句不超过 DEMO_CAP 字。卡片要一眼读完。
 ② 套话：BANNED 里的词不用。只收要读者自己翻译一遍的口头禅和黑话，宁可漏也别误报。
 ③ 感叹号：不用，语气克制。
 ④ 破折号：一个字段最多一个"——"，多了就是在拿标点堆语气。
 ⑤ 吓人和宿命的词（SCARY）只能出现在记史实的字段；给建议的字段和示范要翻成现代说法（出局、背锅、被清洗）。
 ⑥ 像古文却没用「」：引号里有两个以上文言虚词，多半是古文。原文就改用「」（verify_quotes 会逐字校验），
    转述就去掉引号。2026-09-28 在没用「」的字段里查出 5 处古文和原文对不上，这条防的就是它。
"""
import json
import re
import sys
from collections import Counter

from caselib import CASES_DIR, SKILL

CAPS = {"处境": 80, "选项": 40, "抉择": 60, "结果": 60, "决定变量": 60,
        "可迁移": 70, "边界": 60, "现代映射": 40, "史料": 60}
ADVICE = {"可迁移", "边界", "现代映射"}
DEMO_CAP = 60
# 示范里不查的键：用户自己的提问、编号、枚举值、已由 build_site 校验过的古文
DEMO_SKIP = {"id", "question", "goal", "summary", "extra", "themes", "case", "role", "k", "quote", "quote_case"}
BANNED = [
    # AI 腔的口头禅：删掉句子意思不变
    "本质上", "说到底", "归根结底", "换句话说", "某种程度上", "不言而喻", "毋庸置疑", "显而易见",
    "值得注意的是", "需要注意的是", "值得一提的是", "总而言之", "综上所述", "由此可见",
    "至关重要", "不可或缺", "发人深省", "耐人寻味", "值得深思",
    # 互联网黑话：读者要先翻译一遍
    "赋能", "抓手", "闭环", "底层逻辑", "颗粒度", "降维打击", "心智", "势能", "链路", "范式", "组合拳",
    # 参照项目 issue #42 里被读者点名的写法
    "另一头", "产出", "干净的结局", "这条路没有",
]
SCARY = ["赐死", "赐剑", "族诛", "灭族", "夷三族", "腰斩", "车裂", "烹杀", "天命", "注定", "气数", "天亡"]
PARTICLES = set("之乎者也矣焉哉兮曰耳乃何")
# 直引号两两成对，单字引号（"奇"）也要吃掉，否则会把前一对的后引号和后一对的前引号配成一对
QUOTED = re.compile(r"\"([^\"]{1,80})\"|“([^”]{1,80})”")
CLASSIC = re.compile(r"「[^」]*」")


def length(s: str) -> int:
    return len(re.sub(r"\s", "", s))


def check_text(s: str, cap: int, advice: bool) -> list[tuple[str, str]]:
    out = []
    bare = CLASSIC.sub("", s)
    if length(s) > cap:
        out.append(("①长度", f"{length(s)} 字，上限 {cap}"))
    out += [("②套话", w) for w in BANNED if w in bare]
    if "！" in bare or "!" in bare:
        out.append(("③感叹号", ""))
    if bare.count("——") > 1:
        out.append(("④破折号", f"{bare.count('——')} 个"))
    if advice:
        out += [("⑤吓人", w) for w in SCARY if w in bare]
    for m in QUOTED.finditer(bare):
        seg = m.group(1) or m.group(2)
        if sum(ch in PARTICLES for ch in seg) >= 2:
            out.append(("⑥古文没用「」", seg))
    return out


def case_items():
    """逐行取案例字段（可迁移的不同视角分开算长度）：(位置, 字段, 文本)"""
    for f in sorted(CASES_DIR.glob("*.md")):
        cid = f.stem
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^## (\d{2}-\d{2}) ", line)
            if m:
                cid = m.group(1)
                continue
            m = re.match(r"^- ([^：]{1,12})：(.*)$", line)
            if m:
                key = re.sub(r"（.*?）", "", m.group(1)).strip()
                if key in CAPS:
                    yield cid, key, m.group(2).strip()


def demo_items():
    def walk(o, path):
        if isinstance(o, str):
            yield path, o
        elif isinstance(o, list):
            for i, x in enumerate(o):
                yield from walk(x, f"{path}[{i}]")
        elif isinstance(o, dict):
            for k, x in o.items():
                if k not in DEMO_SKIP:
                    yield from walk(x, f"{path}.{k}")
    for d in json.loads((SKILL / "examples" / "demos.json").read_text(encoding="utf-8")):
        yield from walk(d, "示范 " + d["id"])


def main():
    problems = []
    for cid, key, text in case_items():
        problems += [(rule, f"{cid} {key}", note, text) for rule, note in check_text(text, CAPS[key], key in ADVICE)]
    for path, text in demo_items():
        problems += [(rule, path, note, text) for rule, note in check_text(text, DEMO_CAP, True)]
    if "--stat" in sys.argv:
        for rule, n in sorted(Counter(p[0] for p in problems).items()):
            print(f"{rule}  {n}")
    else:
        for rule, where, note, text in problems:
            print(f"[{rule}] {where}" + (f"：{note}" if note else "") + f"\n    {text}")
    print(f"\n说人话检查：{len(problems)} 处不合格。" + ("" if problems else "全部通过。"))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
