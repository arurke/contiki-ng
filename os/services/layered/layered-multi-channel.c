#include "contiki.h"
#include "layered.h"
#include "net/ipv6/uip-ds6-route.h"
#include "net/packetbuf.h"
#include "net/routing/routing.h"
#include "sys/node-id.h"
#include "rpl.h"
#include "rpl-private.h"
#include "uip-icmp6.h"
#include "lib/random.h"
#include <inttypes.h>

#include "sys/log.h"
#define LOG_MODULE "Layered"
#define LOG_LEVEL LOG_LEVEL_INFO

/*
 * The body of this rule should be compiled only when "nbr_routes" is available,
 * otherwise a link error causes build failure. "nbr_routes" is compiled if
 * UIP_MAX_ROUTES != 0. See uip-ds6-route.c.
 */
#if UIP_MAX_ROUTES != 0

typedef struct {
  uint16_t node_depth;
  uint8_t node_layer;
  uint16_t child_depth;
  uint8_t child_layer;
} layered_status_t;


static layered_status_t current_status = {
    .node_depth = 0xffff,
    .node_layer = 0xff,
    .child_depth = 0xffff,
    .child_layer = 0xff,
};

static uint16_t slotframe_handle = 0;
static struct tsch_slotframe *sf_layered;

#define COMMON_CELL_CHANNEL   1
#define NUM_CHANNELS          LAYERED_NUM_CHANNELS
#define CHANNELS              LAYERED_CHANNELS
// Avoid channel 0 due to stats not supporting it.
static uint8_t channels[NUM_CHANNELS] = CHANNELS;

// For gruesome RPL heuristics
#define SIXLO_NEXT_HEADER_OFFSET  2
#define SIXLO_NEXT_HEADER_LEN     3
#define ICMP_TYPE_OFFSET          0
#define ICMP_CODE_OFFSET          1
#define RPL_INSTANCE_ID_OFFSET    4

// For gruesome source addr heuristics
#define HOP_LIMIT_MASK            0x03
#define SIXLO_HEADER_PART2_OFFSET 1
#define SRC_ADDR_MODE_MASK        0x30
#define SRC_ADDR_OFFSET           3

#define FIRST_COMMON_SLOT         (COMMON_SLOT_SPACING - 1)

#if LAYERED_STATS
#define STATS_NUM_LINKS   40
typedef struct {
  uint16_t timeslot;
  uint16_t channel;
  uint8_t options;
  bool active;
  uint32_t tx_attempts;
  uint32_t no_ok_mac;
} layered_stats_t;

static layered_stats_t layered_stats[STATS_NUM_LINKS] = {{0}};
static uint32_t unknown_stats = 0;

void layered_stats_update(struct tsch_neighbor *n, struct tsch_packet *p,
                          struct tsch_link *link, uint8_t channel_offset,
                          uint8_t mac_tx_status) {

  // (channel offset in link cannot be trusted when TSCH_WITH_LINK_SELECTOR)
  for(int i = 0; i < STATS_NUM_LINKS; i++) {
    if(layered_stats[i].timeslot == link->timeslot &&
        layered_stats[i].channel == channel_offset) {

      layered_stats[i].tx_attempts++;

      if(mac_tx_status != MAC_TX_OK) {
        layered_stats[i].no_ok_mac++;
      }

      return;
    }
  }
  unknown_stats++;
}

void layered_print_stats() {
  tsch_schedule_print();

  LOG_INFO("Printing stats:\n");
  int i = 0;
  uint8_t num_links = 0;
  for(i = 0; i < STATS_NUM_LINKS; i++) {
    if(layered_stats[i].timeslot != 0 &&
        layered_stats[i].channel != 0) {

      num_links++;

      if(layered_stats[i].options & LINK_OPTION_SHARED) {
        LOG_INFO("BC: ");
      }
      else {
        LOG_INFO("UC: ");
      }
      LOG_INFO_("TS/CH %" PRIu16 "/%" PRIu16 ": %" PRIu32 " attempts, " \
               " %" PRIu32 " no OK status",
               layered_stats[i].timeslot,
               layered_stats[i].channel,
               layered_stats[i].tx_attempts,
               layered_stats[i].no_ok_mac);
      LOG_INFO_("%s\n", layered_stats[i].active ? "" : " - inactive");
    }
  }

  LOG_INFO("Num links: %" PRIu8 "\n", num_links);

  if(unknown_stats != 0) {
    LOG_ERR("Unknown stats %" PRIu32 "\n", unknown_stats);
  }
}

static void stats_add_link(
    uint16_t timeslot, uint16_t channel, uint8_t options) {
  for(int i = 0; i < STATS_NUM_LINKS; i++) {
    if(layered_stats[i].timeslot == timeslot &&
           layered_stats[i].channel == channel) {
      layered_stats[i].options = options;
      layered_stats[i].active = true;
      // Already exists;
      return;
    }

    if(layered_stats[i].timeslot == 0 &&
        layered_stats[i].channel == 0) {
      layered_stats[i].timeslot = timeslot;
      layered_stats[i].channel = channel;
      layered_stats[i].options = options;
      layered_stats[i].active = true;
      return;
    }
  }
  LOG_ERR("Stats is full!\n");
}

static void stats_deactivate_link(
    uint16_t timeslot, uint16_t channel) {
  for(int i = 0; i < STATS_NUM_LINKS; i++) {
    if(layered_stats[i].timeslot == timeslot &&
           layered_stats[i].channel == channel) {
      layered_stats[i].active = false;
      return;
    }
  }
}
#endif /* LAYERED_STATS */

static uint16_t
get_node_timeslot(const linkaddr_t *addr)
{
  if(addr != NULL && LAYERED_MAX_NUM_NODES > 0) {
    return LAYERED_LINKADDR_HASH(addr) % LAYERED_MAX_NUM_NODES;
  } else {
    return 0xffff;
  }
}

static uint16_t calculate_next_common_slot(void) {
  // Select common slot at random to ensure uniform distribution
  // Experience shows ASN method below produced too much grouping
  uint8_t random_common = random_rand() % NUM_COMMON_SLOTS;
  uint8_t common = (random_common * COMMON_SLOT_SPACING) + FIRST_COMMON_SLOT;
  //LOG_DBG("Common %u\n", common);
  return common;

//  // TODO No guarantee that ASN is updated at this point, but this is
//  // just RPL traffic so any delays should be fine
//  uint16_t current_ts = (tsch_current_asn.ls4b % LAYERED_SF_LEN);
//
//  for(uint16_t i = FIRST_COMMON_SLOT;
//      i<LAYERED_SF_LEN;
//      i+=COMMON_SLOT_SPACING) {
//    if(current_ts < i) {
//      return i;
//    }
//  }
//  return FIRST_COMMON_SLOT;
}

/*---------------------------------------------------------------------------*/
static uint16_t
calculate_channel(uint8_t depth)
{
  // Treat root as on depth 1
  if(depth == 0) {
    depth = 1;
  }

  // -1 for arithmetic simplicity such that bottom is 0
  uint16_t channel = ((depth-1) / LAYERED_NUM_LAYERS) % NUM_CHANNELS;

  // Fetch actual channel from
  channel = channels[channel];

//  LOG_INFO("Channel %u at depth %u\n", channel, depth++);
  return channel;
}
/*---------------------------------------------------------------------------*/

// Find if packet is RPL by analyzing packet
static bool is_rpl_packet_heuristic(void) {
  uint8_t* data = packetbuf_dataptr();

  if(packetbuf_datalen() < 7) {
//    LOG_DBG("Too short for RPL\n");
    return false;
  }

  uint8_t sixlo_nh_len = SIXLO_NEXT_HEADER_LEN;

  // 6LoWPAN IPHC next-header field is 0x3a for ICMPv6
  if(*(data + SIXLO_NEXT_HEADER_OFFSET) != 0x3a) {
    return false;
  }

  // ICMP type, 0x9b is RPL
  if(*(data + sixlo_nh_len + ICMP_TYPE_OFFSET) != 0x9b) {
    // If it was a DIO or DIS, there is one extra byte in the 6lowpan header
    // for IPv6 dest addr. So lets check that offset as well
    sixlo_nh_len++;
    if(*(data + sixlo_nh_len + ICMP_TYPE_OFFSET) != 0x9b) {
      // no luck
      return false;
    }
  }

  // ICMP code, all RPL is below 0x8b
  if(*(data + sixlo_nh_len + ICMP_CODE_OFFSET) >= 0x8a) {
//    LOG_DBG("Byte %u 0x%02x\n", ICMP_CODE_OFFSET, *(data + 4));
    return false;
  }

  // RPL instance ID 0x1e (30)
  // This is not present in DIS, so let's just skip it
//  if(*(data + sixlo_nh_len + RPL_INSTANCE_ID_OFFSET) != 0x1e) {
////    LOG_DBG("Byte %u 0x%02x\n", RPL_INSTANCE_ID_OFFSET, *(data + 7));
//    return false;
//  }

  return true;
}

// Find if packet is RPL by analyzing packetbuf
// TODO The attrs are not populated at the time we are called
//static bool is_rpl_packet_via_packetbuf(void) {
//  // For some reason, the OS stores protocol and type field in strange packetbuf-attrs
//  // Inspired by orchestra_packet_sent()
//  uint8_t protocol = packetbuf_attr(PACKETBUF_ATTR_NETWORK_ID);
//  uint8_t icmp_type = (packetbuf_attr(PACKETBUF_ATTR_CHANNEL) >> 8) && 0x000000ff;
//
//  LOG_DBG("Packet protocol: %u, type: %u\n", protocol, icmp_type);
//
//  if(protocol == UIP_PROTO_ICMP6 && icmp_type == ICMP6_RPL) {
//    return true;
//  }
//  return false;
//}

static bool is_rpl_packet(void) {
//  return is_rpl_packet_via_packetbuf();
  return is_rpl_packet_heuristic();
}

static bool heuristic_is_keepalive(void) {
  // Keep-alives are empty packets (only MAC headers)
  return packetbuf_datalen() == 0;
}

static uint16_t
calculate_layered_timeslot(const linkaddr_t *linkaddr, uint16_t layer) {
  // Hash of node id
  uint16_t timeslot = get_node_timeslot(linkaddr);

  if(timeslot == 0xffff) {
    LOG_ERR("TEST FAILED invalid timeslot\n");
    // Return a common slot
    return calculate_next_common_slot();
  }

  // TODO Because timeslots are 0-indexed
  timeslot--;

  // Shift right into correct layer
  timeslot += (LAYERED_NUM_LAYERS - layer) * LAYERED_MAX_NUM_NODES;

  // Shift to accommodate any common slots. -1 due to ts being 0-index
  uint16_t num_common_slots_so_far = timeslot / (COMMON_SLOT_SPACING - 1);
  timeslot += num_common_slots_so_far;

  return timeslot;
}

static bool
find_source_address(linkaddr_t* source_lladdr) {
  // Use a really bad way to figure out if the originating node address
  // For some reason PACKETBUF_ADDR_SENDER contain our own address
  uint8_t* data = packetbuf_dataptr();

  if(packetbuf_datalen() < 12) {
    LOG_ERR("Too short for source address!\n");
    return false;
  }

  // Is source address compressed? If yes, we are transmitting
  if(((*(data + SIXLO_HEADER_PART2_OFFSET)) & SRC_ADDR_MODE_MASK) == 0x30) {
    memcpy(source_lladdr,
           packetbuf_addr(PACKETBUF_ADDR_SENDER),
           sizeof(linkaddr_t));
//    LOG_INFO("We are sending, header: 0x%02x\n", (*(data + 1)));
    return true;
  }

  uint8_t src_addr_offset = SRC_ADDR_OFFSET;

  // Has inline hop limit? This moves the source addr one byte
  if(((*data) & HOP_LIMIT_MASK) == 0) {
    src_addr_offset++;
//    LOG_INFO("inline hoplimit\n");
  }

  linkaddr_t* fetched_source_address = (linkaddr_t*)(data + src_addr_offset);

  // Create an ipaddr and fill the interface id from the buf
  uip_ipaddr_t ipaddr = {0};
  memcpy(ipaddr.u8 + 8, fetched_source_address->u8, LINKADDR_SIZE);

  // Use ds6 to properly decode lladdr from IP.
  uip_ds6_set_lladdr_from_iid((uip_lladdr_t*) source_lladdr, &ipaddr);

  LOG_DBG("Found node ");
  LOG_DBG_LLADDR(source_lladdr);
  LOG_DBG_("\n");

  return true;
}

/*---------------------------------------------------------------------------*/
static int
select_packet(uint16_t *slotframe, uint16_t *timeslot, uint16_t *channel_offset)
{
  if(packetbuf_attr(PACKETBUF_ATTR_FRAME_TYPE) == FRAME802154_BEACONFRAME) {
    // Use the downward TX slot for beacons
    if(slotframe != NULL) {
      *slotframe = slotframe_handle;
    }
    if(timeslot != NULL) {
      // Our own address, but for layer below us
      *timeslot = calculate_layered_timeslot(&linkaddr_node_addr, current_status.child_layer);
    }
    if(channel_offset != NULL) {
      // For depth below us
      *channel_offset = calculate_channel(current_status.child_depth);
    }
    LOG_DBG("Selected %u/%u for beacon\n", *timeslot, *channel_offset);
    return 1;
  }

  // If a RPL packet, send in common
  if(is_rpl_packet()) {

    if(slotframe != NULL) {
      *slotframe = slotframe_handle;
    }
    if(timeslot != NULL) {
      *timeslot = calculate_next_common_slot();
    }
    if(channel_offset != NULL) {
      *channel_offset = COMMON_CELL_CHANNEL;
    }
    LOG_DBG("Selected %u/%u for RPL packet\n", *timeslot, *channel_offset);
    return 1;
  }

  // If a TSCH keepalive, send it in the common slot
  if(heuristic_is_keepalive()) {
    //LOG_INFO("This was a keepalive packet\n");

    if(slotframe != NULL) {
      *slotframe = slotframe_handle;
    }
    if(timeslot != NULL) {
      *timeslot = calculate_next_common_slot();
    }
    if(channel_offset != NULL) {
      *channel_offset = COMMON_CELL_CHANNEL;
    }
    LOG_DBG("Selected %u/%u for KA packet\n", *timeslot, *channel_offset);
    return 1;
  }

  // It was neither beacon or RPL. So then we assume it is application
  // let's find the originating node such that we can assign it to its
  // correct cell
  linkaddr_t source_lladdr = {{0}};
  if(!find_source_address(&source_lladdr)) {
    // Unable to find the source address, this should not happen
    LOG_ERR("TEST FAILED %u\n", packetbuf_datalen());
    return 1;
  }

//  LOG_DBG("App packet originated from: ");
//  LOG_DBG_LLADDR(&source_lladdr);
//  LOG_DBG_("\n");

  if(slotframe != NULL) {
    *slotframe = slotframe_handle;
  }
  if(timeslot != NULL) {
    *timeslot = calculate_layered_timeslot(&source_lladdr, current_status.node_layer);
  }
  if(channel_offset != NULL) {
    *channel_offset = calculate_channel(current_status.node_depth);
  }
  LOG_DBG("Selected %u/%u for App packet originating from ",
           *timeslot, *channel_offset);
  LOG_DBG_LLADDR(&source_lladdr);
  LOG_DBG_("\n");

  return 1;
}
/*---------------------------------------------------------------------------*/
static void
new_time_source(const struct tsch_neighbor *old, const struct tsch_neighbor *new)
{
  LOG_INFO("New time source ");
  LOG_INFO_LLADDR(tsch_queue_get_nbr_address(new));
  LOG_INFO_(". Add an rx cell here?\n"); //TODO
  LOG_INFO("ASN now is %"PRIu32" so TS should be %lu\n",
           tsch_current_asn.ls4b, (tsch_current_asn.ls4b % LAYERED_SF_LEN));
  LOG_INFO("asn-%x.%lx\n", tsch_current_asn.ms1b, tsch_current_asn.ls4b);
}

static bool
is_root(void) {
  // Note that this might not show correct until after app. has started
  return NETSTACK_ROUTING.node_is_root();
}

static bool cell_already_there(uint16_t timeslot, uint16_t channel,
                               uint8_t link_options, enum link_type link_type) {

  struct tsch_link * curr = tsch_schedule_get_link_by_timeslot(sf_layered, timeslot, channel);

  if(curr != NULL &&
      curr->channel_offset == channel &&
      curr->link_options == link_options &&
      curr->link_type == link_type) {
    return true;
  }

  return false;
}

static void
schedule_upwards_tx_cell(
    const linkaddr_t *linkaddr, uint8_t layer, uint8_t depth, bool remove) {
  uint8_t link_options = LINK_OPTION_TX;
  uint16_t timeslot = calculate_layered_timeslot(linkaddr, layer);
  uint16_t channel = calculate_channel(depth);

  // TODO this stopped DAO from propagating, so currently broadcast is set
  rpl_dag_t* rpl_dag = rpl_get_any_dag();
  const linkaddr_t* parent_linkaddr =
      rpl_get_parent_lladdr(rpl_dag->preferred_parent);

#if LAYERED_STATS
  if(remove) {
    stats_deactivate_link(timeslot, channel);
  }
  else {
    stats_add_link(timeslot, channel, link_options);
  }
#endif

  if(remove) {
    LOG_INFO("Removing upwards TX cell %u/%u to ", timeslot, channel);
    LOG_INFO_LLADDR(parent_linkaddr);
    LOG_INFO_(" for traffic from ");
    LOG_INFO_LLADDR(linkaddr);
    LOG_INFO_("\n");
    struct tsch_link* link_to_remove =
        tsch_schedule_get_link_by_timeslot(sf_layered, timeslot, channel);
    // TODO add error-handling
    tsch_schedule_remove_link(sf_layered, link_to_remove);
  }
  else {
    if(!cell_already_there(timeslot, channel, link_options, LINK_TYPE_NORMAL)) {
      LOG_INFO("Adding upwards TX cell %u/%u to ", timeslot, channel);
      LOG_INFO_LLADDR(parent_linkaddr);
      LOG_INFO_(" for traffic from ");
      LOG_INFO_LLADDR(linkaddr);
      LOG_INFO_("\n");
      tsch_schedule_add_link(sf_layered, link_options, LINK_TYPE_NORMAL,
                             &tsch_broadcast_address, timeslot, channel, 1);
    }
  }
}

static void
schedule_upwards_rx_cell(
    const linkaddr_t *linkaddr, uint8_t layer, uint8_t depth, bool remove) {
  uint8_t link_options = LINK_OPTION_RX;
  uint16_t timeslot = calculate_layered_timeslot(linkaddr, layer);
  uint16_t channel = calculate_channel(depth);

  // Don't add stats for RX cells
//#if LAYERED_STATS
//  stats_add_link(timeslot, channel);
//#endif

  // We set broadcast as the "destination address",
  // but since this is a RX cell the value is probably ignored TODO
  if(remove) {
    LOG_INFO("Removing upwards RX cell %u/%u for traffic from ",
             timeslot, channel);
    LOG_INFO_LLADDR(linkaddr);
    LOG_INFO_("\n");
    struct tsch_link* link_to_remove =
        tsch_schedule_get_link_by_timeslot(sf_layered, timeslot, channel);
    tsch_schedule_remove_link(sf_layered, link_to_remove);
  }
  else {
    if(!cell_already_there(timeslot, channel, link_options, LINK_TYPE_NORMAL)) {
      LOG_INFO("Adding upwards RX cell %u/%u for traffic from ",
               timeslot, channel);
      LOG_INFO_LLADDR(linkaddr);
      LOG_INFO_("\n");
      tsch_schedule_add_link(sf_layered, link_options, LINK_TYPE_NORMAL,
                             &tsch_broadcast_address, timeslot, channel, 1);
    }
  }
}

static void
schedule_downwards_tx_cell(
    const linkaddr_t *linkaddr, uint8_t layer, uint8_t depth, bool remove) {
  uint8_t link_options = LINK_OPTION_TX;
  uint16_t timeslot = calculate_layered_timeslot(linkaddr, layer);
  uint16_t channel = calculate_channel(depth);

#if LAYERED_STATS
  if(remove) {
    stats_deactivate_link(timeslot, channel);
  }
  else {
    stats_add_link(timeslot, channel, link_options);
  }
#endif

  // Allow all kinds of destinations (including broadcast)
  // TODO we limit these to beacons to avoid it being selected by the
  // application data. Proper solution is to implement select_packet()
  // How does orchestra avoid RPL packet going into the "application-cells"?
  if(remove) {
    LOG_INFO("Removing downwards TX cell %u/%u\n", timeslot, channel);
    struct tsch_link* link_to_remove =
        tsch_schedule_get_link_by_timeslot(sf_layered, timeslot, channel);
    tsch_schedule_remove_link(sf_layered, link_to_remove);
  }
  else {
    if(!cell_already_there(timeslot, channel, link_options, LINK_TYPE_ADVERTISING_ONLY)) {
      LOG_INFO("Adding downwards TX cell %u/%u\n", timeslot, channel);
      tsch_schedule_add_link(sf_layered, link_options,
                             LINK_TYPE_ADVERTISING_ONLY,
                             &tsch_broadcast_address, timeslot, channel, 1);
    }
  }
}

static void
schedule_downwards_rx_cell(
    const linkaddr_t *linkaddr, uint8_t layer, uint8_t depth, bool remove) {
  uint8_t link_options = LINK_OPTION_RX;
  uint16_t timeslot = calculate_layered_timeslot(linkaddr, layer);
  uint16_t channel = calculate_channel(depth);

  // Don't add stats for RX cells
//#if LAYERED_STATS
//  stats_add_link(timeslot, channel);
//#endif

  // Allow all kinds of destinations (including broadcast)
  // TODO we limit these to beacons to avoid it being selected by the
  // application data. Proper solution is to implement select_packet()
  if(remove) {
    LOG_INFO("Removing downwards RX cell %u/%u\n", timeslot, channel);
    struct tsch_link* link_to_remove =
        tsch_schedule_get_link_by_timeslot(sf_layered, timeslot, channel);
    tsch_schedule_remove_link(sf_layered, link_to_remove);
  }
  else {
    if(!cell_already_there(timeslot, channel, link_options, LINK_TYPE_ADVERTISING_ONLY)) {
      LOG_INFO("Adding downwards RX cell %u/%u\n", timeslot, channel);
      tsch_schedule_add_link(sf_layered, link_options,
                             LINK_TYPE_ADVERTISING_ONLY,
                             &tsch_broadcast_address, timeslot, channel, 1);
    }
  }
}

static void schedule_common_cells(void) {
  // Add common cells used for RPL and downward application traffic
  for(uint16_t i = FIRST_COMMON_SLOT;
      i < LAYERED_SF_LEN;
      i += COMMON_SLOT_SPACING) {

    uint16_t timeslot = i;
    uint16_t channel = COMMON_CELL_CHANNEL;
    uint8_t options = LINK_OPTION_RX | LINK_OPTION_TX | LINK_OPTION_SHARED;

    LOG_INFO("Adding common cell %u/%u\n", timeslot, channel);

#if LAYERED_STATS
    stats_add_link(timeslot, channel, options);
#endif

    tsch_schedule_add_link(sf_layered, options, LINK_TYPE_NORMAL,
                           &tsch_broadcast_address, i, channel, 1);
  }
}

// TODO NOTE! This does not use same notation as in paper,
// here we have the most lowered-number layer closest to the sink
static uint8_t calculate_layer(uint16_t depth) {
  // Treat the root as on layer 1
  if(depth == 0) {
    depth = 1;
  }

  // For arithmetic simplicity
  depth--;

  // Calc layer (0 or 1)
  uint8_t layer = depth % LAYERED_NUM_LAYERS;

  // And back to layer 1 and 2
  layer++;

  return layer;
}

static void
add_cells(const linkaddr_t *linkaddr, layered_status_t* status, bool default_route) {
  if(linkaddr == NULL) {
    LOG_ERR("linkaddr NULL!\n");
    return;
  }

  LOG_INFO("Scheduling cells (node/child depth %u/%u, layer %u/%u)\n",
           status->node_depth, status->child_depth, status->node_layer, status->child_layer);

  // Receive traffic forwarded by our child
  // The originating node (could be the child) is indicated in linkaddr, and
  // The layer and depth would be the one below our own
  // This cell is not necessary if this was the default-route, i.e.
  // the originating node would be ourself
  if(!default_route) {
    schedule_upwards_rx_cell(linkaddr, status->child_layer, status->child_depth, false);
  }

  // Forward upward traffic originated at the node indicated by the linkaddr
  // The layer is our own
  // Not needed if we are root
  if(!is_root()) {
    // If it was a default route we are the originating node,
    // use our address and depth
    if(default_route) {
      schedule_upwards_tx_cell(
          &linkaddr_node_addr, status->node_layer, status->node_depth, false);
    }
    else {
      schedule_upwards_tx_cell(linkaddr, status->node_layer, status->node_depth, false);
    }
  }

  // Send beacons to our childs
  // Use our own addr, but at the layer and depth below us
  if(default_route) {
    schedule_downwards_tx_cell(&linkaddr_node_addr, status->child_layer, status->child_depth, false);
  }

  // Receive beacons from parent
  // This should follow our parent address, yet our layer and depth
  // It is not necessary if we are root
  if(default_route && !is_root()) {
    schedule_downwards_rx_cell(linkaddr, status->node_layer, status->node_depth, false);
  }
}

static void
remove_cells(const linkaddr_t *linkaddr, layered_status_t* status, bool default_route) {
  if(linkaddr == NULL) {
    LOG_ERR("linkaddr NULL!\n");
    return;
  }

  LOG_INFO("Removing cells (node/child depth %u/%u, layer %u/%u)\n",
           status->node_depth, status->child_depth, status->node_layer, status->child_layer);

  // We will no longer receive traffic forwarded by our child
  // The originating node (could be the child) is indicated in linkaddr, and
  // The layer and depth would be the one below our own
  // This cell is not necessary if this was the default-route, i.e.
  // the originating node would be ourself
  if(!default_route) {
    schedule_upwards_rx_cell(linkaddr, status->child_layer, status->child_depth, true);
  }

  // No longer forward upward traffic originated at the node indicated by linkaddr
  // The layer is our own
  // Not needed if we are root
  if(!is_root()) {
    // If it was a default route we are the originating node,
    // use our address and depth
    if(default_route) {
      schedule_upwards_tx_cell(
          &linkaddr_node_addr, status->node_layer, status->node_depth, true);
    }
    else {
      schedule_upwards_tx_cell(linkaddr, status->node_layer, status->node_depth, true);
    }
  }

  // No longer send beacons to our childs since we might have moved
  // Use our own addr, but at the layer and depth below us
  // This is not necessary if we have no childs (except if we are root)
  if(default_route) {
    schedule_downwards_tx_cell(
        &linkaddr_node_addr, status->child_layer, status->child_depth, true);
  }

  // No longer receive beacons from this parent
  // This should follow our parent address, yet our layer and depth
  // It is not necessary if we are root
  if(default_route && !is_root()) {
    schedule_downwards_rx_cell(linkaddr, status->node_layer, status->node_depth, true);
  }
}

static void update_current_status(uint16_t node_new_depth) {
  if(node_new_depth != current_status.node_depth) {
    LOG_INFO("Node switched depth from %u to %u\n",
             current_status.node_depth, node_new_depth);
    current_status.node_depth = node_new_depth;
  }

  uint8_t node_new_layer = calculate_layer(current_status.node_depth);
  if(node_new_layer != current_status.node_layer) {
    LOG_INFO("Node switched layer from %u to %u\n",
             current_status.node_layer, node_new_layer);
    current_status.node_layer = node_new_layer;
  }

  uint8_t child_new_depth = node_new_depth + 1;
  if(child_new_depth != current_status.child_depth) {
    LOG_INFO("Child switched depth from %u to %u\n",
             current_status.child_depth, child_new_depth);
    current_status.child_depth = child_new_depth;
  }

  uint8_t child_new_layer = calculate_layer(current_status.child_depth);
  if(child_new_layer != current_status.child_layer) {
    LOG_INFO("Child switched layer from %u to %u\n",
             current_status.child_layer, child_new_layer);
    current_status.child_layer = child_new_layer;
  }
}

static void
route_callback(int event,
               const uip_ipaddr_t *route,
               const uip_ipaddr_t *next_hop,
               int num_routes,
               bool route_update) {

  bool route_added =
      (event == UIP_DS6_NOTIFICATION_DEFRT_ADD ||
          event == UIP_DS6_NOTIFICATION_ROUTE_ADD);

  // Fetch the route link-layer address by dissecting the IP
  linkaddr_t route_lladdr = {{0}};
  uip_ds6_set_lladdr_from_iid((uip_lladdr_t*)&route_lladdr, route);

  rpl_dag_t* rpl_dag = rpl_get_any_dag();
  if(rpl_dag == NULL) {
    LOG_ERR("No dag!\n");
    return;
  }

  layered_status_t previous_status = current_status;

  // Fetch depth from dag
  uint16_t node_new_depth = rpl_dag->depth;
  if(node_new_depth == 0xffff) {
    LOG_ERR("New depth invalid! %u\n", route_added);
    // Our depth is invalid, probably we have lost all parents. Do not
    // add cells for new routes as we don't know the depth, but allow removal of old
    if(route_added) {
      return;
    }
  }
  else {
    // Valid depth, update our status
    update_current_status(node_new_depth);
  }

  // Observed:
  // 1. We get periodic adding of default route
  // 2. Default route and regular route are separate things - not duplicated
  // 3. A node never learned the lladdr of its child (very strange).
  //    But in any case, node does not know lladdr of grandchilds or below
  //    So we must use ip addr

  // This does not work as a DAO with new information (e.g. grandchild
  // became child) would be filtered.
  // However, if not filtering these we get a lot of skipped slots,
  // probably because TSCH is busy adding/removing cells
//  if(route_update) {
//    LOG_INFO("Skip this route because it was only an update\n");
//    return;
//  }


  if(event == UIP_DS6_NOTIFICATION_DEFRT_ADD) {
    LOG_INFO("Added default route to ");
    LOG_INFO_6ADDR(route);
    LOG_INFO_(" / ");
    LOG_INFO_LLADDR(&route_lladdr);
    LOG_INFO_(" via ");
    LOG_INFO_6ADDR(next_hop);
    LOG_INFO_("\n");
    add_cells(&route_lladdr, &current_status, true);
  }
  // TODO Does this work well if we have moved depth?
  else if(event == UIP_DS6_NOTIFICATION_DEFRT_RM) {
    LOG_INFO("Removed default route ");
    LOG_INFO_6ADDR(route);
    LOG_INFO_(" / ");
    LOG_INFO_LLADDR(&route_lladdr);
    LOG_INFO_(" via ");
    LOG_INFO_6ADDR(next_hop);
    LOG_INFO_("\n");
    remove_cells(&route_lladdr, &previous_status, true);
  }
  else if(event == UIP_DS6_NOTIFICATION_ROUTE_ADD) {
    LOG_INFO("Added route ");
    LOG_INFO_6ADDR(route);
    LOG_INFO_(" / ");
    LOG_INFO_LLADDR(&route_lladdr);
    LOG_INFO_(" via ");
    LOG_INFO_6ADDR(next_hop);
    LOG_INFO_("\n");
    add_cells(&route_lladdr, &current_status, false);
  }
  // TODO Does this work well if we have moved depth?
  else if(event == UIP_DS6_NOTIFICATION_ROUTE_RM) {
    LOG_INFO("Removed route ");
    LOG_INFO_6ADDR(route);
    LOG_INFO_(" / ");
    LOG_INFO_LLADDR(&route_lladdr);
    LOG_INFO_(" via ");
    LOG_INFO_6ADDR(next_hop);
    LOG_INFO_("\n");
    remove_cells(&route_lladdr, &current_status, false);
  }
}

/*---------------------------------------------------------------------------*/
static void
init(uint16_t sf_handle)
{
  // Register for route changes
  static struct uip_ds6_notification n;
  uip_ds6_notification_add(&n, route_callback);
  LOG_INFO("Registered for route changes\n");

  slotframe_handle = sf_handle;

  /* Slotframe for unicast transmissions */
  sf_layered = tsch_schedule_add_slotframe(
      slotframe_handle, LAYERED_SF_LEN);

  schedule_common_cells();

  // If we are root we already know our depth,
  // so we can add the downward beacon cell
  if(is_root()) {
    LOG_INFO("Adding downward cell for root\n");
    current_status.node_depth = 0;
    current_status.child_depth = 1;
    current_status.node_layer = calculate_layer(current_status.node_depth);
    current_status.child_layer = calculate_layer(current_status.child_depth);
    add_cells(&linkaddr_node_addr, &current_status, true);
  }
}
/*---------------------------------------------------------------------------*/
struct layered_rule layered_multi_channel = {
  init,
  new_time_source,
  select_packet,
  NULL,
  NULL,
  "layered multi-channel",
};

#endif /* UIP_MAX_ROUTES */
