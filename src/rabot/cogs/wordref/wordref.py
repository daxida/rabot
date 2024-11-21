import re
from typing import Any

import requests
from bs4 import BeautifulSoup
from discord import Embed

from rabot.cogs.wordref.entry import Entry
from rabot.log import logger
from rabot.utils import is_english

# https://www.wordreference.com/english/abbreviationsWRD.aspx?dict=engr&abbr=κύρ&src=WR
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


def parse_words(text: str) -> list[str]:
    """Remove attributes to extract a clean list of words.

    Wordref groups words together with their attributes.
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

    BASE_URL = "https://www.wordreference.com"

    def __init__(
        self,
        word: str | None,
        gr_en: bool,
        hide_words: bool,
        min_sentences_shown: int,
        max_sentences_shown: int,
    ) -> None:
        if word is None:
            self.word = None
            self.is_random = True
            extension = "random/gren"
        else:
            self.word = word.strip()
            self.is_random = False
            direction = "engr" if is_english(word) else "gren"
            extension = f"{direction}/{word}"

        self.url = f"{Wordref.BASE_URL}/{extension}"

        self.gr_en = gr_en
        self.hide_words = hide_words
        self.min_sentences_shown = min_sentences_shown
        self.max_sentences_shown = max_sentences_shown

        self.max_random_iterations = 5

    def fetch_embed(self) -> Embed | None:
        """Fetch an embed.

        If self.is_random is True, retry a set amount of times.
        """
        if not self.is_random:
            return self.try_fetch_embed()

        for _ in range(self.max_random_iterations):
            if (embed := self.try_fetch_embed()) is not None:
                return embed

        return None

    def try_fetch_embed(self) -> Embed | None:
        """Try to fetch an embed.

        May fail (return None) if either:
        - The entry is not valid (based on our own set of conditions).
        - The embed is not valid (based on length conditions).
        """
        entry = self.try_fetch_entry()

        if not entry.is_valid_entry:
            return None

        logger.success(f"Valid entry for '{self.word}'.")
        entry.add_embed()

        if not entry.is_valid_embed:
            return None

        logger.success(f"Valid embed for '{self.word}'.")
        return entry.embed

    def try_fetch_entry(self) -> Entry:
        logger.debug(f"GET {self.url}")
        response = requests.get(self.url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        self.word = self.fetch_accented_word(soup)

        new_url = f"{Wordref.BASE_URL}/gren/{self.word}"  # Forced "gren"
        logger.debug(f"URL {new_url}")

        entry = Entry(
            new_url,
            self.word,
            self.gr_en,
            self.hide_words,
            self.min_sentences_shown,
            self.max_sentences_shown,
            self.is_random,
        )

        logger.debug(f"Trying to fetch info for '{self.word}'")
        for res in soup.find_all("table", {"class": "WRD"}):
            self.try_fetch_word(res, entry)
            self.try_fetch_sentence_pairs(res, entry)

        return entry

    def fetch_accented_word(self, soup: BeautifulSoup) -> str:
        """Fetch the accented word in case of non-accented input.

        Relies on wordref.com doing the dirty job of figuring it out for us."""
        try:
            wrd = soup.find("table", {"class": "WRD"})
            fr_wrd = wrd.find("tr", {"class": "even"}).find("td", {"class": "FrWrd"})  # type: ignore
            return fr_wrd.strong.text.split()[0]  # type: ignore
        except Exception as e:
            raise e

    def try_fetch_word(self, res: Any, entry: Entry) -> None:
        # TODO: Make this return a dict instead of mutating entry.
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
                    gr_pos = gr_text.replace(entry.gr_word, "").strip()
                    entry.gr_pos = "" if "," in gr_pos else gr_pos

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
                sentences = set(entry.sentences)

                for stored_pair in sentences:
                    stored_greek, stored_english = stored_pair
                    if self.gr_en:
                        if stored_english == en_sentence:
                            stored_already = True
                            # Our stored answer is already fine
                            if self.word and self.word in stored_greek:
                                break
                            sentences.remove((stored_greek, stored_english))
                            sentences.add((gr_sentence, en_sentence))
                            break
                    # We want our english sentences containing "word"
                    elif stored_greek == gr_sentence:
                        stored_already = True
                        # Our stored answer is already fine
                        if self.word and self.word in stored_english:
                            break
                        sentences.remove((stored_greek, stored_english))
                        sentences.add((gr_sentence, en_sentence))
                        break
                if not stored_already:
                    sentences.add((gr_sentence, en_sentence))

                entry.sentences.extend(list(sentences))


def main() -> None:
    """For testing only."""
    wr = Wordref(
        word=None,
        gr_en=True,
        hide_words=False,
        min_sentences_shown=1,
        max_sentences_shown=3,
    )
    entry = wr.try_fetch_entry()
    print(entry)


if __name__ == "__main__":
    main()
