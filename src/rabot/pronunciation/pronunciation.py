import io

from rabot.pronunciation import forvo, wiktionary


def get_pronunciation(word: str) -> tuple[str, io.BytesIO]:
    message = f"Word: {word}\n"

    _ipa_link, ipa_pronunciation = wiktionary.get_wiktionary_ipa(word)
    if ipa_pronunciation:
        message += f"IPA: {ipa_pronunciation}\n"

    audio_file = forvo.get_forvo_pronunciation_audio(word)

    return message, audio_file
