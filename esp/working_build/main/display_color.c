#include <stdint.h>
#include "mesh.h"
#include "display_color.h"
#include "utils.h"

void display_color(uint8_t buf[FRAME_SIZE]) {
    uint8_t color[3];
    copy_buffer(color, buf+DATA+2, 3);
    ESP_LOGI(MESH_TAG, "Diplay color triplet : (%d, %d, %d)", color[0], color[1], color[2]);
}
