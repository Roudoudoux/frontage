from math import ceil
try :
    from server.flaskutils import print_flush
    import utils.mesh_constants as c
    from utils.crc import Checksum
except :
    import mesh_constants as c
    from crc import Checksum
    def print_flush(*msg):
        print(*msg, file=sys.stderr)
        sys.stderr.flush()

class Frame:
    def __init__(self, crc=None):
        if crc is None:
            self.crc = Checksum()
        else:
            self.crc = crc

    # Converts a string mac address ("12:25:89:125:249:80") to an integer array ([12, 25, 89, 125, 249, 80]), offset being the starting position of the mac address in the array
    def mac_to_array(self, mac, array, offset):
        i = j = 0 #j keeps tracks of the cell in which to write, and i of the length of the substring.
        while ( len(mac) != 0):
            if (i < len(mac) and mac[i] != ':') :
                # while string is not over and character considered isn't separation colon
                i += 1
            else:
                array[offset + j] = int(mac[:i]) #Update cell value with substring computed
                mac = mac[i+1 :]
                i = 0
                j += 1

    # Converts a integer array ([12, 25, 89, 125, 249, 80]) to a string mac address ("12:25:89:125:249:80")
    def array_to_mac(self, data):
        mac = str(int(data[0]))
        for i in range(1, c.MAC_SIZE):
            mac += ":{}".format(int(data[i]))
        return mac #Simple concatenation

    #Generates an INSTALL frame, requires the associated BEACON frame and assignated position as argument
    def install(self, data, comp):
        array = bytearray(c.FRAME_SIZE)
        array[c.VERSION] = c.SOFT_VERSION
        array[c.TYPE] = c.INSTALL
        for j in range (c.DATA, c.DATA + c.MAC_SIZE) :
            #retrieves the mac address from the BEACON frame, and paste it in the INSTALL frame.
            array[j] = data[j]
        array[c.DATA + c.MAC_SIZE] = comp #Position assignated to the newly declared card.
        self.crc.set(array) #generation of the checksum
        return array

    #Generates an INSTALL frame, requires the string mac address of the card and its assignated position.
    def install_from_mac(self, mac, num):
        array = bytearray(c.FRAME_SIZE)
        array[c.VERSION] = c.SOFT_VERSION
        array[c.TYPE] = c.INSTALL
        # print_flush("Before mac")
        self.mac_to_array(mac, array, c.DATA ) #convert the string in bytearray format, and put it in the frame.
        # print_flush("After mac")
        array[c.DATA + c.MAC_SIZE] = num # Position associated to the card.
        self.crc.set(array) #Generation of the checksum
        return array

    # Only used in mock_esp
    def beacon(self, mac):
        array = bytearray(c.FRAME_SIZE)
        array[c.VERSION] = c.SOFT_VERSION
        array[c.TYPE] = c.BEACON
        self.mac_to_array(mac, array, c.DATA)
        self.crc.set(array)
        return array

    # Description :
    # fill the array according to the chosen mod (ama/prod) with the colors matching the pixels position stock in dico
    # Utility :
    # The given array is in fact the COLOR frame which will be sent to ESP root
    def filling_array(self, array, colors, dico, ama, nb_pixels):
        m = len(colors[0])
        n = len(colors)
        for val in dico.values():
            ((i,j), ind) = val
            if ind < nb_pixels :
                if (ama == 0) :# 2D array is interpreted as a 1D array
                    r = colors[int(ind/m)][int(ind % m)][0]
                    v = colors[int(ind/m)][int(ind % m)][1]
                    b = colors[int(ind/m)][int(ind % m)][2]
                elif ( i != -1 and j != -1 and i < n and j < m)  : #The pixel is addressed and within the model boundaries
                    r = colors[i][j][0]
                    v = colors[i][j][1]
                    b = colors[i][j][2]
                else: # unkown value
                    r= v= b= 0
                # Fill the right place in the COLOR frame
                array[c.DATA + 2 + ind*3] = min(255, max(0, int(r*255)))
                array[c.DATA + 3 + ind*3] = min(255, max(0, int(v*255)))
                array[c.DATA + 4 + ind*3] = min(255, max(0, int(b*255)))

    # Description :
    # formating the color frame according to the ESP32 communication protocol
    # Note :
    # Is not with the other functions (in mesh_communication) because msg_color is using and updating some Mesh's attributs
    def color(self, colors, seq, pixels, unks, ama= 1):
        nb_pixels = len(pixels)
        if (ama == 1):
            nb_pixels += len(unks)
        array = bytearray(nb_pixels*3 + 4 + ceil((nb_pixels*3 + 4)/7))
        array[c.VERSION] = c.SOFT_VERSION
        array[c.TYPE] = c.COLOR
        array[c.DATA] = seq // 256
        array[c.DATA+1] = seq % 256
        self.filling_array(array, colors, pixels, ama, nb_pixels)
        if (ama == 1) :
            self.filling_array(array,colors,unks, ama, nb_pixels)
        self.crc.set(array)
        return array

    #Generates an AMA frame, requires the subtype of the frame.
    def ama(self, amatype):
        array = bytearray(c.FRAME_SIZE)
        array[c.VERSION] = c.SOFT_VERSION
        array[c.TYPE]= c.AMA
        array[c.DATA] = amatype # specifies the subtype of the frame : AMA_INIT or AMA_COLOR
        self.crc.set(array) #Generation of the checksum
        return array

    #Generate an ERROR frame with ERROR_GOTO subtype. Requires the string mac address of the target card, and the desired state.
    def har(self, mac, state=c.STATE_COLOR):
        array = bytearray(c.FRAME_SIZE)
        array[c.VERSION] = c.SOFT_VERSION
        array[c.TYPE] = c.ERROR
        array[c.DATA] = c.ERROR_GOTO
        array[c.DATA+1] = state # First data byte is reserved for ERROR subtype.
        self.mac_to_array(mac, array, c.DATA+2) #Convert the string in bytearray format, and put it in the frame after subtype and state.
        self.crc.set(array) # Generation of the checksum.
        return array

    def err_goto(self, nstate = c.STATE_COLOR):
        array = bytearray(c.FRAME_SIZE)
        array[c.VERSION] = c.SOFT_VERSION
        array[c.TYPE] = c.ERROR
        array[c.DATA] = c.ERROR_GOTO
        array[c.DATA+1] = nstate # First data byte is reserved for ERROR subtype.
        self.mac_to_array(mac, array, c.DATA+2) #Convert the string in bytearray format, and put it in the frame after subtype and state.
        self.crc.set(array) # Generation of the checksum.
        return array

    def reboot(self, timetosleep):
        array = bytearray(c.FRAME_SIZE)
        array[c.VERSION] = c.SOFT_VERSION
        array[c.TYPE] = c.REBOOT
        array[c.DATA] = timetosleep // 256
        array[c.DATA+1] = timetosleep % 256
        self.crc.set(array)
        return array

    # Brief : computes an error frame
    # Params :
    #    - data : a bytearray received from the mesh network which follow the
    #    communication format
    #    - ack : boolean (initialy set to True) to acknowledge that data has
    #    been received and dealt with
    #    - unk : boolean (initialy set to False) infroms the ROOT esp whether
    #    or not the declairing esp is known by the server
    # Returns : a bytearray which is the complete frame
    def error(self, data, ack=True, unk=False, subtype=None):
        array = bytearray(c.FRAME_SIZE)
        array[c.VERSION] = c.SOFT_VERSION
        array[c.TYPE] = c.ERROR
        if subtype is not None:
            array[c.DATA] = subtype
        else:
            array[c.DATA] = data[c.DATA]
        array[c.DATA+1] = data[c.DATA+1]
        for j in range(c.DATA+2, c.DATA+ 2 + c.MAC_SIZE):
            array[j] = data[j]
        if ack:
            array[c.DATA+1] = array[c.DATA+1] | 128
        if unk:
            array[c.DATA+1] = array[c.DATA+1] | 32
        self.crc.set(array)
        return array

    # Brief : check whether or not the received frame is valid.
    #    A frame is considered valid if its crc is valid and if the software
    #    version of the sender matches the receiver's one
    # Param :
    #    - frame : a bytearray containning the received frame
    # Returns : a boolean
    def is_valid(self, frame):
        # print_flush("checksum is ",self.crc.check(frame))
        return (self.crc.check(frame) and frame[c.VERSION] == c.SOFT_VERSION)


if __name__ == '__main__':
    test = Frame()
    mac = "2:4:8:16:32:64"
    amac = bytearray(c.MAC_SIZE)
    test.mac_to_array(mac, amac, 0)
    tmac = test.array_to_mac(amac)
    assert(tmac == mac)

    mock_beacon = bytearray(c.FRAME_SIZE)
    test.mac_to_array(mac, mock_beacon, c.DATA)
    finstall = test.install(mock_beacon, 2)
    finstallbis = test.install_from_mac(mac, 2)
    assert(test.is_valid(finstall))
    assert(test.is_valid(finstallbis))
    assert(finstall == finstallbis)

    fama = test.ama(c.AMA_COLOR)
    assert(test.is_valid(fama))
    assert(fama[c.DATA] == c.AMA_COLOR)

    fhar = test.har(mac)
    assert(test.is_valid(fhar))
