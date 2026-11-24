"""标准库 unittest，不依赖 pytest。跑：python -m unittest discover -s tests"""
import json
import os
import shutil
import tempfile
import unittest

from cairnmem import archive, index, lint, search
from cairnmem.text import tokenize, tokenize_ref

SAMPLES = [
    "",
    "  ",
    "红石中继器续信号",
    "GregTech Leisure_1 的 gtlcore-1.2.3.2-fix3",
    "abc a 1.2.3 ERR_PNPM_NO_AGENT_SKILLS_DIR",
    "混合English中文 mixed 汉字ABC",
    "の日本語かな emoji🙂结尾",
    "A",
]


class TestTokenize(unittest.TestCase):
    def test_parity_with_reference(self):
        for s in SAMPLES:
            self.assertEqual(tokenize(s), tokenize_ref(s), msg=repr(s))

    def test_bigram(self):
        self.assertEqual(tokenize("红石"), ["红石"])
        self.assertEqual(tokenize("红石中继器"), ["红石", "石中", "中继", "继器"])

    def test_latin_min_len(self):
        self.assertEqual(tokenize("a bc"), ["bc"])

    def test_lowercase(self):
        self.assertEqual(tokenize("ABCdef"), ["abcdef"])


class Fixture(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cairn-test-")
        self.docs = os.path.join(self.dir, "docs")
        os.makedirs(self.docs)
        self.corpus = os.path.join(self.dir, "corpus.txt")
        with open(os.path.join(self.docs, "a.md"), "w", encoding="utf-8") as f:
            f.write("---\nid: a1\ntitle: 柴油机轨压控制\ncreated_at: 2026-11-20\n---\n"
                    "根因是传感器采样周期与控制器不匹配，曾导致轨压超调失败。\n"
                    "参数见 design/kp.json，构建流水线 build/build_all.sh\n")
        with open(os.path.join(self.docs, "b.md"), "w", encoding="utf-8") as f:
            f.write("---\nid: b2\ntitle: 红石中继器\ncreated_at: 2026-11-21\n---\n"
                    "中继器把信号续到 15 格。\n")
        with open(self.corpus, "w", encoding="utf-8") as f:
            f.write("\n".join([
                "session-11111111-1111-1111-1111-111111111111",
                "T-S 模糊 PI 的 kp.json 停在 design 目录下",
                "session-22222222-2222-2222-2222-222222222222",
                "中继器信号被比较器截断，根因是红石线强充能",
            ]))
        self.cfg = {
            "workdir": os.path.join(self.dir, ".cairn"),
            "sources": [{"kind": "markdown", "path": self.docs}],
            "archive": {"path": self.corpus,
                        "marker_regex": "^session-([0-9a-f\\-]{36})"},
            "scopes": {"thesis": ["轨压", "柴油机"], "redstone": ["红石", "中继器"]},
        }

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class TestIndexSearch(Fixture):
    def test_build_and_find(self):
        index.build(self.cfg, quiet=True)
        idx, store = index.load(self.cfg)
        self.assertEqual(len(store), 2)
        hits = search.find(self.cfg, "轨压 控制", 3)
        self.assertTrue(hits)
        self.assertEqual(hits[0][2]["id"], "a1")

    def test_get_by_prefix(self):
        index.build(self.cfg, quiet=True)
        doc = search.get(self.cfg, "a")
        self.assertIsNotNone(doc)
        self.assertEqual(doc["title"], "柴油机轨压控制")


class TestLint(Fixture):
    def test_detects_no_anchor_and_dead_path(self):
        with open(os.path.join(self.docs, "c.md"), "w", encoding="utf-8") as f:
            f.write("---\nid: c3\ntitle: 纯结论条目\ncreated_at: 2026-11-22\n---\n"
                    "回滚之后要重新装依赖，因为声明版本和实物版本会不一致。\n")
        with open(os.path.join(self.docs, "d.md"), "w", encoding="utf-8") as f:
            f.write("---\nid: d4\ntitle: 死路径条目\ncreated_at: 2026-11-22\n---\n"
                    "产物在 %s 这个位置。\n" % os.path.join(self.dir, "missing.pdf"))
        index.build(self.cfg, quiet=True)
        stats = lint.lint(self.cfg, scope=None, show=0)
        self.assertGreaterEqual(stats["no_anchor"], 1)
        self.assertGreaterEqual(stats["dead"], 1)


class TestArchive(Fixture):
    def test_gap_and_verify(self):
        index.build(self.cfg, quiet=True)
        archive.build(self.cfg)
        items = archive.gap(self.cfg, mins=1, top=50, kind="all", quiet=True)
        self.assertTrue(any(t == "强充" or t == "充能" for _, t, _ in items) or items)
        self.assertEqual(archive.verify(self.cfg, "比较器", show=0), 0)
        self.assertEqual(archive.verify(self.cfg, "不存在的词_zzz", show=0), 1)

    def test_markers_and_dig(self):
        index.build(self.cfg, quiet=True)
        archive.build(self.cfg)
        rows = archive.markers(self.cfg, top=10)
        self.assertTrue(rows)
        rc = archive.dig(self.cfg, "b2", top=3, show=1)
        self.assertIn(rc, (0, 1))


if __name__ == "__main__":
    unittest.main()
