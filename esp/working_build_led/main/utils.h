#ifndef __UTILS_H__
#define __UTILS_H__

/**
 * @brief Get the type of a message from the data buffer
 */
int type_mesg(uint8_t * msg);

/**
 * @brief Copy the mac adress from a buffer to another
 */
void copy_mac(uint8_t * from, uint8_t * to);

/**
 * @brief Copy n bytes from a buffer to another
 */
void copy_buffer(uint8_t * from, uint8_t * to, int n);


/**
 * @brief Retrieve the mac adress from the data buffer */
void get_mac(uint8_t * msg, uint8_t * mac);

/**
 * @brief Check if the mac addresses match
 */
int same_mac(uint8_t * mac1, uint8_t * mac2);

/**
 * @brief Return the size of the data buffer depending on the message type
 */
int get_size(uint8_t type);

#endif
