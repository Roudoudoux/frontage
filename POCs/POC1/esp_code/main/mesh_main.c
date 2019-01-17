/* Mesh Internal Communication Example

   This example code is in the Public Domain (or CC0 licensed, at your option.)

   Unless required by applicable law or agreed to in writing, this
   software is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
   CONDITIONS OF ANY KIND, either express or implied.
*/
#include <string.h>
#include "esp_wifi.h"
#include "esp_system.h"
#include "esp_event_loop.h"
#include "esp_log.h"
#include "esp_mesh.h"
#include "esp_mesh_internal.h"
#include "mesh_light.h"
#include "nvs_flash.h"
#include "lwip/sockets.h"

/*******************************************************
 *                Macros
 *******************************************************/
//#define MESH_P2P_TOS_OFF

/*******************************************************
 *                Constants
 *******************************************************/
#define RX_SIZE          (1500)
#define TX_SIZE          (1460)
#define COLOR             1
#define MAC               2

/*******************************************************
 *                Variable Definitions
 *******************************************************/
static const char *MESH_TAG = "mesh_main";
static const uint8_t MESH_ID[6] = { 0x77, 0x77, 0x77, 0x77, 0x77, 0x77};
static uint8_t tx_buf[TX_SIZE] = { 0, };
static uint8_t rx_buf[RX_SIZE] = { 0, };
static bool is_running = true;
static bool is_mesh_connected = false;
static mesh_addr_t mesh_parent_addr;
static int mesh_layer = -1;
static int send_mac = 0; // Flag binaire
static int mac_request = 0; // identifiant de la requete. Initialisé à 0, les cartes n'y répondent que si l'identifiant du message est strictement supérieur au leur. Sinon, ne font que le transmettre.
static mesh_addr_t node_asked; // Noeud ayant demandé l'adresse MAC (root)
static uint8_t my_mac[6] = {0};
static struct sockaddr_in tcpServerAddr;
static uint32_t sock_fd;

mesh_light_ctl_t light_on = {
    .cmd = MESH_CONTROL_CMD,
    .on = 1,
    .token_id = MESH_TOKEN_ID,
    .token_value = MESH_TOKEN_VALUE,
};

mesh_light_ctl_t light_off = {
    .cmd = MESH_CONTROL_CMD,
    .on = 0,
    .token_id = MESH_TOKEN_ID,
    .token_value = MESH_TOKEN_VALUE,
};

/*******************************************************
 *                Function Declarations
 *******************************************************/

/*******************************************************
 *                Function Definitions
 *******************************************************/
void esp_mesh_p2p_tx_main(void *arg)
{
    int i;
    esp_err_t err;
    int send_count = 0;
    mesh_addr_t route_table[CONFIG_MESH_ROUTE_TABLE_SIZE];
    int route_table_size = 0;
    mesh_data_t data;
    data.data = tx_buf;
    data.size = sizeof(tx_buf);
    data.proto = MESH_PROTO_BIN;
#ifdef MESH_P2P_TOS_OFF
    data.tos = MESH_TOS_DEF;
#endif /* MESH_P2P_TOS_OFF */

    is_running = true;
    while (is_running) {
        /* non-root do nothing but print */
        if (!esp_mesh_is_root()) {
	    ESP_LOGI(MESH_TAG, "state : %d", send_mac);
            ESP_LOGI(MESH_TAG, "layer:%d, rtableSize:%d, %s", mesh_layer,
                     esp_mesh_get_routing_table_size(),
                     (is_mesh_connected && esp_mesh_is_root()) ? "ROOT" : is_mesh_connected ? "NODE" : "DISCONNECT");
            vTaskDelay(10 * 1000 / portTICK_RATE_MS);
	    if (send_mac) { // Les cartes recopient leur adresses mac dans le buffer et l'envoient.
		tx_buf[0] = MAC;
		tx_buf[1] = my_mac[0];
		tx_buf[2] = my_mac[1];
		tx_buf[3] = my_mac[2];
		tx_buf[4] = my_mac[3];
		tx_buf[5] = my_mac[4];
		tx_buf[6] = my_mac[5];
		tx_buf[7] = mac_request;
		send_mac = 0;
		esp_mesh_send(&node_asked, &data, MESH_DATA_P2P, NULL, 0); // Répond au noeud qui a demandé la requête.
		ESP_LOGI(MESH_TAG, "send my mac addr\n");
	    }
	    continue;
        } // Code propre aux cartes root.
	sock_fd = socket(AF_INET, SOCK_STREAM, 0); // Ouverture du socket avec le serveur.
	if (sock_fd == -1) {
	    ESP_LOGE(MESH_TAG, "Socket_fail");
	}
	int ret = connect(sock_fd, (struct sockaddr *)&tcpServerAddr, sizeof(struct sockaddr));
	if (ret != 0) {
	    ESP_LOGE(MESH_TAG, "Connection fail");
	    close(sock_fd);
	    }
        esp_mesh_get_routing_table((mesh_addr_t *) &route_table,
                                   CONFIG_MESH_ROUTE_TABLE_SIZE * 6, &route_table_size); // mise à jour de la table de routage : contient les adresses MAC de toutes les cartes du reseau.
	send_count++;
        if (send_count && !(send_count % 10)) { // Tout les 10 messages : emettre une requete MAC
            ESP_LOGI(MESH_TAG, "size:%d/%d,send_count:%d", route_table_size,
                     esp_mesh_get_routing_table_size(), send_count);
	    if (esp_mesh_is_root()) {
		mac_request++;
		tx_buf[0] = MAC;
		tx_buf[1] = my_mac[0];
		tx_buf[2] = my_mac[1];
		tx_buf[3] = my_mac[2];
		tx_buf[4] = my_mac[3];
		tx_buf[5] = my_mac[4];
		tx_buf[6] = my_mac[5];
		tx_buf[7] = mac_request;
		for (i = 0; i < route_table_size; i++) {
		    err = esp_mesh_send(&route_table[i], &data, MESH_DATA_P2P, NULL, 0); // Envoie d'un message à toutes les cartes au sein du réseau.
		    if (err) {
			ESP_LOGE(MESH_TAG,
				 "[ROOT-2-UNICAST:%d][L:%d]parent:"MACSTR" to "MACSTR", heap:%d[err:0x%x, proto:%d, tos:%d]",
				 send_count, mesh_layer, MAC2STR(mesh_parent_addr.addr),
				 MAC2STR(route_table[i].addr), esp_get_free_heap_size(),
				 err, data.proto, data.tos);
		    } else if (!(send_count % 10)) {
			ESP_LOGW(MESH_TAG,
				 "[ROOT-2-UNICAST:%d][L:%d][rtableSize:%d]parent:"MACSTR" to "MACSTR", heap:%d[err:0x%x, proto:%d, tos:%d]",
				 send_count, mesh_layer,
				 esp_mesh_get_routing_table_size(),
				 MAC2STR(mesh_parent_addr.addr),
				 MAC2STR(route_table[i].addr), esp_get_free_heap_size(),
				 err, data.proto, data.tos);
		    }
		    ESP_LOGI(MESH_TAG, "asked "MACSTR" for mac addr\n", MAC2STR(route_table[i].addr));
		}
		char message[100]; //Envoie des adresse mac de la table de routage au serveur.
		for (i = 0; i < route_table_size; i++) { // Formatage du message.
		    sprintf(message+20*i, "%2x:%2x:%2x:%2x:%2x:%2x - ", route_table[i].addr[0], route_table[i].addr[1], route_table[i].addr[2], route_table[i].addr[3], route_table[i].addr[4], route_table[i].addr[5]);
		}
		int ret = write(sock_fd, message, strlen(message));//ecriture dans le socket.
		ESP_LOGI(MESH_TAG, "Message send : %d - %s", ret, message);
	    }
        } else if (send_mac == 0) {
	    tx_buf[0] = COLOR;
	    tx_buf[26] = (send_count >> 24) & 0xff;
	    tx_buf[25] = (send_count >> 16) & 0xff;
	    tx_buf[24] = (send_count >> 8) & 0xff;
	    tx_buf[23] = (send_count >> 0) & 0xff;
	    if (send_count % 2) {
		memcpy(tx_buf+8, (uint8_t *)&light_on, sizeof(light_on));
	    } else {
		memcpy(tx_buf+8, (uint8_t *)&light_off, sizeof(light_off));
	    }

	    for (i = 0; i < route_table_size; i++) {
		err = esp_mesh_send(&route_table[i], &data, MESH_DATA_P2P, NULL, 0);
		if (err) {
		    ESP_LOGE(MESH_TAG,
			     "[ROOT-2-UNICAST:%d][L:%d]parent:"MACSTR" to "MACSTR", heap:%d[err:0x%x, proto:%d, tos:%d]",
			     send_count, mesh_layer, MAC2STR(mesh_parent_addr.addr),
			     MAC2STR(route_table[i].addr), esp_get_free_heap_size(),
			     err, data.proto, data.tos);
		} else if (!(send_count % 100)) {
		    ESP_LOGW(MESH_TAG,
			     "[ROOT-2-UNICAST:%d][L:%d][rtableSize:%d]parent:"MACSTR" to "MACSTR", heap:%d[err:0x%x, proto:%d, tos:%d]",
			     send_count, mesh_layer,
			     esp_mesh_get_routing_table_size(),
			     MAC2STR(mesh_parent_addr.addr),
			     MAC2STR(route_table[i].addr), esp_get_free_heap_size(),
			     err, data.proto, data.tos);
		}
	    } 
	}
        /* if route_table_size is less than 10, add delay to avoid watchdog in this task. */
        if (route_table_size < 10) {
            vTaskDelay(1 * 1000 / portTICK_RATE_MS);
        }
	close(sock_fd); //Important : fermer le socket après utilisation.
    }
    vTaskDelete(NULL);
}

void esp_mesh_p2p_rx_main(void *arg)
{
    int recv_count = 0;
    esp_err_t err;
    mesh_addr_t from;
    int send_count = 0;
    mesh_data_t data;
    int flag = 0;
    data.data = rx_buf;
    data.size = RX_SIZE;

    is_running = true;
    while (is_running) {
        data.size = RX_SIZE;
        err = esp_mesh_recv(&from, &data, portMAX_DELAY, &flag, NULL, 0);
        if (err != ESP_OK || !data.size) {
            ESP_LOGE(MESH_TAG, "err:0x%x, size:%d", err, data.size);
            continue;
        }
        /* extract send count */
        if (data.size >= sizeof(send_count)) {
            send_count = (data.data[26] << 24) | (data.data[25] << 16)
                         | (data.data[24] << 8) | data.data[23];
        }
        /* process light control */
	if (data.data[0] == COLOR) {
	    recv_count++;
	    mesh_light_process(&from, data.data+8, data.size);
	    if (!(recv_count % 1)) {
		ESP_LOGW(MESH_TAG,
			 "[#RX:%d/%d][L:%d] parent:"MACSTR", receive from "MACSTR", size:%d, heap:%d, flag:%d[err:0x%x, proto:%d, tos:%d]",
			 recv_count, send_count, mesh_layer,
			 MAC2STR(mesh_parent_addr.addr), MAC2STR(from.addr),
			 data.size, esp_get_free_heap_size(), flag, err, data.proto,
			 data.tos);
	    }
	} else if (data.data[0] == MAC) { // si une requete MAC est reçue
	    if (!esp_mesh_is_root()) {
		if (data.data[7] > mac_request) { // Vérification de l'identifiant de la requete.
		    mac_request++;
		    ESP_LOGI(MESH_TAG, "received mac request, sending\n");
		    node_asked = from;
		    send_mac = 1; // Flag pour que la carte envoie un message au prochain rappel de Tx.
		} else {
		    esp_mesh_send(&mesh_parent_addr, &data, MESH_DATA_P2P, NULL, 0); //Transmis au parent immédiatement.
		}
	    } else {// A la réception d'une adresse MAC, le noeud root l'affiche
		ESP_LOGI(MESH_TAG, "MAC received : %x:%x:%x:%x:%x:%x\n", data.data[1], data.data[2], data.data[3], data.data[4], data.data[5], data.data[6]);
	    }
	}
    }
    vTaskDelete(NULL);
}

esp_err_t esp_mesh_comm_p2p_start(void)
{
    static bool is_comm_p2p_started = false;
    if (!is_comm_p2p_started) {
        is_comm_p2p_started = true;
        xTaskCreate(esp_mesh_p2p_tx_main, "MPTX", 3072, NULL, 5, NULL);
        xTaskCreate(esp_mesh_p2p_rx_main, "MPRX", 3072, NULL, 5, NULL);
    }
    return ESP_OK;
}

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
        mesh_connected_indicator(mesh_layer);
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
        mesh_disconnected_indicator();
        mesh_layer = esp_mesh_get_layer();
        break;
    case MESH_EVENT_LAYER_CHANGE:
        mesh_layer = event.info.layer_change.new_layer;
        ESP_LOGI(MESH_TAG, "<MESH_EVENT_LAYER_CHANGE>layer:%d-->%d%s",
                 last_layer, mesh_layer,
                 esp_mesh_is_root() ? "<ROOT>" :
                 (mesh_layer == 2) ? "<layer2>" : "");
        last_layer = mesh_layer;
        mesh_connected_indicator(mesh_layer);
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

void app_main(void)
{
    ESP_ERROR_CHECK(mesh_light_init());
    ESP_ERROR_CHECK(nvs_flash_init());
    /*  tcpip initialization */
    tcpip_adapter_init();
    /* for non-root node (stop for everyone and restart it later) :
     * stop DHCP server on softAP interface by default
     * stop DHCP client on station interface by default
     * */
    ESP_ERROR_CHECK(tcpip_adapter_dhcps_stop(TCPIP_ADAPTER_IF_AP));
    ESP_ERROR_CHECK(tcpip_adapter_dhcpc_stop(TCPIP_ADAPTER_IF_STA));
#if 0
    /* static ip settings */
    tcpip_adapter_ip_info_t sta_ip;
    sta_ip.ip.addr = ipaddr_addr("192.168.1.102");
    sta_ip.gw.addr = ipaddr_addr("192.168.1.1");
    sta_ip.netmask.addr = ipaddr_addr("255.255.255.0");
    tcpip_adapter_set_ip_info(WIFI_IF_STA, &sta_ip);
#endif
    /*  wifi initialization */
    ESP_ERROR_CHECK(esp_event_loop_init(NULL, NULL)); // callback, ctx? (reserved for user)
    wifi_init_config_t config = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&config)); // L'API WI-FI doit toujours être lancée en premier.
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_FLASH));
    ESP_ERROR_CHECK(esp_wifi_start());
    /*  mesh initialization */
    ESP_ERROR_CHECK(esp_mesh_init());
    ESP_ERROR_CHECK(esp_mesh_set_max_layer(CONFIG_MESH_MAX_LAYER)); // default : 25
    ESP_ERROR_CHECK(esp_mesh_set_vote_percentage(1)); // pourcentage pour les élections du futur root
    ESP_ERROR_CHECK(esp_mesh_set_ap_assoc_expire(10)); // si le noeud n'a pas reçu de données dans cet intervalle de temps, se désctive.
#ifdef MESH_FIX_ROOT
    ESP_ERROR_CHECK(esp_mesh_fix_root(1)); // Fixe le noeud root : aucune ré-élection de noeud n'aura pas lieu. ! Un noeud root DOIT etre défini dans ce mode.
#endif
    mesh_cfg_t cfg = MESH_INIT_CONFIG_DEFAULT(); // configuration par défaut du réseau Mesh.
    /* mesh ID */
    memcpy((uint8_t *) &cfg.mesh_id, MESH_ID, 6); // Remplace l'id par défaut par l'ID actuelle du réseau mesh.
    /* mesh event callback */
    cfg.event_cb = &mesh_event_handler; // event callback
    /* router */
    cfg.channel = CONFIG_MESH_CHANNEL; // id du réseau
    cfg.router.ssid_len = strlen(CONFIG_MESH_ROUTER_SSID); // longueur du ssid du reseau
    memcpy((uint8_t *) &cfg.router.ssid, CONFIG_MESH_ROUTER_SSID, cfg.router.ssid_len);
    memcpy((uint8_t *) &cfg.router.password, CONFIG_MESH_ROUTER_PASSWD,
           strlen(CONFIG_MESH_ROUTER_PASSWD));
    /* mesh softAP */
    ESP_ERROR_CHECK(esp_mesh_set_ap_authmode(CONFIG_MESH_AP_AUTHMODE));
    cfg.mesh_ap.max_connection = CONFIG_MESH_AP_CONNECTIONS;
    memcpy((uint8_t *) &cfg.mesh_ap.password, CONFIG_MESH_AP_PASSWD,
           strlen(CONFIG_MESH_AP_PASSWD));
    ESP_ERROR_CHECK(esp_mesh_set_config(&cfg)); // mets à jour la config du réseau mesh.
    /* Initialisation de l'adresse MAC*/
    esp_efuse_mac_get_default(my_mac);
    /* mesh start */
    ESP_ERROR_CHECK(esp_mesh_start());
    ESP_LOGI(MESH_TAG, "mesh starts successfully, heap:%d, %s\n",  esp_get_free_heap_size(),
             esp_mesh_is_root_fixed() ? "root fixed" : "root not fixed"); // log local
    /* Création du socket */
    memset(&tcpServerAddr, 0, sizeof(tcpServerAddr));
    tcpServerAddr.sin_family = AF_INET;
    tcpServerAddr.sin_addr.s_addr = inet_addr("10.0.0.1");
    tcpServerAddr.sin_len = sizeof(tcpServerAddr);
    tcpServerAddr.sin_port = htons(8081);
}
