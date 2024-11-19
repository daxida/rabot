import asyncio

import pytest

from wiktionary.wiktionary import fetch_conjugation, fetch_wiktionary_pos

# https://stackoverflow.com/questions/70015634/how-to-test-async-function-using-pytest
pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio()
async def test_wiktionary_fetch_conjugation():
    """A simple concurrent async test.

    This uses no cache and sends quite some requests to wiktionary. Use carefully.
    Use the debug entry in the fixture to only run certain entries.
    """
    debug = False

    fixture = [
        # verb // has_result // debug
        ("αγαπώ", True, False),
        ("αγαπάω", True, False),
        ("περπατώ", True, False),
        ("περπατάω", True, False),
        ("χαραλώνω", False, False),
        ("βρέχω", False, False),
        ("βρίσκομαι", True, False),
        ("ξέρω", True, False),
        ("είμαι", True, False),
    ]

    if debug:
        fixture = [(verb, has_result, debug) for verb, has_result, debug in fixture if debug]

    tasks = [fetch_conjugation(verb) for verb, _, _ in fixture]
    results = await asyncio.gather(*tasks)
    for (verb, has_result, _), received in zip(fixture, results):
        if has_result:
            assert received is not None, verb
        else:
            assert received is None, verb


@pytest.mark.asyncio()
async def test_wiktionary_fetch_word_greek():
    language = "greek"
    fixture_el = ["τραπέζι", "εστιατόριο"]
    tasks = [fetch_wiktionary_pos(word, language) for word in fixture_el]
    results = await asyncio.gather(*tasks)
    for result in results:
        assert "Ετυμολογία" in result
        assert "Ουσιαστικό" in result


@pytest.mark.asyncio()
async def test_wiktionary_fetch_word_english():
    language = "english"
    fixture_el = ["table", "restaurant"]
    tasks = [fetch_wiktionary_pos(word, language) for word in fixture_el]
    results = await asyncio.gather(*tasks)
    for result in results:
        assert "Etymology" in result
        assert "Noun" in result
