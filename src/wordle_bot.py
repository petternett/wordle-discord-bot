#!/usr/bin/python
# wordle_bot.py
# Author: Petter J. Barhaugen <petter@petternett.no>

import discord
from discord.ext import commands
import random
from datetime import datetime, timedelta
import re
from collections import defaultdict
import emoji  # parse result squares
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # Streak updates
from apscheduler.triggers.cron import CronTrigger            #

import secret


# TODO LIST:
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


# Discord.py setup
TOKEN = secret.token  # Set in secret.py
intents = discord.Intents(messages=True, message_content = True, guilds = True)
bot = discord.Client(intents=intents)

random.seed()
date_format = "%d.%m.%Y %H:%M:%S"
min_date = "01.01.2022 00:00:00"

# Date-number calculation
base_date = "05.03.2022 00:00:00"
base_date_dt = datetime.strptime(base_date, date_format)
base_num  = 259

WORDLE_PATTERN = r"^Wordle\s(?P<num>\d+)\s(?P<tries>[\dX])/\d(?P<hard>[\*])?$"
THREAD_ID = None

# Update after first run
first_run = False

# Global list of users
user_dict = {}
first_run = True


# On ready
@bot.event
async def on_ready():
    print(f"wordle_bot is ready!")


# On message
@bot.event
async def on_message(message):
    global user_dict, first_run

    if message.author == bot.user: return

    # Get current text channel
    text_channel = message.channel

    message_lines = message.content.split("\n")
    header = message_lines[0]
    match = re.search(WORDLE_PATTERN, header)

    # If message is valid Wordle result
    # match[0] = Wordle, match[1] = Number match[2] = tries match[3] = hard
    if match:
        # If user does not exist, create entry
        if message.author.id not in user_dict:
            user_dict.update({message.author.id: User(message.author)})

        # Parse Wordle result
        result = WordleResult(match[1],
                              match[2],
                              match[3],
                              message.created_at,
                              convert_grid(message_lines[2:]))

        # Add result Wordle object to user
        await user_dict[message.author.id].add_result(result)


    # On !wordle command
    if message.content.startswith("!wordle"):

        if first_run:
            await catchup(text_channel)

        await print_stats(text_channel)


# Convert message lines to grid
# TODO: Experimental. check that this works
def convert_grid(message_lines):
    # Initalize 2D array with 0's
    res  = [ [0]*3 for i in range(3) ]

    for i, line in enumerate(message_lines):
        for j, char in enumerate(line):
            if char is emoji.emojize(":black_large_square:") or \
               char is emoji.emojize(":white_large_square:"):
                res[i][j] = 0
            if char is emoji.emojize(":yellow_square:"):
                res[i][j] = 1
            if char is emoji.emojize(":green_square"):
                res[i][j] = 2

    return res



"""
Time-Wordle number calculation functions
"""
async def num_to_date(number):
    delta = number - base_num
    ret = base_date_dt + timedelta(days=delta)

    return ret.date()


async def date_to_num(date_arg=datetime.today()):
    return base_num + int((date_arg - base_date_dt).days)




"""
Check if users' streaks are broken and set played_today for each user to False.
Is run every day at 00:00:00.
"""
async def update_streaks():
    global user_dict

    yesterday_num = await date_to_num() - 1

    for user in user_dict.values():
        if user.get_last_result().number != yesterday_num:
            print(f"update_streaks(): yesterday_num: {yesterday_num}, user {user.author.id} last result: {user.get_last_result().number}")
            user.streak = 0

        # Checked in add_result
        user.played_today = False
        print(f"set user {user.author.id} played_today to False")


# Print stats
async def print_stats(text_channel):

    # Avg_dict: {uid: avg score}
    avg_dict = defaultdict(float)

    # Calculate average guesses. Also, get the longest display name for formatting.
    lname_len = 0
    for user in user_dict.values():
        if len(user.author.display_name) > lname_len: lname_len = len(user.author.display_name)
        avg = i = 0
        for result in user.results:
            if result.tries != 'X':
                avg += int(result.tries)
                i += 1


        # Calculate average guesses and insert into dict
        avg_dict[user.author.id] = avg / i

        # DEBUG
        # print(f"{user.author.display_name} - average score: {avg/i:.2f}, out of {len(user.results)} games")


    # Sort dict of average scores by lowest
    sorted_avg    = sorted(avg_dict.items(), key=lambda item: item[1])
    sorted_streak = sorted(user_dict.values(), key=lambda item: item.cur_streak, reverse=True)


    # Create Embed
    stats = discord.Embed(title="Wordle Stats", color=discord.Color.green())

    # Least average guesses
    # avg_rank_str = '\n'.join([str(rank) for rank in range(1, len(sorted_avg)+1)])
    avg_user_str = '\n'.join([(await bot.fetch_user(score[0])).display_name for score in sorted_avg])
    avg_str      = '\n'.join([f"{score[1]:.2f}" for score in sorted_avg])

    # stats.add_field(name="Rank", value=avg_rank_str, inline=True)
    stats.add_field(name="User", value=avg_user_str, inline=True)
    stats.add_field(name="Avg. guesses", value=avg_str, inline=True)

    stats.add_field(name='\u200B', value='\u200B', inline=False)

    # Streaks
    # streak_rank_str = '\n'.join([str(rank) for rank in range(1, len(sorted_streak)+1)])
    streak_user_str = '\n'.join([(user.author).display_name for user in sorted_streak])
    streak_str      = '\n'.join([str(user.cur_streak) for user in sorted_streak])
    
    # stats.add_field(name="Rank", value=streak_rank_str, inline=True)
    stats.add_field(name="User", value=streak_user_str, inline=True)
    stats.add_field(name="Streak", value=streak_str, inline=True)


    # avg_tries: [user, avg_tries]
    str_bld = "Least average guesses:\n"
    for rank, avg_tries in enumerate(sorted_avg, start=1):

        # Console
        user = await bot.fetch_user(avg_tries[0])
        str_bld += f"\t{rank}. {user.display_name:<{lname_len}}  {avg_tries[1]:.2f}"
        if rank == 1:
            str_bld += emoji.emojize(" :crown:")
        str_bld += "\n"



    str_bld += "\nLongest current streak:\n"
    for rank, user in enumerate(sorted_streak, start=1):
        str_bld += f"\t{rank}. {user.author.display_name:<{lname_len}}  {user.cur_streak} ({user.total_games} total games)"
        if rank == 1:
            str_bld += emoji.emojize(" :crown:")
        str_bld += "\n"

    print(str_bld)
    await text_channel.send(embed=stats)
    # await text_channel.send(str_bld)



"""
- Store all messages made after timestamp.
- Create User instances and store them in user_dict.
- Update each user's played_today if they have.
- Set the appropriate streak for each user.
"""
async def catchup(text_channel):
    global user_dict, first_run, scheduler

    print(f"Catching up in channel/thread {text_channel.name}")

    # Catch up
    start_date = datetime.strptime(min_date, date_format)
    async for message in text_channel.history(limit=None, after=start_date):

        message_lines = message.content.split("\n")
        header = message_lines[0]
        match = re.search(WORDLE_PATTERN, header)

        # If message is valid Wordle result
        # match[0] = Wordle, match[1] = Number, match[2] = tries, match[3] = hard
        if match:
            # If user does not exist, create entry
            if message.author.id not in user_dict:
                user_dict.update({message.author.id: User(message.author)})

            # Parse Wordle result
            result = WordleResult(match[1],
                                  match[2],
                                  match[3],
                                  message.created_at,
                                  convert_grid(message_lines[2:]))

            # Add result Wordle object to user
            await user_dict[message.author.id].add_result(result)

    # Update user played_today if they have
    for user in user_dict.values():
        if user.get_last_result().number == await date_to_num():
            user.played_today = True

    # Set appropriate streak
    for user in user_dict.values():
        # Start with either today or yesterday's number
        # Then go backwards and check for streak breaks

        # DEBUG
        # print("result list: ", end="")
        # for result in reversed(user.results):
        #     print(f"{result.number}", end=", ")
        # print()

        today_num = await date_to_num()
        cur_num = today_num
        cur_streak = 0
        last_result = user.get_last_result()

        # If played valid game today
        if (int(last_result.number) == today_num and last_result.tries != 'X'):
            # print(f"Valid game today: {last_result.number} matches {today_num}")
            cur_streak += 1
        else:
            cur_num -= 1

        # Check each day from yesterday for valid games
        for result in reversed(user.results):

            # Skip today
            if (int(result.number) == today_num):
                # print(f"skipping today, result num: {result.number}, cur num: {cur_num}")
                cur_num -= 1
                continue

            # If played a valid game this cur_num
            if (int(result.number) == cur_num and result.tries != 'X'):
                # print(f"Valid game: {result.number} matches {cur_num}")
                cur_num -= 1
                cur_streak += 1
                continue

            else:
                # print(f"Invalid game: result's {result.number} does not match current number {cur_num} or result is X ({result.tries})")
                break


        # Set streak in User object
        user.cur_streak = cur_streak
        # print(f"Catchup(): Set streak to {cur_streak} ({user.cur_streak}) for user {user.author.display_name}.\n")


    print(f"All caught up in {text_channel.name}\n")

    # Start streak update scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(update_streaks, CronTrigger(minute=0, hour=0))
    scheduler.start()

    first_run = False


"""
Stores a discord.py Author object,
along with a list of Wordle results and the current streak of the user
"""
class User:

    def __init__(self, author):
        self.author = author
        self.results = []  # [WordleResult]
        self.played_today = False
        self.cur_streak = 0
        self.total_games = 0
        self.streaks = []
        # latest wordle num = results[len(results)-1].number

    # Sorts new result into list
    async def add_result(self, result):
        global user_dict

        # Add result, increment streak and update played_today
        # (if not already done so today)
        if self.played_today is False:

            self.results.append(result)
            self.total_games += 1

            # DEBUG
            # print(f"Added result with num {result.number} to results for user {self.author.display_name}.")
            # for result in self.results:
            #     print(f"{result.number}", end=", ")
            # print("\n")

            self.results.sort(key=lambda x: x.number)
            today_num = await date_to_num()

            # Break streak if result is X
            if result.tries == 'X':
                user_dict[self.author.id].cur_streak = 0
                # TODO count all of user's streaks
                # user_dict[self.author.id].streaks
            else:
                user_dict[self.author.id].cur_streak += 1

            # Update played today
            if (int(result.number) == int(today_num)):
                self.played_today = True


    def get_last_result(self):
        return self.results[len(self.results)-1]


class WordleResult:
    def __init__(self, number, tries, hard, post_time, grid):
        self.number = number
        self.tries = tries
        self.hard = hard
        self.post_time = post_time
        self.grid = grid


# Run bot
bot.run(TOKEN)
