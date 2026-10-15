"""Compatibility import: all evaluation and submission scoring lives in the package."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from decisionrobust.scoring import number, score, targeted_success, validate_scored_answers
