import socket
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
WAKE_UP = 89

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
#Declaration of functions

def variable_crc_computer(frame, length, offset, frequency) :
    crc_bool = 0
    i = offset

    if frame != None :
        while (i < length) :
            crc_bool = crc_bool + frame[i]
            i = i + frequency
    return crc_bool % 2

def frame_crc_computer(frame, length, crc_table) :
    if (frame != None) :
        crc_table[0] = variable_crc_computer(frame, length, 0, 1)
        crc_table[1] = variable_crc_computer(frame, length, 0, 2)
        crc_table[2] = variable_crc_computer(frame, length, 1, 2)
        crc_table[3] = variable_crc_computer(frame, length, 0, 3)
        crc_table[4] = variable_crc_computer(frame, length, 1, 3)
        crc_table[5] = variable_crc_computer(frame, length, 2, 3)
        crc_table[6] = sum(crc_table)%2

def crc_get(frame) :
    crc_table = [0] * 7
    size = len(frame) 
    frame2 = [0] * (size-1) * 8
    for i in range(0, size-1) :
        for j in range(0, 8) :
            frame2[(i*8)+j] = (frame[i] & (1 << j)) >> j
    frame_crc_computer(frame2, (size - 1)*8, crc_table)
    crc = crc_table[0] << 6 | crc_table[1] << 5 | crc_table[2] << 4 | crc_table[3] << 3 | crc_table[4] << 2 | crc_table[5] << 1 | crc_table[6]
    frame[size-1] = crc

def crc_check(frame) :
    print(frame)
    crc_table = [0] * 7
    size = len(frame) 
    frame2 = [0] * (size-1) * 8
    for i in range(0, size-1) :
        for j in range(0, 8) :
            frame2[(i*8)+j] = (frame[i] & (1 << j)) >> j
    frame_crc_computer(frame2, (size - 1)*8, crc_table)
    crc = crc_table[0] << 6 | crc_table[1] << 5 | crc_table[2] << 4 | crc_table[3] << 3 | crc_table[4] << 2 | crc_table[5] << 1 | crc_table[6]
    print("Comparing CRC "+str(frame[size-1])+" and "+str(crc))
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
    color1 = [[R,G],[B,W]]
    color2 = [[W,R],[G,B]]
    color3 = [[B,W],[R,G]]
    color4 = [[G,B],[W,R]]
    sequence = [color1, color2, color3, color4]
    i=0
    goon = 'Y'
    print("entre dans l'etape color")
    turn = 0
    while (turn < 200):
        array = msg_color(sequence[i])
        conn.send(array)
        time.sleep(1)
        i = (i+1) % 4
        turn += 1

def state_ama():
    global dic, conn, var
    R = (255,0,0)
    G = (0,255,0)
    D = (0,0,0)
    color = [[D,D],[D,D]]
    array = msg_ama(AMA_INIT)
    conn.send(array)
    for i in range(0, len(dic)):
        ((col, row), mac)=dic.get(i)
        print("Sent color to %d:%d:%d:%d:%d:%d" % (int(mac[0]), int(mac[1]), int(mac[2]), int(mac[3]), int(mac[4]), int(mac[5])))
        array=msg_color(color, i, R)
        print(array)
        conn.send(array)
        print("allumage en rouge envoyé")
        #label .pause
        (x, y) = eval(input("Which pixel is red ? (row, col)"))
        #x = input("Row of the pixel lighting in red")
        #y = input("Col of the pixel lighting in red")
        dic[i]=((x,y), mac)
        print(x, y)
        time.sleep(1)
        array = msg_color(color, i, G)
        print(array)
        conn.send(array)
        print("allumage en green envoyé")
        #time.sleep(5)
        #if(var == 'p'):
        #    var = None
        #    array = msg_color(color, i, D)
        #    conn.send(array)
        #    goto .pause
        ok = input("continue addressage? [Y/n]")
        array = msg_color(color, i, D)
        conn.send(array)
        print("extinction du pixel envoyé")
        if (ok == 'n') :
            i-=1
    array = msg_ama(AMA_COLOR)
    conn.send(array)

def initialisation():
    global conn, addr, s
    # socket creation
    s= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print('Socket has been created')
    # socket binding
    while True:
        try :
            s.bind((HOST, PORT))
            s.listen(11)
        except socket.error as msg:
            continue
            print('Binding has failed\n Err code :' + str(msg[0]) + '\n msg : ' + msg[1])
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
            if data[0] == BEACON :
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
    conn.send(array)
    crc_get(array)
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
    data = "a"
    while data != "" :
        data = conn.recv(1500)
        print(data)

def stop() :
    while(1):
        var= input()
        if (var == 'c'):
            close_co()
            sys.exit()

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
            clean()
            wake_up()
            state_color()
    except :
        print("error")
        close_co()
        sys.exit()
