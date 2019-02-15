import socket
import select
import sys
import os, fcntl
import time
import threading
#import goto

# CONSTANTS

#Server state
initialisated = False
sequence = 0

# Connection
HOST='10.42.0.1'
#HOST='10.0.0.1'
PORT=8080
conn = None
addr = None
SOFT_VERSION = 1

#Frame's type
BEACON = 1
INSTALL = 3
COLOR = 4
AMA = 6
SLEEP = 8
AMA_INIT = 61
AMA_COLOR = 62
SLEEP_SERVER = 81
SLEEP_MESH = 82
SLEEP_WAKEUP = 89

#Field

VERSION = 0
TYPE = 1
DATA = 2
CHECKSUM = 15
FRAME_SIZE = 16

#Time temporisation
time_sleep = 1

#Controler
goon = 'y'
var = None

#Tab of MAC
tab=[]
comp = 0
dic = {}

#inputs for columns and rows
cols=2
rows=3

#Declaration of functions

def crc_get(frame) :
    offset = 0
    size = len(frame)
    b1 = b2 = b3 = b4 = b5 = b6 = 0
    for i in range(0, size-1) :
        B1 = (frame[i] & 1);
        B2 = (frame[i] & 2) >> 1;
        B3 = (frame[i] & 4) >> 2;
        B4 = (frame[i] & 8) >> 3;
        B5 = (frame[i] & 16) >> 4;
        B6 = (frame[i] & 32) >> 5;
        B7 = (frame[i] & 64) >> 6;
        B8 = (frame[i] & 128) >> 7;
        b1 = b1 + B1 + B2 + B3 + B4 + B5 + B6 + B7 + B8;
        b2 = b2 + B2 + B4 + B6 + B8;
        b3 = b3 + B1 + B3 + B5 + B7;
        if (offset == 0) :
            b4 = b4 + B8 + B5 + B2
            b5 = b5 + B7 + B4 + B1
            b6 = b6 + B6 + B3
        elif offset == 1 :
            b4 = b4 + B7 + B4 + B1
            b5 = b5 + B6 + B3
            b6 = b6 + B8 + B5 + B2
        else :
            b4 = b4 + B6 + B3
            b5 = b5 + B8 + B5 + B2
            b6 = b6 + B7 + B4 + B1
        offset = (offset + 1)%3
    crc = b1%2 << 6 | b2%2 << 5 | b3%2 << 4 | b4%2 << 3 | b5%2 << 2 | b6%2 << 1 | (b1 + b2 + b3 + b4 + b5 + b6)%2
    frame[size-1] = crc

def crc_check(frame) :
    offset = 0
    size = len(frame)
    b1 = b2 = b3 = b4 = b5 = b6 = 0
    for i in range(0, size-1) :
        B1 = (frame[i] & 1);
        B2 = (frame[i] & 2) >> 1;
        B3 = (frame[i] & 4) >> 2;
        B4 = (frame[i] & 8) >> 3;
        B5 = (frame[i] & 16) >> 4;
        B6 = (frame[i] & 32) >> 5;
        B7 = (frame[i] & 64) >> 6;
        B8 = (frame[i] & 128) >> 7;
        b1 = b1 + B1 + B2 + B3 + B4 + B5 + B6 + B7 + B8;
        b2 = b2 + B2 + B4 + B6 + B8;
        b3 = b3 + B1 + B3 + B5 + B7;
        if (offset == 0) :
            b4 = b4 + B8 + B5 + B2
            b5 = b5 + B7 + B4 + B1
            b6 = b6 + B6 + B3
        elif offset == 1 :
            b4 = b4 + B7 + B4 + B1
            b5 = b5 + B6 + B3
            b6 = b6 + B8 + B5 + B2
        else :
            b4 = b4 + B6 + B3
            b5 = b5 + B8 + B5 + B2
            b6 = b6 + B7 + B4 + B1
        offset = (offset + 1)%3
    crc = b1%2 << 6 | b2%2 << 5 | b3%2 << 4 | b4%2 << 3 | b5%2 << 2 | b6%2 << 1 | (b1 + b2 + b3 + b4 + b5 + b6)%2
    return frame[size-1] == crc

def msg_install(data):
    global comp
    array = bytearray(16)
    array[VERSION] = SOFT_VERSION
    array[TYPE] = INSTALL
    for j in range (DATA, DATA+6) :
        array[j] = data[j]
    array[DATA+6] = comp
    comp+=1
    crc_get(array)
    return array

def msg_install_from_mac(data, num):
    global comp
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
    global sequence
    print(colors)
    array = bytearray(len(dic)*3 + 5)
    array[VERSION] = SOFT_VERSION
    array[TYPE] = COLOR
    sequence = (sequence + 1) % 65536
    array[DATA] = sequence // 256
    array[DATA+1] = sequence % 256
    print(array[DATA], array[DATA+1], array[DATA]*256 + array[DATA+1])
    for k in range(0, len(dic)):
        ((i, j), mac) = dic.get(k)
        if ( i != -1 and j != -1 and k != ama):
            print(k,i, j, colors[i][j])
            (r,v,b) = colors[i][j]
        elif (k != ama) :
            r= v= b= 0
        else :
            print(k,i,j, col)
            (r,v,b) = col
        array[DATA + 2 + k*3] = r
        array[DATA + 3 + k*3] = v
        array[DATA + 4 + k*3] = b
    crc_get(array)
    return array

def state_color():
    global goon
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
        for i in range(0, rows) :
            line = []
            for j in range(0, cols) :
                line.append(color_selection[color_selecter])
                color_selecter = (color_selecter + 1) % 4
            color.append(line)
        sequence.append(color)
    i=0
    goon = 'Y'
    print("entre dans l'etape color")
    turn = 0
    while (turn < 200):
        array = msg_color(sequence[i])
        conn.send(array)
        time.sleep(0.1)
        i = (i+1) % 4
        turn += 1

def state_ama():#Corriger les trames de verifications.  
    global dic, conn, var
    R = (255,0,0)
    G = (0,255,0)
    D = (0,0,0)
    color = []
    for k in range(0, rows) :
        line = []
        for i in range(0, cols) :
            line.append(D)
        color.append(line)
    array = msg_ama(AMA_INIT)
    conn.send(array)
    i = 0
    while i < len(dic): #'for i in range' is not affected by i modification, it's an enumeration.
        ((col, row), mac)=dic.get(i)
        print("Sent color to %d:%d:%d:%d:%d:%d" % (int(mac[0]), int(mac[1]), int(mac[2]), int(mac[3]), int(mac[4]), int(mac[5])))
        array=msg_color(color, i, R)
        print(array)
        conn.send(array)
        print("allumage en rouge envoyé")
        (x, y) = eval(input("Which pixel is red ? (row, col)"))
        dic[i]=((x,y), mac)
        print(x, y)
        time.sleep(1)
        color[x][y] = G#No verification possible??
        array = msg_color(color)#, i, G)
        print(array)
        conn.send(array)
        color[x][y] = D
        print("allumage en green envoyé")
        ok = input("continue addressage? [Y/n]")
        #array = msg_color(color, i, D)
        #conn.send(array)
        #print("extinction du pixel envoyé")
        if (ok != 'n') :
            i+=1
    array = msg_ama(AMA_COLOR)
    conn.send(array)

def initialisation():
    global conn, addr, s, rows, cols
    # socket creation
    rows = int(input("Please enter number of rows : "))
    cols = int(input("Please enter number of columns : "))
    
    s= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print("Socket has been created")
    # socket binding
    while True:
        try :
            s.bind((HOST, PORT))
            s.listen(11)
        except socket.error as msg:
            continue
            print("Binding has failed\n Err code :" + str(msg[0]) + "\n msg : " + msg[1])
            sys.exit()  
        break
    # what is it for ?


def set_connection():
    global conn, addr, s, initialisated
    while (conn == None) :
        try :
            (conn, addr) = s.accept()
        except :
            continue
    initialisated = True
    print("server connected")

def wake_up() :
    global conn, addr, s, var, tab, dic, comp
    set_wakeup()
    print("server restarted, check if all cards are awake")
    temp = []
    comp = 0
    while (len(temp) != len(tab)) :
        try :
            data = conn.recv(1500)
        except :
            pass
        if (data != "" and crc_check(data)) :
            if data[0] == BEACON :
                print("BEACON : %d-%d-%d-%d-%d-%d" % (int(data[DATA]), int(data[DATA+1]), int(data[DATA+2]), int(data[DATA+3]), int(data[DATA+4]), int(data[DATA+5])))
                mac = [int(data[DATA]), int(data[DATA+1]), int(data[DATA+2]), int(data[DATA+3]), int(data[DATA+4]), int(data[DATA+5])]
                if mac not in tab :
                    print("Unknown card, rejected")
                    continue
                if mac in temp :
                    print("Card already acquitted")
                    continue
                #via tabular use
                temp.append([])
                for j in range (1, 7) :
                    temp[comp].append(int(data[j]))
                array = bytearray(16)
                array[VERSION] = SOFT_VERSION
                array[TYPE] = INSTALL
                for j in range (DATA, DATA+6) :
                    array[j] = data[j]
                for key, value in dic.items() :
                    ((x1, y1), mac1) = value
                    if mac == mac1 :
                        array[DATA+6] = key
                comp+=1
                crc_get(array)
                conn.send(array)
                time.sleep(1)
            else :
                print("A message was recieved but it is not a BEACON")
            print("Still waiting for "+ str(len(tab)-len(temp)) +" cards");
    print("All cards connected, going back into COLORS")
    array = msg_ama(AMA_INIT)
    conn.send(array)
    time.sleep(1)
    #If necessary : re-do addr here (on error on wakeup)
    array = msg_ama(AMA_COLOR)
    conn.send(array)
    time.sleep(1)

    
def get_macs():
    global conn, addr, goon, var, tab, dic, comp
    data = ""
    while((goon != 'n') or (var == 'AMA')):
        try :
            data = conn.recv(1500)
        except :
            pass
        if (data != "" and crc_check(data[0:16])) :
            if data[TYPE] == BEACON :
                print("BEACON : %d-%d-%d-%d-%d-%d" % (int(data[DATA]), int(data[DATA+1]), int(data[DATA+2]), int(data[DATA+3]), int(data[DATA+4]), int(data[DATA+5])))
                mac = [int(data[DATA]), int(data[DATA+1]), int(data[DATA+2]), int(data[DATA+3]), int(data[DATA+4]), int(data[DATA+5])]
                if mac in tab :
                    print("already got this")
                    continue
                #via dictionnary use
                dic[comp]=((-1,-1), data[DATA:DATA+6])
                #via tabular use
                tab.append([])
                for j in range (DATA, DATA+6) :
                    tab[comp].append(int(data[j]))
                array = msg_install(data)
                conn.send(array)
                time.sleep(1)
            else :
                print("A message was recieved but it is not a BEACON")
            goon = input("Would you like to keep going on recieving mac addresses ? [Y/n]")
        else :
            print("Empty message or invalid CRC")

def set_sleep() :
    array = bytearray(16)
    array[VERSION] = SOFT_VERSION
    array[TYPE] = SLEEP
    array[DATA] = SLEEP_SERVER
    crc_get(array)
    conn.send(array)
    time.sleep(10)
    
def set_wakeup() :
    array = bytearray(16)
    array[VERSION] = SOFT_VERSION
    array[TYPE] = SLEEP
    array[DATA] = SLEEP_WAKEUP
    crc_get(array)
    conn.send(array)

def close_co():
    if(conn != None):
        conn.close()
    if(addr != None):
        addr.close()

def clean() : #DEBUG FUNCTION, NOT TO BE KEPT
    is_readable = [s]
    is_writable = []
    is_error = []
    r, w, e = select.select(is_readable, is_writable, is_error, 1.0)
    while r :
        data = conn.recv(1500)
        print(data, len(data))
        r, w, e = select.select(is_readable, is_writable, is_error, 1.0)

def stop() :
    while(1):
        var= input()
        if (var == 'c'):
            close_co()
            sys.exit()

def main() : #Kinda main-like. You can still put executable code between function to do tests outside of main
    while True :
        try :
            if (not initialisated) :
                #threading.Thread(target=stop).start()
                initialisation()
                set_connection()
                get_macs()
                state_ama()
                state_color()
                set_sleep()
            else :
                
                wake_up()
                state_color()
        except :
            print("error")
            close_co()
            sys.exit()

if __name__ == '__main__' :
    main()
