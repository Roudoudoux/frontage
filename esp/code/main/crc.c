#include <stdint.h>
#include <assert.h>
#include <stdio.h>
//#include "crc.h"

/*
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
*/
#define B0 1
#define B1 (1 <<1)
#define B2 (1 <<2)
#define B3 (1 <<3)
#define B4 (1 <<4)
#define B5 (1 <<5)
#define B6 (1 <<6)
#define B7 (1 << 7)
#define CRC_p 7

int min(int a, int b){
  if (a > b){
    return b;
  }
  return a;
}

uint8_t compute_crc(uint8_t * frame, int size){
  uint8_t b0 = 0;
  uint8_t b1 = 0;
  uint8_t b2 = 0;
  uint8_t b3 = 0;
  uint8_t b4 = 0;
  uint8_t b5 = 0;
  uint8_t b6 = 0;
  uint8_t b7 = 0;
  int fsize = min(size, CRC_p);
  for(int i=0; i < fsize; i++){
    b0 = b0 ^ (B0 & frame[i]);
    b1 = b1 ^ (B1 & frame[i]);
    b2 = b2 ^ (B2 & frame[i]);
    b3 = b3 ^ (B3 & frame[i]);
    b4 = b4 ^ (B4 & frame[i]);
    b5 = b5 ^ (B5 & frame[i]);
    b6 = b6 ^ (B6 & frame[i]);
    b7 = b7 ^ (B7 & frame[i]);
  }
  return (b7 | b6 | b5 | b4 | b3 | b2 | b1 | b0);
}

void set_crc(uint8_t * frame, uint16_t size){
  int crc_size = (size / (CRC_p+1));
  if ((crc_size * (CRC_p +1)) != size) {
    crc_size++;
  }
  int offset = 0;
  int fsc = size - crc_size;
  while(crc_size > 0){
    frame[size-crc_size] = compute_crc(frame + offset, fsc);
    fsc = fsc - CRC_p;
    crc_size--;
    offset += CRC_p;
  }
}

int check_crc(uint8_t * frame, uint16_t size) {
  int crc_size = (size / (CRC_p+1));
  if ((crc_size * (CRC_p +1)) != size) {
    crc_size++;
  }
  int offset = 0;
  int fsc = size - crc_size;
  while(crc_size > 0 && frame[size-crc_size] == compute_crc(frame + offset, fsc)){
    fsc = fsc - CRC_p;
    crc_size--;
    offset += CRC_p;
  }
  return crc_size == 0;
}
