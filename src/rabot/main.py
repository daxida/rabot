import discord
from discord import app_commands
from dotenv import dotenv_values
from requests.models import HTTPError

from rabot.exceptions import NotFoundError, RabotError
from rabot.gr_datetime.gr_date import get_full_date
from rabot.help.help import HelpMessage
from rabot.log import logger
from rabot.pronunciation import pronunciation
from rabot.utils import Pagination, fix_greek_spelling
from rabot.wiktionary.embed_message import embed_message as wiktionary_message
from rabot.wiktionary.wiktionary import fetch_conjugation
from rabot.wordref.wordref import Wordref


class MyClient(discord.Client):
    def __init__(self, _intents: discord.Intents) -> None:
        super().__init__(intents=_intents)
        self.synced = False

    async def on_ready(self) -> None:
        await self.wait_until_ready()
        if not self.synced:
            await tree.sync()
            self.synced = True
        logger.success(f"Bot is ready! {self.user}")

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return


intents = discord.Intents.default()
intents.message_content = True
client = MyClient(intents)
tree = app_commands.CommandTree(client)


async def template_command(
    interaction: discord.Interaction,
    word: str | None,
    gr_en: bool,
    hide_words: bool,
    min_sentences_shown: int,
    max_sentences_shown: int,
):
    wordref = Wordref(word, gr_en, hide_words, min_sentences_shown, max_sentences_shown)
    wordref_embed = wordref.fetch_embed()

    # In case of failure, try again once with fixed spelling.
    if wordref_embed is None and word is not None:
        original_word = word
        word = fix_greek_spelling(word)
        logger.info(f"Tried to fix spelling: '{original_word}' to '{word}'")
        wordref = Wordref(word, gr_en, hide_words, min_sentences_shown, max_sentences_shown)
        wordref_embed = wordref.fetch_embed()

    if wordref_embed is None:
        await interaction.response.send_message("The command did not succeed.")
    else:
        await interaction.response.send_message(embed=wordref_embed)
    # try:
    #     wordref = Wordref(word, gr_en, hide_words, amount_sentences_shown)
    #     wordref_embed = wordref.embed()
    #     await interaction.response.send_message(embed=wordref_embed)
    # except Exception as e:
    #     await interaction.response.send_message(content=f"Error: {e}")


# helper function for wiktionary stuff
async def wiktionary_handler(
    interaction: discord.Interaction,
    word: str,
    language: str,
    ephemeral: str = "True",
):
    ephemeral = ephemeral.lower() in ["true", "yes", "1"]
    embeds = await wiktionary_message(word, language)

    await interaction.response.send_message(embed=embeds[0], ephemeral=ephemeral)
    if len(embeds) > 1:
        for embed in embeds[1:]:
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)


@tree.command(name="wiktionary", description="Return the Wiktionary entry for a word")
async def wiktionary(
    interaction: discord.Interaction,
    word: str,
    ephemeral: str = "True",
):
    await wiktionary_handler(interaction, word, language="english", ephemeral=ephemeral)


@tree.command(name="wiktionarygr", description="Return the Wiktionary (Greek) entry for a word")
async def wiktionarygr(
    interaction: discord.Interaction,
    word: str,
    ephemeral: str = "True",
):
    await wiktionary_handler(interaction, word, language="greek", ephemeral=ephemeral)


@tree.command(name="wotdgr", description="Prompts a random Greek word from Wordref")
async def wotdgr(interaction: discord.Interaction):
    await template_command(interaction, None, True, True, 1, 3)


@tree.command(name="wotden", description="Prompts a random english word from Wordref")
async def wotden(interaction: discord.Interaction):
    await template_command(interaction, None, False, True, 1, 3)


@tree.command(name="searchgr", description="Searches the given Greek word in Wordref (supports greeklish)")
async def searchgr(interaction: discord.Interaction, word: str):
    await template_command(interaction, word, True, False, 0, 2)


@tree.command(name="searchen", description="Searches the given english word in Wordref")
async def searchen(interaction: discord.Interaction, word: str):
    await template_command(interaction, word, False, False, 0, 2)


@tree.command(name="helprafa", description="Explains rafabot")
async def helprafa(interaction: discord.Interaction):
    embed = discord.Embed(title="Explains rafabot", description=HelpMessage().message, color=0xFF5733)
    await interaction.response.send_message(embed=embed)


@tree.command(name="date", description="Prompts date in Fidis format")
async def date(interaction: discord.Interaction):
    await interaction.response.send_message(get_full_date())


@tree.command(name="forvo", description="Returns a link with a forvo pronunciation")
async def forvo(interaction: discord.Interaction, word: str):
    # We do not always want to fix the greek spelling because valid words may be
    # modified by the query to `fix_greek_spelling`: ταξίδια => ταξίδι.

    try:
        message, audio_file = pronunciation.get_pronunciation(word)
    except NotFoundError:
        # In case of failure, try again once with fixed spelling.
        word = fix_greek_spelling(word)
        try:
            message, audio_file = pronunciation.get_pronunciation(word)
        except NotFoundError:
            await interaction.response.send_message(f"Could not find the word {word}!")
            return

    file = discord.File(audio_file, filename=f"{word}.mp3")
    await interaction.response.send_message(file=file, content=message)


@tree.command(name="conj", description="Returns the present tense of the verb.")
async def conj(interaction: discord.Interaction, word: str):
    try:
        conjugation = fetch_conjugation(word)
        if conjugation is None:
            prev_word, word = word, fix_greek_spelling(word)
            if prev_word != word:
                conjugation = fetch_conjugation(word)
    except RabotError as e:
        logger.critical(e)
        await interaction.response.send_message(f"Error while fetching conjugation for {word}.")
        return
    except HTTPError as e:
        logger.error(e)
        await interaction.response.send_message(f"Error while fetching conjugation for {word}.")
        return

    if conjugation is None:
        await interaction.response.send_message(f"Could not find conjugation for {word}.")
        return

    url = f"https://el.wiktionary.org/wiki/{word}"
    list_contents = []
    for voice, tense_dict in conjugation.items():
        voice = voice.replace(" φωνή", "")
        for tense, conj in tense_dict.items():
            page = (f"{voice}\n{tense}", "\n".join(conj))
            list_contents.append(page)
    n = len(list_contents)

    async def get_page(page: int):
        verb_tense, conjugation = list_contents[page - 1]
        emb = discord.Embed(title=word, description=f"{verb_tense}\n\n{conjugation}")
        emb.url = url
        # emb.set_author(name=f"Requested by {interaction.user}")
        emb.set_footer(text=f"Page {page} from {n}")
        return emb, n

    await Pagination(interaction, get_page).navigate()


def main() -> None:
    config = dotenv_values(".env")
    token = config["TOKEN"]
    if token is None:
        raise ValueError("Could not find the TOKEN at .env")
    client.run(token)


if __name__ == "__main__":
    main()
