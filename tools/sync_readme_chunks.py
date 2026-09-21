"""
Rewrite the README's Sample Chunks blocks from the actual Chunk objects.

Milestone 3 asks for five chunks pasted into the README with their source file
and the function that produced them, and the grader checks that against the
code. Transcribing them by hand does not survive that: my first pass silently
turned the corpus's curly apostrophes into straight ones in three of the five,
so the README disagreed with the documents it was evidence about.

So the blocks are generated instead of typed. This reads the labels already in
the README, looks each one up, and writes the real text into the fence. It
fails loudly rather than quietly if the README has drifted:

  - a label the corpus no longer produces (re-chunking renumbers everything)
  - a `produced by` the chunk itself disagrees with

Run it from the repo root after any change to chunker.py or the corpus:

    python tools/sync_readme_chunks.py

Exit status is 0 if nothing needed changing, 1 if it rewrote something, so it
can be used as a check as well as a fixer.
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from chunker import split_documents   # noqa: E402
from ingest import load_documents     # noqa: E402

BLOCK = re.compile(
    r"(\*\*Chunk (\d)\*\* — source: `([^`]+)` — produced by: `([^`]+)`\n\n```\n)"
    r"(.*?)"
    r"(\n```)",
    re.S,
)


def main() -> int:
    chunks = {c.label: c for c in split_documents(load_documents("rutgers"))}
    readme = REPO / "README.md"
    original = readme.read_text(encoding="utf-8")
    rewritten: list[str] = []

    def replace(match: re.Match) -> str:
        head, number, label, produced, body, tail = match.groups()
        chunk = chunks.get(label)
        if chunk is None:
            raise SystemExit(
                f"README's chunk {number} names {label}, which this corpus no "
                f"longer produces. Re-chunking renumbers every label, so the "
                f"sample needs re-picking with `python app.py chunks -n 5`."
            )
        if chunk.produced_by != produced:
            raise SystemExit(
                f"README's chunk {number} claims it was produced by "
                f"{produced}, but {label} says {chunk.produced_by}."
            )
        if body != chunk.text:
            rewritten.append(f"chunk {number} ({label})")
        return head + chunk.text + tail

    updated = BLOCK.sub(replace, original)
    found = len(BLOCK.findall(original))

    if found != 5:
        print(f"warning: found {found} sample-chunk blocks in the README, expected 5")

    if updated == original:
        print(f"{found} sample chunks, all exact.")
        return 0

    readme.write_text(updated, encoding="utf-8")
    print(f"Rewrote {len(rewritten)} of {found} sample chunks:")
    for entry in rewritten:
        print(f"  {entry}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
