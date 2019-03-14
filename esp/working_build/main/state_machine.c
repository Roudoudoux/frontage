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
	//ESP_LOGI(MESH_TAG, "received message of type %d", type);

	if (type == B_ACK) {
	    if (!esp_mesh_is_root()) { //dummy test
		if (buf_recv[DATA] == 1) { //Error flag is raised
		    state = ERROR_S;
		    ESP_LOGE(MESH_TAG, "Acquitted, but went into ERROR state");
		    return;
		}
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
	else if (type == ERROR) { //Si je recois une trame erreur quelconque
	    copy_buffer(buf_err, buf_recv, FRAME_SIZE);
	    if (buf_err[DATA] != ERROR_GOTO) {
		buf_err[DATA+1] = buf_err[DATA+1] | state;
	    }
	    state = ERROR_S;
	    ESP_LOGE(MESH_TAG, "Received Error frame : went into ERROR state - %d", state);
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
    /*var locales*/
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
	copy_buffer(buf_send+DATA+1, buf_recv+DATA, 6);
	int head = write_txbuffer(buf_send, FRAME_SIZE);
	xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
    }
    else if (type == AMA) {
	if (buf_recv[DATA] == AMA_INIT) {
	    state = ADDR;
	    ESP_LOGE(MESH_TAG, "Went into ADDR state");
	}
    }
    else if (type == ERROR) { //Check if doesn't provoke trouble : catch any kind of ERROR frame. Here, should only be GOTO.
	copy_buffer(buf_err, buf_recv, FRAME_SIZE);
	if (buf_err[DATA] != ERROR_GOTO) {
	    buf_err[DATA+1] = buf_err[DATA+1] | state;
	}
	state = ERROR_S;
	ESP_LOGE(MESH_TAG, "Received Error frame : went into ERROR state - %d", state);
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

    /*if (type == INSTALL) { //Mixte
	uint8_t mac[6];
	get_mac(buf_recv, mac);
	add_route_table(mac, buf_recv[DATA+6]);//hardcode
	if (esp_mesh_is_root()) {
	    copy_buffer(buf_send, buf_recv, FRAME_SIZE);
	    int head = write_txbuffer(buf_send, FRAME_SIZE);
	    xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
	}
    }
    else */
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
		//Checksum
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
    else if (type == COLOR_E) {//Mixte
	uint16_t sequ = buf_recv[DATA]  << 8 | buf_recv[DATA+1];
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
    else if (type == ERROR) { //Si je recois une trame erreur quelconque
	copy_buffer(buf_err, buf_recv, FRAME_SIZE);
	if (buf_err[DATA] != ERROR_GOTO) { //Sauvegarder etat init si necessaire
	    buf_err[DATA+1] = buf_err[DATA+1] | state;
	}
	state = ERROR_S;
	ESP_LOGE(MESH_TAG, "Received Error frame : went into ERROR state (%d)", state);
    }
    else if (type == BEACON) { //Réception d'un beacon => anormal. Forger erreur.
	//buf_err = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
	buf_err[VERSION] = SOFT_VERSION;
	buf_err[TYPE] = ERROR;
	buf_err[DATA] = ERROR_CO;
	buf_err[DATA+1] = state; 
	copy_buffer(buf_err + DATA + 2, buf_recv + DATA, 6);
	state = ERROR_S;
	ESP_LOGE(MESH_TAG, "Received Beacon frame : went into ERROR state");
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
	ESP_LOGE(MESH_TAG, "Sequ = %d", sequ);
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
    else if (type == COLOR_E) {//Mixte
	uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
	if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
	    current_sequence = sequ;
	    display_color(buf_recv);
	}
    }
    else if (type == ERROR) { //Si je recois une trame erreur quelconque
	copy_buffer(buf_err, buf_recv, FRAME_SIZE);
	if (buf_err[DATA] != ERROR_GOTO) {
	    buf_err[DATA+1] = buf_err[DATA+1] | state;
	}
	state = ERROR_S;
	ESP_LOGE(MESH_TAG, "Received Error frame : went into ERROR state - %d", state);
    }
    else if (type == BEACON) { //Réception d'un beacon => anormal. Forger erreur.
	//buf_err = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
	buf_err[VERSION] = SOFT_VERSION;
	buf_err[TYPE] = ERROR;
	buf_err[DATA] = ERROR_CO;
	buf_err[DATA+1] = state;
	copy_buffer(buf_err + DATA + 2, buf_recv + DATA, 6);
	state = ERROR_S;
	ESP_LOGE(MESH_TAG, "Received BEACON frame : went into ERROR state");
    }
}

void state_sleep() {
    state = COLOR;
}

void state_error() {
    //ESP_LOGI(MESH_TAG, "Entered Error state");
    int type = 0;
    const int len = CONFIG_MESH_ROUTE_TABLE_SIZE * 3 + 5 + (CONFIG_MESH_ROUTE_TABLE_SIZE * 3 + 4)/7;
    uint8_t buf_recv[len];
    uint8_t buf_send[FRAME_SIZE];
    uint8_t buf_blank[FRAME_SIZE] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};

    if (esp_mesh_is_root()) {
	if (!is_server_connected) {
	    connect_to_server();
	    return;//Root can't progress if not connected to the server
	}
    }
    
    if (buf_err[TYPE] != 0) {
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
    //ESP_LOGI(MESH_TAG, "Received message of type %d", type);

    if (type == COLOR) { // Root only
	uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
	ESP_LOGE(MESH_TAG, "Sequ = %d", sequ);
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
	
    else if (type == COLOR_E) {//Mixte
	uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
	if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
	    current_sequence = sequ;
	    display_color(buf_recv);
	}
    }

    else if (type == ERROR) {
	ESP_LOGI(MESH_TAG, "Error frame received - %d", buf_recv[DATA+1]);
	if ((buf_recv[DATA+1] & (1<<7)) == 0) {
	    ESP_LOGI(MESH_TAG, "No ACK");
	    if (buf_recv[DATA] == ERROR_GOTO) {
		err_addr_req = 0;
		state = buf_recv[DATA+1];
		ESP_LOGI(MESH_TAG, "ERROR_GO : state %d", state);
		return;
	    }
	    if (buf_recv[DATA] == ERROR_DECO) {
		ESP_LOGI(MESH_TAG, "Deco frame received : applying modif");
		disable_node(buf_recv + DATA + 2);
	    }
	    //ERROR_CO or ERROR_DECO not ACK => send to server.
	    copy_buffer(buf_send, buf_recv, FRAME_SIZE);
	    int head = write_txbuffer(buf_send, FRAME_SIZE);
	    xTaskCreate(server_emission, "SERTX", 3072, (void *) head, 5, NULL);
	}
	else { //The ACK flag is raised : message from server.
	    ESP_LOGI(MESH_TAG, "Ack Raised -> %d", buf_recv[DATA]);
	    if (buf_recv[DATA] == ERROR_CO) { //Acknowledge new card. If UNK is raised, send a B_ACK with error flag raised. Else, send a ERROR_GOTO + state frame.
		ESP_LOGI(MESH_TAG, "Acquiting new card");
		buf_send[VERSION] = SOFT_VERSION;
		if ((buf_recv[DATA+1] & (1<<5)) == 0) { //UNK is down 
		    ESP_LOGW(MESH_TAG, "enabling node");
		    enable_node(buf_recv + DATA + 2);
		    buf_send[TYPE] = ERROR;
		    buf_send[DATA] = ERROR_GOTO;
		    buf_send[DATA+1] = buf_recv[DATA+1] & ((1<<4)-1);
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
		state = buf_recv[DATA+1] & ((1<<4)-1);
	    }
	}
    }

    else if (type == BEACON) {
	buf_send[VERSION] = SOFT_VERSION;
	buf_send[TYPE] = ERROR;
	buf_send[DATA] = ERROR_CO;
	buf_send[DATA+1] = ERROR_S;
	copy_buffer(buf_send+DATA+2, buf_recv+DATA, 6);
	//copy_buffer(buf_send, buf_recv, FRAME_SIZE);
	int head = write_txbuffer(buf_send, FRAME_SIZE);
	xTaskCreate(server_emission, "SERTX", 3072, (void *) head, 5, NULL);
    }

    else if (type == B_ACK) {
	if (buf_recv[DATA] == 0) {
	    state = CONF;
	    ESP_LOGE(MESH_TAG, "Went into CONF state");
	}
    } 
}






    
/*    
    if (buf_err[DATA+1] & (1<<7) == 0) { // The ACK flag is down : the error just happened and the server must be notified, or it is a GOTO frame.
	if (buf_err[DATA] == ERROR_DECO) {
	    disable_node(buf_err[DATA+2]);
	    copy_buffer(buf_send, buf_err, FRAME_SIZE);
	    int head = write_txbuffer(buf_send, FRAME_SIZE);
	    xTaskCreate(server_emission, "SERTX", 3072, (void *) head, 5, NULL);
	}
	else if (buf_err[DATA] == ERROR_CO) {
	    copy_buffer(buf_send, buf_err, FRAME_SIZE);
	    int head = write_txbuffer(buf_send, FRAME_SIZE);
	    xTaskCreate(server_emission, "SERTX", 3072, (void *) head, 5, NULL);
	}
	else if (buf_err[DATA] == ERROR_GOTO) {
	    state = buf_err[DATA+1];
	} else {
	    ESP_LOGE(MESH_TAG, "Unkown Error frame type");
	}
	state = buf_err[DATA+1] & ((1<<4)-1);
	return;
    }
    
    buf_send[VERSION] = SOFT_VERSION;
    buf_send[TYPE] = B_ACK;
    copy_buffer(buf_send+DATA+1, buf_err+DATA+2, 6);
    if (err_buf[DATA+1] & (1<<5) == 0) { //UNK is down : the normal process will resume
	enable_node(err_buf[DATA+2]);
	int head = write_txbuffer(buf_send, FRAME_SIZE);
	xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
	state = err_buf[DATA+1] & ((1<<4)-1);
	return;
    }
    buf_send[DATA] = 1;
    int head = write_txbuffer(buf_send, FRAME_SIZE);
    xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
    
    while (1) { //On est coince ici tant que pas ERROR_GOTO reçu => combinaison entre code du dessus et code de COLOR. /!\ Toutes trames de changement d'état est interdite, sauf GOTO_CONF.
	copy_buf(buf_send, buf_blank, FRAME_SIZE); //Reset send buffer.
	read_rxbuffer(buf_recv);
	type = type_mesg(buf_recv);
	
	if (type == COLOR) { // Root only
	    uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
	    ESP_LOGE(MESH_TAG, "Sequ = %d", sequ);
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
	    uint16_t sequ = buf_recv[DATA] << 8 | buf_recv[DATA+1];
	    if (sequ > current_sequence || current_sequence - sequ > SEQU_SEUIL) {
		current_sequence = sequ;
		display_color(buf_recv);
	    }
	}
	
	else if (type == ERROR) {
	    if (buf_recv[DATA+1] & (1<<7) == 0) {
		if (buf_recv[DATA] == ERROR_DECO) {
		    disable_node(buf_recv[DATA+2]);
		    copy_buffer(buf_send, buf_recv, FRAME_SIZE);
		    int head = write_txbuffer(buf_send, FRAME_SIZE);
		    xTaskCreate(server_emission, "SERTX", 3072, (void *) head, 5, NULL);
		}
		else if (buf_recv[DATA] == ERROR_GOTO) {
		    state = buf_recv[DATA+1];
		}
	    } else { //ACK
		buf_send[VERSION] = SOFT_VERSION;
		buf_send[TYPE] = B_ACK;
		copy_buffer(buf_send+DATA+1, buf_recv+DATA+2, 6);
		if (buf_recv[DATA+1] & (1<<5) == 0) { //UNK is down : the normal process will resume
		    enable_node(buf_recv[DATA+2]);
		} else {
		    buf_send[DATA] = 1;
		}
		int head = write_txbuffer(buf_send, FRAME_SIZE);
		xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
	    }
	}
	
	else if (type == BEACON) {
	    buf_send[VERSION] = SOFT_VERSION;
	    buf_send[TYPE] = ERROR;
	    buf_send[DATA] = ERROR_CO;
	    buf_recv[DATA+1] = ERROR_S;
	    copy_buffer(buf_recv+DATA+2, buf_recv+DATA, 6);
	    copy_buffer(buf_send, buf_recv, FRAME_SIZE);
	    int head = write_txbuffer(buf_send, FRAME_SIZE);
	    xTaskCreate(server_emission, "SERTX", 3072, (void *) head, 5, NULL);
	}
    }
}
*/
