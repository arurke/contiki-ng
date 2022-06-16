#include "contiki.h"
#include "contiki-net.h"
#include "net/mac/tsch/tsch.h"
#include "lib/random.h"
#include "sys/node-id.h"
#if BUILD_WITH_LAYERED
#include "layered-conf.h"
#endif

#include <inttypes.h>

// FYI: ticks in CLOCK_SECOND on iotlab-m3 is 100

/* Log configuration */
#include "sys/log.h"
#define LOG_MODULE "App"
#define LOG_LEVEL LOG_LEVEL_INFO

#if !TESTBED
#define APP_CONF_NUM_PACKETS  100
#define APP_CONF_DELAY_TX     600
#endif

#define UDP_CLIENT_PORT   8765
#define UDP_SERVER_PORT   5678

#ifdef APP_CONF_ABORT_ON_TOPOLOGY_CHANGE
#define APP_ABORT_ON_TOPOLOGY_CHANGE  APP_CONF_ABORT_ON_TOPOLOGY_CHANGE
#else
#define APP_ABORT_ON_TOPOLOGY_CHANGE  0
#endif

// Time to wait before sending app packets
// Note that typically only the end of the app-packets are used in stats,
// so starting early is not a problem
#ifdef APP_CONF_DELAY_TX
#define APP_DELAY_TX      APP_CONF_DELAY_TX
#else
#define APP_DELAY_TX      360
#endif

// Number of packets. Typically we just send forever and let stats pick
#ifdef APP_CONF_NUM_PACKETS
#define APP_NUM_PACKETS   APP_CONF_NUM_PACKETS
#else
#define APP_NUM_PACKETS   2000000
#endif

#if TESTBED
#if BUILD_WITH_DEPLOYMENT
#define ROOT_NODE_ID      1 // Grenoble m3-358, 0x9378
#else
#define ROOT_NODE_ID      0x9378 // Grenoble m3-358, 0x9378
#endif /* BUILD_WITH_DEPLOYMENT */
#else
#define ROOT_NODE_ID      1
#endif

#if BUILD_WITH_DEPLOYMENT
#include "services/deployment/deployment.h"
// When changing num. nodes, remember to update scheduler configs
// such as orchestra max. hash.
const struct id_mac deployment_fit[] = {
  { 0x01, {{0x02,0x00,0x00,0x00,0x00,0x00,0x93,0x78}}}, // 358
  { 0x02, {{0x02,0x00,0x00,0x00,0x00,0x00,0xa6,0x81}}}, // 356
  { 0x03, {{0x02,0x00,0x00,0x00,0x00,0x00,0x93,0x67}}}, // 354
  { 0x04, {{0x02,0x00,0x00,0x00,0x00,0x00,0x97,0x81}}}, // 351
  { 0x05, {{0x02,0x00,0x00,0x00,0x00,0x00,0x98,0x68}}}, // 348
  { 0x06, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb6,0x69}}}, // 346
  { 0x07, {{0x02,0x00,0x00,0x00,0x00,0x00,0xc0,0x82}}}, // 344
  { 0x08, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb0,0x79}}}, // 342
  { 0x09, {{0x02,0x00,0x00,0x00,0x00,0x00,0xa4,0x79}}}, // 340
  { 0x0a, {{0x02,0x00,0x00,0x00,0x00,0x00,0x96,0x68}}}, // 338
  { 0x0b, {{0x02,0x00,0x00,0x00,0x00,0x00,0x94,0x68}}}, // 336
  { 0x0c, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb7,0x82}}}, // 334
  { 0x0d, {{0x02,0x00,0x00,0x00,0x00,0x00,0x85,0x78}}}, // 332
  { 0x0e, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb0,0x82}}}, // 330
  { 0x0f, {{0x02,0x00,0x00,0x00,0x00,0x00,0x92,0x82}}}, // 328
  { 0x10, {{0x02,0x00,0x00,0x00,0x00,0x00,0xa4,0x80}}}, // 326
  { 0,  {{0}}}
};
//const struct id_mac deployment_fit[] = {
//  { 0x01, {{0x02,0x00,0x00,0x00,0x00,0x00,0x96,0x82}}}, // 69
//  { 0x02, {{0x02,0x00,0x00,0x00,0x00,0x00,0xc2,0x68}}}, // 67
//  { 0x03, {{0x02,0x00,0x00,0x00,0x00,0x00,0x87,0x78}}}, // 65
//  { 0x04, {{0x02,0x00,0x00,0x00,0x00,0x00,0xa1,0x69}}}, // 63
//  { 0x05, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb6,0x78}}}, // 61
//  { 0x06, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb3,0x78}}}, // 58
//  { 0x07, {{0x02,0x00,0x00,0x00,0x00,0x00,0x86,0x77}}}, // 56
//  { 0x08, {{0x02,0x00,0x00,0x00,0x00,0x00,0xc1,0x80}}}, // 54
//  { 0x09, {{0x02,0x00,0x00,0x00,0x00,0x00,0x13,0x83}}}, // 52
//  { 0x0a, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb6,0x83}}}, // 49
//  { 0x0b, {{0x02,0x00,0x00,0x00,0x00,0x00,0x92,0x78}}}, // 46
//  { 0x0c, {{0x02,0x00,0x00,0x00,0x00,0x00,0xc1,0x81}}}, // 44
//  { 0x0d, {{0x02,0x00,0x00,0x00,0x00,0x00,0xa4,0x76}}}, // 42
//  { 0x0e, {{0x02,0x00,0x00,0x00,0x00,0x00,0xa9,0x78}}}, // 40
//  { 0x0f, {{0x02,0x00,0x00,0x00,0x00,0x00,0xa1,0x81}}}, // 38
//  { 0x10, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb5,0x68}}}, // 36
//  { 0,    {{0}}}
//};

//const struct id_mac deployment_fit[] = {
//  { 0x01, {{0x02,0x00,0x00,0x00,0x00,0x00,0x93,0x78}}}, // 358
//  { 0x02, {{0x02,0x00,0x00,0x00,0x00,0x00,0xa6,0x81}}}, // 356
//  { 0x03, {{0x02,0x00,0x00,0x00,0x00,0x00,0x93,0x67}}}, // 354
//  { 0x04, {{0x02,0x00,0x00,0x00,0x00,0x00,0x97,0x81}}}, // 351
//  { 0x05, {{0x02,0x00,0x00,0x00,0x00,0x00,0x98,0x68}}}, // 348
//  { 0x06, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb6,0x69}}}, // 346
//  { 0x07, {{0x02,0x00,0x00,0x00,0x00,0x00,0xc0,0x82}}}, // 344
//  { 0x08, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb0,0x79}}}, // 342
//  { 0x09, {{0x02,0x00,0x00,0x00,0x00,0x00,0xa4,0x79}}}, // 340
//  { 0x0a, {{0x02,0x00,0x00,0x00,0x00,0x00,0x96,0x68}}}, // 338
//  { 0x0b, {{0x02,0x00,0x00,0x00,0x00,0x00,0x94,0x68}}}, // 336
//  { 0x0c, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb7,0x82}}}, // 334
//  { 0x0d, {{0x02,0x00,0x00,0x00,0x00,0x00,0x85,0x78}}}, // 332
//  { 0x0e, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb0,0x82}}}, // 330
//  { 0x0f, {{0x02,0x00,0x00,0x00,0x00,0x00,0x92,0x82}}}, // 328
//  { 0x10, {{0x02,0x00,0x00,0x00,0x00,0x00,0xa4,0x80}}}, // 326
//  { 0x11, {{0x02,0x00,0x00,0x00,0x00,0x00,0xa7,0x82}}}, // 324
//  { 0x12, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb2,0x82}}}, // 322
//  { 0x13, {{0x02,0x00,0x00,0x00,0x00,0x00,0xa4,0x77}}}, // 320
//  { 0x14, {{0x02,0x00,0x00,0x00,0x00,0x00,0x83,0x70}}}, // 318
//  { 0x15, {{0x02,0x00,0x00,0x00,0x00,0x00,0x08,0x62}}}, // 316
//  { 0x16, {{0x02,0x00,0x00,0x00,0x00,0x00,0x95,0x80}}}, // 314
//  { 0x17, {{0x02,0x00,0x00,0x00,0x00,0x00,0x97,0x82}}}, // 312
//  { 0x18, {{0x02,0x00,0x00,0x00,0x00,0x00,0xc1,0x69}}}, // 310
//  { 0x19, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb0,0x83}}}, // 308
//  { 0,    {{0}}}
//};
#endif

// For native: If wanting to match the slotframe, the sending interval
// needs to be same as slotframe length - 1 tick (1 ms).
#ifdef SEND_INTERVAL_FACTOR
#define SEND_INTERVAL     ((uint16_t)((CLOCK_SECOND) * SEND_INTERVAL_FACTOR))
#elif SEND_CONF_INTERVAL
#define SEND_INTERVAL     ((uint16_t)SEND_CONF_INTERVAL)
#else
#define SEND_INTERVAL     ((uint16_t)(5 * CLOCK_SECOND))
#endif

#define PERIODIC_DEBUG_INTERVAL (CLOCK_SECOND * 30)

static struct simple_udp_connection udp_conn;
static bool is_coordinator = false;
static bool is_transmitting_node = true;
static struct ctimer ct_periodic_debug;

/*---------------------------------------------------------------------------*/
PROCESS(app_process, "Application");
AUTOSTART_PROCESSES(&app_process);
/*---------------------------------------------------------------------------*/
static void
periodic_debug() {
  rpl_print_neighbor_list();

  ctimer_set(&ct_periodic_debug,
             PERIODIC_DEBUG_INTERVAL,
             periodic_debug,
             NULL);
}

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

  LOG_INFO("RX data %.*s tick %"PRIu64" from ",
      datalen, (char *) data, local_time_clock_ticks);
  LOG_INFO_6ADDR(sender_addr);
  LOG_INFO_("\n");
}

static bool has_parent_changed(void) {
  static linkaddr_t previous_parent_linkaddr = {0};
  const linkaddr_t* new_parent_linkaddr = NULL;

  rpl_dag_t* rpl_dag = rpl_get_any_dag();

  if(rpl_dag != NULL) {
    new_parent_linkaddr = rpl_get_parent_lladdr(rpl_dag->preferred_parent);
  }

  // If we have no parent or not connected to a DAG
  if(new_parent_linkaddr == NULL) {
    // Was there no parent previously?
    if(linkaddr_cmp(&previous_parent_linkaddr, &linkaddr_null))  {
      return false;
    }
    else {
      linkaddr_copy(&previous_parent_linkaddr, &linkaddr_null);
      return true;
    }
  }

  // If we did not have a parent, set the new one as our parent
  if(linkaddr_cmp(&previous_parent_linkaddr, &linkaddr_null)) {
    linkaddr_copy(&previous_parent_linkaddr, new_parent_linkaddr);
  }

  if(linkaddr_cmp(&previous_parent_linkaddr, new_parent_linkaddr)) {
    return false;
  }
  else {
    linkaddr_copy(&previous_parent_linkaddr, new_parent_linkaddr);
    return true;
  }
}

static uint32_t transmission_start_spread(void) {
  // Spread transmissions across one interval
  return random_rand() % SEND_INTERVAL;
}

/*---------------------------------------------------------------------------*/
PROCESS_THREAD(app_process, ev, data)
{
  static struct etimer periodic_timer;
  static uint32_t packet_count = 0;
  static uint32_t packet_skipped = 0;
  static char tx_str[64];
  static uip_ipaddr_t dest_ipaddr;

  PROCESS_BEGIN();

  ctimer_set(&ct_periodic_debug,
             PERIODIC_DEBUG_INTERVAL,
             periodic_debug,
             NULL);

  if(node_id == ROOT_NODE_ID) {
    is_coordinator = true;
    is_transmitting_node = false;
  }

  // Uncomment to make only the specified node send packets
  // 326, 328, 330, 332
#if TESTBED
  if(node_id != 0x0d && node_id != 0x0e &&
      node_id != 0x0f && node_id != 0x10) {
    is_transmitting_node = false;
  }
#endif

  if(is_coordinator) {
    /* Initialize DAG root. This also sets this node as TSCH coordinator */
    NETSTACK_ROUTING.root_start();

    /* Initialize server UDP connection */
    simple_udp_register(&udp_conn, UDP_SERVER_PORT, NULL,
                        UDP_CLIENT_PORT, udp_rx_callback);
  }
  else if (is_transmitting_node){
    /* Initialize client UDP connection */
    simple_udp_register(&udp_conn, UDP_CLIENT_PORT, NULL,
                        UDP_SERVER_PORT, NULL);

    // Schedule start of transmission
    clock_time_t convergence_delay_ticks = (APP_DELAY_TX * CLOCK_SECOND);
    clock_time_t spread_delay_ticks = transmission_start_spread();

    etimer_set(&periodic_timer, convergence_delay_ticks + spread_delay_ticks);

    LOG_INFO("Node %u, ticks_in_sec %"PRIu32"," \
             " interval %"PRIu16", c-delay %"PRIu32", s-delay %"PRIu32"\n",
             node_id, (uint32_t)CLOCK_SECOND, SEND_INTERVAL,
             convergence_delay_ticks, spread_delay_ticks);
  }

  while(is_transmitting_node && packet_count < APP_NUM_PACKETS) {

    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));

    if(NETSTACK_ROUTING.node_is_reachable() &&
        NETSTACK_ROUTING.get_root_ipaddr(&dest_ipaddr)) {

      if(has_parent_changed()) {
        LOG_WARN("Parent switch\n");
#if APP_ABORT_ON_TOPOLOGY_CHANGE
        break;
#endif
      }

      // Fetch current time in ticks
      uint64_t network_uptime = tsch_get_network_uptime_ticks();

      uint16_t depth = 0;
      rpl_dag_t* rpl_dag = rpl_get_any_dag();
      if(rpl_dag != NULL) {
        depth = rpl_dag->depth;
      }

      // Send to root
      // NOTE! The ASN may not be precise (not updated by TSCH at this point)
      LOG_INFO("TX data num %lu tick %"PRIu64" to ",
               packet_count, network_uptime);
      LOG_INFO_6ADDR(&dest_ipaddr);
      LOG_INFO_(" from depth %u\n", depth);
      snprintf(
          tx_str,
          sizeof(tx_str),
          "num %04"PRIu32" oTick %09"PRIu64"",
          packet_count, network_uptime);
      simple_udp_sendto(&udp_conn, tx_str, strlen(tx_str), &dest_ipaddr);
      packet_count++;
    }
    else {
      if(packet_count == 0) {
        LOG_ERR("No conn!\n");
#if APP_ABORT_ON_NO_CONNECTION
        break;
#endif
      }
      else {
        LOG_ERR("Lost conn! Skipping packet!\n");
        packet_skipped++;
        packet_count++;
      }
    }

    // Minus one to align with slotframe
    // At least on native the timers is triggered 1 tick (1 ms) too late
    etimer_set(&periodic_timer, SEND_INTERVAL - 1);

    /* Add some jitter */
//    etimer_set(&periodic_timer, SEND_INTERVAL
//      - CLOCK_SECOND + (random_rand() % (2 * CLOCK_SECOND)));

  }

  while(is_coordinator) {
    LOG_INFO("Num routes at root: %d\n", uip_ds6_route_num_routes());
    etimer_set(&periodic_timer, CLOCK_SECOND * 30);
    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));
  }

  // Regular nodes which are not transmitting
  while(!is_coordinator && !is_transmitting_node) {
    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));

    if(has_parent_changed()) {
      LOG_WARN("Parent switch\n");
    }
    etimer_set(&periodic_timer, CLOCK_SECOND * 5);
  }

  // Application is done, write final state
  if(is_transmitting_node) {
    if(packet_count >= APP_NUM_PACKETS) {
        LOG_INFO("Done, sent %lu\n", packet_count - packet_skipped);
      }
  }
  else {
    LOG_INFO("Not a transmitting node\n");
  }

  PROCESS_END();
}
/*---------------------------------------------------------------------------*/
