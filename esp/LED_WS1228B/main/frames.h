#include "mesh.h"

void frame_beacon(uint8_t *buf_send);

void frame_beacon_ack(uint8_t *buf, uint8_t *mac, uint8_t opt);

void frame_color_e(uint8_t *buf_send, uint8_t* seq, uint8_t * color, uint8_t *mac);

void frame_reboot(uint8_t *buf_send, unsigned int time_to_wait, uint8_t *mac);
