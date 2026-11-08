"""R06: optional pseudo-High Gothic and historical Gothic-script adapters."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gothic_dialects import normalize_identifier, write_gothic
from omnissiah import OmnissiahError, transpile

LATIN = (ROOT / "examples/high_gothic.omn").read_text(encoding="utf-8")
GLYPHS = (ROOT / "examples/gothic_script.omn").read_text(encoding="utf-8")


class DialectTests(unittest.TestCase):
    def test_high_gothic_generates_cpp(self):
        cpp = transpile(LATIN, "example.omn", dialect="high-gothic")
        self.assertIn("int main()", cpp)
        self.assertIn('omni::prayer("Ave Omnissiah! ", numerum);', cpp)
        self.assertIn("return 0;", cpp)
        self.assertEqual(cpp.split('#line 1 "example.omn"\n', 1)[1].count("\n"), LATIN.count("\n"))

    def test_gothic_script_generates_cpp(self):
        cpp = transpile(GLYPHS, "glyph.omn", dialect="gothic")
        self.assertIn("int main()", cpp)
        self.assertIn("int numerum = 40;", cpp)
        self.assertIn('omni::prayer("Ave Omnissiah! ", numerum);', cpp)
        self.assertEqual(cpp.split('#line 1 "glyph.omn"\n', 1)[1].count("\n"), GLYPHS.count("\n"))

    def test_ru_is_unchanged_and_rejects_foreign_rites(self):
        with self.assertRaises(OmnissiahError) as error:
            transpile(LATIN)
        self.assertEqual(error.exception.code, "OMN001")

    def test_rituals_remain_mandatory_in_both_dialects(self):
        for name, original in (("high-gothic", LATIN), ("gothic", GLYPHS)):
            with self.subTest(dialect=name):
                first_line = original.splitlines(keepends=True)[0]
                with self.assertRaises(OmnissiahError) as error:
                    transpile(original[len(first_line):], dialect=name)
                self.assertEqual(error.exception.code, "OMN001")
                no_io = original.replace("LAUDA spiritum_machinae;\n", "") if name == "high-gothic" else (
                    original.replace(write_gothic("LAUDA") + " " + write_gothic("SPIRITUM_MACHINAE") + ";\n", "")
                )
                with self.assertRaises(OmnissiahError) as error:
                    transpile(no_io, dialect=name)
                self.assertEqual(error.exception.code, "OMN021")

    def test_comments_strings_raw_strings_directives_are_untouched(self):
        prelude = '#define X "ORATIO"\n'
        latin = prelude + LATIN.replace(
            'NUMERUS numerum = 7;',
            'NUMERUS numerum = 7; // ORATIO\n'
            '    auto raw = R"tag(ORATIO FINIS_RITUALIS)tag";\n'
            '    auto literal = "ORATIO CONSECRA";'
        )
        cpp = transpile(latin, dialect="high-gothic")
        self.assertIn('#define X "ORATIO"', cpp)
        self.assertIn('// ORATIO', cpp)
        self.assertIn('R"tag(ORATIO FINIS_RITUALIS)tag"', cpp)
        self.assertIn('"ORATIO CONSECRA"', cpp)

    def test_gothic_custom_identifiers_transliterate(self):
        ident = write_gothic("ferrum")
        src = GLYPHS.replace(write_gothic("numerum"), ident)
        cpp = transpile(src, dialect="gothic")
        self.assertIn("int ferrum = 40;", cpp)
        self.assertIn(", ferrum);", cpp)

    def test_aliases_case_insensitive(self):
        self.assertEqual(normalize_identifier("oratio", "high-gothic"), "МОЛИТВА")
        self.assertEqual(normalize_identifier(write_gothic("consecra"), "gothic"), "ОСВЯТИТЬ")
        self.assertEqual(normalize_identifier("ORATIO", "ru"), "ORATIO")

    def test_unsupported_dialect_explicit_error(self):
        with self.assertRaises(OmnissiahError) as error:
            transpile(LATIN, dialect="unknown")
        self.assertEqual(error.exception.code, "OMN050")

    def test_python_cli_check_emit(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, sample, dialect in (
                ("latin", "high_gothic.omn", "high-gothic"),
                ("glyph", "gothic_script.omn", "gothic"),
            ):
                with self.subTest(name=name):
                    output = Path(tmp) / (name + ".cpp")
                    result = subprocess.run(
                        [sys.executable, str(ROOT / "omnissiah.py"), "emit",
                         str(ROOT / "examples" / sample), "--dialect", dialect,
                         "-o", str(output)],
                        capture_output=True, text=True
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("int main()", output.read_text(encoding="utf-8"))


@unittest.skipUnless(shutil.which("g++"), "requires g++")
class NativeDialectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.temp.name) / "omnic"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "omnissiah.py"), "build",
             str(ROOT / "bootstrap/omnissiah_selfhost.omn"),
             "-o", str(cls.binary), "--optimize=-O0"],
            capture_output=True, text=True
        )
        if proc.returncode:
            cls.temp.cleanup()
            raise AssertionError(proc.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_native_gothic_binary_and_python_equivalence(self):
        for name, dialect, message in (
            ("high_gothic.omn", "high-gothic", "Ave Omnissiah! 7"),
            ("gothic_script.omn", "gothic", "Ave Omnissiah! 40"),
        ):
            with self.subTest(name=name):
                sample = str(ROOT / "examples" / name)
                native = subprocess.run(
                    [str(self.binary), "run", sample, "--dialect", dialect,
                     "--optimize", "-O0"],
                    capture_output=True, text=True
                )
                self.assertEqual(native.returncode, 0, native.stderr)
                self.assertIn(message, native.stdout)
                native_cpp = subprocess.run(
                    [str(self.binary), "emit", sample, "--dialect", dialect],
                    capture_output=True, text=True
                )
                python_cpp = transpile(
                    (ROOT / "examples" / name).read_text(encoding="utf-8"),
                    sample, dialect=dialect
                )
                self.assertEqual(native_cpp.returncode, 0, native_cpp.stderr)
                self.assertEqual(native_cpp.stdout, python_cpp)

    def test_source_ast_remains_lossless_for_gothic_unicode(self):
        sample = str(ROOT / "examples/gothic_script.omn")
        output = subprocess.run(
            [str(self.binary), "source-ast", sample, "--dialect", "gothic"],
            capture_output=True, text=True
        )
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertIn("𐌹𐌽_", output.stdout)

    def test_native_source_emit_with_glyphs(self):
        sample = str(ROOT / "examples/gothic_script.omn")
        out = subprocess.run(
            [str(self.binary), "source-emit", sample, "--dialect", "gothic"],
            capture_output=True, text=True
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("int main()", out.stdout)


if __name__ == "__main__":
    unittest.main()
