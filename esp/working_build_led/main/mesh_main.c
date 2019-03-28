#include <string.h>
#include <nvs_flash.h>
#include <lwip/sockets.h>
#include <pthread.h>

//#define __MAIN__

#include "mesh.h"
#include "utils.h"
#include "crc.h"
#include "shared_buffer.h"
#include "state_machine.h"
#include "thread.h"
#include "display_color.h"

#define BLINK_GPIO 2


/*******************************************************
 *                Variable Definitions
 *******************************************************/

char * MESH_TAG = "mesh_main";
uint8_t MESH_ID[6] = { 0x77, 0x77, 0x77, 0x77, 0x77, 0x77};

bool is_running = true;
bool is_mesh_connected = false;
mesh_addr_t mesh_parent_addr;
int mesh_layer = -1;
uint8_t my_mac[6] = {0};
unsigned int state = INIT;
bool is_asleep = false;
uint16_t current_sequence = 0;
uint8_t buf_err[FRAME_SIZE] = {0};
int err_addr_req = 0;

/*Variable du socket */
struct sockaddr_in tcpServerAddr;
struct sockaddr_in tcpServerReset;
uint32_t sock_fd;
bool is_server_connected = false;

/* Table de routage Arbalet Mesh*/
//struct node route_table[CONFIG_MESH_ROUTE_TABLE_SIZE];
int route_table_size = 0;
//static int num[CONFIG_MESH_ROUTE_TABLE_SIZE];
unsigned int ctr = 0;

/*******************************************************
 *                Function Declarations
 *******************************************************/

/*******************************************************
 *                Function Definitions
 *******************************************************/

/**
 *   @brief Update the route table :
 * - add a mac address to the route table if the position is not used;
 * - swap two element if the mac address is already present and the position is used;
 * - replace the used position by the new mac address otherwise;
 */
void add_route_table(uint8_t * mac, int pos){
    if (pos == route_table_size) {
	copy_mac(mac, route_table[pos].card.addr);
	route_table[pos].state = true;
	route_table_size++;
    } else {
	int i = 0;
	while (! same_mac(mac, route_table[i].card.addr) && i < route_table_size) {
	    i++;
	} if (i == route_table_size) { // Remplacement sans substitution
	    ESP_LOGW(MESH_TAG, "MAC not in route_table, replaced old MAC value by new");
	    copy_mac(mac, route_table[pos].card.addr);
	    route_table[pos].state = true;
	    return;
	}
	copy_mac(route_table[pos].card.addr, route_table[i].card.addr);
	copy_mac(mac, route_table[pos].card.addr);
    }
    for (int j = 0; j < route_table_size; j++) {
	ESP_LOGW(MESH_TAG, "Addr %d : "MACSTR"", j, MAC2STR(route_table[j].card.addr));
    }
}

void disable_node(uint8_t *mac) {
    int i = 0;
    while (! same_mac(mac, route_table[i].card.addr) && i < route_table_size) {
	i++;
    }
    if (i == route_table_size) {
	ESP_LOGE(MESH_TAG, "Request for disabling MAC not in routing table.");
	return;
    }
    route_table[i].state = false;
}

void enable_node(uint8_t *mac) {
    int i = 0;
    while (! same_mac(mac, route_table[i].card.addr) && i < route_table_size) {
	i++;
    }
    if (i == route_table_size) {
	ESP_LOGE(MESH_TAG, "Request for disabling MAC not in routing table.");
	return;
    }
    route_table[i].state = true;
    ESP_LOGI(MESH_TAG, ""MACSTR" : %d", MAC2STR(route_table[i].card.addr), route_table[i].state);
}

/**
 * @brief Opens the socket between the root card and the server, and initialize the connection.
 */
void connect_to_server() {

    sock_fd = socket(AF_INET, SOCK_STREAM, 0); // Ouverture du socket avec le serveur.
    if (sock_fd == -1) {
	ESP_LOGE(MESH_TAG, "Socket_fail");
	return;
    }
    int ret = connect(sock_fd, (struct sockaddr *)&tcpServerAddr, sizeof(struct sockaddr));
    if (ret < 0 && errno != 119) {
	perror("Erreur socket : ");
	ESP_LOGE(MESH_TAG, "Connection fail");
	close(sock_fd);
	vTaskDelay(5000 / portTICK_PERIOD_MS); //Stop for 5s after each try
    }else {
	ESP_LOGW(MESH_TAG, "Connected to Server");
	xTaskCreate(server_reception, "SERRX", 6000, NULL, 5, NULL);
	is_server_connected = true;
	if (state != INIT) {
	    uint8_t buf_send[FRAME_SIZE];
	    buf_send[VERSION] = SOFT_VERSION;
	    buf_send[TYPE] = ERROR;
	    buf_send[DATA] = ERROR_ROOT;
	    buf_send[DATA+1] = state & (route_table_size << 4);
	    copy_buffer(buf_send + DATA + 2, my_mac, 6);
	    int head = write_txbuffer(buf_send, FRAME_SIZE);
	    xTaskCreate(server_emission, "SERTX", 3072, (void *) head, 5, NULL);
	}
    }
}

/**
 * @brief Main function
 * This decides which function to call depending on the state of the card, and regulate the watchdogs of the state machine.
 */
void esp_mesh_state_machine(void * arg) {
    is_running = true;

    while(is_running) {;
	switch(state) {
	case INIT:
	    state_init();
	    break;
	case CONF :
	    state_conf();
	    vTaskDelay(1 / portTICK_PERIOD_MS);
	    break;
	case ADDR :
	    state_addr();
	    vTaskDelay(1 / portTICK_PERIOD_MS);
	    break;
	case COLOR :
	    state_color();
	    vTaskDelay(1 / portTICK_PERIOD_MS);
	    break;
	case ERROR_S :
	    state_error();
	    vTaskDelay(1 / portTICK_PERIOD_MS);
	    break;
	default :
	    ESP_LOGE(MESH_TAG, "ESP entered unknown state %d", state);
	}
    }
    vTaskDelete(NULL);
}

/**
 *@brief Makes the Builtin blue led blink as many times as the layer number
 */
void blink_task(void *pvParameter)
{
    gpio_pad_select_gpio(BLINK_GPIO);
	/* Set the GPIO as a push/pull output */
    gpio_set_direction(BLINK_GPIO, GPIO_MODE_OUTPUT);
	/* Blink off (output low) */
    while(1) {
	for (int i = 0; i < state; i++) {
	    gpio_set_level(BLINK_GPIO, 1);
	    vTaskDelay(200 / portTICK_PERIOD_MS);
	    // Blink on (output high)
	    gpio_set_level(BLINK_GPIO, 0);
	    vTaskDelay(200 / portTICK_PERIOD_MS);
	}
	vTaskDelay(2000 / portTICK_PERIOD_MS);
    }
}

void dummy_task(void *pvParameter)
{
    while(1) {
	ctr++;
	vTaskDelay(10);
    }
}

void CPU_load(void * pvParameter)
{
    while(1) {
	unsigned int cycles = ctr;
	ESP_LOGI(MESH_TAG, "CPU LOAD = %d percent\n", (int)(((float)cycles/100)*100));
	ctr = 0;
	vTaskDelay(1000/portTICK_PERIOD_MS);
    }
}

/**
 * @brief Initialise the Task of the card
 */
esp_err_t esp_mesh_comm_p2p_start(void)
{
    static bool is_comm_p2p_started = false;
    if (!is_comm_p2p_started) {
        is_comm_p2p_started = true;
	xTaskCreate(mesh_reception, "ESPRX", 3072, NULL, 5, NULL);
	xTaskCreate(esp_mesh_state_machine, "STMC", 3072, NULL, 5, NULL);
	xTaskCreate(blink_task, "blink_task", 3072, NULL, 5, NULL);
	//xTaskCreate(CPU_load, "CPUT", 64*configMINIMAL_STACK_SIZE, NULL, 5, NULL);
	//xTaskCreate(dummy_task, "DMYT", configMINIMAL_STACK_SIZE, NULL, 0, NULL);
    }
    return ESP_OK;
}

void error_child_disconnected(uint8_t *mac) {
    ESP_LOGE(MESH_TAG, "Sent frame for Child Disconnection");
    uint8_t buf_send[FRAME_SIZE];
    buf_send[VERSION] = SOFT_VERSION;
    buf_send[TYPE] = ERROR;
    buf_send[DATA] = ERROR_DECO;
    buf_send[DATA+1] = 0;
    copy_buffer(buf_send + DATA + 2, mac, 6);
    int head = write_txbuffer(buf_send, FRAME_SIZE);
    xTaskCreate(mesh_emission, "ESPTX", 3072, (void *) head, 5, NULL);
}

/**
 * @brief Debug logs on event
 */
void mesh_event_handler(mesh_event_t event)
{
    mesh_addr_t id = {0,};
    static uint8_t last_layer = 0;
    ESP_LOGD(MESH_TAG, "esp_event_handler:%d", event.id);

    switch (event.id) {
    case MESH_EVENT_STARTED:
        esp_mesh_get_id(&id);
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_STARTED>ID:"MACSTR"", MAC2STR(id.addr));
        is_mesh_connected = false;
        mesh_layer = esp_mesh_get_layer();
        break;
    case MESH_EVENT_STOPPED:
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_STOPPED>");
        is_mesh_connected = false;
        mesh_layer = esp_mesh_get_layer();
        break;
    case MESH_EVENT_CHILD_CONNECTED:
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_CHILD_CONNECTED>aid:%d, "MACSTR"",
                 event.info.child_connected.aid,
                 MAC2STR(event.info.child_connected.mac));
        break;
    case MESH_EVENT_CHILD_DISCONNECTED:
	error_child_disconnected(event.info.child_disconnected.mac);
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_CHILD_DISCONNECTED>aid:%d, "MACSTR"",
                 event.info.child_disconnected.aid,
                 MAC2STR(event.info.child_disconnected.mac));
        break;
    case MESH_EVENT_ROUTING_TABLE_ADD:
        ESP_LOGW(MESH_TAG, "<MESH_EVENT_ROUTING_TABLE_ADD>add %d, new:%d",
                 event.info.routing_table.rt_size_change,
                 event.info.routing_table.rt_size_new);
        break;
    case MESH_EVENT_ROUTING_TABLE_REMOVE:
        ESP_LOGW(MESH_TAG, "<MESH_EVENT_ROUTING_TABLE_REMOVE>remove %d, new:%d",
                 event.info.routing_table.rt_size_change,
                 event.info.routing_table.rt_size_new);
        break;
    case MESH_EVENT_NO_PARENT_FOUND:
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_NO_PARENT_FOUND>scan times:%d",
                 event.info.no_parent.scan_times);
        /* TODO handler for the failure */
        break;
    case MESH_EVENT_PARENT_CONNECTED:
        esp_mesh_get_id(&id);
        mesh_layer = event.info.connected.self_layer;
        memcpy(&mesh_parent_addr.addr, event.info.connected.connected.bssid, 6);
        ESP_LOGI(MESH_TAG,
                 "<MESH_EVENT_PARENT_CONNECTED>layer:%d-->%d, parent:"MACSTR"%s, ID:"MACSTR"",
                 last_layer, mesh_layer, MAC2STR(mesh_parent_addr.addr),
                 esp_mesh_is_root() ? "<ROOT>" :
                 (mesh_layer == 2) ? "<layer2>" : "", MAC2STR(id.addr));
        last_layer = mesh_layer;
        is_mesh_connected = true;
        if (esp_mesh_is_root()) {
            tcpip_adapter_dhcpc_start(TCPIP_ADAPTER_IF_STA);
        }
        esp_mesh_comm_p2p_start();
        break;
    case MESH_EVENT_PARENT_DISCONNECTED:
        ESP_LOGI(MESH_TAG,
                 "<MESH_EVENT_PARENT_DISCONNECTED>reason:%d",
                 event.info.disconnected.reason);
        is_mesh_connected = false;
        mesh_layer = esp_mesh_get_layer();
	uint8_t fake[FRAME_SIZE] = {0, 0, 0, 0, 255, 0, 255};//In official build, turn off pixels. Currently, may be mistaken for LED failure, so color signal it is.
	display_color(fake);
        break;
    case MESH_EVENT_LAYER_CHANGE:
        mesh_layer = event.info.layer_change.new_layer;
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_LAYER_CHANGE>layer:%d-->%d%s",
                 last_layer, mesh_layer,
                 esp_mesh_is_root() ? "<ROOT>" :
                 (mesh_layer == 2) ? "<layer2>" : "");
        last_layer = mesh_layer;
        break;
    case MESH_EVENT_ROOT_ADDRESS:
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_ROOT_ADDRESS>root address:"MACSTR"",
                 MAC2STR(event.info.root_addr.addr));
        break;
    case MESH_EVENT_ROOT_GOT_IP:
        /* root starts to connect to server */
        ESP_LOGI(MESH_TAG,
                 "<MESH_EVENT_ROOT_GOT_IP>sta ip: " IPSTR ", mask: " IPSTR ", gw: " IPSTR,
                 IP2STR(&event.info.got_ip.ip_info.ip),
                 IP2STR(&event.info.got_ip.ip_info.netmask),
                 IP2STR(&event.info.got_ip.ip_info.gw));
        break;
    case MESH_EVENT_ROOT_LOST_IP:
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_ROOT_LOST_IP>");
        break;
    case MESH_EVENT_VOTE_STARTED:
        ESP_LOGI(MESH_TAG,
                 "<MESH_EVENT_VOTE_STARTED>attempts:%d, reason:%d, rc_addr:"MACSTR"",
                 event.info.vote_started.attempts,
                 event.info.vote_started.reason,
                 MAC2STR(event.info.vote_started.rc_addr.addr));
        break;
    case MESH_EVENT_VOTE_STOPPED:
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_VOTE_STOPPED>");
        break;
    case MESH_EVENT_ROOT_SWITCH_REQ:
        ESP_LOGI(MESH_TAG,
                 "<MESH_EVENT_ROOT_SWITCH_REQ>reason:%d, rc_addr:"MACSTR"",
                 event.info.switch_req.reason,
                 MAC2STR( event.info.switch_req.rc_addr.addr));
        break;
    case MESH_EVENT_ROOT_SWITCH_ACK:
        /* new root */
        mesh_layer = esp_mesh_get_layer();
        esp_mesh_get_parent_bssid(&mesh_parent_addr);
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_ROOT_SWITCH_ACK>layer:%d, parent:"MACSTR"", mesh_layer, MAC2STR(mesh_parent_addr.addr));
        break;
    case MESH_EVENT_TODS_STATE:
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_TODS_REACHABLE>state:%d",
                 event.info.toDS_state);
        break;
    case MESH_EVENT_ROOT_FIXED:
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_ROOT_FIXED>%s",
                 event.info.root_fixed.is_fixed ? "fixed" : "not fixed");
        break;
    case MESH_EVENT_ROOT_ASKED_YIELD:
        ESP_LOGI(MESH_TAG,
                 "<MESH_EVENT_ROOT_ASKED_YIELD>"MACSTR", rssi:%d, capacity:%d",
                 MAC2STR(event.info.root_conflict.addr),
                 event.info.root_conflict.rssi,
                 event.info.root_conflict.capacity);
        break;
    case MESH_EVENT_CHANNEL_SWITCH:
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_CHANNEL_SWITCH>new channel:%d", event.info.channel_switch.channel);
        break;
    case MESH_EVENT_SCAN_DONE:
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_SCAN_DONE>number:%d",
                 event.info.scan_done.number);
        break;
    case MESH_EVENT_NETWORK_STATE:
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_NETWORK_STATE>is_rootless:%d",
                 event.info.network_state.is_rootless);
        break;
    case MESH_EVENT_STOP_RECONNECTION:
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_STOP_RECONNECTION>");
        break;
    case MESH_EVENT_FIND_NETWORK:
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_FIND_NETWORK>new channel:%d, router BSSID:"MACSTR"",
                 event.info.find_network.channel, MAC2STR(event.info.find_network.router_bssid));
        break;
    case MESH_EVENT_ROUTER_SWITCH:
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_ROUTER_SWITCH>new router:%s, channel:%d, "MACSTR"",
                 event.info.router_switch.ssid, event.info.router_switch.channel, MAC2STR(event.info.router_switch.bssid));
        break;
    default:
        ESP_LOGI(MESH_TAG, "unknown id:%d", event.id);
        break;
    }
}

/**
 * @brief Startup function : initialize the cards
 */
void app_main(void)
{
    ESP_ERROR_CHECK(nvs_flash_init());
    /*  tcpip initialization */
    tcpip_adapter_init();
    /* for mesh
     * stop DHCP server on softAP interface by default
     * stop DHCP client on station interface by default
     * */
    ESP_ERROR_CHECK(tcpip_adapter_dhcps_stop(TCPIP_ADAPTER_IF_AP));
    ESP_ERROR_CHECK(tcpip_adapter_dhcpc_stop(TCPIP_ADAPTER_IF_STA));
    /*  wifi initialization */
    ESP_ERROR_CHECK(esp_event_loop_init(NULL, NULL));
    wifi_init_config_t config = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&config));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_FLASH));
    /*wifi_config_t sta_config = {
	.sta = {
	    .ssid = CONFIG_MESH_ROUTER_SSID,
	    .password = CONFIG_MESH_ROUTER_PASSWD
	}
    };
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &sta_config));*/
    ESP_ERROR_CHECK(esp_wifi_start());
    /*  mesh initialization */
    ESP_ERROR_CHECK(esp_mesh_init());
    ESP_ERROR_CHECK(esp_mesh_set_max_layer(CONFIG_MESH_MAX_LAYER));
    ESP_ERROR_CHECK(esp_mesh_set_vote_percentage(1));
    ESP_ERROR_CHECK(esp_mesh_set_ap_assoc_expire(10));
#ifdef MESH_FIX_ROOT
    ESP_ERROR_CHECK(esp_mesh_fix_root(1));
#endif
    mesh_cfg_t cfg = MESH_INIT_CONFIG_DEFAULT();
    /* mesh ID */
    memcpy((uint8_t *) &cfg.mesh_id, MESH_ID, 6);
    /* mesh event callback */
    cfg.event_cb = &mesh_event_handler;
    /* router */
    cfg.channel = CONFIG_MESH_CHANNEL;
    cfg.router.ssid_len = strlen(CONFIG_MESH_ROUTER_SSID);
    memcpy((uint8_t *) &cfg.router.ssid, CONFIG_MESH_ROUTER_SSID, cfg.router.ssid_len);
    memcpy((uint8_t *) &cfg.router.password, CONFIG_MESH_ROUTER_PASSWD,
           strlen(CONFIG_MESH_ROUTER_PASSWD));
    /* mesh softAP */
    ESP_ERROR_CHECK(esp_mesh_set_ap_authmode(CONFIG_MESH_AP_AUTHMODE));
    cfg.mesh_ap.max_connection = CONFIG_MESH_AP_CONNECTIONS;
    memcpy((uint8_t *) &cfg.mesh_ap.password, CONFIG_MESH_AP_PASSWD,
           strlen(CONFIG_MESH_AP_PASSWD));
    ESP_ERROR_CHECK(esp_mesh_set_config(&cfg));
    /* Initialisation de l'adresse MAC*/
    esp_efuse_mac_get_default(my_mac);
    ESP_LOGI(MESH_TAG, "my mac : %d-%d-%d-%d-%d-%d", my_mac[0], my_mac[1], my_mac[2], my_mac[3], my_mac[4], my_mac[5]);
    /* mesh start */
    ESP_ERROR_CHECK(esp_mesh_start());
    ESP_LOGI(MESH_TAG, "mesh starts successfully, heap:%d, %s\n",  esp_get_free_heap_size(),
             esp_mesh_is_root_fixed() ? "root fixed" : "root not fixed");
    /* Socket creation */
    memset(&tcpServerAddr, 0, sizeof(tcpServerAddr));
    tcpServerAddr.sin_family = AF_INET;
    tcpServerAddr.sin_addr.s_addr = inet_addr("10.42.0.1");//("192.168.0.101");
    tcpServerAddr.sin_len = sizeof(tcpServerAddr);
    tcpServerAddr.sin_port = htons(9988);
    /* Strand Init (LED Ribbon) */
    init_leds();
    uint8_t fake[FRAME_SIZE] = {0, 0, 0, 0, 255, 255, 255};
    display_color(fake);
}
