"""
Tests for the merge pass in chunker.py. Run with:  python -m unittest discover tests

Every piece is real, copied out of the thread the bus question missed on,
cs_little_rutgers_things_i_wish_i_knew_earlier.txt, exactly as
_header_and_segments cuts it.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import chunker  # noqa: E402
from ingest import load_documents  # noqa: E402

FLOOR, CAP = 200, 746   # 746 is what that thread's title leaves of the 800 cap

INTRO = "(maybe I was just silly as a first-year for not knowing all this...)"
RU_EXPRESS = (
    "- You can put money on RU Express and pay guest price to eat at dining halls. "
    "You can also pay by cash or credit card, but it's way easier to pay with RU "
    "Express. It's 8.50 for breakfast, 11.50 for lunch, and 17.50 for dinner. For "
    "many meal plans, it's actually cheaper to pay guest entry for each meal than "
    "to have a plan."
)
BUS = (
    "- F and EE buses go around College Ave from SAC --> Student Center --> Scott "
    "Hall. LX, H, and A buses go around College Ave from Student Center --> Scott "
    "Hall --> SAC. You can take a bus from Scott Hall to SAC and vice versa."
)
PRINT_DRIVER = (
    "- You can print to any Rutgers printer from your laptop by downloading the RU "
    "Wireless print driver (google it)."
)
PRINT_RELEASE = (
    "- On print release stations, you can select multiple jobs for printing at the "
    "same time. Select the first job and drag down at an angle; the rest of your "
    "jobs will also be selected. It's magical."
)
BUS_DRIVERS = "- Bus drivers are super cool and you should talk to them."
EDIT = "EDIT: Thanks for all the corrections! I'm editing them into the document."
REPLY_6 = (
    "--- reply 6 (5 votes) ---\nYou can use the grilled chicken in the dining hall "
    "for the cook to order pasta meals."
)
REPLY_7 = (
    "--- reply 7 (4 votes) ---\nSomeone died in it though...Last I heard Cabaret "
    "Theatre was using it for storage..."
)


def merge(*pieces):
    return chunker._merge_small(list(pieces), FLOOR, CAP)


class RealPieces(unittest.TestCase):
    def test_pieces_are_the_lengths_the_diagnosis_quotes(self):
        self.assertEqual(
            [len(p) for p in (INTRO, RU_EXPRESS, BUS, PRINT_DRIVER, PRINT_RELEASE)],
            [68, 323, 225, 112, 195],
        )


class ListItemsStayApart(unittest.TestCase):
    def test_bus_tip_is_not_glued_to_the_printer_tips(self):
        self.assertEqual(
            merge(BUS, PRINT_DRIVER, PRINT_RELEASE), [BUS, PRINT_DRIVER, PRINT_RELEASE]
        )

    def test_an_item_never_joins_a_chunk_already_holding_one(self):
        # Real pieces, not in thread order: intro plus the printer-driver tip is
        # 182 characters, under the floor, so the old rule would have taken the
        # print-release tip as well. The intro takes one tip and then it's closed.
        self.assertEqual(
            merge(INTRO, PRINT_DRIVER, PRINT_RELEASE),
            [f"{INTRO}\n\n{PRINT_DRIVER}", PRINT_RELEASE],
        )


class OtherMergesUnchanged(unittest.TestCase):
    def test_short_intro_still_takes_the_first_item(self):
        self.assertEqual(merge(INTRO, RU_EXPRESS), [f"{INTRO}\n\n{RU_EXPRESS}"])

    def test_plain_paragraph_still_folds_into_an_item(self):
        self.assertEqual(merge(BUS_DRIVERS, EDIT), [f"{BUS_DRIVERS}\n\n{EDIT}"])

    def test_two_short_replies_still_merge(self):
        self.assertEqual(merge(REPLY_6, REPLY_7), [f"{REPLY_6}\n\n{REPLY_7}"])

    def test_cap_still_wins(self):
        self.assertEqual(merge(RU_EXPRESS, "x" * 450), [RU_EXPRESS, "x" * 450])


def merge_groups(pieces, merged):
    """Which input pieces went into each merged chunk, in order.

    A reply can hold its own bulleted list, and that is one person's list, not
    something the merge did. So this walks the pieces the merge was given
    rather than splitting finished chunks on blank lines.
    """
    remaining = iter(pieces)
    groups = []
    for text in merged:
        group = [next(remaining)]
        while "\n\n".join(group) != text:
            group.append(next(remaining))
        groups.append(group)
    return groups


class WholeCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = load_documents(config.CORPUS)
        cls.chunks = chunker.split_documents(cls.documents)

    def test_bus_tip_gets_a_chunk_of_its_own(self):
        header = "THREAD: Little Rutgers things I wish I knew earlier."
        own = [c.label for c in self.chunks if c.text == f"{header}\n\n{BUS}"]
        self.assertEqual(own, ["cs_little_rutgers_things_i_wish_i_knew_earlier.txt#1"])

    def test_no_chunk_holds_two_list_items_the_merge_joined(self):
        glued = []
        for doc in self.documents:
            header, segments = chunker._header_and_segments(doc.text)
            budget = max(config.CHUNK_MIN, config.CHUNK_SIZE - len(header) - 2)
            pieces = []
            for segment in segments:
                pieces += chunker._split_long(segment, budget, config.CHUNK_OVERLAP)
            merged = chunker._merge_small(pieces, config.CHUNK_MIN, budget)
            for index, group in enumerate(merge_groups(pieces, merged)):
                if sum(chunker.LIST_ITEM.match(p) is not None for p in group) >= 2:
                    glued.append(f"{doc.source}#{index}")
        self.assertEqual(glued, [])

    def test_every_chunk_still_fits_the_cap(self):
        self.assertLessEqual(max(len(c.text) for c in self.chunks), config.CHUNK_SIZE)


if __name__ == "__main__":
    unittest.main()
