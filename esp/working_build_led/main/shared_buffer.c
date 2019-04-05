#include <stdint.h>
#include <pthread.h>
#include "mesh.h"
#include "shared_buffer.h"
#include "utils.h"


/* Communication buffer */
#define RXB_SIZE 50000
static uint8_t reception_buffer[RXB_SIZE]; // Reception pipe containing all received message
static int rxbuf_free_size = RXB_SIZE;
static int rxbuf_tail = 0;
static int rxbuf_head = 0;
static pthread_mutex_t rxbuf_write = PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t rxbuf_read = PTHREAD_MUTEX_INITIALIZER;

#define TXB_SIZE 50000
static uint8_t transmission_buffer[TXB_SIZE]; // Transmission pipe containing messages to be send
static int txbuf_free_size = TXB_SIZE;
static int txbuf_head = 0;
static pthread_mutex_t txbuf_write = PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t txbuf_read = PTHREAD_MUTEX_INITIALIZER;

void write_rxbuffer(uint8_t * data, uint16_t size){
 loop:
    while (rxbuf_free_size < size );
    pthread_mutex_lock(&rxbuf_read);
    if (rxbuf_free_size < size ){
	pthread_mutex_unlock(&rxbuf_read);
	goto loop;
    }
    pthread_mutex_lock(&rxbuf_write);
    rxbuf_free_size = rxbuf_free_size - size;
    rxbuf_head = (rxbuf_head + size) % RXB_SIZE;
    pthread_mutex_unlock(&rxbuf_write);
    for(int i = 0; i < size; i++){
	reception_buffer[(head + i) % RXB_SIZE] = data[i];
    }
    pthread_mutex_unlock(&rxbuf_read);
}

int write_txbuffer(uint8_t * data, uint16_t size){
 looptx:
    while (txbuf_free_size < size );
    pthread_mutex_lock(&txbuf_read);
    if (txbuf_free_size < size ){
	pthread_mutex_unlock(&txbuf_read);
	goto looptx;
    }
    pthread_mutex_lock(&txbuf_write);
    txbuf_free_size = txbuf_free_size - size;
    int head = txbuf_head;
    txbuf_head = (txbuf_head + size) % TXB_SIZE;
    pthread_mutex_unlock(&txbuf_write);
    for(int i = 0; i < size; i++) {
	transmission_buffer[(head + i) % TXB_SIZE] = data[i];
    }
    pthread_mutex_unlock(&txbuf_read);
    return head;
}

void read_rxbuffer(uint8_t * data) {
    pthread_mutex_lock(&rxbuf_read);
    if (rxbuf_free_size != RXB_SIZE) {
	int type = get_size(reception_buffer[(rxbuf_tail+TYPE) % RXB_SIZE]);
	for (int i = 0; i < type; i++) {
	    data[i] = reception_buffer[(rxbuf_tail + i) % RXB_SIZE];
	}
	rxbuf_tail = (rxbuf_tail + type) % RXB_SIZE;
	rxbuf_free_size = rxbuf_free_size + type;
    } else {
	pthread_mutex_unlock(&rxbuf_read);
	data[TYPE] = -2;
	return;
    }
    pthread_mutex_unlock(&rxbuf_read);
}

void read_txbuffer(uint8_t * data, int head){
    pthread_mutex_lock(&txbuf_read);
    for (int i = 0; i < FRAME_SIZE; i++) {
	data[i] = transmission_buffer[(head + i) % TXB_SIZE];
    }
    txbuf_free_size = txbuf_free_size + FRAME_SIZE;
    pthread_mutex_unlock(&txbuf_read);
}
