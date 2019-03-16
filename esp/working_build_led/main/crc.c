#include <stdint.h>
#include "crc.h"
#include "mesh.h"

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
