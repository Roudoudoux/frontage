import socket
import select
import sys
import os, fcntl
import time
import pika
import json
import utils.mesh_constants as c
from utils.mesh_communication import Frame
from threading import Thread, Lock
from utils.websock import Websock
from model import Model
from scheduler_state import SchedulerState
from server.flaskutils import print_flush

import struct


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
        self.msg = Frame()
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
        array = self.msg.har(Mesh.mac_root, c.STATE_CONF)
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
            array = self.msg.install_from_mac(val, ind)
            print_flush("voici l'array {}".format(array))
            self.com.send(array)
        # sending ERROR GO_TO
        array = self.msg.har(Mesh.mac_root, previous_state)
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
        print_flush("\tReceived : {} ({}) (valid ? {})".format(data, len(data), self.msg.is_valid(data)))
        if (data != "" and self.msg.is_valid(data)):
            if (data[c.TYPE] == c.ERROR) :
                mac = self.msg.array_to_mac(data[c.DATA+2 : c.DATA +8])
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
                    array = self.msg.error(data, ack=True)
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
                        array = self.msg.error(data, ack=True)
                    elif mac in Mesh.pixels :
                        print_flush("Address is in Mesh.pixels" )
                        array = self.msg.error(data, ack=True)
                    else :
                        # Raising UNK flag
                        Listen.unk[mac] = ((-1, -1),-1)
                        Websock.send_pos_unk(Listen.unk)
                        array = self.msg.error(data, ack=True, unk=True)
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
                        array = self.msg.har(Mesh.mac_root, data[c.DATA+1] & 0x0F)
                        self.com.send(array)
                    return
                else :
                    print_flush("Unkown message type")
                print_flush("Updates  Listen.deco {0} \n Updates Listen.unk {1}".format(Listen.deco, Listen.unk))
                # 2) Once the ERROR has been managed and informations updated, the esp root is informed of its fate
                self.com.send(array)
                print_flush("acquitted")
            elif ( data[c.TYPE] == c.BEACON)  :
                # 1) BEACON are only received during configuration phase. The esp declared itself one-by-one.
                #   Along with their declarations, they are stocked in unk dic wich is sent on Reddis at each new esp BEACON.
                #   It is necessary to do so because their is no way to known in advance how many esp will be in the mesh network.
                mac = self.msg.array_to_mac(data[c.DATA:c.DATA+6])
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
                array = self.msg.install(data, Mesh.comp)
                Mesh.comp += 1
                # 2) A INSTALL Frame is sent to the esp root for it to update its routing table and acknoledge the esp first sender
                self.com.send(array)
                print_flush("I've sent {}".format(array))
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
    ama = 0 #fluctuates between 0 and 3 : 0 => NEVER_addressed; 1 => AMA_INIT; 2 => AMA_COLOR; 3 => HAR
    change_esp_state = False #Order from ama.py to shift ESP in other state

    # Initialisation of Mesh instance requires seting up several connections to be in operating mode
    # A TCP connection for communication with the mesh network
    # A RabbitMQ connection for models recepetion
    # Reddis connection is managed by Websock class and static methods
    def __init__(self, conn, addr):
        Thread.__init__(self)
        print_flush("Pixels :", Mesh.pixels)
        #Manage adressing procedures
        Mesh.addressed = not (Mesh.pixels == {})
        self.ama_check = 0
        self.previous_state = 1
        self.model = Model(SchedulerState.get_rows(), SchedulerState.get_cols())
        #Communication with mesh network config
        self.msg = Frame()
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


    #Determine if the current model has a pattern matching with the expected one.
    # This function is used only in AMA or HAR procedure. It is called in ama_care function which handle models during those procedures.
    #The pattern to match is set in the instance attribut ama_check.
    # If ama_check is set to 0, Mesh class is looking for models having : 1 red pixel, x green pixel (0 <= x < required_amount ) and special pixels (set at -1)
    # else Mesh is looking for models  having : x green pixels and the rest is colored in black
    def ama_model(self) :
        i = self.model.get_height()-1
        if (self.ama_check == 0):
            green = red = 0
            while(i >= 0) :
                j = self.model.get_width()-1
                while (j >= 0 ) :
                    tmp = self.model.get_pixel(i,j) # tmp = (R, G, B)
                    if ( (tmp[0]+tmp[1]+tmp[2]) == -3): # special "color" -1
                        return True
                    elif (tmp[0] == 0 and tmp[1]==1 and tmp[2]==0): # green
                        green += 1
                    elif (tmp[0]== 1 and tmp[1] == 0 and tmp[2] == 0): # red
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

    #Is called to manage the addressing procedures.
    # Get from Reddis the newly update pixel dictionnary and unknown dictionnary
    #     this is a prerequise to build the COLOR frame and ensure that addressing procedures are well executed.
    # The type of model expected is also get from Reddis as it is set by the F-app AMA.py
    # The model received from RabbitMQ is check by ama_model. It necessary because RabbitMQ is refreshed at a frequency of 6Hz,
    # which introduce a delay between the reception of the expected model and the first model matching.
    def ama_care(self):
        #Get the new pixel addressed positions
        tmp = Websock.get_pixels()
        if tmp != None and tmp != {} :
            Mesh.pixels = json.loads(tmp)
        tmp = json.loads(Websock.get_pos_unk())
        if tmp != None :
            Listen.unk = tmp
        #Get the model format to check
        tmp = Websock.get_ama_model()
        if tmp != None:
            self.ama_check = eval(tmp)['ama']
        if self.ama_model():
            # send a COLOR frame only if the model match the expected model
            Mesh.sequence = (Mesh.sequence + 1) % 65536
            array = self.msg.color(self.model._model, Mesh.sequence, Mesh.pixels, Listen.unk, self.ama_check)
            self.mesh_conn.send(array)

    # This function is the manager of the different procedures implemented. It puts the server and the mesh network in the
    # right configuration for the required procedure by putting esp in the right state and manage the dictionnary
    def procedures_manager(self):
        Mesh.ama += 1
        if Mesh.ama == 1 : #AMA procedure starts
            print_flush("START AMA")
            Mesh.addressed = False
            Mesh.print_mesh_info("Start ama (procedures_manager)")
            array = self.msg.ama(c.AMA_INIT)
            self.mesh_conn.send(array)
        elif Mesh.ama == 2 : # Ends adressing procedures
            Mesh.addressed = True
            Mesh.print_mesh_info("End ama (procedures_manager)")
            array = self.msg.ama(c.AMA_COLOR)
            self.mesh_conn.send(array)
            print_flush("END addressing procedure")
        else : # HAR procedure starts
            print_flush("START HAR")
            Mesh.ama = 1
            Mesh.addressed = False
            Mesh.print_mesh_info("Start har (procedures_manager)")
            array = self.msg.har(Mesh.mac_root, c.STATE_CONF)
            self.mesh_conn.send(array)
            print_flush(Listen.unk.keys(), Listen.deco)
            # The pixel in deco are one by one being forgotten and their index is attributed to one of the unknown
            for mac in Listen.unk.keys() :
                if len(Listen.deco) > 0 :
                    pixel_deco = Listen.deco.popitem()
                    print_flush("Adding new element")
                    print_flush(pixel_deco)
                    print_flush("Inserted unknwon card at {0}".format(pixel_deco[1][1]))
                    Listen.unk[mac] = ((-1,-1), pixel_deco[1][1])
                    array = self.msg.install_from_mac(mac, pixel_deco[1][1])
                    self.mesh_conn.send(array)
            Websock.send_pos_unk(Listen.unk)
            Mesh.print_mesh_info("(end procedures_manager)")
            array = self.msg.ama(c.AMA_INIT)
            self.mesh_conn.send(array)

    #Invoque whenever a model is received from RabbitMQ, the callback function is the core.
    #Due to the absence of Reddis notification the callnack funciton is used to check if something have changed
    # - The deconnected pixel dictionnary has to be get from Reddis if a HAR procedure is at stake, because the unknown pixel have taken
    # their indexes in the routing table.
    # - The esp_state is the boolean that determines if a pocedure has started
    def callback(self, ch, method, properties, body):
        Mesh.consummed += 1
        if Mesh.consummed % 100 == 0 : #display mesh status each 100 models received
            Mesh.required_amount = SchedulerState.get_amount()
            Mesh.print_mesh_info("callback")
        # uncommment to reduce the amount of frames send during the esp declaration phase
        # if Mesh.comp < Mesh.required_amount :
        #     print_flush("Not enough pixels on the mesh network to display the model")
        #     return
        if Websock.should_get_deco() :
            Listen.deco = json.loads(Websock.get_deco())
        b = body.decode('ascii')
        self.model.set_from_json(b)
        tmp = Websock.get_esp_state()
        if tmp != None and eval(tmp) != self.previous_state:
            Mesh.change_esp_state = True
            print_flush("tmp != None, tmp = {}".format(tmp))
            self.previous_state = eval(tmp)
        else :
            Mesh.change_esp_state = False
        if Mesh.change_esp_state : # A procedure has started (ie AMA.py is launched) and both the mesh network and the serveur have to be ready
            self.procedures_manager()
        elif (Mesh.ama == 1) : # A procedure is running
            self.ama_care()
        elif (Mesh.addressed) :
            # Production mod : all pixels are addressed
            Mesh.sequence = (Mesh.sequence + 1) % 65536
            array = self.msg.color(self.model._model, Mesh.sequence, Mesh.pixels, Listen.unk)
            self.mesh_conn.send(array)
        else : # Temporisation required between the launching of AMA.py and the frist model matching the procedure arrives
            print_flush("{} : It is not the time to send colors".format(Mesh.consummed))

    #prints information relative to the mesh current state (server point of view)
    @staticmethod
    def print_mesh_info(arg):
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
        print_flush(" ========== Mesh ========== at {}".format(arg))

    #starts the connection to RabbitMQ
    def run(self):
        try:
            self.connection = pika.BlockingConnection(self.params)
            self.channel = self.connection.channel()
            self.channel.exchange_declare(exchange='pixels', exchange_type='fanout')

            result = self.channel.queue_declare(queue='',exclusive=True, arguments={"x-max-length": 1})
            queue_name = result.method.queue
            print_flush("queue_name={}".format(queue_name))
            self.channel.queue_bind(exchange='pixels', queue=queue_name)
            self.channel.basic_consume(queue=queue_name, on_message_callback=self.callback) #, queue=queue_name)
            Mesh.print_mesh_info("basic_consume")
            print_flush('Waiting for pixel data on queue "{}".'.format(queue_name))

            self.channel.start_consuming()
        except Exception as e:
            print_flush(e)
            if self.channel is not None:
                self.channel.close()
            if self.connection is not None:
                self.connection.close()
            raise e
        print_flush("wtf fin de run should have start start_consuming")

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
            print_flush("Socket opened, waiting for connection... already {} has connected".format(nb_connection))
            conn, addr = Mesh.socket.accept()
            nb_connection+=1
            print_flush("Connection accepted with {0}".format(addr))
            if (socket_thread != None) :
                socket_thread.close_socket()
                print_flush("The previous connection has been closed")
            socket_thread = Mesh(conn, addr)
            Mesh.print_mesh_info("main")
            socket_thread.start()

if __name__ == '__main__' :
    main()
