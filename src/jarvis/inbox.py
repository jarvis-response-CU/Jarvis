# References:
#   https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_sql.html
#   https://docs.sqlalchemy.org/en/20/dialects/postgresql.html
#   https://supabase.com/docs/guides/database/connecting-to-postgres

"""Load spreadsheets dropped into data/inbox/ into the database.

Each folder in data/inbox/ becomes one table in the database's "inbox" schema
(data/inbox/emdat/ -> inbox.emdat). Every run rebuilds those tables from all
files currently in the folder, so uploading a corrected file or another month
of data never duplicates rows.

Run it with:  python -m jarvis.inbox
"""

import os
import re

import pandas as pd
from sqlalchemy import create_engine, text

from jarvis.config import PROJECT_ROOT

INBOX_DIR = PROJECT_ROOT / "data" / "inbox"
READERS = {".csv": pd.read_csv, ".xlsx": pd.read_excel}
POSTGRES_NAME_LIMIT = 63
# Supabase publishes the "public" schema through its web API, so uploads go
# in their own schema that the API doesn't expose.
SCHEMA = "inbox"


def clean_name(text):
    """Turn a spreadsheet header into a database-friendly name.

    "AID Contribution ('000 US$)" -> "aid_contribution_000_us"
    """
    name = re.sub(r"[^a-z0-9]+", "_", str(text).lower())
    name = name.strip("_")
    if not name:
        name = "column"
    if name[0].isdigit():
        name = f"col_{name}"
    return name[:POSTGRES_NAME_LIMIT]


def clean_columns(columns):
    """Clean every header, numbering any that end up with the same name."""
    cleaned = []
    for column in columns:
        name = clean_name(column)
        candidate = name
        count = 2
        while candidate in cleaned:
            candidate = f"{name}_{count}"
            count += 1
        cleaned.append(candidate)
    return cleaned


def read_folder(folder):
    """Read every CSV/Excel file in a folder into one table, or None if empty."""
    frames = []
    for path in sorted(folder.iterdir()):
        if path.name.startswith(".") or path.name.lower() == "readme.md":
            continue
        reader = READERS.get(path.suffix.lower())
        if reader is None:
            print(f"  skipped {path.name}: only .csv and .xlsx files are loaded")
            continue
        frame = reader(path)
        frame["source_file"] = path.name
        frames.append(frame)

    if not frames:
        return None
    table = pd.concat(frames, ignore_index=True)
    table.columns = clean_columns(table.columns)
    return table


def sync(engine, inbox_dir=INBOX_DIR, schema=SCHEMA):
    """Rebuild one table per inbox folder. Returns {table name: row count}."""
    if schema:
        with engine.begin() as connection:
            connection.execute(text(f"create schema if not exists {schema}"))

    loaded = {}
    for folder in sorted(inbox_dir.iterdir()):
        if not folder.is_dir():
            continue
        table = read_folder(folder)
        if table is None:
            continue
        table_name = clean_name(folder.name)
        table.to_sql(
            table_name,
            engine,
            schema=schema,
            if_exists="replace",
            index=False,
            chunksize=1000,
        )

        full_name = table_name
        if schema:
            full_name = f"{schema}.{table_name}"
        loaded[full_name] = len(table)
    return loaded


def database_url():
    url = os.getenv("JARVIS_DATABASE_URL")
    if not url:
        raise RuntimeError("JARVIS_DATABASE_URL is not set (see .env.example)")
    # Supabase hands out postgresql:// URLs; SQLAlchemy needs to be told to use psycopg.
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def main():
    engine = create_engine(database_url())
    loaded = sync(engine)
    if not loaded:
        print("No files found in data/inbox/")
    for table_name, rows in loaded.items():
        print(f"loaded {rows} rows into {table_name}")


if __name__ == "__main__":
    main()
