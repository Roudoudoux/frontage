#include "frames.h"
#include "utils.h"

void frame_beacon(uint8_t *buf_send){
  buf_send[VERSION] = SOFT_VERSION;
  buf_send[TYPE] = BEACON;
  copy_mac(my_mac, buf_send+DATA);
}

void frame_beacon_ack(uint8_t *buf_send, uint8_t *mac, uint8_t unk){
  buf_send[VERSION] = SOFT_VERSION;
  buf_send[TYPE] = B_ACK;
  buf_send[DATA] = unk;
  copy_buffer(buf_send+DATA+1, mac, MAC_SIZE);
}

void frame_color_e(uint8_t *buf_send, uint8_t* seq, uint8_t * color, uint8_t *mac){
  buf_send[VERSION] = SOFT_VERSION;
  buf_send[TYPE] = COLOR_E;
  copy_buffer(buf_send+DATA, seq, SEQUENCE_SIZE);
	copy_buffer(buf_send+DATA+2, color, RGB_SIZE); // copy color triplet
	copy_buffer(buf_send+DATA+5, mac, MAC_SIZE);
}

void frame_reboot(uint8_t *buf_send, unsigned int time_to_wait, uint8_t *mac){
  buf_send[VERSION] = SOFT_VERSION;
  buf_send[TYPE] = REBOOT;
  buf_send[DATA] = time_to_wait >> 8;
  buf_send[DATA+1] = time_to_wait & 0x00FF;
  copy_buffer(buf_send+DATA+2, mac, MAC_SIZE);
}

void frame_error(uint8_t *buf_send, int subtype, uint8_t *buf_recv, uint8_t *mac){
  buf_send[VERSION] = SOFT_VERSION;
  buf_send[TYPE] = ERROR;
  buf_send[DATA] = subtype;
  if (subtype == ERROR_GOTO){
    buf_send[DATA+1] = buf_recv[DATA+1] & 0x0F;
  } else {
    buf_send[DATA+1] = ERROR_S;
  }
  copy_buffer(buf_send+DATA+2, mac, MAC_SIZE);
}
