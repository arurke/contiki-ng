#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

#define LOG_CONF_LEVEL_MAC            LOG_LEVEL_WARN
//#define LOG_CONF_LEVEL_TCPIP          LOG_LEVEL_DBG
#define LOG_CONF_LEVEL_IPV6           LOG_LEVEL_WARN
#define LOG_CONF_LEVEL_RPL            LOG_LEVEL_INFO
//#define LOG_CONF_LEVEL_6LOWPAN        LOG_LEVEL_WARN
//#define LOG_CONF_LEVEL_FRAMER         LOG_LEVEL_INFO
#define LOG_CONF_LEVEL_LAYERED        LOG_LEVEL_INFO
#define LOG_CONF_WITH_COMPACT_ADDR    1
// Logging for every TSCH slot
#define TSCH_LOG_CONF_PER_SLOT        1


// Abort application run if topology change during operation
#define APP_CONF_ABORT_ON_TOPOLOGY_CHANGE   0
// Abort application if node does not have connection
#define APP_ABORT_ON_NO_CONNECTION          0

#if BUILD_WITH_DEPLOYMENT
#define DEPLOYMENT_MAPPING deployment_fit
#endif

// Select RPL OF. Note, both employ ETX.
#define USE_OF0                       0
#define USE_MRHOF                     1

#if USE_OF0
#define RPL_CONF_SUPPORTED_OFS        {&rpl_of0}
#define RPL_CONF_OF_OCP               RPL_OCP_OF0
//#define RPL_CONF_STATS                1 // Does not print extra
#define RPL_OF0_CONF_SR               RPL_OF0_FIXED_SR
#endif

#if USE_MRHOF
#define RPL_CONF_SUPPORTED_OFS        {&rpl_mrhof}
#define RPL_CONF_OF_OCP               RPL_OCP_MRHOF
// TODO test added reliability
#define RPL_MRHOF_CONF_SQUARED_ETX    0
#endif

// Use metric container which contains hop count needed for Layered
#if BUILD_WITH_LAYERED
#define RPL_CONF_WITH_MC              1
#define RPL_CONF_DAG_MC               RPL_DAG_MC_HOPCOUNT
#endif

// Enable DAO Ack for robustness
#if BUILD_WITH_LAYERED
//#define RPL_CONF_WITH_DAO_ACK             1
//#define RPL_CONF_DIO_REFRESH_DAO_ROUTES   0
#endif

// TX power in iotlab
#ifndef RF2XX_TX_POWER
#define RF2XX_TX_POWER                    PHY_POWER_m17dBm
#endif
#ifndef RF2XX_RX_RSSI_THRESHOLD
#define RF2XX_RX_RSSI_THRESHOLD           RF2XX_PHY_RX_THRESHOLD__m78dBm
#endif

// Buffer size (note that actual size is -1 due to ringbuf, see issue #1532)
// 64 for grid
#if BUILD_WITH_LAYERED
#define PACKET_BUFFER_SIZE                64
#else
#define PACKET_BUFFER_SIZE                32 // 2 x layered (unicast + other)
#endif
// 16 for 9-hop linear
//#define PACKET_BUFFER_SIZE                16
// 8 for 2-hop topology
//#define PACKET_BUFFER_SIZE                8

// Total queue buffer size
#define QUEUEBUF_CONF_NUM                 PACKET_BUFFER_SIZE

// Max queue size per neighbor. Must be power of two.
// Note, must be increased if not using flows with Layered
#if BUILD_WITH_LAYERED
#define TSCH_QUEUE_CONF_NUM_PER_NEIGHBOR  16
#endif

// Increase incoming packets buffer (def. 4)
#define TSCH_CONF_MAX_INCOMING_PACKETS    8

// Disable use of pending bit which allows nodes to use more slots
#define TSCH_CONF_BURST_MAX_LEN           0

// Allow very deep networks (default 32) TODO use for depth?
#define TSCH_CONF_MAX_JOIN_PRIORITY       64

// Increase number of links for grid-setup
#define TSCH_SCHEDULE_CONF_MAX_LINKS      64

#define TSCH_STATS_CONF_ON                0

// Disable RPL probing which takes up space in queues
#define RPL_CONF_WITH_PROBING             1

// Channels (min. 4 available to allow for orchestra multi-channel)
#define CUSTOM_TSCH_HOPPING_SEQUENCE_16_16 (uint8_t[]){16, 17, 23, 18, 26, 15, 25, 22, 19, 11, 12, 13, 24, 14, 20, 21}
#define CUSTOM_TSCH_HOPPING_SEQUENCE_4_4 (uint8_t[]){18, 22, 24, 17}
#define CUSTOM_TSCH_HOPPING_SEQUENCE_4_4_HIGH (uint8_t[]){22, 24, 25, 26}
#define CUSTOM_TSCH_HOPPING_SEQUENCE_4_4_MED (uint8_t[]){18, 19, 20, 21}
#define CUSTOM_TSCH_HOPPING_SEQUENCE_4_4_BEST_STRASBOURG (uint8_t[]){14, 15, 16, 17}
#define CUSTOM_TSCH_HOPPING_SEQUENCE_6_6_MED (uint8_t[]){16, 17, 18, 19, 20, 21}
// The TSCH_HOPPING_SEQUENCE_4_4 defined in TSCH avoid Wi-Fi channels
#ifndef TSCH_CONF_DEFAULT_HOPPING_SEQUENCE
#define TSCH_CONF_DEFAULT_HOPPING_SEQUENCE    CUSTOM_TSCH_HOPPING_SEQUENCE_4_4_MED
#endif

// TODO for special evaluation
//#ifdef TSCH_CONF_JOIN_HOPPING_SEQUENCE
//#define TSCH_CONF_JOIN_HOPPING_SEQUENCE   CUSTOM_TSCH_HOPPING_SEQUENCE_4_4_MED
//#endif

#if BUILD_WITH_ORCHESTRA
// Max. channel offset for the unicast slotframe.
// Leave at default
//#define ORCHESTRA_CONF_UNICAST_MAX_CHANNEL_OFFSET (sizeof(TSCH_CONF_DEFAULT_HOPPING_SEQUENCE) - 1)

// Length of EB SF (def. 397)
#define ORCHESTRA_CONF_EBSF_PERIOD            397

// Length of common SF (def. 31)
#define ORCHESTRA_CONF_COMMON_SHARED_PERIOD   31

// Length of unicast SF (def. 17)
#if LARGER_TOPOLOGY
#define ORCHESTRA_CONF_UNICAST_PERIOD         29
#else
#define ORCHESTRA_CONF_UNICAST_PERIOD         17
#endif

// Is hash collision free? (def.  0)
#define ORCHESTRA_CONF_COLLISION_FREE_HASH    1

// Max hash output size (def. 0x7fff). Set to number of nodes.
#if LARGER_TOPOLOGY
#define ORCHESTRA_CONF_MAX_HASH               26
#else
#define ORCHESTRA_CONF_MAX_HASH               16
#endif

// Sender or receiver based (def. receiver)
#define ORCHESTRA_CONF_UNICAST_SENDER_BASED   1

//#define RPL_CONF_DIO_REFRESH_DAO_ROUTES 0
//#define RPL_CONF_DEFAULT_LIFETIME 60
//#define RPL_CONF_DAG_LIFETIME 100

#if BUILD_WITH_DEPLOYMENT && TESTBED
// Hash that uses deployment ID. Needed in testbed.
#define ORCHESTRA_CONF_DEPLOYMENT_HASH        1
#endif

#endif

// Num nodes supported for layers (including sink)
//#define LAYERED_CONF_MAX_NUM_NODES            49
#if LARGER_TOPOLOGY
#define LAYERED_CONF_MAX_NUM_NODES            29 // Also removed the ad-hoc fix in layered-conf.h
#else
#define LAYERED_CONF_MAX_NUM_NODES            17 // Also removed the ad-hoc fix in layered-conf.h
#endif
#define LAYERED_CONF_NUM_LAYERS               2
#if LARGER_TOPOLOGY
#define LAYERED_CONF_COMMON_SLOT_SPACING      9
#else
#define LAYERED_CONF_COMMON_SLOT_SPACING      11
#endif

// Convenience variable for no spatial reuse.
// 4 channels give no spatial reuse up to 8 hops
// Note there is only 4 channels which dodges wi-fi
// If increasing, remember to increase hopping sequence as well
#if TEST_NO_SPATIAL_REUSE
#define LAYERED_CONF_CHANNELS                 ((uint8_t[]){1,2,3,4})
#else
#define LAYERED_CONF_CHANNELS                 ((uint8_t[]){1,2}) // TODO for special testing
#endif

#if BUILD_WITH_LAYERED
#define TSCH_SCHEDULE_CONF_MAX_SLOTFRAMES     1
#endif

// Improve chance of dodging other experiments in the testbed
#if TESTBED
#define IEEE802154_CONF_PANID                 0xa371
#endif

// TODO just for testing after queues got filled up. Number from Atis
//#define TSCH_CONF_MAC_MAX_BE 3

// Enable cell duty-cycle statistics
// TODO this assumes cooja mote
#define CELL_DUTY_CYCLE_STATS                 0

/* Reduce ROM and RAM usage */
// No need for large packet support
#define UIP_CONF_BUFFER_SIZE                  140

// TODO Default is 16 // Need a lot because we have neighbor-entries for flows as well
#define NBR_TABLE_CONF_MAX_NEIGHBORS          64

// TODO Default is 16
#define NETSTACK_MAX_ROUTE_ENTRIES            32

// Disable support for packet fragmentation
#define SICSLOWPAN_CONF_FRAG                  0

// No need for process names (used for debugging)
#define PROCESS_CONF_NO_PROCESS_NAMES         1

// Disable stack checker? (not available on native and iotlab)
#define STACK_CHECK_CONF_ENABLED              0

#endif /* PROJECT_CONF_H_ */
