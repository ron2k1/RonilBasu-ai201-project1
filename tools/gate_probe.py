#!/usr/bin/env python3
"""
Would the relevance gate stop a Rutgers question my threads don't answer?

    python tools/gate_probe.py

Criterion 3 asks this about five questions from another world (Mongolia,
diesel engines), and the nearest of those is 0.178 past the cutoff. These are
questions a Rutgers student would actually ask. For each one this prints the
best distance on both indexes, whether the gate would let it through, and the
chunk it would be answered from. Retrieval only: no model calls.

Written after both eval runs, so none of this feeds a criterion. It's evidence
for what I'd write differently.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from gate import check  # noqa: E402
from store import search  # noqa: E402

NEAR_MISSES = [
    "What time does the Busch dining hall close on weekends?",
    "How do I replace a lost Rutgers ID card?",
    "When is the deadline to apply for graduation at Rutgers?",
    "Which Rutgers gym has a swimming pool?",
    "How do I get a parking permit refund at Rutgers?",
]

VARIANTS = ("default", "lists")


def main():
    print(f"cutoff {config.THRESHOLD}, indexes: {', '.join(VARIANTS)}")
    for question in NEAR_MISSES:
        print(f"\n{question}")
        for variant in VARIANTS:
            results = search(question, top_k=config.TOP_K, variant=variant)
            verdict = "passes" if check(results).passed else "refused"
            best = min(results, key=lambda r: r.distance)
            body = best.text.split("\n\n", 1)[-1].replace("\n", " ")
            print(f"  {variant:<8} {best.distance:.4f} {verdict}  {best.label}")
            print(f"           \"{body[:150]}\"")


if __name__ == "__main__":
    main()
