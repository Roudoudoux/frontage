
/**
  * Format a log frame of log_size bytes from a frame received (no matter its length) and an action coded on 1 byte.
  * This frame holds several informations : the time of producing frame, the state in which is the sending esp,
  * the frame which the esp is handelling, its layer and the number of esp on its subtree. The esp is distinguished from the other by its index.
  * _______________________________________________________________________________________________________________
  * | soft_version | type   | mac_address | sent time | essential data |          log_msg               | checksum |
  * |  1 Byte      | 1 Byte |   6 Bytes   |  8 Bytes  | 2 Bytes        |          x Bytes               | y Bytes  |
  * |______________|________|_____________|___________|________________|________________________________|__________|
  */
int log_length(int log_msg_size);

void log_format(uint8_t* frame, uint8_t *log_frame, char *log_msg, int log_size);

void log_send(uint8_t* log_frame, int log_size);
