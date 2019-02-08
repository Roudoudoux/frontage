#include <string.h>
/*#include "esp_wifi.h"
#include "esp_system.h"
#include "esp_event_loop.h"
#include "esp_log.h"
#include "esp_mesh.h"
#include "esp_mesh_internal.h"
#include "nvs_flash.h"
#include "lwip/sockets.h"*/
#include "pthread.h"
/*#include "assert.h"       ---Pour le main de test
#include "stdio.h"*/


/*-------Penser à remplacer int par uint8_t pour les parametres "frame"----------*/



/**
 * @brief Computes a CRC on a frame by bits parity
 * @param computed frame
 * @param length of frame
 * @param the offset of the first computed bit
 * @param the frequency of bit extraction. A 1-frequency means every bit is computed, a 2-frequency means one every 2 bits is computed
 */
int variable_crc_computer(int * frame, int len, int offset, int frequency) {
    int crc_bool = 0;
    int i = offset;

    if(frame != NULL) {
        while(i<len) {
            crc_bool = crc_bool + frame[i];
            i = i+frequency;
        }
    }

    return (crc_bool%2);

}


/**
 * @brief Computes a 7-bits long CRC on a frame by bits parity. Security is ensured by first computing a CRC bit-to-bit, then on even and odd bits, and then one every 3 bits, with 3 different offsets. The last bit of the CRC is a bit-to-bit parity on the 6 first bits themselves.
 * @param computed frame
 * @param length of frame
 * @param 7-cell long table where the crc will be written
 * @attention ensure that the crc_table given in parameters is 7-cell long
 */
void frame_crc_computer(int * frame, int len, int * crc_table) {

    int crc_bool_6 = 0;

    if(frame != NULL) {
        int crc_bool_0 = variable_crc_computer(frame, len, 0, 1);
        crc_table[0] = crc_bool_0;
        crc_bool_6 = crc_bool_0 + crc_bool_6;

        int crc_bool_1 = variable_crc_computer(frame, len, 0, 2);
        crc_table[1] = crc_bool_1;
        crc_bool_6 = crc_bool_1 + crc_bool_6;

        int crc_bool_2 = variable_crc_computer(frame, len, 1, 2);
        crc_table[2] = crc_bool_2;
        crc_bool_6 = crc_bool_2 + crc_bool_6;

        int crc_bool_3 = variable_crc_computer(frame, len, 0, 3);
        crc_table[3] = crc_bool_3;
        crc_bool_6 = crc_bool_3 + crc_bool_6;

        int crc_bool_4 = variable_crc_computer(frame, len, 1, 3);
        crc_table[4] = crc_bool_4;
        crc_bool_6 = crc_bool_4 + crc_bool_6;

        int crc_bool_5 = variable_crc_computer(frame, len, 2, 3);
        crc_table[5] = crc_bool_5;
        crc_bool_6 = crc_bool_5 + crc_bool_6;

        crc_bool_6 = crc_bool_6 % 2;
        crc_table[6] = crc_bool_6;
    }
}


/*int main() {

    int frame[7];
    frame[0] = 0;
    frame[1] = 1;
    frame[2] = 1;
    frame[3] = 0;
    frame[4] = 1;
    frame[5] = 0;
    frame[6] = 1;

    int crc_table[7];
    frame_crc_computer(frame, 7, crc_table);

    assert(crc_table[0] == 0);
    assert(crc_table[1] == 1);
    assert(crc_table[2] == 1);
    assert(crc_table[3] == 1);
    assert(crc_table[4] == 0);
    assert(crc_table[5] == 1);
    assert(crc_table[6] == 0);
    printf("ok");
    return 0;
}*/