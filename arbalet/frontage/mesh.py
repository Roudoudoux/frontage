from server.flaskutils import print_flush

print_flush("ola")
import socket
import select
import sys
import os, fcntl
import time
from threading import Thread, Lock
from math import ceil
from utils.crc import *
from utils.websock import Websock
#import goto

# CONSTANTS

# Connection
HOST='10.42.0.1'
#HOST='10.0.0.1'
PORT=8080
SOFT_VERSION = 1

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

def msg_readressage():
    array = bytearray(16)
    array[VERSION] = SOFT_VERSION
    array[TYPE] = ERROR
    array[DATA] = ERROR_GOTO
    array[DATA+1] = STATE_CONF

def msg_color(colors, ama= False):
    #print(colors)
    l = max(len(Mesh.pixels), Mesh.rows*Mesh.cols)
    array = bytearray(l*3 + 4 + ceil((l*3 + 4)/7))
    array[VERSION] = SOFT_VERSION
    array[TYPE] = COLOR
    Mesh.sequence = (Mesh.sequence + 1) % 65536
    array[DATA] = Mesh.sequence // 256
    array[DATA+1] = Mesh.sequence % 256
    #print(array[DATA], array[DATA+1], array[DATA]*256 + array[DATA+1])
    for v in [ val[1] for val in Mesh.pixels.values()):
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

    def __init__(self, com) :
        print("Listen init")
        Thread.__init__(self)
        self.com = com
        self.deco = []
        self.unk = []
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
                    self.deco.append(data[DATA+2:DATA+8])
                    print(self.deco)
                elif data[DATA] == ERROR_CO :
                    print("known address : %s" % ('y' if data[DATA+2:DATA+8] in self.deco else 'n') )
                    if data[DATA+2:DATA+8] not in self.deco : # Raising UNK flag
                        self.unk.append(data[DATA+2:DATA+8])
                        #ajout export sur REDIS
                        array[DATA+1] = array[DATA+1] | 32
                    else :
                        self.deco.remove(data[DATA+2:DATA+8])
                else :
                    print("WTF????")
                print("Received message, acquitting it", data)
                print(self.deco, self.unk)
                array[DATA+1] = array[DATA+1] | 128
                crc_get(array)
                print(array)
                self.com.conn.send(array)
                print("acquitted")
            else :
                print("received unintersting message...")

class Main_communication(Thread) :
    addressed = False
    rows = 0
    cols = 0
    tab=[]
    comp = 0
    dic = {'default':((-1,-1),-1)}
    sequence = 0

    def __init__(self, conn, addr) :
        Thread.__init__(self)
        self.conn = conn
        self.addr = addr
        if !Main_communication.addressed :
            self.state = 1
        else :
            self.state = 2
        self.stopped = False
        self.l = Listen(self)
        self.l.start() # run ?

    def run(self) :
        self.state_machine()
        print("exiting thread")

    def state_machine(self) :
        print("Entering state machine")
        while True :
            Lockstate.acquire(1)
            if(self.state == 1):
                Lockstate.release()
                self.get_mac()
            elif (self.state == 2):
                Lockstate.release()
                self.l.allowed = True
                self.state_ama()
            else :
                Lockstate.release()
                self.state_color()
        # if not Main_communication.addressed :
        #     Main_communication.addressed = True
        #     self.l.allowed = True
        # else :
        #     self.send_table()
        # while True :
        #     self.state_color() #Todo : send only one message at a time.
        #     if (self.stopped) :
        #         return

    def send_table(self) :
        print(Main_communication.tab, Main_communication.dic)
        print("Todo, send table to new root")

    def get_mac(self) :
        data = ""
        # while (self.state == 1):
        #     Lockstate.release()
        try :
            data = self.conn.recv(1500)
        except :
            pass
        if (data != "" and crc_check(data[0:16])) :
            if data[TYPE] == BEACON :
                print("BEACON : %d-%d-%d-%d-%d-%d" % (int(data[DATA]), int(data[DATA+1]), int(data[DATA+2]), int(data[DATA+3]), int(data[DATA+4]), int(data[DATA+5])))
                mac = [int(data[DATA]), int(data[DATA+1]), int(data[DATA+2]), int(data[DATA+3]), int(data[DATA+4]), int(data[DATA+5])]
                if mac in Main_communication.tab :
                    print("already got this")
                    continue
                Main_communication.pos_unknown[data[DATA:DATA+6]]=((-1,-1), comp)
                #TODO publish on REDIS

                # #via dictionnary use
                # Main_communication.dic[self.comp]=((-1,-1), data[DATA:DATA+6])
                # #via tabular use
                # Main_communication.tab.append([])
                # for j in range (DATA, DATA+6) :
                #     Main_communication.tab[self.comp].append(int(data[j]))
                array = msg_install(data, self.comp)
                self.comp += 1
                self.conn.send(array)
                #time.sleep(1)
            else :
                print("A message was recieved but it is not a BEACON")
        else :
            print("Empty message or invalid CRC")
            #Lockstate.acquire(1)

    def state_ama(self):
        R = (255,0,0)
        G = (0,255,0)
        D = (0,0,0)
        color = []
        for k in range(0, Main_communication.rows) :
            line = []
            for i in range(0, Main_communication.cols) :
                line.append(D)
            color.append(line)
        array = msg_ama(AMA_INIT)
        self.conn.send(array)
        i = 0
        while i < len(self.dic): #'for i in range' is not affected by i modification, it's an enumeration.
            ((col, row), mac)=Main_communication.dic.get(i)
            print("Sent color to %d:%d:%d:%d:%d:%d" % (int(mac[0]), int(mac[1]), int(mac[2]), int(mac[3]), int(mac[4]), int(mac[5])))
            array=msg_color(color, i, R)
            print(array)
            self.conn.send(array)
            print("allumage en rouge envoyé")
            (x, y) = eval(input("Which pixel is red ? (row, col)"))
            Main_communication.dic[i]=((x,y), mac)
            print(x, y)
            time.sleep(1)
            color[x][y] = G
            array = msg_color(color)#, i, G)
            print(array)
            self.conn.send(array)
            color[x][y] = D
            print("allumage en green envoyé")
            ok = input("continue addressage? [Y/n]")
            #array = msg_color(color, i, D)
            #conn.send(array)
            #print("extinction du pixel envoyé")
            if (ok != 'n') :
                i+=1
        array = msg_ama(AMA_COLOR)
        self.conn.send(array)

    def state_color(self, data):
        #recupere les matrices color sur RabbitMQ
        #compute le tableau avec msg_color
        #envoie la frame au mesh network
        array = msg_color()
            self.conn.send(array)
            time.sleep(1)
            i = (i+1) % 4
            turn += 1

    def close_socket(self) :
        print("exiting thread, closing connection")
        self.conn.close()
        print("Closed connection, exiting thread...")
        self.stopped = True

class Mesh(Thread):
    addressed = False
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
        #attributs for
        self.ama_check = False
        self.comp = 0
        self.model = Model(get_rows(), get_cols())
        self.stopped = False
        #Communication with RabbitMQ config
        self.channel = None
        self.connection = None
        credentials = pika.PlainCredentials(environ['RABBITMQ_DEFAULT_USER'], environ['RABBITMQ_DEFAULT_PASS'])
        self.params = pika.ConnectionParameters(host='localhost', credentials=credentials, connection_attempts = 100, heartbeat = 0)

    def negative_model() :
        i = 0
        while(i < self.model.get_height()) :
            j = 0
            while (j < self.model.get_width()) :
                if (self.model.get_pixel(i,j) != (-1, -1, -1)):
                    return False
                j += 1
            i += 1
        return True

    def ama_care():
        array = msg_color(self.model, self.ama_check)
        self.mesh_conn.send(array)
        self.ama_check = !(self.ama_check)

    def callback(self, ch, method, properties, body):
        self.model.set_from_json(body.decode('ascii'))
        if (!Mesh.addressed && self.negative_model() :
            self.ama += 1
            if self.ama == 1 :
                Mesh.rows = get_rows();
                Mesh.cols = get_cols();
                array = msg_ama(AMA_INIT)
                self.mesh_conn.send(array)
            elif self.ama == 2 :
                array = msg_ama(AMA_COLOR)
                self.mesh_conn.send(array)
            else :
                self.ama = 1
                array = msg_readressage()
                self.mesh_conn.send(array)
        elif (!Mesh.addressed && ama == 1) :
            self.ama_care()
        else :
            array = self.mesh_color()
            self.mesh_conn.send(array)

    def get_mac(self) :
        data = "a"
        while (data != ""):
        try :
            data = self.conn.recv(1500)
        except :
            pass
        if (data != "" and crc_check(data[0:16])) :
            if data[TYPE] == BEACON :
                print("BEACON : %d-%d-%d-%d-%d-%d" % (int(data[DATA]), int(data[DATA+1]), int(data[DATA+2]), int(data[DATA+3]), int(data[DATA+4]), int(data[DATA+5])))
                mac = [int(data[DATA]), int(data[DATA+1]), int(data[DATA+2]), int(data[DATA+3]), int(data[DATA+4]), int(data[DATA+5])]
                if mac in Main_communication.tab :
                    print("already got this")
                    continue
                Mesh.pixels[data[DATA:DATA+6]]=((-1,-1), self.comp)
                Websock.send_pos_unk(Mesh.pixels)
                array = msg_install(data, self.comp)
                self.comp += 1
                self.conn.send(array)
                #time.sleep(1)
            else :
                print("A message was recieved but it is not a BEACON")
        else :
            print("Empty message or invalid CRC")

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
            self.close_dmx()
            if self.channel is not None:
                self.channel.close()
            if self.connection is not None:
                self.connection.close()
            raise e

    def close_socket(self) :
        print("exiting thread, closing connection")
        self.conn.close()
        print("Closed connection, exiting thread...")
        self.stopped = True

def main() : #Kinda main-like. You can still put executable code between function to do tests outside of main
    while True :
        Mesh.socket= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while True:
            try :
                Main_communication.s.bind((HOST, PORT))
                Mesh.socket.listen(5)
            except socket.error as msg:
                continue
                print("Binding has failed\n Err code :" + str(msg[0]) + "\n msg : " + msg[1])
                sys.exit()
            break
        socket_thread = None
        print("Socket opened, waiting for connection...")
        while True :
            conn, addr = Mesh.socket.accept()
            print("Connection accepted")
            if (socket_thread != None) :
                socket_thread.close_socket()
            socket_thread = Mesh(conn, addr)
            socket_thread.run()

if __name__ == '__main__' :
    main()
