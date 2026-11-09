"""Liturgical Compiler regression and real C++ integration tests."""
from __future__ import annotations

import argparse
from pathlib import Path
from unittest import mock
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import liturgical_compiler as lc  # noqa: E402
from liturgical_litanies import LITANIES, CATEGORY_TITLES  # noqa: E402


HELLO = """ВО_ИМЯ_ОМНИССИИ;
ОСВЯТИТЬ процессор;
ВОССЛАВИТЬ машинный_дух;
ЛИТАНИЯ главная() {
    МОЛИТВА("APP-RAN");
    ВЕРНУТЬ 0;
}
ДА_БУДЕТ_ВОЛЯ_МАШИНЫ;
"""


class LiturgicalCatalogueTests(unittest.TestCase):
    def test_ten_distinct_prayers_per_stage_around_three_hundred_characters(self):
        self.assertEqual(set(LITANIES), {"purification", "compilation", "linking", "launch"})
        self.assertEqual(set(CATEGORY_TITLES), set(LITANIES))
        for stage, prayers in LITANIES.items():
            with self.subTest(stage=stage):
                self.assertEqual(len(prayers), 10)
                self.assertEqual(len(set(prayers)), 10)
                for prayer in prayers:
                    self.assertTrue(250 <= len(prayer) <= 400, (stage, len(prayer)))

    def test_heresy_is_rejected(self):
        with mock.patch.object(lc.secrets, "randbelow", return_value=0):
            with mock.patch("builtins.input", return_value="wrong prayer"):
                self.assertFalse(lc.demand_litany("purification"))

    def test_missing_input_is_rejected(self):
        with mock.patch.object(lc.secrets, "randbelow", return_value=0):
            with mock.patch("builtins.input", side_effect=EOFError):
                self.assertFalse(lc.demand_litany("compilation"))

    def test_correct_litany_is_accepted(self):
        with mock.patch.object(lc.secrets, "randbelow", return_value=0):
            with mock.patch("builtins.input", return_value=LITANIES["linking"][0]):
                self.assertTrue(lc.demand_litany("linking"))

    def test_runtime_wrap_keeps_source_and_overrides_entrypoint(self):
        raw = "// injected runtime\n#line 1 \"example.omn\"\nint main() { return 0; }"
        wrapped = lc.wrap_runtime(raw)
        self.assertIn("#define main omnissiah_application_main", wrapped)
        self.assertIn("#line 1 \"example.omn\"", wrapped)
        self.assertIn("std::getline(std::cin, spoken)", wrapped)
        self.assertIn("return 77;", wrapped)
        self.assertIn("#undef main", wrapped)
        self.assertEqual(wrapped.count("int main(int argc, char** argv)"), 1)

    def test_opt_in_only_separate_compiler(self):
        original = (ROOT / "omnissiah.py").read_text(encoding="utf-8")
        self.assertNotIn("from liturgical_litanies import", original)
        self.assertNotIn("liturgical_compiler", original)


@unittest.skipUnless(shutil.which("g++"), "g++ required for C++ integration")
class LiturgicalBinaryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory(prefix="omnic-liturgy-test-")
        self.addCleanup(self.tempdir.cleanup)
        self.workspace = Path(self.tempdir.name)
        self.src = self.workspace / "hello.omn"
        self.src.write_text(HELLO, encoding="utf-8")
        self.exe = self.workspace / "hello"
        args = argparse.Namespace(
            source=self.src, dialect="ru", cxx="g++", std="c++20",
            optimize="-O0", keep_cpp=None,
        )
        with mock.patch.object(lc, "demand_litany", return_value=True) as ritual:
            self.assertEqual(lc.build(args, self.exe), 0)
            self.assertEqual(ritual.call_args_list,
                             [mock.call("purification"), mock.call("compilation"),
                              mock.call("linking")])

    def test_no_input_never_reaches_application(self):
        result = subprocess.run([str(self.exe)], input="", text=True,
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, lc.EXIT_RITUAL_REJECTED)
        self.assertNotIn("APP-RAN", result.stdout)
        self.assertIn("OMNL005", result.stderr)

    def test_wrong_input_never_reaches_application(self):
        result = subprocess.run([str(self.exe)], input="heresy\n", text=True,
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, lc.EXIT_RITUAL_REJECTED)
        self.assertNotIn("APP-RAN", result.stdout)
        self.assertIn("OMNL006", result.stderr)

    def test_correct_litany_runs_application_every_time(self):
        # A fresh OS process must ask a fresh litany; it cannot persist acceptance.
        for _ in range(2):
            with subprocess.Popen([str(self.exe)], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, encoding="utf-8") as proc:
                try:
                    heading = proc.stdout.readline()
                    if not heading.strip():
                        heading = proc.stdout.readline()
                    self.assertIn("ЛИТАНИЯ ЗАПУСКА", heading)
                    prayer = proc.stdout.readline().rstrip("\n")
                    self.assertIn("Омниссия", prayer)
                    proc.stdin.write(prayer + "\n")
                    proc.stdin.flush()
                    proc.stdin.close()
                    output = proc.stdout.read()
                    stderr = proc.stderr.read()
                    self.assertEqual(proc.wait(timeout=15), 0, stderr)
                    self.assertIn("APP-RAN", output)
                finally:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait()


if __name__ == "__main__":
    unittest.main()
