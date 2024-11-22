"""Wiktionary Parser for Greek Pages
Example usage: fetch_wiktionary("καλημέρα", language="greek")
Returns as a JSON containing word types and entries

TODO: Unify the parsing.
"""

from __future__ import annotations

import pprint
from typing import Any

import requests
from bs4 import BeautifulSoup

from rabot.exceptions import RabotError
from rabot.log import logger
from rabot.utils import get_language_code

# fmt: off
ENTRIES = [
    "Ετυμολογία", "Ετυμολογία_1", "Ετυμολογία_2",
    "Προφορά", "Προφορά_1", "Προφορά_2",
    "Επιφώνημα", "Έκφραση", "Ουσιαστικό",
    "Εκφράσεις", "Επίθετο", "Επίρρημα", "Συνώνυμα", "Αντώνυμα",
    "Κλιτικός_τύπος_επιθέτου", "Κλιτικός_τύπος_ουσιαστικού",
    "Πολυλεκτικοί_όροι", "Σημειώσεις",
]  # Μεταφράσεις, "Σύνθετα", "Συγγενικά" cut off here
ENTRIES_EN = [
    "Etymology", "Etymology_1", "Etymology_2",
    "Pronunciation", "Pronunciation_2", "Pronunciation_3",
    "Interjection", "Interjection_2", "Expression",
    "Expression_2", "Expressions", "Noun", "Noun_2",
    "Adjective", "Adjective_2", "Adverb", "Adverb_2",
    "Related", "Synonyms", "Antonyms", "Synonyms_2", "Antonyms_2",
]
# fmt: on


class WiktionaryQuery:
    __slots__ = "soup", "word"

    @classmethod
    def create(cls, word: str, *, language: str = "el") -> WiktionaryQuery:
        """Create a WiktionaryQuery object.

        For reference (obsolete since this does not use async anymore).
        https://stackoverflow.com/questions/33128325/how-to-set-class-attribute-with-await-in-init
        """
        word = word.strip()

        lang = get_language_code(language)
        url = f"https://{lang}.wiktionary.org/wiki/{word}"
        logger.debug(f"GET {url}")
        res = requests.get(url)
        soup = BeautifulSoup(res.text, "html.parser")
        WiktionaryQuery.remove_ancient_greek(soup, language)

        self = cls()
        self.word = word
        self.soup = soup

        return self

    @staticmethod
    def remove_ancient_greek(soup: Any, language: str) -> None:
        """Mutates soup to remove ancient greek elements."""
        if language == "english":
            remove_string = "Ancient_Greek"
            stop_at_string = "Greek"
        else:
            remove_string = "Αρχαία_ελληνικά_(grc)"
            stop_at_string = None

        if tag_to_remove := soup.find("h2", id=remove_string):
            current_element = tag_to_remove.find_parent()
            while current_element:
                next_sibling = current_element.find_next_sibling()
                if next_sibling and stop_at_string and next_sibling.find("h2", string=stop_at_string):
                    break

                # remove the current element and move to next sibling
                current_element.extract()
                current_element = next_sibling


VERB_VOICES = ("Ενεργητική φωνή", "Παθητική φωνή")
ConjugationDict = dict[str, dict[str, list[str]]] | None


def fetch_conjugation(word: str) -> ConjugationDict:
    """Fetch the verb conjugation table.

    Retry with word variations by parsing wiktionary.
    """
    query = WiktionaryQuery.create(word)
    conjugation = _fetch_conjugation(query)
    if conjugation:
        logger.success(f"Fetched conjugation for {word}")
    else:
        logger.warning(f"Failed fetching conjugation for {word}")
    return conjugation


def _fetch_conjugation(query: WiktionaryQuery) -> ConjugationDict:
    res = _parse_conjugation(query)
    if res is not None:
        return res

    suggestions = parse_suggestions(query)
    logger.debug(f"Trying suggestions. Found {len(suggestions)}.")
    valid_suggestions = list({*suggestions} - {query.word})

    for suggestion in valid_suggestions:
        new_query = WiktionaryQuery.create(suggestion)
        # If we succeed with a suggestion, just return it,
        # even if it is potentially not the best?
        res = _parse_conjugation(new_query)
        if res is not None:
            return res


def parse_suggestions(query: WiktionaryQuery) -> list[str]:
    """Parse suggested words in case of failure."""
    suggestions: list[str] = []

    suggestions.extend(parse_deite_suggestions(query))

    # Search for άλλη μορφή (other verb form...) suggestions.
    # cf: https://el.wiktionary.org/wiki/περπατώ
    res = query.soup.find_all("li")
    for li in res:
        if "άλλη μορφή" in li.text:
            links = li.find_all("a", title=True)
            for link in links:
                suggestions.append(link["title"])

    if not suggestions:
        logger.warning(f"Found no suggestions for {query.word}.")

    return suggestions


def parse_deite_suggestions(query: WiktionaryQuery) -> list[str]:
    """Search for deite (see also...) suggestions."""
    suggestions: list[str] = []

    deite = ["→ δείτε τη λέξη", "→\xa0δείτε\xa0τη\xa0λέξη"]

    to_search = [
        # cf: https://el.wiktionary.org/wiki/αγαπώ
        ["div", {"class": "NavContent"}],
        # Sometimes deite suggestions are elsewhere.
        # Here we search every "li" (risky, we could add junk).
        # cf: https://el.wiktionary.org/wiki/βρίσκομαι
        #     In this case the suggestion is in the conjugation table.
        ["li"],
    ]

    for search in to_search:
        for div in query.soup.find_all(search):
            if any(d in div.text for d in deite):
                links = div.find_all("a", title=True)
                for link in links:
                    suggestions.append(link["title"])
    return suggestions


def _parse_conjugation(query: WiktionaryQuery) -> ConjugationDict:
    """Parse the verb conjugation table from a word.

    Return None in case of failure.
    """
    logger.debug(f"Trying to fetch {query.word}...")

    # Check that the conjugation header is there.
    # Note that the header being present does not guarantee a valid conjugation table.
    # cf. https://el.wiktionary.org/wiki/βρέχω?printable=yes
    if query.soup.find("h4", {"id": "Κλίση"}) is None:
        logger.trace(f"{query.word} has no conjugation table.")
        return None

    parsed_conjugations = _parse_conjugation_table_one(query) or _parse_conjugation_table_two(query)

    return parsed_conjugations


def _parse_conjugation_table_one(query: WiktionaryQuery) -> ConjugationDict:
    """Try fetching the standard table structure."""
    logger.debug("Trying to fetch table structure one.")

    # The active / passive voices are each in one nav_frame.
    nav_frame = query.soup.find_all("div", {"class": "NavFrame"})
    logger.debug(f"Found {len(nav_frame)} nav_frames")
    if not nav_frame:
        logger.trace(f"{query.word} has no NavFrames.")
        return None

    # The wiktionary table is organized in entries. From which, only
    # the first two are relevant.
    #
    # Each entry contains 8 rows:
    #   - (1) [Verb tense category (f.e. Εξακολουθητικοί χρόνοι)]
    #   - (1) ['πρόσωπα', Verb tenses (f.e. Ενεστώτας)]
    #   - (6) [Personal pronoun, Verb declination]
    table_data: list[list[list[str]]] = []

    for verb_voice in nav_frame:
        nav_head = verb_voice.find("div", {"class": "NavHead"})
        if nav_head is None:
            continue

        title = nav_head.text.strip()
        if title not in VERB_VOICES:
            # This happens when we hit the translation nav_head
            continue

        voice_data: list[list[str]] = []
        nav_content = verb_voice.find("div", {"class": "NavContent"})
        for idx, row in enumerate(nav_content.find_all("tr")):
            # We only need at most 16 rows for the relevant tenses.
            # This prevents the parsing logic from failing if some extra random
            # rows were found.
            # cf: https://el.wiktionary.org/wiki/περπατάω?printable=yes
            if idx == 16:
                break

            row_data: list[str] = list()
            for cell in row.find_all(["th", "td"]):
                # Some variations are <br> separated, we need to replace it
                # to not concatenate them in row_data
                # cf. https://el.wiktionary.org/wiki/βαριέμαι?printable=yes
                for br in cell.find_all("br"):
                    br.replace_with(" / ")

                text = cell.get_text(strip=True)
                if text:
                    row_data.append(text)

            voice_data.append(row_data)

        table_data.append(voice_data)

    if not table_data:
        # This is most likely a malformed webpage
        logger.warning("No data. No NavFrame contained verb information.")
        return None

    relevant_tenses = ["Ενεστώτας", "Παρατατικός", "Αόριστος", "Συνοπτ. Μέλλ."]
    parsed: dict[str, dict[str, list[str]]] = dict()

    for idx_voice, voice_data in enumerate(table_data):
        if len(voice_data) % 8 != 0:
            logger.error(f"The data size is not a multiple of 8: {len(voice_data)}")
            raise RabotError("Logic error when fetching conjugation?")

        parsed_voice: dict[str, list[str]] = dict()
        for i in range(len(voice_data) // 8):
            _ = voice_data[8 * i]  # tense category
            # Take the transpose
            table = list(zip(*voice_data[8 * i + 1 : 8 * (i + 1)]))
            for nav_content in table:
                tense, *conj = nav_content
                if tense in relevant_tenses:
                    parsed_voice[tense] = conj

        parsed[VERB_VOICES[idx_voice]] = parsed_voice

    return parsed


def _parse_conjugation_table_two(query: WiktionaryQuery) -> ConjugationDict:
    """Try fetching the non-standard table structure.

    https://el.wiktionary.org/wiki/ξέρω?printable=yes
    https://el.wiktionary.org/wiki/είμαι?printable=yes

    This usally covers defective verbs.
    """
    # TODO: make this consistent with conj table one!

    logger.info("Trying to fetch table structure two.")

    main_content = query.soup.find("div", {"class": "mw-content-ltr mw-parser-output"})
    if main_content is None:
        raise RabotError("No main content. Wrong logic?")

    tables = main_content.find_all("table")
    if not tables:
        logger.info(f"{query.word} has no tables.")
        return None

    voice_data: list[list[str]] = list()

    for table in tables:
        rows = table.find_all("tr")
        # Need 7 rows
        if len(rows) != 7:
            continue

        for row in rows:
            row_data: list[str] = list()
            for cell in row.find_all(["th", "td"]):
                # Some variations are <br> separated, we need to replace it
                # to not concatenate them in row_data
                # cf. https://el.wiktionary.org/wiki/βαριέμαι?printable=yes
                for br in cell.find_all("br"):
                    br.replace_with(" / ")
                if text := cell.get_text(strip=True):
                    row_data.append(text)

            if row_data:
                voice_data.append(row_data)

    if not voice_data:
        logger.info("No data. No table contained verb information.")
        return None

    # TODO: add this in the other function
    # Be sure that we didn't add two random tables
    height = len(voice_data)
    assert height == 7, f"Expected height to be 7, but got {height}."

    # Copy pasted from table one
    parsed: dict[str, list[str]] = dict()
    for col in zip(*voice_data):
        parsed[col[0]] = list(col[1:])

    relevant_tenses = ["Ενεστώτας", "Παρατατικός"]

    relevant_parsed = {"Ενεργητική φωνή": {tense: parsed[tense] for tense in relevant_tenses}}

    return relevant_parsed


def fetch_wiktionary_pos(word: str, language: str) -> dict[str, list[str]]:
    query = WiktionaryQuery.create(word, language=language)
    return parse_wiktionary_pos(query, language)


def parse_wiktionary_pos(query: WiktionaryQuery, language: str) -> dict[str, list[str]]:
    """Parse parts of speech."""
    entries = ENTRIES_EN[:] if language == "english" else ENTRIES[:]
    pos: dict[str, list[str]] = dict()

    for entry in entries:
        entry_elements = parse_entry(query, entry)
        if entry_elements is not None:
            pos[entry] = entry_elements

    return pos


def parse_entry(query: WiktionaryQuery, entry_id: str) -> list[str] | None:
    # find position of page element with desired type
    results = query.soup.find(["h3", "h4"], id=entry_id)
    if not results:
        return None

    entry_elements: list[str] = []
    # due to wiktionary formatting, finds body under the entry
    next_element = results.parent.find_next_sibling()

    # used for translations and other lists in divs
    if next_element and next_element.name == "div":
        list_element = next_element.find_all("li")
        if list_element:
            for element in list_element:
                # add to the entry list
                entry_elements.append(element.text)
    else:
        # these element types denote new entries so they terminate the loop
        while next_element and next_element.name not in ["h3", "h4", "h5", "div"]:
            list_element = next_element.find_all("li")
            # if only one instance of entry (e.g. only one definition)
            if not list_element:
                entry_elements.append(next_element.text)
                next_element = next_element.find_next_sibling()
            else:
                for element in list_element:
                    entry_elements.append(element.text)
                next_element = next_element.find_next_sibling()

    return entry_elements


if __name__ == "__main__":
    query = WiktionaryQuery.create("τρέχω", language="el")
    conj = fetch_conjugation("δημιουργώ")
    pprint.pprint(conj, compact=True)
