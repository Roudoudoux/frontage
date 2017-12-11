#!/usr/bin/env python
"""
    Copyright 2016:
        Tomas Beati
        Maxime Carere
        Nicolas Verdier
    Copyright 2017:
        + Florian Boudinet
    License: GPL version 3 http://www.gnu.org/licenses/gpl.html

    Arbalet - ARduino-BAsed LEd Table
    Copyright 2015 Yoan Mollard - Arbalet project - http://github.com/arbalet-project
    License: GPL version 3 http://www.gnu.org/licenses/gpl.html
"""
import asyncio
import random
import websockets

from apps.fap import Fap
from apps.actions import Actions
from utils.colors import name_to_rgb


# from arbalet.core import Application, Rate
# import pygame

LEFT = (0, -1)
RIGHT = (0, 1)
DOWN = (1, 0)
UP = (-1, 0)


class Snake(Fap):
    BG_COLOR = 'black'
    PIXEL_COLOR = 'darkred'
    FOOD_COLOR = 'green'

    PLAYABLE = False
    ACTIVATED = True

    PARAMS_LIST = {}

    def __init__(self):
        Fap.__init__(self)

        self.DIRECTION = DOWN
        self.HEAD = (5, 5)
        self.queue = [self.HEAD]
        self.FOOD_POSITIONS = {}
        self.rate = 2
        self.rate_increase = self.args.speed
        self.start_food = self.args.food

    async def handle_message(self, data, path=None): # noqa
        new_dir = None
        if path in [Actions.KEYDOWN, Actions.KEYUP]:
            if data == Actions.K_UP:
                new_dir = UP
            elif data == Actions.K_DOWN:
                new_dir = DOWN
            elif data == Actions.K_RIGHT:
                new_dir = RIGHT
            elif data == Actions.K_LEFT:
                new_dir = LEFT
        elif path == Actions.KEYS:
            if event['key'] == 'up':
                new_dir = UP
            elif event['key'] == 'down':
                new_dir = DOWN
            elif event['key'] == 'right':
                new_dir = RIGHT
            elif event['key'] == 'left':
                new_dir = LEFT

        if new_dir is not None:
            self.DIRECTION = new_dir

    def run(self, params):
        self.start_socket(handle_message)

    def game_over(self):
        print("Game OVER")
        self.model.flash()
        self.model.write("GAME OVER! Score: {}".format(len(self.queue)), 'deeppink')

    def process_extras(self, x=None, y=None):
        pass

    def spawn_food(self, quantity=4):
        for _ in range(0, quantity):
            while True:
                f = (random.randint(0, self.model.height - 1), random.randint(0, self.model.width - 1))
                if f not in self.queue and f not in self.FOOD_POSITIONS:
                    break
            self.FOOD_POSITIONS[f] = True

            self.model.set_pixel(f[0], f[1], self.FOOD_COLOR)

    def run(self):
        rate = Rate(self.rate)

        self.model.set_all(self.BG_COLOR)
        self.model.set_pixel(self.HEAD[0], self.HEAD[1], self.PIXEL_COLOR)
        self.spawn_food(self.start_food)
        for x, y in self.FOOD_POSITIONS:
            self.model.set_pixel(x, y, self.FOOD_COLOR)

        while True:
            rate.sleep_dur = 1.0 / self.rate
            with self.model:
                # No need anymore, thx to asyncio ;)
                # self.process_events()
                new_pos = ((self.HEAD[0] + self.DIRECTION[0]) % self.model.height, (self.HEAD[1] + self.DIRECTION[1]) % self.model.width)
                # check
                if new_pos in self.queue:
                    # Game Over !!
                    break

                self.HEAD = new_pos
                self.model.set_pixel(new_pos[0], new_pos[1], self.PIXEL_COLOR)
                self.queue.append(new_pos)

                if new_pos not in self.FOOD_POSITIONS:
                    x, y = self.queue.pop(0)
                    self.model.set_pixel(x, y, self.BG_COLOR)
                    self.process_extras(x, y)
                else:
                    del self.FOOD_POSITIONS[new_pos]
                    self.spawn_food(1)
                    self.rate += self.rate_increase
                    self.process_extras()
            rate.sleep()
        self.game_over()
        exit()