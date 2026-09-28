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

I wrote `scorer.py` and committed it before this run existed (`e7bd157`), so the
rule for what counts as a pass was fixed before there were results for it to
fit.

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1. Retrieved chunks contain the answer | 4 of 5 | 3/5 | 3/5 | 3/5 |  |
| 2. Every answer names a source | every answer produced | 4/4 | 4/4 | 4/4 |  |
| 3. Gate stops out-of-corpus questions | 4 of 5 | 5/5 | 5/5 | 5/5 |  |
| 4. The answer fits inside one chunk | 4 of 5 | 3/5 | 3/5 | 3/5 |  |
| 5. Every source named was actually retrieved | 5 of 5 | 5/5 | 5/5 | 5/5 |  |

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
