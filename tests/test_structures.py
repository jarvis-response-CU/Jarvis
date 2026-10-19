# References:
#   https://docs.pytest.org/en/stable/how-to/tmp_path.html
#   https://en.wikipedia.org/wiki/Centroid#Of_a_polygon

import json

import pandas as pd
import pytest

from jarvis.structures import build, ring_area_and_center


def square(west, south, size):
    east = west + size
    north = south + size
    return [[west, south], [east, south], [east, north], [west, north], [west, south]]


def parcel(parcel_no, *rings):
    if len(rings) == 1:
        geometry = {"type": "Polygon", "coordinates": [rings[0]]}
    else:
        geometry = {"type": "MultiPolygon", "coordinates": [[ring] for ring in rings]}
    return {"type": "Feature", "properties": {"PARCEL_NO": parcel_no}, "geometry": geometry}


def building(strap, section, building_class, year, finished_sf, roof="", wall=""):
    return {
        "strap": strap,
        "bld_num": 1,
        "section_num": section,
        "bldgClassDscr": building_class,
        "builtYear": year,
        "TotalFinishedSF": finished_sf,
        "Roof_CoverDscr": roof,
        "ExtWallDscrPrim": wall,
    }


@pytest.fixture
def raw_dir(tmp_path):
    straps = [f"R000000{number}" for number in range(1, 8)]
    pd.DataFrame({
        "strap": straps,
        "bldAcutalVal": [500000, 0, 300000, 200000, 100000, 400000, 50000],
        "LandAcutalVal": [900000, 100000, 100000, 100000, 100000, 100000, 100000],
    }).to_csv(tmp_path / "values.csv", index=False)
    pd.DataFrame({
        "strap": straps,
        "Parcelno": ["111", "222", "", "444", "000000000000", "666", "777"],
    }).to_csv(tmp_path / "account_parcels.csv", index=False)

    single_family = "SINGLE FAM RES IMPROVEMENTS"
    farm_house = "FARM/RANCH RESIDENTIAL IMPROVEMENTS"
    shed = "OTHER BLDGS.-AGRICULTURAL"
    wood = "Frame Wood/Shake"
    pd.DataFrame([
        # R0000001: a house listed twice (two basement types), then a smaller shed.
        building("R0000001", 1, single_family, 1995, 3000, "Asphalt", wood),
        building("R0000001", 1, single_family, 1995, 3000, "Asphalt", wood),
        {**building("R0000001", 1, shed, 2010, 400, "Metal"), "bld_num": 2},
        # R0000006: a small newer section is listed before the house itself.
        building("R0000006", 2, shed, 2024, 0),
        building("R0000006", 1, farm_house, 1982, 2825, "Asphalt", wood),
        # R0000007: the assessor's 0 for an unknown year.
        building("R0000007", 1, "OTHER COMM POSSESSORY INTEREST", 0, 1000),
    ]).to_csv(tmp_path / "buildings.csv", index=False)

    features = [
        parcel("111", square(-105.0, 40.0, 0.001)),
        parcel("222", square(-105.1, 40.0, 0.001)),
        parcel("", square(-105.2, 40.0, 0.001)),
        # 444's large piece sits between two small ones.
        parcel(
            "444",
            square(-105.3, 40.0, 0.0002),
            square(-105.29, 40.0, 0.002),
            square(-105.28, 40.0, 0.0002),
        ),
        parcel("000000000000", square(-105.4, 40.0, 0.001)),
        parcel("666", square(-105.5, 40.0, 0.001)),
        parcel("777", square(-105.6, 40.0, 0.001)),
    ]
    collection = {"type": "FeatureCollection", "features": features}
    (tmp_path / "parcels.geojson").write_text(json.dumps(collection))
    return tmp_path


def test_keeps_properties_with_a_building_value_and_a_location(raw_dir):
    table = build(raw_dir).set_index("strap")
    # R0000002 has no building value. R0000003 and R0000005 have blank parcel
    # numbers, which must not match the parcels with the same blank numbers.
    assert list(table.index) == ["R0000001", "R0000004", "R0000006", "R0000007"]
    assert table.loc["R0000001", "bld_value"] == 500000


def test_largest_building_supplies_class_and_materials(raw_dir):
    house = build(raw_dir).set_index("strap").loc["R0000001"]
    assert house["bldg_class"] == "SINGLE FAM RES IMPROVEMENTS"
    assert house["built_year"] == 1995
    assert house["roof"] == "Asphalt"
    assert house["wall"] == "Frame Wood/Shake"


def test_largest_section_wins_even_when_listed_after_a_smaller_one(raw_dir):
    house = build(raw_dir).set_index("strap").loc["R0000006"]
    assert house["bldg_class"] == "FARM/RANCH RESIDENTIAL IMPROVEMENTS"
    assert house["built_year"] == 1982
    assert house["wall"] == "Frame Wood/Shake"


def test_unknown_built_year_is_left_blank(raw_dir):
    table = build(raw_dir).set_index("strap")
    assert pd.isna(table.loc["R0000007", "built_year"])


def test_property_without_a_building_row_has_unknown_materials(raw_dir):
    table = build(raw_dir).set_index("strap")
    assert pd.isna(table.loc["R0000004", "roof"])
    assert pd.isna(table.loc["R0000004", "wall"])


def test_location_is_the_center_of_the_largest_piece(raw_dir):
    table = build(raw_dir).set_index("strap")
    assert table.loc["R0000001", ["lat", "lon"]].tolist() == pytest.approx([40.0005, -104.9995])
    assert table.loc["R0000004", ["lat", "lon"]].tolist() == pytest.approx([40.001, -105.289])


def test_center_of_an_l_shaped_outline():
    # The true center differs from both the corner average and the bounding box center.
    west, south, size = -105.0, 40.0, 0.01
    half = size / 2
    outline = [
        [west, south], [west + size, south], [west + size, south + half],
        [west + half, south + half], [west + half, south + size], [west, south + size],
        [west, south],
    ]
    expected_center = pytest.approx((south + 5 * size / 12, west + 5 * size / 12))

    area, center = ring_area_and_center(outline)
    assert center == expected_center
    # Going around the other way gives the same answer.
    assert ring_area_and_center(outline[::-1]) == (pytest.approx(area), expected_center)
