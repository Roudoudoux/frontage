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

        def __init__(self, username, userid) :
                Fap.__init__(self, username, userid)
                self.action = 1
                self.rows = 0
                self.cols = 0
                self.coord = (-1,-1)
                self.pixels = SchedulerState.get_pixels_dic()
                if self.pixels == {} :
                    self.pixels = {'default' : ((-1,-1), -1)}
                self.pos_unknown = {}

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
            print_flush("entrée dans matriceR........................................")
            self.model.set_all(array((-1,-1,-1)))
            for i in range(ind) :
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
            for (i,j) in self.pixels.values()  :
                self.model.set_pixel(i, j, name_to_rgb('lime'))
            self.send_model()
            print_flush("sortie de matriceG........................................")

        def update(self) :
            default = self.pixels.popitem('default')
            Websock.send_pixels(self.pixels)
            if default :
                self.pixels['default'] = default

        def update_DB(self) :
            self.pixels.pop('default')
            Websock.send_pos_unk({})
            Websock.send_pixels(self.pixels)
            #Update DB
            while (len(self.pixels) != 0) :
                (mac, ((x,y),ind)) = self.pixels.popitem()
                add_cell(x, y, mac, ind)

        def run(self, params, expires_at=None) :
            # self.start_socket()
            # get necessary informations (may be shift in __init__ ?)
            self.rows = SchedulerState.get_rows()
            self.cols = SchedulerState.get_cols()
            self.pos_unknown = loads(Websock.get_pos_unk()) #Exemple {'@mac1' : ((x,j), 0), ...}}
            print_flush(self.pos_unknown) #dummy print
            #Tels mesh.py to shift in AMA mod
            print_flush("je change l'etat des esp en ADDR..............................................................;;")
            Websock.send_esp_state('ADDR')
            self.send_model()
            print_flush("Je suis avant la boucle ..................................................................;")
            #Start the AMA procedure
            iteration = 0
            while (len(self.pos_unknown) != 0) :
                #AMA shall continue as long as there are pixels without known position
                if self.action == 1 :
                    #the previous pixel has its right position
                    (mac, ((x,y),ind)) = self.pos_unknown.popitem()
                    print_flush("je suis rentré dans self.action == 1")
                else :
                    #the previous position was hill initialize
                    self.pixels.pop(mac)
                self.matriceR(ind)
                Websock.send_ama_model('0')
                print_flush(self.model)
                print_flush("avt la boucle d'attente active............................................................;")
                print_flush([(val[0][0],val[0][1]) for val in self.pixels.values()])
                while ((self.coord in [(val[0][0],val[0][1]) for val in self.pixels.values()])):#This one looks really wrong => bypassed starting loop 2
                    #wait for the administrator to gives the coordonates
                    self.send_model()
                    wait += 1
                    time.sleep(0.05)
                print_flush("voici la valeur de wait : {0}".format(wait))
                #####################################################
                if wait == 100 and iteration == 0:                  #
                    self.coord = (0,0)                              #
                elif wait == 100 and iteration == 1:                #
                    self.coord = (0,1)                              #
                iteration += 1                                      #
                #####################################################
                print_flush("apr la boucle d'attente active............................................................;")
                # tmp_coord = self.coord
                self.pixels[mac]=(self.coord, ind) #update of the local dictionary
                self.matriceG(ind)
                Websock.send_ama_model('1')
                self.action = 0
                print_flush("boucle avt la confirmation de self.action....................................................;")
                wait = 0
                while (self.action == 0) and wait < 100 :
                    #wait for the confirmation of the administrator
                    wait += 1
                    self.send_model()
                    time.sleep(0.05)
                    continue
                if self.action == 1 : #administrator ensures the rightfullness of the coordonate
                        self.update()
                else : # the pixel is reput in the pos_unknown dictionary as its position is false
                        self.pos_unknown[mac] = ((x,y), ind)
                        #Start the up right verification
                print_flush("WE DID IT!!!!!! One lap completed!!!!!!!!!")
            for i in range(self.rows) :
                for j in range(self.cols) :
                    self.model.set_pixel(i, j, name_to_rgb('red'))
                    self.send_model()
                    time.sleep(0.1)
                    self.update_DB() #publish on REDIS and save in DB the new pixels dictionary
                    #Tels mesh.py to shift in COLOR mod
            Websock.send_esp_state('COLOR')
