"""Differential and three-generation bootstrap tests for native Omnissiah++."""
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnissiah import transpile, OmnissiahError  # noqa: E402

BOOTSTRAP = ROOT / "bootstrap" / "omnissiah_selfhost.omn"


@unittest.skipUnless(shutil.which("g++"), "g++ is required")
class SelfHostingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="omnissiah-native-tests-")
        cls.dir = Path(cls.temp.name)
        cls.compiler = cls.dir / "omnic"
        process = subprocess.run([
            sys.executable, str(ROOT / "omnissiah.py"), "build", str(BOOTSTRAP),
            "-o", str(cls.compiler), "--optimize=-O0",
        ], capture_output=True, text=True)
        if process.returncode:
            raise AssertionError(f"native bootstrap failed: {process.stderr}\n{process.stdout}")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def check_parity(self, source: str, name: str = "test.omn", dark_age: bool = False):
        path = self.dir / name
        path.write_text(source, encoding="utf-8")
        generated = self.dir / f"{name}.cpp"
        cmd = [str(self.compiler), "emit", str(path), "-o", str(generated)]
        if dark_age:
            cmd.append("--dark-age")
        native = subprocess.run(cmd, text=True, capture_output=True)
        try:
            expected = transpile(source, str(path.resolve()), dark_age=dark_age)
        except OmnissiahError as exc:
            self.assertEqual(native.returncode, 2, native.stdout + native.stderr)
            self.assertIn(f"error {exc.code}:", native.stderr)
        else:
            self.assertEqual(native.returncode, 0, native.stderr)
            self.assertEqual(generated.read_text(encoding="utf-8"), expected)

    def test_bootstrap_source_differential(self):
        self.check_parity(BOOTSTRAP.read_text(encoding="utf-8"), "compiler.omn")

    def test_examples_differential(self):
        for path in sorted((ROOT / "examples").glob("*.omn")):
            with self.subTest(path=path.name):
                self.check_parity(path.read_text(encoding="utf-8"), path.name)

    def test_lexer_literals_and_unicode(self):
        self.check_parity('''#define SOME_MACRO "ЛИТАНИЯ"
ВО_ИМЯ_ОМНИССИИ;
ОСВЯТИТЬ процессор;
ВОССЛАВИТЬ машинный_дух;
ЛИТАНИЯ главная() {
  // ЕСЛИ_ВОЛЯ_ОМНИССИИ and МОЛИТВА are protected here.
  auto raw = u8R"tag(МОЛИТВА(1) and \"quotes\")tag";
  auto message = "МОЛИТВА(2)";
  МОЛИТВА(message, raw);
  ВЕРНУТЬ 0;
}
ДА_БУДЕТ_ВОЛЯ_МАШИНЫ;
''', "literals.omn")

    def test_invalid_programs_differential(self):
        variants = [
            "ЛИТАНИЯ главная() { ВЕРНУТЬ 0; }",
            "ВО_ИМЯ_ОМНИССИИ; ЛИТАНИЯ главная(){ВЕРНУТЬ 0;} ДА_БУДЕТ_ВОЛЯ_МАШИНЫ;",
            "ВО_ИМЯ_ОМНИССИИ; ОСВЯТИТЬ процессор; ЛИТАНИЯ главная() { МОЛИТВА(1); } ДА_БУДЕТ_ВОЛЯ_МАШИНЫ;",
            "ВО_ИМЯ_ОМНИССИИ; ОСВЯТИТЬ процессор; ЛИТАНИЯ главная() { auto x = НОВОЕ ЦЕЛОЕ; } ДА_БУДЕТ_ВОЛЯ_МАШИНЫ;",
            "ВО_ИМЯ_ОМНИССИИ; ОСВЯТИТЬ монитор; ДА_БУДЕТ_ВОЛЯ_МАШИНЫ;",
            "ВО_ИМЯ_ОМНИССИИ; ОСВЯТИТЬ процессор; ЛИТАНИЯ главная() { ВЕРНУТЬ 0; }",
            "ВО_ИМЯ_ОМНИССИИ ОСВЯТИТЬ процессор; ДА_БУДЕТ_ВОЛЯ_МАШИНЫ;",
            "ВО_ИМЯ_ОМНИССИИ; ОСВЯТИТЬ процессор; ЛИТАНИЯ главная() { ОСВЯТИТЬ память; } ДА_БУДЕТ_ВОЛЯ_МАШИНЫ;",
            "/* unterminated",
            'R"tag(never closed',
        ]
        for i, src in enumerate(variants):
            with self.subTest(case=i):
                self.check_parity(src, f"bad{i}.omn")

    def test_dark_age_differential(self):
        self.check_parity('ЛИТАНИЯ главная(){ МОЛИТВА("Факт: 42"); ВЕРНУТЬ 0; }', "dark.omn", True)

    def test_core_duplicate_parameter_diagnostic(self):
        cases = [
            ("int sum(int value, int value) { return value; }", "value"),
            ("ЦЕЛОЕ sum(ЦЕЛОЕ число, ЦЕЛОЕ число) { ВЕРНУТЬ число; }", "число"),
        ]
        for i, (source, name) in enumerate(cases):
            with self.subTest(name=name):
                path = self.dir / f"duplicate-parameter-{i}.omn"
                path.write_text(source, encoding="utf-8")
                result = subprocess.run(
                    [str(self.compiler), "ast", str(path), "--dark-age"],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("OMN117", result.stderr)
                self.assertIn(name, result.stderr)

        valid = self.dir / "distinct-parameters.omn"
        valid.write_text("int sum(int first, int second) { return first + second; }",
                         encoding="utf-8")
        result = subprocess.run(
            [str(self.compiler), "ast", str(valid), "--dark-age"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"kind":"Function"', result.stdout)

    def test_core_duplicate_declarators(self):
        invalid = [
            "int main() { int x = 1, x = 2; return x; }",
            "ЦЕЛОЕ main() { ЦЕЛОЕ число = 1, число = 2; ВЕРНУТЬ число; }",
            "int x = 1, x = 2; int main() { return x; }",
            "int main() { for (int i = 0, i = 1; i < 3; ++i) {} return 0; }",
        ]
        for i, source in enumerate(invalid):
            with self.subTest(source=source):
                path = self.dir / f"duplicate-declarator-{i}.omn"
                path.write_text(source, encoding="utf-8")
                result = subprocess.run(
                    [str(self.compiler), "ast", str(path), "--dark-age"],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("OMN118", result.stderr)

        valid = [
            "int a = 1, b = 2; int main() { return a + b; }",
            "int main() { int x = 1; { int x = 2; } return x; }",
        ]
        for i, source in enumerate(valid):
            with self.subTest(valid=i):
                path = self.dir / f"distinct-declarator-{i}.omn"
                path.write_text(source, encoding="utf-8")
                result = subprocess.run(
                    [str(self.compiler), "ast", str(path), "--dark-age"],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_core_lexical_scope_redeclarations(self):
        invalid = [
            "int main() { int x = 1; int x = 2; return x; }",
            "ЦЕЛОЕ main() { ЦЕЛОЕ число = 1; ЦЕЛОЕ число = 2; ВЕРНУТЬ число; }",
            "int x = 1; int x = 2; int main() { return x; }",
            "int main() { for (int i = 0; i < 2; ++i) { int x = 0; int x = 1; } return 0; }",
        ]
        valid = [
            "int main() { int x = 1; { int x = 2; } return x; }",
            "int x = 1; int main() { int x = 2; return x; }",
            "int main() { for (int i = 0; i < 2; ++i) {} for (int i = 0; i < 2; ++i) {} return 0; }",
        ]
        for i, source in enumerate(invalid):
            with self.subTest(invalid=i):
                path = self.dir / f"scope-invalid-{i}.omn"
                path.write_text(source, encoding="utf-8")
                result = subprocess.run(
                    [str(self.compiler), "ast", str(path), "--dark-age"],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("OMN119", result.stderr)
        for i, source in enumerate(valid):
            with self.subTest(valid=i):
                path = self.dir / f"scope-valid-{i}.omn"
                path.write_text(source, encoding="utf-8")
                result = subprocess.run(
                    [str(self.compiler), "ast", str(path), "--dark-age"],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_real_three_generation_bootstrap(self):
        result = subprocess.run(["bash", str(ROOT / "scripts" / "bootstrap.sh"), str(self.dir / "stages")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"{result.stdout}\n{result.stderr}")
        cpp2 = self.dir / "stages" / "stage2.cpp"
        cpp3 = self.dir / "stages" / "stage3.cpp"
        cpp4 = self.dir / "stages" / "stage4.cpp"
        self.assertEqual(cpp2.read_bytes(), cpp3.read_bytes())
        self.assertEqual(cpp3.read_bytes(), cpp4.read_bytes())
        self.assertEqual(cpp2.read_bytes(), (self.dir / "stages" / "stage0.cpp").read_bytes())
        self.assertEqual(hashlib.sha256(cpp2.read_bytes()).digest(),
                         hashlib.sha256(cpp4.read_bytes()).digest())


if __name__ == "__main__":
    unittest.main()
