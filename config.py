"""
Settings for The Unofficial Guide.

Everything you're likely to change lives here, at the top, on purpose.
You'll edit THRESHOLD in Milestone 4 and the chunking numbers in Milestone 3.

Anything you set in your .env file wins over the defaults here.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")


# ─── The corpus you're working with ──────────────────────────────────────────
# Change this to switch corpora, or pass --corpus on the command line.
# Options are the folder names inside corpora/. See corpora/README.md.

CORPUS = os.getenv("AI201_CORPUS", "rutgers")


# ─── Chunking (Milestone 3) ──────────────────────────────────────────────────
# These are deliberately plain, generic numbers. Milestone 3 is where you
# replace them with numbers that fit the documents you actually read.

# These are a ceiling and a floor, not a window. split_documents cuts on reply
# and paragraph boundaries first; only a segment longer than CHUNK_SIZE gets
# cut again, and only at a sentence end.
#
# 800: the 90th percentile reply in this corpus is 668 characters, so 800 keeps
#      more than nine replies in ten intact. Only 4.2% of natural segments
#      exceed it.
# 200: the fixed-size chunker left fragments of 7, 10 and 32 characters. Below
#      roughly 200 a piece of a Reddit thread answers nothing, so anything
#      smaller gets merged into its neighbour.
# 120: overlap only applies where a long segment had to be cut mid-thought.
#      Cutting on boundaries means there is usually nothing to repair.

CHUNK_SIZE = 800        # ceiling: split a segment only once it passes this
CHUNK_MIN = 200         # floor: merge anything smaller into its neighbour
CHUNK_OVERLAP = 120     # carried back only when a long segment is split


# ─── Retrieval (Milestone 4) ─────────────────────────────────────────────────

# Kept at 5 after measuring rather than by default. Sweeping 3, 5, 8, 12 and 20
# changed nothing until 12, where one expects-phrase finally appeared at rank 11
# with a distance of 0.826 — further away than four of my five out-of-scope
# questions. Paying for seven more chunks on every question to reach one that
# far away is buying noise, so 5 stays.
TOP_K = 5               # how many chunks to pull back per question

# The relevance gate. If the best chunk is further away than this, the system
# refuses to answer instead of handing the model thin material.
#
# LOWER IS BETTER: 0.3 is a close match, 0.9 is unrelated.
#
# Measured, then set. My two groups did not split where I expected them to:
#
#   questions my corpus can answer   0.216  0.404  0.438  (0.453 topically)
#   questions it cannot              0.744  0.778  0.818  0.843  0.859
#
# The 0.744 is one of my own five test questions — registration, my thinnest
# topic at 3 documents. The corpus mentions SPNs exactly once, in passing,
# inside an answer to a different question, so refusing it is correct behaviour
# rather than a miss. That makes the real gap 0.453 → 0.744, and its midpoint
# is 0.599.
#
# 0.60 is that midpoint. It happens to be the number the starter shipped with,
# which I only noticed afterwards — the reasoning is the measurement above, not
# the default. Going higher (0.76, in the gap between my questions and the
# out-of-scope ones) would admit the registration question on material that
# cannot answer it; going lower costs me the bus question at 0.453.
THRESHOLD = 0.6


# ─── Models ──────────────────────────────────────────────────────────────────
# Embeddings run on your own machine and cost no API quota.
# Only generation calls out to a service.

# This is the model Chroma bundles, and leaving it alone is the fast path: it
# downloads about 80 MB from Chroma's own CDN and needs nothing else installed.
#
# Setting it to any other name — unit 2's "try a second embedding model"
# stretch option — switches to loading that model from Hugging Face instead,
# which needs `pip install 'sentence-transformers>=3.4,<3.5'` first. store.py
# says so with a real error message rather than a stack trace if you forget.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
MODEL = os.getenv("AI201_MODEL", "gemini-3.5-flash-lite")


# ─── Rate limiting and quota guards ──────────────────────────────────────────
# You should not need to touch these. They exist so that a runaway loop costs
# you a warning instead of your whole day's allowance.

REQUESTS_PER_MINUTE = 30       # outgoing calls the limiter will allow per minute
SESSION_REQUEST_BUDGET = 300   # stop and warn rather than draining the daily quota
MAX_RETRIES = 4                # on 429 / resource-exhausted, with backoff

CACHE_ENABLED = os.getenv("AI201_CACHE", "1") != "0"
CACHE_DIR = ROOT / ".cache"


# ─── Paths ───────────────────────────────────────────────────────────────────

CORPORA_DIR = ROOT / "corpora"
CHROMA_DIR = ROOT / "chroma_db"
RESULTS_DIR = ROOT / "results"


def corpus_path(name: str | None = None) -> Path:
    """Folder holding the documents for a corpus."""
    return CORPORA_DIR / (name or CORPUS) / "documents"


def collection_name(name: str | None = None, variant: str = "default") -> str:
    """
    Name of the vector-store collection for a corpus.

    `variant` lets you index the same corpus two different ways and query both
    without deleting anything — you'll want that in unit 2 when you compare
    chunking strategies.

    Chroma is fussy about collection names: 3 to 63 characters, starting and
    ending with a letter or digit, and nothing but letters, digits, underscores
    and hyphens in between. If you bring your own corpus and name the folder
    something Chroma won't accept, this cleans it up rather than failing.
    """
    import re

    raw = f"{name or CORPUS}__{variant}"
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "-", raw)
    cleaned = cleaned.strip("_-")          # must start and end alphanumeric
    if not cleaned or not cleaned[0].isalnum():
        cleaned = f"c{cleaned}"
    if not cleaned[-1].isalnum():
        cleaned = f"{cleaned}0"
    return cleaned[:63].rstrip("_-") or "collection"
