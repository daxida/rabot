from discord import Embed

FAQS = {
    "default": {
        "alias": [],
        "author": "me",
        "title": "FAQ list",
        "description": """
Available commands are:
`rabot, explain language transfer`
""",
    },
    "language transfer": {
        "alias": [
            "lt",
            "explain language transfer",
            "explain lt",
            "what is language transfer",
            "what is lt",
        ],
        "author": "scarlettparker",
        "title": "What is Language Transfer?",
        "description": """
Language Transfer is an audio series that teaches the basics of Modern Greek in a natural and easy-to-comprehend manner. It focuses on grammar and teaches useful vocabulary to prepare you for everyday conversations.

It's highly encouraged to check it out, as it will help you build a very solid foundation to communicate in Greek.
The complete series can be found on:
- [YouTube](https://www.youtube.com/watch?v=dHsgJkV9J30&list=PLeA5t3dWTWvtWkl4oOV8J9SMB7L9N9Ogt)
- [SoundCloud](https://soundcloud.com/languagetransfer/sets/complete-greek-more-audios)
- [Transcript (PDF)](https://static1.squarespace.com/static/5c69bfa4f4e531370e74fa44/t/5d03d32873f6f10001a364b5/1560531782855/COMPLETE+GREEK+-+Transcripts_LT.pdf)

The audio series follows the teacher (Mihalis) as he teaches a student useful grammatical constructions and how to form sentences naturally, allowing you to follow along by putting yourself in the student’s shoes. More useful resources can be found in [the resources channel](https://discord.com/channels/350234668680871946/359578025228107776/1132288734738522112), notably in the pins, to help you advance your Greek level after Language Transfer.
""",
    },
    "quiz": {
        "alias": [
            "explain quiz",
        ],
        "author": "me",
        "title": "",
        "description": """
Type `k!q DECK`.

Examples:
- `k!q mem5` (Memrise first 5k words by frequency)
- `k!q mem1` (Memrise first 1k words by frequency)
- `k!q apl` (Aorist Passive verbs)
- `k!q aal` (Aorist Active verbs)
- `k!q wd` (Words that appeared in 📅-word-of-the-day channel.
""",
    },
}


def faq_footer(author: str) -> str:
    attribution = f"FAQ courtesy of {author}. "
    if author == "me":
        attribution = ""
    return f"{attribution}Type 'rabot' for the full FAQ list."


def to_embed(faq: dict[str, str]) -> Embed:
    embed = Embed(title=faq["title"], description=faq["description"], color=0x3392FF)
    embed.set_footer(text=faq_footer(faq["author"]))
    return embed


def get_faq(cmd: str) -> Embed:
    for faq_name, info in FAQS.items():
        if cmd in [faq_name] + info["alias"]:
            return to_embed(info)
    return to_embed(FAQS["default"])
