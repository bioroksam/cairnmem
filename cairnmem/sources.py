"""材料来源：把一个目录 / 一段文本 / 一份 jsonl 读成统一的记录。

统一记录字段（后面所有模块都只认这五个）：
    id, kind, title, body, path, when
"""
import json
import os
import re

_FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def parse_frontmatter(text):
    m = _FRONT.match(text)
    meta, body = {}, text
    if m:
        body = text[m.end():]
        for line in m.group(1).splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, body


def load_markdown_dir(path, kind="document"):
    out = []
    if not os.path.isdir(path):
        return out
    for fn in sorted(os.listdir(path)):
        if not fn.endswith(".md"):
            continue
        full = os.path.join(path, fn)
        with open(full, encoding="utf-8", errors="replace") as f:
            meta, body = parse_frontmatter(f.read())
        out.append({
            "id": meta.get("id") or fn[:-3],
            "kind": meta.get("kind") or kind,
            "title": meta.get("title") or fn[:-3],
            "body": body.strip(),
            "path": full,
            "when": (meta.get("created_at") or meta.get("date") or "")[:10],
        })
    return out


def load_jsonl(path, id_field="id", title_field="title", body_field="body", kind="doc"):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            body = str(o.get(body_field, ""))
            if not body:
                continue
            out.append({
                "id": str(o.get(id_field) or ("%s#%d" % (os.path.basename(path), i))),
                "kind": o.get("kind") or kind,
                "title": str(o.get(title_field) or body[:40]),
                "body": body,
                "path": path,
                "when": str(o.get("created_at") or o.get("when") or "")[:10],
            })
    return out


def load_all(sources):
    docs = []
    for s in sources or []:
        kind = s.get("kind")
        if kind == "markdown":
            docs += load_markdown_dir(os.path.expanduser(s["path"]), s.get("doc_kind", "document"))
        elif kind == "jsonl":
            docs += load_jsonl(os.path.expanduser(s["path"]),
                               s.get("id_field", "id"),
                               s.get("title_field", "title"),
                               s.get("body_field", "body"),
                               s.get("doc_kind", "doc"))
        else:
            raise ValueError("未知来源类型: %r" % kind)
    return docs
