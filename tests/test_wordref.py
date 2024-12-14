from rabot.cogs.wordref.wordref import Wordref


def test_wordref() -> None:
    word = "ημερήσιος"
    gr_en = True

    wordref = Wordref(word, gr_en=gr_en, hide_words=True, sentence_range=(1, 5))
    entry = wordref.try_fetch_entry()

    assert entry.gr_en == gr_en

    assert entry.word == "ημερήσιος"
    assert "ημερήσιος" in entry.items[0].fr_words
    assert "daily" in entry.items[0].to_words
