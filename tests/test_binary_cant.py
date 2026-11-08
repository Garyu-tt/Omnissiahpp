"""Binary Cant transport, compulsory liturgy and native/seed parity."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from binary_cant import BinaryCantError, decode_cant, encode_cant
from omnissiah import OmnissiahError, transpile

CANONICAL = (ROOT / "examples/binary_cant_source.omn").read_text(encoding="utf-8")
CANT = (ROOT / "examples/binary_cant.cant").read_text(encoding="utf-8")


class BinaryCantTests(unittest.TestCase):
    def assert_heresy(self, source, code, **kwargs):
        with self.assertRaises(OmnissiahError) as result:
            transpile(source, "cant.omnc", dialect="binary-cant", **kwargs)
        self.assertEqual(result.exception.code, code)

    def test_example_roundtrip_and_octet_only(self):
        self.assertEqual(decode_cant(CANT), CANONICAL)
        self.assertEqual(encode_cant(CANONICAL), CANT)
        self.assertTrue(set(CANT) <= set("01 \n"))

    def test_binary_cant_transpiles_prayer(self):
        cpp = transpile(CANT, "cant.omnc", dialect="binary-cant")
        self.assertIn("int main()", cpp)
        self.assertIn('omni::prayer("Ave Omnissiah! Binary Cant: ", incantatio);', cpp)
        self.assertIn('#line 1 "cant.omnc"', cpp)

    def test_binary_equivalent_to_plain_high_gothic(self):
        a = transpile(CANT, "x.omnc", dialect="binary-cant")
        b = transpile(CANONICAL, "x.omnc", dialect="high-gothic")
        self.assertEqual(a, b)

    def test_utf8_roundtrip_including_cyrillic(self):
        message = 'ORATIO("Слава Омниссии!");\n𐌰𐍉\n'
        self.assertEqual(decode_cant(encode_cant(message, columns=3)), message)

    def test_missing_binary_liturgies_are_heresy(self):
        cases = [
            ("IN_NOMINE_OMNISSIAH;\n", "OMN001"),
            ("CONSECRA processorem;\n", "OMN020"),
            ("CONSECRA memoriam;\n", "OMN063"),
            ("LAUDA spiritum_machinae;\n", "OMN021"),
            ('ORATIO("Ave Omnissiah! Binary Cant: ", incantatio);', "OMN063"),
        ]
        for removed, code in cases:
            with self.subTest(removed=removed):
                self.assert_heresy(encode_cant(CANONICAL.replace(removed, "")), code)

    def test_binary_mode_disallows_dark_age(self):
        self.assert_heresy(CANT, "OMN064", dark_age=True)

    def test_invalid_octet_and_invalid_utf8(self):
        for malformed in ("01011", "00000002", "000000000", "01010101 ✨"):
            with self.subTest(malformed=malformed):
                with self.assertRaises(BinaryCantError) as error:
                    decode_cant(malformed)
                self.assertEqual(error.exception.code, "OMN060")
                self.assert_heresy(malformed, "OMN060")
        self.assert_heresy("11111111\n", "OMN061")

    def test_non_ascii_whitespace_rejected(self):
        self.assert_heresy("01000001\u2003", "OMN060")

    def test_tokens_in_strings_comments_and_directives_do_not_count(self):
        no_prayer = CANONICAL.replace(
            'ORATIO("Ave Omnissiah! Binary Cant: ", incantatio);',
            'auto literal = "ORATIO(42)"; // ORATIO(0)\n    /* ORATIO(1) */'
        )
        self.assert_heresy(encode_cant(no_prayer), "OMN063")

    def test_decode_cli_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "decoded.omn"
            result = subprocess.run(
                [sys.executable, str(ROOT / "binary_cant.py"), "decode",
                 str(ROOT / "examples/binary_cant.cant"), "-o", str(output)],
                capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_text(encoding="utf-8"), CANONICAL)

    def test_compiler_cli_check_emit(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "cant.cpp"
            for action in ("check", "emit"):
                args = [sys.executable, str(ROOT / "omnissiah.py"), action,
                        str(ROOT / "examples/binary_cant.cant"), "--dialect", "binary-cant"]
                if action == "emit":
                    args.extend(("-o", str(out)))
                p = subprocess.run(args, capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("int main()", out.read_text(encoding="utf-8"))


@unittest.skipUnless(shutil.which("g++"), "needs g++")
class NativeBinaryCantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.tmp.name) / "omnic"
        r = subprocess.run(
            [sys.executable, str(ROOT / "omnissiah.py"), "build",
             str(ROOT / "bootstrap/omnissiah_selfhost.omn"),
             "-o", str(cls.binary), "--optimize=-O0"],
            capture_output=True, text=True
        )
        if r.returncode:
            cls.tmp.cleanup()
            raise AssertionError(r.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def native(self, action="emit", source=None, *extra):
        return subprocess.run(
            [str(self.binary), action, str(source or ROOT / "examples/binary_cant.cant"),
             "--dialect", "binary-cant", *extra],
            capture_output=True, text=True
        )

    def test_native_equals_python(self):
        result = self.native("emit")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout,
                         transpile(CANT, str((ROOT / "examples/binary_cant.cant").resolve()),
                                   dialect="binary-cant"))

    def test_native_program_executes(self):
        result = self.native("run", None, "--optimize=-O0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ave Omnissiah! Binary Cant: 40", result.stdout)

    def test_native_ast_and_source_emit(self):
        with tempfile.TemporaryDirectory() as temp:
            ast = self.native("source-ast")
            self.assertEqual(ast.returncode, 0, ast.stderr)
            tree = json.loads(ast.stdout)
            self.assertEqual(tree["kind"], "TranslationUnit")
            self.assertEqual(tree["end"], len(CANONICAL.encode("utf-8")))
            source_emit = self.native("source-emit")
            self.assertEqual(source_emit.returncode, 0, source_emit.stderr)
            self.assertIn("int main()", source_emit.stdout)

    def test_native_rejects_missing_prayer_and_dark_age(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "no_prayer.cant"
            path.write_text(encode_cant(CANONICAL.replace(
                'ORATIO("Ave Omnissiah! Binary Cant: ", incantatio);', ""
            )), encoding="utf-8")
            error = self.native("check", path)
            self.assertEqual(error.returncode, 2)
            self.assertIn("OMN063", error.stderr)
            error = self.native("check", None, "--dark-age")
            self.assertEqual(error.returncode, 2)
            self.assertIn("OMN064", error.stderr)


if __name__ == "__main__":
    unittest.main()
