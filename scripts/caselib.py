"""案例库与语料的公共读取工具（被 find_cases / verify_quotes / grep_source / check_plain / build_site 共用）。"""
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
CASES_DIR = SKILL / "references" / "cases"
CORPUS_DIR = SKILL / "corpus"
BOOK_DIRS = {"史记": "shiji", "资治通鉴": "tongjian"}
FETCH_HINT = "python scripts/fetch_corpus.py（先 pip install -r requirements.txt，下载一两分钟）"

REQUIRED = ["出处", "年代", "史料", "处境", "选项", "抉择", "原文", "结果",
            "决定变量", "可迁移", "对照", "边界", "现代映射"]
# 史料等级：A 可作依据；B 只依据抉择和结局；C 只作参照。判定标准见 SKILL.md「史料等级」
GRADES = {"A": "可作依据", "B": "依据主干", "C": "只作参照"}
GRADE_RE = re.compile(r"^([ABC])｜(\S.*)$")

# 语料与案例之间常见的异体/繁简残留；两边同时归一，只影响比对不影响展示
VARIANTS = str.maketrans({"馀": "余", "阬": "坑", "彊": "强", "県": "县", "鉅": "巨",
                          "脩": "修", "闲": "间", "嚮": "向", "蚤": "早", "倍": "背",
                          "劎": "剑", "倶": "俱", "讬": "托", "棬": "卷", "𢭏": "捣", "擣": "捣", "鬬": "斗", "鬭": "斗", "鬥": "斗", "呉": "吴"})
PUNCT = re.compile(r"[\s，。、；：？！“”‘’「」『』《》〈〉（）()［］\[\]〔〕【】…—·,.;:?!'\"-]")


def utf8_stdio():
    """脚本输出固定用 UTF-8：Windows 管道默认是 GBK，碰到生僻字会直接报错。"""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


utf8_stdio()


def norm(text: str) -> str:
    return PUNCT.sub("", text).translate(VARIANTS)


def norm_corpus(text: str) -> str:
    # 中华书局式校勘：（x）为删字、［x］/〔x〕为补字；(x) 同删字
    text = re.sub(r"（[^（）]{0,8}）|\([^()]{0,8}\)", "", text)
    return norm(text)


def load_cases():
    """返回 [{id, title, 母题, file, fields{key: value}}]；可迁移（x视角）类字段合并到 可迁移。"""
    cases = []
    for f in sorted(CASES_DIR.glob("*.md")):
        theme = f.stem
        cur = None
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^## (\d{2}-\d{2}) (.+)$", line)
            if m:
                cur = {"id": m.group(1), "title": m.group(2).strip(), "theme": theme,
                       "file": f.name, "fields": {}}
                cases.append(cur)
                continue
            m = re.match(r"^- ([^：]{1,12})：(.*)$", line)
            if cur and m:
                key = re.sub(r"（.*?）", "", m.group(1)).strip()
                val = m.group(2).strip()
                cur["fields"][key] = (cur["fields"].get(key, "") + " " + val).strip()
    return cases


def quotes_of(case) -> list[str]:
    """「原文」字段里的引文：推演只许从这里摘古文。"""
    return re.findall(r"「(.+?)」", case["fields"].get("原文", ""))


def all_quotes_of(case) -> list[tuple[str, str]]:
    """所有字段里用「」标出的古文 [(字段, 引文)]：页面上显示的每一句古文都要逐字对过原文。"""
    return [(k, q) for k, v in case["fields"].items() for q in re.findall(r"「(.+?)」", v)]


def grade_of(case) -> str:
    m = GRADE_RE.match(case["fields"].get("史料", ""))
    return m.group(1) if m else ""


def books_of(case) -> list[str]:
    src = case["fields"].get("出处", "")
    return [b for b in BOOK_DIRS if b in src]


def corpus_ready() -> bool:
    return all(any((CORPUS_DIR / d).glob("*.txt")) for d in BOOK_DIRS.values())


def load_corpus(book: str) -> list[tuple[str, str]]:
    """[(卷文件名, 原文)]；book 为 史记 / 资治通鉴。"""
    d = CORPUS_DIR / BOOK_DIRS[book]
    return [(p.stem, p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.txt"))]
