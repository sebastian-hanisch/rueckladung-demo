"""Kopietest: der Zufallsgenerator ist SplitMix64 mit festen Ausgaben und gleich dem Original aus ab-test-demo, wenn der Nachbarordner da ist."""

import importlib.util
from pathlib import Path

import pytest

from rkl_rng import SplitMix64

ROOT = Path(__file__).resolve().parent.parent


def test_feste_ausgaben_der_ersten_werte():
    # Referenzwerte des SplitMix64-Algorithmus (Seed 0, nach der Definition von Vigna; hier einmal von Hand nachgerechnet und fest eingetragen)
    g = SplitMix64(0)
    assert [g.next() for _ in range(3)] == [16294208416658607535, 7960286522194355700, 487617019471545679]


def test_uniform_liegt_im_halboffenen_intervall_und_below_im_bereich():
    g = SplitMix64(12345)
    for _ in range(2000):
        assert 0.0 <= g.uniform() < 1.0
    assert all(0 <= g.below(7) < 7 for _ in range(2000))
    assert g.below(1) == 0


def test_gleicher_seed_gleiche_folge_und_seed_wird_auf_64_bit_gekuerzt():
    a, b = SplitMix64(99), SplitMix64(99 + (1 << 64))
    assert [a.next() for _ in range(5)] == [b.next() for _ in range(5)]


def test_gleich_dem_original_aus_ab_test_demo_wenn_vorhanden():
    orig = ROOT.parent / "ab-test-demo" / "abt_rng.py"
    if not orig.exists():
        pytest.skip("ab-test-demo liegt nicht neben dem Repo")
    spec = importlib.util.spec_from_file_location("abt_rng_orig", orig)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except ImportError:
        pytest.skip("das Original braucht eine Bibliothek, die hier fehlt")
    cls = getattr(mod, "SplitMix64")
    a, b = SplitMix64(2026), cls(2026)
    assert [a.next() for _ in range(50)] == [b.next() for _ in range(50)]
    assert [a.uniform() for _ in range(50)] == [b.uniform() for _ in range(50)]
