"""
Reddit Saver: turns your Reddit data export into a dark-mode page of your
saved posts and comments, sorted by subreddit and date.

How to use (Windows):
    Drag your Reddit export zip onto "Start Reddit Saver.bat".

Or from a command window:
    python reddit_saver.py "C:\\path\\to\\export.zip"            (with full posts)
    python reddit_saver.py "C:\\path\\to\\export.zip" --no-fetch (links only, fast)

Only uses Python's built-in parts, so nothing extra needs installing.
Your password is never needed: the export already holds the list, and the
full posts are read from Reddit's public pages.
"""

import argparse
import csv
import html
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import webbrowser
import zipfile
from datetime import datetime, timezone

VERSION = "1.3"
USER_AGENT = f"windows:personal-saved-archiver:v{VERSION} (personal use)"
PERMALINK_RE = re.compile(r"/r/([^/]+)/comments/([a-z0-9]+)(?:/([^/?#]*))?(?:/([a-z0-9]+))?", re.I)


def say(msg=""):
    print(msg, flush=True)


# ---------------------------------------------------------------- reading the export

def find_csvs(source):
    """Return {'posts': text, 'comments': text} from a zip file or a folder."""
    found = {}

    def take(name, read):
        low = os.path.basename(name).lower()
        if low == "saved_posts.csv":
            found["posts"] = read()
        elif low == "saved_comments.csv":
            found["comments"] = read()

    if os.path.isdir(source):
        for root, _, files in os.walk(source):
            for f in files:
                path = os.path.join(root, f)
                take(f, lambda p=path: open(p, encoding="utf-8-sig", newline="").read())
    elif zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as z:
            for name in z.namelist():
                take(name, lambda n=name: z.read(n).decode("utf-8-sig"))
    else:
        raise SystemExit(f"I can't read this as a zip file or folder:\n  {source}")
    return found


def read_items(csv_text, kind, start_order):
    items = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        link = row.get("permalink") or next(
            (v for k, v in row.items() if "link" in k or "url" in k), "")
        if not link:
            continue
        if link.startswith("/"):
            link = "https://www.reddit.com" + link
        m = PERMALINK_RE.search(link)
        sub = m.group(1) if m else "(unknown)"
        item_id = row.get("id") or (m.group(4) or m.group(2) if m else link)
        item_id = re.sub(r"^t[13]_", "", item_id)
        items.append({
            "kind": kind, "id": item_id, "sub": sub, "link": link,
            "order": start_order + len(items),
            "slug_title": (m.group(3) or "").replace("_", " ").strip() if m else "",
        })
    return items


# ---------------------------------------------------------------- fetching full posts

class Blocked(Exception):
    pass


def fetch_json(url, max_comments, is_comment):
    params = f"?limit={max_comments}&raw_json=1" + ("&context=3" if is_comment else "")
    api_url = url.split("?")[0].rstrip("/") + "/.json" + params
    req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 60 * (attempt + 1)
                say(f"    Reddit says slow down. Waiting {wait} seconds...")
                time.sleep(wait)
                continue
            if e.code == 404:
                return None
            if e.code in (401, 403):
                raise Blocked(e.code)
            raise
    raise Blocked(429)


def clean(text):
    return html.unescape(text or "")


def trim_comments(children, budget, target_id):
    out, more = [], 0
    for child in children or []:
        kind, d = child.get("kind"), child.get("data", {})
        if kind == "more":
            more += d.get("count", 0) or len(d.get("children", []))
            continue
        if kind != "t1":
            continue
        if budget[0] <= 0:
            more += 1
            continue
        budget[0] -= 1
        replies = d.get("replies")
        sub_children = replies.get("data", {}).get("children", []) if isinstance(replies, dict) else []
        kids, kid_more = trim_comments(sub_children, budget, target_id)
        out.append({
            "id": d.get("id"), "author": d.get("author") or "[deleted]",
            "body": clean(d.get("body")), "created": d.get("created_utc"),
            "score": d.get("score"), "target": d.get("id") == target_id,
            "replies": kids, "more": kid_more,
        })
    return out, more


def parse_thread(raw, item, max_comments):
    post = raw[0]["data"]["children"][0]["data"]
    budget = [max_comments]
    target = item["id"] if item["kind"] == "comment" else None
    comments, more = trim_comments(raw[1]["data"]["children"], budget, target)
    data = {
        "title": clean(post.get("title")),
        "author": post.get("author") or "[deleted]",
        "post_created": post.get("created_utc"),
        "score": post.get("score"),
        "num_comments": post.get("num_comments"),
        "selftext": clean(post.get("selftext")),
        "url": "" if post.get("is_self") else clean(post.get("url")),
        "nsfw": bool(post.get("over_18")),
        "comments": comments, "more": more,
    }
    if item["kind"] == "comment":
        hit = find_comment(comments, item["id"])
        if hit:
            data["comment_author"] = hit["author"]
            data["comment_body"] = hit["body"]
            data["comment_created"] = hit["created"]
            data["comment_score"] = hit["score"]
    return data


def find_comment(comments, cid):
    for c in comments:
        if c["id"] == cid:
            return c
        hit = find_comment(c["replies"], cid)
        if hit:
            return hit
    return None


def fetch_all(items, cache_dir, delay, max_comments, refresh):
    os.makedirs(cache_dir, exist_ok=True)
    todo = [it for it in items
            if refresh or not os.path.exists(os.path.join(cache_dir, f"{it['kind']}_{it['id']}.json"))]
    if not todo:
        say("All posts are already saved on this PC. Nothing new to fetch.")
        return
    minutes = max(1, round(len(todo) * delay / 60))
    say(f"Fetching {len(todo)} new item(s). This takes about {minutes} minute(s).")
    say("You can press Ctrl+C to stop. Progress is kept, and the page is still made.\n")
    failures = 0
    try:
        for n, it in enumerate(todo, 1):
            say(f"  [{n}/{len(todo)}] r/{it['sub']}  {it['kind']} {it['id']}")
            path = os.path.join(cache_dir, f"{it['kind']}_{it['id']}.json")
            try:
                raw = fetch_json(it["link"], max_comments, it["kind"] == "comment")
                data = parse_thread(raw, it, max_comments) if raw else {"gone": True}
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                failures = 0
            except Blocked as e:
                failures += 1
                say(f"    Reddit refused this one (code {e}).")
                if failures >= 5:
                    say("\nReddit is blocking fetching from this PC right now.")
                    say("The page will still be made, with links only for the rest.")
                    say("Try again later, or once your API access is approved.\n")
                    return
            except Exception as e:  # keep going on odd single failures
                failures += 1
                say(f"    Skipped: {e}")
            time.sleep(delay)
    except KeyboardInterrupt:
        say("\nStopped. Making the page with what is saved so far...\n")


def load_cache(items, cache_dir):
    for it in items:
        path = os.path.join(cache_dir, f"{it['kind']}_{it['id']}.json")
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    it.update(json.load(f))
                it["fetched"] = True
            except (OSError, ValueError):
                pass


# ---------------------------------------------------------------- building the page

def load_notes(out_dir):
    """Notes backup saved from the page (notes.json in the output folder)."""
    path = os.path.join(out_dir, "notes.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            notes = json.load(f)
        say(f"Loaded {len(notes)} note(s) from notes.json.\n")
        return notes if isinstance(notes, dict) else {}
    except (OSError, ValueError):
        say("notes.json is there but I couldn't read it. Skipping it.\n")
        return {}


def load_settings():
    """Optional settings.json next to this script, e.g. {"name": "Sam", "assistant": "Nova"}."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {k: str(v) for k, v in data.items() if k in ("name", "assistant")}
    except (OSError, ValueError, AttributeError):
        return {}


def build_page(items, out_path, notes):
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reddit_saver_page.html")
    with open(template_path, encoding="utf-8") as f:
        template = f.read()
    payload = json.dumps({
        "version": VERSION,
        "notes": notes,
        "settings": load_settings(),
        "made": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }, ensure_ascii=False).replace("<", "\\u003c")
    page = template.replace("__SAVED_DATA__", payload)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)


def main():
    ap = argparse.ArgumentParser(description="Make a dark-mode page of your saved Reddit items.")
    ap.add_argument("export", help="your Reddit export zip file, or the unzipped folder")
    ap.add_argument("--no-fetch", action="store_true", help="don't fetch full posts, links only")
    ap.add_argument("--refresh", action="store_true", help="fetch everything again, even if saved")
    ap.add_argument("--delay", type=float, default=7.0, help="seconds between fetches (default 7)")
    ap.add_argument("--max-comments", type=int, default=200, help="comments kept per post (default 200)")
    ap.add_argument("--out", help="output folder (default: 'Reddit Saved' next to the export)")
    ap.add_argument("--no-open", action="store_true", help="don't open the page at the end")
    args = ap.parse_args()

    source = os.path.abspath(args.export.strip('"'))
    out_dir = args.out or os.path.join(os.path.dirname(source), "Reddit Saved")
    os.makedirs(out_dir, exist_ok=True)

    say(f"Reddit Saver {VERSION}\nReading: {source}\n")
    csvs = find_csvs(source)
    if not csvs:
        raise SystemExit("I couldn't find saved_posts.csv or saved_comments.csv in that export.")
    items = read_items(csvs.get("posts", ""), "post", 0) if "posts" in csvs else []
    items += read_items(csvs.get("comments", ""), "comment", len(items)) if "comments" in csvs else []
    posts = sum(1 for i in items if i["kind"] == "post")
    say(f"Found {posts} saved post(s) and {len(items) - posts} saved comment(s), "
        f"in {len({i['sub'] for i in items})} subreddit(s).\n")

    cache_dir = os.path.join(out_dir, "cache")
    if not args.no_fetch:
        fetch_all(items, cache_dir, args.delay, args.max_comments, args.refresh)
    load_cache(items, cache_dir)

    out_path = os.path.join(out_dir, "saved.html")
    build_page(items, out_path, load_notes(out_dir))
    say(f"Done! Your page is here:\n  {out_path}")
    if not args.no_open:
        webbrowser.open("file:///" + out_path.replace("\\", "/"))


if __name__ == "__main__":
    main()
