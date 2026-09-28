# The Unofficial Guide

**Ronil Basu** — corpus: `rutgers`, 80 real r/rutgers threads about Rutgers–New Brunswick, harvested and cleaned by `tools/harvest_rutgers.py`.

---

# Unit 1

## What This Does

This answers questions about Rutgers–New Brunswick from 80 real r/rutgers
threads — the things students tell each other rather than the things the
university publishes.

I threw out all three provided corpora and built my own. Two reasons. The first
is that I go to Rutgers, so I can tell whether an answer is actually right: when
the system tells me about a quiet spot on the second floor of SERC, I know
whether that's true, and I can't say that about a corpus of invented campus
posts. The second is that scraping it myself meant I owned the problems. Reddit
blocks direct scraping, so `tools/harvest_rutgers.py` goes through a mirror and
solves a proof-of-work challenge to get the HTML, then cleans it in a separate
stage that needs no scraping library at all — so anyone grading this can re-run
the build without installing what I installed.

That choice is also why the documents are lumpy in a way the provided corpora
aren't. A guide post somebody spent an afternoon writing sits next to a
four-reply question thread: 1,067 characters at the short end, 16,017 at the
long end. That spread is the entire reason Milestone 3 was interesting for me.

The questions it handles are the ones with a specific answer somewhere in that
pile — where to study on Busch at 2am, what to weigh before converting a class
to Pass/No Credit, which food places near campus students think are overrated.
Every answer cites the thread file it came from. Because my sources are
anonymous students and not the registrar, I made answers report *what students
said* rather than stating it as policy — one person with four upvotes is not the
same claim as a rule.

When the corpus doesn't cover something, the system says so instead of guessing,
and I decide that in my own code with a distance cutoff before the model is ever
called — a refused question costs zero API calls. That catches questions from
another world entirely, and it also caught one of my own five test questions,
which turned out to be about something my corpus barely mentions.

## Chunking Strategy

- **Chunk size:** 800 characters — a ceiling, not a window
- **Chunk floor:** 200 characters — anything smaller gets merged into a neighbour
- **Overlap:** 120 characters, and only where a segment was too long to keep whole

I ran the starter's chunker first and read what it gave me, which is how I
ended up rewriting it. Reading my own documents back, the thing that struck me
is that a Reddit thread is not prose. It's a stack of separate people answering
the same question, and my harvester already writes the seams between them
(`--- reply 4 (33 votes) ---`). When I looked at which text actually answered
anything, it was almost always *one person's reply*, start to finish. Nobody
answers half a question and hands off. So the unit I want in the vector store is
one reply — not 800 characters of whatever happened to sit next to it.

Once I'd decided that, the numbers stopped being a guess and became something I
could measure, so I measured the corpus before writing a line of the new
chunker (80 documents, 1,336 natural segments):

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

Pass 4 wasn't in my plan. I added it after reading the first batch of chunks and
realising I couldn't tell what half of them were about. The starter left 86.8%
of its chunks with no thread title anywhere in them, so a chunk discussing "the
H lot" had nothing inside it saying it was about parking, or Rutgers, or
anything. I knew what it meant because I'd just scraped it; the embedding model
had no such advantage. So I put the thread title on the front of every chunk and
charged its ~40 characters *against* the 800 rather than adding it on top, so a
chunk is still 800 end to end and my cap doesn't quietly become 840.

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

These are the five `python app.py chunks -n 5` gave me, spread evenly across the
corpus. I deliberately did not go shopping for five flattering ones — I took the
spread as printed, which is why chunk 3 is sitting in here doing nothing.

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

I read all five against the question the milestone asks — *could someone answer
something using only this, without reading what came before or after?*

Chunks 2, 4 and 5 pass. Chunk 2 tells you where to study at night on Busch and
names the building. Chunk 4 tells you Krispy Pizza isn't worth it and gives you
three places to go instead. Chunk 5 tells you what Residence Life actually did
on 9/11. Each one is one person's whole thought with the thread title on it, and
I could hand any of them to somebody with no other context. Chunk 1 is a whole
post and reads as one, though I'd note it's an *introduction* pointing at a
faculty comment rather than the comment itself — it tells you the answer exists
and where, which is weaker than telling you the answer.

Chunk 3 is the one I want to point at, because it's the failure I found useful.
Structurally it is perfect: one complete reply, 191 characters, inside both my
floor and my cap, thread title attached. And it answers nothing, because the
person writing it was being nice rather than being informative. No chunk size
fixes that — I could set the cap anywhere and this chunk would still be empty.

What it actually exposes is a gap one stage earlier, in my own harvester.
`_is_answer()` in `tools/harvest_rutgers.py` throws away replies that are
*questions*, which I wrote in Milestone 1 after seeing follow-up questions get
retrieved as though they were answers. It has no notion of a reply that is on
topic, well-formed, and still says nothing. I could have swapped this chunk for
a nicer one and nobody would have known, but I'd rather have it on the page: I
expect it back in unit 2 as a retrieval hit that matches a question and carries
no information, and when that happens I'll already know where to look.

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

**I wrote a prediction into `criteria.md` before I measured any of this, and I
got it wrong.** Under criterion 3 I said: *"I am predicting the Rust question is
the one that gets through."* My reasoning was that 10 of my 80 documents are CS
and data-science threads, so a programming question should land closest to them.

Rust came back the **furthest away of all ten**, at 0.8588. The closest
out-of-scope question was the capital of Mongolia. When I went and read those CS
threads again, the reason was obvious in hindsight: they talk about *which
professor to take* and *whether to do a minor*, not about code. A question about
`for` loop syntax shares almost no vocabulary with them. I was reasoning about
topic the way I think about it, and the embedding model is reasoning about
words. That's the most useful thing I learned in this milestone, and I only
learned it because I had to commit to a number before I could see the answer.

**The two groups also did not split where I expected.** I assumed the gap would
fall between my five questions and the five out-of-scope ones. It doesn't — that
gap is 0.7443 to 0.7778, only 0.0335 wide, and the thing sitting on the wrong
side of it is one of *my own* questions.

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

**1. I specified the chunker, Claude implemented it, and the bug was in the one
rule I hadn't thought hard enough about.** I did the measuring first — reply
lengths, paragraph lengths, what percentage of segments cross which cap — and
came to the spec myself: cut on reply boundaries, 800 ceiling, 200 floor, one
sentence of overlap where a segment has to be hard-split. I handed Claude those
four rules and asked for the implementation rather than asking it what to do,
because the decision was the part I wanted to own.

What came back did all four passes and read correctly to me. I didn't trust that
— I'd already been burned in Milestone 1 by code that read fine — so before
accepting it I had it print min and max chunk length across all 80 documents.
One chunk came back at **875 characters**, over my own cap.

The bug was inside the overlap rule, and it was arguably my spec's fault as much
as the implementation's: "carry one sentence forward" is ambiguous when a
sentence is 600 characters long, and nothing in what I'd written said which of
my two numbers wins. So I made that call explicitly — the tail is carried only
if the next piece still fits underneath the cap, so the ceiling beats the
overlap every time — and had it changed to match. Reading the code would never
have caught this, because the code did exactly what I'd asked for. Only the
measurement disagreed.

**2. I asked for my sample chunks to be pasted into this README, and they came
back quietly corrupted.** Straightforward request: take the five chunks
`app.py chunks -n 5` printed and put them in the Sample Chunks section. They came
back *transcribed* rather than copied, and when I diffed them against the actual
files, three of the five had the corpus's curly apostrophes silently flattened
into straight ones — `they're` where my document actually says `they’re`.

Nobody would have marked me down for it. But this section is supposed to be
evidence about my code, and evidence that doesn't match the thing it describes
is worth nothing — and it would have gone on being wrong every time I re-chunked
and re-pasted. So rather than fixing the three characters, I changed the process
so the class of mistake can't recur: `tools/sync_readme_chunks.py` generates
those fenced blocks directly from the `Chunk` objects, and hard-fails if the
README names a chunk label my corpus no longer produces — which happens on every
re-chunk, since chunk indices renumber — or claims a `produced by` the chunk
itself disagrees with. It exits 0 when nothing needed changing, so I can run it
as a check before committing rather than only as a repair.

That's the same lesson as the first moment, and it's the one I'm actually taking
out of this project: the failures I hit weren't code that looked wrong, they
were code that looked right and disagreed with the data. In Milestone 1 it was a
regex that over-matched on link posts and dragged "You are about to leave
Redlib" into ten of my documents. Every time, the fix started with checking the
output against the source instead of reading the code and believing it. Same problem
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

`python run_eval.py --label before`, run on 2026-09-28 at 02:37. Five questions,
three runs each with caching off, then the five `OUT_OF_SCOPE` questions through
the gate once. The full transcript is `results/run_2026-09-28_0237_before.md`.
Every chunk it retrieved on every run is in the `.json` beside it, and
`python scorer.py results/run_2026-09-28_0237_before.json` rebuilds this table
from that file alone, with no index and no API key.

`scorer.py` was written and committed before this run existed (`e7bd157`), so
the rule for what counts as a pass was fixed before there were results for it
to fit.

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunks contain the answer | 4 of 5 | 3/5 | 3/5 | 3/5 | MISSED |
| 1r. Revised: a retrieved chunk, read on its own, answers | 4 of 5 | 3/5 | 3/5 | 3/5 | MISSED |
| 2. Every answer names a source | every answer produced | 4/4 | 4/4 | 4/4 | MET |
| 3. Gate stops out-of-corpus questions | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 4. The answer fits inside one chunk | 4 of 5 | 3/5 | 3/5 | 3/5 | MISSED |
| 5. Every source named was actually retrieved | 5 of 5 | 5/5 | 5/5 | 5/5 | MET |

Row 1r is the revision of criterion 1 I made in `criteria.md`, written under the
original. It came after this run and before any change to the system, and it
gives the same count as the original. Why I made it is under Verdicts. Row 1r
and row 4 are scored by the same function, `scorer.py::one_chunk_answers`, so
they can't come out different. Revised criterion 1 asks for one retrieved chunk
that answers, which is what criterion 4 already asked for.

Criterion 2 is out of 4 because the gate refused the WebReg question on all
three runs at 0.744, before the model ever saw it, and criterion 2 is about
answers the system writes. I explain that call under Verdicts.

Every count came out the same on all three runs, and the brief says to be
suspicious of that. These are three real runs. `run_eval.py` passes
`cache=False`, the session reported `12 model calls this session, 12555 tokens
(11394 in, 1161 out)` with nothing served from cache, and the answers read
differently each time: run 3 of the Busch question brings up residence lounges
and the other two don't. The counts hold still because criteria 1, 3 and 4
depend only on retrieval, which gives the same chunks every time. The two
criteria that depend on the model held on all 12 answers it wrote.

What the system actually printed, all from run 1 of
`results/run_2026-09-28_0237_before.md`:

**Criterion 1.** Retrieval by `store.py::search`, called from
`run_eval.py::run_once` and written out by `run_eval.py::write_report`. One hit
and the two misses:

```
### Where can I study on Busch campus late at night? — run 1
- Best distance: 0.4377 (passed the gate)
- Chunks, nearest first: `campus_why_no_24_hour_library.txt#2` 0.4377, `campus_why_no_24_hour_library.txt#0` 0.4725, `housing_ultimate_guide_to_on_campus_housing_for_continuing_student.txt#19` 0.4791, `food_general_things_new_students_should_know.txt#3` 0.4877, `food_general_things_new_students_should_know.txt#2` 0.5013

### Which bus do I take from College Avenue to Livingston? — run 1
- Best distance: 0.4533 (passed the gate)
- Chunks, nearest first: `commuting_new_bus_route_just_dropped.txt#0` 0.4533, `commuting_new_bus_route_just_dropped.txt#2` 0.4773, `food_general_things_new_students_should_know.txt#3` 0.4947, `commuting_new_bus_route_just_dropped.txt#1` 0.5275, `cs_little_rutgers_things_i_wish_i_knew_earlier.txt#8` 0.5436

### What can I do if the section I need is already closed on WebReg? — run 1
- Best distance: 0.7443 (refused by the gate)
- Chunks, nearest first: `commuting_professor_needing_student_advice_with_online_course_starts.txt#5` 0.7443, `registration_fall_2023_class_registration.txt#0` 0.7448, `registration_i_got_tired_of_using_six_different_rutgers_tools_to_plan_a.txt#0` 0.7783, `academics_help_am_i_gonna_graduate.txt#1` 0.7865, `commuting_professor_needing_student_advice_with_online_course_starts.txt#6` 0.7985
```

`campus_why_no_24_hour_library.txt#2` is Sample Chunk 2 from unit 1, the one
that names SERC. None of the five bus chunks contains "LX" and none of the five
WebReg chunks contains "SPN".

**Criterion 2.** Answers by `generate.py::answer_from_chunks`, refusal by
`gate.py::check`:

```
### Where can I study on Busch campus late at night? — run 1
According to a student post on Busch, both the ARC and SERC are open 24 hours, and you can find an open classroom there, such as the second floor of SERC [from campus_why_no_24_hour_library.txt].

### Which bus do I take from College Avenue to Livingston? — run 1
Based on the provided documents, there is no mention of which bus to take from College Avenue to Livingston. 

[from commuting_new_bus_route_just_dropped.txt, from food_general_things_new_students_should_know.txt, from cs_little_rutgers_things_i_wish_i_knew_earlier.txt]

### What can I do if the section I need is already closed on WebReg? — run 1
I don't have enough information about that.
```

**Criterion 3.** `run_eval.py::check_out_of_scope`, cutoff 0.6:

```
| Out-of-scope question | Best distance | Gate |
|---|---|---|
| What is the capital of Mongolia? | 0.778 | refused |
| How do I change the oil in a diesel engine? | 0.841 | refused |
| Who won the 1994 World Cup? | 0.843 | refused |
| What is the recommended dosage of ibuprofen for a headache? | 0.818 | refused |
| How do I write a for loop in Rust? | 0.859 | refused |
```

**Criterion 4.** Chunks by `chunker.py::split_documents`, checked by
`scorer.py::one_chunk_answers`. This is
`academics_pass_no_credit_faq_as_it_stands_right_now_way_before_the_p.txt#1`,
fourth nearest for the Pass/No Credit question, and it is the one chunk all
three of that question's answers were built from:

```
THREAD: Pass/No Credit FAQ as it stands right now way before the Provost puts it up

Here’s the most important one for r/Rutgers: P/NC CLASSES WILL COUNT TOWARD MAJORS, PREREQUISITES, WHATEVER ELSE that only needs a C to happen. If you need a B, (Math300 CS, financial accounting) contact an advisor. The waters get murky with the B required rules. My source on this (the first part) is Dr. G himself. Consulting an advisor prior to making the decision is recommended

Additional notes:
```

**Criterion 5.** The answer from `generate.py::answer_from_chunks`, the sources
from `store.py::search`:

```
### Which food places near campus do students think are overrated? — run 1
- Sources retrieved: dining_the_best_food_spots_on_near_campus_from_a_senior_foodie.txt, food_the_most_overrated_food_spots_on_near_campus_by_a_very_cyn.txt

Based on the student posts, RU Hungry is described as the "absolute KING of overrated cuisine" and is mostly hyped for late-night eating after the bars rather than for lunch [from food_the_most_overrated_food_spots_on_near_campus_by_a_very_cyn.txt]. Additionally, Krispy Pizza is called overrated because a student feels its pizza is flavorless and tastes like cardboard [from food_the_most_overrated_food_spots_on_near_campus_by_a_very_cyn.txt]. Another student also mentions that places like Hansel get much of their hype from being eaten at 2 AM when trashed rather than during sober hours [from food_the_most_overrated_food_spots_on_near_campus_by_a_very_cyn.txt].
```

Three citations, all to the same file, and that file is one of the two that
were retrieved.

## Verdicts

| # | Criterion | Verdict | How I decided |
|---|---|---|---|
| 1 | Retrieved chunks contain the answer | MISSED | 3 of 5 on all three runs against a target of 4, and the revised version under it in `criteria.md` also gives 3 on all three. |
| 2 | Every answer names a source | MET | All 12 answers the model wrote named a file. The one thing that named nothing was the gate's refusal, which the model never wrote. |
| 3 | Gate stops out-of-corpus questions | MET | 5 of 5 against a target of 4, and the closest of them, Mongolia at 0.778, still cleared the cutoff by 0.178. |
| 4 | The answer fits inside one chunk | MISSED | 3 of 5 on all three runs against a target of 4, missed on the same two questions as criterion 1. |
| 5 | Every source named was actually retrieved | MET | Every filename in all 12 written answers is one that was retrieved for that question, which the target of 5 of 5 needed on every run. |

I revised criterion 1 without lowering it. The count is 3 under both versions,
so the revision rescued nothing. I made it because the phrase check in my
scorer and the words of the criterion ("contains the answer") come apart on two
of my five questions, in opposite directions, and the reasons are written out
under the original in `criteria.md`. I wanted that settled before the after run
rather than discovered in it. The original row stays in the run log with the
revision under it.

Criterion 2 is the call I'd expect someone to argue with, so I argued it myself.
The case for MISSED is that the template's target says 5 of 5, and a student
asking about WebReg gets "I don't have enough information about that" with no
file named. From where they sit, that is the system's answer. The case for MET
is what I wrote in unit 1: the reason under criterion 2 covers "every answer
that gets produced at all", and it relies on the gate so the model never
answers from nothing. The refusal comes from `gate.py`, not the model, and
there is nothing for it to cite. A filename printed under a refusal would be
citing a document that supports nothing. So I scored criterion 2 over the
answers the model wrote, which is 4 of 4 on every run.

The pass on criterion 2 I trust least is the bus question. All three runs said
"there is no mention of which bus to take from College Avenue to Livingston" and
then listed all three retrieved files. By the letter that names a source. What
it actually does is cite three documents for the claim that none of them says
anything. My grounding rule says to name the document the answer came from,
and it has nothing to say for the case where no document is where the answer
came from. The verdict stays MET because the criterion asks for a name and got
one. The problem goes under What's Still Broken.

Criterion 3 was never close. In unit 1 I set 4 of 5 so the Rust question had
room to get through, and Rust came back furthest away of all. With the nearest
out-of-scope question at 0.778 against a cutoff of 0.6, these five are too far
from Rutgers to put the gate under any pressure. I come back to that under
What I'd Do Differently.

Criterion 5 held on 15 answers, but only 12 of them tested anything. The three
refusals name no file, so they pass without trying. Of the 12 real ones, 8 cite
with the exact `[from ...]` tag `build_prompt` puts in the prompt, and the other
4 wrap the same filename in backticks. Either way the model was repeating a
string it had just been handed. That's why it held, and it means this run
never tried the case I wrote the criterion for, which is a question whose words
look like a filename that wasn't retrieved.

## Diagnoses

Criteria 1 and 4 both missed, on the same two questions, for the same reasons,
so this is two diagnoses rather than four. The run log only shows the top five,
which tells me a question missed but not by how much. So I ranked every chunk
in the index against each question with `tools/answer_rank.py`, which is
retrieval only and costs no model calls. The full output for all five is in
`results/answer_rank_before.txt`. These are the two that missed:

```
Which bus do I take from College Avenue to Livingston?
  expects 'LX': 1 of 853 chunks hold it (top 5 ends at 0.5436)
  rank  18  0.6107  cs_little_rutgers_things_i_wish_i_knew_earlier.txt#1
            "LX, H, and A buses go around College Ave from Student Center --> Scott Hall --> SAC."

What can I do if the section I need is already closed on WebReg?
  expects 'SPN': 1 of 853 chunks hold it (top 5 ends at 0.7985)
  rank  11  0.8259  academics_anonymous_academic_advisor_here_ask_me_your_questions.txt#3
            "Just know that if you are holding a seat, and SPNs were given for that class, that class has more students than what it should."
```

The check the brief suggests for when you're stuck settles the first half of
both. Print the chunks that came back, and if the answer isn't in any of them,
the problem is before generation. It isn't in any of them. Generation did its
job on both questions. Three runs out of three, the model said the documents
never mention which bus to take from College Avenue to Livingston, instead of
reaching for the LX from its own knowledge. The gate refused the WebReg
question before the model ever saw it.

### The bus question: loading first, then chunking

The root is loading, meaning what my harvester collected. "LX" appears in
exactly one sentence of the 80 threads: "LX, H, and A buses go around College
Ave from Student Center --> Scott Hall --> SAC." That sentence is about which
buses loop around College Ave. It never says the LX goes to Livingston, and
nothing else in the corpus names the route. The three bus chunks that did come
back are from one thread about a new route between Livingston and the stadium
lot, and none of them names the LX either. There is no chunk in the index that
a perfect retriever could hand the model for this question.

Chunking made it worse. That sentence sits in a list post, "Little Rutgers
things I wish I knew earlier", where every tip is its own paragraph. The bus tip
is 225 characters, so it clears my 200 floor on its own. The two tips after it
don't: printing from your laptop is 112 and print release stations is 195, and
`_merge_small` in `chunker.py` folds anything under the floor into the chunk in
front of it. So chunk #1 is one bus tip followed by two printer tips, and more
than half of what the embedding model reads in it is about printers. It lands
18th at 0.6107, when the fifth slot closes at 0.5436.

This is the opposite of what I predicted when I wrote criterion 4. I expected
my chunker to fail by cutting too small, with one person's answer split from a
follow-up at a reply marker. That didn't happen on any of my five questions.
The chunking fault the test actually found is the merge pass gluing unrelated
things together, and it isn't a one-off: 27 chunks in the index are two or
more list items the merge pass glued together, across 10 of the 80 threads.
The floor was calibrated on Reddit replies, where anything under 200
characters really is a fragment. In a list post a 112-character tip is a
complete thought.

### The WebReg question: loading first, then embedding

The root is loading again, in the same shape. "SPN" appears once in 80 threads,
in an advisor's reply to someone asking whether dropping a class gives their
seat away. It mentions SPNs to explain why the class stays closed, and never
says a student can ask for one, which is the answer to my question. My
registration topic is three threads and none of them covers it.

Embedding is why the one mention can't be found. The question says section,
closed and WebReg. The chunk says seat, science course, SPNs and closed.
"Closed" is the only word they share, and SPN is a Rutgers abbreviation the
embedding model has no meaning for, so it does nothing to pull the chunk toward
a registration question. It ranks 11th at 0.8259.

In unit 1 I wrote that this chunk is further from the question than four of my
five out-of-scope questions are. Checking it properly now, it's two. 0.8259 is
past Mongolia (0.778) and ibuprofen (0.818) and closer than the other three
(0.841, 0.843, 0.859). The same sentence is in the comment above `TOP_K` in
`config.py`. I'm leaving both as they were written and correcting it here.

Reading the WebReg question's top five turned up something my scoring can't
see. The third chunk, at 0.7783, is a student's launch post for a scheduling
app. Its feature list includes "a course sniper" and "Seat alerts for closed
sections", which is a real, if weak, answer to "what can I do if the section is
closed". My `expects` phrase is "SPN", so neither version of criterion 1 counts
it. I'm not changing the phrase now that I've seen it, because picking the
answer after seeing what retrieval returned is exactly what writing `expects`
in unit 1 was supposed to prevent. It does change the diagnosis. For this
question retrieval did bring back something usable, and the gate refused the
question anyway, because a cosine cutoff on the best chunk can't tell a
0.7443 chunk that says nothing from a 0.7783 chunk that says something.

### The pattern

Both misses are one problem. Each answer is a Rutgers abbreviation, LX or SPN,
that appears exactly once in 80 threads. Each time it's an aside inside a chunk
about something else, in a sentence that doesn't actually state the answer. The
three questions that passed all have their answer in a chunk whose whole
subject is the question: a thread about 24-hour study spots, a Pass/No Credit
FAQ, a list of overrated food. Students on r/rutgers don't write out the things
every Rutgers student already knows, like which bus goes to Livingston, so my
harvester collected threads that mention them in passing and never explain them.
The embedding model can't make up the difference, because it has never seen LX
or SPN and can only find those chunks through the words around them. Those
words are about printers and dropping classes.

The part of that I can change inside this unit is chunking. The corpus stays
the corpus; adding threads that happen to answer my five questions would be
writing the test's answers into the system.

## The Improvement

**What I changed:** One rule in `_merge_small` in `chunker.py`: a list item
never joins a chunk that already holds one. Everything else about merging is
the same. A short intro still takes the first item under it, a plain paragraph
still folds into the item it follows, two short replies still merge, and the
800 cap still wins. A list item is a piece starting with `- `, `* `, `• ` or a
number like `1.`. A whole reply starts with its `--- reply` marker and never
counts, but when a long reply gets cut at a sentence end, a later piece of it
can start with a dash, and six in the corpus do. None of the six was ever
merged with another list item, and I checked that the old and new chunkers
differ in exactly the 10 threads where the merge was gluing tips together. The
tests are in `tests/test_chunker.py`,
built from the real pieces of the LX thread, and one of them runs the whole
corpus and fails if any chunk still holds two list items the merge joined.

That rule is the only change to the pipeline in this unit. Everything else
that's new in the repo measures the pipeline and changes no answer:
`scorer.py` and its tests, the JSON file and chunk list `run_eval.py` now
writes next to each report, and `tools/answer_rank.py` and
`tools/gate_probe.py`, which only call retrieval.

It has a cost I could see before running anything. The corpus now comes out as
910 chunks instead of 853, and 47 of them are under the 200 floor instead of 4.
The shortest went from 163 characters to 64. Those short ones are single tips
with their thread title, like "Most campus centers have microwaves so you can
heat up your food."

I indexed it as a second variant, `python app.py --variant lists index`, so
the old index is still there to compare against, and ran the after eval with
`python run_eval.py --label after --variant lists`. The old index is the
`default` one. Indexing `default` at this commit would build it with the new
rule, so to rebuild the before side of `tools/answer_rank.py` and
`tools/gate_probe.py` from scratch, check out `03d83b1`, run
`python app.py index` there, and come back to this commit to run them.

**Why I picked it:** The bus diagnosis says the LX sentence ranked 18th
because the merge pass buried it under two printer tips, and this is the rule
that did the burying.

It's also the only fix on the table that isn't aimed at my five questions. The
root cause of both misses is loading, and adding threads that happen to say
which bus goes to Livingston would be writing my test's answers into the
corpus. Lowering the gate would let the WebReg question through, but the best
chunk it would get is a professor asking for advice on an online course, and
it would give up the 0.178 margin criterion 3 has. Expanding "LX" and "SPN" in
the query would help exactly two questions, both of them mine. The merge rule
touches 27 chunks across 10 threads, and the bus question is only one of them.

**What I expected before running it:** I wrote this down before building the
new index.

- The bus question's LX chunk will now be one bus tip under a thread title,
  and I think it moves into the top five. That would take the original
  criterion 1 from 3 of 5 to 4 of 5.
- The revised criterion 1 and criterion 4 won't move, because the fix can't
  change what the sentence says. It says the LX goes around College Ave,
  never that it goes to Livingston.
- The model might now say "LX" in its bus answer, because it will be looking
  at a sentence about the LX. If it does, the judge will mark it right, since
  the judge only checks for the phrase. That would be the P/NC problem
  showing up again, not a real fix, and I'd have to say so.
- The WebReg question is the one I'm least sure of. "Seat alerts for closed
  sections" is now a chunk of its own, and a short chunk about closed sections
  could get under 0.6. If it does, the gate lets the question through, and the
  answer will be seat alerts, not SPN, which my judge will mark wrong.
- In 17 of the 47 short chunks the thread title is more than half the text,
  so the embedding is mostly the title. If anything pulls an out-of-scope
  question under 0.6 it's one of those, so criterion 3 is the one that could
  get worse.

### Run Log — After

`python run_eval.py --label after --variant lists`, run on 2026-09-28 at 02:58
against the index built with the new rule. Same five questions, same three runs
with caching off, same five out-of-scope questions. The transcript is
`results/run_2026-09-28_0258_after.md`, every retrieved chunk is in the `.json`
beside it, and `python scorer.py results/run_2026-09-28_0258_after.json`
rebuilds this table. The session reported `12 model calls this session, 11846
tokens (10710 in, 1136 out)`.

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunks contain the answer | 4 of 5 | 4/5 | 4/5 | 4/5 | MET |
| 1r. Revised: a retrieved chunk, read on its own, answers | 4 of 5 | 3/5 | 3/5 | 3/5 | MISSED |
| 2. Every answer names a source | every answer produced | 4/4 | 4/4 | 4/4 | MET |
| 3. Gate stops out-of-corpus questions | 4 of 5 | 5/5 | 5/5 | 5/5 | MET |
| 4. The answer fits inside one chunk | 4 of 5 | 3/5 | 3/5 | 3/5 | MISSED |
| 5. Every source named was actually retrieved | 5 of 5 | 5/5 | 5/5 | 5/5 | MET |

Both run logs side by side:

| Criterion | Target | Before (runs 1, 2, 3) | After (runs 1, 2, 3) | Verdict |
|---|---|---|---|---|
| 1. Retrieved chunks contain the answer | 4 of 5 | 3/5, 3/5, 3/5 | 4/5, 4/5, 4/5 | MISSED → MET |
| 1r. Revised: a retrieved chunk, read on its own, answers | 4 of 5 | 3/5, 3/5, 3/5 | 3/5, 3/5, 3/5 | MISSED → MISSED |
| 2. Every answer names a source | every answer produced | 4/4, 4/4, 4/4 | 4/4, 4/4, 4/4 | MET → MET |
| 3. Gate stops out-of-corpus questions | 4 of 5 | 5/5, 5/5, 5/5 | 5/5, 5/5, 5/5 | MET → MET |
| 4. The answer fits inside one chunk | 4 of 5 | 3/5, 3/5, 3/5 | 3/5, 3/5, 3/5 | MISSED → MISSED |
| 5. Every source named was actually retrieved | 5 of 5 | 5/5, 5/5, 5/5 | 5/5, 5/5, 5/5 | MET → MET |

Every count was the same on all three runs again, and these are three real
runs too. The session made 12 model calls with nothing served from cache, and
the answers read differently each time: run 2 of the Krispy Pizza question
cites only the overrated-spots thread where runs 1 and 3 also cite the senior
foodie's, and run 2 of the P/NC question is the only one that mentions the May
22nd deadline. The counts hold still for the same reason as before. Criteria
1, 3 and 4 depend only on retrieval, and the model held on criteria 2 and 5
in all 12 answers it wrote.

What the system actually printed, all from run 1 of
`results/run_2026-09-28_0258_after.md`:

**Criterion 1.** Retrieval by `store.py::search` over chunks from
`chunker.py::split_documents`, called from `run_eval.py::run_once` and written
out by `run_eval.py::write_report`. The question the fix moved and the one it
didn't:

```
### Which bus do I take from College Avenue to Livingston? — run 1
- Best distance: 0.4448 (passed the gate)
- Chunks, nearest first: `cs_little_rutgers_things_i_wish_i_knew_earlier.txt#1` 0.4448, `cs_little_rutgers_things_i_wish_i_knew_earlier.txt#7` 0.4518, `commuting_new_bus_route_just_dropped.txt#0` 0.4533, `commuting_new_bus_route_just_dropped.txt#2` 0.4773, `cs_little_rutgers_things_i_wish_i_knew_earlier.txt#28` 0.4805

### What can I do if the section I need is already closed on WebReg? — run 1
- Best distance: 0.7443 (refused by the gate)
- Chunks, nearest first: `commuting_professor_needing_student_advice_with_online_course_starts.txt#11` 0.7443, `registration_fall_2023_class_registration.txt#0` 0.7448, `registration_i_got_tired_of_using_six_different_rutgers_tools_to_plan_a.txt#4` 0.7626, `academics_help_am_i_gonna_graduate.txt#1` 0.7865, `commuting_professor_needing_student_advice_with_online_course_starts.txt#12` 0.7985
```

`cs_little_rutgers_things_i_wish_i_knew_earlier.txt#1` is the bus tip on its
own, and it contains "LX". None of the five WebReg chunks contains "SPN".

**Criterion 2.** Answers by `generate.py::answer_from_chunks`, refusal by
`gate.py::check`. The bus answer is the same sentence as before the fix:

```
### Where can I study on Busch campus late at night? — run 1
According to a student post in `campus_why_no_24_hour_library.txt`, ARC and SERC on Busch are both open 24 hours, so you can find an open classroom there. The same student suggested going to the second floor of SERC for more privacy, specifically near the stairwell at the end of the TA office hallway.

### Which bus do I take from College Avenue to Livingston? — run 1
Based on the provided documents, there is no mention of which bus to take from College Avenue to Livingston.

[from cs_little_rutgers_things_i_wish_i_knew_earlier.txt, commuting_new_bus_route_just_dropped.txt]

### What can I do if the section I need is already closed on WebReg? — run 1
I don't have enough information about that.
```

**Criterion 3.** `run_eval.py::check_out_of_scope`, cutoff 0.6. Only the Rust
question moved, from 0.859 to 0.855:

```
| Out-of-scope question | Best distance | Gate |
|---|---|---|
| What is the capital of Mongolia? | 0.778 | refused |
| How do I change the oil in a diesel engine? | 0.841 | refused |
| Who won the 1994 World Cup? | 0.843 | refused |
| What is the recommended dosage of ibuprofen for a headache? | 0.818 | refused |
| How do I write a for loop in Rust? | 0.855 | refused |
```

**Criterion 4.** Chunks by `chunker.py::split_documents`, checked by
`scorer.py::one_chunk_answers`. This is the bus question's nearest chunk after
the fix. It contains "LX", which is why criterion 1 counts it, and it never
says the LX goes to Livingston, which is why criterion 4 doesn't:

```
THREAD: Little Rutgers things I wish I knew earlier.

- F and EE buses go around College Ave from SAC --> Student Center --> Scott Hall. LX, H, and A buses go around College Ave from Student Center --> Scott Hall --> SAC. You can take a bus from Scott Hall to SAC and vice versa.
```

**Criterion 5.** The answer from `generate.py::answer_from_chunks`, the sources
from `store.py::search`:

```
### Which food places near campus do students think are overrated? — run 1
- Sources retrieved: dining_the_best_food_spots_on_near_campus_from_a_senior_foodie.txt, food_the_most_overrated_food_spots_on_near_campus_by_a_very_cyn.txt

Based on the student posts, RU Hungry and Krispy Pizza are mentioned as overrated food spots, with students noting that places like RU Hungry and Hansel mostly get their hype from being eaten late at night while drunk (`food_the_most_overrated_food_spots_on_near_campus_by_a_very_cyn.txt`). Additionally, one student mentioned feeling that some places get more hype than they deserve or have gone downhill (`dining_the_best_food_spots_on_near_campus_from_a_senior_foodie.txt`).
```

Two files named, and both of them were retrieved.

And where the answer-holding chunks rank now, from
`python tools/answer_rank.py --variant lists`, saved in
`results/answer_rank_after.txt`:

```
Which bus do I take from College Avenue to Livingston?
  expects 'LX': 1 of 910 chunks hold it (top 5 ends at 0.4805)
  rank   1  0.4448  cs_little_rutgers_things_i_wish_i_knew_earlier.txt#1
            "LX, H, and A buses go around College Ave from Student Center --> Scott Hall --> SAC."

What can I do if the section I need is already closed on WebReg?
  expects 'SPN': 1 of 910 chunks hold it (top 5 ends at 0.7985)
  rank  12  0.8259  academics_anonymous_academic_advisor_here_ask_me_your_questions.txt#3
            "Just know that if you are holding a seat, and SPNs were given for that class, that class has more students than what it should."
```

**Did it help?**

It helped retrieval and it didn't change a single answer, and the second part
is the one that counts.

Retrieval moved exactly where I aimed it. The chunk holding the corpus's only
LX sentence went from 18th at 0.6107 to 1st at 0.4448. The bus question's top
five used to be three chunks from the new-route thread, a reply listing which
café is on which campus, and one chunk from the list post that was four tips
glued together: bus stops at Public Safety, the Macs in the ARC computer lab,
getting from Cook-Douglass to Buell, and walking to Sears. Now it's three bus
tips from the list post, each on its own (the LX loop, the B-He stop, and that
walking often beats the bus on Busch and Cook-Douglass), and two chunks from
the new-route thread. That took criterion
1 as I originally wrote it from 3 of 5 to 4 of 5 on all three runs, which
meets its target.

The answer didn't move. The model had the LX sentence at the top of its
context on all three runs and still said the documents never mention which bus
goes from College Avenue to Livingston. It's the same sentence it wrote before
the fix, with a different list of files after it. It's right. The sentence says the LX loops around College Ave and
nothing about Livingston, and my grounding instruction tells it not to fill
that in from what it knows. That's also why the risk I was most worried about,
the judge counting a bus answer that just says "LX", never happened. The
revised criterion 1 and criterion 4 stayed at 3 of 5 and are still missed,
which is what I predicted.

So the criterion I wrote in unit 1 says the fix worked, and the revised one
says it didn't, and the revised one is right. A student asking this question
gets the same answer they got before. This is the case I revised criterion 1
for: the original counted a chunk with "LX" in it as an answer, so it scored
the fix as a win while the answer stayed the same. What the fix does show is
that the chunking half of the bus diagnosis was real. Once the printer tips
were gone, the sentence was the easiest thing in the index to find. What's
left is the loading half, a sentence that doesn't hold the answer.

Nothing a criterion measures got worse. The WebReg question is still refused
at 0.7443. The
seat-alerts chunk did get closer, from 0.7783 to 0.7626, and moved into third,
but it's nowhere near 0.6. Criterion 3 held at 5 of 5, and the Rust question,
the one I said a short chunk might pull in, moved from 0.8588 to 0.8550, which
is the direction I predicted and far too small to matter. The Busch, P/NC and
food questions retrieved the same text at the same distances. Where a
label changed, like the housing guide's #19 becoming #21 in the Busch top
five, I checked that the text is identical. The housing guide is a list post,
so splitting its earlier tips renumbered everything after them.

One thing in the transcript looks like progress and isn't. The per-question
table at the top of each run log has the P/NC question passing once before and
twice after. Its retrieval is identical in both runs. That column is `judge`,
which only checks whether the answer contains "P/NC", so it moves with how the
model happens to phrase a correct answer. I'm not counting it for the fix.

I'm keeping the change. It costs nothing any criterion measures, and a list
tip as its own chunk is the right shape for the 10 threads where the merge was
gluing tips together, whether or not my five questions needed it.

## What's Still Broken

**Revised criterion 1 and criterion 4, still 3 of 5.** Both miss on the bus
and WebReg questions, and after the fix both misses are purely loading. The
corpus has no sentence that says which bus goes to Livingston and no sentence
that tells a student to ask for an SPN.

Going back to the harvester to see why, the cause is in
`tools/harvest_rutgers.py`. Each topic is one search sorted `top` of all time,
and `_pick_posts` keeps the most-commented results first. That picks the most
argued-over threads, whatever they're about. Three of the four threads filed
under `buses` aren't about buses at all: they're about the Targum censoring
coverage of the Hong Kong protests, a student accused of cheating, and vaccine
information from a bio professor. The registration search used nearly my
WebReg question's own words and came back with a post of registration dates,
the scheduling-app launch post, and an argument about the PIRG fee. None of
the three is about getting into a closed section.

What I'd do is fix the harvester, not the index. Sort by relevance instead of
comment count, drop a thread whose title and body never use the topic's words,
and take more threads per topic so a thin one like registration isn't three
posts. I stopped short of it for two reasons. It changes the corpus, which
changes every number above, so it would be a new baseline and not an after.
And I know my five questions now. If I pick threads while knowing them, I'm
writing the answers into the corpus. Doing it properly means writing a fresh
set of test questions before the new harvest and measuring against those.

**The bus answer cites documents for saying nothing.** This is the problem I
flagged under Verdicts, and the fix made it more visible, not less. All six
bus answers, before and after, say the documents never mention the route and
then list the files they came from. After the fix the model is citing a thread
whose top chunk is literally about the LX, in an answer saying the LX isn't
mentioned. `GROUNDING_INSTRUCTION` in `generate.py` does have a rule for this
case, "If the documents don't cover the question, say you don't have enough
information", and the model followed it. The rule right after it, "Name the
document your answer came from", has no exception, so the model names files
anyway. What I'd change is that second rule: name a document only when the
answer came from one, so a "they don't cover it" answer reads like the gate's
refusal.
I didn't, because the brief allowed one change and I'd already spent it, and
because criterion 2 would then have to decide whether that counts as an
answer, which is the same argument I had with myself about the gate's refusal.

**The gate lets through Rutgers questions it can't answer.** Criterion 3 is
met and I don't think it means much. `tools/gate_probe.py` asks five questions
a student here would actually ask that my threads don't cover, and all five
get under 0.6 on both indexes. The nearest chunk answers none of them:

```
Which Rutgers gym has a swimming pool?
  default  0.4779 passes  cs_little_rutgers_things_i_wish_i_knew_earlier.txt#17
           "--- reply 2 (10 votes) --- If you order from Amazon and don't want to deal with the campus mail system (anything scheduled for delivery on a weekend u"
  lists    0.3840 passes  cs_little_rutgers_things_i_wish_i_knew_earlier.txt#15
           "- There are bike repair and air pump stations on every campus, near the Busch Campus Center, Livi Plaza bus stop, Douglass Campus Center, and Au Bon P"
```

That one is also a cost of my fix. On the old index the gym question's nearest
chunk was 0.4779 away, and on the new one a one-line tip about bike pumps is
0.3840. A short tip under a short title sits close to a lot of short questions.
The lost-ID question moved the same way, from 0.5334 to 0.5181. The full
output is `results/gate_probe.txt`.

A single cutoff on distance can't fix this. After the fix, the four test
questions the gate lets through have best chunks from 0.2157 to 0.4448, and
everything it refused was 0.7443 or further. Three of the five near misses
land inside that range, and the other two sit just above it at 0.5181 and
0.5245. The bike-pump tip, at 0.3840, is closer to the gym question than the
chunks that really do answer the P/NC question (0.4037) and the Busch question
(0.4377) are to theirs. No cutoff lets those two through and stops the gym
question. The next thing I'd try is a check on whether the best chunk actually
answers, like a reranker that scores each question and chunk as a pair, or
asking the model yes or no before it writes anything. I didn't run these five
through the model, so I don't know yet whether the grounding rule catches them
the way it caught the bus question. That's the first thing I'd measure. I
stopped here because criterion 3 as I wrote it can't see the problem, so I'd
have had no criterion to show a fix working against.

**The fix made 43 more chunks under the floor.** 47 now instead of 4. The
smallest, at 64 characters, is a list item that is only a link,
`- https://climateclock.world`, under its thread title. It was never retrieved
in either run, so nothing measured it, but it's a chunk with nothing in it. A
list item that is only a URL should fold into its neighbour like any other
fragment. I left it because it's one chunk out of 910 and fixing it would have
been a second change to `chunker.py`.

## What I'd Do Differently

**Criterion 1: I'd write the answer down, not the topic.** The `expects`
phrases in `questions.py` were meant to stand for "the answer", and on two of
five questions they don't. "P/NC" is what question 2 is about, so every chunk
about Pass/No Credit contains it, whether or not it says anything worth
knowing. My own chunker makes that worse. It puts the thread title on every
chunk, and one thread is titled "A message about P/NC from a faculty member",
so 6 of that thread's 11 chunks have the phrase only in the title. And `judge`
uses the same phrase to grade the answer, so correct
answers fail it. In the before run, P/NC runs 1 and 2 both gave the FAQ's
real advice, which is to see an advisor if the class needs a B, and both
failed because neither one wrote "P/NC". For the WebReg question "SPN" is
one real answer out of at least two, and the corpus's other one, seat alerts
for closed sections, could never count. So I'd write criterion 1 the way I
revised it, as a reading of whether the chunk answers, from the start, and
for each question I'd write down every answer I'd accept instead of one
phrase.

**Criterion 4: I'd point it at the way my chunker actually fails.** I wrote
it to catch chunks cut too small, an answer split from its follow-up at a
reply marker. None of my five questions has an answer that runs across two
replies, so criterion 4 could only fail where criterion 1 already had. Once I
revised criterion 1 to ask for one chunk that answers, the two became the same
test, scored by the same function, so matching on all six runs tells me
nothing. The failure I found was the opposite direction, chunks glued too big. I'd
either add a question built for the split case, one whose answer is a reply
plus the reply correcting it, or spend criterion 4 on chunk purity: the chunk
holding the answer should be mostly about the answer. That version would have
flagged the bus chunk before any eval, since 307 of its 536 characters under
the title were about printing.

**Criterion 3: I'd ask it questions that could actually get through.** I
picked five out-of-scope questions from other worlds, set 4 of 5 so the Rust
one had room to slip past, and all five cleared the cutoff by at least 0.178.
That measured whether the gate can tell Rutgers from Mongolia, which was never
in doubt. The question that matters is whether it can tell a Rutgers question
my threads answer from one they don't. The five near misses in
`results/gate_probe.txt` would have made criterion 3 fail on the first run,
which is what it should have done.

**Criterion 5: I'd give the model a reason to make a filename up.** It held
on every answer because the model repeated filenames it had just been handed,
and three of the fifteen answers were refusals that passed without naming
anything. The reason I gave for this criterion in unit 1 was that my filenames
read like the words of a question, so a model could invent one. None of my
questions tried that. I'd add one that invites it, like asking whether there's
a thread about where commuters park on College Ave. No thread has that title,
and one about Rutgers exploiting its commuters with parking rules shares most
of its words, so the model has both a real file to stretch and a fake one to
invent. And I'd score criterion 5 only over answers that name at least one
file.

**Criterion 2 I'd keep, with the refusal rule written in.** Whether the
gate's refusal counts as an answer was the one call I had to argue in the
verdict. It should have been settled in the criterion, in unit 1, before I
knew the WebReg question would be the one refused.

## How I Used AI (unit 2)

I leaned on Claude Code harder in unit 2 than in unit 1. It wrote `scorer.py`
and its tests, the changes to `run_eval.py`, `tools/answer_rank.py` and
`tools/gate_probe.py`, and the change to `_merge_small` with its tests. It ran
both evals, and it drafted the unit 2 sections of this README from the results.
Two things were set up so the order of events can be checked rather than
taken on trust: the scorer was committed before the before run (`e7bd157`),
and the prediction was committed before the new index was built (`8483747`).

The moments worth writing down are the same kind as unit 1. Each time
something was wrong, it read fine, and a measurement is what caught it.

**1. A count in the diagnosis was too high, and it was already pushed.** The
first count of chunks where the merge glued list items together was 30 across
12 threads. It worked by splitting finished chunks on blank lines, which also
counted three single replies that contain their own bulleted list. That's one
person's list, and the merge had nothing to do with it. Writing the
whole-corpus test forced the question of which pieces the merge actually
joined, and tracking that gives 27 across 10. The wrong number had gone out in
`147d3c4`. The correction is `03d83b1`, and its message says why.

**2. A test for the fix passed before the fix existed.** The first version of
the test that a list item never joins a chunk already holding one passed on
the old code. The intro plus the first tip was already 393 characters, over
the floor, so the old rule wouldn't have merged the next tip either. A test
that passes without the fix says nothing about the fix. Running the tests red
before writing the code is what showed it, and the test now uses pieces whose
lengths make the old rule merge.

**3. The first draft described chunks from memory.** The first draft of "Did
it help?" said the before run's list-post chunk was a tip about which bus to
take at night. It was four tips glued together, and none of them was about
night buses. After that, every description of a chunk in this write-up was
checked against the text in the results JSON, and every line of every pasted
block was checked against the files in `results/`. The blocks are excerpts,
so lines between the ones shown are left out, but none of them was retyped.

**4. A prediction was wrong, and it stays in.** I predicted the model might
start saying "LX" once it could see the LX sentence. It never did. Committing
the prediction first only means something if it's allowed to be wrong, so it's
still there under The Improvement, as written.

Checking these the same way also turned up a mistake from unit 1. I wrote that
the SPN chunk was further away than four of my five out-of-scope questions,
and it's two. That's corrected under Diagnoses, with unit 1 left as it was.
