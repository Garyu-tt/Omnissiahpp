"""Binary Cant codec: liturgical UTF-8 encoded as space-separated 8-bit octets.

Binary Cant is a fictional Mechanicus-inspired format here, not a canonical
Warhammer 40K language. The source language inside the binary stream is
the pseudo-High-Gothic dialect of Omnissiah++.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

MAX_OCTETS = 4 * 1024 * 1024


class BinaryCantError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def encode_cant(source: str, columns: int = 8) -> str:
    """Encode every UTF-8 byte, including rites, punctuation, spaces and LF."""
    if columns <= 0:
        raise ValueError("columns must be positive")
    data = source.encode("utf-8")
    if len(data) > MAX_OCTETS:
        raise BinaryCantError("OMN062", "исходник превышает предел Binary Cant (4 MiB)")
    words = [f"{byte:08b}" for byte in data]
    return "\n".join(" ".join(words[i:i + columns]) for i in range(0, len(words), columns)) + ("\n" if words else "")


def decode_cant(source: str) -> str:
    """Decode only ASCII binary octets separated by ASCII whitespace.

    Empty input decodes to an empty program, subsequently rejected by the
    mandatory Omnissiah++ liturgical verifier.
    """
    data = bytearray()
    # Unlike str.split(), reject non-ASCII Unicode separators, for native parity.
    if any(c not in "01 \t\r\n\v\f" for c in source):
        raise BinaryCantError("OMN060", "поток должен содержать только 0, 1 и ASCII-пробелы")
    for index, word in enumerate(source.split(), 1):
        if len(word) != 8 or any(bit not in "01" for bit in word):
            raise BinaryCantError("OMN060", f"осквернённый бинарный октет #{index}: {word[:32]!r}")
        if len(data) >= MAX_OCTETS:
            raise BinaryCantError("OMN062", "предел Binary Cant: 4 MiB")
        data.append(int(word, 2))
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise BinaryCantError("OMN061", "двоичный поток не является допустимым UTF-8") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Omnissiah++ Binary Cant octet encoder/decoder")
    parser.add_argument("action", choices=("encode", "decode"))
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=8)
    args = parser.parse_args(argv)
    try:
        content = args.source.read_text(encoding="utf-8-sig")
        result = encode_cant(content, args.columns) if args.action == "encode" else decode_cant(content)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
    except (OSError, ValueError, UnicodeError) as error:
        print(f"Binary Cant: {error}", file=sys.stderr)
        return 2
    print(f"{args.action}: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
