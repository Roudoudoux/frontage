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
#include "assert.h"       //---Pour le main de test
#include "stdio.h"
#include <sys/time.h>


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

int check_crc(int * frame) {
    //printf("?\n");
    int crc_table[7];
    int size = 16;
    int frame2[(size-1)*8];
    for (int i = 0; i < size-1; i++) {
	for (int j = 0; j < 8; j++) {
	    frame2[(i*8)+j] = (frame[i] & (1 << (7-j))) >> (7-j);
	}
    }
    frame_crc_computer(frame2, (size-1)*8, crc_table);
    int crc = crc_table[0] << 6 | crc_table[1] << 5 | crc_table[2] << 4 | crc_table[3] << 3 | crc_table[4] << 2 | crc_table[5] << 1 | crc_table[6];
    //printf("%d and %d\n", frame[size-1], crc);
    frame[size-1] = crc;
}

int main() {

    /*int frame[8];
    frame[0] = 0;
    frame[1] = 1;
    frame[2] = 1;
    frame[3] = 0;
    frame[4] = 1;
    frame[5] = 0;
    frame[6] = 1;
    frame[7] = 0;

    int crc_table[7];
    frame_crc_computer(frame, 8, crc_table);

    assert(crc_table[0] == 0);
    assert(crc_table[1] == 1);
    assert(crc_table[2] == 1);
    assert(crc_table[3] == 1);
    assert(crc_table[4] == 0);
    assert(crc_table[5] == 1);
    assert(crc_table[6] == 0);
    printf("%d", crc_table[0] << 6 | crc_table[1] << 5 | crc_table[2] << 4 | crc_table[3] << 3 | crc_table[4] << 2 | crc_table[5] << 1 | crc_table[6]);
    printf("ok\n");
    int frame2[3] = {106, 212, 58};
    printf("Res = %d\n", check_crc(frame2));*/
    struct timeval tv1, tv2;
    int frame[16] = {1, 3, 172, 48, 36, 96, 58, 42, 1, 0, 0, 0, 0, 0, 0, 0};
    gettimeofday(&tv1, NULL);
    int i = 0;
    while (i < 10000) {
	i++;
	check_crc(frame);
    }
    gettimeofday(&tv2, NULL);
    unsigned long microseconds = (tv2.tv_sec - tv1.tv_sec) * 1000000 + (tv2.tv_usec - tv1.tv_usec);
    printf("Res = %d with time %f µs\n", frame[15], (double)microseconds/10000);
    return 0;
}
