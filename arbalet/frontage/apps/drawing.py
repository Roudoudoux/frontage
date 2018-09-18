#!/usr/bin/env python
"""
    Copyright 2018:
        Bastien Meunier
    License: GPL version 3 http://www.gnu.org/licenses/gpl.html

    Arbalet - ARduino-BAsed LEd Table
    Copyright 2015 Yoan Mollard - Arbalet project - http://github.com/arbalet-project
    License: GPL version 3 http://www.gnu.org/licenses/gpl.html
"""
import random
from json import loads

from apps.fap import Fap
from apps.actions import Actions
from utils.tools import Rate
from utils.colors import name_to_rgb, rgb_to_hsv, rgb255_to_rgb

class Drawing(Fap):

    def __init__(self, username, userid):
        self.rate = Rate(2)
        Fap.__init__(self, username, userid)

    def handle_message(self, json_data, path=None): # noqa
        if json_data is None:
            raise ValueError("Error : message received on websocket is empty.")
        elif isinstance(json_data, str):
            data = loads(json_data)
        else:
            raise ValueError("Incorrect payload value type for Drawing Fapp")

        pixel = data['pixel']
        color = data['color']

        assert(isinstance(pixel['x'], int))
        assert(isinstance(pixel['y'], int))
        assert(isinstance(color['red'], int) and 0 <= color['red'] <= 255)
        assert(isinstance(color['green'], int) and 0 <= color['green'] <= 255)
        assert(isinstance(color['blue'], int) and 0 <= color['blue'] <= 255)

        self.model.set_pixel(pixel['x'], pixel['y'], rgb255_to_rgb(color['red'], color['green'], color['blue']))


    def run(self, params, expires_at=None):
        self.start_socket()
        while True:
            self.send_model()
            self.rate.sleep()

