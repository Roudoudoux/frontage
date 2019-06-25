#include "mesh.h"
#include "crc.h"
#include "utils.h"

#define MAC_POS HEADER_SIZE
#define TIME_POS (MAC_POS + MAC_SIZE)
#define TIME_SIZE 8
#define BDATA_POS (TIME_POS + TIME_SIZE)
#define BASIC_DATA_SIZE 2
#define MSG_POS (BDATA_POS + BASIC_DATA_SIZE)

int log_length(int log_msg_size){
  int raw_data = HEADER_SIZE + MAC_SIZE + TIME_SIZE + BASIC_DATA_SIZE + log_msg_size +1;
  int log_size = raw_data + raw_data / 7;
  if (raw_data % 7 != 0) {
    log_size++;
  }
  return log_size;
}

void log_basic_data(uint8_t * log, int type, int sub_type){
  log[BDATA_POS] = state << 5;
  log[BDATA_POS] = (esp_mesh_get_routing_table_size() & 0x1F) | log[BDATA_POS];
  log[BDATA_POS + 1] = ((esp_mesh_get_layer() << 4) & 0xF0);
  switch (type) {
    case BEACON:
    {
      log[BDATA_POS + 1] = log[BDATA_POS + 1] | 0x01;
      break;
    }
    case B_ACK:
    {
      log[BDATA_POS + 1] = log[BDATA_POS + 1] | 0x02;
      break;
    }
    case INSTALL:
    {
      log[BDATA_POS + 1] = log[BDATA_POS + 1] | 0x03;
      break;
    }
    case COLOR:
    {
      log[BDATA_POS + 1] = log[BDATA_POS + 1] | 0x04;
      break;
    }
    case COLOR_E:
    {
      log[BDATA_POS + 1] = log[BDATA_POS + 1] | 0x05;
      break;
    }
    case AMA:
    {
      switch (sub_type) {
        case AMA_INIT:
        {
          log[BDATA_POS + 1] = log[BDATA_POS + 1] | 0x06;
          break;
        }
        case AMA_COLOR:
        {
          log[BDATA_POS + 1] = log[BDATA_POS + 1] | 0x07;
          break;
        }
        default:
        {
          log[BDATA_POS + 1] = log[BDATA_POS + 1] | 0x0F;
          break;
        }
      }
      break;
    }
    case ERROR:
    {
      switch (sub_type) {
        case ERROR_CO:
        {
          log[BDATA_POS + 1] = log[BDATA_POS + 1] | 0x09;
          break;
        }
        case ERROR_DECO:
        {
          log[BDATA_POS + 1] = log[BDATA_POS + 1] | 0x0A;
          break;
        }
        case ERROR_GOTO:
        {
          log[BDATA_POS + 1] = log[BDATA_POS + 1] | 0x0B;
          break;
        }
        case ERROR_ROOT:
        {
          log[BDATA_POS + 1] = log[BDATA_POS + 1] | 0x0C;
          break;
        }
        default:
        {
          log[BDATA_POS + 1] = log[BDATA_POS + 1] | 0x0F;
          break;
        }
      }
      break;
    }
    case REBOOT:
    {
      log[BDATA_POS + 1] = log[BDATA_POS + 1] | 0x0D;
      break;
    }
    default:
    {
      log[BDATA_POS + 1] = log[BDATA_POS + 1] | 0x0F;
      break;
    }
  }
}

void log_format(uint8_t* frame, uint8_t *log_frame, char * log_msg, int log_msg_size){
  log_frame[VERSION] = SOFT_VERSION;
  log_frame[TYPE] = LOG;
  copy_mac(my_mac, &(log_frame[MAC_POS]));
  log_basic_data(log_frame, frame[TYPE], frame[SUB_TYPE]);

  for(int i = 0 ; i < log_msg_size; i++){
    log_frame[MSG_POS + i] = log_msg[i];
  }
  log_frame[MSG_POS + log_msg_size] = '\0';

  int64_t time = esp_timer_get_time();
  for (int i = 0; i < TIME_SIZE; i++){
    log_frame[TIME_POS + i] = (time >> ((TIME_SIZE-i-1) * 8)) & 0xFF;
  }

  set_crc(log_frame, log_length(log_msg_size));
}


void log_send(uint8_t *log_frame, int log_size) {
  #if SERVER_LOG
  if ( !esp_mesh_is_root()){
    xRingbufferSend(MTQ, log_frame, log_size, FOREVER);
  } else {
    xRingbufferSend(STQ, log_frame, log_size, FOREVER);
  }
  #else
  //write logs on SD card
  #endif
}
