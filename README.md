# Bailey's Next Step

A weekly-updated board of jobs and apprenticeships for one young person in Milton Keynes:
a better job now, and an electrical or engineering apprenticeship next.

- **Board:** `index.html` + `assets/`, served by GitHub Pages. Statuses and notes stay in the
  viewer's browser (with Backup/Restore). No login, no tracking, asks search engines not to index.
- **Weekly run:** `.github/workflows/weekly.yml`, Saturday 09:00 UK (and "Run workflow" by hand).
  Runs the offline tests, then `python -m scout.run`, then commits `data/`.
- **Sources:** GOV.UK Find an Apprenticeship pages, Reed job pages, Rapier and Insight agency
  feeds. Each is read politely (one request at a time, with a pause between requests) and only
  where the site's robots rules and terms allow it.
- **Rules:** unknown pay, dates or requirements stay blank ("not stated"); a source failure is
  reported, never shown as "no vacancies"; adverts close only when the source says so, the page
  has gone, or the closing date has passed.

Run locally: `pip install -r requirements.txt`, then `python -m pytest`, then `python -m scout.run --dry-run`.
