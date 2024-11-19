import re
from typing import Any, List

import requests
from bs4 import BeautifulSoup
from discord import Embed

from rabot.utils import is_english
from rabot.wordref.entry import Entry

ATTRIBUTES_EL = {
    "επίθ": "adj",
    "επίθ άκλ": "TODO",
    "φρ ως": "TODO",  # φράση ως ... πχ. ουσ θηλ
    "ουσ ουδ": "neut. n.",
    "ουσ αρσ": "masc. n.",
    "ουσ θηλ": "fem. n.",
    "ρ έκφρ": "TODO",
    "ρ αμ + επίρ": "TODO",
    "ρ αμ": "TODO",
    "ρ μ + πρόθ": "TODO",
    "ρ μ": "TODO",
    "έκφρ": "TODO",
    "περίφρ": "TODO",
}
ATTRIBUTES_EN = {
    "adj",
    "adv",
    " n",
    "v expr",
    "vi",
    "vtr phrasal sep",
    "vtr + prep",
    "vtr",
}
TAG = "\033[33mWORDREF:\033[0m"
OK = "\033[32m[OK]\033[0m"


def parse_words(text: str) -> List[str]:
    """Wordref groups the words together with their attributes.
    This extracts the word by deleting the attributes from a set list.
    """
    attributes = ATTRIBUTES_EN if is_english(text) else ATTRIBUTES_EL

    while True:
        original_text = text
        text = text.strip()
        for att in attributes:
            pattern = re.escape(att) + r"$"
            text = re.sub(pattern, "", text)
            text = re.sub(r"\+$", "", text)
        if original_text == text:
            break

    return text.split(", ")


class Wordref:
    """Deals with the scraping of Wordref.

    Everything is stored in an Entry class, where the suitability logic and formatting is done.
    """

    wordref_url = "https://www.wordreference.com"

    def __init__(
        self,
        word: str | None,
        gr_en: bool,
        hide_words: bool,
        min_sentences_shown: int,
        max_sentences_shown: int,
    ) -> None:
        # NOTE: The discord API already strips the given "word".
        self.word = word
        self.is_random = word is None

        if self.is_random:
            extension = "random/gren"
        elif is_english(self.word):
            extension = f"engr/{self.word}"
        else:
            extension = f"gren/{self.word}"

        self.url = f"{Wordref.wordref_url}/{extension}"

        self.gr_en = gr_en
        self.hide_words = hide_words
        self.min_sentences_shown = min_sentences_shown
        self.max_sentences_shown = max_sentences_shown

        self.max_random_iterations = 5

    def fetch_embed(self) -> Embed | None:
        if not self.is_random:
            embed = self.try_fetch_embed()
        else:
            embed = None
            for _ in range(self.max_random_iterations):
                embed = self.try_fetch_embed()
                if embed is not None:
                    break

        return embed

    def try_fetch_embed(self) -> Embed | None:
        entry = self.try_fetch_entry()

        if not entry.is_valid_entry:
            return None

        print(f"{TAG} {OK} found a valid entry for {self.word=}.")
        entry.add_embed()

        if not entry.is_valid_embed:
            return None

        print(f"{TAG} {OK} found a valid embed for {self.word=}.")
        return entry.embed

    def try_fetch_entry(self) -> Entry:
        response = requests.get(self.url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Account for the query word being written without accents by scraping the accented word.
        try:
            self.word = (
                soup.find("table", {"class": "WRD"})
                .find("tr", {"class": "even"})
                .find("td", {"class": "FrWrd"})
                .strong.text.split()[0]
            )
        except Exception:
            pass

        link = f"{Wordref.wordref_url}/gren/{self.word}"  # Forced "gren"

        entry = Entry(
            link,
            self.word,
            self.gr_en,
            self.hide_words,
            self.min_sentences_shown,
            self.max_sentences_shown,
            self.is_random,
        )

        print(f"{TAG} requesting {self.url}")
        print(f"{TAG} trying to fetch '{self.word=}' ({link})")
        # print(f"{TAG}\n{entry}")

        for res in soup.find_all("table", {"class": "WRD"}):
            self.try_fetch_word(res, entry)
            self.try_fetch_sentence_pairs(res, entry)

        return entry

    def try_fetch_word(self, res: Any, entry: Entry) -> None:
        for item in res.find_all("tr", {"class": ["even", "odd"]}):
            fr_wrd = item.find("td", {"class": "FrWrd"})
            to_wrd = item.find("td", {"class": "ToWrd"})

            if not fr_wrd or not to_wrd:
                continue

            en_text = to_wrd.text
            gr_text = fr_wrd.text

            if is_english(fr_wrd.text):
                en_text, gr_text = gr_text, en_text

            if not entry.en_word:
                entry.en_word = en_text.strip()

            # Parts of speech
            if (entry.gr_pos is None) and entry.gr_word:
                if len(gr_text.split()) > 1 and entry.gr_word in gr_text:
                    entry.gr_pos = gr_text.replace(entry.gr_word, "").strip()
                    if "," in entry.gr_pos:
                        entry.gr_pos = ""

            # Synonyms
            for word in parse_words(gr_text):
                entry.gr_synonyms.add(word)
            for word in parse_words(en_text):
                entry.en_synonyms.add(word)

    def try_fetch_sentence_pairs(self, res: Any, entry: Entry) -> None:
        """Options:
        - (1) Stores every pair (even when there are
             two translations to a sentence)
        Ex.
        (EN) The supposed masterpiece discovered in the old house was a fake.
        (T1) Το υποτιθέμενο έργο τέχνης που βρέθηκε στο παλιό σπίτι ήταν πλαστό.
        (T2) Το δήθεν έργο τέχνης που βρέθηκε στο παλιό σπίτι ήταν πλαστό.

        - (2) Store only one pair giving priority to containing the original word.
        """
        gr_sentence = ""
        en_sentence = ""
        for item in res.find_all("tr", {"class": ["even", "odd"]}):
            fr_ex = item.find("td", {"class": "FrEx"})
            to_ex = item.find("td", {"class": "ToEx"})

            # Resets buffered sentences
            if not fr_ex and not to_ex:
                en_sentence = ""
                gr_sentence = ""

            # Buffers sentences to then group them in pairs
            if fr_ex:
                en_sentence = fr_ex.text
            if to_ex:
                gr_sentence = to_ex.text
                # Delete "Translation not found" message
                if "Αυτή η πρόταση δεν είναι μετάφραση της αγγλικής πρότασης." in gr_sentence:
                    gr_sentence = ""

            # Groups them in pairs
            if gr_sentence and en_sentence:
                # Option 1
                # entry.sentences.add((gr_sentence, en_sentence))

                # Option 2
                stored_already = False
                for stored_pair in entry.sentences:
                    stored_greek, stored_english = stored_pair
                    if self.gr_en is True:
                        if stored_english == en_sentence:
                            stored_already = True
                            # Our stored answer is already fine
                            if self.word and self.word in stored_greek:
                                break
                            entry.sentences.remove((stored_greek, stored_english))
                            entry.sentences.add((gr_sentence, en_sentence))
                            break
                    # We want our english sentences containing "word"
                    elif stored_greek == gr_sentence:
                        stored_already = True
                        # Our stored answer is already fine
                        if self.word and self.word in stored_english:
                            break
                        entry.sentences.remove((stored_greek, stored_english))
                        entry.sentences.add((gr_sentence, en_sentence))
                        break
                if not stored_already:
                    entry.sentences.add((gr_sentence, en_sentence))
