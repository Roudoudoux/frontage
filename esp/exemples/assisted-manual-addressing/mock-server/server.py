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

#inputs for columns and rows
cols=2
rows=3

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
    global mac
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



    sequence = []
    color_selection = [R, G, B, W]

    #generation of a 4-couloured pattern long sequence
    #which will be displayed by the esp32
    for k in range(0,4) :
        color = []
        color_selecter = k % 4
        for i in range(0, rows) :
            color_selecter = (color_selecter + i) % 4
            line = []
            for j in range(0, cols) :
                line.append(color_selection[color_selecter])
                color_selecter = color_selecter +1
                j=j
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

def state_ama():
    global dic, conn, var, cols, rows
    R = (255,0,0)
    G = (0,255,0)
    D = (0,0,0)
    color = []
    for k in range(0, rows) :
        line = []
        k=k
        for i in range(0, cols) :
            line.append(D)
        color.append(line)
    #color = [[D,D,D],[D,D,D]]
    array = msg_ama(AMA_INIT)
    conn.send(array)
    for i in range(0, len(dic)):
        (_, mac)=dic.get(i)
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
    global conn, addr, s, rows, cols
    # socket creation
    print("Please enter number of rows :")
    rows = input()
    print("Please enter number of columns :")
    cols = input()

    s= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print('Socket has been created')
    # socket binding
    while True:
        try :
            s.bind((HOST, PORT))
            s.listen(11)
        except socket.error:
            print('Binding has failed\n Err code :')
            continue
            #sys.exit()  
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
            print("Still waiting for "+ str(len(tab)-len(temp)) +" cards")
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
                #on recupere l'@mac de la trame BEACON
                print("BEACON : %d" % (int(data[1])))
                mac = []
                for x in data[2:6] :
                    print("-%d" % (int(x)))
                    mac = mac + [int(x)]
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



#Le MAIN est ici

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
