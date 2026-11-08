# Omnissiah++ R03: self-hosting bootstrap + core AST

The native compiler lives in [`omnissiah_selfhost.omn`](omnissiah_selfhost.omn):
**source code written in Omnissiah++** (with ordinary C++20 syntax where the
language deliberately inherits C++). It is not generated C++ renamed to `.omn`.
The file contains the ritual invocation, consecrations, localized keywords,
lexer, UTF-8 validation, ritual checks, translator, native CLI and build runner.

## Reproduce

Requirements: Python 3.10+, a POSIX shell, C++20 compiler (`g++` or `clang++`),
`cmp` and `sha256sum`. Python is necessary **only for stage 0**.

```sh
bash scripts/bootstrap.sh build/bootstrap
# Or use: CXX=clang++ bash scripts/bootstrap.sh build/clang-bootstrap

build/bootstrap/omnic-stage3 run examples/hello.omn
build/bootstrap/omnic-stage3 build examples/memory.omn -o build/relic
build/relic
```

The seven bootstrap checks:

1. **Stage 0**: Python R01 transpiles `omnissiah_selfhost.omn`, C++ compiler
   compiles the result as `omnic-stage1`.
2. **Stage 1**: `omnic-stage1` (native binary) compiles the same `.omn` file as
   `omnic-stage2` and saves the generated C++.
3. **Stage 2**: `omnic-stage2` compiles that `.omn` into `omnic-stage3`.
4. **Stage 3**: `omnic-stage3` emits another copy of the C++.
5. Verify byte-identical stage 2, stage 3 and stage 4 C++ output and equivalence
   with stage 0 Python output. A digest is printed for the stable translation.
6. Compile/run original `.omn` examples using stage 3. The test suite also runs
   a differential corpus of valid and invalid sources.
7. Parse a Core program into JSON AST, compile that program from AST-derived
   C++ and run it using the stage 3 compiler (again without Python).

**What “self-hosted” means here:** after the stage-0 seed, the entire
Omnissiah++ frontend (lexer, ritual checker and transpiler) is translated by a
binary built from the same `.omn` source. Stages 1+ require no Python.

**What it does not mean:** this is *not* an independently implemented machine-code
backend or a complete C++ parser. The R03 Core parser handles an explicitly limited
grammar; the compiler source itself is still bootstrapped through the legacy
C++-compatible token translator. C++ code generation uses a trusted existing
C++ toolchain. The ritual checks are lexical, not security controls. The C++
source standard library and toolchain remain required for building new binaries.
This is a standard *self-hosted source-to-source compiler*.

The native `check` / `emit` commands can run on other platforms where the binary
has been built. The native `build` and `run` commands use POSIX process spawning,
and have been tested on Linux; Windows native compilation is not yet supported.

## R03 native syntax frontend

`CoreParser` builds a tree of `ASTNode` nodes from native lexer tokens. Nodes
include source position and children. `core-emit` generates a fresh C++20 source
from this tree; `core-build` and `core-run` compile/execute that generated code.
The old `emit`/`build`/`run` commands preserve the full C++-compatible dialect.

```sh
build/bootstrap/omnic-stage3 ast examples/core_syntax.omn -o build/core.ast.json
build/bootstrap/omnic-stage3 core-run examples/core_syntax.omn
```

Unsupported C++ features are not silently represented as AST. Core is not a
replacement for GCC/Clang and is not yet capable of parsing its own native
compiler source. The stage-0 Python seed, C++ toolchain, runtime headers and
POSIX process runner still have the documented roles.

## Roadmap

- R04: expand Core to the native compiler's own source grammar, separate
  parser, semantic analysis and backend into stable units, add source spans,
  differential fuzzing and richer type checks.
- R05: make the **AST backend** itself self-host (stage 1 -> 2 -> 3 via Core)
  with reproducible output; test GCC and Clang and full compiler fixtures.
- Later: optional LLVM or independent machine-code backend. Removing the C++
  toolchain dependency is a much larger project than frontend self-hosting.
