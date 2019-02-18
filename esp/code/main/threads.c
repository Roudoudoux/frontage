#include <stdint.h>
#include <lwip/sockets.h>
#include "mesh.h"
#include "thread.h"
#include "shared_buffer.h"
#include "utils.h"
#include "crc.h"


static uint8_t tx_buf[TX_SIZE] = { 0, };
static uint8_t rx_buf[RX_SIZE] = { 0, };


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
        ESP_LOGE(MESH_TAG, "Communication Socket error");
        continue;
      }
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

    //ESP_LOGI(MESH_TAG, "Message to mesh = %d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d", mesg[0], mesg[1], mesg[2], mesg[3], mesg[4], mesg[5], mesg[6], mesg[7], mesg[8], mesg[9], mesg[10], mesg[11], mesg[12], mesg[13], mesg[14], mesg[15]);

    //ESP_LOGI(MESH_TAG, "calculating CRC...");
    set_crc(mesg, FRAME_SIZE);
    //ESP_LOGI(MESH_TAG, "CRC calculated.");
    data.data = mesg;
    data.size = FRAME_SIZE;

    //ESP_LOGI(MESH_TAG, "Message to mesh = %d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d", mesg[0], mesg[1], mesg[2], mesg[3], mesg[4], mesg[5], mesg[6], mesg[7], mesg[8], mesg[9], mesg[10], mesg[11], mesg[12], mesg[13], mesg[14], mesg[15]);

    switch(type_mesg(mesg)) {
    case BEACON: //Send a beacon to the root.
        err = esp_mesh_send(NULL, &data, MESH_DATA_P2P, NULL, 0);
	if (err != 0) {
	    //perror("Beacon failed");
	    ESP_LOGE(MESH_TAG, "Couldn't send BEACON to root");
	    //state = ERROR_S;
	}
	break;
    case COLOR_E: //Send a Color frame (one triplet) to a specific card. The mac is in the frame.
	{
	    mesh_addr_t to;
	    get_mac(mesg, to.addr);
	    err = esp_mesh_send(&to, &data, MESH_DATA_P2P, NULL, 0);
	    if (err != 0) {
		//perror("Color fail");
		ESP_LOGE(MESH_TAG, "Couldn't send COLOR to "MACSTR"", MAC2STR(to.addr));
		//state = ERROR_S;
	    }
	}
	break;
    case B_ACK: // Send a beacon acknowledgement to a specific card. The mac is in the frame.
	{
	    mesh_addr_t to;
	    get_mac(mesg, to.addr);
	    err = esp_mesh_send(&to, &data, MESH_DATA_P2P, NULL, 0);
	    if (err != 0) {
		//perror("B_ACK fail");
		ESP_LOGE(MESH_TAG, "Couldn't send B_ACK to "MACSTR" - %s", MAC2STR(to.addr), esp_err_to_name(err));
	    }
	}
	break;
	/*case SLEEP_R : // Put all cards in the mesh in sleep mode. To do this, the messages are sent to the cards with the less cards in their subnet, and then to those with greater subnet, to ensure that there is always a card to relay the messages
        data.data[TYPE] = SLEEP;
        for (int i = 0; i < route_table_size; i++) {
	    esp_mesh_get_subnet_nodes_num(&route_table[i].card, &num[i]);
	}
	int count = 0;
	while (count < route_table_size) {
	    for (int i = 0; i < route_table_size; i++) {
		if (num[i] == count) {
		    esp_mesh_send(&route_table[i].card, &data, MESH_DATA_P2P, NULL, 0);
		}
	    }
	    count++;
	}
	break;*/
    default : //Broadcast the message to all the mesh. This include AMA, SLEEP and INSTALL frames.
	for (int i = 0; i < route_table_size; i++) {
	    if (!same_mac(route_table[i].card.addr, my_mac)) {
		err = esp_mesh_send(&route_table[i].card, &data, MESH_DATA_P2P, NULL, 0);
		if (err != 0) {
		    //perror("message fail");
		    ESP_LOGE(MESH_TAG, "Couldn't send message %d to "MACSTR"", type_mesg(mesg), MAC2STR(route_table[i].card.addr));
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
