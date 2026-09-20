"""Validate the supplementary NVDA symbol data without NVDA or an engine."""
from pathlib import Path
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from generate_symbol_dictionary import content


def main():
    for language in ("en", "de"):
        path = ROOT / "nvda/addon/locale" / language / "symbols-openevv.dic"
        raw = path.read_text(encoding="utf-8")
        assert raw == content(language), f"Regenerate {path}"
        rows = {}
        header = False
        for line in raw.splitlines():
            if not line or line.startswith("#"):
                continue
            if line == "symbols:":
                assert not header
                header = True
                continue
            assert header
            char, name, level, preserve = line.split("\t")
            assert len(char) == 1 and char not in rows
            assert name.strip() == name and name and "?" not in name and "`" not in name
            name.encode("cp1252")  # Labels must reach the Western ECI boundary intact.
            assert not any(unicodedata.category(c).startswith("C") for c in name)
            assert level == "all" and preserve == "never"
            rows[char] = name
        assert set(rows) == set(map(chr, range(0x2500, 0x2580)))
        assert "\u2192" not in rows  # Use NVDA's existing localized arrows.
        expected = "Rahmenecke oben rechts" if language == "de" else "top right corner"
        assert rows["\u2510"] == expected
        print(f"PASS: {language}: 128 unique, encodable NVDA symbol labels; no existing symbol overrides")
    assert "UNICODE LICENSE V3" in (ROOT / "UNICODE-LICENSE.txt").read_text(encoding="utf-8")


if __name__ == "__main__":
    main()
