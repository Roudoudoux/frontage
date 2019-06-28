#ifndef __MESH_H__
#define __MESH_H__
#define SERVER_LOG 1

#include "esp_wifi.h"
#include "esp_system.h"
#include "esp_event_loop.h"
#include "esp_log.h"
#include "esp_mesh.h"
#include "esp_mesh_internal.h"
#include <driver/gpio.h>
#include "freertos/ringbuf.h"

#define TIME_TO_GET_MESH 150000000 //time in seconds
#define SOFT_VERSION 2
#define SEQU_SEUIL 60000

#define RX_SIZE          (1500)
#define TX_SIZE          (1460)

/* Frames composition*/

#define VERSION 0
#define TYPE 1
#define SUB_TYPE 2
#define DATA 2
#define CHECKSUM 15
#define HEADER_SIZE 2
#define FRAME_SIZE 16

/* Frames types */

#define BEACON 1
#define B_ACK 2
#define INSTALL 3
#define COLOR 4
#define COLOR_E 5
#define AMA 6
#define ERROR 7
#define REBOOT 8
#define LOG 9

/* AMA sub types */
#define AMA_START 59
#define AMA_INIT 60
#define AMA_COLOR 61
#define AMA_END 62

/* ERROR sub types */

#define ERROR_CO 71
#define ERROR_DECO 72
#define ERROR_GOTO 73
#define ERROR_ROOT 74

/* States */

#define INIT 1
#define CONF 2
#define ADDR 3
#define COLOR 4
#define ERROR_S 5
#define REBOOT_S 6

/* Colors Miscellaneous */

#define HIGH 1
#define LOW 0
#define OUTPUT GPIO_MODE_OUTPUT
#define INPUT GPIO_MODE_INPUT


#define RGB_SIZE 3
#define SEQUENCE_SIZE 2
#define MAC_SIZE 6
#define FOREVER (15000 / portTICK_PERIOD_MS)

RingbufHandle_t STQ, RQ, MTQ;
/*******************************************************
 *                Structures
 *******************************************************/
/**
 * @brief Route table element
 */
struct node {
    mesh_addr_t card; /**< Mac address of the card, mesh_addr_t format */
    bool state; /**< Indicate if card is currently connected to the root */
};

struct node route_table[CONFIG_MESH_ROUTE_TABLE_SIZE];
extern int route_table_size;
extern char *MESH_TAG;
extern uint8_t MESH_ID[6];

extern bool is_running;
extern bool is_mesh_connected;
extern mesh_addr_t mesh_parent_addr;
extern int mesh_layer;
extern uint8_t my_mac[MAC_SIZE];
extern unsigned int state;
extern unsigned int old_state;
extern bool is_asleep;
extern uint16_t current_sequence;
extern uint8_t buf_err[FRAME_SIZE];
extern int err_addr_req;
extern int err_prev_state;


/* Socket's variable */
extern struct sockaddr_in tcpServerAddr;
extern struct sockaddr_in tcpServerReset;
extern uint32_t sock_fd;
extern bool is_server_connected;

/* Logical routing table */
extern int route_table_size;

/* Main functions */
/**
 *   @brief Update the route table :
 * - add a mac address to the route table if the position is not used;
 * - swap two element if the mac address is already present and the position is used;
 * - replace the used position by the new mac address otherwise;
 */
void add_route_table(uint8_t *, int);

/**
 * @brief Disable a node : prevent the root from sending message to this specific node. Is used to indicate that it's down.
 */
void disable_node(uint8_t *);

/**
 * @brief Enable a node : allow the root to send messages again to this specific node. Is used to indicate that a node is reconnected to the mesh network.
 */
void enable_node(uint8_t *);

/**
 * @brief Opens the socket between the root card and the server, and initialize the connection. Is mandatory for becoming root.
 */
void connect_to_server();

/**
 * @brief Main function
 * This decides which function to call depending on the state of the card, and regulate the watchdogs of the state machine.
 */
void esp_mesh_state_machine(void *);

/**
 *@brief Makes the Builtin blue led blink as many times as the layer number : Debug.
 */
void blink_task(void *);

/**
 * @brief Initialise the Task of the card
 */
esp_err_t esp_mesh_comm_p2p_start(void);

/**
 * @brief Send a message to the root notifying that a child disconnection event happened, or a child answers with the NO_ROUTING error.
 */
void error_child_disconnected(uint8_t *);

/**
 * @brief Send a beacon to the root on reconnection to the network : allow for layer switches.
 */
void send_beacon_on_disco();

/**
 * @brief Debug logs on event, and events management.
 */
void mesh_event_handler(mesh_event_t);

/**
 * @brief Startup function : initialize the cards
 */
void app_main(void);



#endif
