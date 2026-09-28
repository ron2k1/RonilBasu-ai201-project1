#!/usr/bin/env python3
"""
Where does the chunk holding each question's answer rank, across the whole index?

    python tools/answer_rank.py
    python tools/answer_rank.py --variant v2

The run log only shows the top five, which tells me a question missed but not
by how much. This ranks every chunk in the index against each test question
and reports where the ones holding the `expects` phrase landed, with the
sentence the phrase sits in. Retrieval only: no model calls.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import questions as qs  # noqa: E402
from scorer import contains_expected  # noqa: E402
from store import search  # noqa: E402

SENTENCE = re.compile(r"[^.!?\n]*[.!?]?")


def sentence_with(text: str, expects: str) -> str:
    for sentence in SENTENCE.findall(text):
        if contains_expected(sentence, expects):
            return sentence.strip()
    return ""


def main():
    parser = argparse.ArgumentParser(description="Rank of each answer-bearing chunk.")
    parser.add_argument("--variant", default="default")
    args = parser.parse_args()

    for item in qs.answered():
        question, expects = item["question"], item["expects"]
        ranked = search(question, top_k=100_000, variant=args.variant)
        hits = [
            (rank, r) for rank, r in enumerate(ranked, 1)
            if contains_expected(r.text, expects)
        ]
        print(f"\n{question}")
        print(f"  expects {expects!r}: {len(hits)} of {len(ranked)} chunks hold it "
              f"(top {config.TOP_K} ends at {ranked[config.TOP_K - 1].distance:.4f})")
        for rank, r in hits[:5]:
            print(f"  rank {rank:>3}  {r.distance:.4f}  {r.label}")
            print(f"            \"{sentence_with(r.text, expects)}\"")


if __name__ == "__main__":
    main()
