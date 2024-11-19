"""
Wiktionary Parser for Greek Pages
Example usage: fetch_wiktionary("καλημέρα", language="greek")
Returns as a JSON containing word types and entries

TODO: Unify the parsing.
"""

import logging
from typing import Any

from aiohttp import ClientSession
from bs4 import BeautifulSoup

from utils import get_language_code

default_language = "greek"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wiktionary")

# fmt: off
ENTRIES = [
    "Ετυμολογία", "Ετυμολογία_1", "Ετυμολογία_2",
    "Προφορά", "Προφορά_1", "Προφορά_2",
    "Επιφώνημα", "Έκφραση", "Ουσιαστικό",
    "Εκφράσεις", "Επίθετο", "Επίρρημα", "Συνώνυμα", "Αντώνυμα",
    "Κλιτικός_τύπος_επιθέτου", "Κλιτικός_τύπος_ουσιαστικού",
    "Πολυλεκτικοί_όροι", "Σημειώσεις"
]  # Μεταφράσεις, "Σύνθετα", "Συγγενικά" cut off here
ENTRIES_EN = [
    "Etymology", "Etymology_1", "Etymology_2",
    "Pronunciation", "Pronunciation_2", "Pronunciation_3",
    "Interjection", "Interjection_2", "Expression",
    "Expression_2", "Expressions", "Noun", "Noun_2",
    "Adjective", "Adjective_2", "Adverb", "Adverb_2",
    "Related", "Synonyms", "Antonyms", "Synonyms_2", "Antonyms_2"
]
# fmt: on


class WiktionaryQuery:
    __slots__ = "word", "language", "soup"

    @classmethod
    async def create(cls, word: str, language: str, printable: bool = True):
        # https://stackoverflow.com/questions/33128325/how-to-set-class-attribute-with-await-in-init
        self = cls()
        self.word = word

        lcode = get_language_code(language)
        # Not sure why we would want the printable version here.
        base_url = f"https://{lcode}.wiktionary.org/wiki/{{}}"
        if printable:
            base_url += "?printable=yes"

        url = base_url.format(word)
        logger.info(f"{url=}")

        async with ClientSession() as session:
            async with session.get(url) as response:
                page_content = await response.read()

        soup = BeautifulSoup(page_content, "html.parser")
        WiktionaryQuery.remove_ancient_greek(soup, language)

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


async def fetch_conjugation(word: str) -> dict[str, str] | None:
    """
    Fetch the verb conjugation table from a word.
    Retry with word variations by parsing wiktionary.
    """

    query = await WiktionaryQuery.create(word, default_language, printable=False)
    conjugation = await _fetch_conjugation(query)
    logger.info("Success." if conjugation else "Failure.")
    return conjugation


async def _fetch_conjugation(query: WiktionaryQuery) -> dict[str, str] | None:
    res = _parse_conjugation(query)
    if res is not None:
        return res

    logger.info("Trying suggestions.")
    # FIXME: parses too many things
    suggestions = parse_suggestions(query)
    logger.info(f"Found {len(suggestions)} suggestions.")
    # Maybe there are cyclic references?
    max_retries = 10
    seen_words = {query.word}

    for suggestion in suggestions:
        if suggestion in seen_words:
            continue
        seen_words.add(suggestion)

        if len(seen_words) >= max_retries:
            logger.warning(f"Reached {max_retries=}")
            return None

        new_query = await WiktionaryQuery.create(suggestion, default_language, printable=False)
        res = _parse_conjugation(new_query)
        # If we succeed with a suggestion, just return it,
        # even if it is potentially not the best?
        if res is not None:
            return res


def parse_suggestions(query: WiktionaryQuery) -> list[str]:
    """Generic helper to parse suggested words in case of failure."""
    # TODO: merge li soups (needs further testing).
    suggestions: list[str] = list()

    # Search for deite (see also...) suggestions
    deite = ["→ δείτε τη λέξη", "→\xa0δείτε\xa0τη\xa0λέξη"]

    # cf: https://el.wiktionary.org/wiki/αγαπώ?printable=yes
    res = query.soup.find_all("div", {"class": "NavContent"})
    for div in res:
        if any(d in div.text for d in deite):
            links = div.find_all("a", title=True)
            for link in links:
                suggestions.append(link["title"])

    # Sometimes deite suggestions are elsewhere.
    # Here we search everything (even though we could potentially find
    # an unwanted match somewhere?).
    # cf: https://el.wiktionary.org/wiki/βρίσκομαι?printable=yes
    res = query.soup.find_all("li")
    for span in res:
        if any(d in span.text for d in deite):
            links = span.find_all("a", title=True)
            for link in links:
                suggestions.append(link["title"])

    # Search for other verb forms
    # cf: https://el.wiktionary.org/wiki/περπατώ?printable=yes
    res = query.soup.find_all("li")
    for li in res:
        if "άλλη μορφή" in li.text:
            links = li.find_all("a", title=True)
            for link in links:
                suggestions.append(link["title"])

    if not suggestions:
        logger.warning(f"Found no suggestions for {query.word}.")

    return suggestions


def _parse_conjugation(query: WiktionaryQuery) -> dict[str, str] | None:
    """
    Parse the verb conjugation table from a word.
    Return None in case of failure.
    """
    logger.info(f"Trying to fetch {query.word}...")

    # Check that the conjugation header is there.
    # Note that the header doesn't guarantee a valid conjugation table.
    # cf. https://el.wiktionary.org/wiki/βρέχω?printable=yes
    if query.soup.find("h4", {"id": "Κλίση"}) is None:
        logger.info(f"{query.word} has no conjugation table.")
        return None

    parsed_conjugations = _parse_conjugation_table_one(query) or _parse_conjugation_table_two(query)

    return parsed_conjugations


def _parse_conjugation_table_one(query: WiktionaryQuery) -> dict[str, str] | None:
    """Try fetching the standard table structure."""
    logger.info("Trying to fetch table structure one.")

    verb_voices = ["Ενεργητική φωνή", "Παθητική φωνή"]

    # The active / passive voices are each in one nav_frame.
    nav_frame = query.soup.find_all("div", {"class": "NavFrame"})
    if not nav_frame:
        logger.info(f"{query.word} has no NavFrames.")
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
        title_res = verb_voice.find("div", {"class": "NavHead"})
        if title_res is None:
            continue
        title = title_res.text.strip()
        if title not in verb_voices:
            continue

        voice_data: list[list[str]] = list()
        entry = verb_voice.find("div", {"class": "NavContent"})
        for idx, row in enumerate(entry.find_all("tr")):
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
        logger.info("No data. No NavFrame contained verb information.")
        return None

    parsed: dict[str, dict[str, list[str]]] = dict()
    for idx_voice, voice_data in enumerate(table_data):
        if not len(voice_data) % 8 == 0:
            logger.warning(f"The data size is not a multiple of 8: {len(voice_data)}")
            assert False

        parsed_voice: dict[str, list[str]] = dict()
        for i in range(len(voice_data) // 8):
            _ = voice_data[8 * i]  # tense category
            # Take the transpose
            table = list(zip(*voice_data[8 * i + 1 : 8 * (i + 1)]))
            for entry in table:
                parsed_voice[entry[0]] = list(entry[1:])

        parsed[verb_voices[idx_voice]] = parsed_voice

    # Just hack something visual for the moment
    relevant_tenses = ["Ενεστώτας", "Παρατατικός", "Αόριστος", "Συνοπτ. Μέλλ."]

    cur_voice = verb_voices[0]
    relevant_parsed = {tense: "\n".join(parsed[cur_voice][tense]) for tense in relevant_tenses}

    return relevant_parsed


def _parse_conjugation_table_two(query: WiktionaryQuery) -> dict[str, str] | None:
    """
    Try fetching the non-standard table structure. Cf.
    https://el.wiktionary.org/wiki/ξέρω?printable=yes
    https://el.wiktionary.org/wiki/είμαι?printable=yes

    This usally covers defective verbs.
    """
    logger.info("Trying to fetch table structure two.")

    main_content = query.soup.find("div", {"class": "mw-content-ltr mw-parser-output"})
    assert main_content is not None

    tables = main_content.find_all("table")
    if not tables:
        logger.info(f"{query.word} has no tables.")
        return None

    voice_data: list[list[str]] = list()

    for table in tables:
        # Need 7 rows
        rows = table.find_all("tr")
        if len(rows) != 7:
            continue

        for row in rows:
            # Copy pasted from previous function

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

            if row_data:
                voice_data.append(row_data)

    if not voice_data:
        logger.info("No data. No table contained verb information.")
        return None

    # TODO: add this in the other function
    # Be sure that we didn't add two random tables
    height = len(voice_data)
    assert height == 7, f"Expected height to be 7, but got {height}."

    # Copy pasted
    parsed: dict[str, list[str]] = dict()
    # Take the transpose
    for col in zip(*voice_data):
        parsed[col[0]] = list(col[1:])
    # print(parsed)

    relevant_tenses = ["Ενεστώτας", "Παρατατικός"]

    relevant_parsed = {tense: "\n".join(parsed[tense]) for tense in relevant_tenses}

    return relevant_parsed


async def fetch_wiktionary_pos(word: str, language: str) -> dict[str, list[str]]:
    query = await WiktionaryQuery.create(word, language)
    entries = parse_wiktionary_pos(query, language)
    return entries


def parse_wiktionary_pos(query: WiktionaryQuery, language: str) -> dict[str, list[str]]:
    entries = ENTRIES[:]
    if language == "english":
        entries = ENTRIES_EN[:]

    parts_of_speech: dict[str, list[str]] = dict()
    for entry in entries:
        entry_elements = parse_entry(query, entry)
        if entry_elements is not None:
            parts_of_speech[entry] = entry_elements

    return parts_of_speech


def parse_entry(query: WiktionaryQuery, entry_type: str) -> list[str] | None:
    # find position of page element with desired type
    results = query.soup.find(["h3", "h4"], id=entry_type)
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
    pass
