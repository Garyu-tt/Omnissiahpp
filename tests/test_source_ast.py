"""R04: self-hosted, lossless structural syntax tree and AST bootstrap."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = ROOT / "bootstrap" / "omnissiah_selfhost.omn"


@unittest.skipUnless(shutil.which("g++"), "g++ required for native self-hosting")
class SourceASTTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="omnissiah-r04-")
        cls.work = Path(cls.tmp.name)
        cls.compiler = cls.work / "omnic-r04"
        result = subprocess.run([
            sys.executable, str(ROOT / "omnissiah.py"), "build", str(SELF),
            "-o", str(cls.compiler), "--optimize=-O0"
        ], text=True, capture_output=True)
        if result.returncode:
            raise AssertionError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def invoke(self, command, src, *args):
        return subprocess.run([str(self.compiler), command, str(src), *args],
                              capture_output=True, text=True)

    def source(self, text):
        path = self.work / f"source-{len(list(self.work.glob('source-*.omn')))}.omn"
        path.write_text(text, encoding="utf-8")
        return path

    @staticmethod
    def walk(tree):
        yield tree
        for child in tree["children"]:
            yield from SourceASTTests.walk(child)

    def test_native_compiler_parses_itself(self):
        result = self.invoke("source-ast", SELF)
        self.assertEqual(result.returncode, 0, result.stderr)
        tree = json.loads(result.stdout)
        self.assertEqual(tree["kind"], "TranslationUnit")
        self.assertEqual((tree["start"], tree["end"]), (0, SELF.stat().st_size))
        nodes = list(self.walk(tree))
        self.assertGreater(len(nodes), 3000)
        self.assertTrue(any(n["kind"] == "Group" and n["value"] == "{" for n in nodes))
        self.assertTrue(any(n["kind"] == "directive" and "#include" in n["value"] for n in nodes))
        self.assertTrue(any(n["kind"] == "string" and "R\"OMNIRUNTIME" in n["value"] for n in nodes))

    def test_r05_declaration_roles_preserve_lossless_source(self):
        src = self.source('''namespace shrine {
struct Relic { int charge; };
int bless(int n) { return n + 1; }
}
''')
        result = self.invoke("source-ast", src, "--dark-age")
        self.assertEqual(result.returncode, 0, result.stderr)
        tree = json.loads(result.stdout)
        roles = [n.get("role") for n in self.walk(tree) if n["kind"] == "Group"]
        self.assertIn("NamespaceBody", roles)
        self.assertIn("TypeBody", roles)
        self.assertIn("CallableOrControlBody", roles)
        self.assertEqual(self.invoke("source-emit", src, "--dark-age").returncode, 0)

    def test_source_emitter_matches_legacy_byte_for_byte(self):
        for source in [SELF, *(ROOT / "examples").glob("*.omn")]:
            with self.subTest(source=source.name):
                old = self.invoke("emit", source)
                new = self.invoke("source-emit", source)
                self.assertEqual(new.returncode, old.returncode, new.stderr)
                self.assertEqual(new.stderr, old.stderr)
                self.assertEqual(old.stdout, new.stdout)

    def test_ast_preserves_utf8_string_comments_and_macro_braces(self):
        src = self.source('''#define CURLY "{ not a brace }"
ВО_ИМЯ_ОМНИССИИ;
ОСВЯТИТЬ процессор;
ЛИТАНИЯ главная() {
    const char* t = u8R"tag(())]} ПРИВЕТ )tag";
    // [} ignore comments
    ВЕРНУТЬ 0;
}
ДА_БУДЕТ_ВОЛЯ_МАШИНЫ;
''')
        result = self.invoke("source-ast", src)
        self.assertEqual(result.returncode, 0, result.stderr)
        obj = json.loads(result.stdout)
        self.assertEqual(obj["end"], src.stat().st_size)
        nodes = list(self.walk(obj))
        self.assertTrue(any(n["kind"] == "comment" and "[}" in n["value"] for n in nodes))
        self.assertTrue(any(n["kind"] == "string" and "ПРИВЕТ" in n["value"] for n in nodes))
        self.assertEqual(self.invoke("source-emit", src).returncode, 0)

    def test_detect_unclosed_delimiter_with_source_position(self):
        src = self.source("int main() { int x = 2;\n")
        res = self.invoke("source-ast", src, "--dark-age")
        self.assertEqual(res.returncode, 2)
        self.assertIn("OMN130", res.stderr)
        self.assertRegex(res.stderr, r":1:\d+: error OMN130:")

    def test_detect_wrong_closing_delimiter(self):
        src = self.source("int main() { int value[2] = {1,2]; }\n")
        res = self.invoke("source-emit", src, "--dark-age")
        self.assertEqual(res.returncode, 2)
        self.assertIn("OMN131", res.stderr)

    def test_limit_nesting_to_prevent_stack_exhaustion(self):
        src = self.source("(" * 520 + "0" + ")" * 520)
        res = self.invoke("source-ast", src, "--dark-age")
        self.assertEqual(res.returncode, 2)
        self.assertIn("OMN132", res.stderr)

    def test_new_backend_executes_compiled_program(self):
        old = self.invoke("run", ROOT / "examples" / "hello.omn", "--optimize", "-O0")
        new = self.invoke("source-run", ROOT / "examples" / "hello.omn", "--optimize", "-O0")
        self.assertEqual(old.returncode, 0, old.stderr)
        self.assertEqual(new.returncode, old.returncode, new.stderr)
        self.assertEqual(new.stdout, old.stdout)


if __name__ == "__main__":
    unittest.main()
