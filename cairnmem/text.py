"""分词与停用词。零依赖、纯标准库。

两条硬约定：
  * 汉字只取相邻二元组（"红石中继器" -> 红石/石中/中继/继器）。
  * 英文 / 数字取连续段，长度 >= 2，统一小写。

为什么不切词（jieba）：在「术语查询 + 短文档」场景下实测二元组更好，
切词会把专有名词切碎并且引入词典依赖。详见 README。
"""
import os
import re

_CJK_LO, _CJK_HI = 0x4E00, 0x9FFF
_TOKEN = re.compile(r"[\u4e00-\u9fff]+|[A-Za-z0-9_.+\-]+")
_CJK_ONLY = re.compile(r"^[\u4e00-\u9fff]+$")
_LATIN_ONLY = re.compile(r"^[a-z][a-z0-9_.+\-]{1,}$")
_FIRST_CJK = re.compile(r"^[\u4e00-\u9fff]")


def tokenize(text):
    """快速实现：正则切段 + 切片生成二元组，全部在 C 层完成。"""
    toks = []
    for m in _TOKEN.finditer(text):
        s = m.group(0)
        if _FIRST_CJK.match(s):
            n = len(s) - 1
            if n > 0:
                toks.extend([s[i:i + 2] for i in range(n)])
        elif len(s) >= 2:
            toks.append(s.lower())
    return toks


def tokenize_ref(text):
    """参考实现：逐字符状态机。慢，但语义最直白，测试用它钉住 tokenize()。"""
    toks, lat, prev = [], [], None
    for ch in text:
        o = ord(ch)
        if _CJK_LO <= o <= _CJK_HI:
            if len(lat) >= 2:
                toks.append("".join(lat))
            lat = []
            if prev is not None:
                toks.append(prev + ch)
            prev = ch
        elif o < 0x80 and (ch.isalnum() or ch in "_.+-"):
            prev = None
            lat.append(ch.lower())
        else:
            if len(lat) >= 2:
                toks.append("".join(lat))
            lat = []
            prev = None
    if len(lat) >= 2:
        toks.append("".join(lat))
    return toks


def is_cjk(tok):
    return bool(_CJK_ONLY.match(tok))


def is_latin(tok):
    return bool(_LATIN_ONLY.match(tok))


def load_stopwords(paths):
    s = set()
    for p in paths or []:
        if not p:
            continue
        p = os.path.expanduser(p)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                w = line.strip()
                if w and not w.startswith("#"):
                    s.add(w)
    return s
