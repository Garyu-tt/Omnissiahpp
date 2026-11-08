"""Unit and actual C++ integration tests. No external Python dependencies."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omnissiah import OmnissiahError, transpile  # noqa: E402

HEADER = '''ВО_ИМЯ_ОМНИССИИ;
ОСВЯТИТЬ процессор;
ВОССЛАВИТЬ машинный_дух;
ОСВЯТИТЬ память;
'''
FOOTER = 'ДА_БУДЕТ_ВОЛЯ_МАШИНЫ;\n'


class SemanticTests(unittest.TestCase):
    def assert_heresy(self, source, code):
        with self.assertRaises(OmnissiahError) as raised:
            transpile(source, 'test.omn')
        self.assertEqual(raised.exception.code, code)

    def test_hello(self):
        out = transpile(HEADER + 'ЛИТАНИЯ главная() { МОЛИТВА("ok"); ВЕРНУТЬ 0; }\n' + FOOTER)
        self.assertIn('int main()', out)
        self.assertIn('omni::prayer("ok")', out)

    def test_missing_invocation(self):
        self.assert_heresy('ЛИТАНИЯ главная(){ВЕРНУТЬ 0;}\n' + FOOTER, 'OMN001')

    def test_missing_end(self):
        self.assert_heresy(HEADER + 'ЛИТАНИЯ главная(){ВЕРНУТЬ 0;}\n', 'OMN019')

    def test_no_processor_blessing(self):
        self.assert_heresy('ВО_ИМЯ_ОМНИССИИ;\nЛИТАНИЯ главная(){ВЕРНУТЬ 0;}\n' + FOOTER, 'OMN020')

    def test_no_io_blessing(self):
        self.assert_heresy('ВО_ИМЯ_ОМНИССИИ; ОСВЯТИТЬ процессор;\n'
                           'ЛИТАНИЯ главная(){МОЛИТВА("x");}\n' + FOOTER, 'OMN021')

    def test_direct_cout_requires_io_blessing(self):
        self.assert_heresy('ВО_ИМЯ_ОМНИССИИ; ОСВЯТИТЬ процессор;\n'
                           'ЛИТАНИЯ главная(){std::cout << 123;}\n' + FOOTER, 'OMN021')

    def test_no_memory_blessing(self):
        self.assert_heresy('ВО_ИМЯ_ОМНИССИИ; ОСВЯТИТЬ процессор;\n'
                           'ЛИТАНИЯ главная(){auto p = new int(7); delete p;}\n' + FOOTER, 'OMN022')

    def test_no_memory_blessing_with_localized_syntax(self):
        self.assert_heresy('ВО_ИМЯ_ОМНИССИИ; ОСВЯТИТЬ процессор;\n'
                           'ЛИТАНИЯ главная(){АВТО p = НОВОЕ ЦЕЛОЕ(7);}\n' + FOOTER, 'OMN022')

    def test_rites_only_toplevel(self):
        self.assert_heresy(HEADER + 'ЛИТАНИЯ главная(){ОСВЯТИТЬ память; ВЕРНУТЬ 0;}\n' + FOOTER,
                           'OMN012')

    def test_no_late_rites(self):
        self.assert_heresy('ВО_ИМЯ_ОМНИССИИ; ОСВЯТИТЬ процессор;\n'
                           'ЛИТАНИЯ главная(){ВЕРНУТЬ 0;}\n'
                           'ОСВЯТИТЬ память;\n' + FOOTER, 'OMN018')

    def test_no_code_after_end(self):
        self.assert_heresy(HEADER + 'ЛИТАНИЯ главная(){ВЕРНУТЬ 0;}\n' + FOOTER + 'ЦЕЛОЕ x;', 'OMN015')

    def test_missing_semicolon(self):
        self.assert_heresy('ВО_ИМЯ_ОМНИССИИ\nОСВЯТИТЬ процессор;', 'OMN013')

    def test_unknown_rite(self):
        self.assert_heresy('ВО_ИМЯ_ОМНИССИИ;\nОСВЯТИТЬ видеокарту;\n' + FOOTER, 'OMN017')

    def test_dark_age_can_work_without_rites(self):
        out = transpile('ЛИТАНИЯ главная(){ МОЛИТВА("dark"); ВЕРНУТЬ 0; }', dark_age=True)
        self.assertIn('omni::prayer("dark")', out)

    def test_strings_comments_and_directives_not_translated(self):
        source = ('#define NOTE "МОЛИТВА ИНАЧЕ"\n' + HEADER +
                  'ЛИТАНИЯ главная(){\n'
                  ' // ЛИТАНИЯ главная(); МОЛИТВА(1)\n'
                  ' /* ЕСЛИ_ВОЛЯ_ОМНИССИИ */\n'
                  ' auto a = R"foo(МОЛИТВА(1); ВЕРНУТЬ)foo";\n'
                  ' auto b = "МОЛИТВА(2)"; МОЛИТВА(a,b); ВЕРНУТЬ 0;\n'
                  '}\n' + FOOTER)
        out = transpile(source)
        self.assertIn('#define NOTE "МОЛИТВА ИНАЧЕ"', out)
        self.assertIn('// ЛИТАНИЯ главная(); МОЛИТВА(1)', out)
        self.assertIn('R"foo(МОЛИТВА(1); ВЕРНУТЬ)foo"', out)
        self.assertIn('"МОЛИТВА(2)"', out)
        self.assertIn('omni::prayer(a,b)', out)

    def test_maintains_line_positions(self):
        src = (HEADER + 'ЛИТАНИЯ главная() {\n'
               '  МОЛИТВА("Привет");\n}\n' + FOOTER)
        output = transpile(src, 'my_test.omn')
        self.assertIn('#line 1 "my_test.omn"', output)
        self.assertEqual(output.split('#line 1 "my_test.omn"\n', 1)[1].count('\n'), src.count('\n'))

    def test_unterminated_comment(self):
        self.assert_heresy('/* no end', 'OMN040')

    def test_unterminated_raw(self):
        self.assert_heresy('R"foo(unclosed', 'OMN041')


@unittest.skipUnless(shutil.which('g++'), 'g++ is not installed')
class IntegrationTests(unittest.TestCase):
    def run_example(self, filename):
        with tempfile.TemporaryDirectory() as td:
            command = [sys.executable, str(ROOT / 'omnissiah.py'), 'run',
                       str(ROOT / 'examples' / filename)]
            return subprocess.run(command, text=True, capture_output=True, cwd=td)

    def test_hello_binary(self):
        result = self.run_example('hello.omn')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Слава Омниссии!', result.stdout)
        self.assertIn('Литания №3', result.stdout)

    def test_memory_and_templates_binary(self):
        result = self.run_example('memory.omn')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Ответ машинного духа: 42', result.stdout)
        self.assertIn('Размер архива: 3', result.stdout)

    def test_cpp_error_points_at_omn_file(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / 'bad.omn'
            source.write_text(HEADER + 'ЛИТАНИЯ главная() {\n  НЕСУЩЕСТВУЕТ();\n  ВЕРНУТЬ 0;\n}\n' + FOOTER,
                              encoding='utf-8')
            result = subprocess.run([sys.executable, str(ROOT / 'omnissiah.py'), 'build',
                                     str(source), '-o', str(Path(td) / 'binary')],
                                    text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('bad.omn:6:', result.stderr)


if __name__ == '__main__':
    unittest.main()
