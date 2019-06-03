from math import ceil
from random import randint

class Checksum:
    def __init__(self):
        self.CRC_p = 7
        self.B0 = 1
        self.B1 = 1 << 1
        self.B2 = 1 << 2
        self.B3 = 1 << 3
        self.B4 = 1 << 4
        self.B5 = 1 << 5
        self.B6 = 1 << 6
        self.B7 = 1 << 7

    def size(self, frame_length):
        return ceil(frame_length/7)

    def __compute(self, frame):
        b0 = b1 = b2 = b3 = b4 = b5 = b6 = b7= 0
        c_size = min(len(frame), self.CRC_p)
        for i in range(0, c_size) :
            b0 = b0 ^ (self.B0 & frame[i]);
            b1 = b1 ^ (self.B1 & frame[i]);
            b2 = b2 ^ (self.B2 & frame[i]);
            b3 = b3 ^ (self.B3 & frame[i]);
            b4 = b4 ^ (self.B4 & frame[i]);
            b5 = b5 ^ (self.B5 & frame[i]);
            b6 = b6 ^ (self.B6 & frame[i]);
            b7 = b7 ^ (self.B7 & frame[i]);
        return(b7|b6|b5|b4|b3|b2|b1|b0)

    def set(self, frame):
        f_size = len(frame)
        crc_size = int(f_size / (self.CRC_p + 1))
        if ((crc_size * (self.CRC_p + 1) != f_size)):
            crc_size += 1
        offset = 0
        fsc = f_size - crc_size
        while (crc_size > 0):
            frame[f_size-crc_size] = self.__compute(frame[offset:fsc])
            crc_size-=1
            offset += self.CRC_p

    def check(self, frame) :
        f_size = len(frame)
        crc_size = int(f_size / (self.CRC_p + 1))
        if ((crc_size * (self.CRC_p + 1) != f_size)):
            crc_size += 1
        offset = 0
        fsc = f_size - crc_size
        while (crc_size > 0 and frame[f_size-crc_size] == self.__compute(frame[offset:fsc])):
            crc_size-=1
            offset += self.CRC_p
        return(crc_size == 0)


if __name__ == '__main__':
    test = Checksum()
    frames = [bytearray(i*3+4) for i in range(6)]
    for frame in frames:
        l = len(frame)
        c_size = test.size(l)
        for i in range(l - c_size):
            frame[i] = randint(0,255)
        test.set(frame)
        assert(test.check(frame))
