"""Lightweight runtime locations; no network/training imports in serving."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ART=ROOT/'artifacts'
DATA=ART/'data'
