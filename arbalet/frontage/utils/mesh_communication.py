import utils.mesh_constants as c
from utils.crc import crc_get
# '12:123:12:43:34'
def mac_to_array(mac, array, offset):
    i = j = 0
    while ( len(mac) != 0):
        if (i < len(mac) and mac[i] != ':') :
            i += 1
        else:
            array[offset + j] = int(mac[:i])
            mac = mac[i+1 :]
            i = 0
            j += 1

def array_to_mac(data):
    return (str(int(data[0])) + ":" + str(int(data[1])) + ":" + str(int(data[2])) + ":" + str(int(data[3])) + ":" + str(int(data[4])) + ":" + str(int(data[5])))

def msg_install(data, comp):
    array = bytearray(16)
    array[c.VERSION] = c.SOFT_VERSION
    array[c.TYPE] = c.INSTALL
    for j in range (c.DATA, c.DATA+6) :
        array[j] = data[j]
    array[c.DATA+6] = comp
    crc_get(array)
    return array


def msg_install_from_mac(mac, num):
    array = bytearray(16)
    array[c.VERSION] = c.SOFT_VERSION
    array[c.TYPE] = c.INSTALL
    # print_flush("Before mac")
    mac_to_array(mac, array, c.DATA )
    # print_flush("After mac")
    array[c.DATA+6] = num
    crc_get(array)
    return array

def msg_ama(amatype):
    array = bytearray(16)
    array[c.VERSION] = c.SOFT_VERSION
    array[c.TYPE]= AMA
    array[c.DATA] = amatype
    crc_get(array)
    return array

def msg_readressage(mac, state=c.STATE_COLOR):#Check why no mac
    array = bytearray(16)
    array[c.VERSION] = c.SOFT_VERSION
    array[c.TYPE] = c.ERROR
    array[c.DATA] = c.ERROR_GOTO
    array[c.DATA+1] = state
    mac_to_array(mac, array, c.DATA+2)
    crc_get(array)
    return array
