# References:
#   https://docs.pytest.org/en/stable/how-to/monkeypatch.html

import pytest

from jarvis import wildfire

URL = "https://example.com/MapServer/0"


def fake_server(total, page_size):
    """Stands in for an ArcGIS layer holding `total` features, served `page_size` at a time."""
    features = [{"type": "Feature", "id": i} for i in range(total)]

    def get_json(url, params):
        if url == URL:
            return {"maxRecordCount": page_size, "fields": [{"name": "OBJECTID", "type": "esriFieldTypeOID"}]}
        if params.get("returnCountOnly"):
            return {"count": total}
        start = params["resultOffset"]
        return {"features": features[start:start + params["resultRecordCount"]]}

    return get_json


def test_pages_until_every_feature_is_downloaded(monkeypatch):
    monkeypatch.setattr(wildfire, "get_json", fake_server(total=5, page_size=2))
    collection = wildfire.fetch_layer(URL)
    assert [feature["id"] for feature in collection["features"]] == [0, 1, 2, 3, 4]


def test_missing_features_raise(monkeypatch):
    get_json = fake_server(total=5, page_size=2)

    def server_that_stops_early(url, params):
        if params.get("resultOffset", 0) >= 4:
            return {"features": []}
        return get_json(url, params)

    monkeypatch.setattr(wildfire, "get_json", server_that_stops_early)
    with pytest.raises(RuntimeError, match="5 features but 4"):
        wildfire.fetch_layer(URL)


def test_feature_added_during_download_is_kept(monkeypatch):
    get_json = fake_server(total=6, page_size=2)
    count_calls = []

    def growing_server(url, params):
        if params.get("returnCountOnly"):
            count_calls.append(1)
            first_count = len(count_calls) == 1
            return {"count": 5 if first_count else 6}
        return get_json(url, params)

    monkeypatch.setattr(wildfire, "get_json", growing_server)
    collection = wildfire.fetch_layer(URL)
    assert len(collection["features"]) == 6


def test_duplicate_features_raise(monkeypatch):
    get_json = fake_server(total=5, page_size=2)

    def server_that_repeats_a_page(url, params):
        if params.get("resultOffset") == 2:
            params = {**params, "resultOffset": 0}
        return get_json(url, params)

    monkeypatch.setattr(wildfire, "get_json", server_that_repeats_a_page)
    with pytest.raises(RuntimeError, match="more than one page"):
        wildfire.fetch_layer(URL)
