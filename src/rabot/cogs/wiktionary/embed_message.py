import re

import discord

from rabot.cogs.wiktionary.wiktionary import fetch_wiktionary_pos
from rabot.utils import get_language_code


def split_long_text(text: str, max_length: int) -> list[str]:
    """Splits the text into multiple parts if it exceeds max_length."""
    parts = []
    while len(text) > max_length:
        # split at the last newline before the max_length to avoid cutting words mid-sentence
        split_index = text.rfind("\n", 0, max_length)
        if split_index == -1:
            split_index = max_length
        parts.append(text[:split_index])
        text = text[split_index:].lstrip()  # remove leading spaces or newlines
    parts.append(text)
    return parts


async def embed_message(word: str, language: str) -> list[discord.Embed]:
    """Fetches Wiktionary data and returns a list of discord.Embeds with split messages."""
    res = await fetch_wiktionary_pos(word, language)

    lcode = get_language_code(language)

    title = f"∙∙∙∙∙ {word} ∙∙∙∙∙"
    link = f"https://{lcode}.wiktionary.org/wiki/{word}"
    description = ""

    important_keys = [
        "Επίθετο",
        "Adjective",
        "Ουσιαστικό",
        "Noun",
        "Επίρρημα",
        "Adverb",
        "Επιφώνημα",
        "Interjection",
        "Κλιτικός_τύπος_επιθέτου",
        "Κλιτικός_τύπος_ουσιαστικού",
    ]

    format_keys = ["Ετυμολογία", "Etymology", "Προφορά", "Pronunciation"]

    for key in res.keys():
        formatted_key = key.replace("_", " ")
        if language == "english":
            formatted_key = re.sub(r"\s\d+$", "", formatted_key)

        description += f"**{formatted_key}: **\n"

        if any(term in formatted_key for term in important_keys):
            for entry in res[key][1:]:
                description += "> " + str(entry.strip("\n")) + "\n"
        elif any(term in formatted_key for term in format_keys):
            for entry in res[key]:
                description += "∙ " + str(entry.strip("\n")) + "\n"
        else:
            for entry in res[key]:
                description += "> " + str(entry.strip("\n")) + "\n"

    # split the description if it exceeds 2000 characters
    embed_parts = split_long_text(description, 2000)
    embeds = []
    for i, part in enumerate(embed_parts):
        embed = discord.Embed(
            title=f"{title} (Part {i + 1}/{len(embed_parts)})" if len(embed_parts) > 1 else title,
            url=link,
            description=part,
            color=0x3392FF,
        )
        embed.set_footer(text=f"https://forvo.com/word/{word}")
        embeds.append(embed)

    return embeds
