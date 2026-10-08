# References:
#   https://docs.sqlalchemy.org/en/20/dialects/sqlite.html
#   https://docs.pytest.org/en/stable/how-to/tmp_path.html

import pandas as pd
import pytest
from sqlalchemy import create_engine

from jarvis.inbox import clean_columns, clean_name, database_url, sync


def make_inbox(tmp_path):
    fires = tmp_path / "fire_history"
    fires.mkdir()
    first_file = pd.DataFrame({"Fire Name": ["Marshall", "Calwood"], "Acres ('000)": [6, 10]})
    first_file.to_csv(fires / "a.csv", index=False)
    second_file = pd.DataFrame({"Fire Name": ["Cameron Peak"], "Acres ('000)": [208]})
    second_file.to_excel(fires / "b.xlsx", index=False)
    (fires / "notes.pdf").write_bytes(b"not a spreadsheet")
    (fires / "README.md").write_text("ignored")
    (tmp_path / "empty_folder").mkdir()
    return tmp_path


def test_clean_name_handles_messy_headers():
    assert clean_name("AID Contribution ('000 US$)") == "aid_contribution_000_us"
    assert clean_name("2020 Population") == "col_2020_population"
    assert clean_name("???") == "column"
    assert len(clean_name("x" * 100)) == 63


def test_duplicate_headers_get_numbered():
    assert clean_columns(["Name", "name", "NAME!"]) == ["name", "name_2", "name_3"]


def test_each_folder_becomes_one_table(tmp_path):
    engine = create_engine("sqlite://")
    # SQLite has no schemas, so the tests write plain tables.
    loaded = sync(engine, make_inbox(tmp_path), schema=None)

    assert loaded == {"fire_history": 3}
    table = pd.read_sql("select * from fire_history", engine)
    assert list(table.columns) == ["fire_name", "acres_000", "source_file"]
    assert set(table["source_file"]) == {"a.csv", "b.xlsx"}


def test_running_twice_does_not_duplicate_rows(tmp_path):
    engine = create_engine("sqlite://")
    inbox = make_inbox(tmp_path)
    sync(engine, inbox, schema=None)
    sync(engine, inbox, schema=None)
    count = pd.read_sql("select count(*) as n from fire_history", engine)["n"][0]
    assert count == 3


def test_database_url_switches_to_psycopg(monkeypatch):
    monkeypatch.setenv("JARVIS_DATABASE_URL", "postgresql://user:pw@host:5432/postgres")
    assert database_url() == "postgresql+psycopg://user:pw@host:5432/postgres"
    monkeypatch.delenv("JARVIS_DATABASE_URL")
    with pytest.raises(RuntimeError, match="not set"):
        database_url()
