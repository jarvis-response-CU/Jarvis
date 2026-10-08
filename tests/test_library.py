import pandas as pd
from sqlalchemy import create_engine

from jarvis.library import catalog, read_links, sync_library


def make_library(tmp_path):
    (tmp_path / "apis.txt").write_text(
        "# instructions line\n"
        "https://api.weather.gov  NWS forecasts\n"
        "\n"
        "NOAA tides - https://tidesandcurrents.noaa.gov/api/\n"
        "ask Ben about the county data\n"
    )
    (tmp_path / "websites.txt").write_text("https://landfire.gov\n")
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "Marshall Fire report.pdf").write_bytes(b"%PDF-1.4 fake")
    (tmp_path / "README.md").write_text("ignored")
    return tmp_path


def test_read_links_splits_url_and_note(tmp_path):
    rows = read_links(make_library(tmp_path) / "apis.txt")
    assert rows == [
        {"list": "apis", "url": "https://api.weather.gov", "note": "NWS forecasts"},
        {"list": "apis", "url": "https://tidesandcurrents.noaa.gov/api/", "note": "NOAA tides"},
        {"list": "apis", "url": None, "note": "ask Ben about the county data"},
    ]


def test_catalog_lists_documents_with_github_links(tmp_path):
    files, links = catalog(make_library(tmp_path))

    assert list(files["file_name"]) == ["Marshall Fire report.pdf"]
    assert files["folder"][0] == "reports"
    assert files["github_url"][0].endswith("/data/library/reports/Marshall%20Fire%20report.pdf")
    assert sorted(set(links["list"])) == ["apis", "websites"]
    assert len(links) == 4


def test_sync_library_writes_both_tables(tmp_path):
    engine = create_engine("sqlite://")
    loaded = sync_library(engine, make_library(tmp_path), schema=None)

    assert loaded == {"library_files": 1, "library_links": 4}
    stored = pd.read_sql("select * from library_links", engine)
    assert "https://landfire.gov" in set(stored["url"])


def test_empty_library_still_creates_tables(tmp_path):
    engine = create_engine("sqlite://")
    loaded = sync_library(engine, tmp_path, schema=None)
    assert loaded == {"library_files": 0, "library_links": 0}
