#!/usr/bin/python
# -*- coding: utf-8 -*-
# User.py
# Author: Petter J. Barhaugen <petter@petternett.no>

import discord
from datetime import date

## Local imports
from converts import date_to_num
from WordleResult import WordleResult


"""
Stores a discord.py Author object,
along with a list of Wordle results and the current streak of the user
"""
class User:
    def __init__(self, author):
        self.author = author
        self.results: [WordleResult] = []
        self.played_nums: [int] = []
        self.last_played: int | None = None
        self.cur_streak = 0
        self.total_games = 0
        self.streaks = []
        # latest wordle num = results[len(results)-1].number

    # Sorts new result into list
    async def add_result(self, result: WordleResult):

        today_num = await date_to_num()
        if result.number > today_num:
            print(f"Invalid Wordle number: {result.number}. Newest number is {today_num}. This might be due to a time zone related error.")
            return

        # If not already played that day and not in the future
        if result.number not in self.played_nums:
            self.results.append(result)
            self.results.sort(key=lambda x: x.number)

            # If result was from today, update streak
            if result.number == today_num:
                # Break streak if result is X
                if result.tries == 'X':
                    self.cur_streak = 0
                else:
                    self.cur_streak += 1

            # Update played numbers and last played
            self.total_games += 1
            self.played_nums.append(result.number)
            if not self.last_played or result.number > self.last_played:
                self.last_played = result.number


    def get_last_result(self):
        return self.results[len(self.results)-1]
