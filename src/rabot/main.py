import discord
from discord import app_commands
from dotenv import dotenv_values
from requests.models import HTTPError

from rabot.cogs.faqs.faqs import handle_message
from rabot.cogs.fun.gr_datetime.gr_date import get_full_date
from rabot.cogs.pronunciation import pronunciation
from rabot.cogs.wiktionary.embed_message import embed_message as wiktionary_message
from rabot.cogs.wiktionary.wiktionary import fetch_conjugation
from rabot.cogs.wordref.wordref import Wordref
from rabot.exceptions import NotFoundError, RabotError
from rabot.log import logger
from rabot.utils import Pagination, fix_greek_spelling


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

    @staticmethod
    async def try_delete_starting_message(message: discord.Message) -> None:
        """Try to delete the message that prompted a command."""
        permissions = message.channel.permissions_for(message.author)
        if permissions.manage_messages:
            await message.delete()
        else:
            logger.warning("Bot lacks permission to delete messages.")

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return

        response = handle_message(message)
        if response is None:
            return

        if isinstance(response.content, str):
            await message.channel.send(response.content)
        elif isinstance(response.content, discord.Embed):
            await message.channel.send(embed=response.content)
        else:
            raise NotImplementedError

        if response.delete_starting_message:
            await MyClient.try_delete_starting_message(message)


intents = discord.Intents.default()
intents.message_content = True
client = MyClient(intents)
tree = app_commands.CommandTree(client)


async def templ_wordref(
    inter: discord.Interaction,
    word: str | None,
    gr_en: bool,
    hide_words: bool,
    min_sentences_shown: int,
    max_sentences_shown: int = 2,
) -> None:
    """Template for wordref commands."""
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
        await inter.response.send_message("The command did not succeed.")
    else:
        await inter.response.send_message(embed=wordref_embed)
    # try:
    #     wordref = Wordref(word, gr_en, hide_words, amount_sentences_shown)
    #     wordref_embed = wordref.embed()
    #     await inter.response.send_message(embed=wordref_embed)
    # except Exception as e:
    #     await inter.response.send_message(content=f"Error: {e}")


async def templ_wiktionary(
    inter: discord.Interaction, word: str, language: str, *, ephemeral: str = "True"
) -> None:
    """Template for wiktionary commands."""
    eph = ephemeral.lower() in ["true", "yes", "1"]
    embeds = await wiktionary_message(word, language)

    await inter.response.send_message(embed=embeds[0], ephemeral=eph)
    if len(embeds) > 1:
        for embed in embeds[1:]:
            await inter.followup.send(embed=embed, ephemeral=eph)


@tree.command(name="wiktionary", description="Search an English word in Wiktionary")
async def wiktionary(inter: discord.Interaction, word: str, ephemeral: str = "True") -> None:
    await templ_wiktionary(inter, word, language="english", ephemeral=ephemeral)


@tree.command(name="wiktionarygr", description="Search a Greek word in Wiktionary")
async def wiktionarygr(inter: discord.Interaction, word: str, ephemeral: str = "True") -> None:
    await templ_wiktionary(inter, word, language="greek", ephemeral=ephemeral)


@tree.command(name="wotdgr", description="Search a random Greek word in Wordref")
async def wotdgr(inter: discord.Interaction) -> None:
    await templ_wordref(inter, None, True, True, 1)


@tree.command(name="wotden", description="Search a random english word in Wordref")
async def wotden(inter: discord.Interaction) -> None:
    await templ_wordref(inter, None, False, True, 1)


@tree.command(name="searchgr", description="Search a Greek word in Wordref (supports greeklish)")
async def searchgr(inter: discord.Interaction, word: str) -> None:
    await templ_wordref(inter, word, True, False, 0)


@tree.command(name="searchen", description="Search an English word in Wordref")
async def searchen(inter: discord.Interaction, word: str) -> None:
    await templ_wordref(inter, word, False, False, 0)


@tree.command(name="date", description="Prompt date in Fidis format")
async def date(inter: discord.Interaction) -> None:
    await inter.response.send_message(get_full_date())


@tree.command(name="forvo", description="Search a Greek word pronunciation in forvo")
async def forvo(inter: discord.Interaction, word: str) -> None:
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
            await inter.response.send_message(f"Could not find the word {word}!")
            return

    file = discord.File(audio_file, filename=f"{word}.mp3")
    await inter.response.send_message(file=file, content=message)


@tree.command(name="conj", description="Get the present tense of the verb")
async def conj(inter: discord.Interaction, word: str) -> None:
    try:
        conjugation = fetch_conjugation(word)
        if conjugation is None:
            prev_word, word = word, fix_greek_spelling(word)
            if prev_word != word:
                conjugation = fetch_conjugation(word)
    except RabotError as e:
        logger.critical(e)
        await inter.response.send_message(f"Error while fetching conjugation for {word}.")
        return
    except HTTPError as e:
        logger.error(e)
        await inter.response.send_message(f"Error while fetching conjugation for {word}.")
        return

    if conjugation is None:
        await inter.response.send_message(f"Could not find conjugation for {word}.")
        return

    url = f"https://el.wiktionary.org/wiki/{word}"
    list_contents = []
    for voice, tense_dict in conjugation.items():
        voice = voice.replace(" φωνή", "")
        for tense, conj in tense_dict.items():
            page = (f"{voice}\n{tense}", "\n".join(conj))
            list_contents.append(page)
    n = len(list_contents)

    async def get_page(page: int) -> tuple[discord.Embed, int]:
        verb_tense, conjugation = list_contents[page - 1]
        emb = discord.Embed(title=word, description=f"{verb_tense}\n\n{conjugation}")
        emb.url = url
        # emb.set_author(name=f"Requested by {inter.user}")
        emb.set_footer(text=f"Page {page} from {n}")
        return emb, n

    await Pagination(inter, get_page).navigate()


def main() -> None:
    config = dotenv_values(".env")
    token = config["TOKEN"]
    if token is None:
        raise ValueError("Could not find the TOKEN at .env")
    client.run(token)


if __name__ == "__main__":
    main()
