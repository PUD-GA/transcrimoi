"""Emplacements des tests : séparer code partageable et données locales privées."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
FIXTURES = TESTS / "fixtures"
EXPERIMENTS = TESTS / "experiments"
EXPERIMENT_MODELS = TESTS / "models"
SOURCES = TESTS / "sources"
SYNTH = SOURCES / "synth"
REAL = SOURCES / "reel"
WAMATIPSIA = SOURCES / "wamatipsia"
RUNS = TESTS / "runs"
