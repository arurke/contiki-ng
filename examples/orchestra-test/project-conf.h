#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

// NOTE z1 cannot support extensive logging due to ROM size
#define LOG_CONF_LEVEL_MAC            LOG_LEVEL_DBG
//#define LOG_CONF_LEVEL_TCPIP          LOG_LEVEL_DBG
//#define LOG_CONF_LEVEL_IPV6           LOG_LEVEL_DBG
#define LOG_CONF_LEVEL_RPL            LOG_LEVEL_DBG
//#define LOG_CONF_LEVEL_6LOWPAN        LOG_LEVEL_WARN
//#define LOG_CONF_LEVEL_FRAMER         LOG_LEVEL_INFO
#define LOG_CONF_WITH_COMPACT_ADDR    1

// Use only objective function 0
#define RPL_CONF_SUPPORTED_OFS        {&rpl_of0}
#define RPL_CONF_OF_OCP               RPL_OCP_OF0
//#define RPL_CONF_STATS                1 // Does not print extra
#define RPL_OF0_CONF_SR               RPL_OF0_FIXED_SR

// Enable DAO Ack for robustness
#if BUILD_WITH_LAYERED
//#define RPL_CONF_WITH_DAO_ACK             1
//#define RPL_CONF_DIO_REFRESH_DAO_ROUTES   0
#endif

// z1 sets to 2, but we have seen queue full, so we try force TSCH default 4
//#define TSCH_CONF_MAX_INCOMING_PACKETS    4

// Total queue buffer size
#define QUEUEBUF_CONF_NUM                 8

// Max queue size per neighbor
#define TSCH_QUEUE_CONF_NUM_PER_NEIGHBOR  8

// Disable use of pending bit which allows nodes to use more slots
#define TSCH_CONF_BURST_MAX_LEN           0

// Disable RPL probing which takes up space in queues
#define RPL_CONF_WITH_PROBING             0

// Allow very deep networks
#define TSCH_CONF_MAX_JOIN_PRIORITY       64

// Number of channels (4 available to allow for orchestra multi-channel)
#define TSCH_CONF_DEFAULT_HOPPING_SEQUENCE    TSCH_HOPPING_SEQUENCE_4_4
#define ORCHESTRA_CONF_UNICAST_MAX_CHANNEL_OFFSET 2


// Length of EB SF (def. 397)
#define ORCHESTRA_CONF_EBSF_PERIOD            397

// Length of common SF (def. 31)
#define ORCHESTRA_CONF_COMMON_SHARED_PERIOD   31

// Length of unicast SF (def. 17)
#define ORCHESTRA_CONF_UNICAST_PERIOD         101

// Is hash collision free? (def.  0)
#define ORCHESTRA_CONF_COLLISION_FREE_HASH    1

// Max hash output size (def. 0x7fff)
#define ORCHESTRA_CONF_MAX_HASH               49

// Sender or receiver based (def. receiver)
#define ORCHESTRA_CONF_UNICAST_SENDER_BASED   1

#if BUILD_WITH_ORCHESTRA
#define SCHED_SLOTFRAME_LEN                   ORCHESTRA_CONF_UNICAST_PERIOD
#endif

// Num nodes supported for layers (including sink)
#define LAYERED_CONF_MAX_NUM_NODES            49
#define LAYERED_CONF_NUM_LAYERS               2
#define LAYERED_CONF_COMMON_SLOT_SPACING      31

// Enable cell duty-cycle statistics
// TODO this assumes cooja mote
#define CELL_DUTY_CYCLE_STATS                 0

/* Reduce ROM and RAM usage so that it builds on z1 */
// No need for large packet support
#define UIP_CONF_BUFFER_SIZE                  140

// Disable support for packet fragmentation
#define SICSLOWPAN_CONF_FRAG                  0

// No need for process names (used for debugging)
#define PROCESS_CONF_NO_PROCESS_NAMES         1

// Disable stack checker? (it is not running native btw)
#define STACK_CHECK_CONF_ENABLED              0

#endif /* PROJECT_CONF_H_ */
