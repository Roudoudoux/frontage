#include <stdint.h>
#include "crc.h"


uint8_t compute_crc(uint8_t * frame, uint16_t size){
    //used to choose the right mask to apply for the one-of-three bits sums.
    int offset = 0;
    //temporary variables to stock Byte's bits.
    int B1 = 0;
    int B2 = 0;
    int B3 = 0;
    int B4 = 0;
    int B5 = 0;
    int B6 = 0;
    int B7 = 0;
    int B8 = 0;
    //temporary sums
    int b1 = 0;
    int b2 = 0;
    int b3 = 0;
    int b4 = 0;
    int b5 = 0;
    int b6 = 0;
    int i;
    for (i = 0; i < size-1; i++) {
	B1 = (frame[i] & 1);
	B2 = (frame[i] & 2) >> 1;
	B3 = (frame[i] & 4) >> 2;
	B4 = (frame[i] & 8) >> 3;
	B5 = (frame[i] & 16) >> 4;
	B6 = (frame[i] & 32) >> 5;
	B7 = (frame[i] & 64) >> 6;
	B8 = (frame[i] & 128) >> 7;
	b1 = b1 + B1 + B2 + B3 + B4 + B5 + B6 + B7 + B8;
	b2 = b2 + B2 + B4 + B6 + B8;
	b3 = b3 + B1 + B3 + B5 + B7;
	if (offset == 0) {
	    b4 = b4 + M3_1;
	    b5 = b5 + M3_2;
	    b6 = b6 + M3_3;
	} else if (offset == 1) {
	    b4 = b4 + M3_2;
	    b5 = b5 + M3_3;
	    b6 = b6 + M3_1;
	} else {
	    b4 = b4 + M3_3;
	    b5 = b5 + M3_1;
	    b6 = b6 + M3_2;
	}
	offset = (offset + 1)%3;
    }
    return b1%2 << 6 | b2%2 << 5 | b3%2 << 4 | b4%2 << 3 | b5%2 << 2 | b6%2 << 1 | (b1 + b2 + b3 + b4 + b5 + b6)%2;
}

void set_crc(uint8_t * frame, uint16_t size){
    frame[size-1] = compute_crc(frame, size);
}

int check_crc(uint8_t * frame, uint16_t size) {
    return frame[size-1] == compute_crc(frame, size);
}
