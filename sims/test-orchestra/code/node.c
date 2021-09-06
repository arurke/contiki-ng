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

#define UDP_CLIENT_PORT   8765
#define UDP_SERVER_PORT   5678

#define ABORT_ON_TOPOLOGY_CHANGE  0

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
const struct id_mac deployment_fit[] = {
  { 2,  {{0x02,0x00,0x00,0x00,0x00,0x00,0x95,0x84}}}, // 203
  { 3,  {{0x02,0x00,0x00,0x00,0x00,0x00,0xb8,0x77}}}, // 204
  { 4,  {{0x02,0x00,0x00,0x00,0x00,0x00,0x91,0x83}}}, // 292
  { 5,  {{0x02,0x00,0x00,0x00,0x00,0x00,0x88,0x76}}}, // 300
  { 6,  {{0x02,0x00,0x00,0x00,0x00,0x00,0x97,0x82}}}, // 312
  { 7,  {{0x02,0x00,0x00,0x00,0x00,0x00,0x96,0x68}}}, // 338
  { 8,  {{0x02,0x00,0x00,0x00,0x00,0x00,0xb6,0x69}}}, // 346
  { 9,  {{0x02,0x00,0x00,0x00,0x00,0x00,0x93,0x67}}}, // 354
  { 10, {{0x02,0x00,0x00,0x00,0x00,0x00,0x85,0x69}}}, // 199
  { 11, {{0x02,0x00,0x00,0x00,0x00,0x00,0x94,0x67}}}, // 295
  { 12, {{0x02,0x00,0x00,0x00,0x00,0x00,0x88,0x77}}}, // 304
  { 13, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb0,0x83}}}, // 308
  { 14, {{0x02,0x00,0x00,0x00,0x00,0x00,0x08,0x62}}}, // 316
  { 15, {{0x02,0x00,0x00,0x00,0x00,0x00,0xa4,0x77}}}, // 320
  { 16, {{0x02,0x00,0x00,0x00,0x00,0x00,0xa4,0x80}}}, // 326
  { 17, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb0,0x82}}}, // 330
  { 18, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb7,0x82}}}, // 334
  { 19, {{0x02,0x00,0x00,0x00,0x00,0x00,0xb0,0x79}}}, // 342
  { 20, {{0x02,0x00,0x00,0x00,0x00,0x00,0x85,0x70}}}, // 350
  { 1,  {{0x02,0x00,0x00,0x00,0x00,0x00,0x93,0x78}}}, // 358
  { 0,  {{0}}}
};
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

#define NUM_PACKETS       100

// Time to wait before sending app packets
// 1800 (30 min) used for grid, 600 otherwise
#define TIME_TO_START_TX  1800

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

  // If there is no parent
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

  if(linkaddr_cmp(new_parent_linkaddr, &linkaddr_null)) {
    linkaddr_copy(&previous_parent_linkaddr, new_parent_linkaddr);
  }

  if(!linkaddr_cmp(&previous_parent_linkaddr, new_parent_linkaddr)) {
    return false;
  }

  return true;
}

/*---------------------------------------------------------------------------*/
PROCESS_THREAD(app_process, ev, data)
{
  static struct etimer periodic_timer;
  static unsigned count = 0;
  static char str[64];
  static bool application_success = true;
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
//  if(node_id != 8 && node_id != 2 &&
//      node_id != 9 && node_id != 10) {
//    is_transmitting_node = false;
//  }

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
    clock_time_t convergence_delay_ticks = (TIME_TO_START_TX * CLOCK_SECOND);
    uint32_t slotframe_duration_ms =
        (uint32_t)((uint32_t)SCHED_SLOTFRAME_LEN * \
        TSCH_DEFAULT_TIMESLOT_TIMING[tsch_ts_timeslot_length]) / 1000;
//    LOG_INFO("sizeof clock_time %u, sflen: %u. ts len: %u, sf dur ms: %lu\n",
//                 sizeof(clock_time_t), SCHED_SLOTFRAME_LEN,
//                 TSCH_DEFAULT_TIMESLOT_TIMING[tsch_ts_timeslot_length],
//                 slotframe_duration_ms);
    uint32_t random = random_rand();
    clock_time_t intra_slotframe_delay_ticks =
        ((random % slotframe_duration_ms) * CLOCK_SECOND) / 1000;
//    LOG_INFO("rand: %lu, rand_ticsk_times_ms: %lu, delay: %"PRIu32"\n",
//             (random),
//             ((random % slotframe_duration_ms) * CLOCK_SECOND) ,
//             intra_slotframe_delay_ticks);

    etimer_set(
        &periodic_timer,
        convergence_delay_ticks + intra_slotframe_delay_ticks);

    LOG_INFO("Node %u, ticks_in_sec %"PRIu32"," \
             " interval %"PRIu16", c-delay %"PRIu32", s-delay %"PRIu32"\n",
             node_id, (uint32_t)CLOCK_SECOND, SEND_INTERVAL, convergence_delay_ticks,
             intra_slotframe_delay_ticks);
  }

  while(is_transmitting_node && count < NUM_PACKETS) {

    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));

    if(NETSTACK_ROUTING.node_is_reachable() &&
        NETSTACK_ROUTING.get_root_ipaddr(&dest_ipaddr)) {

      if(has_parent_changed()) {
        LOG_WARN("Parent switch\n");
#if ABORT_ON_TOPOLOGY_CHANGE
        application_success = false;
        break;
#endif
      }

      // Fetch current time in ticks
      uint64_t network_uptime = tsch_get_network_uptime_ticks();

      // Send to root
      // NOTE! The ASN may not be precise (not updated by TSCH at this point)
      LOG_INFO("TX data num %u tick %"PRIu64" to ",
          count, network_uptime);
      LOG_INFO_6ADDR(&dest_ipaddr);
      LOG_INFO_("\n");
      snprintf(
          str,
          sizeof(str),
          "num %04d oTick %09"PRIu64"",
          count, network_uptime);
      simple_udp_sendto(&udp_conn, str, strlen(str), &dest_ipaddr);
      count++;
    }
    else {
      LOG_ERR("No conn!\n");
      application_success = false;
      break;
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

  if(is_transmitting_node) {
    if(application_success) {
        LOG_INFO("Done\n");
      }
  }
  else {
    LOG_INFO("Not a transmitting node\n");
  }


  PROCESS_END();
}
/*---------------------------------------------------------------------------*/
