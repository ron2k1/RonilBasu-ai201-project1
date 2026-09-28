"""
Stage 2 of the pipeline: splitting documents into chunks.

⚠️ THIS IS THE FILE YOU CHANGE IN MILESTONE 3.

`split_documents` below is deliberately plain. It cuts every document into
fixed-size pieces with a fixed overlap and pays no attention to where sentences
or paragraphs end. It works, and it is not good.

On a corpus of short posts it may not cut anything at all: `campus_life` comes
out as 88 documents and 88 chunks, because almost nothing in it reaches 800
characters. That is the baseline, not a bug — Milestone 3 is where you decide
whether one post should stay one chunk.

Your job in Milestone 3 is to replace the *body* of `split_documents` with a
strategy that fits the documents you actually read in Milestone 1. Keep the
name and the shape of what it returns — the rest of the pipeline calls it, and
your README has to name the function that produced your chunks.

If you get stuck for 30 minutes, `fallback_split` is the original. Switch back
to it, write down what you saw, and move on. That's a real observation about
your pipeline, not giving up.
"""

import re
from dataclasses import dataclass

import config
from ingest import Document

# The shape harvest_rutgers.py writes: a THREAD/TOPIC header, the post body,
# then one "--- reply 3 (274 votes) ---" marker per comment. The chunker cuts
# on those markers first, because they are where one person stops talking and
# another starts.
HEADER_PREFIXES = ("THREAD:", "TOPIC:")
REPLY_MARKER = re.compile(r"^(--- reply \d+ \(-?\d+ votes\) ---)$", re.M)
PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
# A piece that starts "- ", "* ", "• ", "1. " or "1) ". A whole reply starts with
# its "--- reply" marker and never matches, but a later piece of a long reply
# that _split_long cut can. Six in this corpus do, and none of them was ever
# merged with another list item, so the rule below changes nothing for them.
LIST_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


@dataclass
class Chunk:
    """One piece of one document."""

    text: str
    source: str        # which file it came from
    index: int         # which chunk within that file, starting at 0
    produced_by: str   # the function that made it — cite this in your README

    @property
    def label(self) -> str:
        return f"{self.source}#{self.index}"


def fallback_split(
    documents: list[Document],
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """
    The starter's original chunker. Fixed-size character windows with overlap.

    Keep this function. Milestone 3's stop rule points back at it, and having
    something to compare your own strategy against is useful in unit 2.
    """
    chunk_size = chunk_size or config.CHUNK_SIZE
    overlap = overlap or config.CHUNK_OVERLAP

    if overlap >= chunk_size:
        raise ValueError("overlap has to be smaller than chunk_size")

    chunks: list[Chunk] = []
    for doc in documents:
        start = 0
        index = 0
        while start < len(doc.text):
            piece = doc.text[start : start + chunk_size].strip()
            if piece:
                chunks.append(
                    Chunk(
                        text=piece,
                        source=doc.source,
                        index=index,
                        produced_by="chunker.py::fallback_split",
                    )
                )
                index += 1
            start += chunk_size - overlap

    return chunks


def _header_and_segments(text: str) -> tuple[str, list[str]]:
    """
    Pull the THREAD/TOPIC header off a document and cut the rest where the
    document itself already breaks: one segment per reply, one per paragraph
    of the original post.

    The reply marker is kept at the top of its segment. It costs about thirty
    characters and it tells the model two things worth knowing — that this is
    somebody answering rather than asking, and how many people agreed.
    """
    lines = text.splitlines()
    header = "\n".join(ln for ln in lines if ln.startswith(HEADER_PREFIXES)).strip()
    body = "\n".join(ln for ln in lines if not ln.startswith(HEADER_PREFIXES)).strip()

    # re.split with a capturing group gives [post, marker, reply, marker, ...]
    parts = REPLY_MARKER.split(body)

    segments: list[str] = []
    post = parts[0].strip()
    if post:
        segments += [p.strip() for p in PARAGRAPH_BREAK.split(post) if p.strip()]
    for i in range(1, len(parts) - 1, 2):
        marker, reply = parts[i].strip(), parts[i + 1].strip()
        if reply:
            segments.append(f"{marker}\n{reply}")

    return header, segments


def _tail_sentences(text: str, overlap: int) -> str:
    """The last whole sentences of `text`, up to about `overlap` characters."""
    if overlap <= 0:
        return ""
    tail = ""
    for sentence in reversed(SENTENCE_END.split(text.strip())):
        candidate = f"{sentence} {tail}".strip() if tail else sentence
        if tail and len(candidate) > overlap:
            break
        tail = candidate
    return tail


def _split_long(segment: str, cap: int, overlap: int) -> list[str]:
    """
    Cut a single over-long segment at sentence ends, repeating the tail of each
    piece at the head of the next.

    Overlap only happens here. A reply that fits under the cap is never cut, so
    there is nothing to repair and no duplicated text in the store.
    """
    if len(segment) <= cap:
        return [segment]

    pieces: list[str] = []
    current = ""
    for sentence in SENTENCE_END.split(segment):
        while len(sentence) > cap:          # one sentence longer than the cap
            pieces.append(sentence[:cap].strip())
            sentence = sentence[cap - overlap :]
        if not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= cap:
            current = f"{current} {sentence}"
        else:
            pieces.append(current.strip())
            # The tail is whole sentences, so it can be longer than `overlap`
            # asks for. Carry it only if the next piece still fits underneath
            # the cap — the cap wins over the overlap, every time.
            tail = _tail_sentences(current, overlap)
            fits = tail and len(tail) + 1 + len(sentence) <= cap
            current = f"{tail} {sentence}".strip() if fits else sentence
    if current.strip():
        pieces.append(current.strip())
    return pieces


def _merge_small(pieces: list[str], floor: int, cap: int) -> list[str]:
    """
    Fold anything under `floor` into its neighbour, as long as it still fits,
    except that a list item never joins a chunk that already holds one.

    The floor was set on replies, where under 200 characters really is a
    fragment. In a list post a 112-character tip is a whole thought, and
    folding it in is what put the corpus's only LX sentence in a chunk that
    was mostly about printers. An intro can still take the first item, and a
    plain paragraph can still fold into the item it follows.
    """
    merged: list[str] = []
    holds_item: list[bool] = []
    for piece in pieces:
        is_item = LIST_ITEM.match(piece) is not None
        if merged:
            too_small = len(piece) < floor or len(merged[-1]) < floor
            fits = len(merged[-1]) + 2 + len(piece) <= cap
            second_item = is_item and holds_item[-1]
            if too_small and fits and not second_item:
                merged[-1] = f"{merged[-1]}\n\n{piece}"
                holds_item[-1] = holds_item[-1] or is_item
                continue
        merged.append(piece)
        holds_item.append(is_item)
    return merged


def split_documents(documents: list[Document]) -> list[Chunk]:
    """
    Boundary-first chunking for r/rutgers threads.

    A Reddit thread is not prose, it is a stack of separate opinions, and the
    fixed-size splitter could not see that: on this corpus it ended 86.8% of its
    chunks mid-sentence and left 35.7% of them with no thread title and no reply
    marker, so the chunk no longer said what it was about. Its smallest pieces
    were 7, 10 and 32 characters.

    Four passes, in this order:

      1. Cut where the document already breaks — one segment per reply, one per
         paragraph of the original post.
      2. Cut a segment again only if it passes CHUNK_SIZE, and then at a
         sentence end, carrying CHUNK_OVERLAP characters of the previous
         sentence forward.
      3. Merge anything under CHUNK_MIN into its neighbour, but never two
         list items into one chunk (added in unit 2).
      4. Prepend the thread title to every chunk, so a chunk retrieved on its
         own still says which thread it came from.

    The header is charged against the cap rather than added on top of it, which
    keeps every chunk inside CHUNK_SIZE end to end.
    """
    cap = config.CHUNK_SIZE
    floor = config.CHUNK_MIN
    overlap = config.CHUNK_OVERLAP

    chunks: list[Chunk] = []
    for doc in documents:
        header, segments = _header_and_segments(doc.text)
        # Whatever the header costs is room the body no longer has. The floor
        # is the lower bound so a pathologically long title cannot squeeze the
        # body down to nothing.
        budget = max(floor, cap - len(header) - 2)

        pieces: list[str] = []
        for segment in segments:
            pieces += _split_long(segment, budget, overlap)
        pieces = _merge_small(pieces, floor, budget)

        for index, piece in enumerate(pieces):
            chunks.append(
                Chunk(
                    text=f"{header}\n\n{piece}" if header else piece,
                    source=doc.source,
                    index=index,
                    produced_by="chunker.py::split_documents",
                )
            )

    return chunks


def describe(chunks: list[Chunk]) -> str:
    """A one-line summary, printed after indexing."""
    if not chunks:
        return "0 chunks"
    lengths = [len(c.text) for c in chunks]
    return (
        f"{len(chunks)} chunks, "
        f"{sum(lengths) // len(lengths)} characters on average "
        f"(shortest {min(lengths)}, longest {max(lengths)}), "
        f"produced by {chunks[0].produced_by}"
    )


if __name__ == "__main__":
    from ingest import load_documents

    chunks = split_documents(load_documents())
    print(describe(chunks))
