# The Unofficial Guide

**Ronil Basu** — corpus: `rutgers`, 80 real r/rutgers threads about Rutgers–New Brunswick, harvested and cleaned by `tools/harvest_rutgers.py`.

> **This file is your submission.** Fill it in as you go — most sections get
> written during the milestone that produces them, not at the end.
>
> How the starter works, and every command you'll need, is in `RUNNING.md`.
> Leave that file alone.
>
> **Paste everything as text.** No screenshots, no video. A typed table gets
> full credit; a picture of the same table gets none.
>
> Delete these instruction blocks as you replace them. The `<!-- -->` comments
> are notes to you and don't show up when the page renders — you can leave them
> or remove them.

---

# Unit 1

## What This Does

<!-- Three or four sentences. Which corpus you picked, and the kinds of
     questions your system answers. Write it for someone who has never seen
     this repo.

     Milestone 5. -->

## Chunking Strategy

**Chunk size:** 800 characters — a ceiling, not a window
**Overlap:** 120 characters, and only where a segment was too long to keep whole

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

<!-- One complete question and answer, pasted as text, with the source line
     visible. Milestone 4. -->

**Question:**

**Answer:**

```
```

**My relevance cutoff:**

<!-- The number you set in config.py, and how you got there.

     You ran five questions your corpus covers and the five in OUT_OF_SCOPE
     that it clearly doesn't, and wrote down the best distance for each. What
     did those two groups look like? Where was the gap? Put the actual numbers
     here — the table below wants all ten rows.

     Milestone 4. -->

| Question | In corpus? | Best distance |
|---|---|---|
|  |  |  |

## How I Used AI

<!-- Two specific moments. For each: what you asked for, what came back, and
     what you changed about it.

     "I asked Claude to write the chunking function from my notes. It ignored
     the overlap, so I added that myself" is the level of detail we're after.
     "I used AI to help me code" is not.

     Milestone 5. -->

**1.**

**2.**

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
