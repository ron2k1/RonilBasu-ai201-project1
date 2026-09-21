# The Unofficial Guide

**Ronil Basu** — corpus: `rutgers`, 80 real r/rutgers threads about Rutgers–New Brunswick, harvested and cleaned by `tools/harvest_rutgers.py`.

---

# Unit 1

## What This Does

This answers questions about Rutgers–New Brunswick from 80 real r/rutgers
threads — the things students tell each other rather than the things the
university publishes. I built the corpus myself with `tools/harvest_rutgers.py`
instead of using one of the three provided, so the documents are uneven in the
way real scraped text is: a guide post somebody spent an afternoon writing sits
next to a four-reply question thread, 1,067 characters at the short end and
16,017 at the long end.

It handles questions with a specific answer somewhere in that pile — where to
study on Busch at 2am, what to weigh before converting a class to Pass/No
Credit, which food places near campus students think are overrated. Every answer
cites the thread file it came from, and because the sources are anonymous
students rather than the registrar, answers say *what students said* rather than
stating it as policy.

When the corpus doesn't cover something it says so instead of guessing, and that
refusal is decided in my code by a distance cutoff before the model is called at
all — a refused question costs zero API calls. That catches genuinely unrelated
questions and, as it turned out, one of my own five test questions whose answer
is not really in the corpus.

## Chunking Strategy

- **Chunk size:** 800 characters — a ceiling, not a window
- **Chunk floor:** 200 characters — anything smaller gets merged into a neighbour
- **Overlap:** 120 characters, and only where a segment was too long to keep whole

My documents are Reddit threads, and a thread is not prose. It is a stack of
separate people answering the same question, already separated by markers my
harvester writes (`--- reply 4 (33 votes) ---`). The information that answers a
question is almost always *one person's reply*, start to finish. So the unit I
want in the vector store is one reply, not 800 characters of whatever happened
to be adjacent.

That made the size question measurable instead of a guess. I measured the
corpus before writing anything (80 documents, 1,336 natural segments):

| | min | p50 | p75 | p90 | max |
|---|---|---|---|---|---|
| document | 1,067 | 3,862 | 5,974 | 10,014 | 16,017 |
| reply (n=621) | 80 | 215 | 398 | **668** | 4,705 |
| post paragraph (n=715) | 1 | 168 | 301 | 486 | 3,240 |

**800** is the ceiling because the 90th-percentile reply is 668 characters, so
800 keeps more than nine replies in ten intact; only 4.2% of natural segments
are longer than it. **200** is the floor because the starter's chunker left
fragments of 7, 10 and 32 characters, and below roughly 200 a piece of a thread
answers nothing. **120** of overlap only applies where a segment did have to be
cut — cutting on boundaries means there is usually nothing to repair, and I did
not want the same sentence embedded twice across 800 chunks for no reason.

`split_documents` in `chunker.py` runs four passes:

1. Cut where the document already breaks — one segment per reply, one per
   paragraph of the original post.
2. Cut again only if a segment passes 800, and then at a sentence end, carrying
   the previous sentence forward.
3. Merge anything under 200 into its neighbour.
4. Prepend the thread title to every chunk.

Pass 4 is the one I did not plan and added after reading the first output. The
starter left 86.8% of its chunks with no thread title in them at all, so a chunk
about "the H lot" had nothing in it saying it was about parking at Rutgers. The
title costs about 40 characters and is charged against the 800 rather than added
on top, so a chunk is still 800 end to end.

What it changed, measured the same way on both:

| | `fallback_split` (starter) | `split_documents` (mine) |
|---|---|---|
| chunks | 608 | 853 |
| average length | 743 | 533 |
| shortest / longest | 7 / 800 | 163 / 800 |
| under 200 characters | 14 (2.3%) | 4 (0.5%) |
| start mid-sentence | 469 (77.1%) | 0 (0%) |
| no thread title | 528 (86.8%) | 0 (0%) |

The number I care about most is not in that table: **1 sentence out of 4,001 in
this corpus is longer than the cap**, which means there is exactly one place in
the whole corpus where a chunk gets cut mid-sentence. Everywhere else the 800 is
reached at a sentence boundary.

Two things I did not get right on the first pass, both found by measuring rather
than reading:

- My first overlap implementation carried the last *whole* sentence forward
  without checking it still fit, which pushed one chunk to 875 characters — over
  my own stated cap. The cap now wins over the overlap.
- Four chunks are still under the 200 floor, because merging them into their
  neighbour would have pushed that neighbour over 800. I chose to keep the cap
  hard and let the floor be best-effort. Those four are whole replies with their
  thread title attached, not fragments, so I think that is the right trade — but
  it is a trade, and criterion 4 is written against it.

## Sample Chunks

All five printed by `python app.py chunks -n 5`, spread evenly across the corpus
rather than picked — including the one that doesn't work.

**Chunk 1** — source: `academics_a_message_about_p_nc_from_a_faculty_member_please_read_thi.txt#0` — produced by: `chunker.py::split_documents`

```
THREAD: A message about P/NC from a faculty member. Please read this as well before opting to convert your grades
TOPIC: Academics

https://www.reddit.com/r/rutgers/comments/kdv5l2/fall_2020_passno_credit_form/gga7hu8/

A faculty member has commented on the P/NC megathread about converting grades for this semester, future semester and ramifications of doing so on your future. I have linked the comment above as well as included the text below. Read it especially if you are considering a masters degree. I asked them to make a post, but since they used a throwaway they’re probably not checking comment replies
```

**Chunk 2** — source: `campus_why_no_24_hour_library.txt#2` — produced by: `chunker.py::split_documents`

```
THREAD: why no 24 hour library

--- reply 3 (29 votes) ---
If you’re on Busch, ARC and SERC are both open 24 hours, so you should be able to find an open classroom. If you want more privacy, go to the second floor of SERC. Go through the door leading to the TA office hallway. Back in the day, I moved a table to the end of that hallway near the stairwell. That was my secret spot and nobody goes there..
```

**Chunk 3** — source: `cs_i_am_once_again_asking_for_you_to_consider_taking_my_summe.txt#6` — produced by: `chunker.py::split_documents`

```
THREAD: I am once again asking for...you to consider taking my summer course: Evolution, Disease, and Medicine.

--- reply 8 (3 votes) ---
I wish I could!!! Work and other classes overlap but hoping you get more people registered !
```

**Chunk 4** — source: `food_the_most_overrated_food_spots_on_near_campus_by_a_very_cyn.txt#2` — produced by: `chunker.py::split_documents`

```
THREAD: The MOST Overrated Food Spots On/Near Campus by a (Very Cynical) Senior Foodie :)

Krispy Pizza: What does everyone see in this place? The pizza is flavorless and tastes like cardboard, I'd rather eat at a chain like Domino's. I urge y'all to take the time to walk to easton and go to Daniel's for some absolutely elite Margherita or Vodka slices. PJ's is decent too, and Gio's is an absolute unit when you're trashed on a Saturday night.
```

**Chunk 5** — source: `life_rutgers_on_9_11.txt#5` — produced by: `chunker.py::split_documents`

```
THREAD: Rutgers on 9/11

Residence Life did a really good job getting people away from their TV’s and getting their mind off the events. There were a lot of group activities that took place on 9/11 and the days after. Spending time in the common areas, we learned a lot about our dorm mates that week.
```

**Reading them against "could someone answer a question using only this?":**
chunks 2, 4 and 5 each stand on their own — chunk 2 answers where to study at
night on Busch, chunk 4 answers whether Krispy Pizza is worth it and names three
alternatives, chunk 5 answers what Residence Life did on 9/11. Chunk 1 is a
whole post and reads as one, though it is an introduction that points at the
faculty comment rather than containing it.

Chunk 3 is the useful failure. It is a structurally perfect chunk — one complete
reply, 191 characters, thread title attached — and it answers nothing, because
the underlying comment is somebody being nice rather than somebody knowing
something. No chunk size fixes that. It is an ingest problem: my harvester's
`_is_answer()` filter in `tools/harvest_rutgers.py` drops replies that are
*questions*, and has no notion of a reply that is on topic and still empty. I am
leaving it in rather than hand-picking a nicer sample, because I expect it to
turn up again in unit 2 as a retrieval result that matches a question and
carries nothing.

## Sample Answer

**Question:** Where can I study on Busch campus late at night?

**Answer:** (`python app.py ask "Where can I study on Busch campus late at night?"`)

```
  (best distance 0.438, cutoff 0.6)

According to `campus_why_no_24_hour_library.txt`, you can go to ARC and SERC on Busch since both are open 24 hours. One student suggests using an open classroom or going to the second floor of SERC, specifically pointing out a quiet spot at the end of the TA office hallway near the stairwell.

Sources retrieved: campus_why_no_24_hour_library.txt, food_general_things_new_students_should_know.txt, housing_ultimate_guide_to_on_campus_housing_for_continuing_student.txt

1 model calls this session, 1016 tokens (943 in, 73 out)
```

The chunk that answer came from is Sample Chunk 2 above. "One student suggests"
is the grounding instruction doing something I added in this milestone — see
below.

And the same command on a question my corpus does not cover, which never
reaches the model at all:

```
$ python app.py ask "What can I do if the section I need is already closed on WebReg?"
  (best distance 0.744, cutoff 0.6)

I don't have enough information about that.

0 model calls this session
```

**My relevance cutoff: 0.60**

All ten best distances, `TOP_K = 5`:

| Question | In corpus? | Best distance |
|---|---|---|
| Which food places near campus do students think are overrated? | yes | **0.2157** |
| What should I think about before converting a class to Pass/No Credit? | yes | **0.4037** |
| Where can I study on Busch campus late at night? | yes | **0.4377** |
| Which bus do I take from College Avenue to Livingston? | topic yes, answer no | **0.4533** |
| ↑ *cutoff sits here: 0.60* | | |
| What can I do if the section I need is already closed on WebReg? | one passing mention | **0.7443** |
| What is the capital of Mongolia? | no | 0.7778 |
| What is the recommended dosage of ibuprofen for a headache? | no | 0.8175 |
| How do I change the oil in a diesel engine? | no | 0.8410 |
| Who won the 1994 World Cup? | no | 0.8429 |
| How do I write a for loop in Rust? | no | 0.8588 |

**The two groups did not split where I expected.** I assumed the gap would fall
between my five questions and the five out-of-scope ones. It doesn't — that gap
is 0.7443 to 0.7778, only 0.0335 wide, and the thing sitting on the wrong side
of it is one of *my own* questions.

The real split is between questions my corpus can answer (0.2157–0.4533) and
questions it can't (0.7443 and up), and that gap is **0.29 wide**. The
registration question belongs in the second group: `SPN` appears exactly once in
80 documents, in passing, inside an answer to a different question, and the
chunk holding it sits at distance **0.826** — further from the question than
four of my five out-of-scope questions are. So refusing it is the system being
right, not the system missing.

Midpoint of 0.4533 and 0.7443 is 0.599, so the cutoff is **0.60**. That is the
number the starter shipped with, which I noticed only after arriving at it. What
each direction costs me, concretely:

- **0.76** — in the naive gap — admits the registration question and hands the
  model five chunks that cannot answer it. The gate exists so that decision
  isn't left to the model.
- **0.45** loses the bus question at 0.4533, which does retrieve the right
  threads even though nothing in them names the LX.

I also swept `TOP_K` across 3, 5, 8, 12 and 20. Nothing changed until 12, where
the SPN chunk appears at rank 11 — 0.826 away. Paying for seven more chunks on
every question to reach one that far off is buying noise, so `TOP_K` stays at 5.

**What I changed in `GROUNDING_INSTRUCTION`:** two rules, both aimed at this
corpus rather than at grounding in general.

1. *Only name filenames that appear in a `[from ...]` line above.* My filenames
   are generated from thread titles, so a convincing one is easy to assemble out
   of the words in a question — and a fabricated citation passes criterion 2
   while being worse than no citation, because it looks checkable.
2. *These are anonymous student posts, not official policy — report what
   students said.* That rule is why the sample answer above says "One student
   suggests" instead of stating a quiet spot in SERC as a fact about Rutgers.

## How I Used AI

**1. The chunker's overlap, which I had to catch by measuring rather than
reading.** I gave Claude my numbers — cut on reply boundaries, 800 ceiling, 200
floor, one sentence of overlap where a segment has to be split — and asked for
the implementation. What came back did all four passes correctly and looked
right. Then I had it print min and max chunk length against the corpus, and one
chunk came out at **875 characters**, over the cap the overlap was supposed to
respect. The cause was in the overlap itself: it carried the last *whole*
sentence forward, and when that sentence was 600 characters long, tail plus next
sentence blew straight past 800. What I changed was the precedence — the tail is
now carried only if the next piece still fits underneath the cap, so the cap
wins over the overlap every time. I would not have found it by reading the code,
because the code does exactly what the description says.

**2. Pasting sample chunks into this README, which quietly corrupted them.** I
asked for the five chunks from `app.py chunks -n 5` to be written into the Sample
Chunks section. They came back transcribed, and on checking them against the
files, three of the five had the corpus's curly apostrophes silently turned into
straight ones — `they're` where the document actually says `they’re`. Small, but this
README is supposed to be evidence about my code, and evidence that disagrees
with the thing it describes is worthless. So I changed the approach instead of
the text: `tools/sync_readme_chunks.py` now generates those fenced blocks
straight out of the `Chunk` objects, and refuses if the README names a chunk
label the corpus no longer produces or claims a `produced by` the chunk itself
disagrees with. It exits 0 when nothing needed changing, so it works as a check
as well as a fixer. Same problem
had already bitten me in Milestone 1, when the harvester's post-body regex
over-matched on link posts and dragged "You are about to leave Redlib" into ten
documents — both times the lesson was to check the output against the source
rather than read the code and believe it.

<!-- ── Stretch features ─────────────────────────────────────────────────────
     Doing one? Say so here BEFORE you start. A feature this README never
     claims earns nothing.
     ───────────────────────────────────────────────────────────────────────── -->

---

# Unit 2

<!-- These sections get ADDED to what's already above. Don't delete or rewrite
     unit 1 — the point is that someone can see what you said before you knew
     how it went. -->

## Run Log — Before

<!-- Your five criteria, three runs each. `python run_eval.py --label before`
     runs the questions, puts the OUT_OF_SCOPE ones through the gate, and
     writes it all into results/ for you. Targets come from criteria.md; the
     verdict column is your call.

     Criterion 3 is measured in one deterministic pass rather than three, so
     the same number goes in all three run columns. That's correct, not lazy.

     Milestone 1. -->

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 |  |  |  |  |
| 2. Every answer names a source | 5 of 5 |  |  |  |  |
| 3. Gate stops out-of-corpus questions | 4 of 5 |  |  |  |  |
| 4. | | | | | |
| 5. | | | | | |

<!-- Underneath, paste the REAL output for each criterion from one of your
     runs — the actual text your system produced, not a description of it.
     Name the file and function that produced it. -->

## Verdicts

<!-- MET or MISSED for each of the five, against the target you wrote last
     unit — not a new one. Plus a sentence on how you decided. That sentence
     matters most where it was close.

     If your target said 4 of 5 and your runs came out 4, 3, 4, that's a MISS.
     The target has to hold, not show up occasionally.

     Milestone 2. -->

| # | Criterion | Verdict | How I decided |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |
| 3 |  |  |  |
| 4 |  |  |  |
| 5 |  |  |  |

## Diagnoses

<!-- For each miss: which stage caused it, and how. The stage alone isn't
     enough — you need the mechanism.

     Not a diagnosis: "Question 3 didn't work."
     A diagnosis:     "Question 3 asks about laundry costs. The answer is in
                       one sentence that got split across two chunks, so
                       neither chunk on its own contains it."

     The five stages: loading → chunking → embedding → retrieval → generation.

     Look for a pattern. If three misses all ask about numbers, that's one
     problem, not three.

     Missed nothing? Say so, then say honestly whether your targets were set
     low, and which one you'd tighten and to what.

     Milestone 3. -->

## The Improvement

**What I changed:**

**Why I picked it:**

<!-- Connect it to a specific diagnosis above in one sentence. If you can't,
     you picked a fix because it sounded impressive. -->

### Run Log — After

<!-- Same format, same five criteria, three runs each.
     `python run_eval.py --label after` -->

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunk contains the answer | 4 of 5 |  |  |  |  |
| 2. Every answer names a source | 5 of 5 |  |  |  |  |
| 3. Gate stops out-of-corpus questions | 4 of 5 |  |  |  |  |
| 4. | | | | | |
| 5. | | | | | |

**Did it help?**

<!-- Say plainly whether it did, and how you know. If it made things worse,
     say that — a change that backfired, honestly reported, earns full credit
     and is more interesting than one that worked. What matters is that you can
     tell.

     Milestone 4. -->

## What's Still Broken

<!-- For each criterion still missed after your fix: what you'd do about it,
     and why you stopped where you did.

     "I ran out of time" is fine if it's true. Pretending nothing is left is
     not.

     Milestone 5. -->

## What I'd Do Differently

<!-- Knowing what you know now — which of your five criteria would you write
     differently, and why?

     Milestone 5. -->
