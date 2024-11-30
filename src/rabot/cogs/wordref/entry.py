import pprint
from dataclasses import dataclass

import discord

from rabot.cogs.wordref.longest import highlight_synonyms
from rabot.log import logger


@dataclass
class DictEntryItem:
    fr_words: list[str]
    to_words: list[str]
    fr_exs: list[str]
    to_exs: list[str]

    @property
    def is_valid(self) -> bool:
        return all(len(x) > 0 for x in [self.fr_words, self.to_words, self.fr_exs, self.to_exs])

    def invert(self) -> None:
        self.fr_words, self.to_words = self.to_words, self.fr_words
        self.fr_exs, self.to_exs = self.to_exs, self.fr_exs


@dataclass
class DictEntry:
    word: str
    gr_en: bool
    url: str | None
    items: list[DictEntryItem]

    @property
    def is_valid_entry(self) -> bool:
        # We must have at least one item
        return any(item.is_valid for item in self.items)

    def __str__(self) -> str:
        return pprint.pformat(vars(self), indent=1)


def fmt_dict_entry_item(
    word: str,
    de_item: DictEntryItem,
    *,
    hide_words: bool = False,
) -> dict[str, str | bool]:
    sep = "||" if hide_words else ""

    fr_exs_fmted = highlight_synonyms(
        "- " + "\n".join(de_item.fr_exs),
        set(de_item.fr_words),
    )
    to_exs_fmted = highlight_synonyms(
        "\n".join(de_item.to_exs),
        set(de_item.to_words),
    )
    sentences = f"{fr_exs_fmted}\n{sep}_{to_exs_fmted}_{sep}"

    fr_synonyms = list(set(de_item.fr_words) - {word})
    if fr_synonyms:
        name = f"{sep}{de_item.to_words[0]} (~{fr_synonyms[0]}){sep}"
    else:
        name = f"{sep}{de_item.to_words[0]}{sep}"

    return dict(
        name=f"> {name}",
        value=sentences,
        inline=False,
    )


def fmt_dict_entry(
    de: DictEntry,
    *,
    hide_words: bool = False,
    max_sentences_shown: int = 2,
) -> discord.Embed:
    """Convert the entry into a Discord embed.

    https://plainenglish.io/blog/send-an-embed-with-a-discord-bot-in-python
    """

    title = f"∙ {de.word} ∙"

    embed = discord.Embed(
        title=title,
        url=de.url,
        color=0xFF5733,
    )

    for de_item in de.items[:max_sentences_shown]:
        field = fmt_dict_entry_item(de.word, de_item, hide_words=hide_words)
        embed.add_field(**field)  # type: ignore

    # May not work with other directions
    # footer = f"http://forvo.com/word/{de.word}/#el"
    # footer = f"[🔊]({footer})"
    # embed.add_field(name="", value=footer, inline=True)

    if len(embed) > 2000:
        logger.warning(f"Too long embed {len(embed)=}")

    return embed
