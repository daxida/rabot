from typing import Callable

import discord
import requests
from bs4 import BeautifulSoup

from rabot.log import logger

GREEKLISH = str.maketrans(
    {
        "a": "α",
        "b": "β",
        "c": "σ",  # There's no equivalent for 'c' in Greek, but 'σ' is commonly used
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
        case "english" | "en":
            return "en"
        case "greek" | "el" | "ελληνικά":
            return "el"
        case _:
            raise NotImplementedError(f"Language {language} is not supported")


def greeklish_to_greek(word: str) -> str:
    """Convert greeklish to greek.

    In case of an already greek word, return it unchanged.
    """
    return word.lower().translate(GREEKLISH)


def fix_greek_spelling(word: str) -> str:
    """Fix the spelling of a word.

    Snippet from the wordref script that requests WordReference to get
    the greek accented version of a given word (which can be greeklish
    or a non-accented greek word).
    It can not be imported from the wordref due to circular import.

    Examples:
        * fix_greek_spelling("xara")     => χαρά
        * fix_greek_spelling("χαρα")     => χαρά
        * fix_greek_spelling("χαρά")     => χαρά
        * fix_greek_spelling("nonsense") => nonsense
    """
    greek_word = greeklish_to_greek(word)
    url = f"https://www.wordreference.com/gren/{greek_word}"
    logger.debug(f"GET {url}")
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    try:
        wrd = soup.find("table", {"class": "WRD"})
        fr_wrd = wrd.find("tr", {"class": "even"}).find("td", {"class": "FrWrd"})  # type: ignore
        accented_word = fr_wrd.strong.text.split()[0].strip(",")  # type: ignore
    except Exception:
        accented_word = word

    return accented_word


# https://stackoverflow.com/questions/76247812/how-to-create-pagination-embed-menu-in-discord-py
class Pagination(discord.ui.View):
    def __init__(self, inter: discord.Interaction, get_page: Callable) -> None:
        self.inter = inter
        self.get_page = get_page
        self.total_pages: int = 0
        self.index: int = 1
        super().__init__(timeout=100)

    async def interaction_check(self, inter: discord.Interaction) -> bool:
        if inter.user == self.inter.user:
            return True
        emb = discord.Embed(
            description="Only the author of the command can perform this action.",
            color=16711680,
        )
        await inter.response.send_message(embed=emb, ephemeral=True)
        return False

    async def navigate(self) -> None:
        emb, self.total_pages = await self.get_page(self.index)
        assert self.total_pages > 0

        if self.total_pages == 1:
            await self.inter.response.send_message(embed=emb)
        elif self.total_pages > 1:
            self.update_buttons()
            await self.inter.response.send_message(embed=emb, view=self)

    async def edit_page(self, inter: discord.Interaction) -> None:
        emb, self.total_pages = await self.get_page(self.index)
        self.update_buttons()
        await inter.response.edit_message(embed=emb, view=self)

    def update_buttons(self) -> None:
        if self.index > self.total_pages // 2:
            self.children[2].emoji = "⏮️"
        else:
            self.children[2].emoji = "⏭️"
        self.children[0].disabled = self.index == 1
        self.children[1].disabled = self.index == self.total_pages

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.blurple)
    async def previous(self, inter: discord.Interaction, button: discord.Button) -> None:
        self.index -= 1
        await self.edit_page(inter)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.blurple)
    async def next(self, inter: discord.Interaction, button: discord.Button) -> None:
        self.index += 1
        await self.edit_page(inter)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.blurple)
    async def end(self, interaction: discord.Interaction, button: discord.Button) -> None:
        if self.index <= self.total_pages // 2:
            self.index = self.total_pages
        else:
            self.index = 1
        await self.edit_page(interaction)

    async def on_timeout(self) -> None:
        """Remove buttons on timeout."""
        message = await self.inter.original_response()
        await message.edit(view=None)

    @staticmethod
    def compute_total_pages(total_results: int, results_per_page: int) -> int:
        return ((total_results - 1) // results_per_page) + 1
