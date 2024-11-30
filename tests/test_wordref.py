from rabot.cogs.wordref.wordref import Wordref


def test_wordref() -> None:
    word = "ημερήσιος"
    gr_en = True
    hide_words = True
    min_sentences_shown = 1
    max_sentences_shown = 5

    wordref = Wordref(word, gr_en, hide_words, min_sentences_shown, max_sentences_shown)
    entry = wordref.try_fetch_entry()

    assert entry.gr_en == gr_en

    assert entry.word == "ημερήσιος"
    assert "ημερήσιος" in entry.items[0].fr_words
    assert "daily" in entry.items[0].to_words
