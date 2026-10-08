# Adding data to the database

Drop a spreadsheet in a folder here and it goes into the database by itself.
No accounts, passwords, or installs needed — just GitHub.

## How to add a file

1. On GitHub, open the repo and click into **`data` → `inbox`**.
2. Open the folder your data belongs in (for example **`emdat`**).
   Need a new folder? See "Starting a new dataset" below.
3. Click **Add file → Upload files** (top right).
4. Drag your file onto the page.
5. Scroll down and click the green **Commit changes** button.
6. Wait about a minute, then click the **Actions** tab at the top of the repo.
   - Green check ✅ = your data is in the database. You're done.
   - Red X ❌ = something went wrong. Message Brody with the file name.

## Rules

- **File types:** `.csv` or `.xlsx` only. Anything else is skipped.
- **One kind of data per folder.** Every file in a folder becomes one table, so
  files in the same folder should have the same column headers.
- **Fixing a file:** upload the corrected file with the **same name** — it
  replaces the old one. Don't upload both versions.
- **Removing data:** open the file on GitHub, click the trash-can icon, and commit.
  The table is rebuilt without it.
- **Public repo:** anyone on the internet can see these files. Only upload
  public data you're allowed to share. Never upload passwords or personal info.
- **Size:** GitHub's upload page takes files up to 25 MB.

## Starting a new dataset

On the **Upload files** page you can't make a folder, so do this instead:

1. In `data/inbox`, click **Add file → Create new file**.
2. In the name box type your folder name, a slash, then `README.md`
   — for example `fire_history/README.md`.
3. In the big text box, write one line about what the data is and where it's from.
4. Click **Commit changes**. Your folder now exists — upload files into it as above.

Use lowercase and underscores for folder names (`fire_history`, not `Fire History`).
The folder `fire_history` becomes the table `inbox.fire_history` in the database.
