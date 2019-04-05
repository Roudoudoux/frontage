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

from time import sleep

from server.flaskutils import print_flush

class Ama(Fap) :
        PLAYABLE = True
        ACTIVATED = True
        #The F-app has three modes possible
        PARAMS_LIST = {'mode': ['ama', #AMA, or Assisted Manual Addressing, is the classic addressing procedure
                                'rac', #RAC, which is french for HAR, or Hot Assisted Readressing, is the addressing procedure performed to add pixels on the spot
                                'skip']} #Skip allow to retrieve the last addressing registered, and use it again.

        #Initialisation of the class
        def __init__(self, username, userid) :
                Fap.__init__(self, username, userid)
                self.action = 1 #Input regarding the validity of position
                self.rows = 0 #dimensions of the matrix
                self.cols = 0
                self.coord = (-1,-1) #Input from the server : specified pixel
                self.pixels = {'default' : ((-1,-1), -1)} #Fake pixel, to avoid having an empty dictionnary
                self.pos_unknown = {}
                self.deco = {}

        #Event handler function, calls every time a message is received from the Frontend
        def handle_message(self, json_data, path=None) :
            print_flush(json_data)
            #Retrieving and extracting the message
            if json_data is None :
                    raise ValueError("Error : empty message received from WebSocket")
            elif isinstance(json_data, str) :
                    data = loads(json_data)
            else :
                    raise ValueError("Incorrect payload value type for AMA Fapp")

            if (data.get('x') != None): #Coordinates were sent for the pixel
                    x = int(data['x'])
                    y = int(data['y'])
                    self.coord = (y, x) #Updating the pixel coordinate.
            elif (data.get('action') != None): #User specified validity of their input
                    self.action = data.get('action')
            else :
                    print_flush("Received unknown message from frontend")

        #Generate a matrix in 1D array format, and send to RabbitMq to be displayed in order to identify the current card position
        #The cards are ordered according to their position in the routing table (index), and receives either a black (not addressed), green (adressed) or red (currently addressed) pixel color.
        #This 1D array is organized as a 2D array the dimensions of the model to be sent through RabbitMQ, but will be interpreted back later.
        def matriceR(self, ind, iteration) :
            self.model.set_all(array((-1,-1,-1))) #-1 matrix : must be read as a 1D array.
            for i in [val[1] for val in self.pixels.values()] : #Browse all addressed card, and registered their color as green
                if i == -1 :
                    continue
                x = int(i / self.cols) #convert the index to a two dimension position
                y = i % self.cols
                self.model.set_pixel(x, y, name_to_rgb('lime'))
            x = int(ind / self.cols) #Put the current card's color to red.
            y = ind % self.cols
            self.model.set_pixel(x, y, name_to_rgb('red'))
            self.send_model()

        #Generate a verification matrix, and send it through RabbitMQ to check the newly addressed card.
        #This matrix is a regular 2D array, using cards' position, and all addressed cards are green.
        def matriceG(self, ind) :
            self.model.set_all('black')#All cards are shut down
            for (i,j) in [(val[0][0],val[0][1]) for val in self.pixels.values()]  :
                if (i != -1 and j != -1) : #If either is set to -1, the card is not addressed yet.
                    self.model.set_pixel(i, j, name_to_rgb('lime'))#set all addressed cards to Green.
            self.send_model()

        #Notifies the server of modifications on pos_unknown and pixels dictionnaries
        def update(self) :
            Websock.send_pos_unk(self.pos_unknown) #List of pixels to be addressed
            default = self.pixels.pop('default') #As default is a false pixel, it must be removed before sending the array
            #print_flush(self.pixels)
            Websock.send_pixels(self.pixels) #list of addressed pixels
            if default : #if default was removed, it is added again.
                self.pixels['default'] = default

        #Updates the Database : memorize the addressing of the pixels.
        def update_DB(self) :
            if self.pixels.get('default') : #Remove the fake pixel
                self.pixels.pop('default')
            #Updates the server dictionnaries
            Websock.send_pixels(self.pixels)
            Websock.send_pos_unk({})
            Websock.send_deco(self.deco)
            Websock.send_get_deco()
            #Update DB
            if (self.params['mode'] == 'ama' or self.params['mode'] == 'skip') : # in case of initial addressing, the previous configuration is first deleted.
                SchedulerState.drop_dic()
                print_flush("Database cleaned")
            while (len(self.pixels) != 0) : #Pixels are then added one by one to the database
                (mac, ((x,y),ind)) = self.pixels.popitem()
                SchedulerState.add_cell(x, y, mac, ind)
            print_flush("Database updated")

        #Allow to use the previous addressing as the current one
        def skip_procedure(self):
            #Retrieves the previous configuration
            self.pixels = SchedulerState.get_pixels_dic()
            #print_flush("Before readressing : {0} - {1}".format(self.pixels, self.pos_unknown))
            delete = [key for key in self.pos_unknown] #retrieves all the mac address of the card to be addressed
            for key in delete : #Pixel will be matched one on one with those of the Database, according to their mac address.
                value = self.pos_unknown[key]
                pixel = self.pixels.get(key)
                if pixel is None : #No match is found : user shouldn't have use this... unforeseen behaviour may occur from this point on.
                    print_flush("ERROR : using skip is not possible")
                else :
                    pixel = (pixel[0], value[1]) #The old index value is replaced with the new one.
                    self.pixels[key] = pixel #the pixel is then updated
                    self.pos_unknown.pop(key) #Finally, the pixel being addressed, so it's removed for the Unkown list.
            #print_flush("After readressing : {0} - {1}".format(self.pixels, self.pos_unknown))
            #Finally, the dictionnary modifications are notified to the server though the Websocket
            Websock.send_pos_unk(self.pos_unknown)
            Websock.send_pixels(self.pixels)

        #When addressing is over, but before admin close the F-app : makes App wait.
        def wait_to_be_kill(self):
            self.model.set_all('black')
            self.send_model()
            while True:
                print_flush("Addressing is over...")
                time.sleep(0.05)

        #Makes all pixels go from green to red, starting from the top left one to the bottom right one, in reading order.
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

        #Addressing procedure for all cards in the pos_unknown dictionnary
        def addressing_procedure(self):
            iteration = 1 #Unused variable - functionality to be implemented later
            #AMA/HAR shall continue as long as there are pixels without known position
            while (len(self.pos_unknown) != 0) :
                if self.action == 1 :
                    #the previous pixel has its right position, considering a new one
                    (mac, ((x,y),ind)) = self.pos_unknown.popitem()
                else :
                    #the previous position was ill initialize, the same card is considered again, and removed from addressed pixel.
                    self.pixels.pop(mac)
                    self.pos_unknown.pop(mac)
                self.matriceR(ind, iteration) #First, send the position request model
                Websock.send_ama_model(0) #Warn the server that the model is in 1D array format
                #print_flush(self.model)
                self.coord = (-1, -1)#Reset coordinate in case previous addressing was wrong
                print_flush("Waiting for user to input coordinates...")
                #print_flush([(val[0][0],val[0][1]) for val in self.pixels.values()])
                #print_flush(self.coord)
                #The command under generate an array containing all the (x, y) coordinates of addressed card.
                while ((self.coord in [(val[0][0],val[0][1]) for val in self.pixels.values()])):
                    #Here is where the default pixel is used : is coordinate of (-1, -1) matches with self.coord, so the program can't progress until user specified new coordinate
                    self.send_model()
                    time.sleep(0.05)
                #print_flush("apr la boucle d'attente active............................................................;")
                self.pixels[mac]=(self.coord, ind) #update of the local dictionary
                self.update() #Update the server dictionnaries
                self.matriceG(ind) #Send the validation matrix
                Websock.send_ama_model(1) # Warns the server that the model must be interpreted as a normal 2D array.
                self.action = 0 #No validation input
                print_flush("Waiting for user validation...")
                while (self.action == 0):
                    #wait for the confirmation of the administrator
                    self.send_model()
                    time.sleep(0.05)
                if self.action == 1 :
                    #Action is validated by user
                    print_flush("Input confirmed")
                    iteration += 1
                else : # the pixel is reput in the pos_unknown dictionary as its position is false
                    print_flush("Input canceled")
                    self.pos_unknown[mac] = ((x,y), ind)

        #Before doing HAR procedure, the index associated with disconnected cards in the routing table will be reused for the cards to be addressed.
        def reattributing_indexes(self):
            self.deco = loads(Websock.get_deco()) #retrieves the disconnected cards.
            for mac in self.pos_unknown.keys() :
                if len(self.deco) > 0 :
                    # dummy security, should do something in the case of it happenning but dunno what (yet)
                    pixel_deco = self.deco.popitem()
                    self.pos_unknown[mac] = ((-1,-1), pixel_deco[1][1]) #associate the disconnected card index to the unknown card.
            self.pixels = loads(Websock.get_pixels())#retrieves the current pixel list
            self.pixels['default'] = ((-1,-1), -1) #adds the fake pixel security.

        # Communicates all cell coordinates available for the HAR procedure to the frontend
        def send_pixel_down(self, positions):
            print_flush("Sending positions to frontend...")
            #print_flush(positions)
            Websock.send_data(positions, 'Pixel down message', self.username, self.userid)

        #Main function : starts the correct procedure, depending on the argument.
        def run(self, params, expires_at=None) :
            self.start_socket()
            # get necessary informations
            self.rows = SchedulerState.get_rows()
            self.cols = SchedulerState.get_cols()
            # get the pixels to address
            self.pos_unknown = loads(Websock.get_pos_unk()) #format {'@mac1' : ((x,j), index), ...}}
            self.params = params
            print_flush("Launched AMA app with {0} parameter".format(self.params['mode']))
            if (self.params['mode'] == 'ama') : # assisted manual addressing : reset the position of all pixels
                Websock.send_pixels({})
            elif (self.params['mode'] == 'rac') :
                 # hot assisted readdressing : reattribute the unusued pixel indexes (get from deconnected pixels) without changing already addressed pixels
                 self.deco = loads(Websock.get_deco())
                 array = []
                 for key in self.deco.keys(): #Generate the list of all free cells for the frontend
                     value = self.deco[key]
                     array += [value[0]]
                 self.send_pixel_down(array) #sends this list to the frontend
                 self.reattributing_indexes() #update the dictionnaries
            #Put esp root in ADDR or CONF state, depending on the current state of the server : indicate start of procedure
            Websock.send_esp_state(0)
            if self.params['mode'] == 'skip' :
                self.skip_procedure()
                sleep(1)
            else :
                self.addressing_procedure()
            #publish on REDIS and save in DB the new pixels dictionary
            self.update_DB()
            #Put ESPs in COLOR state
            Websock.send_esp_state(1)
            self.visual_verification()
            self.wait_to_be_kill()
