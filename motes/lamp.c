/*
* AUTHORS: Antoine Andrieux & Thibaut Colson & Amine Djuric
* COURSE: LINGI2145 (INFO-Y118) Mobile and embedded computing
* DATE: 11/05/2021
*/

#include "contiki.h"
#include "lib/random.h"
#include "sys/ctimer.h"
#include "net/ipv6/uip.h"
#include "net/ipv6/uip-ds6.h"
#include "net/ipv6/uip-udp-packet.h"
#include "sys/ctimer.h"
#include "dev/leds.h"


#include <stdio.h>
#include <string.h>

#define UDP_CLIENT_PORT 8765
#define UDP_SERVER_PORT 5678

#define UDP_EXAMPLE_ID  190

#define DEBUG DEBUG_PRINT
#include "net/ipv6/uip-debug.h"

#define START_INTERVAL    (15 * CLOCK_SECOND)
#define SEND_INTERVAL   (60 * CLOCK_SECOND)
#define SEND_TIME   (random_rand() % (SEND_INTERVAL))
#define MAX_PAYLOAD_LEN   30

static struct uip_udp_conn *client_conn;
static uip_ipaddr_t server_ipaddr;

/*---------------------------------------------------------------------------*/
PROCESS(udp_client_process, "UDP client process");
AUTOSTART_PROCESSES(&udp_client_process);
/*---------------------------------------------------------------------------*/
static void tcpip_handler(void) {

  char* str;
  
  if(uip_newdata()) {

    str = uip_appdata;
    str[uip_datalen()] = '\0';    
    char tmp[uip_datalen()];

    int i;
    for(i = 0; i < uip_datalen(); ++i) {tmp[i] = str[i];}

    char* led_color;
    char* command;
    char* delimiter = "/";

    led_color = strtok(tmp, delimiter);
    command = strtok(NULL, delimiter);

    PRINTF("Lamp : %s/%s\n", led_color, command);

    // led/bbbb::c30c:0:0:2/red/on 
    // led/bbbb::c30c:0:0:2/green/on 
    // led/bbbb::c30c:0:0:2/blue/on 


    if(strcmp(led_color, "blue") == 0) { // check if they are the same
      if(strcmp(command,"on") == 0){
        leds_toggle(LEDS_YELLOW);
      } 
      else {
        leds_off(LEDS_YELLOW);
      }
    }

    else if(strcmp(led_color, "green") == 0) { 
      if(strcmp(command,"on") == 0){
        leds_toggle(LEDS_GREEN);
      } 
      else {
        leds_off(LEDS_GREEN);
      }
    }

    else if(strcmp(led_color, "red") == 0) {    
      if(strcmp(command,"on") == 0){
        leds_toggle(LEDS_RED);
      } 
      else {
        leds_off(LEDS_RED);
      }
    }
  }
}

/*---------------------------------------------------------------------------*/

static void send_packet(void *ptr) {
  
  char buf[MAX_PAYLOAD_LEN];  
  sprintf(buf, "Hi server, i'm a lamp");
  uip_udp_packet_sendto(client_conn, buf, strlen(buf), &server_ipaddr, UIP_HTONS(UDP_SERVER_PORT));

}

/*---------------------------------------------------------------------------*/

static void print_local_addresses(void) {
  int i;
  uint8_t state;

  PRINTF("Client IPv6 addresses: ");
  for(i = 0; i < UIP_DS6_ADDR_NB; i++) {
    state = uip_ds6_if.addr_list[i].state;
    if(uip_ds6_if.addr_list[i].isused &&
       (state == ADDR_TENTATIVE || state == ADDR_PREFERRED)) {
      PRINT6ADDR(&uip_ds6_if.addr_list[i].ipaddr);
      PRINTF("\n");
      /* hack to make address "final" */
      if (state == ADDR_TENTATIVE) {
        uip_ds6_if.addr_list[i].state = ADDR_PREFERRED;
      }
    }
  }
}
/*---------------------------------------------------------------------------*/
static void set_global_address(void) {
  uip_ipaddr_t ipaddr;

  uip_ip6addr(&ipaddr, 0xbbbb, 0, 0, 0, 0, 0, 0, 1);
  uip_ds6_set_addr_iid(&ipaddr, &uip_lladdr);
  uip_ds6_addr_add(&ipaddr, 0, ADDR_AUTOCONF);

  /* set server address */
  uip_ip6addr(&server_ipaddr, 0xbbbb, 0, 0, 0, 0, 0, 0, 1);

}
/*---------------------------------------------------------------------------*/
PROCESS_THREAD(udp_client_process, ev, data) {

  static struct etimer periodic;
  static struct ctimer backoff_timer;

  PROCESS_BEGIN();

  PROCESS_PAUSE();  

  set_global_address();

  PRINTF("UDP client process started\n");

  print_local_addresses();

  /* new connection with remote host */
  client_conn = udp_new(NULL, UIP_HTONS(UDP_SERVER_PORT), NULL);
  udp_bind(client_conn, UIP_HTONS(UDP_CLIENT_PORT));

  PRINTF("Created a connection with the server ");
  PRINT6ADDR(&client_conn->ripaddr);
  PRINTF(" local/remote port %u/%u\n", UIP_HTONS(client_conn->lport), UIP_HTONS(client_conn->rport));

  etimer_set(&periodic, SEND_INTERVAL);
  leds_off(LEDS_ALL);
  
  while(1) {
    PROCESS_YIELD();
    
    if(ev == tcpip_event) {
      tcpip_handler();
    }

    if(etimer_expired(&periodic)) {
      etimer_reset(&periodic);
      ctimer_set(&backoff_timer, SEND_TIME, send_packet, NULL);
    }
  }

  PROCESS_END();
}
/*---------------------------------------------------------------------------*/
