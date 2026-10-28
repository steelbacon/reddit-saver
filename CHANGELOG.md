# Reddit Saver changelog

## v1.3 (28 Oct 2026)
- Personal names moved out of the code into an optional `settings.json` next to the script, for example `{"name": "Sam", "assistant": "Nova"}`. Without it, the page uses "My" and "Download for AI".
- `settings.json` is never uploaded to GitHub.

## v1.2 (28 Oct 2026)
- **Notes:** every item has an **Add note** button, for why you saved it. Notes show in an amber box and are searchable.
- Notes are kept in your browser. **Back up notes** saves them as `notes.json`; put that file in the **Reddit Saved** folder and the next run builds them into the page, so they're safe even if browser data is cleared.
- **Download for your assistant:** one Markdown file with every item grouped by subreddit, with your notes, and text, dates and top comments when available.
- Tip: Ctrl+Enter or Esc finishes a note.

## v1.1 (28 Oct 2026)
- Each item now shows a readable title taken from its link, even when full posts can't be fetched.
- Comments show a note that the title is from the post they were saved in.
- New start file: **Make page without fetching.bat**, which makes the page straight away without asking Reddit for anything.
- Version number now shows at the bottom of the page.
- Why: on the first real run, Reddit refused to hand out full posts without an API login (code 403).

## v1.0 (28 Oct 2026)
- First version.
- Reads `saved_posts.csv` and `saved_comments.csv` from the Reddit export zip.
- Fetches each saved post and its comment thread slowly (7 seconds apart) and keeps them on the PC.
- Builds a dark-mode page: subreddits on the left, search, Posts / Comments filter, sorting by date or save order, and threaded conversations with your saved comment marked.
- Windows start file: drag the export zip onto **Start Reddit Saver.bat**.
