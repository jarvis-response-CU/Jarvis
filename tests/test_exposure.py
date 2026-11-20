import pandas as pd

from jarvis.simulations.common.exposure import exposure_summary, structures_on_grid

RESULT = {
    "bounds": {"south": 40.0, "west": -105.0, "north": 40.003, "east": -104.997},
    "rows": 3,
    "cols": 3,
}


def table():
    return pd.DataFrame({
        "lat": [40.0005, 40.0025, 41.0, 40.003],
        "lon": [-104.9995, -104.9975, -105.0, -104.998],
        "bld_value": [100.0, 400.0, 800.0, 50.0],
    })


def test_structures_outside_the_grid_are_dropped_and_rows_are_integers():
    placed = structures_on_grid(RESULT, table())
    assert placed[["row", "col"]].values.tolist() == [[0, 0], [2, 2]]
    assert placed["row"].dtype.kind == "i"


def test_input_table_is_not_modified():
    structures = table()
    structures_on_grid(RESULT, structures)
    assert "row" not in structures.columns


def test_summary_counts_and_affected_subset():
    placed = structures_on_grid(RESULT, table())
    summary = exposure_summary("nsi_2026", placed, [True, False])
    assert summary == {
        "inventory": "nsi_2026",
        "properties_on_grid": 2,
        "building_value_on_grid": 500,
        "properties_affected": 1,
        "affected_building_value": 100,
    }


def test_summary_without_affected_omits_affected_fields():
    summary = exposure_summary("nsi_2026", structures_on_grid(RESULT, table()))
    assert "properties_affected" not in summary
