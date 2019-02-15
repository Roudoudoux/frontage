#include <stdint.h>
#include "mesh.h"
#include "state_machine.h"
#include "thread.h"
#include "utils.h"
#include "display_color.h"
#include "shared_buffer.h"

void state_init() {
    uint8_t buf_recv[FRAME_SIZE];
    uint8_t buf_send[FRAME_SIZE];

    int type = 0;

    if (esp_mesh_is_root()) {
	if (!is_server_connected) {
	    connect_to_server();
	    return;//Root can't progress if not connected to the server
	}
    }

    /* Check if it has received an acknowledgement */
    while (type != 254) {
	read_rxbuffer(buf_recv);
	type = type_mesg(buf_recv);
	ESP_LOGI(MESH_TAG, "received message of type %d", type);

	if (type == B_ACK) {
	    if (!esp_mesh_is_root()) { //dummy test
		state = ADDR;
		ESP_LOGE(MESH_TAG, "Went into ADDR state");
		return;
	    }
	} else if (type == INSTALL) {
	    if (esp_mesh_is_root()) { //dummy test
		uint8_t mac[6];
		get_mac(buf_recv, mac);
		add_route_table(mac, 0);
		state = CONF;
		ESP_LOGE(MESH_TAG, "Went into CONF state");
		return;
	    } 
	}
    }

    /*Creation of BEACON frame */
    buf_send[VERSION] = SOFT_VERSION;
    buf_send[TYPE] = BEACON;
    ESP_LOGI(MESH_TAG, "my mac : %d-%d-%d-%d-%d-%d", my_mac[0], my_mac[1], my_mac[2], my_mac[3], my_mac[4], my_mac[5]);
    ESP_LOGI(MESH_TAG, "buf send : %d-%d-%d-%d-%d-%d-%d-%d", buf_send[0], buf_send[1], buf_send[2], buf_send[3], buf_send[4], buf_send[5], buf_send[6], buf_send[7]);
    copy_mac(my_mac, buf_send+DATA);
    //Rajout version, checksum, etc...
    int head = write_txbuffer(buf_send, FRAME_SIZE);
    if (esp_mesh_is_root()) {
	xTaskCreate(server_emission, "SERTX", 3072, (void *) head, 5, NULL);
    }
    else {
	xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
    }
}


void state_conf() {
    /*var locales*/
    uint8_t buf_recv[FRAME_SIZE];
    uint8_t buf_send[FRAME_SIZE];

    int type = 0;

    read_rxbuffer(buf_recv);
    type = type_mesg(buf_recv);

    if (type == BEACON) {
	ESP_LOGI(MESH_TAG, "Received a beacon, transfered");
	copy_buffer(buf_send, buf_recv, FRAME_SIZE);
	int head = write_txbuffer(buf_send, FRAME_SIZE);
	xTaskCreate(server_emission, "SERTX", 3072, (void *) head, 5, NULL);
    }
    else if (type == INSTALL) {
	uint8_t mac[6];
	get_mac(buf_recv, mac);
	add_route_table(mac, buf_recv[DATA+6]);
	ESP_LOGI(MESH_TAG, "Got install for MAC "MACSTR" at pos %d, acquitted it", MAC2STR(mac), buf_recv[DATA+6]);
	buf_send[VERSION] = SOFT_VERSION;
	buf_send[TYPE] = B_ACK;
	copy_buffer(buf_send+DATA, buf_recv+DATA, 6);
	//Checksum, version, etc...
	int head = write_txbuffer(buf_send, FRAME_SIZE);
	xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
    }
    else if (type == AMA) {
	if (buf_recv[DATA] == AMA_INIT) {//HC
	    state = ADDR;
	    ESP_LOGE(MESH_TAG, "Went into ADDR state");
	}
    }
}

void state_addr() {
    int type = 0;
    uint8_t buf_recv[CONFIG_MESH_ROUTE_TABLE_SIZE * 3 + 5];//Hard-code?
    uint8_t buf_send[FRAME_SIZE];

    //ESP_LOGI(MESH_TAG, "entered addr");
    read_rxbuffer(buf_recv);
    type = type_mesg(buf_recv);
    //ESP_LOGI(MESH_TAG, "read buffer, type = %d", type);

    if (type == INSTALL) { //Mixte
	uint8_t mac[6];
	get_mac(buf_recv, mac);
	add_route_table(mac, buf_recv[DATA+6]);//hardcode
	if (esp_mesh_is_root()) {
	    copy_buffer(buf_send, buf_recv, FRAME_SIZE);
	    int head = write_txbuffer(buf_send, FRAME_SIZE);
	    xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
	}
    }
    else if (type == COLOR) { // Root only
	ESP_LOGI(MESH_TAG, "Message = %d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d", buf_recv[0], buf_recv[1], buf_recv[2], buf_recv[3], buf_recv[4], buf_recv[5], buf_recv[6], buf_recv[7], buf_recv[8], buf_recv[9], buf_recv[10]);
	uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
	ESP_LOGI(MESH_TAG, "comparing %d and %d", sequ, current_sequence);
	if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
	    current_sequence = sequ;
	    buf_send[VERSION] = SOFT_VERSION;
	    buf_send[TYPE] = COLOR_E;
	    for (int i = 0; i < route_table_size; i++) {
		copy_buffer(buf_send+DATA, buf_recv+DATA, 2);
		copy_buffer(buf_send+DATA+2, buf_recv+DATA+2+i*3, 3); // copy color triplet
		copy_buffer(buf_send+DATA+5, route_table[i].card.addr, 6); // copy mac adress
		//Checksum
		if (!same_mac(route_table[i].card.addr, my_mac)) {
		    int head = write_txbuffer(buf_send, FRAME_SIZE);
		    xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
		} else {
		    display_color(buf_send);
		}
	    }
	}
    }
    else if (type == COLOR_E) {//Mixte
	ESP_LOGI(MESH_TAG, "Message = %d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d", buf_recv[0], buf_recv[1], buf_recv[2], buf_recv[3], buf_recv[4], buf_recv[5], buf_recv[6], buf_recv[7], buf_recv[8], buf_recv[9], buf_recv[10], buf_recv[11], buf_recv[12], buf_recv[13], buf_recv[14], buf_recv[15]);
	uint16_t sequ = buf_recv[DATA]  << 8 | buf_recv[DATA+1];
	ESP_LOGI(MESH_TAG, "comparing %d and %d", sequ, current_sequence);
	if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
	    current_sequence = sequ;
	    display_color(buf_recv);
	}
    }
    else if (type == AMA) { //Mixte
	if (buf_recv[DATA] == AMA_COLOR) {//HC
	    if (esp_mesh_is_root()) {
		copy_buffer(buf_send, buf_recv, FRAME_SIZE);
		int head = write_txbuffer(buf_send, FRAME_SIZE);
		xTaskCreate(mesh_emission, "ESPTX", 3072,  (void *) head, 5, NULL);
	    }
	    state = COLOR;
	    ESP_LOGE(MESH_TAG, "Went into COLOR state");
	}
    }
}

void state_color() {
    int type = 0;
    uint8_t buf_recv[1 + CONFIG_MESH_ROUTE_TABLE_SIZE * 3 + 4];
    uint8_t buf_send[FRAME_SIZE];

    read_rxbuffer(buf_recv);
    type = type_mesg(buf_recv);

    if (type == COLOR) { // Root only
	ESP_LOGI(MESH_TAG, "Message = %d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d", buf_recv[0], buf_recv[1], buf_recv[2], buf_recv[3], buf_recv[4], buf_recv[5], buf_recv[6], buf_recv[7], buf_recv[8], buf_recv[9], buf_recv[10]);
	uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
	if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
	    current_sequence = sequ;
	    buf_send[VERSION] = SOFT_VERSION;
	    buf_send[TYPE] = COLOR_E;
	    for (int i = 0; i < route_table_size; i++) {
		copy_buffer(buf_send+DATA, buf_recv+DATA, 2);
		copy_buffer(buf_send+DATA+2, buf_recv+DATA+2+i*3, 3); // copy color triplet
		copy_buffer(buf_send+DATA+5, route_table[i].card.addr, 6); // copy mac adresscopy_buffer(buf_send+DATA, buf_recv+DATA+2+i*3, 3); // copy color triplet
		//Checksum
		if (!same_mac(route_table[i].card.addr, my_mac)) {
		    int head = write_txbuffer(buf_send, FRAME_SIZE);
		    xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
		} else {
		    display_color(buf_send);
		}
	    }
	}
    }
    else if (type == COLOR_E) {//Mixte
	ESP_LOGI(MESH_TAG, "Message = %d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d-%d", buf_recv[0], buf_recv[1], buf_recv[2], buf_recv[3], buf_recv[4], buf_recv[5], buf_recv[6], buf_recv[7], buf_recv[8], buf_recv[9], buf_recv[10], buf_recv[11], buf_recv[12], buf_recv[13], buf_recv[14], buf_recv[15]);
	uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
	if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
	    current_sequence = sequ;
	    display_color(buf_recv);
	}
    }
    else if (type == BEACON) {//Root only
	state = ERROR_S;
    }
    else if (type == SLEEP) {
	if (buf_recv[DATA] == SLEEP_SERVER) {
	    ESP_LOGE(MESH_TAG, "Card received Server variant of Sleep");

	    if (esp_mesh_is_root()) {
		copy_buffer(buf_send, buf_recv, FRAME_SIZE);
		buf_send[DATA] = SLEEP_MESH;
		int head = write_txbuffer(buf_send, FRAME_SIZE);
		xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
	    }
	} else if (buf_recv[DATA] == SLEEP_MESH) {
	    state = SLEEP_S;
	}
    }
}

void state_sleep() {
    int type = 0;
    uint8_t buf_recv[1 + CONFIG_MESH_ROUTE_TABLE_SIZE * 3 + 4];//Hard-code?
    uint8_t buf_send[FRAME_SIZE];

    if (!is_asleep) {
	ESP_LOGE(MESH_TAG, "entered sleep");
	is_asleep = true;
    }
    read_rxbuffer(buf_recv);
    type = type_mesg(buf_recv);

    if (type == SLEEP) {
	if (buf_recv[DATA] == WAKE_UP) {
	    if (esp_mesh_is_root()) {
		copy_buffer(buf_send, buf_recv, FRAME_SIZE);
		int head = write_txbuffer(buf_send, FRAME_SIZE);
		xTaskCreate(mesh_emission, "ESPTX", 3072,  (void *) head, 5, NULL);
	    }
	    ESP_LOGE(MESH_TAG, "Woke up : return to INIT state to check if everyone is here");
	    is_asleep = false;
	    state = INIT;
	}
    }
}

void state_error() {
    ESP_LOGE(MESH_TAG, "An error occured during card functionnement");
    state = COLOR;
}
