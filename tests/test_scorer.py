"""
Tests for scorer.py. Run with:  python -m unittest discover tests

Every string in here is real: the answer is the unit 1 sample answer from the
README, and the chunk texts are sentences copied out of corpora/rutgers. The
fabricated filename is the example criteria.md uses for criterion 5.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scorer  # noqa: E402

REFUSAL = "I don't have enough information about that."

SAMPLE_ANSWER = (
    "According to `campus_why_no_24_hour_library.txt`, you can go to ARC and "
    "SERC on Busch since both are open 24 hours. One student suggests using an "
    "open classroom or going to the second floor of SERC, specifically pointing "
    "out a quiet spot at the end of the TA office hallway near the stairwell."
)

SERC_CHUNK = {
    "label": "campus_why_no_24_hour_library.txt#2",
    "source": "campus_why_no_24_hour_library.txt",
    "distance": 0.4377,
    "text": (
        "THREAD: why no 24 hour library\n\n--- reply 3 (29 votes) ---\n"
        "If you’re on Busch, ARC and SERC are both open 24 hours, so you should "
        "be able to find an open classroom."
    ),
}

LX_CHUNK = {
    "label": "cs_little_rutgers_things_i_wish_i_knew_earlier.txt#1",
    "source": "cs_little_rutgers_things_i_wish_i_knew_earlier.txt",
    "distance": 0.6107,
    "text": (
        "THREAD: Little Rutgers things I wish I knew earlier.\n\n- F and EE buses "
        "go around College Ave from SAC --> Student Center --> Scott Hall. LX, H, "
        "and A buses go around College Ave from Student Center --> Scott Hall --> SAC."
    ),
}

BUS_CHUNK = {
    "label": "commuting_new_bus_route_just_dropped.txt#0",
    "source": "commuting_new_bus_route_just_dropped.txt",
    "distance": 0.4533,
    "text": "THREAD: new bus route just dropped!!!\n\nBasically replaced plaza with JMA",
}


class ContainsExpected(unittest.TestCase):
    def test_plural_still_counts(self):
        self.assertTrue(scorer.contains_expected("and SPNs were given for that class", "SPN"))

    def test_phrase_inside_a_longer_word_does_not(self):
        self.assertFalse(scorer.contains_expected("the ALX line", "LX"))

    def test_case_does_not_matter(self):
        self.assertTrue(scorer.contains_expected("krispy pizza is mid", "Krispy Pizza"))

    def test_slash_phrase(self):
        self.assertTrue(scorer.contains_expected("if you P/NC every single class", "P/NC"))


class Judge(unittest.TestCase):
    def test_sample_answer_is_right(self):
        self.assertTrue(scorer.judge("q", "SERC", SAMPLE_ANSWER, [SERC_CHUNK]))

    def test_refusal_is_never_right(self):
        self.assertFalse(scorer.judge("q", "SPN", REFUSAL, []))


class NamedFiles(unittest.TestCase):
    def test_backticked_filename_is_found(self):
        self.assertEqual(
            scorer.named_files(SAMPLE_ANSWER), ["campus_why_no_24_hour_library.txt"]
        )

    def test_no_filename(self):
        self.assertEqual(scorer.named_files("Students say the LX."), [])


class Criterion2NamesASource(unittest.TestCase):
    def test_refusal_is_not_an_answer_to_score(self):
        self.assertIsNone(scorer.names_a_source(REFUSAL, [SERC_CHUNK], gate_passed=False))

    def test_filename_counts(self):
        self.assertTrue(scorer.names_a_source(SAMPLE_ANSWER, [SERC_CHUNK], gate_passed=True))

    def test_retrieved_name_without_extension_counts(self):
        answer = "In campus_why_no_24_hour_library, a student says SERC."
        self.assertTrue(scorer.names_a_source(answer, [SERC_CHUNK], gate_passed=True))

    def test_answer_naming_nothing_fails(self):
        answer = "Students say ARC and SERC are open all night."
        self.assertFalse(scorer.names_a_source(answer, [SERC_CHUNK], gate_passed=True))


class Criterion5CitationsWereRetrieved(unittest.TestCase):
    def test_real_citation(self):
        self.assertTrue(scorer.citations_were_retrieved(SAMPLE_ANSWER, [SERC_CHUNK]))

    def test_invented_citation_fails(self):
        answer = "See parking_where_do_commuters_park_on_college_ave.txt for this."
        self.assertFalse(scorer.citations_were_retrieved(answer, [SERC_CHUNK]))

    def test_one_real_one_invented_still_fails(self):
        answer = SAMPLE_ANSWER + " Also parking_where_do_commuters_park_on_college_ave.txt."
        self.assertFalse(scorer.citations_were_retrieved(answer, [SERC_CHUNK]))

    def test_refusal_names_nothing_so_nothing_is_invented(self):
        self.assertTrue(scorer.citations_were_retrieved(REFUSAL, [SERC_CHUNK]))


class Criterion1And4(unittest.TestCase):
    def test_c1_phrase_in_any_retrieved_chunk(self):
        self.assertTrue(scorer.retrieved_has_answer("SERC", [BUS_CHUNK, SERC_CHUNK]))
        self.assertFalse(scorer.retrieved_has_answer("LX", [BUS_CHUNK]))

    def test_revised_c1_needs_a_reading_not_just_the_phrase(self):
        self.assertTrue(scorer.retrieved_answers("SERC", [BUS_CHUNK, SERC_CHUNK]))
        self.assertFalse(scorer.retrieved_answers("LX", [BUS_CHUNK, LX_CHUNK]))

    def test_c4_hand_checked_yes(self):
        ok, unjudged = scorer.one_chunk_answers("SERC", [SERC_CHUNK])
        self.assertTrue(ok)
        self.assertEqual(unjudged, [])

    def test_c4_phrase_present_but_judged_no(self):
        # C1 passes on this chunk and C4 must not: LX is named, Livingston never is.
        self.assertTrue(scorer.retrieved_has_answer("LX", [LX_CHUNK]))
        ok, unjudged = scorer.one_chunk_answers("LX", [LX_CHUNK])
        self.assertFalse(ok)
        self.assertEqual(unjudged, [])

    def test_c4_unjudged_chunk_fails_closed_and_is_reported(self):
        chunk = dict(SERC_CHUNK, source="some_other_thread.txt", label="some_other_thread.txt#0")
        ok, unjudged = scorer.one_chunk_answers("SERC", [chunk])
        self.assertFalse(ok)
        self.assertEqual(unjudged, ["some_other_thread.txt#0"])


class Table(unittest.TestCase):
    def run_data(self):
        def entry(answer, passed, retrieved):
            return {"answer": answer, "gate_passed": passed, "retrieved": retrieved}

        return {
            "questions": [
                {"expects": "SERC", "runs": [entry(SAMPLE_ANSWER, True, [SERC_CHUNK])] * 3},
                {"expects": "LX", "runs": [entry("Take the bus.", True, [BUS_CHUNK])] * 3},
                {"expects": "SPN", "runs": [entry(REFUSAL, False, [BUS_CHUNK])] * 3},
            ],
            "out_of_scope": [{"refused": True}, {"refused": True}, {"refused": False}],
        }

    def test_counts_per_criterion(self):
        rows = {row[0][:2]: row[2] for row in scorer.criteria_rows(self.run_data())}
        self.assertEqual(rows["1."], ["1/3"] * 3)
        self.assertEqual(rows["1r"], ["1/3"] * 3)
        self.assertEqual(rows["2."], ["1/2"] * 3)      # the refusal is not scored
        self.assertEqual(rows["3."], ["2/3"] * 3)
        self.assertEqual(rows["4."], ["1/3"] * 3)
        self.assertEqual(rows["5."], ["3/3"] * 3)


if __name__ == "__main__":
    unittest.main()
