"""检索：碎片 -> 全文。

打分 = sum over 命中 token 的 (1+log(tf)) * idf
      * 标题命中 3x
      * 纯数字 token 2.5x（让「39 页」这类查询不被泛词淹没）
再加一项稀有词加成：查询里 idf 最高的 3 个 token，
命中标题 +6*idf，命中正文 +1.5*idf。
"""
import math

from .index import load
from .text import tokenize


def snippet(body, toks, width=70):
    best = -1
    for t in toks:
        if len(t) < 2:
            continue
        i = body.find(t)
        if i >= 0 and (best < 0 or i < best):
            best = i
    if best < 0:
        return body[:width * 2].replace("\n", " ")
    a, b = max(0, best - width), min(len(body), best + width)
    return ("…" if a else "") + body[a:b].replace("\n", " ") + ("…" if b < len(body) else "")


def find(cfg, query, k=6):
    idx, store = load(cfg)
    qterms = tokenize(query)
    if not qterms:
        print("查询里没有可用 token")
        return []
    scored = {}
    for t in qterms:
        is_num = t.isdigit()
        for did, c in idx["post"].get(t, {}).items():
            w = (1.0 + math.log(c)) * idx["idf"].get(t, 1.0)
            if t in set(store[did].get("_title_toks", [])):
                w *= 3.0
            if is_num:
                w *= 2.5
            scored[did] = scored.get(did, 0.0) + w
    if not scored:
        print("没有命中")
        return []

    rare = sorted(set(qterms), key=lambda t: -idx["idf"].get(t, 0.0))[:3]
    for did in list(scored):
        d = store[did]
        tt = set(d.get("_title_toks", []))
        for t in rare:
            if len(t) < 2 and not t.isdigit():
                continue
            if t in tt:
                scored[did] += idx["idf"].get(t, 0.0) * 6.0
            elif t in d["body"]:
                scored[did] += idx["idf"].get(t, 0.0) * 1.5

    out = []
    for did, sc in sorted(scored.items(), key=lambda kv: -kv[1])[:k]:
        d = store[did]
        out.append((did, sc, d))
        print("[%s] %.2f  %s" % (d["kind"], sc, d["title"][:70]))
        print("      %s  %s" % (d["when"], did))
        print("      %s" % snippet(d["body"], qterms))
    return out


def get(cfg, did):
    _, store = load(cfg)
    hit = None
    for k, v in store.items():
        if k == did or k.startswith(did):
            hit = v
            break
    if not hit:
        print("没有这个 id: %s" % did)
        return None
    print("标题：%s" % hit["title"])
    print("类型：%s   时间：%s" % (hit["kind"], hit["when"]))
    print("来源：%s" % hit["path"])
    print("-" * 60)
    print(hit["body"])
    return hit


def listing(cfg, limit=None):
    _, store = load(cfg)
    rows = sorted(store.items(), key=lambda kv: kv[1].get("when", ""), reverse=True)
    if limit:
        rows = rows[:limit]
    for did, d in rows:
        print("%-10s %-8s %s" % (d.get("when", ""), d["kind"][:8], d["title"][:64]))
    print("共 %d 条" % len(store))
