"""
Build the `rutgers` corpus out of real r/rutgers discussion.

The provided corpora were written for this course. This one wasn't — it is
scraped, which means it arrives with all the junk a web page carries. Cleaning
it is the point, not an inconvenience.

Two stages, kept apart on purpose:

    fetch   Pull pages off a Redlib mirror and drop the HTML on disk untouched.
            Needs a browser, because the mirror runs a proof-of-work check.

    build   Turn that saved HTML into .txt documents. Standard library only, so
            it re-runs without the scraping dependency and without the network.

Splitting them means Unit 2 can re-tune the cleaning without re-scraping.

    python tools/harvest_rutgers.py fetch --raw .harvest
    python tools/harvest_rutgers.py build --raw .harvest

Reddit blocks direct API access from this machine, so the source is a Redlib
mirror — a read-only front end that serves the same posts as plain HTML.
Usernames are replaced with "reply N": the shipped corpora name no real people
and a public repo shouldn't either. Post text itself is left alone, since
redacting it would hollow out the thing being retrieved.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import time
from pathlib import Path

MIRROR = "https://safereddit.com"
SUBREDDIT = "rutgers"

REPO = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO / "corpora" / "rutgers" / "documents"
SOURCES = REPO / "corpora" / "rutgers" / "sources.json"

# Topics a Rutgers student actually asks other students about. The slug becomes
# the document filename prefix, so retrieval results stay readable.
TOPICS: list[tuple[str, str]] = [
    ("housing", "housing lottery seniority points"),
    ("housing", "best dorm honest review"),
    ("offcampus", "off campus housing landlord New Brunswick"),
    ("buses", "bus system route wait time"),
    ("dining", "dining hall Brower Livingston food"),
    ("parking", "parking permit lot ticket"),
    ("registration", "webreg registration closed section prerequisite"),
    ("courses", "which professor should I take"),
    ("cs", "computer science major advice"),
    ("data", "data science statistics major courses"),
    ("careers", "internship career fair resume"),
    ("commuting", "commuter student advice train"),
    ("money", "term bill financial aid scholarship"),
    ("academics", "withdraw from a class W transcript"),
    ("academics", "grade appeal professor dispute"),
    ("campus", "study spots library quiet"),
    ("food", "cheap food near campus"),
    ("life", "advice for incoming students wish I knew"),
]

# Flairs that carry jokes rather than answers.
SKIP_FLAIRS = {"shitpost", "memes", "meme", "sports", "photo", "art"}

# Roommate-finding megathreads: thousands of comments, none of them answers.
SKIP_TITLE = re.compile(r"megathread|roommate", re.I)

CHALLENGE = "Verifying your browser"


# --------------------------------------------------------------------------
# fetch
# --------------------------------------------------------------------------

def fetch_stage(raw_dir: Path, per_topic: int, delay: float) -> None:
    try:
        from scrapling.fetchers import StealthySession
    except ImportError:
        sys.exit(
            "The fetch stage needs `scrapling` (pip install scrapling; "
            "python -m scrapling install). The build stage does not — if the "
            "documents are already committed, you only need `build`."
        )

    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "search").mkdir(exist_ok=True)
    (raw_dir / "posts").mkdir(exist_ok=True)

    with StealthySession(headless=True) as session:

        def grab(url: str) -> str:
            """One page, retrying with a longer wait if the PoW page shows up."""
            for wait in (6000, 12000, 20000):
                resp = session.fetch(
                    url, network_idle=True, wait=wait, timeout=120000
                )
                page = _body_of(resp)
                if CHALLENGE not in page[:4000] and len(page) > 5000:
                    return page
            return ""

        seen: set[str] = set()
        queue: list[tuple[str, str]] = []

        for slug, query in TOPICS:
            url = (
                f"{MIRROR}/r/{SUBREDDIT}/search"
                f"?q={query.replace(' ', '+')}&restrict_sr=on&sort=top&t=all"
            )
            page = grab(url)
            name = f"{slug}__{query.replace(' ', '_')[:40]}.html"
            if not page:
                print(f"  search MISS  {query}")
                continue
            (raw_dir / "search" / name).write_text(page, encoding="utf-8")
            picks = _pick_posts(page, per_topic, seen)
            queue.extend((slug, href) for href in picks)
            print(f"  search ok    {query}  -> {len(picks)} posts")
            time.sleep(delay)

        print(f"\n{len(queue)} posts queued\n")

        for index, (slug, href) in enumerate(queue, 1):
            post_id = href.strip("/").split("/")[3]
            out = raw_dir / "posts" / f"{slug}__{post_id}.html"
            if out.exists():
                continue
            page = grab(MIRROR + href)
            if not page:
                print(f"  [{index}/{len(queue)}] MISS {post_id}")
                continue
            out.write_text(page, encoding="utf-8")
            print(f"  [{index}/{len(queue)}] ok   {post_id}")
            time.sleep(delay)


def _body_of(resp) -> str:
    for attr in ("html_content", "body", "content", "text"):
        value = getattr(resp, attr, None)
        if isinstance(value, str) and len(value) > 200:
            return value
    return str(resp)


def _pick_posts(page: str, limit: int, seen: set[str]) -> list[str]:
    """Best posts on a search page: most-discussed first, junk dropped."""
    picked = []
    # Split on the post container's id, not on `class="post`, which also
    # matches post_score / post_body / post_footer and would cut each post
    # into pieces with the title and the comment count in different halves.
    for block in page.split('<div class="post" id="')[1:]:
        href = re.search(r'href="(/r/rutgers/comments/[^"]+)"', block)
        title = re.search(r'class="post_title">(.*?)</h2>', block, re.S)
        if not href or not title:
            continue
        link = html_lib.unescape(href.group(1)).split("?")[0]
        text = _strip_tags(re.sub(r'<a [^>]*class="post_flair".*?</a>', "", title.group(1), flags=re.S))
        flair = re.search(r'class="post_flair"[^>]*><span>([^<]*)</span>', block)
        comments = re.search(r'class="post_comments" title="(\d+) comments?"', block)

        if link in seen or SKIP_TITLE.search(text):
            continue
        if flair and flair.group(1).strip().lower() in SKIP_FLAIRS:
            continue
        count = _comment_count(comments.group(1) if comments else "0")
        if count < 3 or count > 400:
            continue
        picked.append((count, link))
        seen.add(link)

    picked.sort(reverse=True)
    return [link for _, link in picked[:limit]]


def _comment_count(raw: str) -> int:
    raw = raw.strip()
    if raw.endswith("k"):
        return int(float(raw[:-1]) * 1000)
    return int(float(raw or 0))


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

BOT_AUTHORS = {"automoderator", "ru_bot", "remindmebot", "sneakpeekbot"}
DEAD = {"[deleted]", "[removed]", ""}

# Flairs the community itself uses to mark "this is venting, not information".
# Cheaper and more accurate than trying to infer it from the text.
DROP_FLAIRS = {"rant/vent", "rant", "vent", "crashout", "shitpost", "meme", "memes"}

# This corpus is committed to a public repo that gets graded. Reddit is candid;
# a slur in a submitted assignment is a different thing. A post that opens this
# way is dropped whole, a reply that does is dropped on its own so the rest of
# the thread survives.
SLURS = re.compile(
    r"\b(retard\w*|f[a4]gg\w*|n[i1]gg\w+|tr[a4]nn(?:y|ie|ies)|sp[i1]c|ch[i1]nk|k[i1]ke)\b",
    re.I,
)


def build_stage(raw_dir: Path, max_replies: int) -> None:
    posts_dir = raw_dir / "posts"
    if not posts_dir.exists():
        sys.exit(f"No raw posts at {posts_dir}. Run the fetch stage first.")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for stale in DOCS_DIR.glob("*.txt"):
        stale.unlink()

    manifest: dict[str, dict] = {}
    kept = skipped = 0

    for path in sorted(posts_dir.glob("*.html")):
        page = path.read_text(encoding="utf-8")
        doc = _parse_post(page, max_replies)
        if doc is None:
            skipped += 1
            continue

        topic = path.name.split("__")[0]
        name = f"{topic}_{_slug(doc['title'])}.txt"
        (DOCS_DIR / name).write_text(doc["text"], encoding="utf-8")
        manifest[name] = {
            "title": doc["title"],
            "url": f"https://www.reddit.com{doc['permalink']}",
            "posted": doc["created"],
            "replies_kept": doc["replies"],
            "topic": topic,
        }
        kept += 1

    SOURCES.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    total = sum(len(p.read_text(encoding="utf-8")) for p in DOCS_DIR.glob("*.txt"))
    print(f"{kept} documents written, {skipped} dropped as too thin")
    print(f"{total:,} characters, ~{total // max(kept, 1):,} per document")
    print(f"manifest -> {SOURCES.relative_to(REPO)}")


def _parse_post(page: str, max_replies: int) -> dict | None:
    title_block = re.search(r'<h1 class="post_title">(.*?)</h1>', page, re.S)
    if not title_block:
        return None
    title = _strip_tags(
        re.sub(r'<a [^>]*class="post_flair".*?</a>', "", title_block.group(1), flags=re.S)
    )
    title = re.sub(r"\s+", " ", title).strip()
    if not title:
        return None

    # Anchor on the inner "md" wrapper, which is where Redlib puts rendered
    # markdown. Without it, a link post (which has no self-text) matches the
    # outer div and drags the page footer and the "You are about to leave
    # Redlib" interstitial into the document.
    body_block = re.search(
        r'<div class="post_body">\s*<div class="md">(.*?)</div>\s*</div>', page, re.S
    )
    body = _to_text(body_block.group(1)) if body_block else ""

    created = re.search(r'<span class="created" title="([^"]+)"', page)
    permalink = re.search(r'href="(/r/rutgers/comments/[^"?]+)"', page)
    flair = re.search(r'class="post_flair"[^>]*><span>([^<]*)</span>', page)

    if flair and flair.group(1).strip().lower() in DROP_FLAIRS:
        return None
    if SLURS.search(body) or SLURS.search(title):
        return None

    replies = _parse_comments(page, max_replies)

    # A post with no body and no usable replies answers nothing. Drop it.
    if len(body) < 120 and not replies:
        return None

    lines = [f"THREAD: {title}"]
    if flair:
        lines.append(f"TOPIC: {html_lib.unescape(flair.group(1)).strip()}")
    lines.append("")
    if body:
        lines.append(body)
    for index, (score, text) in enumerate(replies, 1):
        lines.append("")
        lines.append(f"--- reply {index} ({score} votes) ---")
        lines.append(text)

    return {
        "title": title,
        "text": "\n".join(lines).strip() + "\n",
        "created": created.group(1) if created else "",
        "permalink": permalink.group(1) if permalink else "",
        "replies": len(replies),
    }


NOT_AN_ANSWER = re.compile(
    r"^(thanks|thank you|ty\b|this\b|same\b|lol|lmao|bump|congrats|good luck|rip\b)",
    re.I,
)


def _is_answer(text: str) -> bool:
    """
    Keep replies that answer, drop replies that ask.

    Score alone doesn't separate them — "ok so if I want Busch do I need
    roommates?" collects upvotes from everyone wondering the same thing, then
    retrieves beautifully and grounds the model in a question. So: count
    question marks against finished statements.
    """
    # Trailing emoticons hide the real last character ("getting in? :,))").
    body = re.sub(r"[^\w?.!]+$", "", text.rstrip())
    # An answer almost never ends on a question mark. A follow-up always does.
    if body.endswith("?"):
        return False
    if NOT_AN_ANSWER.match(text) and len(text) < 400:
        return False
    # If the first "?" arrives before the first ".", the reply opens by asking.
    # That catches the ones that bury their question mark mid-paragraph and
    # then trail off into a period, which the ending check alone lets through.
    first_question = body.find("?")
    if first_question != -1:
        enders = [i for i in (body.find("."), body.find("!")) if i != -1]
        if not enders or first_question < min(enders):
            return False
    return True


def _parse_comments(page: str, limit: int) -> list[tuple[int, str]]:
    scores = re.findall(r'<p class="comment_score" title="(-?\d+)"', page)
    authors = re.findall(r'<a class="comment_author[^"]*" href="/user/([^"]+)"', page)
    bodies = re.findall(r'<div class="comment_body[^"]*">(.*?)</div></div>', page, re.S)

    out: list[tuple[int, str]] = []
    for index, raw in enumerate(bodies):
        text = _to_text(raw)
        author = authors[index].lower() if index < len(authors) else ""
        score = int(scores[index]) if index < len(scores) else 0

        if author in BOT_AUTHORS or text.lower() in DEAD:
            continue
        if len(text) < 80 or score < 2:
            continue
        if SLURS.search(text):
            continue
        if not _is_answer(text):
            continue
        out.append((score, text))

    out.sort(key=lambda pair: -pair[0])
    return out[:limit]


# --------------------------------------------------------------------------
# cleaning
# --------------------------------------------------------------------------

def _to_text(fragment: str) -> str:
    """Markdown-rendered HTML down to plain text, structure preserved."""
    text = fragment
    text = re.sub(r"<(script|style)\b.*?</\1>", "", text, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<li[^>]*>", "\n- ", text, flags=re.I)
    text = re.sub(r"</(p|h[1-6]|blockquote|ul|ol|li|pre|table|tr)>", "\n", text, flags=re.I)
    text = re.sub(r"<h[1-6][^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<hr\s*/?>", "\n", text, flags=re.I)
    text = _strip_tags(text)

    # Bare links and image embeds are navigation, not content.
    text = re.sub(r"https?://\S*(?:preview|thumb|redd\.it|imgur)\S*", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_tags(fragment: str) -> str:
    return html_lib.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return slug[:58] or "untitled"


# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["fetch", "build"])
    parser.add_argument("--raw", default=".harvest", help="where raw HTML lives")
    parser.add_argument("--per-topic", type=int, default=5)
    parser.add_argument("--max-replies", type=int, default=8)
    parser.add_argument("--delay", type=float, default=1.5)
    args = parser.parse_args()

    raw_dir = Path(args.raw)
    if not raw_dir.is_absolute():
        raw_dir = REPO / raw_dir

    if args.stage == "fetch":
        fetch_stage(raw_dir, args.per_topic, args.delay)
    else:
        build_stage(raw_dir, args.max_replies)


if __name__ == "__main__":
    main()
