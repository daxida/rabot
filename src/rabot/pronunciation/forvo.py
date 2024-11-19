# From: https://github.com/realmayus/anki_forvo_dl/blob/main/src/Forvo.py

import base64
import io
import random
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import List, Union
from urllib.error import HTTPError

import requests
from bs4 import BeautifulSoup

from rabot.utils import NotFoundError

search_url = "https://forvo.com/word/"
download_url = "https://forvo.com/download/mp3/"


def log_debug(msg):
    # print(msg)
    pass


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
    audio: Union[str, None] = None


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
    def __init__(self, word: str, language: str):
        self.html: BeautifulSoup
        self.language = language
        word = word.strip()
        log_debug("[Forvo.py] Using search query: %s" % word)
        self.word = word
        self.pronunciations: List[Pronunciation] = []

        # Set a user agent so that Forvo/CloudFlare lets us access the page
        opener = urllib.request.build_opener()

        opener.addheaders = HEADERS
        urllib.request.install_opener(opener)

    def load_search_query(self):
        """Retries only in case of 403: Forbidden."""
        for _ in range(3):
            try:
                self._load_search_query()
            except HTTPError as e:
                if e.code != 403:
                    raise e
                time.sleep(0.5)

    def _load_search_query(self):
        """Loads the search result page on Forvo"""
        try:
            log_debug("[Forvo.py] Reading result page")
            page = urllib.request.urlopen(url=search_url + urllib.parse.quote_plus(self.word)).read()
            log_debug("[Forvo.py] Done with reading result page")

            log_debug("[Forvo.py] Initializing BS4")
            self.html = BeautifulSoup(page, "html.parser")
            log_debug("[Forvo.py] Initialized BS4")
        except HTTPError as e:
            log_debug(f"[Forvo.py] HTTPError: {e}")
            if e.code == 404:
                raise NotFoundError()
            # Sometimes we can get 403: Forbidden
            raise e
        except Exception as e:
            log_debug("[Forvo.py] Exception: " + str(e))
            raise e

    def get_pronunciations(self):
        """Creates pronunciation objects from the soup"""
        log_debug("[Forvo.py] Searching language containers")
        available_langs_el = self.html.find_all(id=re.compile(r"language-container-\w{2,4}"))
        log_debug("[Forvo.py] Done searching language containers")
        log_debug("[Forvo.py] Compiling list of available langs")
        available_langs = [
            re.findall(r"language-container-(\w{2,4})", el.attrs["id"])[0] for el in available_langs_el
        ]
        if self.language not in available_langs:
            raise NotFoundError()
        log_debug("[Forvo.py] Done compiling list of available langs")

        log_debug("[Forvo.py] Searching lang container")
        lang_container = [
            lang
            for lang in available_langs_el
            if re.findall(r"language-container-(\w{2,4})", lang.attrs["id"])[0] == self.language
        ][0]
        log_debug("[Forvo.py] Done searching lang container")

        log_debug("[Forvo.py] Going through all pronunciations")
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
                    vote_count = int(str(re.findall(r"(-?\d+).*", vote_count_inner_span[0].contents[0])[0]))

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
                        base64.b64decode(pronunciation_dl), "utf-8",
                    )
                    is_ogg = True
                else:
                    pronunciation_dl = pronunciation_dls[0]
                    dl_url = "https://audio00.forvo.com/audios/mp3/" + str(
                        base64.b64decode(pronunciation_dl), "utf-8",
                    )

                author_info = pronunciation.find_all(
                    lambda el: bool(el.find_all(string=re.compile("Pronunciation by"))),
                    class_="info",
                )[0]
                username = re.findall("Pronunciation by(.*)", author_info.get_text(" "), re.DOTALL)[0].strip()
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

        return self


def get_forvo_pronunciation_audio(word: str) -> io.BytesIO:
    """Can raise if 404: NotFound, or 403: Forbidden"""
    f = Forvo(word, "el")
    f.load_search_query()
    f.get_pronunciations()

    # pronunciation = f.pronunciations[0]
    pronunciation = random.choice(f.pronunciations)
    response = requests.get(pronunciation.download_url, headers=dict(HEADERS))
    audio_file = io.BytesIO(response.content)

    return audio_file
