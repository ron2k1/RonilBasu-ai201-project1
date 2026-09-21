"""
Your test questions.

Milestone 2 asks you to write five questions your system should be able to
answer from your corpus, specific enough to have a right answer.

  ✗ "What are good dining halls?"          — no right answer
  ✓ "What do students say about wait times at Commons during lunch?"

Fill in `QUESTIONS` below. `expects` is a word or short phrase you'd expect a
correct answer to contain — you'll use it in unit 2 when you build a scorer,
and having written it now means you decided what "correct" meant before you saw
any results.

`OUT_OF_SCOPE` holds five questions your documents clearly don't cover. You
need these in Milestone 4 to find where your relevance cutoff belongs, and
again in unit 2, where `run_eval.py` runs them through the gate and writes what
happened into your run log — that's the evidence for criterion 3.

Swap them for your own if you like. Keep five of them either way: criterion 3
names a target of "4 of 5", and four of three is not a thing.
"""

# Five topics, deliberately not five of the same topic. The corpus covers 16,
# unevenly — academics has 9 documents and registration has 3 — so these are
# spread from the thickest coverage to the thinnest on purpose. Question 4 sits
# on the thinnest, and I expect it to be the hard one.
#
# Each `expects` is a proper noun rather than a general word, because "the bus"
# appears in an answer that is right and in an answer that is waffle, and "LX"
# only appears in one of them.
QUESTIONS = [
    {
        # campus — 4 documents
        "question": "Where can I study on Busch campus late at night?",
        "expects": "SERC",
    },
    {
        # academics — 9 documents, the thickest topic in the corpus
        "question": "What should I think about before converting a class to Pass/No Credit?",
        "expects": "P/NC",
    },
    {
        # buses — 4 documents
        "question": "Which bus do I take from College Avenue to Livingston?",
        "expects": "LX",
    },
    {
        # registration — 3 documents, the thinnest topic in the corpus
        "question": "What can I do if the section I need is already closed on WebReg?",
        "expects": "SPN",
    },
    {
        # food — 5 documents
        "question": "Which food places near campus do students think are overrated?",
        "expects": "Krispy Pizza",
    },
]

# Questions from a different world entirely. Your gate should refuse all five.
#
# There are five of these because criterion 3 in criteria.md names a target of
# "at least 4 of 5" — you need five things to try before you can report 4 of 5.
# `run_eval.py` runs these through retrieval and the gate on every eval and
# records what happened, so criterion 3 has evidence in the run log alongside
# the others. They cost no model calls: a refusal never reaches the model.
OUT_OF_SCOPE = [
    "What is the capital of Mongolia?",
    "How do I change the oil in a diesel engine?",
    "Who won the 1994 World Cup?",
    "What is the recommended dosage of ibuprofen for a headache?",
    "How do I write a for loop in Rust?",
]


def answered() -> list[dict]:
    """The questions you've actually filled in."""
    return [q for q in QUESTIONS if q.get("question", "").strip()]
