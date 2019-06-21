#include <stdint.h>
#include <lwip/sockets.h>
#include "mesh.h"
#include "thread.h"
#include "display_color.h"
#include "utils.h"
#include "crc.h"
#include "logs.h"

static uint8_t rx_buf[RX_SIZE] = { 0, };
static uint8_t waiting_serv = 0;

void mesh_reception(void * arg) {
  esp_err_t err;
  mesh_addr_t from;
  uint8_t log_buffer[100];
  mesh_data_t data;
  int flag = 0;
  data.data = rx_buf;
  data.proto = MESH_PROTO_BIN;
  data.tos = MESH_TOS_P2P;

  while(is_running) {
    data.size = RX_SIZE;
    err = esp_mesh_recv(&from, &data, portMAX_DELAY, &flag, NULL, 0);
    if (err != ESP_OK) {
      #if CONFIG_MESH_DEBUG_LOG
      ESP_LOGE(MESH_TAG, "mesh_reception :: err:0x%x, size:%d", err, data.size);
      #endif
      continue;
    }
    if (data.data[VERSION] != SOFT_VERSION) {
      #if CONFIG_MESH_DEBUG_LOG
      ESP_LOGE(MESH_TAG, "Software versions not matching with Mesh");
      #endif
      continue;
    } if (!(check_crc(data.data, data.size))) {
      #if CONFIG_MESH_DEBUG_LOG
      ESP_LOGE(MESH_TAG, "Invalid CRC from Mesh");
      #endif
      continue;
    }
    #if CONFIG_MESH_DEBUG_LOG
    ESP_LOGI(MESH_TAG, "Received message from mesh of size %d\n", data.size);
    #endif
    if (data.data[TYPE] == LOG){ // Log messages does not go through esp state machine. Should be received only by ESP ROOT.
      #if CONFIG_MESH_DEBUG_LOG
      ESP_LOGI(MESH_TAG, "received a log of %d from "MACSTR" => transmitting to server", data.size, MAC2STR(from.addr));
      #endif
      xRingbufferSend(STQ, data.data, data.size, FOREVER);
    } else {
      char log_msg[50];
      int log_msg_size = sprintf(log_msg, "Received from "MACSTR"", MAC2STR(from.addr));
      int lsize = log_length(log_msg_size);
      log_format(data.data, log_buffer, log_msg, log_msg_size);
      log_send(log_buffer, lsize);
      xRingbufferSend(RQ, data.data, FRAME_SIZE, FOREVER);
    }
  }
  vTaskDelete(NULL);
}

void server_reception(void * arg) {
  uint8_t buf[1500];
  int len;
  int tampon = 0;

  while(is_running) {
    len = recv(sock_fd, &buf[tampon], 1500-tampon, MSG_OOB);
    if (len == -1) {
      waiting_serv++;
      #if CONFIG_MESH_DEBUG_LOG
      ESP_LOGE(MESH_TAG, "Communication Socket error, %d", waiting_serv);
      #endif
      if (waiting_serv == 15) {
        is_server_connected = false;
        waiting_serv = 0;
        uint8_t buf_send[FRAME_SIZE];
        buf_send[VERSION] = SOFT_VERSION;
        buf_send[TYPE] = COLOR_E;
        current_sequence++;
        buf_send[DATA] = (current_sequence & (0xFF00))>>8;
        buf_send[DATA+1] = current_sequence & (0x00FF);
        uint8_t zeros[3] = {0, 0, 0};
        for (int i = 0; i < route_table_size; i++) {
          copy_buffer(buf_send+DATA+2, zeros, 3);
          copy_buffer(buf_send+DATA+5, route_table[i].card.addr, 6);
          if (!same_mac(route_table[i].card.addr, my_mac)) {
            if (route_table[i].state) {
              xRingbufferSend(MTQ, &buf_send, FRAME_SIZE, FOREVER);
            }
          } else {
            display_color(buf_send);
          }
        }
        vTaskDelete(NULL);
      }
      continue;
    }
    if (len == 0) {
      waiting_serv++;
      #if CONFIG_MESH_DEBUG_LOG
      ESP_LOGE(MESH_TAG, "Empty message from server, %d", waiting_serv);
      #endif
      if (waiting_serv == 15) {
        is_server_connected = false;
        waiting_serv = 0;
        uint8_t buf_send[FRAME_SIZE];
        buf_send[VERSION] = SOFT_VERSION;
        buf_send[TYPE] = COLOR_E;
        current_sequence++;
        buf_send[DATA] = (current_sequence & (0xFF00))>>8;
        buf_send[DATA+1] = current_sequence & (0x00FF);
        uint8_t zeros[3] = {0, 0, 0};
        for (int i = 0; i < route_table_size; i++) {
          copy_buffer(buf_send+DATA+2, zeros, 3);
          copy_buffer(buf_send+DATA+5, route_table[i].card.addr, 6);
          if (!same_mac(route_table[i].card.addr, my_mac)) {
            if (route_table[i].state) {
              xRingbufferSend(MTQ, &buf_send, FRAME_SIZE, FOREVER);
            }
          } else {
            display_color(buf_send);
          }
        }
        vTaskDelete(NULL);
      }
      continue;
    }
    waiting_serv = 0;
    int head = 0;
    while(head < len+tampon) {
      int size = get_size(buf[head+TYPE]);
      if (head+size > 1500) {
        #if CONFIG_MESH_DEBUG_LOG
        ESP_LOGE(MESH_TAG, "Message on other half, copying...");
        #endif
        for (int i = 0; i < 1500 - head; i++) {
          buf[i] = buf[head+i];
        }
        tampon = 1500 - head;
        head = head + tampon;
        continue;
      }
      if (buf[head+VERSION] != SOFT_VERSION) {
        #if CONFIG_MESH_DEBUG_LOG
        ESP_LOGE(MESH_TAG, "Software version not matching with server");
        #endif
        head = head + size;
        continue;
      }
      if (buf[head+TYPE] == COLOR && len == (1500-tampon)) {
        head = head+size;
        #if CONFIG_MESH_DEBUG_LOG
        ESP_LOGE(MESH_TAG, "Catching up, dropping color frame");
        #endif
        continue;
      }
      if (!check_crc(buf+head, size)) {
        #if CONFIG_MESH_DEBUG_LOG
        ESP_LOGE(MESH_TAG, "Invalid CRC from server");
        #endif
        head = head + size;
        continue;
      }
      xRingbufferSend(RQ, buf+head, size, FOREVER);
      head = head + size;
    }
  }
  vTaskDelete(NULL);
}

void mesh_emission(void * arg){
  int err;
  uint8_t log_buffer[100];
  mesh_data_t data;
  uint8_t *mesg = NULL;
  size_t size = 0;
  while(is_running){
    if ((mesg = xRingbufferReceive(MTQ, &size, FOREVER)) != NULL){
      int64_t timeb = esp_timer_get_time();
      ESP_LOGI(MESH_TAG, "I want to send %d bytes", size);
      set_crc(mesg, size);
      data.data = mesg;
      data.size = (int) size;
      data.proto = MESH_PROTO_BIN;
      data.tos = MESH_TOS_P2P;
      int flags = MESH_DATA_P2P;
      if (state == COLOR_E){
        flags = flags | MESH_DATA_NONBLOCK;
      }
      switch (type_mesg(mesg)) {
        case BEACON: //Send a beacon to the root.
        {
          err = esp_mesh_send(NULL, &data, flags , NULL, 0);
          if (err != 0) {
            #if CONFIG_MESH_DEBUG_LOG
            ESP_LOGE(MESH_TAG, "Couldn't send BEACON to root - %s", esp_err_to_name(err));
            #endif
          }
          break;
        }
        case COLOR_E: //Send a Color frame (one triplet) to a specific card. The mac is in the frame.
        {
          mesh_addr_t to;
          get_mac(mesg, to.addr);
          err = esp_mesh_send(&to, &data, flags, NULL, 0); //Should prevent freezing of cards, but didn't work -> further testing is required (still blocking?)
          if (err != 0) {
            #if CONFIG_MESH_DEBUG_LOG
            ESP_LOGE(MESH_TAG, "Couldn't send COLOR to "MACSTR" - %s", MAC2STR(to.addr), esp_err_to_name(err));
            #endif
            if (err == ESP_ERR_MESH_NO_ROUTE_FOUND && state != CONF) {
              error_child_disconnected(to.addr);
            }
          }
          break;
        }
        case B_ACK:
        {
          #if CONFIG_MESH_DEBUG_LOG
          ESP_LOGI(MESH_TAG, "Sending B_ACK");
          #endif
          mesh_addr_t to;
          get_mac(mesg, to.addr);
          err = esp_mesh_send(&to, &data, flags, NULL, 0);
          if (err != 0) {
            #if CONFIG_MESH_DEBUG_LOG
            ESP_LOGE(MESH_TAG, "Couldn't send B_ACK to "MACSTR" - %s", MAC2STR(to.addr), esp_err_to_name(err));
            #endif
            if (err == ESP_ERR_MESH_NO_ROUTE_FOUND && state != CONF) {
              error_child_disconnected(to.addr);
            }
          }
          break;
        }
        case ERROR :
        {
          #if CONFIG_MESH_DEBUG_LOG
          ESP_LOGW(MESH_TAG, "Reached error, type = %d\n", mesg[DATA]);
          #endif
          if (mesg[DATA] == ERROR_DECO) {
            #if CONFIG_MESH_DEBUG_LOG
            ESP_LOGI(MESH_TAG, "error relay worked");
            #endif
            err = esp_mesh_send(NULL, &data, flags, NULL, 0);
            if (err != 0) {
              #if CONFIG_MESH_DEBUG_LOG
              ESP_LOGE(MESH_TAG, "Couldn't send ERROR to root - %s", esp_err_to_name(err));
              #endif
            }
          } else if (mesg[DATA] == ERROR_GOTO) {
            mesh_addr_t to;
            get_mac(mesg, to.addr);
            err = esp_mesh_send(&to, &data, flags, NULL, 0);
            if (err != 0) {
              #if CONFIG_MESH_DEBUG_LOG
              ESP_LOGI(MESH_TAG, "Coudln't send ERROR_GOTO %d to "MACSTR" : %s", mesg[DATA+1], MAC2STR(to.addr), esp_err_to_name(err));
              #endif
              if (err == ESP_ERR_MESH_NO_ROUTE_FOUND && state != CONF) {
                error_child_disconnected(to.addr);
              }
            } else {
              #if CONFIG_MESH_DEBUG_LOG
              ESP_LOGI(MESH_TAG, "send ERROR_GOTO %d to "MACSTR, mesg[DATA+1], MAC2STR(to.addr));
              #endif
            }
          }
          break;
        }
        case LOG:
        {
          err = esp_mesh_send(NULL, &data, flags, NULL, 0);
          ESP_LOGI(MESH_TAG, "Send a log of %d bytes which has returned err : %x ", data.size, err);
          if (err != ESP_OK) {
            ESP_LOGE(MESH_TAG, "an error occured");
          }
          break;
        }
        default : //Broadcast the message to all the mesh. This concerns AMA frames.
        {
          for (int i = 0; i < route_table_size; i++) {
            if (!same_mac(route_table[i].card.addr, my_mac) && route_table[i].state) {
              err = esp_mesh_send(&route_table[i].card, &data, flags, NULL, 0);
              if (err != 0) {
                #if CONFIG_MESH_DEBUG_LOG
                ESP_LOGE(MESH_TAG, "Couldn't send message %d to "MACSTR" - %s", type_mesg(mesg), MAC2STR(route_table[i].card.addr), esp_err_to_name(err));
                #endif
                if (err == ESP_ERR_MESH_NO_ROUTE_FOUND && state != CONF) {
                  error_child_disconnected(route_table[i].card.addr);
                }
              }
            }
          }
          break;
        }
      }
      if (mesg[TYPE] != LOG){
        int64_t timea = esp_timer_get_time();
        int64_t dif = timea - timeb;
        char log_msg[50];
        int log_msg_size = sprintf(log_msg, " %llu microsec to send the frame", dif);
        int lsize = log_length(log_msg_size);
        log_format(mesg, log_buffer, log_msg, log_msg_size);
        log_send(log_buffer, lsize);
      }
      vRingbufferReturnItem(MTQ, mesg);
      mesg = NULL;
    }
  }
}

void server_emission(void * arg){
  uint8_t *mesg = NULL;
  size_t size = 0;
  while(is_running){
    if ((mesg =  (uint8_t*) xRingbufferReceive(STQ, &size, FOREVER)) != NULL) {
      if (mesg[TYPE] != LOG){
        set_crc(mesg, FRAME_SIZE);
      }
      int err = write(sock_fd, mesg, size);
      if (err == FRAME_SIZE){
        #if CONFIG_MESH_DEBUG_LOG
        ESP_LOGI(MESH_TAG, "Message %d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d send to serveur", mesg[0], mesg[1], mesg[2], mesg[3], mesg[4], mesg[5], mesg[6], mesg[7], mesg[8], mesg[9], mesg[10], mesg[11], mesg[12], mesg[13], mesg[14], mesg[15]);
        #endif
      } else  if (err == size){
        #if CONFIG_MESH_DEBUG_LOG
        ESP_LOGI(MESH_TAG, "Message from %dx:%dx:%dx:%dx:%dx:%dx",  mesg[2], mesg[3], mesg[4], mesg[5], mesg[6], mesg[7]);
        ESP_LOGI(MESH_TAG, "Log has been transmitted to server");
        #endif
      } else {
        perror("message to server fail");
        #if CONFIG_MESH_DEBUG_LOG
        ESP_LOGE(MESH_TAG, "Error on send to serveur, message %d - sent %d bytes out of %d ", type_mesg(mesg), err, size);
        #endif
      }
    vRingbufferReturnItem(STQ, mesg);
    mesg = NULL;
    }
  }
  vTaskDelete(NULL);
}
