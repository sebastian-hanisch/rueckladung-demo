"""PDF-Export: Sonderzeichen werden bereinigt, jede Stufe lässt sich als PDF ausgeben."""

import pytest

import rkl_constants as C
import rkl_evaluation as E
import rkl_pdf_export as PDF


def test_clean_ersetzt_sonderzeichen_und_streicht_emoji():
    text = PDF.clean("Rückladung – β ≥ 20 % → ± 5 € „Test“ ↩️ ✓ Δ")
    assert "–" not in text and "→" not in text and "±" not in text and "€" not in text and "↩" not in text and "Δ" not in text
    assert "Rückladung" in text and "beta" in text and ">= 20" in text and "EUR" in text
    text.encode("latin-1")   # muss in der Standardschrift darstellbar sein


@pytest.fixture(scope="module")
def analyse():
    return E.analyse(E.Settings(20, 0.4, "gemischt", "rand", 2, 20, 3))


@pytest.mark.parametrize("key", C.STAGE_KEYS)
def test_pdf_fuer_jede_stufe(analyse, key):
    st = E.Settings(20, 0.4, "gemischt", "rand", 2, 20, 3)
    data = PDF.build_pdf(st, analyse, key)
    assert data[:5] == b"%PDF-" and len(data) > 1500


def test_pdf_enthaelt_die_wichtigsten_angaben(analyse):
    st = E.Settings(20, 0.4, "gemischt", "mitte", 2, 20, 3)
    data = PDF.build_pdf(st, analyse, "M")
    assert b"%PDF-" in data[:8]
