# References:
#   https://docs.pytest.org/en/stable/how-to/monkeypatch.html

import pandas as pd
import pytest

from jarvis.simulations.fire import damage_run
from jarvis.simulations.fire.damage_run import estimate_damage, load_structures

# A 3 x 3 grid of 0.001-degree cells. Row 0 is the south edge.
RESULT = {
    "bounds": {"south": 40.0, "west": -105.0, "north": 40.003, "east": -104.997},
    "rows": 3,
    "cols": 3,
    "duration_min": 20,
    "cells": [0, 0, 0, 1, 1, 10],
}


def property_at(lat, lon, value, factor):
    return {"lat": lat, "lon": lon, "bld_value": value, "loss_factor": factor}


def test_only_properties_in_burned_cells_count_and_they_count_from_ignition():
    structures = pd.DataFrame([
        property_at(40.0005, -104.9995, 100, 0.5),  # cell (0, 0), burning from minute 0
        property_at(40.0015, -104.9985, 200, 0.25),  # cell (1, 1), from minute 10
        property_at(40.0025, -104.9975, 400, 1.0),  # cell (2, 2), never burns
        property_at(41.0, -105.0, 800, 1.0),  # nowhere near the grid
    ])
    damage = estimate_damage(RESULT, structures)

    assert damage["properties"] == 2
    assert damage["exposed_value"] == 300
    assert damage["expected_loss"] == 100
    by_minute = damage["by_minute"]
    assert len(by_minute["properties"]) == 21
    assert [by_minute["properties"][minute] for minute in (0, 9, 10, 20)] == [1, 1, 2, 2]
    assert [by_minute["expected_loss"][minute] for minute in (0, 9, 10, 20)] == [50, 50, 100, 100]


def test_missing_county_files_raise_file_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("JARVIS_DATABASE_URL", raising=False)
    load_structures.cache_clear()
    with pytest.raises(FileNotFoundError):
        load_structures()
    load_structures.cache_clear()


def test_saved_table_is_used_and_given_loss_factors(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("JARVIS_DATABASE_URL", raising=False)
    (tmp_path / "processed").mkdir()
    pd.DataFrame({
        "lat": [40.0], "lon": [-105.0], "bld_value": [100],
        "wall": ["Frame Wood/Shake"], "roof": [None],
    }).to_csv(tmp_path / "processed" / "structures.csv", index=False)
    load_structures.cache_clear()
    try:
        table = load_structures()
    finally:
        load_structures.cache_clear()
    # The tuned wood-siding factor; the blank roof falls back to siding alone.
    assert table["loss_factor"].tolist() == [0.606]


def test_database_is_read_when_configured(monkeypatch):
    monkeypatch.setenv("JARVIS_DATABASE_URL", "postgresql://example")
    queries = []

    def fake_read_sql(query, engine):
        queries.append(query)
        return pd.DataFrame({
            "lat": [40.0], "lon": [-105.0], "bld_value": [100],
            "wall": ["Frame Wood/Shake"], "roof": [None],
        })

    monkeypatch.setattr(pd, "read_sql", fake_read_sql)
    monkeypatch.setattr(damage_run, "engine", lambda: None)
    load_structures.cache_clear()
    try:
        table = load_structures()
    finally:
        load_structures.cache_clear()
    assert "boulder.structures" in queries[0]
    assert table["loss_factor"].tolist() == [0.606]
