import socket
import select
import sys
import os, fcntl
import time
from threading import Thread
from math import ceil
from crc import *
#import goto
# CONSTANTS

# Connection
HOST='10.42.0.1'
#HOST='10.0.0.1'
PORT=9988
SOFT_VERSION = 1

#Frame's type
BEACON = 1
INSTALL = 3
COLOR = 4
AMA = 6
ERROR = 7
AMA_INIT = 61
AMA_COLOR = 62
ERROR_CO = 71
ERROR_DECO = 72
ERROR_GOTO = 73
REBOOT = 8
#Field

VERSION = 0
TYPE = 1
DATA = 2
FRAME_SIZE = 16

#Declaration of functions - Utils

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

def msg_color(colors, ama= -1, col= None):
    #print(colors)
    array = bytearray(len(Main_communication.dic)*3 + 4 + ceil((len(Main_communication.dic)*3 + 4)/7))
    array[VERSION] = SOFT_VERSION
    array[TYPE] = COLOR
    Main_communication.sequence = (Main_communication.sequence + 1) % 65536
    array[DATA] = Main_communication.sequence // 256
    array[DATA+1] = Main_communication.sequence % 256
    #print(array[DATA], array[DATA+1], array[DATA]*256 + array[DATA+1])
    for k in range(0, len(Main_communication.dic)):
        ((i, j), mac) = Main_communication.dic.get(k)
        if ( i != -1 and j != -1 and k != ama):
            #print(k,i, j, colors[i][j])
            (r,v,b) = colors[i][j]
        elif (k != ama) :
            r= v= b= 0
        else :
            #print(k,i,j, col)
            (r,v,b) = col
        array[DATA + 2 + k*3] = r
        array[DATA + 3 + k*3] = v
        array[DATA + 4 + k*3] = b
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

    def reboot(self):
        print("start reboot")
        self.unk = []
        self.deco = []
        array = bytearray(FRAME_SIZE)
        array[VERSION] = SOFT_VERSION
        array[TYPE] = REBOOT
        array[DATA] = 100 // 256
        array[DATA+1] = 100 %256
        crc_get(array)
        self.com.conn.send(array)
        print("I've sent {}".format(array))

    def listen(self) :
        print("Listening...")
        data = ""
        try :
            data = self.com.conn.recv(1500)
        except :
            pass
        if (data != "" and crc_check(data[0:16])) :
            if (data[TYPE] == ERROR) :
                print("Received data :", data)
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
    dic = {}
    sequence = 0

    def __init__(self, conn, addr) :
        Thread.__init__(self)
        self.conn = conn
        self.addr = addr
        self.stopped = False
        self.l = Listen(self)
        self.l.start()

    def run(self) :
        self.state_machine()
        print("exiting thread")

    def reboot(self):
        Main_communication.addressed = False
        Main_communication.comp = 0
        Main_communication.sequence = 0
        Main_communication.dic = {}
        Main_communication.tab = []
        self.l.reboot()

    def state_machine(self) :
        print("Entering state machine")
        if not Main_communication.addressed :
            self.get_macs()
            self.state_ama()
            Main_communication.addressed = True
            self.l.allowed = True
        else :
            self.l.allowed = True
            self.send_table()
        while True :
            self.state_color() #Todo : send only one message at a time.
            if (self.stopped) :
                return

    def send_table(self) :
        print(Main_communication.tab, Main_communication.dic)
        print("Todo, send table to new root")

    def get_macs(self) :
        data = ""
        goon = 'y'
        while (goon != 'n'):
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
                    #via dictionnary use
                    Main_communication.dic[self.comp]=((-1,-1), data[DATA:DATA+6])
                    #via tabular use
                    Main_communication.tab.append([])
                    for j in range (DATA, DATA+6) :
                        Main_communication.tab[self.comp].append(int(data[j]))
                    array = msg_install(data, self.comp)
                    self.comp += 1
                    self.conn.send(array)
                    time.sleep(1)
                else :
                    print("A message was recieved but it is not a BEACON")
                goon = input("Would you like to keep going on recieving mac addresses ? [Y/n]")
                if (goon == 'reboot'):
                    self.reboot()
            else :
                print("Empty message or invalid CRC")

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
            elif (ok == 'reboot'):
                self.reboot()
        array = msg_ama(AMA_COLOR)
        self.conn.send(array)

    def state_color(self):
        R = (255,0,0)
        G = (0,255,0)
        B = (0,0,255)
        W = (255,255,255)

        sequence = []
        color_selection = [R, G, B, W]

        #generation of a 4-couloured pattern long sequence
        #which will be displayed by the esp32
        for k in range(0,4) :
            color = []
            color_selecter = k
            for i in range(0, Main_communication.rows) :
                line = []
                for j in range(0, Main_communication.cols) :
                    line.append(color_selection[color_selecter])
                    color_selecter = (color_selecter + 1) % 4
                color.append(line)
            sequence.append(color)
        i=0
        turn = 0
        while (turn < 4):
            array = msg_color(sequence[i])
            self.conn.send(array)
            time.sleep(1)
            i = (i+1) % 4
            turn += 1

    def close_socket(self) :
        print("exiting thread, closing connection")
        self.conn.close()
        print("Closed connection, exiting thread...")
        self.stopped = True

def main() : #Kinda main-like. You can still put executable code between function to do tests outside of main
    while True :
        Main_communication.rows = int(input("Please enter number of rows : "))
        Main_communication.cols = int(input("Please enter number of columns : "))
        Main_communication.s= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while True:
            try :
                Main_communication.s.bind((HOST, PORT))
                Main_communication.s.listen(5)
            except socket.error as msg:
                continue
                print("Binding has failed\n Err code :" + str(msg[0]) + "\n msg : " + msg[1])
                sys.exit()
            break
        socket_thread = None
        print("Socket opened, waiting for connection...")
        print(Main_communication.s)
        while True :
            if socket_thread is not None:
                r = input("reboot ? [y/N]")
                if (r != 'y') :
                    socket_thread.reboot()
            conn, addr = Main_communication.s.accept()
            print("Connection accepted")
            if (socket_thread != None) :
                socket_thread.close_socket()
            socket_thread = Main_communication(conn, addr)
            socket_thread.start()

if __name__ == '__main__' :
    main()
