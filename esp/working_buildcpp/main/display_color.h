#ifndef __DISPLAY_COLOR_H__
#define __DISPLAY_COLOR_H__


#include <NeoPixelBus.h>

const uint16_t PixelCount = 4; // this example assumes 4 pixels, making it smaller will cause a failure
const uint8_t PixelPin = 2;  // make sure to set this to the correct pin, ignored for Esp8266

#define colorSaturation 128


NeoPixelBus<NeoGrbFeature, Neo800KbpsMethod> strip(PixelCount, PixelPin);
/**
 *@brief Debug function : write in monitor mode the colours that should be displayed by the light leds.
 */
void display_color(uint8_t buf[FRAME_SIZE]);

#endif
