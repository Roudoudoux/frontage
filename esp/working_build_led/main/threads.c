#include <stdint.h>
#include <lwip/sockets.h>
#include "mesh.h"
#include "thread.h"
#include "shared_buffer.h"
#include "display_color.h"
#include "utils.h"
#include "crc.h"


//static uint8_t tx_buf[TX_SIZE] = { 0, }; //unused
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
#if CONFIG_MESH_DEBUG_LOG
	    ESP_LOGE(MESH_TAG, "err:0x%x, size:%d", err, data.size);
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
	write_rxbuffer(data.data, data.size);
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
		    copy_buffer(buf_send+DATA+5, route_table[i].card.addr, 6);		    if (!same_mac(route_table[i].card.addr, my_mac)) {
			if (route_table[i].state) {
			    int head = write_txbuffer(buf_send, FRAME_SIZE);
			    xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
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
			    int head = write_txbuffer(buf_send, FRAME_SIZE);
			    xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
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
#if CONFIG_MESH_DEBUG_LOG
	    ESP_LOGE(MESH_TAG, "Couldn't send BEACON to root - %s", esp_err_to_name(err));
#endif
	}
	break;
    case COLOR_E: //Send a Color frame (one triplet) to a specific card. The mac is in the frame.
	{
	    mesh_addr_t to;
	    get_mac(mesg, to.addr);
	    err = esp_mesh_send(&to, &data, MESH_DATA_P2P, NULL, 0);
	    if (err != 0) {
#if CONFIG_MESH_DEBUG_LOG
		ESP_LOGE(MESH_TAG, "Couldn't send COLOR to "MACSTR" - %s", MAC2STR(to.addr), esp_err_to_name(err));
#endif
		if (err == ESP_ERR_MESH_NO_ROUTE_FOUND && state != CONF) {
		    error_child_disconnected(to.addr);
		}
	    }
	}
	break;
    case B_ACK:
	{
#if CONFIG_MESH_DEBUG_LOG
	    ESP_LOGI(MESH_TAG, "Sending B_ACK");
#endif
	    mesh_addr_t to;
	    get_mac(mesg, to.addr);
	    err = esp_mesh_send(&to, &data, MESH_DATA_P2P, NULL, 0);
	    if (err != 0) {
#if CONFIG_MESH_DEBUG_LOG
		ESP_LOGE(MESH_TAG, "Couldn't send B_ACK to "MACSTR" - %s", MAC2STR(to.addr), esp_err_to_name(err));
#endif
		if (err == ESP_ERR_MESH_NO_ROUTE_FOUND && state != CONF) {
		    error_child_disconnected(to.addr);
		}
	    }
	}
	break;
    case ERROR :
	{
#if CONFIG_MESH_DEBUG_LOG
	    ESP_LOGW(MESH_TAG, "Reached error, type = %d\n", mesg[DATA]);
#endif
	    if (mesg[DATA] == ERROR_DECO) {
#if CONFIG_MESH_DEBUG_LOG
		ESP_LOGI(MESH_TAG, "error relay worked");
#endif
		err = esp_mesh_send(NULL, &data, MESH_DATA_P2P, NULL, 0);
		if (err != 0) {
#if CONFIG_MESH_DEBUG_LOG
		    ESP_LOGE(MESH_TAG, "Couldn't send ERROR to root - %s", esp_err_to_name(err));
#endif
		}
	    } else if (mesg[DATA] == ERROR_GOTO) {
		mesh_addr_t to;
		get_mac(mesg, to.addr);
		err = esp_mesh_send(&to, &data, MESH_DATA_P2P, NULL, 0);
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
	}
	break;
    default : //Broadcast the message to all the mesh. This concerns AMA frames.
	for (int i = 0; i < route_table_size; i++) {
	    if (!same_mac(route_table[i].card.addr, my_mac) && route_table[i].state) {
		err = esp_mesh_send(&route_table[i].card, &data, MESH_DATA_P2P, NULL, 0);
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
    }
    vTaskDelete(NULL);
}

void server_emission(void * arg) {
    uint8_t mesg[FRAME_SIZE];

    read_txbuffer(mesg, (int) arg);
    set_crc(mesg, FRAME_SIZE);

    int err = write(sock_fd, mesg, FRAME_SIZE);
    if (err == FRAME_SIZE) {
#if CONFIG_MESH_DEBUG_LOG
	ESP_LOGI(MESH_TAG, "Message %d send to serveur", type_mesg(mesg));
#endif
    }
    else {
	perror("Mesg to server fail");
#if CONFIG_MESH_DEBUG_LOG
	ESP_LOGE(MESH_TAG, "Error on send to serveur, message %d - sent %d bytes", type_mesg(mesg), err);
#endif
    }
    vTaskDelete(NULL);
}
