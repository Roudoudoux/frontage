#include <stdint.h>
#include "mesh.h"
#include "display_color.h"
#include "utils.h"

void display_color(uint8_t buf[FRAME_SIZE]) {
    uint8_t col[3];
    copy_buffer(col, buf+DATA+2, 3);
    RgbColor color(col[0], col[1], col[2]);
    for(int i = 0; i < PixelCount; i++){
      strip.SetPixelColor(i, color);
    }
    strip.Show();
    ESP_LOGI(MESH_TAG, "Diplay color triplet : (%d, %d, %d)", col[0], col[1], col[2]);
}
