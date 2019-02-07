import socket
import sys
import os, fcntl
import time
import threading
#import goto

# CONSTANTS

#Server state
initialisated = False

# Connection
HOST='10.42.0.1'
#HOST='10.0.0.1'
PORT=8080
conn = None
addr = None

#Frame's type
BEACON = 1
INSTALL = 3
COLOR = 4
AMA = 6
SLEEP = 8
AMA_INIT = 61
AMA_COLOR = 62
WAKEUP=10

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

def msg_install(data):
    global comp
    array = bytearray(16)
    array[0] = INSTALL
    for j in range (1, 7) :
        array[j] = data[j]
    array[7] = comp
    comp+=1
    return array

def msg_install_from_mac(data, num):
    global comp
    array = bytearray(16)
    array[0] = INSTALL
    for j in range (1, 7) :
        array[j] = data[j-1]
    array[7] = num
    return array

def msg_ama(amatype):
    array = bytearray(16)
    array[0]= AMA
    array[1] = amatype
    return array

def msg_color(colors, ama= -1, col= None):
    print(colors)
    array = bytearray(1+ len(dic)*3 + 4)
    array[0] = COLOR
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
        array[1+ k*3] = r
        array[2+ k*3] = v
        array[3+ k*3] = b
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
        time.sleep(0.1)
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
        if (data != "") :
            if data[0] == BEACON :
                print("BEACON : %d-%d-%d-%d-%d-%d" % (int(data[1]), int(data[2]), int(data[3]), int(data[4]), int(data[5]), int(data[6])))
                mac = [int(data[1]), int(data[2]), int(data[3]), int(data[4]), int(data[5]), int(data[6])]
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
                array = msg_install(data)
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
        if (data != "") :
            if data[0] == BEACON :
                print("BEACON : %d-%d-%d-%d-%d-%d" % (int(data[1]), int(data[2]), int(data[3]), int(data[4]), int(data[5]), int(data[6])))
                mac = [int(data[1]), int(data[2]), int(data[3]), int(data[4]), int(data[5]), int(data[6])]
                if mac in tab :
                    print("already got this")
                    continue
                #via dictionnary use
                dic[comp]=((-1,-1), data[1:7])
                #via tabular use
                tab.append([])
                for j in range (1, 7) :
                    tab[comp].append(int(data[j]))
                array = msg_install(data)
                conn.send(array)
                time.sleep(1)
            else :
                print("A message was recieved but it is not a BEACON")
            goon = input("Would you like to keep going on recieving mac addresses ? [Y/n]")

def set_sleep() :
    array = bytearray(16)
    array[0] = SLEEP
    array[8] = 255
    array[7] = 255
    array[6] = 255
    conn.send(array)
    time.sleep(10)

def set_wakeup() :
    array = bytearray(16)
    array[0] = WAKEUP
    conn.send(array)

def close_co():
    if(conn != None):
        conn.close()
    if(addr != None):
        addr.close()

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
            wake_up()
            state_color()
    except :
        print("error")
        close_co()
        sys.exit()
