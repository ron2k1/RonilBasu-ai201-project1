# Acceptance criteria — The Unofficial Guide

Five criteria that say what "working" means for this system, written in unit 1
**before** any results existed.

An acceptance criterion names a target: a number, a count, a rate, or something
a person could plainly observe. *"Retrieval works"* is an opinion. *"For at
least 4 of my 5 test questions, the top results include a chunk containing the
answer"* is a criterion.

Under each one, write a sentence or two on **why that target** and not a
stricter or looser one. A reason that says something about your corpus or your
pipeline earns credit; *"80% seemed reasonable"* does not.

> Missing your own targets next unit costs you nothing. Setting a target so
> easy you can't miss it does.

---

## 1. Retrieved chunks contain the answer

For at least 4 of my 5 test questions, the retrieved chunks include one that
contains the answer.

**Why this target:** My 80 documents cover 16 topics unevenly — academics has 9
and registration has 3 — and I picked my five questions across that spread
deliberately rather than all from the thick end. Question 4 ("what can I do if
the section is closed on WebReg?") sits on those 3 registration documents and
asks for a specific mechanism, so it is the one I expect to miss. 4 of 5 leaves
room for exactly that question and no other; 5 of 5 would mean my thinnest topic
has to work as well as my thickest, which I do not believe, and 3 of 5 would let
a second failure through without me having to explain it.

> **Revised in unit 2:** For at least 4 of my 5 test questions, a retrieved
> chunk contains the question's `expects` phrase inside a passage that, read on
> its own, answers the question. The phrase turning up somewhere in the chunk
> is not enough by itself.
>
> **Why revised:** When I built the scorer I used the `expects` phrase as the
> stand-in for "the answer", since that is what I wrote those phrases for in
> unit 1. Reading the corpus showed that stand-in failing in both directions on
> my own questions. "P/NC" is the topic of question 2 rather than its answer,
> so any chunk about Pass/No Credit would pass whether or not it said anything
> worth thinking about. And the only "LX" in all 80 threads sits in "LX, H, and
> A buses go around College Ave", which never says the LX goes to Livingston. A
> chunk holding that sentence would pass the phrase check and still not answer
> question 3. On the before run the phrase check and my reading agree, 3 of 5
> both ways, so this revision changes no number I already had. It only stops
> the check from counting a chunk that doesn't answer. The original target
> stays at 4 of 5.

---

## 2. Every answer names a source

Every answer the system produces names at least one source document.

**Why this target:** All five, because nothing has to go right for this to work
— it only has to not go wrong. `build_prompt` in `generate.py` puts
`[from <filename>]` on the front of every chunk it sends, and the relevance gate
means the model never receives an empty set of documents, so every answer that
gets produced at all has filenames sitting directly above the question.
`GROUNDING_INSTRUCTION` then asks for one by name. A miss here would not be a
hard question, it would be the model ignoring an instruction while looking at
the answer, and I want that to show up as a failure rather than be absorbed by a
4-of-5 target.

---

## 3. The relevance gate stops out-of-corpus questions

When I ask a question my documents clearly don't cover, the relevance gate
stops it and the system returns "I don't have enough information about that" —
in at least 4 of 5 tries.

<!-- The five questions are the ones in `OUT_OF_SCOPE` at the bottom of
     `questions.py`, and `run_eval.py` puts them through the gate and writes
     what happened into your run log. Swap them for your own if you'd rather —
     just keep five of them, or the "4 of 5" above has nothing to be 4 of. -->

**Why this target:** 4 of 5 rather than 5 of 5 because the five out-of-scope
questions are not equally far from my corpus. Four of them (Mongolia, diesel
engines, the 1994 World Cup, ibuprofen) are from another world entirely, but
"How do I write a for loop in Rust?" is a programming question, and 10 of my 80
documents are CS and data-science threads full of people talking about
programming and which language to learn. I expect that one to land closer than
the other four, and a single distance cutoff cannot push it away without also
refusing real questions about CS courses — which is the more expensive mistake.
Writing this before I measured: I am predicting the Rust question is the one
that gets through.

---

## 4. The answer fits inside one chunk

For at least 4 of my 5 test questions, one **single** retrieved chunk contains
everything needed to answer, including that question's `expects` phrase from
`questions.py`. If the `expects` phrase is in the retrieved set but no one chunk
holds it together with the context that makes it an answer, that question counts
as a failure even if the system's final answer was right.

**Why this target:** This is the direct test of whether 800/200 were the right
bounds, because it fails in the direction my chunker actually leans. I cut on
reply boundaries, which means the failure mode I built in is chunks that are too
*small* — one person's answer running into a follow-up reply and getting split
at the marker between them. The fixed-size chunker I replaced could not fail
this way; it would have bundled both replies into the same 800-character window
by accident. So this criterion is only meaningful against my chunker, which is
the point.

I set it at 4 of 5 and not 5 of 5 for a reason I can already name: four of my
853 chunks came out under my own 200-character floor, because merging them into
a neighbour would have pushed that neighbour past the 800 cap. I chose to keep
the cap hard and let the floor be best-effort, and this criterion is where that
trade gets tested rather than argued.



---

## 5. Every source named was actually retrieved

For all 5 of my test questions, every filename the answer names is one of the
files that was actually retrieved for that question. A filename that appears in
the answer but not in the retrieved set counts as a failure, even if the rest of
the answer is correct.

**Why this target:** Criterion 2 only asks that an answer names *a* source, and
an answer can pass it while lying. My source filenames are generated from thread
titles, so they read like `parking_where_do_commuters_park_on_college_ave.txt` —
which means a plausible-looking filename is trivially easy for a model to invent
out of the words in my question. That fabrication would pass criterion 2, look
more verifiable than a real citation, and be wrong. Since my whole corpus is
anonymous student opinion with no authority behind it, the citation back to the
thread is the only thing making an answer checkable at all.

All 5 and not 4 of 5 because this is not a difficulty, it is a correctness
boundary. The filenames are handed to the model in the prompt by `build_prompt`;
naming one it was not given is not a near miss on a hard question, it is the
system making something up in exactly the place I am relying on it not to. One
failure out of five is a reason to change the prompt, not a tolerance to build
into the target.



---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 2 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath it, like this:

         ## 1. Retrieved chunks contain the answer

         For at least 4 of my 5 test questions, the retrieved chunks include
         one that contains the answer.

         **Why this target:** ...

         > **Revised in unit 2:** For at least 4 of 5 questions, the top three
         > results contain the answer.
         >
         > **Why revised:** I couldn't judge "the chunks include one that
         > contains the answer" the same way twice — I scored two questions
         > differently on Monday than on Wednesday. The new version is
         > something I can actually check.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "I said 4 of 5 but got 2 of 5, so 2 of 5 is more realistic."

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.

     The whole reason the originals stay visible is so someone can see what you
     said before you knew the answer.
     ───────────────────────────────────────────────────────────────────────── -->
