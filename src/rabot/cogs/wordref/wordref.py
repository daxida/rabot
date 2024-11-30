import re
from typing import Any

import requests
from bs4 import BeautifulSoup
from discord import Embed

from rabot.cogs.wordref.entry import DictEntry, DictEntryItem, fmt_dict_entry
from rabot.exceptions import RabotError
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
    "επίρ": "adverb",
}
ATTRIBUTES_EN = {
    "adj",
    "adv",
    "n",
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

    words = [w for w in text.split(", ") if w]

    return words


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

    def get_soup(self) -> BeautifulSoup:
        logger.debug(f"GET {self.url}")
        response = requests.get(self.url)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

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
        """
        entry = self.try_fetch_entry()

        if not entry.is_valid_entry:
            return None

        logger.success(f"Valid entry for '{self.word}'.")
        embed = fmt_dict_entry(
            entry,
            hide_words=self.hide_words,
            max_sentences_shown=self.max_sentences_shown,
        )

        return embed

    def try_fetch_entry(self) -> DictEntry:
        soup = self.get_soup()
        if self.gr_en or self.is_random:
            self.word = self.fetch_accented_word(soup)
        if self.word is None:
            raise RabotError("Not initialized word in Wordref")

        new_url = f"{Wordref.BASE_URL}/gren/{self.word}"  # Forced "gren"
        logger.debug(f"URL {new_url}")

        all_wr_entries = []
        for res in soup.find_all("table", {"class": "WRD"}):
            wr_entries = self.fetch_wordref_entries(res)
            # If opposite order, invert fr <=> to
            if self.gr_en ^ (res["data-dict"] == "gren"):
                for e in wr_entries:
                    e.invert()
            all_wr_entries.extend(wr_entries)

        all_wr_entries = [wre for wre in all_wr_entries if wre.fr_exs and wre.to_exs]

        entry = DictEntry(
            self.word,
            self.gr_en,
            new_url,
            all_wr_entries,
        )

        return entry

    def fetch_accented_word(self, soup: BeautifulSoup) -> str:
        """Fetch the accented word in case of non-accented input.

        Relies on wordref.com doing the dirty job of figuring it out for us.
        """
        try:
            wrd = soup.find("table", {"class": "WRD"})
            fr_wrd = wrd.find("tr", {"class": "even"}).find("td", {"class": "FrWrd"})  # type: ignore
            return fr_wrd.strong.text.split()[0].strip(",")  # type: ignore
        except Exception as e:
            logger.warning(f"Could not find the accented version of {self.word}")
            if self.word is None:
                raise RabotError from e
            return self.word

    def fetch_wordref_entries(self, res: Any) -> list[DictEntryItem]:
        """
        -------------------------------------------
        Entry 1:
        | Row 1   | tr class="odd"                |
        | Row 2   | tr class="odd"                |
        Entry 2:
        -------------------------------------------
        | Row 3   | tr class="even"               |
        Entry 3:
        -------------------------------------------
        | Row 4   | tr class="odd"                |
        | Row 5   | tr class="odd"                |
        | Row 6   | tr class="odd"                |
        Entry 4:
        -------------------------------------------
        | Row 7   | tr class="even"               |
        | Row 8   | tr class="even"               |
        -------------------------------------------
        etc.
        """
        groups = []
        cur_group = None
        cur_class = None

        for row in res.find_all("tr", {"class": ["odd", "even"]}):
            row_class = row["class"][0]
            if row_class != cur_class:
                if cur_group:
                    groups.append(cur_group)
                cur_group = BeautifulSoup("", "html.parser")
                cur_class = row_class
            cur_group.append(row)  # type: ignore

        if cur_group:
            groups.append(cur_group)

        wr_entries = []
        for group in groups:
            fr_wrd_tag = group.find("td", {"class": "FrWrd"})
            to_wrd_tag = group.find("td", {"class": "ToWrd"})
            fr_wrds = []
            to_wrds = []
            for tag in fr_wrd_tag:
                fr_wrds.extend(parse_words(tag.text))
            for tag in to_wrd_tag:
                to_wrds.extend(parse_words(tag.text))

            # Parsing POS requires to first scrape their abbreviation list.
            # for word in to_wrds:
            #     if self.word in word:
            #         print(word)

            fr_exs = []
            for item in group.find_all("td", {"class": "FrEx"}):
                text = item.text.strip()
                if "ⓘ" not in text:
                    fr_exs.append(text)
            to_exs = []
            for item in group.find_all("td", {"class": "ToEx"}):
                text = item.text.strip()
                if "ⓘ" not in text:
                    to_exs.append(text)

            # If the pairs are not balanced, take the first choice.
            #
            # > I'm not sure what this thing is.   < this
            # > Δεν ξέρω τι είναι αυτό το πράγμα.  < this
            # > Δεν ξέρω τι είναι αυτό το πράμα.
            min_size = min(len(fr_exs), len(to_exs))
            fr_exs = fr_exs[:min_size]
            to_exs = to_exs[:min_size]

            wr_entry = DictEntryItem(fr_wrds, to_wrds, fr_exs, to_exs)
            wr_entries.append(wr_entry)

        return wr_entries


def main() -> None:
    """For testing only."""
    import sys

    word = sys.argv[1].strip() if len(sys.argv) > 1 else None

    wr = Wordref(
        word=word,
        gr_en=True,
        hide_words=False,
        min_sentences_shown=1,
        max_sentences_shown=3,
    )
    entry = wr.try_fetch_entry()
    print(entry)


if __name__ == "__main__":
    main()
