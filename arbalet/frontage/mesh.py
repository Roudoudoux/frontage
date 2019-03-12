import socket
import select
import sys
import os, fcntl
import time
import pika
import json
from threading import Thread, Lock
from math import ceil
from utils.crc import crc_get, crc_check
from utils.websock import Websock
from model import Model
from scheduler_state import SchedulerState
from server.flaskutils import print_flush

import struct

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', bytes(ifname[:15], 'utf-8'))
    )[20:24])


# CONSTANTS

# Connection
HOST='0.0.0.0'#str(get_ip_address('eth0'))
#HOST='10.0.0.1'
PORT=9988
SOFT_VERSION = 1

print_flush("")
print_flush("")
print_flush("")
print_flush(HOST)
print_flush("")
print_flush("")
print_flush("")

#Frame's type
BEACON = 1
INSTALL = 3
COLOR = 4
AMA = 6
ERROR = 7
SLEEP = 8
AMA_INIT = 61
AMA_COLOR = 62
ERROR_CO = 71
ERROR_DECO = 72
ERROR_GOTO = 73
SLEEP_SERVER = 81
SLEEP_MESH = 82
SLEEP_WAKEUP = 89

#Field

VERSION = 0
TYPE = 1
DATA = 2
FRAME_SIZE = 16

# state

STATE_CONF = 2


def mac_to_array(mac, array, offset):
    i = j = 0
    while ( len(mac) != 0):
        if (i < len(mac) and mac[i] != ':') :
            i += 1
        else:
            array[offset + j] = int(mac[:i])
            mac = mac[i+1 :]
            i = 0
            j += 1

def array_to_mac(data):
    return (str(int(data[0])) + ":" + str(int(data[1])) + ":" + str(int(data[2])) + ":" + str(int(data[3])) + ":" + str(int(data[4])) + ":" + str(int(data[5])))

def msg_install(data, comp):
    array = bytearray(16)
    array[VERSION] = SOFT_VERSION
    array[TYPE] = INSTALL
    for j in range (DATA, DATA+6) :
        array[j] = data[j]
    array[DATA+6] = comp
    crc_get(array)
    return array


def msg_install_from_mac(data, num):
    array = bytearray(16)
    array[VERSION] = SOFT_VERSION
    array[TYPE] = INSTALL
    for j in range (DATA, DATA+1) :
        array[j] = data[j-DATA]
    array[DATA+6] = num
    crc_get(array)
    return array

def msg_ama(amatype):
    array = bytearray(16)
    array[VERSION] = SOFT_VERSION
    array[TYPE]= AMA
    array[DATA] = amatype
    crc_get(array)
    return array

def msg_readressage():#Check why no mac
    array = bytearray(16)
    array[VERSION] = SOFT_VERSION
    array[TYPE] = ERROR
    array[DATA] = ERROR_GOTO
    array[DATA+1] = STATE_CONF
    return array

def msg_color(colors, ama= False):
    #print_flush(colors)
    l = len(Mesh.pixels) + len(Listen.deco)
    array = bytearray(l*3 + 4 + ceil((l*3 + 4)/7))
    array[VERSION] = SOFT_VERSION
    array[TYPE] = COLOR
    Mesh.sequence = (Mesh.sequence + 1) % 65536
    array[DATA] = Mesh.sequence // 256
    array[DATA+1] = Mesh.sequence % 256
    #print_flush(array[DATA], array[DATA+1], array[DATA]*256 + array[DATA+1])
    for v in Mesh.pixels.values():
        ((i,j), ind) = v
        if ( i != -1 and j != -1):
            if (ama ) :
                (r,v,b) = colors[ind/l][ind % l]
            else :
                (r,v,b) = colors[i][j]
        else:
            r= v= b= 0
        array[DATA + 2 + ind*3] = r
        array[DATA + 3 + ind*3] = v
        array[DATA + 4 + ind*3] = b
    for v in Listen.deco.values():
        ((i,j), ind) = v
        if ( i != -1 and j != -1):
            if (ama ) :
                (r,v,b) = colors[ind/l][ind % l]
            else :
                (r,v,b) = colors[i][j]
        else:
            r= v= b= 0
        array[DATA + 2 + ind*3] = r
        array[DATA + 3 + ind*3] = v
        array[DATA + 4 + ind*3] = b
    crc_get(array)
    return array

class Listen(Thread) :
    deco = {}
    unk = {}

    def __init__(self, com) :
        print_flush("Listen init")
        Thread.__init__(self)
        self.com = com
        self.allowed = False
        print_flush("Listen fin init")

    def run(self) :
        print_flush("Listen start")
        while True:
            if self.allowed :
                self.listen()

    def listen(self) :
        data = ""
        try :
            print_flush("Listening...")
            data = self.com.conn.recv(1500)
        except :
            pass
        if (data != "" and crc_check(data[0:16])) :
            #ajout message sur sentry
            if (data[TYPE] == ERROR) :
                array = bytearray(16)
                array[VERSION] = SOFT_VERSION
                array[TYPE] = ERROR
                array[DATA] = data[DATA]
                array[DATA+1] = data[DATA+1]
                for j in range (DATA+2, DATA+8) :
                    array[j] = data[j]
                #Setting flags...
                mac = array_to_mac(data[DATA+2 : DATA +8])
                if data[DATA] == ERROR_DECO :
                    Listen.deco[mac] = Mesh.pixels.pop(mac)
                    print_flush(Listen.deco)
                elif data[DATA] == ERROR_CO :
                    print_flush("known address : %s" % ('y' if mac in Listen.deco.keys() else 'n') )
                    if mac not in Listen.deco : # Raising UNK flag
                        Listen.unk[mac] = ((-1, -1),-1)
                        Websock.send_pos_unk(Listen.unk)
                        array[DATA+1] = array[DATA+1] | 32
                    else :
                        Mesh.pixels[mac] = Listen.deco.pop(mac)
                else :
                    print_flush("WTF????")
                print_flush("Received message, acquitting it", data)
                print_flush(Listen.deco, Listen.unk)
                array[DATA+1] = array[DATA+1] | 128
                crc_get(array)
                print_flush(array)
                self.com.conn.send(array)
                print_flush("acquitted")
            else :
                print_flush("received unintersting message...")

class Mesh(Thread):
    socket
    addressed = False
    ama = 0
    rows = 0
    cols = 0
    comp = 0
    pixels = {}
    sequence = 0

    def __init__(self, conn, addr):
        print_flush("Mesh init")
        Thread.__init__(self)
        #Communication with mes network config
        self.mesh_conn = conn
        self.mesh_addr = addr
        self.ama_check = False
        self.comp = 0
        self.model = Model(SchedulerState.get_rows(), SchedulerState.get_cols())
        print_flush("la matrice fait :" + str(SchedulerState.get_rows()) + str(SchedulerState.get_cols()))

        self.stopped = False
        self.l = Listen(self)
        self.l.start()
        #Communication with RabbitMQ config
        self.channel = None
        self.connection = None
        credentials = pika.PlainCredentials(os.environ['RABBITMQ_DEFAULT_USER'], os.environ['RABBITMQ_DEFAULT_PASS'])
        self.params = pika.ConnectionParameters(host='rabbit', credentials=credentials, heartbeat = 0)
        print_flush("Mesh fin init")

    def negative_model(self) :
        i = 0
        print_flush(self.model.get_height(), self.model.get_width())
        while(i < self.model.get_height()) :
            j = 0
            while (j < self.model.get_width()) :
                if (self.model.get_pixel(i,j) != (-1, -1, -1)):
                    return False
                j += 1
            i += 1
        return True

    def ama_care(self, dif):
        Mesh.pixels = json.loads(Websock.get_pixels())
        Listen.unk = json.loads(Websock.get_pos_unk())
        array = msg_color(self.model._model, self.ama_check)
        self.mesh_conn.send(array)
        if dif :
            self.ama_check = not self.ama_check

    def callback(self, ch, method, properties, body):
        #eviter de le faire dans tous les cas
        print_flush("Reached callback")
        # prev = self.model.copy()
        print_flush("Managed to copy model")
        print_flush(body)
        b = body.decode('ascii')
        print_flush(b)
        self.model.set_from_json(b, True)
        print_flush("Decripted JSON")
        if self.negative_model() :
            Mesh.ama += 1
            if Mesh.ama == 1 :
                Mesh.rows = SchedulerState.get_rows()
                Mesh.cols = SchedulerState.get_cols()
                array = msg_ama(AMA_INIT)
                self.mesh_conn.send(array)
            elif Mesh.ama == 2 :
                Mesh.addressed = True
                array = msg_ama(AMA_COLOR)
                self.mesh_conn.send(array)
            else :
                Mesh.ama = 1
                Websock.send_pos_unk(Listen.unk)
                array = msg_readressage()
                self.mesh_conn.send(array)
        elif (Mesh.ama == 1) :
            # dif = self.model.__eq__(prev)
            self.ama_care(dif)
        else :
            print_flush("Preparing to send colors...")
            array = msg_color(self.model._model)
            print_flush("Colors ready")
            self.mesh_conn.send(array)
            print_flush("Send colors")

    def send_table(self):
        pass
        #TODO


    def print_mesh_info(self):
        print_flush(" ========== Mesh ==========")
        print_flush("-------- Is mesh initialized :")
        print_flush(Mesh.addressed)
        print_flush("-------- Is Running?")
        print_flush("True")
        print_flush("-------- Pixels?")
        print_flush(Mesh.pixels)

    def get_mac(self) :
        data = "a"
        print_flush("on commence a recup les addr mac")
        while (self.comp != 2):#HARDCODE
            try :
                print_flush("on attend des données")
                data = self.mesh_conn.recv(1500)
                print_flush("on a reçu des données")
            except :
                print_flush(data)
                pass
            if (data != "a" and crc_check(data[0:16])) :
                if data[TYPE] == BEACON :
                    print_flush("BEACON : %d-%d-%d-%d-%d-%d" % (int(data[DATA]), int(data[DATA+1]), int(data[DATA+2]), int(data[DATA+3]), int(data[DATA+4]), int(data[DATA+5])))
                    mac = array_to_mac(data[DATA:DATA+6])
                    print_flush(mac)
                    if Mesh.pixels.get(mac) != None :
                        print_flush("already got the pixel " + mac)
                        continue
                    Mesh.pixels[mac]=((0,0), self.comp)
                    # Mesh.pixels[mac]=((-1,-1), self.comp)
                    Websock.send_pos_unk(Mesh.pixels)
                    array = msg_install(data, self.comp)
                    self.comp += 1
                    self.mesh_conn.send(array)
                    #time.sleep(1)
                else :
                    print_flush("A message was recieved but it is not a BEACON")
            elif data != "a" :
                print_flush("Empty message or invalid CRC", data)
        print_flush("end of get_mac function")

    def run(self):
        print_flush("start running ^^")
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
            array = msg_ama(AMA_INIT)
            self.mesh_conn.send(array)
            Mesh.ama = 2
            #FIN TEMPORAIRE

            self.channel.start_consuming()
        except Exception as e:
            if self.channel is not None:
                self.channel.close()
            if self.connection is not None:
                self.connection.close()
            raise e

    def close_socket(self) :
        print_flush("exiting thread, closing connection")
        self.mesh_conn.close()
        print_flush("Closed connection, exiting thread...")
        self.stopped = True

def main() :
    while True :
        Mesh.socket= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while True:
            try :
                Mesh.socket.bind((HOST, PORT))
                Mesh.socket.listen(5)
            except socket.error as msg:
                print_flush("Socket has failed :",msg)
                time.sleep(0.1)
                continue
            break
        print_flush(Mesh.socket)
        socket_thread = None
        print_flush("Socket opened, waiting for connection...")
        while True :
            print_flush("try to coonect")
            conn, addr = Mesh.socket.accept()
            print_flush("Connection accepted")
            if (socket_thread != None) :
                socket_thread.close_socket()
            socket_thread = Mesh(conn, addr)
            socket_thread.print_mesh_info()
            if (not Mesh.addressed):
                socket_thread.get_mac() # Ajouter un envoie de trmae vide lorsque la route à finie de remplir l=sa table de routage logique
            socket_thread.run()

if __name__ == '__main__' :
    print_flush("Yo")
    main()
