import pytest

from rabot.cogs.pronunciation.pronunciation import get_pronunciation
from rabot.exceptions import NotFoundError
from rabot.utils import fix_greek_spelling


def test_existing_pronunciation() -> None:
    word = "ευχαριστώ"
    message, _ = get_pronunciation(word)
    assert message == "Word: ευχαριστώ\nIPA: ef.xa.ɾiˈsto\n"


def test_non_existing_pronunciation() -> None:
    word = "μπλαμπλα"
    with pytest.raises(NotFoundError):
        get_pronunciation(word)


def test_retry_pronunciation() -> None:
    word = "ευχαριστω"
    with pytest.raises(NotFoundError):
        get_pronunciation(word)

    # Retry with corrected spelling
    word = fix_greek_spelling(word)
    message, _ = get_pronunciation(word)
    assert message == "Word: ευχαριστώ\nIPA: ef.xa.ɾiˈsto\n"
