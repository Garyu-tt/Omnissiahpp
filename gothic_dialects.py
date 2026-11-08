"""Optional High Gothic and Gothic-script lexical aliases for Omnissiah++.

This is deliberately *pseudo*-High Gothic: Warhammer 40k has no complete
standardized High Gothic grammar. The glyph mode uses the historical Gothic
Unicode block (U+10330..U+1034A) as a creative orthographic layer, not as a
claim that the two languages are historically related.
"""
from __future__ import annotations

DIALECTS = ("ru", "high-gothic", "gothic")

# Canonical output tokens intentionally reuse the established ritual checker.
HIGH_GOTHIC = {
    "IN_NOMINE_OMNISSIAH": "ВО_ИМЯ_ОМНИССИИ",
    "FINIS_RITUALIS": "ДА_БУДЕТ_ВОЛЯ_МАШИНЫ",
    "CONSECRA": "ОСВЯТИТЬ",
    "LAUDA": "ВОССЛАВИТЬ",
    "PROCESSOREM": "процессор",
    "MEMORIAM": "память",
    "SPIRITUM_MACHINAE": "машинный_дух",
    "LITANIA": "ЛИТАНИЯ",
    "PRIMARIA": "главная",
    "NUMERUS": "ЦЕЛОЕ",
    "FRACTIO": "ДРОБЬ",
    "VERBUM": "СТРОКА",
    "LOGICA": "ЛОГИКА",
    "VERUM": "ИСТИНА",
    "FALSUM": "ЛОЖЬ",
    "VACUUM": "НИЧТО",
    "AUTOMATUM": "АВТО",
    "CONSTANS": "ПОСТОЯННО",
    "SI": "ЕСЛИ_ВОЛЯ_ОМНИССИИ",
    "ALITER": "ИНАЧЕ",
    "DUM": "ПОКА_ДУХ_НЕ_УСМИРЕН",
    "ITERATIO": "СВЯЩЕННЫЙ_ЦИКЛ",
    "REDDO": "ВЕРНУТЬ",
    "FRANGE": "ПРЕРВАТЬ",
    "PERGE": "ПРОДОЛЖИТЬ",
    "CLASSIS": "КЛАСС",
    "STRUCTURA": "СТРУКТУРА",
    "TEMPLUM": "ШАБЛОН",
    "PUBLICUM": "ПУБЛИЧНО",
    "PRIVATUM": "ЧАСТНО",
    "PROTECTUM": "ЗАЩИЩЕНО",
    "CREA": "НОВОЕ",
    "DELE": "УДАЛИТЬ",
    "SPATIUM": "ПРОСТРАНСТВО",
    "UTERE": "ИСПОЛЬЗОВАТЬ",
    "ORATIO": "МОЛИТВА",
}

# Historical Gothic has no direct 'c' or 'v' grapheme. For ease of writing,
# script mode accepts phoneticized k/w aliases (KONSEKRA, WERBUM, etc.).
for _word, _canonical in list(HIGH_GOTHIC.items()):
    HIGH_GOTHIC.setdefault(_word.replace("C", "K").replace("V", "W"), _canonical)

GOTHIC_TO_LATIN = dict(zip(
    "𐌰𐌱𐌲𐌳𐌴𐌵𐌶𐌷𐌸𐌹𐌺𐌻𐌼𐌽𐌾𐌿𐍀𐍂𐍃𐍄𐍅𐍆𐍇𐍈𐍉",
    ("a", "b", "g", "d", "e", "q", "z", "h", "th", "i",
     "k", "l", "m", "n", "j", "u", "p", "r", "s",
     "t", "w", "f", "ng", "hw", "o"),
))

# Convenient way to prepare examples from the subset shared with Latin.
LATIN_TO_GOTHIC = {
    letter: glyph for glyph, latin in GOTHIC_TO_LATIN.items()
    if len(latin) == 1 for letter in (latin,)
}


def normalize_identifier(word: str, dialect: str = "ru") -> str:
    """Canonicalize a single identifier; never feed strings/comments here."""
    if dialect not in DIALECTS:
        raise ValueError(f"unknown dialect: {dialect}")
    if dialect == "ru":
        return word
    if dialect == "gothic":
        word = "".join(GOTHIC_TO_LATIN.get(c, c) for c in word)
    return HIGH_GOTHIC.get(word.upper(), word)


def write_gothic(word: str) -> str:
    """Render ASCII into Gothic script for examples/tests (c -> k, v -> w)."""
    word = word.lower().replace("c", "k").replace("v", "w")
    return "".join(LATIN_TO_GOTHIC.get(char, char) for char in word)
