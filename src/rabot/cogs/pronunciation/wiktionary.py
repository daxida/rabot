from typing import Any, Tuple

import requests
from bs4 import BeautifulSoup


def get_wiktionary_ipa(word: str) -> Tuple[str, Any | None]:
    link = f"https://el.wiktionary.org/wiki/{word}"
    response = requests.get(link)
    if response.status_code != 200:
        return link, None
    soup = BeautifulSoup(response.text, "html.parser")
    # Account for the query word being written without accents by scraping the accented word.
    pronunciation = soup.find("a", {"title": "Παράρτημα:Προφορά/νέα ελληνικά"})
    if pronunciation is None:
        return link, None
    return link, pronunciation.text
