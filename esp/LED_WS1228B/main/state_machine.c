#include <stdint.h>
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
int colo_trans[10] = {COLOR,    COLOR,    COLOR,    COLOR,    COLOR,    COLOR,    COLOR,    ERROR_S,  REBOOT_S, COLOR};
int erro_trans[10] = {ERROR_S,  ERROR_S,  ERROR_S,  ERROR_S,  ERROR_S,  ERROR_S,  ERROR_S,  ERROR_S,  REBOOT_S, ERROR_S};
int rebo_trans[10] = {REBOOT_S, REBOOT_S, REBOOT_S, REBOOT_S, REBOOT_S, REBOOT_S, REBOOT_S, REBOOT_S, REBOOT_S, REBOOT_S};

int *transitions[6] = {init_trans, conf_trans, addr_trans, colo_trans, erro_trans, rebo_trans};

int transition(int cstate, int ftype, int fstype){
  if (ftype < 1 || ftype > 9) return cstate;
  if (cstate < 1 || cstate > 6) return REBOOT_S;
  if (ftype == AMA && fstype > AMA_START && fstype < AMA_END) ftype = ftype + (ftype % 10);
  return transitions[cstate - 1][ftype - 1];
}

void state_init(uint8_t *buf_recv, uint8_t* buf_log){
  int type = 0;
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

void state_init_old(uint8_t *buf_recv) {
  int type = 0;
  uint8_t buf_send[FRAME_SIZE] = {0,};
  if (esp_mesh_is_root()) {
    uint8_t fake[FRAME_SIZE] = {0, 0, 0, 0, 255, 255, 0};
    display_color(fake);
    if (!is_server_connected) {
      connect_to_server();
      return;//Root can't progress if not connected to the server
    }
  }

  /* Check if it has received an acknowledgement */
  if (buf_recv != NULL){
    while (type != 254) {
      type = type_mesg(buf_recv);
    if (type == B_ACK) {
      if (!esp_mesh_is_root()) { //dummy test
        if (buf_recv[DATA] == 1) { //Error flag is raised
          state = ERROR_S;
#if CONFIG_MESH_DEBUG_LOG
          ESP_LOGE(MESH_TAG, "Acquitted, but went into ERROR state");
#endif
          return;
        }
        uint8_t fake[FRAME_SIZE] = {0, 0, 0, 0, 0, 0, 255}; //Node cards will light up in blue while not initialised
        display_color(fake);
        state = ADDR;
#if CONFIG_MESH_DEBUG_LOG
        ESP_LOGE(MESH_TAG, "Went into ADDR state");
#endif
        return;
      }
    } else if (type == INSTALL) {
      if (esp_mesh_is_root()) { //dummy test
        uint8_t mac[6];
        get_mac(buf_recv, mac);
        add_route_table(mac, 0);
        state = CONF;
#if CONFIG_MESH_DEBUG_LOG
        ESP_LOGE(MESH_TAG, "Went into CONF state");
#endif
        return;
      }
    }
    else if (type == ERROR) {
      copy_buffer(buf_err, buf_recv, FRAME_SIZE);
      if (buf_err[DATA] != ERROR_GOTO) {
        buf_err[DATA+1] = buf_err[DATA+1] | state;
      }
      err_prev_state = state;
      state = ERROR_S;
#if CONFIG_MESH_DEBUG_LOG
      ESP_LOGE(MESH_TAG, "Received Error frame : went into ERROR state - %d", state);
#endif
      return;
    }
    else if (type == REBOOT) {
      state = REBOOT_S;
    }
  }
}
  /*Creation of BEACON frame */
  frame_beacon(buf_send);
  ESP_LOGI(MESH_TAG, "Message %d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d BEACON before queue", (int) buf_send[0], (int) buf_send[1], (int) buf_send[2], (int) buf_send[3], (int) buf_send[4], (int) buf_send[5], (int) buf_send[6], (int) buf_send[7], (int) buf_send[8], (int) buf_send[9], (int) buf_send[10], (int) buf_send[11], (int) buf_send[12], (int) buf_send[13], (int) buf_send[14], (int) buf_send[15]);
  if (esp_mesh_is_root()) {
    xRingbufferSend(STQ, &buf_send, FRAME_SIZE, FOREVER);
  }
  else {
    xRingbufferSend(MTQ, &buf_send, FRAME_SIZE, FOREVER);
  }
  vTaskDelay(5000 / portTICK_PERIOD_MS); //Stop for 5s after each beacon
}

void state_conf(uint8_t *buf_recv, uint8_t *buf_log){
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
  switch(state) {
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

void state_conf_old(uint8_t *buf_recv) {
  int type = 0;
  uint8_t buf_send[FRAME_SIZE] = {0,};
  if (esp_mesh_is_root()) {
    if (!is_server_connected) {
      connect_to_server();
      return;//Root can't progress if not connected to the server
    }
  }

  type = type_mesg(buf_recv);

  if (type == BEACON) {
#if CONFIG_MESH_DEBUG_LOG
    ESP_LOGI(MESH_TAG, "Received a beacon, transfered");
#endif
    // copy_buffer(buf_send, buf_recv, FRAME_SIZE);
    xRingbufferSend(STQ, &buf_recv, FRAME_SIZE, FOREVER);
  }
  else if (type == REBOOT) {
    state = REBOOT_S;
    #if CONFIG_MESH_DEBUG_LOG
        ESP_LOGI(MESH_TAG, "je passe en REBOOT state potow %d", type);
    #endif
    xRingbufferSend(RQ, &buf_recv, FRAME_SIZE, FOREVER);
    //write_rxbuffer(buf_recv, FRAME_SIZE);
  }
  else if (type == INSTALL) {
    uint8_t mac[6];
    get_mac(buf_recv, mac);
    add_route_table(mac, buf_recv[DATA+MAC_SIZE]);
#if CONFIG_MESH_DEBUG_LOG
    ESP_LOGI(MESH_TAG, "Got install for MAC "MACSTR" at pos %d, acquitted it", MAC2STR(mac), buf_recv[DATA+6]);
#endif
    frame_beacon_ack(buf_send, buf_recv+DATA, 0);
    xRingbufferSend(MTQ, &buf_send, FRAME_SIZE, FOREVER);
  }
  else if (type == AMA) {
    if (buf_recv[DATA] == AMA_INIT) {
      state = ADDR;
#if CONFIG_MESH_DEBUG_LOG
      ESP_LOGE(MESH_TAG, "Went into ADDR state");
#endif
    }
  }
  else if (type == ERROR) { //Check if doesn't provoke trouble : catch any kind of ERROR frame. Here, should only be GOTO.
    copy_buffer(buf_err, buf_recv, FRAME_SIZE);
    if (buf_err[DATA] != ERROR_GOTO) {
      buf_err[DATA+1] = buf_err[DATA+1] | state;
    }
    err_prev_state = state;
    state = ERROR_S;
#if CONFIG_MESH_DEBUG_LOG
    ESP_LOGE(MESH_TAG, "Received Error frame : went into ERROR state - %d", state);
#endif
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

void state_addr_old(uint8_t *buf_recv) {
  int type = 0;
  uint8_t buf_send[FRAME_SIZE] = {0,};

  if (esp_mesh_is_root()) {
    if (!is_server_connected) {
      connect_to_server();
      return;//Root can't progress if not connected to the server
    }
  }

  // read_rxbuffer(buf_recv);
  type = type_mesg(buf_recv);
  if (type == COLOR) { // Root only
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
  }
  else if (type == REBOOT) {
    state = REBOOT_S;
  }
  else if (type == COLOR_E) {//Mixed
    uint16_t sequ = buf_recv[DATA]  << 8 | buf_recv[DATA+1];
    if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
      current_sequence = sequ;
      display_color(buf_recv);
    }
  }
  else if (type == AMA) { //Mixed
    if (buf_recv[DATA] == AMA_COLOR) {
      if (esp_mesh_is_root()) {
        copy_buffer(buf_send, buf_recv, FRAME_SIZE);
        xRingbufferSend(MTQ, &buf_send, FRAME_SIZE, FOREVER);
      }
      state = COLOR;
#if CONFIG_MESH_DEBUG_LOG
      ESP_LOGE(MESH_TAG, "Went into COLOR state");
#endif
    }
  }
  else if (type == ERROR) {
    copy_buffer(buf_err, buf_recv, FRAME_SIZE);
    err_prev_state = state;
    state = ERROR_S;
#if CONFIG_MESH_DEBUG_LOG
    ESP_LOGE(MESH_TAG, "Received Error frame : went into ERROR state (%d)", state);
#endif
  }
  else if (type == BEACON) { //Anomalous beacon received : error frame raised.
    buf_err[VERSION] = SOFT_VERSION;
    buf_err[TYPE] = ERROR;
    buf_err[DATA] = ERROR_CO;
    buf_err[DATA+1] = state;
    err_prev_state = state;
    copy_buffer(buf_err + DATA + 2, buf_recv + DATA, 6);
    state = ERROR_S;
#if CONFIG_MESH_DEBUG_LOG
    ESP_LOGE(MESH_TAG, "Received Beacon frame : went into ERROR state");
#endif
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

  switch(state){
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

void state_color_old(uint8_t *buf_recv) {
  int type = 0;
  uint8_t buf_send[FRAME_SIZE] = {0,};

  if (esp_mesh_is_root()) {
    if (!is_server_connected) {
      connect_to_server();
      return;//Root can't progress if not connected to the server
    }
  }

  type = type_mesg(buf_recv);

  if (type == COLOR) { // Root only
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
  }
  else if (type == REBOOT) {
    state = REBOOT_S;
  }
  else if (type == COLOR_E) {//Mixed
    uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
    if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
      current_sequence = sequ;
      display_color(buf_recv);
    }
  }
  else if (type == ERROR) {
    copy_buffer(buf_err, buf_recv, FRAME_SIZE);
    err_prev_state = state;
    state = ERROR_S;
#if CONFIG_MESH_DEBUG_LOG
    ESP_LOGE(MESH_TAG, "Received Error frame : went into ERROR state - %d", state);
#endif
  }
  else if (type == BEACON) { //Anomalous beacon received : error frame raised.
    buf_err[VERSION] = SOFT_VERSION;
    buf_err[TYPE] = ERROR;
    buf_err[DATA] = ERROR_CO;
    buf_err[DATA+1] = state;
    copy_buffer(buf_err + DATA + 2, buf_recv + DATA, 6);
    err_prev_state = state;
    state = ERROR_S;
#if CONFIG_MESH_DEBUG_LOG
    ESP_LOGE(MESH_TAG, "Received BEACON frame : went into ERROR state");
#endif
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
  esp_restart();
}



void state_reboot_old(uint8_t *buf_recv) {
  int type = 0;
  uint8_t buf_send[FRAME_SIZE] = {0,};
  mesh_addr_t broadcast[CONFIG_MESH_ROUTE_TABLE_SIZE];
  int broadcast_size = 0;

  type = type_mesg(buf_recv);
  int i=0;
  #if CONFIG_MESH_DEBUG_LOG
  ESP_LOGI(MESH_TAG, "je suis en reboot state potow %d", type);
  #endif
  buf_send[VERSION] = SOFT_VERSION;
  buf_send[TYPE] = REBOOT;
  buf_send[DATA] = buf_recv[DATA]; // time before restart strong bits;
  buf_send[DATA+1] = buf_recv[DATA+1]; // time before restart weak bits;

  if (esp_mesh_is_root()) {
    esp_mesh_get_routing_table((mesh_addr_t *) &broadcast, CONFIG_MESH_ROUTE_TABLE_SIZE*MAC_SIZE, &broadcast_size);
    for(i=0; i < broadcast_size; i++){
      copy_buffer(buf_send+DATA+2, broadcast[i].addr, 6);
      if (!same_mac(broadcast[i].addr, my_mac)) {
        xRingbufferSend(MTQ, &buf_send, FRAME_SIZE, FOREVER);
      }
    }
  }
  if (type == REBOOT){
    const TickType_t waiting_time = buf_send[DATA] << 8 | buf_send[DATA+1];
    #if CONFIG_MESH_DEBUG_LOG
    ESP_LOGI(MESH_TAG, "j'attends %d ms avt de reboot", (int) buf_send[DATA] << 8 | buf_send[DATA+1]);
    #endif
    vTaskDelay(waiting_time);
    #if CONFIG_MESH_DEBUG_LOG
    ESP_LOGI(MESH_TAG, "je reboot");
    #endif
    esp_restart();
  }

  #if CONFIG_MESH_DEBUG_LOG
  ESP_LOGI(MESH_TAG, "je n'ai pas reboot");
  #endif
}

void state_error(uint8_t *buf_recv, uint8_t *buf_log){

}

void state_error_old(uint8_t *buf_recv) {
  int type = 0;
  uint8_t buf_send[FRAME_SIZE] = {0,};
#if CONFIG_MESH_DEBUG_LOG
ESP_LOGI(MESH_TAG, "Entered Error state");
#endif
  const int len = CONFIG_MESH_ROUTE_TABLE_SIZE * 3 + 5 + (CONFIG_MESH_ROUTE_TABLE_SIZE * 3 + 4)/7;
  uint8_t buf_blank[FRAME_SIZE] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};

  if (esp_mesh_is_root()) {
    if (!is_server_connected) {
      connect_to_server();
      return;//Root can't progress if not connected to the server
    }
  }

  if (buf_err[TYPE] != 0) { //An error has already been received. As frame are consummed on reading, there is an exception for this frame, which is stocked in this special buffer. As such, this buffer should be read before trying to read from the reception buffer
    if (FRAME_SIZE < len) {
      copy_buffer(buf_recv, buf_err, FRAME_SIZE);
    } else {
      copy_buffer(buf_recv, buf_err, len);
    }
    copy_buffer(buf_err, buf_blank, FRAME_SIZE); //Reset buf_err to show the error has been considered
  }
  type = type_mesg(buf_recv);

  if (type == COLOR) { // Root only
    uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
#if CONFIG_MESH_DEBUG_LOG
    ESP_LOGE(MESH_TAG, "Sequ = %d", sequ);
#endif
    if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
      current_sequence = sequ;
      buf_send[VERSION] = SOFT_VERSION;
      buf_send[TYPE] = COLOR_E;
      for (int i = 0; i < route_table_size; i++) {
        copy_buffer(buf_send+DATA, buf_recv+DATA, 2);
        copy_buffer(buf_send+DATA+2, buf_recv+DATA+2+i*3, 3); // copy color triplet
        copy_buffer(buf_send+DATA+5, route_table[i].card.addr, 6); // copy mac adress
        if (!same_mac(route_table[i].card.addr, my_mac)) {
          if (route_table[i].state) {
            xRingbufferSend(MTQ, &buf_send, FRAME_SIZE, FOREVER);
          }
        } else {
          display_color(buf_send);
        }
      }
    }
  }

  else if (type == COLOR_E) {//Mixed
    uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
    if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
      current_sequence = sequ;
      display_color(buf_recv);
    }
  }
  else if (type == REBOOT) {
    state = REBOOT_S;
  }
  else if (type == ERROR) {
#if CONFIG_MESH_DEBUG_LOG
    ESP_LOGI(MESH_TAG, "Error frame received - %d", buf_recv[DATA+1]);
#endif
    if (buf_recv[DATA] == ERROR_GOTO) {
      if (same_mac(buf_recv + DATA + 2, my_mac)) { //Check if the message is for him.
        err_addr_req = 0;
        state = buf_recv[DATA+1] & 0x0F;
#if CONFIG_MESH_DEBUG_LOG
	      ESP_LOGI(MESH_TAG, "ERROR_GO : state %d", state);
#endif
	      return;
      } else { //Forward the message.
        buf_send[VERSION] = SOFT_VERSION;
        buf_send[TYPE] = ERROR;
        buf_send[DATA] = ERROR_GOTO;
        buf_send[DATA+1] = buf_recv[DATA+1] & 0x0F;
        copy_buffer(buf_send+DATA+2, buf_recv+DATA+2, 6);
        xRingbufferSend(MTQ, &buf_send, FRAME_SIZE, FOREVER);
#if CONFIG_MESH_DEBUG_LOG
	      ESP_LOGW(MESH_TAG, "Forwarded GOTO frame");
#endif
	      if (err_addr_req == 0) { //If possible, go out the error state.
          state = err_prev_state;
        }
      }
    }
    if ((buf_recv[DATA+1] & (1<<7)) == 0) {//ACK flag is down : message from the mesh network
#if CONFIG_MESH_DEBUG_LOG
      ESP_LOGI(MESH_TAG, "No ACK");
#endif
      if (buf_recv[DATA] == ERROR_DECO) {
#if CONFIG_MESH_DEBUG_LOG
	      ESP_LOGI(MESH_TAG, "Deco frame received : applying modif");
#endif
	      disable_node(buf_recv + DATA + 2);
      }
      //ERROR_CO or ERROR_DECO not ACK => send to server.
      copy_buffer(buf_send, buf_recv, FRAME_SIZE);
      xRingbufferSend(STQ, &buf_send, FRAME_SIZE, FOREVER);
    } else { //The ACK flag is raised : message from server.
#if CONFIG_MESH_DEBUG_LOG
      ESP_LOGI(MESH_TAG, "Ack Raised -> %d", buf_recv[DATA]);
#endif
      if (buf_recv[DATA] == ERROR_CO) { //Acknowledge new card. If UNK is raised, send a B_ACK with error flag raised. Else, send a ERROR_GOTO + state frame.
#if CONFIG_MESH_DEBUG_LOG
	      ESP_LOGI(MESH_TAG, "Acquiting new card");
#endif
	      buf_send[VERSION] = SOFT_VERSION;
        if ((buf_recv[DATA+1] & (1<<5)) == 0) { //UNK is down
#if CONFIG_MESH_DEBUG_LOG
	        ESP_LOGW(MESH_TAG, "enabling node");
#endif
	        enable_node(buf_recv + DATA + 2);
          buf_send[TYPE] = ERROR;
          buf_send[DATA] = ERROR_GOTO;
          buf_send[DATA+1] = buf_recv[DATA+1] & 0x0F;
          copy_buffer(buf_send+DATA+2, buf_recv+DATA+2, 6);
        } else { //UNK is up
          buf_send[TYPE] = B_ACK;
          buf_send[DATA] = 1;
          copy_buffer(buf_send+DATA+1, buf_recv+DATA+2, 6);
          err_addr_req = 1;
        }
        xRingbufferSend(MTQ, &buf_send, FRAME_SIZE, FOREVER);
      }
      if (err_addr_req == 0) {
        state = err_prev_state;
      }
    }
  }
  else if (type == BEACON) {
    buf_send[VERSION] = SOFT_VERSION;
    buf_send[TYPE] = ERROR;
    buf_send[DATA] = ERROR_CO;
    buf_send[DATA+1] = ERROR_S;
    copy_buffer(buf_send+DATA+2, buf_recv+DATA, 6);
    xRingbufferSend(STQ, &buf_send, FRAME_SIZE, FOREVER);
  } else if (type == B_ACK) {
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
  }
}
