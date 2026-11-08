#!/usr/bin/env bash
# Deterministic bootstrap: Python -> Omnissiah++ -> Omnissiah++ -> Omnissiah++.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$ROOT/bootstrap/omnissiah_selfhost.omn"
CXX="${CXX:-g++}"
if [[ $# -gt 1 ]]; then
  echo 'Usage: scripts/bootstrap.sh [output-directory]' >&2
  exit 64
fi
if [[ $# -eq 1 ]]; then
  mkdir -p -- "$1"
  OUT="$(cd -- "$1" && pwd)"
else
  OUT="$(mktemp -d "${TMPDIR:-/tmp}/omnissiah-bootstrap.XXXXXXXX")"
  trap 'rm -rf -- "$OUT"' EXIT
fi
printf '[0/7] Building stage 1 with Python (last Python dependency)...\n'
python3 "$ROOT/omnissiah.py" build "$SOURCE" -o "$OUT/omnic-stage1" --cxx "$CXX" --optimize=-O0
printf '[1/7] Stage 1 compiles itself to stage 2...\n'
"$OUT/omnic-stage1" build "$SOURCE" -o "$OUT/omnic-stage2" --cxx "$CXX" --optimize -O0 --keep-cpp "$OUT/stage2.cpp"
printf '[2/7] Stage 2 compiles itself to stage 3...\n'
"$OUT/omnic-stage2" build "$SOURCE" -o "$OUT/omnic-stage3" --cxx "$CXX" --optimize -O0 --keep-cpp "$OUT/stage3.cpp"
printf '[3/7] Stage 3 emits a fourth generation...\n'
"$OUT/omnic-stage3" emit "$SOURCE" -o "$OUT/stage4.cpp"
cmp "$OUT/stage2.cpp" "$OUT/stage3.cpp"
cmp "$OUT/stage3.cpp" "$OUT/stage4.cpp"
printf '[4/7] Comparing native output against original Python implementation...\n'
python3 "$ROOT/omnissiah.py" emit "$SOURCE" -o "$OUT/stage0.cpp"
cmp "$OUT/stage0.cpp" "$OUT/stage2.cpp"
printf '[5/7] Running native-built examples...\n'
"$OUT/omnic-stage3" run "$ROOT/examples/hello.omn" --cxx "$CXX" --optimize -O0
"$OUT/omnic-stage3" run "$ROOT/examples/memory.omn" --cxx "$CXX" --optimize -O0
printf '[6/7] Testing R03 AST-driven backend without Python...\n'
"$OUT/omnic-stage3" ast "$ROOT/examples/core_syntax.omn" -o "$OUT/core_syntax.ast.json"
"$OUT/omnic-stage3" core-run "$ROOT/examples/core_syntax.omn" --cxx "$CXX" --optimize -O0
printf '[7/7] Self-host verified, SHA-256 of stable C++: '
sha256sum "$OUT/stage3.cpp" | cut -d' ' -f1
printf 'Machine spirit appeased. No Python was used in stages 1, 2, or 3.\n'
