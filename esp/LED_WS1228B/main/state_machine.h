#ifndef __STATE_MACHINE_H__
#define __STATE_MACHINE_H__

/**
 * @brief return the normal next state from the frame type
 * the frame will be handeled in this next state.
 */
int transition(int cstate, int ftype, int subtype);

/**
 * @brief Main function of the INIT state.
 * In this state, root card will send BEACON to server, and wait for INSTALL to go into CONF state.
 * Node cards will send BEACON to the root, and wait for B_ACK to go into ADDR state. B_ACK frame can have an error Flag raised, in which case card will instead go into ERROR state.
 * The root card can switch at any time into ERROR state if an error occured within the mesh network or in the server.
 */
void state_init(uint8_t * buf_recv, uint8_t *buf_log);

 /**
  * @brief Main function of the CONF state, only used by the root card.
  * In this state, it transfers BEACON frame from the mesh to the server, and wait for INSTALL frame to send a B_ACK to the concerned card.
  * If it receives an AMA_init frame, it goes into the ADDR state
  * The root card can switch at any time into ERROR state if an error occured within the mesh network or in the server.
  */
void state_conf(uint8_t * buf_recv, uint8_t *buf_log);

/**
  * @brief Main function for the ADDR state.
  * This state is used during the Assisted Manual Addressing.
  * If the root receives a COLOR frame, it breaks it into COLOR_E frame, and send them to the proper card using its route table.
  * On reception on AMA_color frame, the Addressing is over, and all cards go into COLOR state
  * The root card can switch at any time into ERROR state if an error occured within the mesh network or in the server.
  */
void state_addr(uint8_t * buf_recv, uint8_t *buf_log);

/**
 * @brief Main function for the COLOR state.
 * This is the main state of the card.
 * If the root receives a COLOR frame, it breaks it into COLOR_E frame, and send them to the proper card using its route table.
 * On reception of COLOR_E frame, the card will dislay the color indicated.
 * The root card can switch at any time into ERROR state if an error occured within the mesh network or in the server.
 */
void state_color(uint8_t * buf_recv, uint8_t *buf_log);


/**
 * @brief Main function for the SLEEP state
 * This state is to be implemented, and is currently unused.
 */
 void state_reboot(uint8_t * buf_recv, uint8_t *buf_log);


 /**
  * @brief Main function for the ERROR state.
  * This state is used for error management, whatever error type it is. As such, it has the same functions as the color state, so that cards can still work properly while in this state.
  * This state has its own buffer, buff_err, that is filled when an error occured, so the message can be retrieved and processed properly.
  * There are different kind of errors :
  * - ERR_DECO happens when a child is disconnected from its parent, or unreachable. The message is to be sent to the server, in order for the error to be acknowledged.
  * - ERR_CO happens when a card declares itself outside of moments planned for it (CONF state) : the server is to be noticed, and several outcomes may happens.
  * - ERR_GOTO forces a card to change state.
  * - ERR_ROOT is used to notify the server that a reconnection with a different root happened.
  */
  void state_error(uint8_t * buf_recv, uint8_t *buf_log);
#endif
