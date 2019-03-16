#ifndef __DISPLAY_COLOR_H__
#define __DISPLAY_COLOR_H__

/**
 *@brief Debug function : write in monitor mode the colours that should be displayed by the light leds.
 */
void display_color(uint8_t buf[FRAME_SIZE]);

void init_leds();

#endif
