import json
from typing import Callable

import discord
import requests
from bs4 import BeautifulSoup

from rabot.log import logger


# TODO: Move exceptions to its own file
class NotFoundError(Exception):
    pass


class RabotError(Exception):
    pass


GREEKLISH = str.maketrans(
    {
        "a": "α",
        "b": "β",
        "c": "σ",  # There's no direct equivalent for 'c' in Greek, but 'σ' is commonly used in borrowed words
        "d": "δ",
        "e": "ε",
        "f": "φ",
        "g": "γ",
        "h": "η",
        "i": "ι",
        "j": "τζ",  # The Greek equivalent of 'j' is 'τζ'
        "k": "κ",
        "l": "λ",
        "m": "μ",
        "n": "ν",
        "o": "ο",
        "p": "π",
        "q": "κ",  # Similar to 'k'
        "r": "ρ",
        "s": "σ",
        "t": "τ",
        "u": "υ",
        "v": "β",  # Similar to 'b'
        "w": "ω",
        "x": "χ",
        "y": "υ",
        "z": "ζ",  # The Greek equivalent of 'z' is 'ζ'
    },
)


def is_english(word: str) -> bool:
    return all(ord(ch) < 200 for ch in word)


def get_language_code(language: str) -> str:
    match language:
        case "english":
            return "en"
        case "greek":
            return "el"
        case _:
            raise NotImplementedError(f"Language {language} is not supported")


def print_json(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def greeklish_to_greek_characters(word: str) -> str:
    return word.lower().translate(GREEKLISH)


def fix_greek_spelling(word: str) -> str:
    """Snippet from the wordref script that requests WordReference to get
    the greek accented version of a given word (which can be greeklish
    or a non-accented greek word).

    Examples:
        * fix_greek_spelling("xara")     => χαρά
        * fix_greek_spelling("χαρα")     => χαρά
        * fix_greek_spelling("χαρά")     => χαρά
        * fix_greek_spelling("nonsense") => nonsense

    """
    greek_word_no_accents = greeklish_to_greek_characters(word)
    url = f"https://www.wordreference.com/gren/{greek_word_no_accents}"
    logger.debug(f"GET {url}")
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # TODO: remove dedup (found in wordref::wordref)
    try:
        word = (
            soup.find("table", {"class": "WRD"})
            .find("tr", {"class": "even"})
            .find("td", {"class": "FrWrd"})
            .strong.text.split()[0]
        )
    except Exception:
        pass

    # We have to trim in case of multiple comma separated words. For example:
    # "https://www.wordreference.com/gren/αγαπώ" returns "αγαπάω," (from αγαπάω, αγαπώ)
    word = word.strip(",")

    return word


# https://stackoverflow.com/questions/76247812/how-to-create-pagination-embed-menu-in-discord-py
class Pagination(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, get_page: Callable):
        self.interaction = interaction
        self.get_page = get_page
        self.total_pages: int = 0
        self.index: int = 1
        super().__init__(timeout=100)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.interaction.user:
            return True
        emb = discord.Embed(
            description="Only the author of the command can perform this action.",
            color=16711680,
        )
        await interaction.response.send_message(embed=emb, ephemeral=True)
        return False

    async def navigate(self):
        emb, self.total_pages = await self.get_page(self.index)
        assert self.total_pages > 0

        if self.total_pages == 1:
            await self.interaction.response.send_message(embed=emb)
        elif self.total_pages > 1:
            self.update_buttons()
            await self.interaction.response.send_message(embed=emb, view=self)

    async def edit_page(self, interaction: discord.Interaction):
        emb, self.total_pages = await self.get_page(self.index)
        self.update_buttons()
        await interaction.response.edit_message(embed=emb, view=self)

    def update_buttons(self):
        if self.index > self.total_pages // 2:
            self.children[2].emoji = "⏮️"
        else:
            self.children[2].emoji = "⏭️"
        self.children[0].disabled = self.index == 1
        self.children[1].disabled = self.index == self.total_pages

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.blurple)
    async def previous(self, interaction: discord.Interaction, button: discord.Button):
        self.index -= 1
        await self.edit_page(interaction)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: discord.Button):
        self.index += 1
        await self.edit_page(interaction)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.blurple)
    async def end(self, interaction: discord.Interaction, button: discord.Button):
        if self.index <= self.total_pages // 2:
            self.index = self.total_pages
        else:
            self.index = 1
        await self.edit_page(interaction)

    async def on_timeout(self):
        # remove buttons on timeout
        message = await self.interaction.original_response()
        await message.edit(view=None)

    @staticmethod
    def compute_total_pages(total_results: int, results_per_page: int) -> int:
        return ((total_results - 1) // results_per_page) + 1
