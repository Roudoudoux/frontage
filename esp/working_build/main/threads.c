#include <stdint.h>
#include <lwip/sockets.h>
#include "mesh.h"
#include "thread.h"
#include "shared_buffer.h"
#include "utils.h"
#include "crc.h"


static uint8_t tx_buf[TX_SIZE] = { 0, };
static uint8_t rx_buf[RX_SIZE] = { 0, };
static uint8_t waiting_serv = 0;


void mesh_reception(void * arg) {
    esp_err_t err;
    mesh_addr_t from;
    mesh_data_t data;
    int flag = 0;
    data.data = rx_buf;
    data.size = RX_SIZE;


    while(is_running) {
      err = esp_mesh_recv(&from, &data, portMAX_DELAY, &flag, NULL, 0);
      if (err != ESP_OK || !data.size) {
        ESP_LOGE(MESH_TAG, "err:0x%x, size:%d", err, data.size);
        continue;
      }
      if (data.data[VERSION] != SOFT_VERSION) {
        ESP_LOGE(MESH_TAG, "Software versions not matching with Mesh");
        continue;
      } if (!(check_crc(data.data, data.size))) {
        ESP_LOGE(MESH_TAG, "Invalid CRC from Mesh");
        continue;
      }
      write_rxbuffer(data.data, data.size);
  }

  vTaskDelete(NULL);
}

void server_reception(void * arg) {
    uint8_t buf[1500];
    int len;

    while(is_running) {
      len = recv(sock_fd, &buf, 1500, MSG_OOB);
      if (len == -1) {
	  waiting_serv++;
	  ESP_LOGE(MESH_TAG, "Communication Socket error, %d", waiting_serv);
	  if (waiting_serv == 15) {
	      is_server_connected = false;
	      waiting_serv = 0;
	      vTaskDelete(NULL);
	  }
	  continue;
      }
      if (len == 0) {
	  waiting_serv++;
	  ESP_LOGE(MESH_TAG, "Empty message from server, %d", waiting_serv);
	  if (waiting_serv == 15) {
	      is_server_connected = false;
	      waiting_serv = 0;
	      vTaskDelete(NULL);
	  }
	  continue;
      }
      waiting_serv = 0;
      ESP_LOGI(MESH_TAG, "Message received from server of len %d = %d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d", len, buf[0], buf[1], buf[2], buf[3], buf[4], buf[5], buf[6], buf[7], buf[8], buf[9], buf[10], buf[11], buf[12], buf[13], buf[14], buf[15]);
      int head = 0;
      while(head < len) {
	  int size = get_size(buf[head+TYPE]);
	  if (buf[VERSION] != SOFT_VERSION) {
	      ESP_LOGE(MESH_TAG, "Software version not matching with server");
	      head = head + size;
	      continue;
	  } if (!check_crc(buf+head, size)) {
	      ESP_LOGE(MESH_TAG, "Invalid CRC from server");
	      head = head + size;
	      continue;
	  }
	  write_rxbuffer(buf+head, size);
	  head = head + size;
      }
  }

  vTaskDelete(NULL);
}

void mesh_emission(void * arg) {
    int err;
    mesh_data_t data;
    uint8_t mesg[FRAME_SIZE];
    read_txbuffer(mesg, (int) arg);

    set_crc(mesg, FRAME_SIZE);
    data.data = mesg;
    data.size = FRAME_SIZE;

    switch(type_mesg(mesg)) {
    case BEACON: //Send a beacon to the root.
        err = esp_mesh_send(NULL, &data, MESH_DATA_P2P, NULL, 0);
	if (err != 0) {
	    ESP_LOGE(MESH_TAG, "Couldn't send BEACON to root - %s", esp_err_to_name(err));
	}
	break;
    case COLOR_E: //Send a Color frame (one triplet) to a specific card. The mac is in the frame.
	{
	    mesh_addr_t to;
	    get_mac(mesg, to.addr);
	    err = esp_mesh_send(&to, &data, MESH_DATA_P2P, NULL, 0);
	    if (err != 0) {
		ESP_LOGE(MESH_TAG, "Couldn't send COLOR to "MACSTR" - %s", MAC2STR(to.addr), esp_err_to_name(err));
	    }
	}
	break;
    case B_ACK: 
	{
	    ESP_LOGI(MESH_TAG, "Sending B_ACK");
	    mesh_addr_t to;
	    get_mac(mesg, to.addr);
	    err = esp_mesh_send(&to, &data, MESH_DATA_P2P, NULL, 0);
	    if (err != 0) {
		ESP_LOGE(MESH_TAG, "Couldn't send B_ACK to "MACSTR" - %s", MAC2STR(to.addr), esp_err_to_name(err));
	    }
	}
	break;
    case ERROR :
	if (mesg[DATA] == ERROR_DECO) {
	    ESP_LOGI(MESH_TAG, "error relay worked");
	    err = esp_mesh_send(NULL, &data, MESH_DATA_P2P, NULL, 0);
	    if (err != 0) {
		ESP_LOGE(MESH_TAG, "Couldn't send ERROR to root - %s", esp_err_to_name(err));
	    }
	}
	break;
    default : //Broadcast the message to all the mesh. This include AMA, SLEEP and INSTALL frames.
	for (int i = 0; i < route_table_size; i++) {
	    if (!same_mac(route_table[i].card.addr, my_mac) && route_table[i].state) {
		err = esp_mesh_send(&route_table[i].card, &data, MESH_DATA_P2P, NULL, 0);
		if (err != 0) {
		    ESP_LOGE(MESH_TAG, "Couldn't send message %d to "MACSTR" - %s", type_mesg(mesg), MAC2STR(route_table[i].card.addr), esp_err_to_name(err));
		}
	    }
	}
    }
    vTaskDelete(NULL);
}

void server_emission(void * arg) {
    uint8_t mesg[FRAME_SIZE];

    read_txbuffer(mesg, (int) arg);
    set_crc(mesg, FRAME_SIZE);

    int err = write(sock_fd, mesg, FRAME_SIZE);
    if (err == FRAME_SIZE) {
	ESP_LOGI(MESH_TAG, "Message %d send to serveur", type_mesg(mesg));
    }
    else {
	perror("mesg to server fail");
	ESP_LOGE(MESH_TAG, "Error on send to serveur, message %d - sent %d bytes", type_mesg(mesg), err);
    }
    vTaskDelete(NULL);
}
