#!/usr/bin/env python3
"""Opt-in ritual compiler for Omnissiah++.

This is a separate compiler entrypoint. The ordinary omnissiah.py and native
self-hosted compiler remain completely unchanged.

Build stages: purification, compilation, linking.
Each resulting executable requires a fresh launch litany on EVERY invocation.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

from liturgical_litanies import CATEGORY_TITLES, LITANIES

ROOT = Path(__file__).resolve().parent
EXIT_RITUAL_REJECTED = 77


def demand_litany(stage: str) -> bool:
    prayers = LITANIES[stage]
    index = secrets.randbelow(len(prayers))
    prayer = prayers[index]
    print(f"\\n⚙ {CATEGORY_TITLES[stage].upper()} [{index + 1:02d}/10]")
    print(prayer)
    try:
        response = input("Повтори молитву дословно для продолжения: ")
    except (EOFError, KeyboardInterrupt):
        print("\\nOMNL001: литания не произнесена; обряд остановлен.", file=sys.stderr)
        return False
    if response != prayer:
        print("OMNL002: молитва искажена; обряд остановлен.", file=sys.stderr)
        return False
    print("✓ Литания принята.")
    return True


def original_cli(action: str, source: Path, dialect: str, *extra: str) -> list[str]:
    return [
        sys.executable, str(ROOT / "omnissiah.py"), action, str(source),
        "--dialect", dialect, *extra,
    ]


def wrap_runtime(cpp: str) -> str:
    """Rename only the application's main, then inject the unskippable entrypoint."""
    before, separator, after = cpp.partition("\\n#line 1 ")
    if not separator:
        raise ValueError("OMNL003: compiler output has no source #line marker")

    prayers = ",\\n".join("        " + json.dumps(line, ensure_ascii=False)
                           for line in LITANIES["launch"])
    entry = r"""
#undef main

namespace omnissiah_liturgical {
static const std::array<const char*, 10> launch_litanies = {
__PRAYERS__
};

template<class Entry>
int invoke(Entry entry, int argc, char** argv) {
    if constexpr (std::is_invocable_r_v<int, Entry, int, char**>) {
        return entry(argc, argv);
    } else if constexpr (std::is_invocable_r_v<int, Entry>) {
        return entry();
    } else {
        static_assert(std::is_invocable_r_v<int, Entry>,
                      "OMNL004: unsupported main signature");
        return 77;
    }
}
}

int main(int argc, char** argv) {
    std::random_device entropy;
    std::mt19937 engine(entropy());
    std::uniform_int_distribution<int> pick(0, 9);
    const int index = pick(engine);
    const std::string expected = omnissiah_liturgical::launch_litanies[index];
    std::cout << "\\n[ЛИТАНИЯ ЗАПУСКА " << (index + 1) << "/10]\\n"
              << expected << "\\n" << std::flush;
    std::cout << "Повтори молитву дословно для запуска: " << std::flush;
    std::string spoken;
    if (!std::getline(std::cin, spoken)) {
        std::cerr << "\\nOMNL005: молитва не введена; запуск запрещён.\\n";
        return 77;
    }
    if (spoken != expected) {
        std::cerr << "OMNL006: искажённая молитва; запуск запрещён.\\n";
        return 77;
    }
    std::cout << "Омниссия благословляет пробуждение.\\n" << std::flush;
    return omnissiah_liturgical::invoke(omnissiah_application_main, argc, argv);
}
""".replace("__PRAYERS__", prayers)
    # Include standard headers before renaming main to avoid affecting headers.
    headers = ("#include <array>\\n#include <iostream>\\n#include <random>\\n"
               "#include <string>\\n#include <type_traits>\\n")
    return (headers + before + "\\n#define main omnissiah_application_main"
            + separator + after + "\\n" + entry)


def emit(source: Path, dialect: str, target: Path) -> int:
    command = original_cli("emit", source, dialect, "-o", str(target))
    return subprocess.run(command, check=False).returncode


def build(args: argparse.Namespace, output: Path) -> int:
    if not demand_litany("purification"):
        return EXIT_RITUAL_REJECTED

    with tempfile.TemporaryDirectory(prefix="omnissiah-liturgical-") as td:
        temp = Path(td)
        translated = temp / "translated.cpp"
        if rc := emit(args.source, args.dialect, translated):
            return rc

        cpp = temp / "liturgical.cpp"
        try:
            cpp.write_text(wrap_runtime(translated.read_text(encoding="utf-8")),
                           encoding="utf-8")
            if args.keep_cpp is not None:
                args.keep_cpp.parent.mkdir(parents=True, exist_ok=True)
                args.keep_cpp.write_text(cpp.read_text(encoding="utf-8"),
                                         encoding="utf-8")
        except (OSError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 3

        if not demand_litany("compilation"):
            return EXIT_RITUAL_REJECTED

        obj = temp / "application.o"
        common = [args.cxx, f"-std={args.std}", args.optimize,
                  "-Wall", "-Wextra", "-pedantic"]
        if rc := subprocess.run([*common, "-c", str(cpp), "-o", str(obj)],
                                check=False).returncode:
            return rc

        if not demand_litany("linking"):
            return EXIT_RITUAL_REJECTED

        output.parent.mkdir(parents=True, exist_ok=True)
        return subprocess.run([args.cxx, str(obj), "-o", str(output)],
                              check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="liturgical_compiler",
        description="Отдельный компилятор с обязательными литаниями сборки и запуска",
    )
    parser.add_argument("--version", action="version",
                        version="Omnissiah++ Liturgical Compiler R01")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "build", "run"):
        command = commands.add_parser(name)
        command.add_argument("source", type=Path)
        command.add_argument("--dialect",
                             choices=("ru", "high-gothic", "gothic", "binary-cant"),
                             default="ru")
        if name in ("build", "run"):
            command.add_argument("--cxx", default=os.environ.get("CXX", "g++"))
            command.add_argument("--std", choices=("c++17", "c++20", "c++23"),
                                 default="c++20")
            command.add_argument("--optimize", choices=("-O0", "-O1", "-O2", "-O3", "-Os"),
                                 default="-O2")
            command.add_argument("--keep-cpp", type=Path)
        if name == "build":
            command.add_argument("-o", "--output", type=Path)
        if name == "run":
            command.add_argument("--arg", action="append", default=[])
    args = parser.parse_args(argv)

    try:
        if args.command == "check":
            if not demand_litany("purification"):
                return EXIT_RITUAL_REJECTED
            return subprocess.run(original_cli("check", args.source, args.dialect),
                                  check=False).returncode
        if args.command == "build":
            output = (args.output or args.source.with_suffix("")).resolve()
            rc = build(args, output)
            if rc == 0:
                print(f"✓ Реликвия собрана: {output}")
            return rc
        if args.command == "run":
            with tempfile.TemporaryDirectory(prefix="omnissiah-liturgical-run-") as td:
                output = Path(td) / "blessed-program"
                if rc := build(args, output):
                    return rc
                return subprocess.run([str(output), *args.arg], check=False).returncode
    except (OSError, UnicodeError) as error:
        print(f"OMNL007: системная ошибка: {error}", file=sys.stderr)
        return 3
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
