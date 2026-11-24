"""档案层：从原始材料里，找出知识库还没有抽象掉的东西。

它只做两件事：
    gap     算「档案里有、知识库里没有」的缺口
    verify  给某个候选回档案找证据（出处 + 上下文）

外加线索驱动的一对：
    markers 找出知识库里「做过工程 / 吃过大亏」的条目
    dig     顺着这类条目回档案挖原始记录（命令、版本、报错原文）

硬规则：dig / verify 零命中 = 假设错，直接丢弃。
没有证据的候选不许进知识库，否则这一层会变成编造工厂。
"""
import collections
import json
import os
import re

from .index import load, workdir
from .text import is_cjk, is_latin, load_stopwords, tokenize

DEFAULT_MARKER = r"^session-([0-9a-f\-]{36})"

DEFAULT_LESSON = ["根因", "踩坑", "报错", "失败", "不兼容", "冲突", "崩溃", "回滚",
                  "损坏", "权限", "超时", "卡死", "无效", "无法", "铁律", "唯一可", "避坑"]
DEFAULT_ARTIFACT = ["脚本", "流水线", "构建", "产物", "工具", "命令行", "路径", "实现",
                    "交付", "跑通", "写成", "建了", "写了", "搭了", "代码", ".py", ".mjs",
                    ".sh", ".ps1", ".c", "配置", "版本"]

ANCHOR = re.compile(
    r"[A-Za-z_][A-Za-z0-9_.\-]{3,}"
    r"|\d+(?:\.\d+){1,3}(?:-[A-Za-z0-9.]+)?")


def _acfg(cfg):
    """档案源是「一份文本 + 一个可选的分段正则」。

    marker_regex 为 None 时整份材料算作一段 —— 这样 cairn 不预设任何工具、
    任何日志格式，只要求你能把材料导成一份纯文本。
    """
    a = cfg.get("archive") or {}
    path = os.path.expanduser(a.get("path") or "")
    pat = a.get("marker_regex")
    return a, path, (re.compile(pat) if pat else None)


def _counts_path(cfg):
    return os.path.join(workdir(cfg), "archive_counts.json")


def build(cfg):
    a, path, _ = _acfg(cfg)
    if not path or not os.path.exists(path):
        raise SystemExit("archive.path 不存在：%r" % path)
    c = collections.Counter()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            c.update(tokenize(line))
    out = _counts_path(cfg)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False)
    print("档案词频：%d token，%d 种 -> %s" % (sum(c.values()), len(c), out))
    return c


def _load_counts(cfg):
    p = _counts_path(cfg)
    if not os.path.exists(p):
        raise SystemExit("还没有档案词频，先跑: cairn archive-build")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _kb_vocab(cfg):
    _, store = load(cfg)
    voc = set()
    for d in store.values():
        voc.update(tokenize(d["title"] + " " + d["body"]))
    return voc, store


def _stop(cfg):
    a = cfg.get("archive") or {}
    return load_stopwords([os.path.expanduser(p) for p in (a.get("stopwords") or [])])


def gap(cfg, mins=20, top=60, kind="cjk", quiet=False):
    voc, _ = _kb_vocab(cfg)
    counts = _load_counts(cfg)
    stop = _stop(cfg)
    items = []
    for t, c in counts.items():
        if c < mins or t in voc or t in stop:
            continue
        if kind in ("cjk", "all") and is_cjk(t):
            k = "cjk"
        elif kind in ("lat", "all") and is_latin(t):
            k = "lat"
        else:
            continue
        items.append((c, t, k))
    items.sort(reverse=True)
    if not quiet:
        print("知识库词表 %d 种，档案词表 %d 种" % (len(voc), len(counts)))
        print("候选（频次>=%d、去停用词、kind=%s）：%d 种\n" % (mins, kind, len(items)))
        for c, t, k in items[:top]:
            print("%8d  %-4s  %s" % (c, k, t))
    return items


def verify(cfg, term, show=3):
    _, path, marker = _acfg(cfg)
    if not path or not os.path.exists(path):
        raise SystemExit("archive.path 不存在：%r" % path)
    sid, sess, hits, total = None, set(), [], 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.rstrip("\n")
            m = marker.match(s) if marker else None
            if m:
                sid = m.group(1)
                continue
            if term in s:
                total += 1
                sess.add(sid)
                if len(hits) < show * 4:
                    i = s.find(term)
                    a, b = max(0, i - 90), min(len(s), i + len(term) + 90)
                    hits.append((sid, s[a:b]))
    print("证据：%d 处，涉及 %d 段" % (total, len(sess)))
    if total == 0:
        print("档案里没有 -> 这个假设是错的，不要写进知识库")
        return 1
    for sid, frag in hits[:show]:
        print("\n[%s]\n  %s" % ((sid or "?")[:8], frag))
    return 0


def _marks(cfg, text):
    a = cfg.get("archive") or {}
    lo = [w for w in (a.get("lesson_words") or DEFAULT_LESSON) if w in text]
    ar = [w for w in (a.get("artifact_words") or DEFAULT_ARTIFACT) if w in text]
    return lo, ar


def markers(cfg, top=40):
    _, store = load(cfg)
    rows = []
    for d in store.values():
        text = d["title"] + "\n" + d["body"]
        lo, ar = _marks(cfg, text)
        if lo or ar:
            rows.append((len(lo) + len(ar), len(lo), len(ar), d))
    rows.sort(key=lambda r: -r[0])
    print("知识库 %d 条，带经验标记 %d 条（两类都有 %d 条）\n"
          % (len(store), len(rows), sum(1 for r in rows if r[1] and r[2])))
    print("%3s %3s %3s  %-9s %-10s %s" % ("合", "亏", "工", "类型", "ID", "标题"))
    print("-" * 92)
    for s, lo, ar, d in rows[:top]:
        print("%3d %3d %3d  %-9s %-10s %s" % (s, lo, ar, d["kind"][:9], d["id"][:10], d["title"][:44]))
    print("\n用 id 前 8 位去挖：cairn dig <id>")
    return rows


def _anchors(text, counts, stop, limit=14):
    seen, cand = set(), []
    for raw in ANCHOR.findall(text):
        raw = raw.strip(".-")
        if len(raw) < 4:
            continue
        low = raw.lower()
        if low in seen or low in stop:
            continue
        specific = (any(c in raw for c in "_.-")
                    or any(c.isdigit() for c in raw)
                    or any(c.isupper() for c in raw[1:])
                    or len(raw) >= 12)
        if not specific:
            continue
        seen.add(low)
        if counts.get(low, 0) >= 2:
            cand.append((len(raw), low))
    cand.sort(reverse=True)
    return [t for _, t in cand][:limit]


def _scan(cfg, terms, per_term=2, window=90):
    _, path, marker = _acfg(cfg)
    terms = list({t.lower() for t in terms})
    hits = {t: [] for t in terms}
    sess = {t: set() for t in terms}
    total = collections.Counter()
    cur = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.rstrip("\n")
            m = marker.match(s) if marker else None
            if m:
                cur = m.group(1)
                continue
            low = s.lower()
            for t in terms:
                if t in low:
                    total[t] += 1
                    sess[t].add(cur)
                    if len(hits[t]) < per_term:
                        i = low.find(t)
                        a, b = max(0, i - window), min(len(s), i + len(t) + window)
                        hits[t].append((cur, s[a:b]))
    return total, sess, hits


def dig(cfg, sel, top=6, show=2):
    _, store = load(cfg)
    cands = [d for d in store.values() if d["id"].startswith(sel)]
    if not cands:
        sl = sel.lower()
        cands = [d for d in store.values() if sl in (d["title"] + d["body"]).lower()]
    if not cands:
        raise SystemExit("没有匹配的条目：%s" % sel)
    d = cands[0]
    text = d["title"] + "\n" + d["body"]
    lo, ar = _marks(cfg, text)
    counts = _load_counts(cfg)
    stop = _stop(cfg)
    cand = _anchors(text, counts, stop)
    print("条目：%s" % d["title"])
    print("类型：%s   ID：%s" % (d["kind"], d["id"]))
    print("经验标记：踩坑 %s" % ("、".join(lo) if lo else "无"))
    print("          工程 %s" % ("、".join(ar) if ar else "无"))
    if not cand:
        print("\n这条没有任何能在档案里追的标识符 —— 结论无法回溯，考虑补具体名字。")
        return 1
    total, sess, hits = _scan(cfg, cand, per_term=show)
    anchors = sorted([t for t in cand if total[t] >= 2], key=lambda t: (len(sess[t]), -total[t]))[:top]
    print("锚点（按定位精度排序：涉及片段越少越精准）：%s\n" % ("、".join(anchors) or "无"))
    if not anchors:
        print("所有候选锚点要么不出现、要么铺得太散 —— 追不到具体事故。")
        return 1
    grand = sum(total[t] for t in anchors)
    print("档案命中合计 %d 处，涉及 %d 段\n"
          % (grand, len(set().union(*[sess[t] for t in anchors]))))
    for a in anchors:
        print("[%s]  %d 处 / %d 段" % (a, total[a], len(sess[a])))
        for sid, frag in hits[a]:
            print("   %s  %s" % ((sid or "?")[:8], frag.replace("\n", " ")[:180]))
    print()
    if grand == 0:
        print("结论：档案里没有任何支撑 —— 要么发生在本档案之外，要么这条是没落地的推断。")
        return 1
    print("结论：有档案支撑，可以往下挖原始记录（命令、版本、报错原文）。")
    return 0
