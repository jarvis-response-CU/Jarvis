# Library

A place for anything that isn't a spreadsheet: PDFs, reports, and links.
Everything here also shows up in the database so it's easy to find later.

## Adding a PDF or other document

1. Open this folder (`data/library`) on GitHub.
2. Click "Add file", then "Upload files".
3. Drag your file in and click "Commit changes".

You can make subfolders to stay organized, for example `reports/` or `papers/`.
Files have to be under 25 MB, and the repo is public, so only add things that are okay to share.

## Adding an API or website link

1. Click `apis.txt` (for APIs) or `websites.txt` (for regular websites).
2. Click the pencil icon to edit.
3. Add your link on a new line. You can put a short note after it, like
   `https://api.weather.gov  National Weather Service forecasts`
4. Click "Commit changes".

## Where it shows up in the database

In Supabase, open Table Editor and switch the schema dropdown to `inbox`:

- `library_files` lists every document, with a link to open it on GitHub.
- `library_links` lists every link, with your note and which list it came from.
