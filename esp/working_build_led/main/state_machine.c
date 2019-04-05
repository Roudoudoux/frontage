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
	uint8_t fake[FRAME_SIZE] = {0, 0, 0, 0, 255, 255, 0};
	display_color(fake);
	if (!is_server_connected) {
	    connect_to_server();
	    return;//Root can't progress if not connected to the server
	}
    }

    /* Check if it has received an acknowledgement */
    while (type != 254) {
	read_rxbuffer(buf_recv);
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
	else if (type == ERROR) { //At error reception : immediatly switch within ERROR state
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
    }

    /*Creation of BEACON frame */
    buf_send[VERSION] = SOFT_VERSION;
    buf_send[TYPE] = BEACON;
    copy_mac(my_mac, buf_send+DATA);
    int head = write_txbuffer(buf_send, FRAME_SIZE);
    if (esp_mesh_is_root()) {
	xTaskCreate(server_emission, "SERTX", 3072, (void *) head, 5, NULL);
    }
    else {
	xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
    }
    vTaskDelay(5000 / portTICK_PERIOD_MS); //Stop for 5s after each beacon
}


void state_conf() {
    /*local variables*/
    uint8_t buf_recv[FRAME_SIZE];
    uint8_t buf_send[FRAME_SIZE];

    int type = 0;

    if (esp_mesh_is_root()) {
	if (!is_server_connected) {
	    connect_to_server();
	    return;//Root can't progress if not connected to the server
	}
    }

    read_rxbuffer(buf_recv);
    type = type_mesg(buf_recv);

    if (type == BEACON) {
#if CONFIG_MESH_DEBUG_LOG
	ESP_LOGI(MESH_TAG, "Received a beacon, transfered");
#endif
	copy_buffer(buf_send, buf_recv, FRAME_SIZE);
	int head = write_txbuffer(buf_send, FRAME_SIZE);
	xTaskCreate(server_emission, "SERTX", 3072, (void *) head, 5, NULL);
    }
    else if (type == INSTALL) {
	uint8_t mac[6];
	get_mac(buf_recv, mac);
	add_route_table(mac, buf_recv[DATA+6]);
#if CONFIG_MESH_DEBUG_LOG
	ESP_LOGI(MESH_TAG, "Got install for MAC "MACSTR" at pos %d, acquitted it", MAC2STR(mac), buf_recv[DATA+6]);
#endif
	buf_send[VERSION] = SOFT_VERSION;
	buf_send[TYPE] = B_ACK;
	buf_send[DATA] = 0;
	copy_buffer(buf_send+DATA+1, buf_recv+DATA, 6);
	int head = write_txbuffer(buf_send, FRAME_SIZE);
	xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
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

void state_addr() {
    int type = 0;
    uint8_t buf_recv[CONFIG_MESH_ROUTE_TABLE_SIZE * 3 + 5 + (CONFIG_MESH_ROUTE_TABLE_SIZE * 3 + 4)/7];
    uint8_t buf_send[FRAME_SIZE];

    if (esp_mesh_is_root()) {
	if (!is_server_connected) {
	    connect_to_server();
	    return;//Root can't progress if not connected to the server
	}
    }

    read_rxbuffer(buf_recv);
    type = type_mesg(buf_recv);
    if (type == COLOR) { // Root only
	uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
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
			int head = write_txbuffer(buf_send, FRAME_SIZE);
			xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
		    }
		} else {
		    display_color(buf_send);
		}
	    }
	}
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
		int head = write_txbuffer(buf_send, FRAME_SIZE);
		xTaskCreate(mesh_emission, "ESPTX", 3072,  (void *) head, 5, NULL);
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

void state_color() {
    int type = 0;
    uint8_t buf_recv[CONFIG_MESH_ROUTE_TABLE_SIZE * 3 + 5 + (CONFIG_MESH_ROUTE_TABLE_SIZE * 3 + 4)/7];
    uint8_t buf_send[FRAME_SIZE];

    if (esp_mesh_is_root()) {
	if (!is_server_connected) {
	    connect_to_server();
	    return;//Root can't progress if not connected to the server
	}
    }

    read_rxbuffer(buf_recv);
    type = type_mesg(buf_recv);

    if (type == COLOR) { // Root only
	uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
#if CONFIG_MESH_DEBUG_LOG
	ESP_LOGE(MESH_TAG, "Sequ = %d / current_sequence = %d", sequ, current_sequence);
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
			int head = write_txbuffer(buf_send, FRAME_SIZE);
			xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
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

void state_sleep() { //Unused for now.
    state = COLOR;
}

void state_error() {
#if CONFIG_MESH_DEBUG_LOG
    ESP_LOGI(MESH_TAG, "Entered Error state");
#endif
    int type = 0;
    const int len = CONFIG_MESH_ROUTE_TABLE_SIZE * 3 + 5 + (CONFIG_MESH_ROUTE_TABLE_SIZE * 3 + 4)/7;
    uint8_t buf_recv[CONFIG_MESH_ROUTE_TABLE_SIZE * 3 + 5 + (CONFIG_MESH_ROUTE_TABLE_SIZE * 3 + 4)/7];
    uint8_t buf_send[FRAME_SIZE];
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
    } else {
	read_rxbuffer(buf_recv);
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
			int head = write_txbuffer(buf_send, FRAME_SIZE);
			xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
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
		int head = write_txbuffer(buf_send, FRAME_SIZE);
		xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
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
	    int head = write_txbuffer(buf_send, FRAME_SIZE);
	    xTaskCreate(server_emission, "SERTX", 3072, (void *) head, 5, NULL);
	}
	else { //The ACK flag is raised : message from server.
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
		int head = write_txbuffer(buf_send, FRAME_SIZE);
		xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
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
	int head = write_txbuffer(buf_send, FRAME_SIZE);
	xTaskCreate(server_emission, "SERTX", 3072, (void *) head, 5, NULL);
    }

    else if (type == B_ACK) {
	if (buf_recv[DATA] == 0) {
	    state = ADDR;
#if CONFIG_MESH_DEBUG_LOG
	    ESP_LOGE(MESH_TAG, "Went into ADDR state");
#endif
	}
	else {
#if CONFIG_MESH_DEBUG_LOG
	    ESP_LOGE(MESH_TAG, "There is still an error with the HaR procedure, sorry :/");
#endif
	}
    }
}
