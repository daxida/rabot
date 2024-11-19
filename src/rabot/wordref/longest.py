import re
import unicodedata
from typing import Set


def lcs(a: str, b: str) -> int:
    """Finds the longuest common substring of a and b."""
    if a == b:
        return len(a)
    var = 0
    while a:
        i = 1
        while True:
            _buffer = a[:i]
            if _buffer in b and i < len(a):
                i += 1
            else:
                break
        var = max(i - 1, var)
        a = a[i:]

    return var


def normalize_greek_word(word: str) -> str:
    """Return a greek word without accents in lowercase.
    ["Άλφα", "Αλφα", "άλφα", "αλφα"] are all converted into "αλφα".

    >>> words = ["Άλφα", "Αλφα", "άλφα", "αλφα"]
    >>> normalized_words = [normalize_greek_word(w) for w in words]
    >>> assert len(set(normalized_words)) == 1
    """
    normalized = unicodedata.normalize("NFKD", word).casefold()
    return "".join(c for c in normalized if not unicodedata.combining(c))


def get_delta(a: str, b: str) -> float:
    aa = normalize_greek_word(a)
    bb = normalize_greek_word(b)

    max_length = max(len(aa), len(bb))
    m = max(lcs(aa, bb), lcs(bb, aa))

    return (max_length - m) / max_length


def highlight_synonyms(sentence: str, synonyms: Set[str]) -> str:
    for word in set(sentence.split()):
        # Removes punctuation to match the correct words
        word = re.sub(r"\(|\)|,|\.|", "", word)  # add ; ??
        for reference in synonyms:
            # 1 = same word, 0 = completely different
            dif = get_delta(word, reference)
            # If the estimated difference is lower than 0.25
            # we treat both word as the same (declension, plural etc.)
            if dif <= 0.3:
                sentence = sentence.replace(word, f"**{word}**")
                break

    return sentence


if __name__ == "__main__":
    pass
