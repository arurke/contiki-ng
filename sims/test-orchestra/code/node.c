#include "contiki.h"
#include "contiki-net.h"
#include "net/mac/tsch/tsch.h"
#include "lib/random.h"
#include "sys/node-id.h"

#include <inttypes.h>

// FYI: int-size on z1 is 2 bytes

/* Log configuration */
#include "sys/log.h"
#define LOG_MODULE "App"
#define LOG_LEVEL LOG_LEVEL_INFO

#define UDP_CLIENT_PORT   8765
#define UDP_SERVER_PORT   5678
#define ROOT_NODE_ID      1

// For native: If wanting to match the slotframe, the sending interval
// needs to be same as slotframe length - 1 tick (1 ms).
#ifdef SEND_INTERVAL_FACTOR
#define SEND_INTERVAL     ((uint16_t)((CLOCK_SECOND) * SEND_INTERVAL_FACTOR))
#elif SEND_CONF_INTERVAL
#define SEND_INTERVAL     ((uint16_t)SEND_CONF_INTERVAL)
#else
#define SEND_INTERVAL     ((uint16_t)(5 * CLOCK_SECOND))
#endif

#define NUM_PACKETS       1000
#define TIME_TO_START_TX  600 // Wait 10 min for convergence TODO

static struct simple_udp_connection udp_conn;
static bool is_coordinator = false;

/*---------------------------------------------------------------------------*/
PROCESS(app_process, "Application");
AUTOSTART_PROCESSES(&app_process);

/*---------------------------------------------------------------------------*/
static void
udp_rx_callback(struct simple_udp_connection *c,
         const uip_ipaddr_t *sender_addr,
         uint16_t sender_port,
         const uip_ipaddr_t *receiver_addr,
         uint16_t receiver_port,
         const uint8_t *data,
         uint16_t datalen)
{
  if(!is_coordinator) {
    LOG_ERR("Regular node rx\n");
    return;
  }

  uint64_t local_time_clock_ticks = tsch_get_network_uptime_ticks();

  LOG_INFO("Received data %.*s at ASN %"PRIu32" tick %"PRIu64" from ",
      datalen, (char *) data, tsch_current_asn.ls4b, local_time_clock_ticks);
  LOG_INFO_6ADDR(sender_addr);
  LOG_INFO_("\n");
}
/*---------------------------------------------------------------------------*/
PROCESS_THREAD(app_process, ev, data)
{
  static struct etimer periodic_timer;
  static unsigned count = 0;
  static char str[64];
  uip_ipaddr_t dest_ipaddr;

  PROCESS_BEGIN();

  is_coordinator = (node_id == ROOT_NODE_ID);

  if(is_coordinator) {
    /* Initialize DAG root. This also sets this node as TSCH coordinator */
    NETSTACK_ROUTING.root_start();

    /* Initialize server UDP connection */
    simple_udp_register(&udp_conn, UDP_SERVER_PORT, NULL,
                        UDP_CLIENT_PORT, udp_rx_callback);
  }
  else {
    /* Initialize client UDP connection */
    simple_udp_register(&udp_conn, UDP_CLIENT_PORT, NULL,
                        UDP_SERVER_PORT, NULL);

    // Schedule start of transmission
    clock_time_t delay =
        (TIME_TO_START_TX * CLOCK_SECOND) + (random_rand() % CLOCK_SECOND);
    etimer_set(
        &periodic_timer,
        delay);
    LOG_INFO("Node %u, ticks_in_sec %"PRIu32"," \
             " interval %"PRIu16", delay %"PRIu32"\n",
             node_id, CLOCK_SECOND, SEND_INTERVAL, delay);
  }

  while(!is_coordinator && count < NUM_PACKETS) {
    // Uncomment to make only the specified node send packets
//    if(node_id != 2) {
//      break;
//    }

    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));

    if(NETSTACK_ROUTING.node_is_reachable() &&
        NETSTACK_ROUTING.get_root_ipaddr(&dest_ipaddr)) {

      // Fetch current time in ticks
      uint64_t network_uptime = tsch_get_network_uptime_ticks();

      // Send to root
      // NOTE! The ASN may not be precise (not updated by TSCH at this point)
      LOG_INFO("Sending data num %u at ASN %"PRIu32" tick %"PRIu64" to ",
          count, tsch_current_asn.ls4b, network_uptime);
      LOG_INFO_6ADDR(&dest_ipaddr);
      LOG_INFO_("\n");
      snprintf(
          str,
          sizeof(str),
          "num %d oASN %"PRIu32" oTick %"PRIu64"",
          count, tsch_current_asn.ls4b, network_uptime);
      simple_udp_sendto(&udp_conn, str, strlen(str), &dest_ipaddr);
      count++;
    }
    else {
      LOG_ERR("No conn!\n");
      break;
    }

    // Minus one to align with slotframe
    // At least on native the timers is triggered 1 tick (1 ms) too late
    etimer_set(&periodic_timer, SEND_INTERVAL - 1);

    /* Add some jitter */
//    etimer_set(&periodic_timer, SEND_INTERVAL
//      - CLOCK_SECOND + (random_rand() % (2 * CLOCK_SECOND)));

  }

  if(!is_coordinator) {
    LOG_INFO("Done\n");
  }

  PROCESS_END();
}
/*---------------------------------------------------------------------------*/
