import time as t
import sys as s
import socket
from threading import Thread, Semaphore
from queue import Queue
from mesh_communication import Frame
from mesh_constants import *

FRONTAGE_PATH = "/home/thor/Svartalfheim/frontage"

class Logs(Thread):
    file = None
    nb_logs = 0
    path = FRONTAGE_PATH + "/arbalet/frontage/logs/"
    def __init__(self, name = None):
        Thread.__init__(self)

        if (name is None):
            name = "logs_"+nb_logs+".log"
        Logs.file = open(Logs.path + name, 'wt')
        


class Commands(Thread):
    pending_queue = None
    log_queue = None
    nmsg = None
    start_addr = False
    end_addr = True
    manual = False
    send_color = True
    conn = None
    fmsg = Frame()

    @staticmethod
    def get_queue():
        return (Commands.pending_queue, Commands.nmsg)

    # OK
    def __init__(self):
        Thread.__init__(self)
        self.running = True
        self.server = None
        Commands.pending_queue = Queue()
        Commands.log_queue = Queue()
        Commands.nmsg = Semaphore(0)
        self.shortcuts = {"h":"help",
                          "ss": "start_server",
                          "sa":"sender-auto",
                          "a" : "addressing",
                          "m" : "msg",
                          "d" : "display",
                          "exec" : "script",
                          "e" : "exit" }
        self.commands = {"help":("cmd", "if no arg display general list of commands"),
                         "start-server": ("", "start the server application"),
                         "sender-auto": ("True|False", "the server will manage automatically the sending of messages (default True)"),
                         "addressing": ("", "start an addressing procedure"),
                         "msg":("TYPE DATA","TYPE : INSTALL | ERR-GOTO | REBOOT | COLOR\n\
        DATA : \n\
        \tINSTALL implies a mac address and a index as data, if none is given will do automatically\n\
        \tERR-GOTO implies a state to go to (COLOR | REBOOT | INSTALL | CONF | ADDR)\n\
        \tREBOOT implies a time (in milisecond) to wait before restarting esp if none is given, would be set to NB_pixels*30 milliseconds\n\
        \tCOLOR implies a matrix of color triplet if none is given, would dislpay french flag"),
                         "display":("info","info can be either a specific field or a predefined param. :\n\
        \t-pixels : prints 3 category-pixels (pixels, unk and deco);\n\
        \t-matrix : prints the color matrix in server memory;\n\
        \t-all : prints all the messages in pending in the queue"),
                         "script":("file","file has to be a relative path to a file in .spt which contains a scenario"),
                         "stop" : ("","stops the server (sever, mesh and listen instances are closed)"),
                         "exit" : ("", "exit properly the application")}

    # OK
    def execute(self, cmd, args=[None]):
        if (cmd == "help" or cmd == "h"):
            self.help(args[0])
        elif (cmd == "start-server" or cmd == "ss"):
            self.start_server()
        elif (cmd == "sender-auto" or cmd == "sa"):
            self.send_method(args[0])
        elif (cmd == "addressing" or cmd == "a"):
            self.addressing()
        elif (cmd == "stop"):
            self.stop_server()
        elif (cmd == "display" or cmd == "d"):
            self.display(args[0])
        elif (cmd == "scrpit" or cmd == "exec"):
            self.script(args[0])
        elif (cmd == "msg" or cmd == "m"):
            if (len(args) >= 2):
                self.msg(args[0], args[1])
            else:
                self.msg(args[0], None)
        elif (cmd == "exit" or cmd == "e"):
            self.running = False
        else:
            self.help()

    # OK
    def addressing(self):
        Commands.start_addr = True
        Commands.end_addr = False

    # OK
    def send_method(self, auto):
        if (auto is not None):
            print("auto send : {}".format("on" if auto == "True" else "off"))
            Commands.manual = auto
        else :
            print("auto send : off")
            Commands.manual = False

    # OK
    def start_server(self, arg=5):
        self.server = Server(arg)
        self.server.start()
        self.nmsg.acquire()
        print(self.pending_queue.get())

    # OK
    def help(self, c=None):
        print("Usage :")
        if (c is None):
            for cmd in self.commands:
                print("\t{}".format(cmd, self.commands[cmd][0]))
        else:
            cmd = self.commands.get(c)
            if (cmd is None):
                self.help()
            else:
                print("\t{} {}\n\t{}".format(c, cmd[0], cmd[1]))

    # OK
    def stop_server(self):
        Server.running = False
        if (self.server is not None):
            print("Waiting for Server ...")
            self.server.join()
        while self.nmsg.acquire(False):
            print(self.pending_queue.get())

    # OK
    def app_exit(self):
        self.stop_server()
        print("Application exiting ...")
        s.exit()

    # OK
    def display(self, arg):
        if (arg == None or arg == "all"):
            count = 0
            while Commands.nmsg.acquire(False):
                msg = Commands.pending_queue.get(False)
                print(msg)
                count += 1
            if (count == 0):
                print("No message in the queue")
            else:
                print("No more messages")
        elif (arg == "pixels"):
            print("Addressed and functional pixels :\n\t{}\nDeconnected pixels :\n\t{}\nUnknowned pixels :\n\t{}".format(
                Mesh.pixels,
                Listen.deco,
                Listen.unk))
        elif (arg == "model"):
            for row in Mesh.model:
                print("\t{}".format(row))
        else:
            try:
                zcorp = eval(arg)
                print(zcorp)
                if (str(type(zcorp)) == "<class 'function'>"):
                    print(zcorp())
                else:
                    print(zcorp)
            except:
                print("ERROR: unknown value {}".format(arg))

    # TO TEST
    def msg(self, mtype, data):
        if Commands.conn is None:
            print("No connection : sending impossible")
        elif mtype is None:
            print("A message type is required")
        elif eval(mtype) == REBOOT:
            if data is None:
                tts = (len(Mesh.pixels) + len(Listen.unk))*5
            elif type(eval(data)) is int:
                tts = eval(data)
            else :
                tts = (len(Mesh.pixels) + len(Listen.unk))*5
            array = Commands.fmsg.reboot(tts)
        elif eval(mtype) == ERROR_GOTO:
            array = Commands.fmsg.err_goto(eval(data))
        else:
            print("Please enter correct inputs")
            return
        m = "SEND : {}".format(int(array[0]))
        for i in range(1, len(array)):
            m += ":{}".format(int(array[i]))
        Commands.conn.send(array)
        print(m)

    # TO DO
    def script(self, path):
        print("script function TODO")
        pass

    # OK
    def run(self):
        while self.running:
            if (not Commands.end_addr) :
                continue
            else :
                rinput = input("> ")
                agrs = rinput.split(" ")
                # print("args input are : {}".format(agrs))
                cmd = self.commands.get(agrs[0])
                scmd = self.shortcuts.get(agrs[0])
                if (cmd is None and scmd is None):
                    self.help()
                else:
                    # print("cmd : {}".format(cmd))
                    self.execute(agrs[0], agrs[1:] if agrs[1:] != [] else [None])
        self.app_exit()


# Yet to see if ok
class Listen(Thread):
    unk = {}
    deco = {}
    running = True

    def __init__(self, com):
        Thread.__init__(self)
        (self.p_queue, self.p_sem) = Commands.get_queue()
        self.count = 0
        self.msg = Frame()
        self.com = com

    def send_table(self, previous_state):
        pmsg = "\tSENDING TABLE: START\n"
        self.p_queue.put(pmsg)
        self.p_sem.release()
        array = self.msg.har(Mesh.mac_root, STATE_CONF)
        self.com.send(array)
        root_val = Mesh.pixels[Mesh.mac_root]
        card_list = [None]*Mesh.nb_pixels
        for val in Mesh.pixels:
            ((i,j),ind) = Mesh.pixels.get(val)
            card_list[ind]=val
        for val in Listen.deco:
            ((i,j),ind) = Listen.deco.get(val)
            card_list[ind]=val
        for ind, value in enumerate(card_list):
            pmsg += "\t\tINSTALL : {} at {}\n".format(value,ind)
            self.p_queue.put(pmsg)
            self.p_sem.release()
            array = self.msg.install_from_mac(value,ind)
            self.com.send(array)
        array = self.msg.har(Mesh.mac_root, previous_state)
        self.com.send(array)
        pmsg = "\tSENDING TABLE: END\n"
        self.p_queue.put(pmsg)
        self.p_sem.release()

    def beacon_handler(self, data):
        mac = self.msg.array_to_mac(data[DATA:DATA+MAC_SIZE])
        pmsg = "MESSAGE {} is a BEACON:\n\tmac:{}".format(self.count, mac)
        if Listen.unk.get(mac) is not None:
            pmsg += "\n\tALREADY DECLARED"
            self.p_queue.put(pmsg)
            self.p_sem.release()
            return
        pmsg += "\n\tindex: {}".format(Mesh.nb_pixels)
        if (Mesh.nb_pixels == 0):
            pmsg += "\n\tIS ROOT"
            Mesh.mac_root = mac
        self.p_queue.put(pmsg)
        self.p_sem.release()
        Listen.unk[mac]=((-1,-1), Mesh.nb_pixels)
        array = self.msg.install(data, Mesh.nb_pixels)
        self.com.send(array)
        pmsg = "ANSWER:\t {}".format(int(array[0]))
        for b in array[1:]:
            pmsg += ":{}".format(int(b))
        self.p_queue.put(pmsg)
        self.p_sem.release()
        Mesh.nb_pixels += 1

    def error_handler(self, data):
        mac = self.msg.array_to_mac(data[DATA:DATA+MAC_SIZE])
        pmsg = "MESSAGE {} is an ERROR".format(self.count)
        if (data[SUB_TYPE] == ERROR_DECO):
            pmsg += "_DECO from {}".format(mac)
            if (Mesh.pixels.get(mac) is not None):
                pmsg += "\n\t was in Mesh.pixels (now in Listen.unk)"
                Listen.deco[mac] = Mesh.pixels.pop(mac)
            elif (Listen.unk.get(mac) is not None):
                pmsg += "\n\t was in Listen.unk (now lost)"
                Listen.unk.pop(mac)
            array = self.msg.error(data, ack=True)
        elif (data[SUB_TYPE] == ERROR_CO):
            pmsg += "_CO from {}".format(mac)
            if (Listen.deco.get(mac) is not None):
                pmsg += "\n\twas in Listen.deco, is now in Mesh.pixels"
                Mesh.pixels[mac] = Listen.deco.pop(mac)
                array = self.msg.error(data, ack=True)
            elif (Mesh.pixels.get(mac) is not None):
                pmsg += "\n\twas already in Mesh.pixels"
                array = self.msg.error(data, ack=True)
            else:
                pmsg += "\n\tis new, is now in Listen.unk"
                Listen.unk[mac]= ((-1,-1),-1)
                array = self.msg.error(data, ack=True, unk=True)
        elif (data[SUB_TYPE] == ERROR_ROOT):
            pmsg += "_ROOT from {}".format(mac)
            Mesh.mac_root = mac
            nb_card = (data[DATA+1] & 0xF0) >> 4
            if (Mesh.nb_pixels > nb_card):
                pmsg += "\n\t There are more esps in mesh than in server's dics"
                self.p_queue.put(pmsg)
                self.p_sem.release()
                self.send_table([DATA+1] & 0x0F)
            else:
                pmsg += "\n\tThere are more esps in server's memory than in mesh network"
                self.p_queue.put(pmsg)
                self.p_sem.release()
                Mesh.nb_pixels = nb_card
                Mesh.addressed = True
                array = self.msg.har(Mesh.mac_root, data[DATA+1]& 0x0F)
                self.com.send(array)
                pmsg = "ANSWER:\t {}".format(int(array[0]))
                for b in array[1:]:
                    pmsg += ":{}".format(int(b))
                self.p_queue.put(pmsg)
                self.p_sem.release()
            return
        else:
            pmsg += "\n\t SUB-TYPE not recognize"
            self.p_queue.put(pmsg)
            self.p_sem.release()
            return
        self.com.send(array)
        pmsg = "ANSWER:\t {}".format(int(array[0]))
        for b in array[1:]:
            pmsg += ":{}".format(int(b))
        self.p_queue.put(pmsg)
        self.p_sem.release()

    def listen(self):
        data = ""
        self.count += 1
        try:
            data = self.com.recv(1500)
        except:
            return
        if (data != FRAME_SIZE and self.msg.is_valid(data)):
            if (data[TYPE] == ERROR):
                self.error_handler(data)
            elif (data[TYPE] == BEACON):
                self.beacon_handler(data)
            else:
                pmsg = "MESSAGE {} is not supposed to happen.\n\tRECEIVED: ".format(self.count)
                for bit in data:
                    pmsg += str(int(bit)) + " "
                self.p_queue.put(pmsg)
                self.p_sem.release()

    def close(self):
        Listen.running = False

    def run(self):
        while Listen.running:
            self.listen()
        print("Listen closed")

# In process
class Mesh(Thread):
    socket = None
    mac_root = ''
    sequence = 0
    pixels = {}
    required_amount = 0
    consummed = 0
    nb_pixels = 0
    addressed = None
    ama = 0
    model = [[]]
    change_esp_state = False
    running = True
    addressing = False

    # OK
    def __init__(self, conn, addr):
        Thread.__init__(self)
        Mesh.addressed = not(Mesh.pixels == {})
        self.ama_check = 0
        self.previous_state = 1
        self.rows = 4
        self.cols = 4
        self.addressing = False
        Mesh.model = [[(0,0,0) for i in range(self.cols)] for j in range(self.rows)]
        self.msg = Frame()
        self.mesh_conn = conn
        self.mesh_conn.settimeout(10)
        self.mesh_addr = addr
        self.l = Listen(conn)
        self.l.start()
        (self.p_queue, self.p_sem) = Commands.get_queue()

    # OK
    def ama_model(self):
        i = self.rows -1
        if (self.ama_check == 0):
            green = red = 0
            while(i >= 0):
                j = self.cols -1
                while(j >= 0):
                    tmp = Mesh.model[i][j]
                    if( (tmp[0]+tmp[1]+tmp[2]) == -3):
                        return True
                    elif (tmp[0] == 0 and tmp[1] == 1 and tmp[2] == 0):
                        green += 1
                    elif (tmp[0] == 1 and tmp[1] == 0 and tmp[2] == 0):
                        red += 1
                    else:
                        return False
                    j -= 1
                i -= 1
            return (green == Mesh.required_amount -1 and red == 1)
        elif (self.ama_check == 1):
            while(i >= 0):
                j = self.cols -1
                while (j >= 0):
                    tmp = self.model[i][j]
                    if  (( (tmp[0]+tmp[1]+tmp[2]) != 0) and
                         (tmp[0] != 1 and tmp[1]+tmp[2] != 0) and
                         (tmp[1] != 1 and tmp[0]+tmp[2] != 0)):
                        return False
                    j -= 1
                i-= 1
            return True
        return False

    # OK
    def ama_care(self):
        if self.ama_model():
            self.ama_check = (self.ama_check + 1) % 2
            Mesh.sequence = (Mesh.sequence + 1) % 65536
            array = self.msg.color(Mesh.model, Mesh.sequence, Mesh.pixels, Listen.unk, self.ama_check)
            self.mesh_conn.send(array)

    # OK
    def procedures_manager(self):
        Mesh.ama += 1
        if Mesh.ama == 1 :
            print("START AMA")
            Mesh.addressed = False
            Mesh.addressing = True
            Mesh.print_mesh_info(True, self.p_queue, self.p_sem)
            array = self.msg.ama(AMA_INIT)
            self.mesh_conn.send(array)
        elif Mesh.ama == 2 :
            Mesh.addressed = True
            Mesh.addressing = None
            Mesh.print_mesh_info(True, self.p_queue, self.p_sem)
            array = self.msg.ama(AMA_COLOR)
            self.mesh_conn.send(array)
            print("END addressing procedure")
        else :
            print("START HAR")
            Mesh.ama = 1
            Mesh.addressed = False
            Mesh.addressing = True
            Mesh.print_mesh_info(True, self.p_queue, self.p_sem)
            array = self.msg.har(Mesh.mac_root, STATE_CONF)
            self.mesh_conn.send(array)
            print(Listen.unk.keys(), Listen.deco)
            for mac in Listen.unk.keys() :
                if len(Listen.deco) > 0 :
                    pixel_deco = Listen.deco.popitem()
                    print("Adding new element")
                    print(pixel_deco)
                    print("Inserted unknwon card at {0}".format(pixel_deco[1][1]))
                    Listen.unk[mac] = ((-1,-1), pixel_deco[1][1])
                    array = self.msg.install_from_mac(mac, pixel_deco[1][1])
                    self.mesh_conn.send(array)
            Mesh.print_mesh_info(True, self.p_queue, self.p_sem)
            array = self.msg.ama(AMA_INIT)
            self.mesh_conn.send(array)

    # OK
    def change_model(self, param=None):
        black = (0,0,0)
        blue = (0,0,255)
        green = (0,255,0)
        red = (255,0,0)
        white = (255,255,255)
        colors = [black, blue, green, red, white]
        if Mesh.addressed and Commands.send_color:
            for row in Mesh.model:
                for i in range(self.cols):
                    row[i] = colors[(i+Mesh.sequence)%5]
        elif self.addressing :
            #During the addressing procedures
            if (Mesh.addressing is not None):
                if (self.ama_check == 0):
                    if len(Listen.unk) == 0:
                        Mesh.ama == 2
                        return
                    ans = input("press a key to continue")
                    (pmac, pix) = Listen.unk.popitem()
                    for i in range(self.rows):
                        for j in range(self.cols):
                            Mesh.model[i][j] = (-1,-1,-1)
                    Mesh.model[pix[1]//self.cols][pix[1]%self.cols] = red
                    Mesh.pixels[pmac]=pix
                    Mesh.addressing = pmac
                else:
                    ans = input("which pixel is lit ?(row,col)")
                    (r,c) = eval(ans)
                    ((x,y),ind) = Mesh.pixels[Mesh.addressing]
                    Mesh.pixels[Mesh.addressing] = ((r,c), ind)
                    for i in range(self.rows):
                        for j in range(self.cols):
                            Mesh.model[i][j] = black
                    Mesh.model[r][c]=(0,1,0)
                    for val in Mesh.pixels.values():
                        ((i,j),ind) = val
                        if (Mesh.ama == 0):
                            Mesh.model[i//self.cols][i% self.cols] = green
                        else:
                            Mesh.model[i][j] = green
                t.sleep(0.1)
        else :
            pass

    # OK
    def callback(self):
        Mesh.consummed += 1
        if Mesh.consummed % 100 == 0 :
            self.print_mesh_info(True, self.p_queue, self.p_sem)
        if Commands.start_addr:
            Commands.start_addr = False
            self.addressing = True
            ans = input("Dimension of the model ? (r,c)")
            (self.rows, self.cols) = eval(ans)
            Mesh.model = [[(0,0,0) for i in range(self.cols)] for j in range(self.rows)]
            ans = input("Number of required pixels ?")
            Mesh.required_amount = eval(ans)
            self.procedures_manager()
        elif (Mesh.ama == 1) :
            self.ama_care()
        elif (Mesh.addressed) :
            Mesh.sequence = (Mesh.sequence + 1) % 65536
            array = self.msg.color(self.model, Mesh.sequence, Mesh.pixels, Listen.unk)
            self.mesh_conn.send(array)
        else :
            pass

    @staticmethod
    def print_mesh_info(q=False, p_queue=None, p_sem=None):
        pmsg = " ========== Mesh ==========\n\tIs mesh initialized :\t\t{}\n\
\tColor frame sent :\t\t{}\n\tPixels amount declared ?\t{}\n\t\
Pixels amount required ?\t{}\n\tPixels?\t\t\t\t{}\n\tPixels deconnected?\t\t{}\n\
\tPixels unknown?\t\t\t{}\n========== Mesh ==========".format(Mesh.addressed,
Mesh.consummed, Mesh.nb_pixels, Mesh.required_amount, Mesh.pixels, Listen.deco, Listen.unk)
        if q:
            p_queue.put(pmsg)
            p_sem.release()
        else:
            return pmsg

    def run(self):
        while Mesh.running:
            self.change_model()
            self.callback()
            t.sleep(0.2)
        self.close_socket()
        print("Mesh closed")

    def close_socket(self) :
        if (self.l is not None and self.l.is_alive()):
            print("Waiting for Listen...")
            Listen.running = False
            self.l.join()
        if self.mesh_conn is not None :
            self.mesh_conn.close()
        Mesh.socket.close()

# OK
class Server(Thread):
    running = False

    # OK
    def __init__(self, timeout=5):
        Thread.__init__(self)
        (self.p_queue, self.p_sem) = Commands.get_queue()
        Mesh.socket= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while True:
            try :
                Mesh.socket.bind((HOST, PORT))
                Mesh.socket.listen(5)
                break
            except socket.error as msg:
                t.sleep(5)
                continue
        self.socket_thread = None
        self.p_queue.put("Server started")
        self.p_sem.release()
        Server.running = True
        Mesh.socket.settimeout(timeout)

    # OK
    def run(self):
        nb_connection = 0
        while self.running :
            try:
                conn, addr = Mesh.socket.accept()
                nb_connection+=1
                self.p_queue.put("Connection accepted with {0}".format(addr))
                self.p_sem.release()
                if (self.socket_thread != None) :
                    Commands.conn = None
                    self.socket_thread.close_socket()
                self.socket_thread = Mesh(conn, addr)
                Commands.conn = conn
                self.socket_thread.start()
            except:
                continue
        Commands.conn = None
        Mesh.running = False
        if self.socket_thread is not None:
            print("Waiting for Mesh...")
            self.socket_thread.join()
        print("Server stopped")

if (__name__ == "__main__"):
    test = Commands()
    test.start()
