#!/usr/bin/python
# -*- coding: utf-8 -*-
# processes.py
# Author: Petter J. Barhaugen <petter@petternett.no>

import discord
import re
from emoji import emojize
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # Streak updates
from apscheduler.triggers.cron import CronTrigger            #
from collections import defaultdict

## Local imports
from User import User
from WordleResult import WordleResult
from converts import date_to_num, date_format, min_date, convert_grid

WORDLE_PATTERN = r"^Wordle\s(?P<num>\d+)\s(?P<tries>[\dX])/\d(?P<hard>[\*])?$"


"""
Check if users' streaks are broken
Is run every day at 00:00:00.
"""
async def update_streaks(user_dict):

    yesterday_num = await date_to_num() - 1

    for user in user_dict.values():
        if user.get_last_result().number != yesterday_num:
            print(f"update_streaks(): yesterday_num: {yesterday_num}, user {user.author.id} last result: {user.get_last_result().number}")
            user.streak = 0


""" Print statistics.
    Calculates average number of guesses, and longest streak.
    Creates embed and sends to channel/thread.
"""
async def print_stats(text_channel, user_dict, bot):

    # Avg_dict: {UID: avg score}
    avg_dict = defaultdict(float)

    # Calculate average guesses. Also, get the longest display name for formatting.
    for user in user_dict.values():
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
    avg_user_str = f"{emojize(':crown:')} {avg_user_str}"

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

    await text_channel.send(embed=stats)


""" Parse Wordle result.
    Matches with valid Wordle results and adds it to User.
"""
async def parse_result(msg, user_dict):
    
    msg_lines = msg.content.split("\n")
    header = msg_lines[0]
    match = re.search(WORDLE_PATTERN, header)

    # If message is valid Wordle result
    # match[0] = "Wordle"
    # match[1] = number
    # match[2] = no. tries
    # match[3] = hard?
    if match:
        # If user does not exist, create entry
        if msg.author.id not in user_dict:
            user_dict[msg.author.id] = User(msg.author)

        # Parse Wordle result
        hard = bool(match[3])
        result = WordleResult(int(match[1]),
                              int(match[2]),
                              hard,
                              msg.created_at,
                              await convert_grid(msg_lines[2:]))

        # Add result Wordle object to user
        await user_dict[msg.author.id].add_result(result)

""" Catch up when bot is started for the first time:
- Store all messages made after timestamp.
- Create User instances and store them in user_dict.
- Update each user's last played if they have one.
- Set the appropriate streak for each user.
"""
async def catchup(text_channel, user_dict):
    print(f"Catching up in channel/thread {text_channel.name}")

    # Catch up
    start_date = datetime.strptime(min_date, date_format)
    async for msg in text_channel.history(limit=None, after=start_date):
        await parse_result(msg, user_dict)

    # Update user last played if they have one
    for user in user_dict.values():
        if user.get_last_result().number == await date_to_num():
            user.played_today = True

    # Set appropriate streak
    for user in user_dict.values():

        # Start with either today or yesterday's number
        # Then go backwards and check for streak breaks
        today_num = await date_to_num()
        check_num = today_num
        cur_streak = 0
        last_result = user.get_last_result()

        # If played valid game today
        if (int(last_result.number) == today_num and last_result.tries != 'X'):
            # print(f"Valid game today: {last_result.number} matches {today_num}")
            cur_streak += 1
        else:
            check_num -= 1

        # Check each day from yesterday for valid games
        for result in reversed(user.results):

            # Skip today
            if (int(result.number) == today_num):
                # print(f"skipping today, result num: {result.number}, cur num: {check_num}")
                check_num -= 1
                continue

            # If played a valid game this check_num
            if (int(result.number) == check_num and result.tries != 'X'):
                # print(f"Valid game: {result.number} matches {check_num}")
                check_num -= 1
                cur_streak += 1
                continue

            else:
                # print(f"Invalid game: result's {result.number} does not match current number {check_num} or result is X ({result.tries})")
                break

        # Set streak in User object
        user.cur_streak = cur_streak

    print(f"All caught up in {text_channel.name}\n")

    # Start streak update scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: update_streaks(user_dict), CronTrigger(minute=0, hour=0))
    scheduler.start()
