"""命令行入口。"""
import argparse
import json
import os
import sys

from . import __version__, archive as arch, index, lint as lintmod, search

TEMPLATE = {
    "workdir": "~/.cairn",
    "sources": [
        {"kind": "markdown", "path": "~/notes", "doc_kind": "note"}
    ],
    "archive": {
        "path": "~/corpus/cleaned.txt",
        "marker_regex": None,
        "stopwords": [
            "data/stopwords-zh.txt",
            "data/stopwords-en.txt"
        ]
    },
    "scopes": {
        "notes": ["TODO", "idea"]
    }
}


def load_cfg(path):
    p = os.path.expanduser(path)
    if not os.path.exists(p):
        raise SystemExit("找不到配置 %s —— 先跑 cairn init 生成一份。" % p)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def cmd_init(a):
    p = os.path.expanduser(a.path)
    if os.path.exists(p) and not a.force:
        raise SystemExit("%s 已存在（要覆盖加 --force）" % p)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(TEMPLATE, f, ensure_ascii=False, indent=2)
    print("已写出配置模板：%s" % p)
    print("改完 sources / archive.path 后跑：cairn index")


def build_parser():
    p = argparse.ArgumentParser(prog="cairn", description="可验证的记忆层：索引、体检、档案")
    p.add_argument("-c", "--config", default="cairn.json", help="配置文件路径（默认 cairn.json）")
    p.add_argument("-V", "--version", action="version", version="cairnmem %s" % __version__)
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("init", help="生成配置模板")
    s.add_argument("--path", default="cairn.json")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("index", help="重建索引")
    s.set_defaults(func=lambda a, c: index.build(c))

    s = sub.add_parser("find", help="关键词找全文")
    s.add_argument("query", nargs="+")
    s.add_argument("-k", type=int, default=6)
    s.set_defaults(func=lambda a, c: search.find(c, " ".join(a.query), a.k))

    s = sub.add_parser("get", help="按 id 打全文")
    s.add_argument("id")
    s.set_defaults(func=lambda a, c: search.get(c, a.id))

    s = sub.add_parser("list", help="列全部条目")
    s.add_argument("-n", type=int, default=0)
    s.set_defaults(func=lambda a, c: search.listing(c, a.n or None))

    s = sub.add_parser("lint", help="体检：无锚点/外部来源/死路径/标题截断/日期/同族")
    s.add_argument("--scope", default=None)
    s.add_argument("--kind", default=None)
    s.add_argument("--show", type=int, default=6)
    s.set_defaults(func=lambda a, c: lintmod.lint(c, a.scope, a.kind, a.show))

    s = sub.add_parser("archive-build", help="建档案词频")
    s.set_defaults(func=lambda a, c: arch.build(c))

    s = sub.add_parser("gap", help="档案有 / 知识库无 的缺口队列")
    s.add_argument("--min", type=int, default=20)
    s.add_argument("--top", type=int, default=60)
    s.add_argument("--kind", default="cjk", choices=["cjk", "lat", "all"])
    s.set_defaults(func=lambda a, c: arch.gap(c, a.min, a.top, a.kind))

    s = sub.add_parser("verify", help="回档案验证某个词")
    s.add_argument("term")
    s.add_argument("--show", type=int, default=3)
    s.set_defaults(func=lambda a, c: sys.exit(arch.verify(c, a.term, a.show)))

    s = sub.add_parser("markers", help="哪些条目值得回档案挖")
    s.add_argument("--top", type=int, default=40)
    s.set_defaults(func=lambda a, c: arch.markers(c, a.top))

    s = sub.add_parser("dig", help="顺着一条结论回档案挖原始记录")
    s.add_argument("sel")
    s.add_argument("--top", type=int, default=6)
    s.add_argument("--show", type=int, default=2)
    s.set_defaults(func=lambda a, c: sys.exit(arch.dig(c, a.sel, a.top, a.show)))
    return p


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    p = build_parser()
    a = p.parse_args(argv)
    if not getattr(a, "func", None):
        p.print_help()
        return 0
    cfg = load_cfg(a.config)
    r = a.func(a, cfg)
    return r if isinstance(r, int) else 0
