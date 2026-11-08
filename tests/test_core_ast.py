"""R03: the self-hosted binary parses and emits C++ from an AST."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "bootstrap" / "omnissiah_selfhost.omn"


@unittest.skipUnless(shutil.which("g++"), "g++ required for native compiler")
class CoreASTTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="omnissiah-r03-")
        cls.dir = Path(cls.tmp.name)
        cls.native = cls.dir / "omnic"
        result = subprocess.run(
            [sys.executable, str(ROOT / "omnissiah.py"), "build", str(BOOTSTRAP),
             "-o", str(cls.native), "--optimize=-O0"],
            text=True, capture_output=True,
        )
        if result.returncode:
            raise AssertionError(f"Cannot bootstrap compiler: {result.stderr}")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def invoke(self, action, source, *args):
        return subprocess.run([str(self.native), action, str(source), *args],
                              text=True, capture_output=True)

    def temp_source(self, source):
        path = self.dir / f"input_{len(list(self.dir.glob('input_*.omn')))}.omn"
        path.write_text(source, encoding="utf-8")
        return path

    def core(self, body, *, ritual="ВО_ИМЯ_ОМНИССИИ;\nОСВЯТИТЬ процессор;\n"):
        return self.temp_source(ritual + body + "\nДА_БУДЕТ_ВОЛЯ_МАШИНЫ;\n")

    def test_ast_is_structured_json(self):
        r = self.invoke("ast", ROOT / "examples" / "core_syntax.omn")
        self.assertEqual(r.returncode, 0, r.stderr)
        node = json.loads(r.stdout)
        self.assertEqual(node["kind"], "Program")
        kinds = {x["kind"] for x in node["children"]}
        self.assertTrue({"Ritual", "Struct", "Function"}.issubset(kinds))
        main = next(x for x in node["children"] if x["value"] == "главная")
        self.assertEqual(main["kind"], "Function")
        self.assertTrue(any(x["kind"] == "For" for x in main["children"][-1]["children"]))
        self.assertGreater(main["line"], 1)

    def test_core_compiler_can_run_genuine_generated_cpp(self):
        src = ROOT / "examples" / "core_syntax.omn"
        generated = self.dir / "generated.cpp"
        result = self.invoke("core-emit", src, "-o", str(generated))
        self.assertEqual(result.returncode, 0, result.stderr)
        cpp = generated.read_text(encoding="utf-8")
        self.assertIn('int main(', cpp)
        self.assertIn('struct Relic', cpp)
        self.assertIn('for (int i = 0;', cpp)
        self.assertNotIn('ВО_ИМЯ_ОМНИССИИ;', cpp)
        binary = self.dir / "core_syntax"
        build = subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-pedantic",
                                str(generated), "-o", str(binary)], text=True, capture_output=True)
        self.assertEqual(build.returncode, 0, build.stderr)
        run = subprocess.run([str(binary)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout, "R03 core: 10\n")

    def test_core_and_legacy_execution_match(self):
        for filename in ("core_syntax.omn", "hello.omn"):
            with self.subTest(filename=filename):
                path = ROOT / "examples" / filename
                native_core = self.invoke("core-run", path, "--optimize", "-O0")
                native_legacy = self.invoke("run", path, "--optimize", "-O0")
                self.assertEqual(native_core.returncode, 0, native_core.stderr)
                self.assertEqual(native_legacy.returncode, 0, native_legacy.stderr)
                self.assertEqual(native_core.stdout, native_legacy.stdout)

    def test_expression_associativity_and_literals(self):
        source = self.core('''
ЛИТАНИЯ главная() {
    ЦЕЛОЕ a = 3, b = 4;
    a = b = 5;
    a = -a + 2 * b;
    a = (a > 0) ? a : 0;
    ВЕРНУТЬ (a == 5) ? 0 : 1;
}''')
        result = self.invoke("ast", source)
        self.assertEqual(result.returncode, 0, result.stderr)
        tree = json.loads(result.stdout)
        assignments = tree["children"][-2]["children"][-1]["children"]
        self.assertEqual(assignments[1]["children"][0]["value"], "=")
        run = self.invoke("core-run", source, "--optimize", "-O0")
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_nested_calls_members_and_boolean_logic(self):
        source = self.core('''
ВОССЛАВИТЬ машинный_дух;
СТРУКТУРА Box { ПУБЛИЧНО: ЦЕЛОЕ value; ЦЕЛОЕ read() { ВЕРНУТЬ value; } };
ЛИТАНИЯ главная() {
    СТРОКА text = "ok";
    ЦЕЛОЕ a = 2;
    ЕСЛИ_ВОЛЯ_ОМНИССИИ ((a == 2) && ИСТИНА) { МОЛИТВА(text); }
    ВЕРНУТЬ 0;
}''')
        run = self.invoke("core-run", source, "--optimize", "-O0")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout, "ok\n")

    def test_strict_grammar_reports_missing_semicolon(self):
        source = self.core('ЛИТАНИЯ главная() { ЦЕЛОЕ x = 12 ВЕРНУТЬ x; }')
        result = self.invoke("ast", source)
        self.assertEqual(result.returncode, 2)
        self.assertIn('OMN111', result.stderr)
        self.assertRegex(result.stderr, r':\d+:\d+: error OMN111:')

    def test_strict_grammar_rejects_unclosed_block(self):
        source = self.temp_source('ЛИТАНИЯ главная() { ВЕРНУТЬ 0;')
        result = self.invoke("ast", source, "--dark-age")
        self.assertEqual(result.returncode, 2)
        self.assertIn('OMN115', result.stderr)

    def test_core_rejects_unsupported_preprocessor_directive(self):
        source = self.temp_source('#define RETURN_ZERO 0\n' +
            'ВО_ИМЯ_ОМНИССИИ; ОСВЯТИТЬ процессор; '
            'ЛИТАНИЯ главная() { ВЕРНУТЬ RETURN_ZERO; } ДА_БУДЕТ_ВОЛЯ_МАШИНЫ;')
        result = self.invoke("core-emit", source)
        self.assertEqual(result.returncode, 2)
        self.assertIn('OMN116', result.stderr)

    def test_ast_output_file(self):
        path = self.dir / "core.ast.json"
        r = self.invoke("ast", ROOT / "examples" / "hello.omn", "-o", str(path))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(path.read_text())["kind"], "Program")


if __name__ == "__main__":
    unittest.main()
