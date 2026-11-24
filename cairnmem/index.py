"""建索引：文档 -> 倒排表 + idf。

索引和正文分开存：index.json 只有倒排和 idf，store.json 有全文。
两者都是**派生品**，随时可以从材料重建 —— 所以它们丢了不算损失，材料丢了才算。
"""
import json
import math
import os

from .sources import load_all
from .text import tokenize


def workdir(cfg):
    d = os.path.expanduser(cfg.get("workdir") or os.path.join(".", ".cairn"))
    os.makedirs(d, exist_ok=True)
    return d


def paths(cfg):
    d = workdir(cfg)
    return (os.path.join(d, "index.json"), os.path.join(d, "store.json"))


def build(cfg, quiet=False):
    docs = load_all(cfg.get("sources"))
    store, post, df = {}, {}, {}
    for d in docs:
        text = (d["title"] + " " + d["body"]).strip()
        tf = {}
        for t in tokenize(text):
            tf[t] = tf.get(t, 0) + 1
        d["_title_toks"] = sorted(set(tokenize(d["title"])))
        store[d["id"]] = d
        for t, c in tf.items():
            post.setdefault(t, {})[d["id"]] = c
            df[t] = df.get(t, 0) + 1

    N = len(docs)
    idf = {t: math.log((1.0 + N) / (1.0 + c)) + 1.0 for t, c in df.items()}
    ipath, spath = paths(cfg)
    with open(ipath, "w", encoding="utf-8") as f:
        json.dump({"N": N, "idf": idf, "post": post}, f, ensure_ascii=False)
    with open(spath, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False)

    if not quiet:
        kinds = {}
        for d in docs:
            kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
        print("索引完成：%d 条 %s，正文 %d 字符，token %d 种"
              % (N, kinds, sum(len(d["body"]) for d in docs), len(df)))
        print("  %s" % ipath)
        print("  %s" % spath)
    return {"N": N, "tokens": len(df)}


def load(cfg):
    ipath, spath = paths(cfg)
    if not os.path.exists(ipath) or not os.path.exists(spath):
        raise SystemExit("还没有索引，先跑: cairn index")
    with open(ipath, encoding="utf-8") as f:
        idx = json.load(f)
    with open(spath, encoding="utf-8") as f:
        store = json.load(f)
    return idx, store
