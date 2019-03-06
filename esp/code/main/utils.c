#include <stdint.h>
#include "mesh.h"
#include "utils.h"

/**
 * @brief Get the type of a message from the data buffer
 */
int type_mesg(uint8_t * msg){
    return (int) msg[TYPE];
}

/**
 * @brief Copy the mac adress from a buffer to another
 */
void copy_mac(uint8_t * from, uint8_t * to){
    for(int k=0; k < 6; k++){
	to[k] = from[k];
    }
}

/*Copy size bytes from buffer b to buffer a*/
void  copy_buffer(uint8_t * a, uint8_t * b, int size) {
    for (int i = 0; i < size; i++) {
      a[i] = b[i];
    }
}

/**
 * @brief Retrieve the mac adress from the data buffer */
void get_mac(uint8_t * msg, uint8_t * mac){
    int start = -2;
    switch(type_mesg(msg)){
    case BEACON :
    case B_ACK:
    case INSTALL :
	start = DATA;
	break;
    case COLOR_E:
	start = DATA + 5;
	break;
    case COLOR:
    case AMA :
    case SLEEP:
	start = -1;
	break;
    case ERROR:
	start = DATA;
	break;
    default: //all unknown messages are ignored
	start = -2;
     }
    if (start >= 0) {
	copy_mac(msg+start, mac);
	return ;
    }
    if (start == -2) {
	//ESP_LOGE(MESH_TAG, "unknown msg type");
    }
}

/**
 * @brief Check if the mac addresses match
 */
int same_mac(uint8_t * mac1, uint8_t * mac2) {
    int i = 0;
    while (i<6 && mac1[i] == mac2[i]) {
	i++;
    }
    return i == 6;
}

/**
 * @brief Return the size of the data buffer depending on the message type
 */
int get_size(uint8_t type) {
    if (type == COLOR) {
	int len = 3 * route_table_size + 4 + (3 * route_table_size + 4)/7;
	if ((3 * route_table_size + 4) % 7 ==0) {
	    return len;
	}
	return len + 1;
    } else {
	return FRAME_SIZE;
    }
}
