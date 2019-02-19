#ifndef __CRC_H__
#define __CRC_H__

#define M3_1 B2 + B5 + B8
#define M3_2 B1 + B4 + B7
#define M3_3 B3 + B6

/*µ
 * @brief: compute the CRC sum of a size-long frame. The result is contained in a uint8_t.
 * @param frame is the pointer address to the frame
 * @param size is the frame size (CRC included)
 * @return returns the crc attributed to the frame.
 */
uint8_t compute_crc(uint8_t * frame, uint16_t size);

/**
 * @brief set the Byte dedicated to the CRC sum.
 * @param frame is the pointer address to the frame
 * @param size is the frame size (CRC included)
 * @return the function return nothing
 */
void set_crc(uint8_t * frame, uint16_t size);

/**
 * @brief
 * @param frame is the pointer address to the frame
 * @param size is the frame size (CRC included)
 * @return 0 if the crc is valid and -1 elsewise.
 */
int check_crc(uint8_t * frame, uint16_t size);

#endif
