# Reddit Saver

A small personal tool that turns **my own** Reddit saved posts and comments into one offline, dark-mode page on my PC, sorted by subreddit and date, with search and personal notes.

## What it does

1. Reads `saved_posts.csv` and `saved_comments.csv` from my official Reddit data export (reddit.com/settings/data-request).
2. Optionally reads each saved post and its comment thread, slowly (one request every 7 seconds), and keeps a copy on my own computer.
3. Builds a local HTML page: subreddits on the left, search, filters, threaded comments, and a note on each item for why I saved it.

## What it does not do

- It is **read-only**. It never posts, comments, votes, or sends messages.
- It only reads **my own** saved list and the threads those items belong to. It does not collect data about other users.
- Nothing is shared, sold, published, or used to train AI models. Everything stays on my own PC.
- Light use only: a run now and then, well inside Reddit's rate limits.

## Planned API use

If Reddit approves Data API access, the tool will use the official API with OAuth as a "script" type app on my own account, through the PRAW library, instead of public pages. That gives the full saved list with titles, dates and comment threads. Same rules as above: read-only, my own account, personal use.

## How to run it (Windows)

1. Install Python 3 from python.org.
2. Drag the Reddit export zip onto `Start Reddit Saver.bat`, or onto `Make page without fetching.bat` for a links-only page.
3. The page opens when it's done, from a `Reddit Saved` folder next to the zip.

Only Python's built-in modules are used. See `CHANGELOG.md` for versions.
