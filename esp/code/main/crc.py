CRC_p = 7
B0 = 1
B1 = 1 << 1
B2 = 1 << 2
B3 = 1 << 3
B4 = 1 << 4
B5 = 1 << 5
B6 = 1 << 6
B7 = 1 << 7


def crc_compute(frame) :
    global CRC_p, B0, B1, B2, B3, B4, B5, B6, B7
    b0 = b1 = b2 = b3 = b4 = b5 = b6 = b7= 0
    size = min(len(frame), CRC_p)
    for i in range(0, size-1) :
        b0 = b0 ^ (B0 & frame[i]);
        b1 = b1 ^ (B1 & frame[i]);
        b2 = b2 ^ (B2 & frame[i]);
        b3 = b3 ^ (B3 & frame[i]);
        b4 = b4 ^ (B4 & frame[i]);
        b5 = b5 ^ (B5 & frame[i]);
        b6 = b6 ^ (B6 & frame[i]);
        b7 = b7 ^ (B7 & frame[i]);
    return(b7|b6|b5|b4|b3|b2|b1|b0)

def crc_get(frame):
    global CRC_p
    size = len(frame)
    crc_size = int(size / (CRC_p + 1))
    if ((crc_size * (CRC_p +1) != size)):
        crc_size += 1
    offset = 0
    fsc = size - crc_size
    while (crc_size > 0):
        frame[size-crc_size] = crc_compute(frame[offset:fsc])
        fsc -= CRC_p
        crc_size-=1
        offset += CRC_p

def crc_check(frame) :
    global CRC_p
    size = len(frame)
    crc_size = int(size / (CRC_p + 1))
    if ((crc_size * (CRC_p +1) != size)):
        crc_size += 1
    offset = 0
    fsc = size - crc_size
    while (crc_size > 0 and frame[size-crc_size] == crc_compute(frame[offset:fsc])):
        fsc -= CRC_p
        crc_size-=1
        offset += CRC_p
    return(crc_size == 0)
