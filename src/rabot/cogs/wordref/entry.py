import pprint
import urllib
import urllib.parse
from dataclasses import dataclass

import discord

from rabot.cogs.wordref.longest import highlight_synonyms
from rabot.log import logger


@dataclass
class Entry:
    """Container class where the suitability logic and formatting is done."""

    link: str
    gr_word: str
    gr_en: bool
    hide_words: bool
    min_sentences_shown: int
    max_sentences_shown: int
    is_random: bool

    def __post_init__(self) -> None:
        """Extra attributes that we want to init separatedly."""
        self.en_word: str | None = None
        self.gr_synonyms: set[str] = set()
        self.en_synonyms: set[str] = set()
        self.sentences: list[tuple[str, str]] = []
        self.gr_pos: str | None = None  # Parts of speech
        self.embed: discord.Embed | None = None

    @property
    def is_valid_entry(self) -> bool:
        word = self.gr_word

        if not self.link:
            logger.warning(f"Could not find the link for {word}.")
            return False
        if not self.gr_word:
            logger.warning(f"Could not find the greek word for {word}.")
            return False
        if not self.en_word:
            logger.warning(f"Could not find the english word for {word}.")
            return False
        if not self.gr_synonyms:
            logger.warning(f"Could not find a greek synonym for {word}.")
            return False
        if not self.en_synonyms:
            logger.warning(f"Could not find an english synonym for {word}.")
            return False
        if not len(self.sentences) >= self.min_sentences_shown:
            logger.warning(f"Could not find enough sentences ({self.min_sentences_shown}) for {word}.")
            return False

        if not self.gr_pos:
            logger.warning(f"Could not find POS for {word}.")

        return True

    @property
    def is_valid_embed(self) -> bool:
        assert self.embed

        # To prevent Discord message length error:
        # HTTPException: 400 Bad Request (error code: 40060)
        if len(self.embed) >= 2000:
            return False

        return True

    def sort_sentences_by_contains_word(self) -> None:
        self.sentences = list(self.sentences)
        if self.gr_en:
            self.sentences.sort(key=lambda pair: self.gr_word in pair[0], reverse=True)
        else:
            self.sentences.sort(key=lambda pair: self.en_word in pair[0], reverse=True)

    def debug(self) -> None:
        """Stringifies the entry in a debug format"""
        print()
        print("#" * 70)

        # Some sortings for easier reading (CARE IT CHANGES THE SET TO LIST).
        sorted_gr_synonyms = sorted(self.gr_synonyms)
        sorted_en_synonyms = sorted(self.en_synonyms)
        self.sentences = sorted(self.sentences)

        msg = "\n"
        msg += f"{self.link}\n"
        msg += "\n"
        msg += f"Greek word: --------- {self.gr_word}\n"
        msg += f"English word: ------- {self.en_word}\n"
        msg += f"POS: ---------------- {self.gr_pos}\n"
        msg += "\n"
        msg += f"Greek synonyms: ----- {sorted_gr_synonyms}\n"
        msg += f"English synonyms: --- {sorted_en_synonyms}\n"
        msg += "\n"
        for idx, (gsen, esen) in enumerate(self.sentences):
            if idx >= self.max_sentences_shown:
                break
            msg += f"> {idx + 1}: {gsen}\n"
            msg += f"> {idx + 1}: {highlight_synonyms(gsen, self.gr_synonyms)}\n"
            msg += f"> {idx + 1}: {esen}\n"
            msg += f"> {idx + 1}: {highlight_synonyms(esen, self.en_synonyms)}\n"

        print(f"\033[33m{msg}\033[0m")

        # Open the link in a new tab
        open_website = False
        if open_website:
            clean_link = self.link.replace("https://", "")
            encoded_url = urllib.parse.quote(f"{clean_link}")
            # webbrowser.open_new(f"https://{encoded_url}")
            print(f"https://{encoded_url}")

    def get_embed(
        self,
        show_pos=True,
        show_translations=True,
        show_synonyms=False,
        show_sentences=True,
        show_footer=True,
    ) -> discord.Embed:
        """Convert the entry into a Discord embed.

        https://plainenglish.io/blog/send-an-embed-with-a-discord-bot-in-python
        """
        # self.debug()

        if self.gr_en:
            pos = f" - *{self.gr_pos}*" if self.gr_pos else ""
        else:
            # Swap gr and en
            self.gr_word, self.en_word = self.en_word, self.gr_word
            self.sentences = [(esen, gsen) for gsen, esen in self.sentences]
            pos = ""

        if not show_pos:
            pos = ""

        # title
        title = f"∙∙∙∙∙ {self.gr_word}{pos} ∙∙∙∙∙"

        # descprition formatting
        sep = "||" if self.hide_words else ""

        # translations
        translations = f"**Translations:** {sep}{self.en_word}{sep}\n"

        # synonyms (Wordreference structure for this is irregular.)
        amount_synonyms_shown = 2
        synonyms_lst = list(self.gr_synonyms - {self.gr_word})
        # Prefer synonyms witn no spaces
        synonyms_lst.sort(key=lambda s: " " in s)
        synonyms_lst = synonyms_lst[:amount_synonyms_shown]
        synonyms_str = ", ".join(synonyms_lst)
        synonyms = "**Synonyms: **"
        synonyms += f"{sep}{synonyms_str}{sep}\n"

        # sentences
        self.sort_sentences_by_contains_word()
        sentences = "**Sentences:**\n"
        # We can't write "> {idx}." with a dot because Discord will overwrite the indexes.
        for idx, (gsen, esen) in enumerate(self.sentences):
            if idx >= self.max_sentences_shown:
                break
            sentences += f"> {idx + 1}: {highlight_synonyms(gsen, self.gr_synonyms)}\n"
            sentences += f"> {idx + 1}: {sep}{highlight_synonyms(esen, self.en_synonyms)}{sep}\n"

        description = ""
        if show_translations:
            description += translations
        if show_synonyms and synonyms != "**Synonyms:**":
            description += synonyms
        if show_sentences and sentences != "**Sentences:**\n":
            description += sentences

        embed = discord.Embed(
            title=title,
            url=f"{self.link}",
            description=description,
            color=0xFF5733,
        )

        if show_footer:
            # NOTE: add forvo here?
            footer = ""
            footer += f"https://forvo.com/word/{self.gr_word}/#el"
            embed.set_footer(text=footer)

        return embed

    def add_embed(
        self,
        show_pos=True,
        show_translations=True,
        show_synonyms=False,
        show_sentences=True,
        show_footer=True,
    ) -> None:
        """Get and store the embed to avoid repeated calls."""
        self.embed = self.get_embed(
            show_pos,
            show_translations,
            show_synonyms,
            show_sentences,
            show_footer,
        )

    def __str__(self) -> str:
        return pprint.pformat(vars(self), indent=1)
