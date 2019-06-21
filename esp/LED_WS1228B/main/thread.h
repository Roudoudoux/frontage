#ifndef __THREAD_H__
#define __THREAD_H__


/**
 * @brief Main reception function for the mesh side : always checks if a message is available for this card, and writes it in the reception pipe.
 *
 * @attention This is a Task that is always running.
 *
 * @attention The Watchdog is resetted automatically as esp_mesh_recv is an blocking call while no message have been received.
 */
void mesh_reception(void * arg);


/**
 * @brief Main reception function for the server side, only used by the root card. It checks if a message is available, and writes it in the repection pipe.
 *
 * @attention This is a Task that is always running.
 *
 * @attention The Watchdog is resetted automatically as esp_mesh_recv is an blocking call while no message have been received.
 */
 void server_reception(void * arg);


 /**
  *@brief Function that sends a message to a specific card or broadcast it.
  * - The message is read from the mesh transmission pipe using the adress given in argument.
  * - Then, depending on the type of the message, it will either be sent to a specific card, or to the whole mesh.
  * - This Task is created when the message must be sent, and destroyed afterwards.
  */
  void mesh_emission(void * arg);


  /**
   *@brief Function that sends a message to the server.
   * - The message is read from the server transmission pipe, using the address given in arguments.
   * - It is then wrtitten in the socket binding the root card and the server.
   * - This task is created when a message need to be sent, and destroyed afterwards.
   *
   * @attention Only the root card can use this
   */
   void server_emission(void * arg);

#endif
