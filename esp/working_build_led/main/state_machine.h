#ifndef __STATE_MACHINE_H__
#define __STATE_MACHINE_H__


/**
 * @brief Main function of the INIT state.
 * In this state, root card will send BEACON to server, and wait for INSTALL to go into CONF state.
 * Node cards will send BEACON to the root, and wait for B_ACK to go into ADDR state
 */
void state_init();

 /**
  * @brief Main function of the CONF state, only used by the root card.
  * In this state, it transfers BEACON frame from the mesh to the server, and wait for INSTALL frame to send a B_ACK to the concerned card.
  * If it receives an AMA_init frame, it goes into the ADDR state
  */
void state_conf();

/**
  * @brief Main function for the ADDR state.
  * This state is used during the Assisted Manual Addressing.
  * In this state, the root card will wait for INSTALL frame from the server, and broadcast them to the mesh network. On reception, every card will update its route table.
  * If the root receives a COLOR frame, it breaks it into COLOR_E frame, and send them to the proper card using its route table.
  * On reception on AMA_color frame, the Addressing is over, and all cards go into COLOR state
  */
void state_addr();

/**
 * @brief Main function for the COLOR state.
 * This is the main state of the card.
 * If the root receives a COLOR frame, it breaks it into COLOR_E frame, and send them to the proper card using its route table.
 * On reception of COLOR_E frame, the card will dislay the color indicated.
 * The root card can switch at any time into ERROR state if an error occured within the mesh network or in the server.
 * On reception of SLEEP frame from the server, the root will put the mesh network asleep
 */
void state_color();


/**
 * @brief Main function for the SLEEP state
 * In this state, cards don't do much. They simply wait for a WAKEUP frame from the server.
 * (to be implemented/corrected)
 */
 void state_sleep();


 /**
  * @brief To be implemented
  */
  void state_error();
#endif
