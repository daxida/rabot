# From: https://github.com/realmayus/anki_forvo_dl/blob/main/src/Forvo.py

import base64
import io
import random
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from urllib.error import HTTPError

import requests
from bs4 import BeautifulSoup

from rabot.exceptions import NotFoundError
from rabot.log import logger

LANG_CONTAINER_RE = re.compile(r"language-container-(\w{2,4})")


@dataclass
class Pronunciation:
    language: str
    user: str
    origin: str
    id: int
    votes: int
    download_url: str
    is_ogg: bool
    word: str
    # audio: str | None = None


HEADERS = [
    (
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    ),
    (
        "Accept",
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    ),
    ("Accept-Language", "en-US,en;q=0.5"),
    ("Referer", "https://forvo.com/"),
]


class Forvo:
    SEARCH_URL = "https://forvo.com/word/"

    def __init__(self, word: str, language: str) -> None:
        self.language = language
        self.word = word.strip()
        logger.debug("[Forvo.py] Using search query: %s" % self.word)

        self.soup: BeautifulSoup
        self.pronunciations: list[Pronunciation] = []

        # Set a user agent so that Forvo/CloudFlare lets us access the page
        opener = urllib.request.build_opener()
        opener.addheaders = HEADERS
        urllib.request.install_opener(opener)

    def fetch_soup(self) -> None:
        """Fetch Forvo's html and soup it.

        Retries only in case of 403: Forbidden.
        """
        for _ in range(3):
            try:
                self.soup = self._fetch_soup()
                logger.success(f"Fetched html for {self.word}")
                break
            except HTTPError as e:
                if e.code != 403:
                    raise e
                logger.error(e)
                time.sleep(0.5)

    def _fetch_soup(self) -> BeautifulSoup:
        try:
            url = Forvo.SEARCH_URL + urllib.parse.quote_plus(self.word)
            logger.debug(f"[Forvo.py] GET {url}")
            page = urllib.request.urlopen(url=url).read()
            return BeautifulSoup(page, "html.parser")
        except HTTPError as e:
            logger.debug(f"[Forvo.py] HTTPError: {e}")
            if e.code == 404:
                raise NotFoundError from e
            raise RuntimeError(f"Failed to fetch page from Forvo: {e}") from e

    def get_pronunciations(self) -> None:
        """Populates self.pronunciations from the stored soup's."""
        available_langs_el = self.soup.find_all(id=LANG_CONTAINER_RE)
        logger.debug("[Forvo.py] Done searching language containers")

        available_langs = [
            LANG_CONTAINER_RE.findall(el.attrs["id"])[0] for el in available_langs_el
        ]
        if self.language not in available_langs:
            raise NotFoundError
        logger.debug("[Forvo.py] Done compiling list of available langs")

        lang_container = [
            lang
            for lang in available_langs_el
            if LANG_CONTAINER_RE.findall(lang.attrs["id"])[0] == self.language
        ][0]
        logger.debug("[Forvo.py] Done searching lang container")

        logger.debug("[Forvo.py] Going through all pronunciations")
        for accents in lang_container.find_all(class_="pronunciations")[0].find_all(
            class_="pronunciations-list",
        ):
            for pronunciation in accents.find_all("li"):
                if len(pronunciation.find_all(class_="more")) == 0:
                    continue

                vote_count = (
                    pronunciation.find_all(class_="more")[0]
                    .find_all(class_="main_actions")[0]
                    .find_all(id=re.compile(r"word_rate_\d+"))[0]
                    .find_all(class_="num_votes")[0]
                )

                vote_count_inner_span = vote_count.find_all("span")
                if len(vote_count_inner_span) == 0:
                    vote_count = 0
                else:
                    vote_count = int(
                        str(re.findall(r"(-?\d+).*", vote_count_inner_span[0].contents[0])[0])
                    )

                pronunciation_dls = re.findall(
                    r"Play\(\d+,'.+','.+',\w+,'([^']+)",
                    pronunciation.find_all(id=re.compile(r"play_\d+"))[0].attrs["onclick"],
                )

                is_ogg = False
                if len(pronunciation_dls) == 0:
                    """Fallback to .ogg file"""
                    pronunciation_dl = re.findall(
                        r"Play\(\d+,'[^']+','([^']+)",
                        pronunciation.find_all(id=re.compile(r"play_\d+"))[0].attrs["onclick"],
                    )[0]
                    dl_url = "https://audio00.forvo.com/ogg/" + str(
                        base64.b64decode(pronunciation_dl),
                        "utf-8",
                    )
                    is_ogg = True
                else:
                    pronunciation_dl = pronunciation_dls[0]
                    dl_url = "https://audio00.forvo.com/audios/mp3/" + str(
                        base64.b64decode(pronunciation_dl),
                        "utf-8",
                    )

                author_info = pronunciation.find_all(
                    lambda el: bool(el.find_all(string=re.compile("Pronunciation by"))),
                    class_="info",
                )[0]
                username = re.findall(
                    "Pronunciation by(.*)",
                    author_info.get_text(" "),
                    re.DOTALL,
                )[0].strip()
                # data-p* appears to be a way to define arguments for click event
                # handlers; heuristic: if there's only one unique integer value,
                # then it's the ID
                id_ = next(
                    iter(
                        {
                            int(v)
                            for link in pronunciation.find_all(class_="ofLink")
                            for k, v in link.attrs.items()
                            if re.match(r"^data-p\d+$", k) and re.match(r"^\d+$", v)
                        },
                    ),
                )
                if id_:
                    self.pronunciations.append(
                        Pronunciation(
                            self.language,
                            username,
                            pronunciation.find_all(class_="from")[0].contents[0],
                            id_,
                            vote_count,
                            dl_url,
                            is_ogg,
                            self.word,
                        ),
                    )


def get_forvo_pronunciation_audio(word: str) -> io.BytesIO:
    """Return a random pronunciation of the word.

    Can raise if 404: NotFound, or 403: Forbidden.
    """
    fv = Forvo(word, "el")
    fv.fetch_soup()
    fv.get_pronunciations()

    # pronunciation = f.pronunciations[0]
    pronunciation = random.choice(fv.pronunciations)
    response = requests.get(pronunciation.download_url, headers=dict(HEADERS))
    audio_file = io.BytesIO(response.content)

    return audio_file


if __name__ == "__main__":
    """For testing only."""
    fv = Forvo("καλημέρα", "el")
    fv.fetch_soup()
    fv.get_pronunciations()
    print(fv.pronunciations)
