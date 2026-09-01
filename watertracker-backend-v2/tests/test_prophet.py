from __future__ import annotations

from datetime import date

from app.services.prophet_service import (
    _periode_to_date,
    _periode_to_year_semester,
    predire_tarissement,
)


def test_periode_to_year_semester():
    assert _periode_to_year_semester("2024-S1") == (2024, 1)
    assert _periode_to_year_semester("2024-S2") == (2024, 2)
    assert _periode_to_year_semester("2023-S2") == (2023, 2)


def test_periode_to_year_semester_invalid():
    assert _periode_to_year_semester("2024") is None
    assert _periode_to_year_semester("abc-S1") is None
    assert _periode_to_year_semester("2024-Q1") is None


def test_periode_to_date():
    assert _periode_to_date("2024-S1") == date(2024, 1, 1)
    assert _periode_to_date("2024-S2") == date(2024, 7, 1)


def test_prophet_unavailable_raises():
    """Sans données (moins de 3 périodes), on renvoie une erreur explicite."""
    import pandas as pd
    from unittest.mock import MagicMock

    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = []
    out = predire_tarissement(db, source_id=1)
    assert "erreur" in out
