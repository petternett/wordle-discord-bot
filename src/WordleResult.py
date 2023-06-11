#!/usr/bin/python
# -*- coding: utf-8 -*-
# WordleResult.py
# Author: Petter J. Barhaugen <petter@petternett.no>


class WordleResult:
    def __init__(self, number: int, tries: int, hard: bool, post_time, grid):
        self.number: int = number
        self.tries:  int = tries
        self.hard:   bool = hard
        self.post_time = post_time
        self.grid = grid
