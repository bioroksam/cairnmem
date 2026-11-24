"""体检：找出「以后查不到账」的条目。

五项，各自对应一种具体的失效：
    无锚点        —— 结论没法回溯到原始材料
    外部来源不全  —— 引了 URL 却没有抓取日期 / 快照
    死路径        —— 正文里的绝对路径已不存在
    标题被截断    —— title 是 body 的硬截断（生成侧缺陷）
    日期不符      —— 正文写的日期 != 条目自身的日期
外加一项：标题同族（同一项目多篇多版本）。

工具只负责把问题算出来。**修不修、怎么修，由写那条的人决定。**
"""
import os
import re

from .index import load

ANCHOR = re.compile(
    r"[A-Za-z]:[\\/]"
    r"|[\w\-]+\.(?:py|mjs|js|ts|md|json|csv|docx|pdf|ps1|bat|sh|jar|txt|yaml|yml|db|zip|log|toml)"
    r"|\b\d+\.\d+\.\d+\b"
    r"|\b[A-Z][a-zA-Z]*(?:Error|Exception)\b"
    r"|\bERR_[A-Z_]+\b"
    r"|\b[a-z][a-z0-9]*\.[a-z][a-z0-9]*\.[a-z][a-z0-9]*\b")

ABSPATH = re.compile(r'(?<![A-Za-z])[A-Za-z]:[\\/][^\s，。、；：！？（）"\'<>|]*')
SRCLINE = re.compile(r"来源[:：]\s*https?://")
CAPTURED = re.compile(r"抓取\s*20\d\d-\d\d-\d\d")
SNAPSHOT = re.compile(r"快照")


def _in_scope(d, scope, scopes):
    if not scope:
        return True
    words = scopes.get(scope) or [scope]
    t = d["title"] + " " + d["body"]
    return any(w in t for w in words)


def lint(cfg, scope=None, kind=None, show=6):
    _, store = load(cfg)
    scopes = cfg.get("scopes") or {}
    rows = [d for d in store.values()
            if (not kind or d["kind"] == kind) and _in_scope(d, scope, scopes)]
    if not rows:
        print("范围内没有条目（scope=%s）" % scope)
        return {}

    label = "/".join((scopes.get(scope) or [scope])[:3]) if scope else "全部"
    print("体检范围：%s —— %d 条（%s）" % (
        label, len(rows),
        " / ".join("%s %d" % (k, sum(1 for d in rows if d["kind"] == k))
                   for k in sorted({d["kind"] for d in rows}))))

    no_anchor, dead, trunc, badwhen, badsrc = [], [], [], [], []
    for d in rows:
        body = d["body"]
        if not ANCHOR.search(body):
            no_anchor.append(d)
        if SRCLINE.search(body) and not (CAPTURED.search(body) and SNAPSHOT.search(body)):
            badsrc.append(d)
        dp = []
        for p in set(ABSPATH.findall(body)):
            p = p.replace("\\\\", "\\").replace("/", "\\").rstrip("." + chr(96) + "\\")
            if len(p) <= 3 or os.path.exists(p):
                continue
            cut = p.rfind("\\")
            if cut <= 2:
                continue
            parent, base = p[:cut], p[cut + 1:]
            # 只报「父目录在、文件名带后缀、文件不在」；父目录都不在的多半是正文截断
            if os.path.exists(parent) and "." in base and len(base) > 3:
                dp.append(p)
        if dp:
            dead.append((d, sorted(set(dp))))
        if len(d["title"]) >= 34 and body.startswith(d["title"]):
            trunc.append(d)
        ds = set(re.findall(r"20\d\d-\d\d-\d\d", body))
        if ds and d.get("when") and d["when"] not in ds:
            badwhen.append((d, sorted(ds)[:3]))

    def fam(s):
        return re.sub(r"[\s（(【\[：:].*", "", s)
    buckets = {}
    for d in rows:
        k = fam(d["title"])
        if len(k) >= 6:
            buckets.setdefault(k, []).append(d)
    dups = [(k, v) for k, v in buckets.items() if len(v) > 1]

    def head(title, desc, items):
        print("\n【%s】%d 条" % (title, len(items)))
        print("  " + desc)
        for d in items[:show]:
            print("  %-10s %-8s %s" % (d["id"][:8], d["kind"][:8], d["title"][:56]))
        if len(items) > show:
            print("  … 还有 %d 条" % (len(items) - show))

    head("无锚点", "正文没有任何可定位标识符（路径/文件名/版本号/报错串/包名）。以后只能信，不能验。", no_anchor)
    head("外部来源不全", "引了 http(s) 来源但缺「抓取 日期」或「快照 路径」。链接会烂，只留 URL 等于没留。", badsrc)
    head("标题被截断", "title 是 body 的硬截断、不带省略号（生成侧缺陷）。", trunc)

    print("\n【死路径】%d 条" % len(dead))
    if not dead:
        print("  没有")
    for d, ps in dead[:show]:
        print("  %-10s %s" % (d["id"][:8], d["title"][:40]))
        for p in ps[:3]:
            print("             x %s" % p)

    print("\n【日期不符】%d 条（正文日期 != 条目日期）" % len(badwhen))
    for d, ds in badwhen[:show]:
        print("  %-10s when=%-10s 正文提 %s  %s"
              % (d["id"][:8], d.get("when", ""), ",".join(ds), d["title"][:28]))

    print("\n【标题同族】%d 组（同一项目多篇多版本，合并前先认）" % len(dups))
    for k, v in sorted(dups, key=lambda kv: -len(kv[1]))[:show]:
        print("  %-20s %s" % (k, " / ".join(x["id"][:8] for x in v)))

    print("\n汇总：%d 条里 无锚点 %d、外部来源不全 %d、死路径 %d、标题截断 %d、日期不符 %d、标题同族 %d 组"
          % (len(rows), len(no_anchor), len(badsrc), len(dead), len(trunc), len(badwhen), len(dups)))
    return {"rows": len(rows), "no_anchor": len(no_anchor), "badsrc": len(badsrc),
            "dead": len(dead), "trunc": len(trunc), "badwhen": len(badwhen), "dups": len(dups)}
