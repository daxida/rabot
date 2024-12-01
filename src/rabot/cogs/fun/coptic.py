import unicodedata


def remove_greek_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    normalized = unicodedata.normalize("NFC", stripped)
    return normalized


def to_coptic(text: str, *, remove_accents: bool = True) -> str:
    # https://www.suscopts.org/deacons/coptic/FT-Coptic%20Language-Lectures.pdf
    chars_co = "ⲀⲁⲂⲃⲄⲅⲆⲇⲈⲉⲌⲍⲎⲏⲐⲑⲒⲓⲔⲕⲖⲗⲘⲙⲚⲛⲜⲝⲞⲟⲠⲡⲢⲣⲤⲥⲥⲦⲧⲨⲩⲪⲫⲬⲭⲮⲯⲰⲱ"
    chars_gr = "ΑαΒβΓγΔδΕεΖζΗηΘθΙιΚκΛλΜμΝνΞξΟοΠπΡρΣσςΤτΥυΦφΧχΨψΩω"
    translation_table = str.maketrans(dict(zip(chars_gr, chars_co)))

    if remove_accents:
        text = remove_greek_accents(text)

    return text.translate(translation_table)
