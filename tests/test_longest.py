import itertools

from rabot.wordref.longest import get_delta


def test_longest():
    words = ["Άλφα", "Αλφα", "άλφα", "αλφα"]
    for w1, w2 in itertools.combinations(words, 2):
        assert get_delta(w1, w2) == 0
