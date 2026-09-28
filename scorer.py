"""
Deciding whether an answer was right, and whether each criterion held.

    python scorer.py results/run_<stamp>_before.json

`run_eval.py` imports `judge` from here and uses it for the per-question
pass/fail columns. The per-criterion table my README asks for comes from
`criteria_rows`, run over the JSON file `run_eval.py` writes next to its
report. It reads only that file, so the counts can be checked again from the
committed evidence without an index, an API key, or a single model call.

Written and committed before the first run, so the rules below were fixed
before I had any results for them to flatter.
"""

import json
import re
import sys

# A document is named when the answer contains its filename. The filenames are
# built from thread titles: lowercase words joined with underscores, ending .txt.
FILENAME = re.compile(r"[A-Za-z0-9][\w-]*\.txt")

# Criterion 4 asks whether ONE chunk holds everything needed to answer. Whether
# the phrase is in a chunk is mechanical. Whether the chunk around it actually
# answers the question is a reading, so these are my readings, written down.
#
# Keyed by source file plus a sentence that has to still be in the chunk, not
# by chunk label, because labels renumber every time the chunker changes and a
# judgment that silently moved to a different chunk would be worse than none.
# A chunk that holds the phrase and matches nothing here fails, and is listed
# as unjudged so I have to go and read it.
HAND_CHECKED = [
    # (source, sentence that must be in the chunk, answers the question?, why)
    (
        "campus_why_no_24_hour_library.txt",
        "ARC and SERC are both open 24 hours",
        True,
        "names two buildings on Busch open all night and a quiet spot in one",
    ),
    (
        "academics_pass_no_credit_faq_as_it_stands_right_now_way_before_the_p.txt",
        "a P or NC grade will not change GPA",
        True,
        "you can pick which classes, the deadline, and that GPA is untouched",
    ),
    (
        "academics_pass_no_credit_faq_as_it_stands_right_now_way_before_the_p.txt",
        "P/NC CLASSES WILL COUNT TOWARD MAJORS",
        True,
        "counts for anything needing a C, see an advisor if you need a B",
    ),
    (
        "academics_pass_no_credit_faq_as_it_stands_right_now_way_before_the_p.txt",
        "Professors will not know",
        True,
        "the professor never finds out, and the W deadline",
    ),
    (
        "food_the_most_overrated_food_spots_on_near_campus_by_a_very_cyn.txt",
        "Krispy Pizza: What does everyone see in this place?",
        True,
        "names Krispy Pizza as overrated and says where to go instead",
    ),
    (
        "cs_little_rutgers_things_i_wish_i_knew_earlier.txt",
        "LX, H, and A buses go around College Ave",
        False,
        "says the LX loops around College Ave, never that it goes to Livingston",
    ),
    (
        "academics_anonymous_academic_advisor_here_ask_me_your_questions.txt",
        "SPNs were given for that class",
        False,
        "brings up SPNs only to say dropping a closed class frees no seat",
    ),
]

TARGETS = {
    1: "4 of 5",
    2: "every answer produced",
    3: "4 of 5",
    4: "4 of 5",
    5: "5 of 5",
}

NAMES = {
    1: "1. Retrieved chunks contain the answer",
    2: "2. Every answer names a source",
    3: "3. Gate stops out-of-corpus questions",
    4: "4. The answer fits inside one chunk",
    5: "5. Every source named was actually retrieved",
}

# The original stays in the table, the revision goes underneath it.
REVISED_1 = "1r. Revised: a retrieved chunk, read on its own, answers"


def _field(result, name):
    """Retrieved chunks arrive as store.Result objects live, or dicts from JSON."""
    return result[name] if isinstance(result, dict) else getattr(result, name)


def contains_expected(text: str, expects: str) -> bool:
    """The `expects` phrase from questions.py, as a word rather than a substring.

    Case doesn't matter and a plural still counts (SPNs is SPN). A letter
    straight before or after it does, so the LX is not found inside ALX.
    """
    pattern = r"(?<![A-Za-z])" + re.escape(expects) + r"s?(?![A-Za-z])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def judge(question, expects, answer, results) -> bool:
    """Was the answer right? It has to say what I wrote down in unit 1."""
    return contains_expected(answer, expects)


def named_files(answer: str) -> list[str]:
    """Every filename the answer names, in the order it names them."""
    return FILENAME.findall(answer)


def names_a_source(answer, results, gate_passed) -> bool | None:
    """Criterion 2. None for a refusal: the gate wrote it, not the model."""
    if not gate_passed:
        return None
    if named_files(answer):
        return True
    # Naming a retrieved thread without its .txt still names it.
    stems = {_field(r, "source").removesuffix(".txt") for r in results}
    return any(stem in answer for stem in stems)


def citations_were_retrieved(answer, results) -> bool:
    """Criterion 5. Every filename named has to be one that was handed over."""
    retrieved = {_field(r, "source") for r in results}
    return all(name in retrieved for name in named_files(answer))


def retrieved_has_answer(expects, results) -> bool:
    """Criterion 1. Some retrieved chunk contains the expects phrase."""
    return any(contains_expected(_field(r, "text"), expects) for r in results)


def retrieved_answers(expects, results) -> bool:
    """Criterion 1 as revised in unit 2: the phrase, in a chunk I read as answering.

    The phrase alone was the wrong stand-in for "the answer" on two of my five
    questions (see the revision in criteria.md). It is the same function as
    criterion 4, so the two rows can never disagree: one chunk that answers is
    what criterion 4 already asked for.
    """
    return one_chunk_answers(expects, results)[0]


def _hand_check(result):
    source, text = _field(result, "source"), _field(result, "text")
    for checked_source, sentence, answers, _why in HAND_CHECKED:
        if source == checked_source and sentence in text:
            return answers
    return None


def one_chunk_answers(expects, results) -> tuple[bool, list[str]]:
    """Criterion 4. One chunk holds the phrase AND, read alone, answers.

    Returns the verdict and the labels of any chunk holding the phrase that I
    have not read yet. Those count as a fail until I have.
    """
    unjudged = []
    for result in results:
        if not contains_expected(_field(result, "text"), expects):
            continue
        verdict = _hand_check(result)
        if verdict is True:
            return True, []
        if verdict is None:
            unjudged.append(_field(result, "label"))
    return False, unjudged


def criteria_rows(data) -> list[tuple[str, str, list[str]]]:
    """One row per criterion: name, target, and a count for every run."""
    questions = data["questions"]
    n_runs = len(questions[0]["runs"]) if questions else 0
    runs = [[q["runs"][i] | {"expects": q["expects"]} for q in questions] for i in range(n_runs)]

    def count(check):
        return [f"{sum(check(e) for e in run)}/{len(run)}" for run in runs]

    def c2(run):
        scored = [
            names_a_source(e["answer"], e["retrieved"], e["gate_passed"]) for e in run
        ]
        scored = [s for s in scored if s is not None]
        return f"{sum(scored)}/{len(scored)}"

    gate = data.get("out_of_scope", [])
    c3 = f"{sum(r['refused'] for r in gate)}/{len(gate)}"

    return [
        (NAMES[1], TARGETS[1], count(lambda e: retrieved_has_answer(e["expects"], e["retrieved"]))),
        (REVISED_1, TARGETS[1], count(lambda e: retrieved_answers(e["expects"], e["retrieved"]))),
        (NAMES[2], TARGETS[2], [c2(run) for run in runs]),
        (NAMES[3], TARGETS[3], [c3] * n_runs),
        (NAMES[4], TARGETS[4], count(lambda e: one_chunk_answers(e["expects"], e["retrieved"])[0])),
        (NAMES[5], TARGETS[5], count(lambda e: citations_were_retrieved(e["answer"], e["retrieved"]))),
    ]


def unjudged_chunks(data) -> list[str]:
    """Chunks criterion 4 needed a reading of and didn't have one."""
    missing = set()
    for q in data["questions"]:
        for entry in q["runs"]:
            missing.update(one_chunk_answers(q["expects"], entry["retrieved"])[1])
    return sorted(missing)


def criteria_markdown(data) -> str:
    """The run log table, minus the verdict column. The verdict is my call."""
    rows = criteria_rows(data)
    n = len(rows[0][2])
    lines = [
        "| Criterion | Target | " + " | ".join(f"Run {i}" for i in range(1, n + 1)) + " |",
        "|---|---|" + "---|" * n,
    ]
    for name, target, counts in rows:
        lines.append(f"| {name} | {target} | " + " | ".join(counts) + " |")
    missing = unjudged_chunks(data)
    if missing:
        lines += ["", "Criterion 4 counted these as fails because I haven't read them yet:"]
        lines += [f"- `{label}`" for label in missing]
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python scorer.py results/run_<stamp>_<label>.json")
    with open(sys.argv[1], encoding="utf-8") as f:
        print(criteria_markdown(json.load(f)))
