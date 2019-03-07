#!/usr/bin/env python
"""

Presentation

"""

from json import loads

from apps.fap import Fap
from apps.actions import Actions
from utils.tools import Rate
from utils.colors import name_to_rgb, rgb_to_hsv, rgb255_to_rgb
from utils.websock import Websock
from scheduler_state import SchedulerState

from db.models import FappModel
from db.base import session_factory
from json import dumps
from numpy import array


class Ama(Fap) :
        PLAYABLE = True
        ACTIVATED = True
        
        def __init__(self, username, userid) :
                Fap.__init__(self, username, userid)
                self.rows = 0
                self.cols = 0
                self.addressed = []

        def handle_message(self, json_data, path=None) :
                if json_data is None :
                        raise ValueError("Error : empty message received from WebSocket")
                elif isinstance(json_data, str) :
                        data = loads(json_data)
                else :
                        raise ValueError("Incorrect payload value type for AMA Fapp")

                #Format du json {x:int, y:int}

                x = int(data['x'])
                y = int(data['y'])
                self.coord = (x, y)
                

        def matriceR(self, ind) :
                self.model.set_all(array((-1, -1, -1)))
                for i in range(ind-1) :
                        x = i / self.cols
                        y = i % self.cols
                        self.model.set_pixel(x, y, name_to_rgb('green'))
                x = ind / self.cols
                y = ind % self.cols
                self.model.set_pixel(x, y, name_to_rgb('red'))
                self.model.send()

        def matriceG(self, ind) :
                while (self.coord == (-1, -1)) :
                        continue
                (x, y) = self.coord
                self.coord = (-1, -1)
                #TODO : Update REDDIS
                add_cell(x, y, card)
                self.addressed.append((x, y))
                self.model.set_all('black')
                for (i, j) in self.addressed :
                        self.model.set_pixel(i, j, name_to_rgb('green'))
                self.model.send()

        def update(self, ind) :
                #Get input from frontend

        def run(self, params, expires_at=None) :
                while (self.rows * self.cols == 0) :
                        self.rows = SchedulerState.get_rows()
                        self.cols = SchedulerState.get_cols()
                self.cards = Websock.get_mac() #Exemple [{'adresse': @mac1}, {'adresse':...}]
                print(self.cards)
                num = len(self.cards)
                ind = 0
                self.model.set_all(array((-1, -1, -1)))
                self.model.send()
                                   
                while (ind < num) :
                        self.matriceR(ind)
                        self.matriceG(ind)
                        self.update(ind)
                        
                
                
