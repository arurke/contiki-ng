#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

#define LOG_CONF_LEVEL_MAC            LOG_LEVEL_ERR
//#define LOG_CONF_LEVEL_TCPIP          LOG_LEVEL_DBG
//#define LOG_CONF_LEVEL_IPV6           LOG_LEVEL_DBG
//#define LOG_CONF_LEVEL_RPL            LOG_LEVEL_DBG
//#define LOG_CONF_LEVEL_6LOWPAN        LOG_LEVEL_WARN
//#define LOG_CONF_LEVEL_FRAMER         LOG_LEVEL_INFO
#define LOG_CONF_WITH_COMPACT_ADDR    1

// Use only objective function 0
#define RPL_CONF_SUPPORTED_OFS        {&rpl_of0}
#define RPL_CONF_OF_OCP               RPL_OCP_OF0
//#define RPL_CONF_STATS                1 // Does not print extra
#define RPL_OF0_CONF_SR               RPL_OF0_FIXED_SR

// z1 sets to 2, but we have seen queue full, so we try force TSCH default 4
#define TSCH_CONF_MAX_INCOMING_PACKETS    4

// Total queue buffer size
#define QUEUEBUF_CONF_NUM                 4

// Max queue size per neighbor
#define TSCH_QUEUE_CONF_NUM_PER_NEIGHBOR  4

// Disable use of pending bit which allows nodes to use more slots
#define TSCH_CONF_BURST_MAX_LEN           0

// Allow very deep networks
#define TSCH_CONF_MAX_JOIN_PRIORITY       64

// Disable RPL probing which takes up space in queues
#define RPL_CONF_WITH_PROBING             0

// Number of channels (1)
#define TSCH_CONF_DEFAULT_HOPPING_SEQUENCE    TSCH_HOPPING_SEQUENCE_2_2

// Length of EB SF (def. 397)
#define ORCHESTRA_CONF_EBSF_PERIOD            397

// Length of common SF (def. 31)
#define ORCHESTRA_CONF_COMMON_SHARED_PERIOD   31

// Length of unicast SF (def. 17)
#define ORCHESTRA_CONF_UNICAST_PERIOD         101

// Is hash collision free? (def.  0)
#define ORCHESTRA_CONF_COLLISION_FREE_HASH    1

// Max hash output size (def. 0x7fff)
#define ORCHESTRA_CONF_MAX_HASH               0x10

// Sender or receiver based (def. receiver)
#define ORCHESTRA_CONF_UNICAST_SENDER_BASED   1


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
