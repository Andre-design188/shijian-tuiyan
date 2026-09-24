"""下载《史记》130卷、《资治通鉴》294卷全文到 corpus/，统一转成简体。来源：维基文库。

用法：python fetch_corpus.py            # 断点续传：已有且完整的卷会跳过
      python fetch_corpus.py --force    # 全部重下
做法：每次请求批量取 50 卷的源文本（wikitext），本地清洗后用 opencc 繁转简，一两分钟就能下完。
依赖：pip install opencc-python-reimplemented
只需跑一次。语料是 verify_quotes.py / grep_source.py 的底座。
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from opencc import OpenCC

T2S = OpenCC("t2s").convert
ROOT = Path(__file__).resolve().parent.parent / "corpus"
API = "https://zh.wikisource.org/w/api.php"
BOOKS = {"shiji": ("史記/卷{:03d}", 130), "tongjian": ("資治通鑑/卷{:03d}", 294)}

SHIJI = ("五帝本纪 夏本纪 殷本纪 周本纪 秦本纪 秦始皇本纪 项羽本纪 高祖本纪 吕太后本纪 孝文本纪 孝景本纪 孝武本纪 "
         "三代世表 十二诸侯年表 六国年表 秦楚之际月表 汉兴以来诸侯王年表 高祖功臣侯者年表 惠景间侯者年表 建元以来侯者年表 "
         "建元已来王子侯者年表 汉兴以来将相名臣年表 礼书 乐书 律书 历书 天官书 封禅书 河渠书 平准书 "
         "吴太伯世家 齐太公世家 鲁周公世家 燕召公世家 管蔡世家 陈杞世家 卫康叔世家 宋微子世家 晋世家 楚世家 越王勾践世家 "
         "郑世家 赵世家 魏世家 韩世家 田敬仲完世家 孔子世家 陈涉世家 外戚世家 楚元王世家 荆燕世家 齐悼惠王世家 萧相国世家 "
         "曹相国世家 留侯世家 陈丞相世家 绛侯周勃世家 梁孝王世家 五宗世家 三王世家 "
         "伯夷列传 管晏列传 老子韩非列传 司马穰苴列传 孙子吴起列传 伍子胥列传 仲尼弟子列传 商君列传 苏秦列传 张仪列传 "
         "樗里子甘茂列传 穰侯列传 白起王翦列传 孟子荀卿列传 孟尝君列传 平原君虞卿列传 魏公子列传 春申君列传 范雎蔡泽列传 "
         "乐毅列传 廉颇蔺相如列传 田单列传 鲁仲连邹阳列传 屈原贾生列传 吕不韦列传 刺客列传 李斯列传 蒙恬列传 张耳陈馀列传 "
         "魏豹彭越列传 黥布列传 淮阴侯列传 韩信卢绾列传 田儋列传 樊郦滕灌列传 张丞相列传 郦生陆贾列传 傅靳蒯成列传 "
         "刘敬叔孙通列传 季布栾布列传 袁盎晁错列传 张释之冯唐列传 万石张叔列传 田叔列传 扁鹊仓公列传 吴王濞列传 "
         "魏其武安侯列传 韩长孺列传 李将军列传 匈奴列传 卫将军骠骑列传 平津侯主父列传 南越列传 东越列传 朝鲜列传 "
         "西南夷列传 司马相如列传 淮南衡山列传 循吏列传 汲郑列传 儒林列传 酷吏列传 大宛列传 游侠列传 佞幸列传 滑稽列传 "
         "日者列传 龟策列传 货殖列传 太史公自序").split()
# 通鉴各纪起始卷（纪名, 首卷），据此推出"汉纪三十三"之类的卷名
TONGJIAN = [("周纪", 1), ("秦纪", 6), ("汉纪", 9), ("魏纪", 69), ("晋纪", 79), ("宋纪", 119), ("齐纪", 135),
            ("梁纪", 145), ("陈纪", 167), ("隋纪", 177), ("唐纪", 185), ("后梁纪", 266), ("后唐纪", 272),
            ("后晋纪", 280), ("后汉纪", 286), ("后周纪", 290)]
assert len(SHIJI) == 130


def cn_num(n: int) -> str:
    digits = "零一二三四五六七八九"
    if n < 10:
        return digits[n]
    tens, ones = divmod(n, 10)
    return ("" if tens == 1 else digits[tens]) + "十" + (digits[ones] if ones else "")


def title_of(book: str, n: int) -> str:
    if book == "shiji":
        return SHIJI[n - 1]
    name, first = [t for t in TONGJIAN if t[1] <= n][-1]
    return f"{name}{cn_num(n - first + 1)}"


def fetch_batch(titles: list[str]) -> dict[str, str]:
    """返回 {请求标题: wikitext}；自动跟随重定向。"""
    q = urllib.parse.urlencode({
        "action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
        "redirects": "1", "titles": "|".join(titles), "format": "json", "formatversion": "2",
    })
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": "shijian-tuiyan/1.0 (personal study)"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read().decode("utf-8"))["query"]
            break
        except Exception as e:  # noqa: BLE001
            if attempt == 5:
                raise
            time.sleep((60 if getattr(e, "code", None) == 429 else 5) * (attempt + 1))
    back = {x["to"]: x["from"] for x in d.get("redirects", [])}
    norm = {x["to"]: x["from"] for x in d.get("normalized", [])}
    out = {}
    for p in d["pages"]:
        if "revisions" not in p:
            continue
        title = p["title"]
        title = back.get(title, title)
        title = norm.get(title, title)
        out[title] = p["revisions"][0]["slots"]["main"]["content"]
    return out


# 行内包裹型模板（專/ProperNoun 人名地名、標/書 书名、YL 纪年、另 异读、! 僻字）：保留第一个参数；
# 其余模板整段删除——页眉导航、{{*|…}} 小字注与三家注、{{~~|…}} 年表删改。
INLINE = re.compile(r"\{\{\s*(ProperNoun|專|專名|专名|專名號|標|書|书名|書名|書名號|BookTitle|Book title|僻字|SIC|Sic|ruby|Ruby|異體字|异体字|YL|另|!)\s*\|([^{}]*)\}\}")
TEMPLATE_SEEN: dict[str, int] = {}


def clean(wt: str) -> str:
    wt = re.sub(r"<!--.*?-->|<ref[^>]*?/>|<ref.*?</ref>", "", wt, flags=re.S)
    wt = re.sub(r"-\{(?:[^{}|]*\|)?([^{}]*)\}-", r"\1", wt)  # 语言转换保护标记 -{字}-
    for name in re.findall(r"\{\{\s*([^|{}\n]+?)\s*[|}]", wt):
        TEMPLATE_SEEN[name] = TEMPLATE_SEEN.get(name, 0) + 1
    while True:
        nxt = INLINE.sub(lambda m: m.group(2).split("|")[0], wt)
        if nxt == wt:
            break
        wt = nxt
    while True:  # 由内向外剥模板
        nxt = re.sub(r"\{\{[^{}]*\}\}", "", wt)
        if nxt == wt:
            break
        wt = nxt
    wt = re.sub(r"\[\[(?:[Cc]ategory|分类|File|Image):[^\]]*\]\]", "", wt)
    wt = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", wt)
    wt = re.sub(r"<br\s*/?>", "\n", wt, flags=re.I)
    wt = re.sub(r"<[^>]+>", "", wt)
    wt = re.sub(r"'{2,}|__[A-Z]+__", "", wt)
    wt = re.sub(r"^=+\s*(.*?)\s*=+\s*$", r"\1", wt, flags=re.M)
    lines = [ln.strip() for ln in wt.splitlines()]
    return T2S("\n".join(ln for ln in lines if ln))


def main():
    force = "--force" in sys.argv
    for book, (pattern, total) in BOOKS.items():
        out_dir = ROOT / book
        out_dir.mkdir(parents=True, exist_ok=True)
        todo = []
        for n in range(1, total + 1):
            f = out_dir / f"{n:03d}_{title_of(book, n)}.txt"
            if force or not f.exists() or f.stat().st_size < 500:
                todo.append(n)
        for i in range(0, len(todo), 50):
            chunk = todo[i:i + 50]
            got = fetch_batch([pattern.format(n) for n in chunk])
            for n in chunk:
                wt = got.get(pattern.format(n))
                if not wt:
                    print(f"缺失 {book} {n:03d}", flush=True)
                    continue
                for old in out_dir.glob(f"{n:03d}_*.txt"):
                    old.unlink()
                text = clean(wt)
                (out_dir / f"{n:03d}_{title_of(book, n)}.txt").write_text(text, encoding="utf-8")
                print(f"{book} {n:03d} {title_of(book, n)} {len(text)}", flush=True)
            time.sleep(2)
    top = sorted(TEMPLATE_SEEN.items(), key=lambda x: -x[1])[:25]
    print("模板统计（检查是否有该保留正文的模板被整段删掉）：", top)
    print("done")


if __name__ == "__main__":
    main()
