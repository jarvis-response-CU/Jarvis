# References:
#   https://docs.python.org/3/library/pathlib.html
#   https://docs.python.org/3/library/urllib.parse.html
#   https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_sql.html

"""Catalog what's in data/library/ so it can be found from the database.

- Documents (PDFs etc.) stay in GitHub; library_files gets one row per file
  with a link to open it there.
- Every .txt file is a list of links, one per line ("URL  optional note");
  library_links gets one row per line, tagged with the file name (apis, websites).
"""

import re
from urllib.parse import quote

import pandas as pd

from jarvis.config import PROJECT_ROOT

LIBRARY_DIR = PROJECT_ROOT / "data" / "library"
GITHUB_FILE_URL = "https://github.com/jarvis-response-CU/Jarvis/blob/main/data/library/"
URL_PATTERN = re.compile(r"https?://\S+")


def read_links(path):
    """One row per non-empty line; lines starting with # are instructions, not links."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        match = URL_PATTERN.search(line)
        url = None
        note = line
        if match:
            url = match.group()
            note = line.replace(url, "").strip(" -–:|\t")

        rows.append({"list": path.stem, "url": url, "note": note or None})
    return rows


def catalog(library_dir=LIBRARY_DIR):
    """Return (files table, links table) for everything in the library folder."""
    files = []
    links = []
    for path in sorted(library_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith(".") or path.name.lower() == "readme.md":
            continue
        if path.suffix.lower() == ".txt":
            links.extend(read_links(path))
            continue

        relative = path.relative_to(library_dir).as_posix()
        files.append({
            "file_name": path.name,
            "folder": path.parent.relative_to(library_dir).as_posix(),
            "size_kb": round(path.stat().st_size / 1024, 1),
            "github_url": GITHUB_FILE_URL + quote(relative),
        })

    files_table = pd.DataFrame(files, columns=["file_name", "folder", "size_kb", "github_url"])
    links_table = pd.DataFrame(links, columns=["list", "url", "note"])
    return files_table, links_table


def sync_library(engine, library_dir=LIBRARY_DIR, schema="inbox"):
    """Rebuild library_files and library_links. Returns {table name: row count}."""
    files_table, links_table = catalog(library_dir)
    loaded = {}
    for name, table in [("library_files", files_table), ("library_links", links_table)]:
        table.to_sql(name, engine, schema=schema, if_exists="replace", index=False)

        full_name = name
        if schema:
            full_name = f"{schema}.{name}"
        loaded[full_name] = len(table)
    return loaded
