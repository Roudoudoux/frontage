#include <stdint.h>
#include "esp_sleep.h"
#include "mesh.h"
#include "state_machine.h"
#include "thread.h"
#include "utils.h"
#include "display_color.h"
#include "logs.h"
#include "frames.h"

//     FRAMES :     BEACON     B_ACK     INSTALL  COLOR     COLOR_E   AMA_INIT  AMA_COLOR  ERROR     REBOOT     LOG
int init_trans[10] = {INIT,     ADDR,     CONF,     INIT,     INIT,     INIT,     INIT,     ERROR_S,  REBOOT_S, INIT};
int conf_trans[10] = {CONF,     CONF,     CONF,     CONF,     CONF,     ADDR,     CONF,     ERROR_S,  REBOOT_S, CONF};
int addr_trans[10] = {ADDR,     ADDR,     ADDR,     ADDR,     ADDR,     ADDR,     COLOR,    ERROR_S,  REBOOT_S, ADDR};
int colo_trans[10] = {ERROR_S,  COLOR,    COLOR,    COLOR,    COLOR,    COLOR,    COLOR,    ERROR_S,  REBOOT_S, COLOR};
int erro_trans[10] = {ERROR_S,  ERROR_S,  ERROR_S,  ERROR_S,  ERROR_S,  ERROR_S,  ERROR_S,  ERROR_S,  REBOOT_S, ERROR_S};
int rebo_trans[10] = {REBOOT_S, REBOOT_S, REBOOT_S, REBOOT_S, REBOOT_S, REBOOT_S, REBOOT_S, REBOOT_S, REBOOT_S, REBOOT_S};

int *transitions[6] = {init_trans, conf_trans, addr_trans, colo_trans, erro_trans, rebo_trans};

int transition(int cstate, int ftype, int fstype){
  if (ftype < 1 || ftype > 9) return cstate;
  if (cstate < 1 || cstate > 6) return REBOOT_S;
  if (ftype == AMA && fstype > AMA_START && fstype < AMA_END) ftype = ftype + (ftype % 10);
  return transitions[cstate - 1][ftype - 1];
}

void reboot(void){ //FIX ME
  state = INIT;
  old_state = INIT;
  esp_mesh_stop();
  esp_wifi_deinit();
  esp_deep_sleep(500);
}

void state_init(uint8_t *buf_recv, uint8_t* buf_log){
  // int type = 0;
  uint8_t buf_send[FRAME_SIZE] = {0,};
  if (esp_mesh_is_root()){
    uint8_t fake_color[FRAME_SIZE] = {0,0,0,0,255,255,0,0,0,0,0,0,0,0,0,0};
    display_color(fake_color);
    if (!is_server_connected) {
      connect_to_server();
      return;
    }
  }
  if (buf_recv == NULL) {
    frame_beacon(buf_send);
    if (esp_mesh_is_root()){
      xRingbufferSend(STQ, buf_send, FRAME_SIZE, FOREVER);
      vTaskDelay(50/portTICK_PERIOD_MS);
    } else {
      xRingbufferSend(MTQ, buf_send, FRAME_SIZE, FOREVER);
      vTaskDelay(500/portTICK_PERIOD_MS);
    }
    return;
  } else {
    log_format(buf_recv, buf_log, "Received an unexpected frame", 28);
    log_send(buf_log, log_length(28));
  }
}

void state_conf(uint8_t *buf_recv, uint8_t *buf_log){
  uint8_t buf_send[FRAME_SIZE] = {0,};
  if (esp_mesh_is_root()) {
    if (!is_server_connected) {
      connect_to_server();
      return;//Root can't progress if not connected to the server
    }
  }
  if (buf_recv == NULL) return;
  int type = type_mesg(buf_recv);
  switch(type) {
    case BEACON:
    {
      //relay beacon frames to server
      xRingbufferSend(STQ, &buf_recv, FRAME_SIZE, FOREVER);
      break;
    }
    case INSTALL:
    {
      //stock the mac in route table
      uint8_t mac[6];
      get_mac(buf_recv, mac);
      add_route_table(mac, buf_recv[DATA+MAC_SIZE]);
      //send beacon_ack to the corresponding esp
      if (!same_mac(mac, my_mac)){
        char log_msg[70];
        int log_msg_size = sprintf(log_msg,"Got install for MAC "MACSTR" at pos %d, acquitted it", MAC2STR(mac), buf_recv[DATA+MAC_SIZE]);
        log_format(buf_recv, buf_log, log_msg, log_msg_size);
        log_send(buf_log, log_length(log_msg_size));
#if CONFIG_MESH_DEBUG_LOG
        ESP_LOGI(MESH_TAG, "Got install for MAC "MACSTR" at pos %d, acquitted it", MAC2STR(mac), buf_recv[DATA+MAC_SIZE]);
#endif
        frame_beacon_ack(buf_send, mac, 0);
        xRingbufferSend(MTQ, &buf_send, FRAME_SIZE, FOREVER);
      }
      break;
    }
    default :
    {
      break;
    }
  }
}

void state_addr(uint8_t *buf_recv, uint8_t* buf_log){
  int type = 0;
  uint8_t buf_send[FRAME_SIZE] = {0,};
  if (esp_mesh_is_root()) {
    if (!is_server_connected) {
      connect_to_server();
      return;//Root can't progress if not connected to the server
    }
  }
  if (buf_recv == NULL) return;
  type = type_mesg(buf_recv);
  switch(type){
    case AMA :
    {
      log_format(buf_recv, buf_log, "Have moved to ADDR", 18);
      log_send(buf_log, log_length(18));
      break;
    }
    case COLOR :
    {
      uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
      if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
        current_sequence = sequ;
        for (int i = 0; i < route_table_size; i++) {
          frame_color_e(buf_send, buf_recv+DATA, buf_recv +DATA+SEQUENCE_SIZE + i*3, route_table[i].card.addr);
          if (!same_mac(route_table[i].card.addr, my_mac)) {
            if (route_table[i].state) {
              xRingbufferSend(MTQ, &buf_send,FRAME_SIZE, FOREVER);
            }
          } else {
            display_color(buf_send);
          }
        }
      }
      break;
    }
    case COLOR_E :
    {
      uint16_t sequ = buf_recv[DATA]  << 8 | buf_recv[DATA+1];
      if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
        current_sequence = sequ;
        display_color(buf_recv);
      }
      break;
    }
    default:
    {
      break;
    }
  }
}

void state_color(uint8_t *buf_recv, uint8_t *buf_log){
  int type = 0;
  uint8_t buf_send[FRAME_SIZE] = {0,};

  if (esp_mesh_is_root()) {
    if (!is_server_connected) {
      connect_to_server();
      return;//Root can't progress if not connected to the server
    }
  }
  type = type_mesg(buf_recv);

  switch(type){
    case AMA :
    {
      if ((buf_recv[SUB_TYPE] == AMA_COLOR) && esp_mesh_is_root()){
        xRingbufferSend(MTQ, &buf_recv, FRAME_SIZE, FOREVER);
      }
      break;
    }
    case COLOR:
    {
      uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
      #if CONFIG_MESH_DEBUG_LOG
      ESP_LOGE(MESH_TAG, "Sequ = %d / current_sequence = %d", sequ, current_sequence);
      #endif
      if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
        current_sequence = sequ;
        for (int i = 0; i < route_table_size; i++) {
          frame_color_e(buf_send, buf_recv +DATA , buf_recv+ DATA + SEQUENCE_SIZE + i*3, route_table[i].card.addr);
          if (!same_mac(route_table[i].card.addr, my_mac)) {
            if (route_table[i].state) {
              xRingbufferSend(MTQ, &buf_send, FRAME_SIZE, FOREVER);
            }
          } else {
            display_color(buf_send);
          }
        }
      }
      break;
    }
    case COLOR_E:
    {
      uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
      if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
        current_sequence = sequ;
        display_color(buf_recv);
      }
      break;
    }
    default:
    {
      break;
    }
  }
}

void state_reboot(uint8_t *buf_recv, uint8_t *buf_log){
  uint8_t buf_send[FRAME_SIZE] = {0,};
  mesh_addr_t broadcast[CONFIG_MESH_ROUTE_TABLE_SIZE];
  int broadcast_size = 0;
  TickType_t waiting_time = 0;
  if (buf_recv != NULL){
    int type = type_mesg(buf_recv);
    switch (type) {
      case REBOOT:
      {
        #if CONFIG_MESH_DEBUG_LOG
        ESP_LOGI(MESH_TAG, "REBOOT_S :je recu un REBOOT");
        #endif
        waiting_time = buf_recv[DATA] << 8 | buf_recv[DATA+1];
        if (esp_mesh_is_root()){
          esp_mesh_get_routing_table((mesh_addr_t *) &broadcast, CONFIG_MESH_ROUTE_TABLE_SIZE*MAC_SIZE, &broadcast_size);
          for (int i=0; i < broadcast_size; i++){
            frame_reboot(buf_send, waiting_time, broadcast[i].addr);
            if (!same_mac(broadcast[i].addr, my_mac)){
              xRingbufferSend(MTQ, &buf_send, FRAME_SIZE, FOREVER);
            }
          }
        }

        break;
      }
      default:
      {
        #if CONFIG_MESH_DEBUG_LOG
        ESP_LOGI(MESH_TAG, "REBOOT_S :je recu un message mais pas un REBOOT");
        #endif
        break;
      }
    }
  } else {
    #if CONFIG_MESH_DEBUG_LOG
    ESP_LOGI(MESH_TAG, "REBOOT_S :je n'ai pas recu de message");
    #endif
    waiting_time = esp_mesh_get_routing_table_size() * 50;
  }
  #if CONFIG_MESH_DEBUG_LOG
  ESP_LOGI(MESH_TAG, "j'attends %d ms avt de reboot", (int) buf_send[DATA] << 8 | buf_send[DATA+1]);
  #endif
  vTaskDelay(waiting_time);
  #if CONFIG_MESH_DEBUG_LOG
  ESP_LOGI(MESH_TAG, "je reboot");
  #endif
  reboot();
}

void state_error(uint8_t *buf_recv, uint8_t *buf_log){
  int type = 0;
  uint8_t buf_send[FRAME_SIZE];
  if (esp_mesh_is_root()) {
    if (!is_server_connected) {
      connect_to_server();
      return;//Root can't progress if not connected to the server
    }
  }
  if (buf_recv == NULL) return;
  type = type_mesg(buf_recv);
  switch (type) {
    case COLOR :
    {
      uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
      #if CONFIG_MESH_DEBUG_LOG
      ESP_LOGE(MESH_TAG, "Sequ = %d / current_sequence = %d", sequ, current_sequence);
      #endif
      if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
        current_sequence = sequ;
        for (int i = 0; i < route_table_size; i++) {
          frame_color_e(buf_send, buf_recv +DATA , buf_recv+ DATA + SEQUENCE_SIZE + i*3, route_table[i].card.addr);
          if (!same_mac(route_table[i].card.addr, my_mac)) {
            if (route_table[i].state) {
              xRingbufferSend(MTQ, &buf_send, FRAME_SIZE, FOREVER);
            }
          } else {
            display_color(buf_send);
          }
        }
      }
      break;
    }
    case COLOR_E:
    {
      uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
      if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
        current_sequence = sequ;
        display_color(buf_recv);
      }
      break;
    }
    case ERROR:
    {
      #if CONFIG_MESH_DEBUG_LOG
          ESP_LOGI(MESH_TAG, "Error frame received - %d", buf_recv[DATA+1]);
      #endif
      switch (sub_type(buf_recv)) {
        case ERROR_ROOT:
        {
          #if CONFIG_MESH_DEBUG_LOG
          ESP_LOGE(MESH_TAG, "This frame has nothing to do in the state machine");
          #endif
          break;
        }
        case ERROR_CO:
        {
          // Frame comming from ?
          if ((buf_recv[DATA+1] & (1 << 7)) == 0 ){ // Mesh Netwoork
            xRingbufferSend(STQ, &buf_recv, FRAME_SIZE, FOREVER);
          } else { // Server
            #if CONFIG_MESH_DEBUG_LOG
            	      ESP_LOGI(MESH_TAG, "Acquiting new card");
            #endif
            // The card is known from server ?
            if ((buf_recv[DATA+1] & (1<<5)) == 0) { // yes, return in its rightful state
              #if CONFIG_MESH_DEBUG_LOG
                 ESP_LOGW(MESH_TAG, "enabling node");
              #endif
    	        enable_node(buf_recv + DATA + 2);
              frame_error(buf_send, ERROR_GOTO, buf_recv, buf_recv + DATA + 2);
              xRingbufferSend(MTQ, &buf_send, FRAME_SIZE, FOREVER);
            } else { // no, is put in ERROR_S
              frame_beacon_ack(buf_send, buf_recv + DATA + 2, 1);
              xRingbufferSend(MTQ, &buf_send, FRAME_SIZE, FOREVER);
              old_state = ERROR_S;
            }
          }
          break;
        }
        case ERROR_DECO:
        {
          // Frame comming from ?
          if ((buf_recv[DATA+1] & (1 << 7)) == 0 ){ // Mesh Netwoork
            #if CONFIG_MESH_DEBUG_LOG
            	      ESP_LOGI(MESH_TAG, "Deco frame received : applying modif");
            #endif
            disable_node(buf_recv + DATA + 2);
            xRingbufferSend(STQ, &buf_recv, FRAME_SIZE, FOREVER);
          }
          break;
        }
        case ERROR_GOTO:
        {
          // Is the frame addressed to me ?
          if (same_mac(buf_recv + DATA + 2, my_mac)){ // yes, I changed of state
            old_state = buf_recv[DATA+1] & 0x0F;
            #if CONFIG_MESH_DEBUG_LOG
            	      ESP_LOGI(MESH_TAG, "ERROR_GO : state %d", state);
            #endif
          } else { // no, I Forward it
            xRingbufferSend(MTQ, &buf_recv, FRAME_SIZE, FOREVER);
            #if CONFIG_MESH_DEBUG_LOG
            	      ESP_LOGW(MESH_TAG, "Forwarded GOTO frame");
            #endif
          }
          break;
        }
        default:
        break;
      }
      state = old_state;
      break;
    }
    case BEACON :
    {
      frame_error(buf_send, ERROR_CO, buf_recv, buf_recv + DATA);
      xRingbufferSend(STQ, &buf_send, FRAME_SIZE, FOREVER);
      break;
    }
    case B_ACK:
    {
      if (buf_recv[DATA] == 0) {
        state = ADDR;
  #if CONFIG_MESH_DEBUG_LOG
        ESP_LOGE(MESH_TAG, "Went into ADDR state");
  #endif
      } else {
  #if CONFIG_MESH_DEBUG_LOG
        ESP_LOGE(MESH_TAG, "There is still an error with the HaR procedure, sorry :/");
  #endif
      }
      break;
    }
    default:
    break;
  }
}
