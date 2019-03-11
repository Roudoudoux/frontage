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

import struct

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', bytes(ifname[:15], 'utf-8'))
    )[20:24])

#import goto

# CONSTANTS

# Connection
HOST='0.0.0.0'#str(get_ip_address('eth0'))
#HOST='10.0.0.1'
PORT=9988
SOFT_VERSION = 1

print("")
print("")
print("")
print(HOST)
print("")
print("")
print("")

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
    #print(colors)
    l = len(Mesh.pixels) + len(Listen.deco)
    array = bytearray(l*3 + 4 + ceil((l*3 + 4)/7))
    array[VERSION] = SOFT_VERSION
    array[TYPE] = COLOR
    Mesh.sequence = (Mesh.sequence + 1) % 65536
    array[DATA] = Mesh.sequence // 256
    array[DATA+1] = Mesh.sequence % 256
    #print(array[DATA], array[DATA+1], array[DATA]*256 + array[DATA+1])
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
        print("Listen init")
        Thread.__init__(self)
        self.com = com
        self.allowed = False

    def run(self) :
        print("Listen start")
        while True:
            if self.allowed :
                self.listen()

    def listen(self) :
        print("Listening...")
        data = ""
        try :
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
                if data[DATA] == ERROR_DECO :
                    Listen.deco[data[DATA+2:DATA+8]] = Mesh.pixels.pop(data[DATA+2:DATA+8])
                    print(Listen.deco)
                elif data[DATA] == ERROR_CO :
                    print("known address : %s" % ('y' if data[DATA+2:DATA+8] in Listen.deco.keys() else 'n') )
                    if data[DATA+2:DATA+8] not in Listen.deco : # Raising UNK flag
                        Listen.unk[data[DATA+2:DATA+8]] = ((-1, -1),-1)
                        Websock.send_pos_unk(Listen.unk)
                        array[DATA+1] = array[DATA+1] | 32
                    else :
                        Mesh.pixels[data[DATA+2:DATA+8]] = Listen.deco.pop(data[DATA+2:DATA+8])
                else :
                    print("WTF????")
                print("Received message, acquitting it", data)
                print(Listen.deco, Listen.unk)
                array[DATA+1] = array[DATA+1] | 128
                crc_get(array)
                print(array)
                self.com.conn.send(array)
                print("acquitted")
            else :
                print("received unintersting message...")

class Mesh(Thread):
    addressed = False
    ama = 0
    rows = 0
    cols = 0
    comp = 0
    pixels = {}
    sequence = 0

    def __init__(self, conn, addr):
        Thread.__init__(self)
        #Communication with mes network config
        self.mesh_conn = conn
        self.mesh_addr = addr
        self.ama_check = False
        self.comp = 0
        self.model = Model(SchedulerState.get_rows(), SchedulerState.get_cols())
        self.stopped = False
        self.l = Listen(self)
        self.l.start()
        #Communication with RabbitMQ config
        self.channel = None
        self.connection = None
        credentials = pika.PlainCredentials(os.environ['RABBITMQ_DEFAULT_USER'], os.environ['RABBITMQ_DEFAULT_PASS'])
        self.params = pika.ConnectionParameters(host='localhost', credentials=credentials, connection_attempts = 100, heartbeat = 0)

    def negative_model(self) :
        i = 0
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
        prev = self.model.copy()
        curr = self.model.set_from_json(body.decode('ascii'))
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
            dif = prev.model.__eq__(curr)
            self.ama_care(dif)
        else :
            array = msg_color(self.model._model)
            self.mesh_conn.send(array)

    def send_table(self):
        pass
        #TODO

    def get_mac(self) :
        data = "a"
        while (self.comp != 4):#HARDCODE
            try :
                data = self.conn.recv(1500)
            except :
                pass
            if (data != "a" and crc_check(data[0:16])) :
                if data[TYPE] == BEACON :
                    print("BEACON : %d-%d-%d-%d-%d-%d" % (int(data[DATA]), int(data[DATA+1]), int(data[DATA+2]), int(data[DATA+3]), int(data[DATA+4]), int(data[DATA+5])))
                    mac = [int(data[DATA]), int(data[DATA+1]), int(data[DATA+2]), int(data[DATA+3]), int(data[DATA+4]), int(data[DATA+5])]
                    if Mesh.pixels[mac] :
                        print("already got this")
                        continue
                    Mesh.pixels[data[DATA:DATA+6]]=((-1,-1), self.comp)
                    Websock.send_pos_unk(Mesh.pixels)
                    array = msg_install(data, self.comp)
                    self.comp += 1
                    self.mesh_conn.send(array)
                    #time.sleep(1)
                else :
                    print("A message was recieved but it is not a BEACON")
            elif data != "a" :
                print("Empty message or invalid CRC", data)

    def run(self):
        try:
            self.connection = pika.BlockingConnection(self.params)
            self.channel = self.connection.channel()

            self.channel.exchange_declare(exchange='pixels', exchange_type='fanout')

            result = self.channel.queue_declare(exclusive=True, arguments={"x-max-length": 1})
            queue_name = result.method.queue

            self.channel.queue_bind(exchange='pixels', queue=queue_name)
            self.channel.basic_consume(self.callback, queue=queue_name, no_ack=True)

            print('Waiting for pixel data on queue "{}".'.format(queue_name))
            self.channel.start_consuming()
        except Exception as e:
            if self.channel is not None:
                self.channel.close()
            if self.connection is not None:
                self.connection.close()
            raise e

    def close_socket(self) :
        print("exiting thread, closing connection")
        self.mesh_conn.close()
        print("Closed connection, exiting thread...")
        self.stopped = True

def main() : #Kinda main-like. You can still put executable code between function to do tests outside of main
    while True :
        Mesh.socket= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while True:
            try :
                Mesh.socket.bind((HOST, PORT))
                Mesh.socket.listen(5)
            except socket.error as msg:
                print("Socket has failed :",msg)
                time.sleep(0.1)
                continue
            break
        socket_thread = None
        print("Socket opened, waiting for connection...") 
        while True :
            conn, addr = Mesh.socket.accept()
            print("Connection accepted")
            if (socket_thread != None) :
                socket_thread.close_socket()
            socket_thread = Mesh(conn, addr)
            if (not Mesh.addressed):
                socket_thread.get_mac() # Ajouter un envoie de trmae vide lorsque la route à finie de remplir l=sa table de routage logique
            socket_thread.run()

if __name__ == '__main__' :
    print("Yo")
    main()
