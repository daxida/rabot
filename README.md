Discord bot for learning greek at the [greek server](https://discord.gg/greek).

## How to use

First of all, you will need a discord bot. For how to set it up you can check the documentation [here](https://discordpy.readthedocs.io/en/stable/discord.html).

1. (Optional) Create a virtual environment `python3 -m venv venv` and activate it.
2. Install with: `pip install -e .` or `pip install -e .[dev]` for developping.
3. Get your TOKEN from [here](https://discord.com/developers/applications).
4. Create a `.env` file in the root directory with the following format: `TOKEN="Mytoken"`.
5. Launch the bot with `rabot`.

## Notes
The formatting is done with `ruff`. If you want to contribute, it will be appreciated if you could run `ruff format` and `ruff check` prior to committing.