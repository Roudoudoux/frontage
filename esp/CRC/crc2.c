#include <stdio.h>
#include <sys/time.h>
#include <unistd.h>
#include <asm/unistd.h>

#define M3_1 B2 + B5 + B8
#define M3_2 B1 + B4 + B7
#define M3_3 B3 + B6


int check_crc(int * frame) {
    int offset = 0;
    int B1 = 0;
    int B2 = 0;
    int B3 = 0;
    int B4 = 0;
    int B5 = 0;
    int B6 = 0;
    int B7 = 0;
    int B8 = 0;
    int size = 16; //HC
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
    frame[size-1] = b1%2 << 6 | b2%2 << 5 | b3%2 << 4 | b4%2 << 3 | b5%2 << 2 | b6%2 << 1 | (b1 + b2 + b3 + b4 + b5 + b6)%2;
    //return frame[size-1];
}



int main() {
    struct timeval tv1, tv2;
    int frame[16] = {1, 3, 172, 48, 36, 96, 58, 42, 1, 0, 0, 0, 0, 0, 0, 0};
    gettimeofday(&tv1, NULL);
    int i = 0;
    while (i < 10000) {
	i++;
	check_crc(frame);
    }
    gettimeofday(&tv2, NULL);
    unsigned long microseconds = (tv2.tv_sec - tv1.tv_sec) * 1000000 + (tv2.tv_usec - tv1.tv_usec);
    printf("Res = %d with time %f µs\n", frame[15], (double)microseconds/10000);
    return 0;
}
