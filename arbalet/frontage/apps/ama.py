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
                self.action = 1
                self.rows = 0
                self.cols = 0
                self.coord = (-1,-1)
                self.pixels = {'default' : ((-1,-1), -1)}
                self.pos_unknown = {}

        #get information from frontage-frontend
        def handle_message(self, json_data, path=None) :
                if json_data is None :
                        raise ValueError("Error : empty message received from WebSocket")
                elif isinstance(json_data, str) :
                        data = loads(json_data)
                else :
                        raise ValueError("Incorrect payload value type for AMA Fapp")

                #Format du json {x:int, y:int}
                if (data['x'] != None):
                    x = int(data['x'])
                    y = int(data['y'])
                    self.coord = (x, y)
                elif (data['continue'] != None):
                    self.action = 1
                else :
                    self.action = -1

        #send the color matrix on RabbitMQ to be displayed on the mesh network to address a pixel
        def matriceR(self, ind) :
            self.model.set_all(array((-1,-1,-1)))
            for i in range(ind-1) :
                x = i / self.cols
                y = i % self.cols
                self.model.set_pixel(x, y, name_to_rgb('green'))
            x = ind / self.cols
            y = ind % self.cols
            self.model.set_pixel(x, y, name_to_rgb('red'))
            self.model.send()

        #send the color matrix on RabbitMQ to be displayed on the mesh network to confirm the pixel address
        def matriceG(self, ind) :
                self.model.set_all('black')
                for (i, j) in self.addressed :
                        self.model.set_pixel(i, j, name_to_rgb('green'))
                self.model.send()

        def update(self) :
            Websock.send_pixels(self.pixels)
            Websock.send_pos_unk({})
            #Update DB
            while (len(self.pixels) != 0) :
                (mac, ((x,y),ind)) = self.pixels.popitem()
                add_cell(x, y, mac)

        def run(self, params, expires_at=None) :
                # get necessary informations (may be shift in __init__ ?)
                self.rows = SchedulerState.get_rows()
                self.cols = SchedulerState.get_cols()
                self.pos_unknown = Websock.get_pos_unk() #Exemple {'@mac1' : ((x,j), 0), ...}}
                print(self.pos_unknown) #dummy print
                #Tels mesh.py to shift in AMA mod
                self.model.set_all(array((-1, -1, -1)))
                self.model.send()
                #Start the AMA procedure
                while (len(self.pos_unknown) != 0) : #AMA shall continue as long as there are pixels without known position
                    if self.action == 1 : #the previous pixel has its right position
                        (mac, ((x,y),ind)) = self.pos_unknown.popitem()
                    else : #the previous position was hill initialize
                        self.pixels.pop(mac)
                    self.matriceR(ind)
                    while (!(self.coord in [val[0] for val in self.pixels.values()])): #wait for the administrator to gives the coordonates
                        continue
                    # tmp_coord = self.coord
                    self.pixels[mac]=(self.coord, ind) #update of the local dictionary
                    self.matriceG(ind)
                    self.action = 0
                    while self.action == 0 : #wait for the confirmation of the administrator
                        continue
                    if action == 1 : #administrator ensures the rightfullness of the coordonate
                        self.update(mac, self.coord, ind) #I think we should wait for the end to do that
                    else : # the pixel is reput in the pos_unknown dictionary as its position is false
                        self.pos_unknown[mac] = ((x,y), ind)
                #Start the up right verification
                for i in range(self.rows) :
                    for j in range(self.cols) :
                        self.model.set_pixel(i, j, name_to_rgb('red'))
                        self.model.send()
                        sleep(0.1)
                self.update() #publish on REDIS and save in DB the new pixels dictionary
                #Tels mesh.py to shift in COLOR mod
                self.model.set_all(array((-1, -1, -1)))
                self.model.send()
