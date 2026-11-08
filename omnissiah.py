#!/usr/bin/env python3
"""Omnissiah++: ritual-aware UTF-8 C++20 transpiler (stdlib-only)."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from gothic_dialects import DIALECTS, normalize_identifier
from binary_cant import BinaryCantError, decode_cant
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

VERSION = "0.1.0"

# Canonical Omnissiah++ lexemes. Native C++ remains valid inside rituals.
KEYWORDS = {
    "ЛИТАНИЯ": "int", "главная": "main", "ГЛАВНАЯ": "main",
    "ЦЕЛОЕ": "int", "ДРОБЬ": "double", "СТРОКА": "std::string",
    "ЛОГИКА": "bool", "ИСТИНА": "true", "ЛОЖЬ": "false",
    "НИЧТО": "void", "АВТО": "auto", "ПОСТОЯННО": "const",
    "ЕСЛИ_ВОЛЯ_ОМНИССИИ": "if", "ИНАЧЕ": "else",
    "ПОКА_ДУХ_НЕ_УСМИРЕН": "while", "СВЯЩЕННЫЙ_ЦИКЛ": "for",
    "ВЕРНУТЬ": "return", "ПРЕРВАТЬ": "break", "ПРОДОЛЖИТЬ": "continue",
    "КЛАСС": "class", "СТРУКТУРА": "struct", "ШАБЛОН": "template",
    "ПУБЛИЧНО": "public", "ЧАСТНО": "private", "ЗАЩИЩЕНО": "protected",
    "НОВОЕ": "new", "УДАЛИТЬ": "delete", "ПРОСТРАНСТВО": "namespace",
    "ИСПОЛЬЗОВАТЬ": "using", "МОЛИТВА": "omni::prayer",
}

INVOKE = "ВО_ИМЯ_ОМНИССИИ"
END = "ДА_БУДЕТ_ВОЛЯ_МАШИНЫ"
RITUALS = {("ОСВЯТИТЬ", "процессор"): "cpu",
           ("ОСВЯТИТЬ", "память"): "memory",
           ("ВОССЛАВИТЬ", "машинный_дух"): "io"}

RAW_STRING_RE = re.compile(r'(?:u8|u|U|L)?R"([^()\\\s]{0,16})\(')
NORMAL_STRING_RE = re.compile(r"""(?:u8|u|U|L)?(["'])""")

RUNTIME = '''// Omnissiah++ runtime v0.1.0
#include <iostream>
#include <string>
#include <utility>
namespace omni {
    template<typename... Args>
    void prayer(Args&&... args) {
        if constexpr (sizeof...(Args) > 0) {
            (std::cout << ... << std::forward<Args>(args));
        }
        std::cout << '\\n';
    }
}
'''

@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    start: int
    end: int
    line: int
    column: int


class OmnissiahError(Exception):
    def __init__(self, code: str, message: str, token: Token | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.token = token

    def format(self, filename: str) -> str:
        if self.token is None:
            return f"{filename}: error {self.code}: {self.message}"
        return f"{filename}:{self.token.line}:{self.token.column}: error {self.code}: {self.message}"


def lex(source: str) -> list[Token]:
    """Lossless lexer: protects UTF-8 strings, comments, raw strings, and directives."""
    out = []
    i, n, line, col = 0, len(source), 1, 1
    line_prefix_whitespace = True

    def advance(chunk: str):
        nonlocal line, col, line_prefix_whitespace
        if '\n' in chunk:
            line += chunk.count('\n')
            col = len(chunk.rsplit('\n', 1)[1]) + 1
            line_prefix_whitespace = (chunk.rsplit('\n', 1)[1].strip(' \t\r') == '')
        else:
            col += len(chunk)
            if chunk.strip(' \t\r'):
                line_prefix_whitespace = False

    while i < n:
        start, sl, sc = i, line, col
        c = source[i]
        kind = 'punct'
        if c.isspace():
            kind = 'ws'
            i += 1
            while i < n and source[i].isspace():
                i += 1
        elif c == '#' and line_prefix_whitespace:
            kind = 'directive'
            i += 1
            while i < n:
                eol = source.find('\n', i)
                if eol < 0:
                    i = n
                    break
                continuation = source[i:eol].rstrip().endswith('\\')
                i = eol + 1
                if not continuation:
                    break
        elif source.startswith('//', i):
            kind = 'comment'
            i = source.find('\n', i)
            if i == -1:
                i = n
        elif source.startswith('/*', i):
            kind = 'comment'
            ending = source.find('*/', i + 2)
            if ending == -1:
                raise OmnissiahError('OMN040', 'незакрытый комментарий', Token('comment', '', start, start, sl, sc))
            i = ending + 2
        else:
            # C++ raw literal: R"tag(contents)tag", incl. u8R"...".
            rm = RAW_STRING_RE.match(source, i)
            if rm:
                kind = 'string'
                delimiter = ')' + rm.group(1) + '"'
                ending = source.find(delimiter, i + len(rm.group(0)))
                if ending == -1:
                    raise OmnissiahError('OMN041', 'незакрытая raw-строка', Token('string', '', start, start, sl, sc))
                i = ending + len(delimiter)
            else:
                # Normal C++ string/character literals (u8, u, U, L prefixes).
                qm = NORMAL_STRING_RE.match(source, i)
                if qm:
                    kind = 'string'
                    q = qm.group(1)
                    i += len(qm.group(0))
                    while i < n:
                        if source[i] == '\\':
                            i += min(2, n - i)
                        elif source[i] == q:
                            i += 1
                            break
                        else:
                            i += 1
                    else:
                        raise OmnissiahError('OMN042', 'незакрытая строка или символ', Token('string', '', start, start, sl, sc))
                elif c == '_' or c.isalpha() or ord(c) > 127 and c.isidentifier():
                    kind = 'identifier'
                    i += 1
                    while i < n and (source[i] == '_' or source[i].isalnum()):
                        i += 1
                elif c.isdigit():
                    kind = 'number'
                    i += 1
                    while i < n and (source[i].isalnum() or source[i] in "._'"):
                        i += 1
                else:
                    i += 1
        value = source[start:i]
        out.append(Token(kind, value, start, i, sl, sc))
        advance(value)
    return out


def _significant(tokens: list[Token]) -> list[Token]:
    return [t for t in tokens if t.kind not in ('ws', 'comment', 'directive')]


def _masked(s: str) -> str:
    return ''.join('\n' if c == '\n' else ' ' for c in s)


def _pattern(sig: list[Token], index: int, parts: tuple[str, ...]) -> bool:
    return (index + len(parts) <= len(sig)
            and all(sig[index + k].value == part for k, part in enumerate(parts)))


def _is_io(sig: list[Token], i: int) -> bool:
    v = sig[i].value
    if v in {'МОЛИТВА', 'printf', 'scanf', 'puts', 'putchar', 'getchar',
             'fprintf', 'fputs', 'fgets', 'fopen', 'fread', 'fwrite',
             'ofstream', 'ifstream', 'fstream'}:
        return True
    return any(_pattern(sig, i, ('std', ':', ':', name))
               for name in ('cout', 'cin', 'cerr', 'clog', 'print', 'println',
                            'ofstream', 'ifstream', 'fstream'))


def _is_alloc(sig: list[Token], i: int) -> bool:
    v = sig[i].value
    return v in {'new', 'delete', 'НОВОЕ', 'УДАЛИТЬ', 'malloc',
                 'calloc', 'realloc', 'free', 'make_unique', 'make_shared'}


def transpile(source: str, filename: str = '<input>', *, dark_age: bool = False,
              dialect: str = 'ru') -> str:
    binary_cant = dialect == "binary-cant"
    if binary_cant:
        if dark_age:
            raise OmnissiahError('OMN064', 'Binary Cant запрещает Тёмную эру: молитвы обязательны')
        try:
            source = decode_cant(source)
        except BinaryCantError as err:
            raise OmnissiahError(err.code, str(err)) from err
        dialect = "high-gothic"
    if '\x00' in source:
        raise OmnissiahError('OMN043', 'NUL в исходном файле')
    if dialect not in DIALECTS:
        raise OmnissiahError('OMN050', f'неизвестный диалект: {dialect}')
    toks = lex(source)
    sig = [replace(t, value=normalize_identifier(t.value, dialect))
           if t.kind == 'identifier' else t for t in _significant(toks)]
    edits: list[tuple[int, int, str]] = []
    rituals: dict[str, Token] = {}
    invoked = ended = False
    depth = 0
    i = 0
    seen_nonritual = False
    while i < len(sig):
        t = sig[i]
        v = t.value
        if v in {INVOKE, END, 'ОСВЯТИТЬ', 'ВОССЛАВИТЬ'}:
            if depth:
                raise OmnissiahError('OMN012', 'ритуал разрешён только на верхнем уровне', t)
            if v == INVOKE or v == END:
                if i + 1 >= len(sig) or sig[i + 1].value != ';':
                    raise OmnissiahError('OMN013', 'после священного маркера нужна точка с запятой', t)
                if v == INVOKE:
                    if invoked or (seen_nonritual and not dark_age):
                        raise OmnissiahError('OMN001', 'призыв Омниссии должен быть первым', t)
                    invoked = True
                else:
                    if ended:
                        raise OmnissiahError('OMN014', 'завершение указано дважды', t)
                    ended = True
                    if i + 2 < len(sig):
                        raise OmnissiahError('OMN015', 'после завершения не должно быть кода', sig[i + 2])
                edits.append((t.start, sig[i + 1].end, _masked(source[t.start:sig[i + 1].end])))
                i += 2
                continue
            if i + 2 >= len(sig) or sig[i + 2].value != ';':
                raise OmnissiahError('OMN016', 'ритуал имеет форму «ОСВЯТИТЬ память;»', t)
            target = sig[i + 1].value
            kind = RITUALS.get((v, target))
            if not kind:
                raise OmnissiahError('OMN017', f'неизвестный ритуал «{v} {target}»', t)
            if not invoked and not dark_age:
                raise OmnissiahError('OMN001', 'сначала призови Омниссию', t)
            if seen_nonritual and not dark_age:
                raise OmnissiahError('OMN018', 'ритуалы должны предшествовать объявлениям и функциям', t)
            rituals[kind] = t
            edits.append((t.start, sig[i + 2].end, _masked(source[t.start:sig[i + 2].end])))
            i += 3
            continue
        if v == '{':
            depth += 1
        if v == '}':
            depth -= 1
        if not invoked and not dark_age:
            raise OmnissiahError('OMN001', 'первая инструкция: ВО_ИМЯ_ОМНИССИИ;', t)
        if ended:
            raise OmnissiahError('OMN015', 'код после завершения', t)
        if v in ('главная', 'ГЛАВНАЯ', 'main') and i + 1 < len(sig) and sig[i + 1].value == '(':
            if 'cpu' not in rituals and not dark_age:
                raise OmnissiahError('OMN020', 'прежде чем объявить main(), напиши ОСВЯТИТЬ процессор;', t)
        if _is_io(sig, i) and 'io' not in rituals and not dark_age:
            raise OmnissiahError('OMN021', 'ввод-вывод требует ВОССЛАВИТЬ машинный_дух;', t)
        if _is_alloc(sig, i) and 'memory' not in rituals and not dark_age:
            raise OmnissiahError('OMN022', 'выделение/освобождение памяти требует ОСВЯТИТЬ память;', t)
        if t.kind == 'identifier':
            if v in KEYWORDS:
                edits.append((t.start, t.end, KEYWORDS[v]))
            elif v != source[t.start:t.end]:
                edits.append((t.start, t.end, v))
        seen_nonritual = True
        i += 1
    if not dark_age:
        if not invoked:
            raise OmnissiahError('OMN001', 'отсутствует ВО_ИМЯ_ОМНИССИИ;')
        if not ended:
            raise OmnissiahError('OMN019', 'отсутствует ДА_БУДЕТ_ВОЛЯ_МАШИНЫ;')
    if binary_cant:
        words = [t.value for t in sig]
        required = (
            ('ОСВЯТИТЬ', 'процессор', ';'),
            ('ОСВЯТИТЬ', 'память', ';'),
            ('ВОССЛАВИТЬ', 'машинный_дух', ';'),
        )
        for rite in required:
            if not any(tuple(words[k:k+3]) == rite for k in range(len(words) - 2)):
                raise OmnissiahError('OMN063', f'Binary Cant требует ритуал: {" ".join(rite)}')
        if not any(words[k] == 'МОЛИТВА' and words[k+1] == '('
                   for k in range(len(words) - 1)):
            raise OmnissiahError('OMN063', 'Binary Cant требует хотя бы одну МОЛИТВА(...)')
    # Apply backwards, maintaining line numbers exactly.
    translated = source
    for start, end, replacement in sorted(edits, key=lambda x: x[0], reverse=True):
        translated = translated[:start] + replacement + translated[end:]
    escaped = filename.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')
    return f"{RUNTIME}\n#line 1 \"{escaped}\"\n{translated}"


def compiler_command(cxx: str, cpp: Path, output: Path, std: str = 'c++20', optimize: str = '-O2') -> list[str]:
    return [cxx, f'-std={std}', optimize, '-Wall', '-Wextra', '-pedantic', str(cpp), '-o', str(output)]


def build(source: Path, output: Path, *, cxx: str, dark_age: bool,
          keep_cpp: Path | None, std: str, optimize: str, dialect: str = 'ru') -> int:
    text = source.read_text(encoding='utf-8-sig')
    generated = transpile(text, str(source.resolve()), dark_age=dark_age, dialect=dialect)
    with tempfile.TemporaryDirectory(prefix='omnissiah-') as td:
        cpp = Path(td) / (source.stem + '.cpp')
        cpp.write_text(generated, encoding='utf-8')
        if keep_cpp:
            keep_cpp.parent.mkdir(parents=True, exist_ok=True)
            keep_cpp.write_text(generated, encoding='utf-8')
        output.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(compiler_command(cxx, cpp, output, std, optimize))
        return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='omnissiah', description='Omnissiah++ v0.1 ritual-aware C++ transpiler')
    parser.add_argument('--version', action='version', version=f'Omnissiah++ {VERSION}')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('check', 'emit', 'build', 'run'):
        p = sub.add_parser(name)
        p.add_argument('source', type=Path, help='Исходный .omn/.opp файл UTF-8')
        p.add_argument('--dark-age', action='store_true', help='Режим Тёмной эры: отключить обязательность ритуалов')
        p.add_argument('--dialect', choices=DIALECTS, default='ru',
                       help='ru, high-gothic, gothic или binary-cant (бинарная литания)')
        if name in ('emit', 'build'):
            p.add_argument('-o', '--output', type=Path)
        if name in ('build', 'run'):
            p.add_argument('--cxx', default=os.environ.get('CXX', 'g++'))
            p.add_argument('--std', default='c++20', choices=('c++17', 'c++20', 'c++23'))
            p.add_argument('--optimize', default='-O2', choices=('-O0', '-O1', '-O2', '-O3', '-Os'))
            p.add_argument('--keep-cpp', type=Path)
        if name == 'run':
            p.add_argument('--arg', action='append', default=[], help='Аргумент для исполняемой программы')
    args = parser.parse_args(argv)
    try:
        original = args.source.read_text(encoding='utf-8-sig')
        if args.dark_age:
            print('⚠ ТЁМНАЯ ЭРА ТЕХНОЛОГИЙ: проверки ритуалов отключены.', file=sys.stderr)
        if args.command in ('check', 'emit'):
            generated = transpile(original, str(args.source.resolve()), dark_age=args.dark_age, dialect=args.dialect)
            if args.command == 'check':
                print(f'Омниссия благословил синтаксис: {args.source} (проверка ритуалов; C++ ещё не компилировался)')
            elif args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(generated, encoding='utf-8')
                print(f'C++ создан: {args.output}')
            else:
                print(generated, end='')
            return 0
        if args.command == 'build':
            output = args.output or args.source.with_suffix('')
            rc = build(args.source, output, cxx=args.cxx, dark_age=args.dark_age,
                       keep_cpp=args.keep_cpp, std=args.std, optimize=args.optimize, dialect=args.dialect)
            if rc == 0:
                print(f'Компиляция завершена: {output}')
            return rc
        if args.command == 'run':
            with tempfile.TemporaryDirectory(prefix='omnissiah-run-') as tmp:
                executable = Path(tmp) / 'ritual'
                rc = build(args.source, executable, cxx=args.cxx, dark_age=args.dark_age,
                           keep_cpp=args.keep_cpp, std=args.std, optimize=args.optimize, dialect=args.dialect)
                if rc:
                    return rc
                return subprocess.run([str(executable), *args.arg]).returncode
    except OmnissiahError as exc:
        print(exc.format(str(args.source)), file=sys.stderr)
        return 2
    except (OSError, UnicodeError) as exc:
        print(f'Ошибка ввода-вывода: {exc}', file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
