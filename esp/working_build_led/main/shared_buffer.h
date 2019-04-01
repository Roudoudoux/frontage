#ifndef __SHARED_BUFFER_H__
#define __SHARED_BUFFER_H__


/**
 * @brief Write a number of bytes from the data buffer into the reception pipe, and update the writable size of the pipe
 */
void write_rxbuffer(uint8_t * data, uint16_t size);

/**
 * @brief Write a number of bytes from the data buffer into the transmission pipe, and update the writable size of the pipe
 */
int write_txbuffer(uint8_t * data, uint16_t size);

/**
 * @brief Read the data on the reception pipe, and write it in the data buffer. Update the writable size of the pipe
 */
void read_rxbuffer(uint8_t * data);

/**
 * @brief Read the data on the transmission pipe, and write it in the databuffer. Update the writable size of the pipe.
 */
void read_txbuffer(uint8_t * data, int arg);
#endif
