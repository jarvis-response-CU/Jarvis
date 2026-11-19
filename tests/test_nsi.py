import pytest

from jarvis.simulations.common import nsi

BOUNDS = {"south": 40.01, "west": -105.04, "north": 40.04, "east": -105.01}


def feature(lon, lat, **props):
    return {"geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props}


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path))
    return tmp_path


def test_normalize_maps_public_fields_and_prefers_fullrep():
    table = nsi.normalize([
        feature(-105.02, 40.02, occtype="RES1-1SNB", bldgtype="W", sqft=1500, found_type="S",
                found_ht=2.0, num_story=1, val_struct=100, fullrep=250, med_yr_blt=1980),
        feature(-105.03, 40.03, bldgtype="M", val_struct=90),
        feature(-105.03, 40.03, bldgtype="M"),
    ])
    assert table["bld_value"].tolist() == [250, 90]
    assert table.loc[0, ["occupancy", "building_type", "foundation_height_ft", "stories"]].tolist() == [
        "RES1-1SNB", "W", 2.0, 1,
    ]
    assert {"lat", "lon", "replacement_value", "median_year_built"} <= set(table.columns)


def test_cache_is_used_so_each_area_is_fetched_once(data_dir):
    calls = []

    def fetch(bounds):
        calls.append(bounds)
        return [feature(bounds["west"] + 0.01, bounds["south"] + 0.01, bldgtype="W", fullrep=100)]

    first = nsi.load_nsi(BOUNDS, fetch=fetch)
    count = len(calls)
    second = nsi.load_nsi(BOUNDS, fetch=fetch)
    assert count == len(calls) > 0
    assert len(first) == len(second) > 0
    assert (data_dir / "processed" / "nsi" / nsi.NSI_RELEASE).is_dir()


def test_empty_tiles_are_not_cached(data_dir):
    calls = []

    def fetch(bounds):
        calls.append(bounds)
        return []

    nsi.load_nsi(BOUNDS, fetch=fetch)
    first = len(calls)
    nsi.load_nsi(BOUNDS, fetch=fetch)
    assert len(calls) == 2 * first


def test_only_structures_inside_bounds_are_returned(data_dir):
    def fetch(bounds):
        return [feature(-105.02, 40.02, fullrep=1), feature(-105.5, 40.5, fullrep=1)]

    table = nsi.load_nsi(BOUNDS, fetch=fetch)
    assert len(table[(table["lon"] < -105.04) | (table["lat"] > 40.04)]) == 0


def test_fetch_failure_raises_nsi_unavailable(data_dir):
    def fetch(bounds):
        raise OSError("offline")

    with pytest.raises(nsi.NsiUnavailable):
        nsi.load_nsi(BOUNDS, fetch=fetch)


def test_oversized_area_is_refused_without_requests(data_dir):
    def fetch(bounds):
        raise AssertionError("should not fetch")

    with pytest.raises(nsi.NsiUnavailable):
        nsi.load_nsi({"south": 30, "west": -110, "north": 40, "east": -100}, fetch=fetch)


def test_request_posts_a_polygon_to_the_configured_root(monkeypatch):
    monkeypatch.setenv("JARVIS_NSI_API_ROOT", "https://example.test/nsiapi/")
    seen = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, *args):
            return b'{"features": [{"properties": {}}]}'

    def urlopen(request, timeout):
        seen.append(request)
        return Response()

    monkeypatch.setattr(nsi.urllib.request, "urlopen", urlopen)
    assert len(nsi.fetch_tile(BOUNDS)) == 1
    request = seen[0]
    assert request.full_url == "https://example.test/nsiapi/structures?fmt=fc"
    assert request.get_method() == "POST"
    ring = nsi.json.loads(request.data)["coordinates"][0]
    assert ring[0] == ring[-1] and [-105.04, 40.01] in ring


def test_response_without_features_is_an_error(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, *args):
            return b'{"message": "nope"}'

    monkeypatch.setattr(nsi.urllib.request, "urlopen", lambda request, timeout: Response())
    with pytest.raises(ValueError):
        nsi.fetch_tile(BOUNDS)
