#!/usr/bin/env python
"""
Presentation
"""

import time

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

from server.flaskutils import print_flush

class Ama(Fap) :
        PLAYABLE = True
        ACTIVATED = True
        PARAMS_LIST = {'uapp': ['true',
                                'false']}

        def __init__(self, username, userid) :
                Fap.__init__(self, username, userid)
                self.action = 1
                self.rows = 0
                self.cols = 0
                self.coord = (-1,-1)
                # self.pixels = SchedulerState.get_pixels_dic()
                self.pixels = {'default' : ((-1,-1), -1) }
                self.pos_unknown = {}
                self.deco = {}

        #get information from frontage-frontend
        def handle_message(self, json_data, path=None) :
            print_flush(json_data)
            if json_data is None :
                    raise ValueError("Error : empty message received from WebSocket")
            elif isinstance(json_data, str) :
                    data = loads(json_data)
            else :
                    raise ValueError("Incorrect payload value type for AMA Fapp")

            #Format du json {x:int, y:int}
            if (data.get('x') != None):
                    x = int(data['x'])
                    y = int(data['y'])
                    self.coord = (y, x)#En vertu des lois de traitement d'image, VTTA RPZ!
            elif (data.get('action') != None):
                    self.action = data.get('action')
            else :
                    print_flush("Received unknown message from frontend")

        #send the color matrix on RabbitMQ to be displayed on the mesh network to address a pixel
        def matriceR(self, ind, iteration) :
            print_flush("entrée dans matriceR........................................")
            self.model.set_all(array((-1,-1,-1)))
            for i in [val[1] for val in self.pixels.values()] :
                if i == -1 :
                    continue
                x = int(i / self.cols)
                y = i % self.cols
                self.model.set_pixel(x, y, name_to_rgb('lime'))
            x = int(ind / self.cols)
            y = ind % self.cols
            self.model.set_pixel(x, y, name_to_rgb('red'))
            self.send_model()
            print_flush("sortie de matriceR..............................................")

        #send the color matrix on RabbitMQ to be displayed on the mesh network to confirm the pixel address
        def matriceG(self, ind) :
            print_flush("entrée dans matriceG........................................")
            self.model.set_all('black')
            for (i,j) in [(val[0][0],val[0][1]) for val in self.pixels.values()]  :
                if (i != -1 and j != -1) :
                    self.model.set_pixel(i, j, name_to_rgb('lime'))
            self.send_model()
            print_flush("sortie de matriceG........................................")
            print_flush(self.model)

        def update(self) :
            Websock.send_pos_unk(self.pos_unknown)
            default = self.pixels.pop('default')
            print_flush(self.pixels)
            Websock.send_pixels(self.pixels)
            if default :
                self.pixels['default'] = default

        def update_DB(self) :
            self.pixels.pop('default')
            Websock.send_pixels(self.pixels)
            Websock.send_pos_unk({})
            Websock.send_deco(self.deco)
            Websock.send_get_deco()
            #Update DB
            if (self.params['uapp'] == 'true') :
                SchedulerState.drop_dic()
                print_flush("Database cleaned")
            while (len(self.pixels) != 0) :
                (mac, ((x,y),ind)) = self.pixels.popitem()
                SchedulerState.add_cell(x, y, mac, ind)
            print_flush("Database updated")

        def skip_procedure(self):
            for key in self.pos_unknown.keys :
                value = self.pos_unknown[key]
                pixel = self.pixels.get(key)
                if pixel is None :
                    print_flush("ERROR : using skip is not possible")
                else :
                    pixel[1] = value[1]
                    self.pixels[key] = pixel
                    self.pos_unknown.popitem(key)
            Websock.send_pos_unk(self.pos_unknown)
            Websock.send_pixels(self.pixels)

        def wait_to_be_kill(self):
            self.model.set_all('black')
            self.send_model()
            while True:
                print_flush("Addressing is over...")
                time.sleep(0.05)

        def visual_verification(self):
            print_flush(SchedulerState.get_pixels_dic())
            for i in range(self.rows) :
                for j in range(self.cols) :
                    self.model.set_pixel(i, j, name_to_rgb('red'))
                    waiting = 0
                    while waiting < 10 :
                        self.send_model()
                        time.sleep(0.1)
                        waiting += 1

        def addressing_procedure(self):
            iteration = 1
            while (len(self.pos_unknown) != 0) :
                #AMA/RaC shall continue as long as there are pixels without known position
                if self.action == 1 :
                    #the previous pixel has its right position
                    (mac, ((x,y),ind)) = self.pos_unknown.popitem()
                    print_flush("je suis rentré dans self.action == 1")
                else :
                    #the previous position was hill initialize
                    self.pixels.pop(mac)
                    self.pos_unknown.pop(mac)
                self.matriceR(ind, iteration)
                Websock.send_ama_model(0)
                print_flush(self.model)
                print_flush("avt la boucle d'attente active............................................................;")
                print_flush([(val[0][0],val[0][1]) for val in self.pixels.values()])
                print_flush(self.coord)
                while ((self.coord in [(val[0][0],val[0][1]) for val in self.pixels.values()])):#This one looks really wrong => bypassed starting loop 2
                    #wait for the administrator to gives the coordonates
                    self.send_model()
                    time.sleep(0.05)
                print_flush("apr la boucle d'attente active............................................................;")
                self.pixels[mac]=(self.coord, ind) #update of the local dictionary
                self.update()
                self.matriceG(ind)
                Websock.send_ama_model(1)
                self.action = 0
                print_flush("boucle avt la confirmation de self.action....................................................;")
                while (self.action == 0):
                    #wait for the confirmation of the administrator
                    self.send_model()
                    time.sleep(0.05)
                    continue
                if self.action == 1 :
                    #administrator ensures the rightfullness of the coordonate
                    iteration += 1
                else : # the pixel is reput in the pos_unknown dictionary as its position is false
                        self.pos_unknown[mac] = ((x,y), ind)

        def reattributing_indexes(sef):
            self.deco = loads(Websock.get_deco())
            for mac in self.pos_unknown.keys() :
                if len(self.deco) > 0 :
                    # dummy security, should do something in the case of it happenning but dunno what (yet)
                    pixel_deco = self.deco.popitem()
                    self.pos_unknown[mac] = ((-1,-1), pixel_deco[1][1])
            self.pixels = loads(Websock.get_pixels())
            self.pixels['default'] = ((-1,-1), -1)

        def run(self, params, expires_at=None) :
            self.start_socket()
            # get necessary informations (may be shift in __init__ ?)
            self.rows = SchedulerState.get_rows()
            self.cols = SchedulerState.get_cols()
            # get the pixels to address
            self.pos_unknown = loads(Websock.get_pos_unk()) #Exemple {'@mac1' : ((x,j), 0), ...}}
            self.params = params
            if (self.params['mode'] == "ama") : # assisted manual addressing : reset the position of all pixels
                Websock.send_pixels({})
            elif (self.params['mode'] == "har") :
                 # hot assisted readdressing : reattribute the unsued frame indexes (get from deconnected pixels) without touching to already addressed pixels
                 self.reattributing_indexes()
                 # TODO : griser les pixels contenus dans self.pixels
            #Put esp root in ADDR or CONF state
            Websock.send_esp_state(0)
            if self.params['mode'] == "skip" :
                self.skip_procedure()
            else :
                self.addressing_procedure()
            #publish on REDIS and save in DB the new pixels dictionary
            self.update_DB()
            #Put ESPs in COLOR state
            Websock.send_esp_state(1)
            self.visual_verification()
            self.wait_to_be_kill()
