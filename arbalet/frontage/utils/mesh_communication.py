import utils.mesh_constants as c
from utils.crc import crc_get

# Converts a string mac address ("12:25:89:125:249:80") to an integer array ([12, 25, 89, 125, 249, 80]), offset being the starting position of the mac address in the array
def mac_to_array(mac, array, offset):
    i = j = 0 #j keeps tracks of the cell in which to write, and i of the length of the substring.
    while ( len(mac) != 0):
        if (i < len(mac) and mac[i] != ':') : # while string is not over and character considered isn't separation colon
            i += 1
        else:
            array[offset + j] = int(mac[:i]) #Update cell value with substring computed
            mac = mac[i+1 :]
            i = 0
            j += 1


# Converts a integer array ([12, 25, 89, 125, 249, 80]) to a string mac address ("12:25:89:125:249:80")
def array_to_mac(data):
    return (str(int(data[0])) + ":" + str(int(data[1])) + ":" + str(int(data[2])) + ":" + str(int(data[3])) + ":" + str(int(data[4])) + ":" + str(int(data[5]))) #Simple concatenation

#Generates an INSTALL frame, requires the associated BEACON frame and assignated position as argument
def msg_install(data, comp):
    array = bytearray(16)
    array[c.VERSION] = c.SOFT_VERSION
    array[c.TYPE] = c.INSTALL
    for j in range (c.DATA, c.DATA+6) : #retrieves the mac address from the BEACON frame, and paste it in the INSTALL frame.
        array[j] = data[j]
    array[c.DATA+6] = comp #Position assignated to the newly declared card.
    crc_get(array) #generation of the checksum
    return array

#Generates an INSTALL frame, requires the string mac address of the card and its assignated position.
def msg_install_from_mac(mac, num):
    array = bytearray(16)
    array[c.VERSION] = c.SOFT_VERSION
    array[c.TYPE] = c.INSTALL
    # print_flush("Before mac")
    mac_to_array(mac, array, c.DATA ) #convert the string in bytearray format, and put it in the frame.
    # print_flush("After mac")
    array[c.DATA+6] = num # Position associated to the card.
    crc_get(array) #Generation of the checksum
    return array

#Generates an AMA frame, requires the subtype of the frame.
def msg_ama(amatype):
    array = bytearray(16)
    array[c.VERSION] = c.SOFT_VERSION
    array[c.TYPE]= c.AMA
    array[c.DATA] = amatype # specifies the subtype of the frame : AMA_INIT or AMA_COLOR
    crc_get(array) #Generation of the checksum
    return array

#Generate an ERROR frame with ERROR_GOTO subtype. Requires the string mac address of the target card, and the desired state.
def msg_readressage(mac, state=c.STATE_COLOR):#Check why no mac
    array = bytearray(16)
    array[c.VERSION] = c.SOFT_VERSION
    array[c.TYPE] = c.ERROR
    array[c.DATA] = c.ERROR_GOTO
    array[c.DATA+1] = state # First data byte is reserved for ERROR subtype.
    mac_to_array(mac, array, c.DATA+2) #Convert the string in bytearray format, and put it in the frame after subtype and state.
    crc_get(array) # Generation of the checksum.
    return array
