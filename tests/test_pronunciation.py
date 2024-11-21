from rabot.cogs.pronunciation.pronunciation import get_pronunciation
from rabot.exceptions import NotFoundError
from rabot.utils import fix_greek_spelling


def test_existing_pronunciation() -> None:
    word = "ευχαριστώ"
    message, _ = get_pronunciation(word)
    assert message == "Word: ευχαριστώ\nIPA: ef.xa.ɾiˈsto\n"


def test_non_existing_pronunciation() -> None:
    word = "μπλαμπλα"
    try:
        get_pronunciation(word)
        assert False, "Expected NotFoundException but no exception was raised."
    except NotFoundError:
        pass  # Test passes if NotFoundException is raised
    except Exception as e:
        assert False, f"Expected NotFoundException but got {type(e).__name__}"


def test_retry_pronunciation() -> None:
    word = "ευχαριστω"
    try:
        get_pronunciation(word)
        assert False, "Should fail the first time"
    except NotFoundError:
        word = fix_greek_spelling(word)
        message, _ = get_pronunciation(word)
        assert message == "Word: ευχαριστώ\nIPA: ef.xa.ɾiˈsto\n"
