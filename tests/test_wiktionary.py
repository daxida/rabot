import asyncio

import pytest

from rabot.cogs.wiktionary.wiktionary import (
    ConjugationDict,
    fetch_conjugation,
    fetch_wiktionary_pos,
)

# https://stackoverflow.com/questions/70015634/how-to-test-async-function-using-pytest
pytest_plugins = ("pytest_asyncio",)


async def fetch_conjugation_async(verb: str) -> ConjugationDict:
    return fetch_conjugation(verb)


async def fetch_wiktionary_pos_async(word: str, language: str) -> dict[str, list[str]]:
    return fetch_wiktionary_pos(word, language)


@pytest.mark.asyncio
async def test_wiktionary_fetch_conjugation() -> None:
    """A simple concurrent async test.

    This uses no cache and sends quite some requests to wiktionary. Use carefully.
    Use the debug entry in the fixture to only run certain entries.
    """
    debug = False

    # FIX: deite suggestions
    fixture = [
        # verb // has_result // debug
        # ("αγαπώ", True, False), # The deite suggestion logic is off
        ("αγαπάω", True, False),
        # ("περπατώ", True, False), # The deite suggestion logic is off
        ("περπατάω", True, False),
        ("χαραλώνω", False, False),
        # ("βρέχω", False, False),
        # ("βρίσκομαι", True, False), # The deite suggestion logic is off
        ("ξέρω", True, False),
        ("είμαι", True, False),
    ]

    if debug:
        fixture = [(verb, has_result, debug) for verb, has_result, debug in fixture if debug]

    tasks = [fetch_conjugation_async(verb) for verb, _, _ in fixture]
    results = await asyncio.gather(*tasks)
    for (verb, has_result, _), received in zip(fixture, results):
        if has_result:
            assert received is not None, verb
        else:
            assert received is None, verb


@pytest.mark.asyncio
async def test_wiktionary_fetch_word_greek() -> None:
    language = "greek"
    fixture_el = ["τραπέζι", "εστιατόριο"]
    tasks = [fetch_wiktionary_pos_async(word, language) for word in fixture_el]
    results = await asyncio.gather(*tasks)
    for result in results:
        assert "Ετυμολογία" in result
        assert "Ουσιαστικό" in result


@pytest.mark.asyncio
async def test_wiktionary_fetch_word_english() -> None:
    language = "english"
    fixture_el = ["table", "restaurant"]
    tasks = [fetch_wiktionary_pos_async(word, language) for word in fixture_el]
    results = await asyncio.gather(*tasks)
    for result in results:
        assert "Etymology" in result
        assert "Noun" in result
