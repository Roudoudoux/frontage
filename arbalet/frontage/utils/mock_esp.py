from crc import Checksum
from mesh_communication import Frame
from threading import Thread
from mesh_constants import *
import socket


class Mock_esp(Thread):
    def __init__(self, mac='2:4:8:16:32:64'):
        Thread.__init__(self)
        self.frame = Frame()
        self.crc = Checksum()
        self.mac = mac
        self.ind = None
        self.state = STATE_INIT
        self.routing_table = [None for i in range(FRAME_SIZE)]
        self.connection = socket.create_connection((HOST, PORT))
        self.connection.settimeout(20)

    # send a beacon frame and wait for a install frame in return
    def state_init(self):
        barray = self.frame.beacon(self.mac)
        self.connection.send(barray)
        data = self.connection.recv(1500)
        print("I received : {} (type {})".format(data, data[TYPE]))
        if (data != "" and self.frame.is_valid(data[0:FRAME_SIZE])):
            if data[TYPE] == INSTALL:
                mac = self.frame.array_to_mac(data[DATA:])
                self.ind = int(data[DATA+MAC_SIZE])
                print("I am {} in the routing table".format(self.ind))
                self.routing_table[self.ind] = mac
        self.state = STATE_CONF

    # relay beacon frame from other esp, update the routing table and send a
    # beacon_ack in return

    def state_conf(self):
        data = self.connection.recv(1500)
        print("I received : {} (type {})".format(data, data[TYPE]))
        if (data != "" and self.frame.is_valid(data[0:FRAME_SIZE])):
            if data[TYPE] == AMA:
                if data[DATA] == AMA_INIT:
                    self.state = STATE_ADDR
                elif data[DATA] == AMA_COLOR:
                    print("ERROR : amma_color should not be received here")
            if data[TYPE] == INSTALL:
                mac = self.frame.array_to_mac(data[DATA:])
                self.routing_table[int(data[DATA+MAC_SIZE])] = mac
                # TODO beacon ack

    # relay color frame during addressing operations
    def state_addr(self):
        data = self.connection.recv(1500)
        print("I received : {} (type {})".format(data, data[TYPE]))
        llen = len(data)
        if (data != "" and self.frame.is_valid(data[0:llen])):
            if data[TYPE] == AMA:
                if data[DATA] == AMA_COLOR:
                    self.state = STATE_COLOR
                elif data[DATA] == AMA_INIT:
                    print("ERROR : amma_init should not be received here")
            if data[TYPE] == COLOR:
                print("Message color received")
                if data[DATA] == self.ind:
                    print("Displaying matrix")
                    self.display_colors(data[DATA+2:])
                else:
                    print("ERROR : is not for me")

    # operational state : relay color frame
    def state_color(self):
        data = self.connection.recv(1500)
        llen = len(data)
        print("I received : {} (type {})".format(data, data[TYPE]))
        if (data != "" and self.frame.is_valid(data[0:llen])):
            if data[TYPE] == COLOR:
                self.display_colors(data[DATA+2:])

    # manage all connection/deconnection problem
    def state_error(self):
        data = self.connection.recv(1500)
        print("I received : {} (type {})".format(data, data[TYPE]))
        if (data != "" and self.frame.is_valid(data[0:FRAME_SIZE])):
            pass

    def display_colors(self, colors):
        print("COLOR : \tR\tG\tB\n\t\t{}\t{}\t{}".format(colors[0], colors[1], colors[2]))

    def run(self):
        while True:
            try :
                print("I am currently in state {}".format(self.state))
                if self.state == STATE_INIT:
                    self.state_init()
                elif self.state == STATE_CONF:
                    self.state_conf()
                elif self.state == STATE_ADDR:
                    self.state_addr()
                elif self.state == STATE_COLOR:
                    self.state_color()
                elif self.state == STATE_ERROR:
                    self.state_error()
                else:
                    print("ERROR : state not defined")
                    break
            except:
                continue


if __name__ == '__main__':
    esp = Mock_esp()
    esp.start()
