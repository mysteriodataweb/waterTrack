from __future__ import annotations

import sys
from pathlib import Path

# Rendre le package `app` importable depuis les tests.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
