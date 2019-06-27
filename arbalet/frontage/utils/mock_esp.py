import socket
from random import randint
from time import sleep
from crc import Checksum
from mesh_communication import Frame
from threading import Thread
from mesh_constants import *

class esp32:
    @staticmethod
    def __gen_mac(fst):
        str_mac = str(fst)
        for i in range(1, MAC_SIZE):
            str_mac += ":{}".format(randint(0,255))
        return str_mac

    def __init__(self, num, row, col):
        self.row = row
        self.col = col
        self.ind = None
        self.state = STATE_INIT
        self.mac = esp32.__gen_mac(num)

class Mock_mesh(Thread):

    def __init__(self, row=1, col=1):
        Thread.__init__(self)
        self.frame = Frame()
        self.crc = Checksum()

        self.co_server = socket.create_connection((HOST, PORT))
        self.co_server.settimeout(15)
        self.sended = 1
        self.nb_pixels = row*col
        self.rows = row
        self.cols = col
        self.frontage = [[(0,0,0) for i in range(self.cols)] for j in range(self.rows)]
        self.esps = [None for i in range(self.nb_pixels)]
        for i in range(self.nb_pixels):
            self.esps[i] = esp32(i, i//row, i%col)
        self.esp_root = self.esps[0]

        self.general_state = STATE_INIT

    # send a beacon frame and wait for a install frame in return
    def state_init(self):
        barray = self.frame.beacon(self.esp_root.mac)
        self.co_server.send(barray)
        print("I send {}".format(barray))
        data = self.co_server.recv(1500)
        print("I received : {} (type {})".format(data, data[TYPE]))
        if (data != "" and self.frame.is_valid(data[0:FRAME_SIZE])):
            if data[TYPE] == INSTALL:
                mac = self.frame.array_to_mac(data[DATA:])
                ind = int(data[DATA+MAC_SIZE])
                for i in range(self.nb_pixels):
                    if mac == self.esps[i].mac:
                        self.esps[i].state = STATE_CONF
                        self.esps[i].ind = ind
                        self.general_state = STATE_CONF
                        break



    # relay beacon frame from other esp, update the routing table and send a
    # beacon_ack in return
    def state_conf(self):
        if self.sended < self.nb_pixels :
            barray = self.frame.beacon(self.esps[self.sended].mac)
            self.co_server.send(barray)
            sleep(0.1)
            self.sended += 1
        data = self.co_server.recv(1500)
        if (data != "" and self.frame.is_valid(data[0:FRAME_SIZE])):
            if data[TYPE] == AMA:
                print("I've received a AMA")
                if data[DATA] == AMA_INIT:
                    self.esp_root.state = STATE_ADDR
                    for i in range(self.nb_pixels):
                        if self.esps[i].state != STATE_ADDR:
                            print("ERROR : an esp ({}) is not in the rightfull state".format(self.esps[i].mac))
                            return
                    self.general_state = STATE_ADDR
                    # verifier que toutes soient dans l'état addr
                elif data[DATA] == AMA_COLOR:
                    print("ERROR : amma_color should not be received here")
            if data[TYPE] == INSTALL:
                mac = self.frame.array_to_mac(data[DATA:])
                ind = int(data[DATA+MAC_SIZE])
                for i in range(self.nb_pixels):
                    if mac == self.esps[i].mac:
                        self.esps[i].state = STATE_ADDR
                        self.esps[i].ind = ind
                        print("{} has been acquitted".format(self.esps[i].mac))
                        break

    # relay color frame during addressing operations
    def state_addr(self):
        data = self.co_server.recv(1500)
        # print("I received : {} (type {})".format(data, data[TYPE]))
        llen = len(data)
        if (data != "" and self.frame.is_valid(data[0:llen])):
            if data[TYPE] == AMA:
                if data[DATA] == AMA_COLOR:
                    for i in range(self.nb_pixels):
                        self.esps[i].state = STATE_CONF
                    self.general_state = STATE_COLOR
                elif data[DATA] == AMA_INIT:
                    print("ERROR : amma_init should not be received here")
            if data[TYPE] == COLOR:
                self.display_colors(data[DATA+2:])

    # operational state : relay color frame
    def state_color(self):
        data = self.co_server.recv(1500)
        llen = len(data)
        # print("I received : {} (type {})".format(data, data[TYPE]))
        if (data != "" and self.frame.is_valid(data[0:llen])):
            if data[TYPE] == COLOR:
                self.display_colors(data[DATA+2:])

    # manage all co_server/deconnection problem
    def state_error(self):
        data = self.co_server.recv(1500)
        # print("I received : {} (type {})".format(data, data[TYPE]))
        if (data != "" and self.frame.is_valid(data[0:FRAME_SIZE])):
            pass

    def display_colors(self, colors):
        for i in range(self.nb_pixels):
            col = (int(colors[i*3]), int(colors[i*3+1]), int(colors[i*3+2]))
            for j in range(self.nb_pixels):
                if self.esps[j].ind == i :
                    r = self.esps[j].row
                    c = self.esps[j].col
                    break
            if r + c != -2:
                self.frontage[r][c] = col
            else:
                print("esp not find")
        print("\n\n=============================================================\n")
        for row in self.frontage:
            print("\t{}".format(row))
        print("\n=============================================================\n\n")


    def run(self):
        while True:
            try :
                # print("I am currently in state {}".format(self.general_state))
                if self.general_state == STATE_INIT:
                    self.state_init()
                elif self.general_state == STATE_CONF:
                    self.state_conf()
                elif self.general_state == STATE_ADDR:
                    self.state_addr()
                elif self.general_state == STATE_COLOR:
                    self.state_color()
                elif self.general_state == STATE_ERROR:
                    self.state_error()
                else:
                    print("ERROR : state not defined")
                    break
            except:
                continue


if __name__ == '__main__':
    mesh = Mock_mesh(3,3)
    mesh.start()
