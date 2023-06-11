#!/usr/bin/python
# -*- coding: utf-8 -*-
# wordle_bot.py
# Author: Petter J. Barhaugen <petter@petternett.no>

import discord
from discord.ext import commands
import random
from datetime import datetime, timedelta
import re

# Local imports
import secret
from converts import convert_grid
from processes import update_streaks, print_stats, catchup, parse_result

# TODO LIST:
# * Persistent storage in db
# * Details of user (!wordle <user>):
#   * Date of user's first game played
#   * User's longest streak
#   * Other stuff?
# * Hard mode counter (hard mode streak?)
# * Who posts earliest on average?
# * Who has the best starter word? (Grid analysis)
# * Fair overall game score
#   * Bayesian average?
#   * Disqualify when significantly less games?

CMD_PREFIX = '!'

# Discord.py setup
intents = discord.Intents(messages=True, message_content=True, guilds=True)
bot = commands.Bot(command_prefix=CMD_PREFIX, intents=intents)

random.seed()

# Global list of users
user_dict = {}
# Update after first run
first_run = True


# On ready
@bot.event
async def on_ready():
    print(f"wordle_bot is ready!")


# On !wordle command
@bot.command()
async def wordle(ctx, arg=None):
    global first_run

    if first_run:
        await catchup(ctx.channel, user_dict)
        first_run = False

    await print_stats(ctx.channel, user_dict, bot)


# On message
@bot.event
async def on_message(msg):
    if msg.author == bot.user: return

    # Parse Wordle result
    await parse_result(msg, user_dict)

    # Check for commands
    await bot.process_commands(msg)


bot.run(secret.token)
