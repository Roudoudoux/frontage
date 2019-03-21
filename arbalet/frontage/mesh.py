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


def msg_color(colors, ama= 1):
    l = Mesh.comp
    # print_flush("there are {0} pixels take into account and ama is {1}".format(l, ama))
    m = len(colors[0])
    n = len(colors)
    # print_flush("m = ", m)
    array = bytearray(l*3 + 4 + ceil((l*3 + 4)/7))
    array[c.VERSION] = c.SOFT_VERSION
    array[c.TYPE] = c.COLOR
    Mesh.sequence = (Mesh.sequence + 1) % 65536
    array[c.DATA] = Mesh.sequence // 256
    array[c.DATA+1] = Mesh.sequence % 256
    # print_flush(colors)
    for val in Mesh.pixels.values():#Concat avec Listen.unk?
        ((i,j), ind) = val
        # print_flush("val =", val, "ama = ", ama)
        if (ama == 0) :#La matrice est un tabular
            # print_flush("On passe dans ama == 0", colors[int(ind/m)][int(ind % m)])
            # print_flush("indice : ", int(ind/m), ",", ind % m)
            # print_flush("type de colors :", type(colors))
            r = colors[int(ind/m)][int(ind % m)][0]
            v = colors[int(ind/m)][int(ind % m)][1]
            b = colors[int(ind/m)][int(ind % m)][2]
            # print_flush("nan mais tout va bien en fait")
        elif ( i != -1 and j != -1 and i < n and j < m)  : #Il y a un champ color
            r = colors[i][j][0]
            v = colors[i][j][1]
            b = colors[i][j][2]
        else: # Valeur inconnue et/ou ininterressante
            # print_flush("On passe dans pixel à 0")
            r= v= b= 0
        # print_flush("le pixel {0} {1} (indice {5}) recoit la couleur ({2}, {3}, {4})".format(i,j,r,v,b, ind))
        array[c.DATA + 2 + ind*3] = min(255, max(0, int(r*255)))
        array[c.DATA + 3 + ind*3] = min(255, max(0, int(v*255)))
        array[c.DATA + 4 + ind*3] = min(255, max(0, int(b*255)))
    # print_flush(array)
    for val in Listen.deco.values():#R.a.C =>
        ((i,j), ind) = val
        r= v= b= 0
        array[c.DATA + 2 + ind*3] = min(255, max(0, int(r*255)))
        array[c.DATA + 3 + ind*3] = min(255, max(0, int(v*255)))
        array[c.DATA + 4 + ind*3] = min(255, max(0, int(b*255)))
    if (Mesh.ama == 1) :
        #en plein adressage
        for val in Listen.unk.values():#Concat avec Listen.unk?
            ((i,j), ind) = val
            if (ama == 0) :#La matrice est un tabular
                r = colors[int(ind/m)][int(ind % m)][0]
                v = colors[int(ind/m)][int(ind % m)][1]
                b = colors[int(ind/m)][int(ind % m)][2]
            elif ( i != -1 and j != -1): #Il y a un champ color
                r = colors[i][j][0]
                v = colors[i][j][1]
                b = colors[i][j][2]
            else: # Valeur inconnue et/ou ininterressante
                r= v= b= 0
            array[c.DATA + 2 + ind*3] = min(255, max(0, int(r*255)))
            array[c.DATA + 3 + ind*3] = min(255, max(0, int(v*255)))
            array[c.DATA + 4 + ind*3] = min(255, max(0, int(b*255)))
    # print_flush(array)
    crc_get(array)
    # print_flush(array)
    return array

class Listen(Thread) :
    deco = {} # matrix of pixels addressed but lost, deconnected
    unk = {} # matrix of new pixels which do not have positions

    def __init__(self, com) :
        # print_flush("Listen init")
        Thread.__init__(self)
        self.com = com
        # self.allowed = False
        self.count = 0
        # print_flush("Listen fin init")

    def run(self) :
        # print_flush("Listen start")
        while True:
            self.listen()

    def listen(self) :
        data = ""
        self.count += 1
        print_flush("{0} Listening...".format(self.count))
        data = self.com.mesh_conn.recv(1500)
        if (data != "" and crc_check(data[0:16])) :
            #ajout message sur sentry
            if (data[c.TYPE] == c.ERROR) :
                array = bytearray(16)
                array[c.VERSION] = c.SOFT_VERSION
                array[c.TYPE] = c.ERROR
                array[c.DATA] = data[c.DATA]
                array[c.DATA+1] = data[c.DATA+1]
                for j in range (c.DATA+2, c.DATA+8) :
                    array[j] = data[j]
                #Setting flags...
                mac = array_to_mac(data[c.DATA+2 : c.DATA +8])
                print_flush("Pixel {0} has encountered a problem {1}".format(mac, data[c.DATA]))
                if data[c.DATA] == c.ERROR_DECO :
                    if (Mesh.pixles.get(mac) is not None) :
                        Listen.deco[mac] = Mesh.pixels.pop(mac)
                        Websock.send_pixels(Mesh.pixels)
                    elif (Listen.unk.get(mac) is not None) :
                        Listen.unk.pop(mac)
                    print_flush("Add pixel {0} to Listen.deco : {1}".format(mac, Listen.deco))
                elif data[c.DATA] == c.ERROR_CO :
                    if mac in Listen.deco :
                        print_flush("Address is in Listen.deco")
                        Mesh.pixels[mac] = Listen.deco.pop(mac)
                        Websock.send_pixels(Mesh.pixels)
                    elif mac in Mesh.pixels :
                        print_flush("Address is in Mesh.pixels" )
                    else :
                        # Raising UNK flag
                        Mesh.comp +=1
                        Listen.unk[mac] = ((-1, -1),-1) #pb, on ne peut pas mettre -1 en indice de tableau
                        Websock.send_pos_unk(Listen.unk)
                        array[c.DATA+1] = array[c.DATA+1] | 32
                else :
                    print_flush("WTF????")
                print_flush("Received message, acquitting it", data)
                print_flush("Updates  Listen.deco {0} \n Updates Listen.unk {1}".format(Listen.deco, Listen.unk))
                array[c.DATA+1] = array[c.DATA+1] | 128
                crc_get(array)
                # print_flush(array)
                self.com.mesh_conn.send(array)
                print_flush("acquitted")
            elif ( data[c.TYPE] == c.BEACON)  :
                print_flush("BEACON : %d-%d-%d-%d-%d-%d" % (int(data[c.DATA]), int(data[c.DATA+1]), int(data[c.DATA+2]), int(data[c.DATA+3]), int(data[c.DATA+4]), int(data[c.DATA+5])))
                mac = array_to_mac(data[c.DATA:c.DATA+6])
                print_flush("le pixel ayant l'adresse {0} se déclare".format(mac))
                if (Mesh.comp == 0):
                    Mesh.mac_root= mac
                if Listen.unk.get(mac) != None :
                    print_flush("But it has already be declared ")
                    pass
                Listen.unk[mac]=((-1,-1), Mesh.comp)
                Websock.send_pos_unk(Listen.unk)
                array = msg_install(data, Mesh.comp)
                Mesh.comp += 1
                self.com.mesh_conn.send(array)
            else :
                print_flush("received unintersting message...")

class Mesh(Thread):
    socket = None #socket bind to mesh network through AP
    mac_root = '' #esp32 root mac address

    #Is there realy a need for you "addressed" ??

    addressed = None
    ama = 0 #fluctuates between 0 and 3 : 0 => NEVER_addressed; 1 => AMA_INIT; 2 => AMA_COLOR; 3 => RAC
    change_esp_state = False #Order from ama.py to shift ESP in other state
    rows = 0 #matrix height
    cols = 0 # matrix width
    comp = 0 # pixel amount
    sequence = 0 # sequence number of the COLOR frame

    # pixels = {} # dictionnary of pixel, position (x,y) and i
    pixels = SchedulerState.get_pixels_dic()


    def __init__(self, conn, addr):
        Thread.__init__(self)
        print_flush("Pixels :", Mesh.pixels)
        Mesh.addressed = not (Mesh.pixels == {})
        #Communication with mesh network config
        self.mesh_conn = conn
        self.mesh_addr = addr
        self.ama_check = 0
        self.p = 0
        self.model = Model(SchedulerState.get_rows(), SchedulerState.get_cols())

        self.stopped = False
        self.l = Listen(self)
        self.l.start()
        #Communication with RabbitMQ config
        self.channel = None
        self.connection = None
        credentials = pika.PlainCredentials(os.environ['RABBITMQ_DEFAULT_USER'], os.environ['RABBITMQ_DEFAULT_PASS'])
        self.params = pika.ConnectionParameters(host='rabbit', credentials=credentials, heartbeat = 0)

    def ama_model(self) :
        # print_flush("entering ama_model")
        i = self.model.get_height()-1
        if (self.ama_check == 0): #this part fonctionne
            # print_flush("entering kind 0 :")
            while(i >= 0) :
                j = self.model.get_width()-1
                while (j >= 0 ) :
                    tmp = self.model.get_pixel(i,j)
                    # print_flush("pixels {0} {1} : {2}".format(i,j,tmp))
                    if ( (tmp[0]+tmp[1]+tmp[2]) == -3):
                        # print_flush("quiting ama_model True 0")
                        return True
                    j -= 1
                i -= 1
            # print_flush("quiting ama_model False 0")
            return False
        elif (self.ama_check == 1): #not tested
            # print_flush("entering kind 1 :")
            while(i >= 0) :
                j = self.model.get_width()-1
                while (j >= 0 ) :
                    tmp = self.model.get_pixel(i,j)
                    # print_flush("pixels {0} {1} : {2}".format(i,j,tmp))
                    if (( (tmp[0]+tmp[1]+tmp[2]) != 0) and (tmp[0] != 1 and tmp[1]+tmp[2] != 0) and (tmp[1] != 1 and tmp[0]+tmp[2] != 0)):
                        # print_flush("quiting ama_model False 1")
                        return False
                    j -= 1
                i -= 1
                # print_flush("quiting ama_model True 1")
                return True

    def ama_care(self):
        #Get the new pixel addressed positions
        # print_flush(Mesh.pixels)
        tmp = Websock.get_pixels()
        if tmp != None and tmp != {} :
            # print_flush("tmp (pixels) : {0}".format(tmp))
            Mesh.pixels = json.loads(tmp)
        # print_flush(Mesh.pixels)
        tmp = json.loads(Websock.get_pos_unk())
        if tmp != None :
            # print_flush("tmp (pos_unk) : {0}".format(tmp))
            Listen.unk = tmp
            # print_flush("Le websocket deconne encoe!!!!")
        #Get the Frame format to check
        tmp = Websock.get_ama_model()
        if tmp != None:
            self.ama_check = eval(tmp)['ama']
        # print_flush("on passe à ama_model")
        if self.ama_model():
            array = msg_color(self.model._model, self.ama_check)
            self.mesh_conn.send(array)

    def callback(self, ch, method, properties, body):
        if Mesh.comp < len(Mesh.pixels):
            return
        b = body.decode('ascii')
        self.model.set_from_json(b)
        tmp = Websock.get_esp_state()
        if tmp != 'None' and tmp != None:
            Mesh.change_esp_state = True
        else :
            Mesh.change_esp_state = False
        # print_flush(self.model)
        self.p += 1
        print_flush("{2} : on m'a demandé de changer d'état : {0} ({1})".format(Mesh.change_esp_state, tmp, self.p))
        if Mesh.change_esp_state :
            Mesh.ama += 1
            if Mesh.ama == 1 :
                print_flush("DEBUT Mesh.ama = 1")
                Mesh.addressed = False
                Mesh.rows = SchedulerState.get_rows()
                Mesh.cols = SchedulerState.get_cols()
                array = msg_ama(c.AMA_INIT)
                self.mesh_conn.send(array)
                print_flush("FIN Mesh.ama = 1")
            elif Mesh.ama == 2 :
                print_flush("DEBUT Mesh.ama = 2")
                Mesh.addressed = True
                array = msg_ama(c.AMA_COLOR)
                self.mesh_conn.send(array)
                print_flush("FIN Mesh.ama = 2")
            else : # RaC ==========================> TO CHECK
                print_flush("DEBUT Mesh.ama = 3")
                Mesh.ama = 1
                Mesh.addressed = False
                Websock.send_pos_unk(Listen.unk)
                array = msg_readressage(Mesh.mac_root,c.STATE_ADDR)
                self.mesh_conn.send(array)
                print_flush("FIN Mesh.ama = 3")
        elif (Mesh.ama == 1) :
            print_flush("phase d'addressage")
            self.ama_care()
        elif (Mesh.addressed) :
            array = msg_color(self.model._model)
            self.mesh_conn.send(array)
        else :
            print_flush("it is not the time to send colors")

    def send_table(self): #pb : récupérer l'adresse de la nouvelle root
        #passe la nouvelle root en state_conf
        array = msg_readressage(Mesh.mac_root, c.STATE_CONF)#comment trouver l'adresse mac de la nouvelle root ????
        self.mesh_conn.send(array)
        time.sleep(0.1)
        #envoie de trames install
        for val in Mesh.pixels :
            ((i,j), ind) = Mesh.pixels.get(val)
            print_flush("on envoie INSTALL pour {}".format(ind))
            array = msg_install_from_mac(val, ind)
            print_flush("voici l'array {}".format(array))
            self.mesh_conn.send(array)
            time.sleep(0.1)
        #passe en AMA_INIT puis en AMA_COLOR
        array = msg_ama(c.AMA_INIT)
        self.mesh_conn.send(array)
        time.sleep(0.1)
        array = msg_ama(c.AMA_COLOR)
        self.mesh_conn.send(array)
        print_flush("on a fini l'envoie de la table")

    def print_mesh_info(self): #dummy print
        print_flush(" ========== Mesh ==========")
        print_flush("-------- Is mesh initialized :")
        print_flush(Mesh.addressed)
        print_flush("-------- Is Running?")
        print_flush("True")
        print_flush("-------- Pixels?")
        print_flush(Mesh.pixels)

    def run(self):
        try:
            self.connection = pika.BlockingConnection(self.params)
            self.channel = self.connection.channel()
            self.channel.exchange_declare(exchange='pixels', exchange_type='fanout')

            result = self.channel.queue_declare(exclusive=True, arguments={"x-max-length": 1})
            queue_name = result.method.queue

            self.channel.queue_bind(exchange='pixels', queue=queue_name)
            self.channel.basic_consume(self.callback, queue=queue_name, no_ack=True)
            self.print_mesh_info()
            print_flush('Waiting for pixel data on queue "{}".'.format(queue_name))

            #TEMPORAIRE
            # Mesh.addressed = True
            # array = msg_ama(AMA_INIT)
            # self.mesh_conn.send(array)
            # array = msg_ama(AMA_COLOR)
            # self.mesh_conn.send(array)
            # Mesh.ama = 2
            # #FIN TEMPORAIRE

            self.channel.start_consuming()
        except Exception as e:
            if self.channel is not None:
                self.channel.close()
            if self.connection is not None:
                self.connection.close()
            raise e

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
        # print_flush(Mesh.socket)
        socket_thread = None
        while True :
            print_flush("Socket opened, waiting for connection...")
            conn, addr = Mesh.socket.accept()
            print_flush("Connection accepted with {0}".format(addr))
            nb_connection += 1
            if (socket_thread != None) :
                socket_thread.close_socket()
            socket_thread = Mesh(conn, addr)
            socket_thread.print_mesh_info()
            # socket_thread.l.allowed = True
            if Mesh.addressed  and nb_connection != 1 :
                print_flush("Envoie de la table de rootage à la nouvelle root")
                socket_thread.send_table() #ne semble pas être pris en compte lors d'un pb de la root
            socket_thread.start()

if __name__ == '__main__' :
    main()
