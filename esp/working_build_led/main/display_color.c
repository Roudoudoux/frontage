#include <stdint.h>
#include "mesh.h"
#include "display_color.h"
#include "utils.h"
#include "esp32_digital_led_lib.h"

strand_t strand[1] = {{.rmtChannel = 1, .gpioNum = 15, .ledType = LED_WS2812B_V3, .brightLimit = 32, .numPixels =  20, .pixels = NULL, ._stateVars = NULL}};//Array is normal, pls don't edit

void gpioSetup(int gpioNum, int gpioMode, int gpioVal) {
  #if defined(ARDUINO) && ARDUINO >= 100
    pinMode (gpioNum, gpioMode);
    digitalWrite (gpioNum, gpioVal);
  #elif defined(ESP_PLATFORM)
    gpio_num_t gpioNumNative = (gpio_num_t)(gpioNum);
    gpio_mode_t gpioModeNative = (gpio_mode_t)(gpioMode);
    gpio_pad_select_gpio(gpioNumNative);
    gpio_set_direction(gpioNumNative, gpioModeNative);
    gpio_set_level(gpioNumNative, gpioVal);
  #endif
}

void init_leds() {
    gpioSetup(15, OUTPUT, LOW);
    ESP_LOGI(MESH_TAG, "Led init : %d", digitalLeds_initStrands(strand, 1));
}

void display_color(uint8_t buf[FRAME_SIZE]) {
    strand_t * pStrand = &strand[0];
    uint8_t color[3];
    copy_buffer(color, buf+DATA+2, 3);
    for (uint16_t i = 0; i < pStrand->numPixels; i++) {
      pStrand->pixels[i] = pixelFromRGB(color[0], color[1], color[2]);
    }
    digitalLeds_updatePixels(pStrand);
    ESP_LOGI(MESH_TAG, "Diplay color triplet : (%d, %d, %d)", color[0], color[1], color[2]);
}
