import socket
import select
import sys
import os, fcntl
import time
import pika
import json
import utils.mesh_constants as c
from utils.mesh_communication import msg_ama, msg_install, msg_install_from_mac, msg_readressage, array_to_mac, mac_to_array
from threading import Thread, Lock
from math import ceil
from utils.crc import crc_get, crc_check
from utils.websock import Websock
from model import Model
from scheduler_state import SchedulerState
from server.flaskutils import print_flush

import struct


# Description :
# the two dictionnaries have the same formate {key : ((x,y), ind)},
# For a key k presents in both dico1 and dico2, matching key update the "ind" value of
# k in dico2 with the one in dico1.
# Utility :
# This function is used in a case of skipping AMA procedure to refresh the pixel indexes
# in COLOR frames
def matching_keys(dico1, dico2):
    if (len(dico1) == len(dico2)):
        for key in dico1.keys() :
            if (dico2.get(key) == None):
                return False
        for key in dico1.keys() :
            val1 = dico1[key]
            val2 = dico2[key]
            val2[1] = val1[1]
            dico2[key] = val2
        return True
    else :
        return False

# Description :
# fill the array according to the chosen mod (ama/prod) with the colors matching the pixels position stock in dico
# Utility :
# The given array is in fact the COLOR frame which will be sent to ESP root
def filling_array(array, colors, dico, ama):
    m = len(colors[0])
    n = len(colors)
    for val in dico.values():
        ((i,j), ind) = val
        if ind < Mesh.comp :
            if (ama == 0) :# 2D array is interpreted as a 1D array
                r = colors[int(ind/m)][int(ind % m)][0]
                v = colors[int(ind/m)][int(ind % m)][1]
                b = colors[int(ind/m)][int(ind % m)][2]
            elif ( i != -1 and j != -1 and i < n and j < m)  : #The pixel is addressed and within the model boundaries
                r = colors[i][j][0]
                v = colors[i][j][1]
                b = colors[i][j][2]
            else: # unkown value
                r= v= b= 0
            # Fill the right place in the COLOR frame
            array[c.DATA + 2 + ind*3] = min(255, max(0, int(r*255)))
            array[c.DATA + 3 + ind*3] = min(255, max(0, int(v*255)))
            array[c.DATA + 4 + ind*3] = min(255, max(0, int(b*255)))

# Description :
# formating the color frame according to the ESP32 communication protocol
# Note :
# Is not with the other functions (in mesh_communication) because msg_color is using and updating some Mesh's attributs
def msg_color(colors, ama= 1):
    l = Mesh.comp
    array = bytearray(l*3 + 4 + ceil((l*3 + 4)/7))
    array[c.VERSION] = c.SOFT_VERSION
    array[c.TYPE] = c.COLOR
    Mesh.sequence = (Mesh.sequence + 1) % 65536
    array[c.DATA] = Mesh.sequence // 256
    array[c.DATA+1] = Mesh.sequence % 256
    filling_array(array, colors, Mesh.pixels, ama)
    if (Mesh.ama == 1) :
        filling_array(array,colors,Listen.unk, ama)
    crc_get(array)
    return array

# The Listen class is used to managed the communication with the mesh network.
# It waits for messages from ESP root and finds the rigth response
# A response is composed of two parts :
# - 1) a process in the service
# - 2) a frame to send to the esp root
#
# Those parts will be indicated in the code respectively by "1)" and "2)"
#
# Listen class is also the one managing the dictionnaries deco and unk wich are
# respectively manager of the not responding esps and the newly add ones.
class Listen(Thread) :
    deco = {} # matrix of pixels addressed but lost, deconnected
    unk = {} # matrix of new pixels which do not have positions


    # Listen requires a socket descritor to communicate with esp root
    # It initialised the redis values of the different dictionnaries and the get_deco value
    def __init__(self, com) :
        Thread.__init__(self)
        self.com = com
        self.count = 0
        Websock.send_deco(Listen.deco)
        Websock.send_pos_unk(Listen.unk)
        Websock.send_get_deco(False)

    #Send the current routing table to the new elected root within the mesh network
    # To do so, the esp root is put in CONF state (which allows the reception of INSTALL frames)
    # then INSTALL frame are send in the indexe ascending order. At last the esp root is put in
    # its previous state via the emission of a go_to frame
    def send_table(self, previous_state):
        print_flush("Sending routing table... Step 1 achieved.")
        array = msg_readressage(Mesh.mac_root, c.STATE_CONF)
        self.com.send(array)
        # sorting values in acsending order as required by ESP algorithm
        root_val = Mesh.pixels[Mesh.mac_root]
        card_list = [None] * Mesh.comp
        for val in Mesh.pixels :
            ((i,j), ind) = Mesh.pixels.get(val)
            card_list[ind] = ((i, j), val)
        for val in Listen.deco :
            ((i,j), ind) = Listen.deco.get(val)
            card_list[ind] = ((i, j), val)
        # sending INSTALL frame one by one
        for ind, value in enumerate(card_list) :
            ((i, j), val) = value
            print_flush("on envoie INSTALL pour {}".format(ind))
            array = msg_install_from_mac(val, ind)
            print_flush("voici l'array {}".format(array))
            self.com.send(array)
        # sending ERROR GO_TO
        array = msg_readressage(Mesh.mac_root, previous_state)
        self.com.send(array)
        print_flush("Routing table has been sent to {}".format(Mesh.mac_root))

    #Reacts to all messages received from the mesh network.
    # listen is talkative in view to inform via print_flush the administrator of all the messages it received
    def listen(self) :
        data = ""
        self.count += 1
        print_flush("{0} Listening... {1}".format(self.count, time.asctime( time.localtime(time.time()) )))
        # receives 1500 (a wifi frame length)
        data = self.com.recv(1500)
        if (data != "" and crc_check(data[0:16])) :
            if (data[c.TYPE] == c.ERROR) :
                # when a frame ERROR is received, an ERROR frame will be sent no matter the sub-type
                array = bytearray(16)
                array[c.VERSION] = c.SOFT_VERSION
                array[c.TYPE] = c.ERROR
                array[c.DATA] = data[c.DATA]
                array[c.DATA+1] = data[c.DATA+1]
                for j in range (c.DATA+2, c.DATA+8) :
                    array[j] = data[j]
                mac = array_to_mac(data[c.DATA+2 : c.DATA +8])
                print_flush("Pixel {0} has encountered a problem {1}".format(mac, data[c.DATA]))
                if data[c.DATA] == c.ERROR_DECO :
                    # 1) the pixel deconnected has to be removed from the working pixel dictionnary and put in the deconnected pixel one
                    #    If the pixel is not adressed it can be removed from the server knowledges
                    if (Mesh.pixels.get(mac) is not None) :
                        Listen.deco[mac] = Mesh.pixels.pop(mac)
                        Websock.send_pixels(Mesh.pixels)
                        Websock.send_deco(Listen.deco)
                    elif (Listen.unk.get(mac) is not None) :
                        Listen.unk.pop(mac)
                    print_flush("Add pixel {0} to Listen.deco : {1}".format(mac, Listen.deco))
                elif data[c.DATA] == c.ERROR_CO :
                    # 1) the new pixel is deal with along with the informations known about it.
                    #    If it has been adressed, it gets to work again without any action from administrator
                    #    Else a administrator action is required. In the former case the pixel goes in working pixels dic
                    #    In the latter it goes in unknown pixels dic to wait for human intervention
                    if mac in Listen.deco :
                        print_flush("Address is in Listen.deco")
                        Mesh.pixels[mac] = Listen.deco.pop(mac)
                        Websock.send_pixels(Mesh.pixels)
                        Websock.send_deco(Listen.deco)
                    elif mac in Mesh.pixels :
                        print_flush("Address is in Mesh.pixels" )
                    else :
                        # Raising UNK flag
                        Listen.unk[mac] = ((-1, -1),-1)
                        Websock.send_pos_unk(Listen.unk)
                        array[c.DATA+1] = array[c.DATA+1] | 32
                elif data[c.DATA] == c.ERROR_ROOT :
                    # 1) a reelection has occured in the mesh network, the new esp root send a frame to declared herself.
                    #    The mac_root is updated and the known card number is comparted to the one of the root.
                    Mesh.mac_root = mac
                    nb_card = (data[c.DATA+1] & 0xF0) >> 4
                    print_flush("on dit qu'il y a {}".format(nb_card))
                    # 2) If the error has occured because of the mesh network  : the routing table is sent to the newly elected esp root
                    #    Else it was due to the sever wich takes the nb_pixels has granted and considered pixels has addressed.
                    if Mesh.comp >= nb_card :
                        self.send_table(data[c.DATA+1] & 0x0F)
                    else :
                        Mesh.comp = nb_card
                        Mesh.addressed = True
                        array = msg_readressage(Mesh.mac_root, data[c.DATA+1] & 0x0F)
                        self.com.send(array)
                    return
                else :
                    print_flush("Unkown message type")
                print_flush("Updates  Listen.deco {0} \n Updates Listen.unk {1}".format(Listen.deco, Listen.unk))
                # The ACK flag is raised to prevent the esp root that it's error has been handled
                array[c.DATA+1] = array[c.DATA+1] | 128
                # 2) Once the ERROR has been managed and informations updated, the esp root is informed of its fate
                crc_get(array)
                self.com.send(array)
                print_flush("acquitted")
            elif ( data[c.TYPE] == c.BEACON)  :
                # 1) BEACON are only received during configuration phase. The esp declared itself one-by-one.
                #   Along with their declarations, they are stocked in unk dic wich is sent on Reddis at each new esp BEACON.
                #   It is necessary to do so because their is no way to known in advance how many esp will be in the mesh network.
                mac = array_to_mac(data[c.DATA:c.DATA+6])
                print_flush("Pixel {0} is declaring itself".format(mac))
                if (Mesh.comp == 0):
                    # The first to declared itself is the esp root
                    Mesh.mac_root= mac
                if Listen.unk.get(mac) != None :
                    # an ESP is only considered once
                    print_flush("But it has already be declared ")
                    pass
                Listen.unk[mac]=((-1,-1), Mesh.comp)
                Websock.send_pos_unk(Listen.unk)
                array = msg_install(data, Mesh.comp)
                Mesh.comp += 1
                # 2) A INSTALL Frame is sent to the esp root for it to update its routing table and acknoledge the esp first sender
                self.com.send(array)
            else :
                print_flush("received unintersting message...")

    def run(self) :
        #dummy infinite loop
        while True:
            self.listen()


# Mesh class is the model consummer. It ensures that models are well interpreted and match with the action
# taking place on the frontend. The AMA/HAR procedure are managed by this class in the maner to understand models
# and what information to get or to sent to F-app. The only F-app "talking via Reddis" with Mesh class is AMA.py
class Mesh(Thread):
    socket = None #socket bind to mesh network through AP
    mac_root = '' #esp32 root mac address
    sequence = 0 # sequence number of the COLOR frame
    pixels = SchedulerState.get_pixels_dic() #pixels addressed and connected
    required_amount = SchedulerState.get_amount() #number of pixel required by the administrator
    consummed = 0 #model consummed on RabbitMQ
    comp = 0 # pixel amount
    #Manage adressing procedures
    addressed = None #Tels if the pixels are addressed or not
    ama = 0 #fluctuates between 0 and 3 : 0 => NEVER_addressed; 1 => AMA_INIT; 2 => AMA_COLOR; 3 => RAC
    change_esp_state = False #Order from ama.py to shift ESP in other state

    # Initialisation of Mesh instance requires seting up several connection to be in operating mode
    def __init__(self, conn, addr):
        Thread.__init__(self)
        print_flush("Pixels :", Mesh.pixels)
        #Manage adressing procedures
        Mesh.addressed = not (Mesh.pixels == {})
        self.ama_check = 0
        self.previous_state = 1
        self.model = Model(SchedulerState.get_rows(), SchedulerState.get_cols())
        #Communication with mesh network config
        self.mesh_conn = conn
        self.mesh_addr = addr
        self.l = Listen(conn)
        self.l.start()
        self.stopped = False
        #Communication with RabbitMQ config
        self.channel = None
        self.connection = None
        credentials = pika.PlainCredentials(os.environ['RABBITMQ_DEFAULT_USER'], os.environ['RABBITMQ_DEFAULT_PASS'])
        self.params = pika.ConnectionParameters(host='rabbit', credentials=credentials, heartbeat = 0)


    #determine if the current model has a pattern matching with the expected oneself.
    #All along adressing procedures, there are only two model types accepted : the one filled with green and black and the one with green, undifined and one red pixel.
    #The pattern to match is set in the instance attribut ama_check.
    def ama_model(self) :
        i = self.model.get_height()-1
        if (self.ama_check == 0):
            green = red = 0
            while(i >= 0) :
                j = self.model.get_width()-1
                while (j >= 0 ) :
                    tmp = self.model.get_pixel(i,j)
                    if ( (tmp[0]+tmp[1]+tmp[2]) == -3):
                        return True
                    elif (tmp[0] == 0 and tmp[1]==1 and tmp[2]==0):
                        green += 1
                    elif (tmp[0]== 1 and tmp[1] == 0 and tmp[2] == 0):
                        red += 1
                    else :
                        return False
                    j -= 1
                i -= 1
            return (green == Mesh.required_amount -1 and red == 1)
        elif (self.ama_check == 1):
            while(i >= 0) :
                j = self.model.get_width()-1
                while (j >= 0 ) :
                    tmp = self.model.get_pixel(i,j)
                    if (( (tmp[0]+tmp[1]+tmp[2]) != 0) and (tmp[0] != 1 and tmp[1]+tmp[2] != 0) and (tmp[1] != 1 and tmp[0]+tmp[2] != 0)):
                        return False
                    j -= 1
                i -= 1
                return True

    #update the known pieces of information before trying to display the model on the mesh network.
    def ama_care(self):
        #Get the new pixel addressed positions
        tmp = Websock.get_pixels()
        if tmp != None and tmp != {} :
            Mesh.pixels = json.loads(tmp)
        tmp = json.loads(Websock.get_pos_unk())
        if tmp != None :
            Listen.unk = tmp
        #Get the Frame format to check
        tmp = Websock.get_ama_model()
        if tmp != None:
            self.ama_check = eval(tmp)['ama']
        if self.ama_model():
            array = msg_color(self.model._model, self.ama_check)
            self.mesh_conn.send(array)

    #invoque whenever a model is received from RabbitMQ, the callback function is the core. It checks if a readressing procedures has been required_amount
    # and reacts correspondivly.
    def callback(self, ch, method, properties, body):
        Mesh.consummed += 1
        if Mesh.consummed % 100 == 0 :
            Mesh.required_amount = SchedulerState.get_amount()
            Mesh.print_mesh_info()
        if Mesh.comp < Mesh.required_amount :
            return
        #print_flush("Entered callback corps")
        if Websock.should_get_deco() :
            Listen.deco = json.loads(Websock.get_deco())
        b = body.decode('ascii')
        self.model.set_from_json(b)
        tmp = Websock.get_esp_state()
        # print_flush(tmp)
        # print_flush("avt eval de tmp {}".format(tmp))
        if tmp != None and eval(tmp) != self.previous_state: #temporaire en attendant une mise de verrou dans websocket
            Mesh.change_esp_state = True
            print_flush("tmp != None, tmp = {}".format(tmp))
            self.previous_state = eval(tmp)
        else :
            # print_flush("tmp == None")
            Mesh.change_esp_state = False
        # print_flush("ap eval de tmp {}".format(self.previous_state))
        if Mesh.change_esp_state :
            Mesh.ama += 1
            if Mesh.ama == 1 : #AMA procedure starts
                print_flush("DEBUT Mesh.ama = 1")
                Mesh.addressed = False
                Mesh.print_mesh_info()
                array = msg_ama(c.AMA_INIT)
                self.mesh_conn.send(array)
                print_flush("FIN Mesh.ama = 1")
            elif Mesh.ama == 2 : # Ends adressing procedures
                print_flush("DEBUT Mesh.ama = 2")
                Mesh.addressed = True
                Mesh.print_mesh_info()
                array = msg_ama(c.AMA_COLOR)
                self.mesh_conn.send(array)
                print_flush("FIN Mesh.ama = 2")
            else : # RaC procedure starts
                print_flush("DEBUT Mesh.ama = 3")
                Mesh.ama = 1
                Mesh.addressed = False
                Mesh.print_mesh_info()
                array = msg_readressage(Mesh.mac_root, c.STATE_CONF)
                self.mesh_conn.send(array)
                print_flush(Listen.unk.keys(), Listen.deco)
                for mac in Listen.unk.keys() :
                    if len(Listen.deco) > 0 :
                        pixel_deco = Listen.deco.popitem()
                        print_flush("Adding new element")
                        print_flush(pixel_deco)
                        print_flush("Inserted unknwon card at {0}".format(pixel_deco[1][1]))
                        Listen.unk[mac] = ((-1,-1), pixel_deco[1][1])
                        array = msg_install_from_mac(mac, pixel_deco[1][1])
                        self.mesh_conn.send(array)
                Websock.send_pos_unk(Listen.unk)
                Mesh.print_mesh_info()
                array = msg_ama(c.AMA_INIT)
                self.mesh_conn.send(array)
                print_flush("FIN Mesh.ama = 3")
        elif (Mesh.ama == 1) :
            self.ama_care()
        elif (Mesh.addressed) :
            #print_flush("Sending color")
            array = msg_color(self.model._model)
            self.mesh_conn.send(array)
            #print_flush("Colors send")
        else :
            print_flush("{} : It is not the time to send colors".format(Mesh.consummed))

    #prints information relative to the mesh current state (server point of view)
    @staticmethod
    def print_mesh_info():
        print_flush(" ========== Mesh ==========")
        print_flush("-------- Is mesh initialized :")
        print_flush(Mesh.addressed)
        print_flush("-------- Color frame sent : ")
        print_flush(Mesh.consummed)
        print_flush("-------- Pixels amount declared ?")
        print_flush(Mesh.comp)
        print_flush("-------- Pixels amount required ?")
        print_flush(Mesh.required_amount)
        print_flush("-------- Pixels?")
        print_flush(Mesh.pixels)
        print_flush("-------- Pixels deconnected?")
        print_flush(Listen.deco)
        print_flush("-------- Pixels unknown?")
        print_flush(Listen.unk)

    #starts the connection to RabbitMQ
    def run(self):
        try:
            self.connection = pika.BlockingConnection(self.params)
            self.channel = self.connection.channel()
            self.channel.exchange_declare(exchange='pixels', exchange_type='fanout')

            result = self.channel.queue_declare(exclusive=True, arguments={"x-max-length": 1})
            queue_name = result.method.queue

            self.channel.queue_bind(exchange='pixels', queue=queue_name)
            self.channel.basic_consume(self.callback, queue=queue_name, no_ack=True)
            Mesh.print_mesh_info()
            print_flush('Waiting for pixel data on queue "{}".'.format(queue_name))

            self.channel.start_consuming()
        except Exception as e:
            if self.channel is not None:
                self.channel.close()
            if self.connection is not None:
                self.connection.close()
            raise e

    #Close nicely the connections with other services before killing the thread
    def close_socket(self) :
        print_flush("exiting thread, closing connection")
        if self.mesh_conn is not None :
            self.mesh_conn.close()
        if self.channel is not None:
            self.channel.close()
        if self.connection is not None:
            self.connection.close()
        print_flush("Closed connection, exiting thread...")
        self.stopped = True

def main() :
    nb_connection = 0
    Websock.send_esp_state(1)
    while True :
        Mesh.socket= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print_flush(Mesh.socket.gettimeout())
        while True:
            try :
                Mesh.socket.bind((c.HOST, c.PORT))
                Mesh.socket.listen(5)
            except socket.error as msg:
                print_flush("Socket has failed :",msg)
                time.sleep(0.1)
                continue
            break
        socket_thread = None
        while True :
            print_flush("Socket opened, waiting for connection...")
            conn, addr = Mesh.socket.accept()
            print_flush("Connection accepted with {0}".format(addr))
            if (socket_thread != None) :
                socket_thread.close_socket()
                print_flush("The previous connection has been closed")
            socket_thread = Mesh(conn, addr)
            Mesh.print_mesh_info()
            socket_thread.start()

if __name__ == '__main__' :
    main()
