/*
 * Copyright (c) 2014, SICS Swedish ICT.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 * 3. Neither the name of the Institute nor the names of its contributors
 *    may be used to endorse or promote products derived from this software
 *    without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE INSTITUTE AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE INSTITUTE OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 *
 * This file is part of the Contiki operating system.
 *
 */

/**
 * \file
 *         Per-neighbor packet queues for TSCH MAC.
 *         The list of neighbors uses the TSCH lock, but per-neighbor packet array are lock-free.
 *				 Read-only operation on neighbor and packets are allowed from interrupts and outside of them.
 *				 *Other operations are allowed outside of interrupt only.*
 * \author
 *         Simon Duquennoy <simonduq@sics.se>
 *         Beshr Al Nahas <beshr@sics.se>
 *         Domenico De Guglielmo <d.deguglielmo@iet.unipi.it >
 *         Atis Elsts <atis.elsts@edi.lv>
 */

/**
 * \addtogroup tsch
 * @{
*/

#include "contiki.h"
#include "lib/list.h"
#include "lib/memb.h"
#include "lib/random.h"
#include "net/queuebuf.h"
#include "net/mac/tsch/tsch.h"
#include "net/nbr-table.h"
#include <string.h>
#if BUILD_WITH_LAYERED
#include "layered.h"
#endif

/* Log configuration */
#include "sys/log.h"
#define LOG_MODULE "TSCH Queue"
#define LOG_LEVEL LOG_LEVEL_INFO

/* Check if TSCH_QUEUE_NUM_PER_NEIGHBOR is power of two */
#if (TSCH_QUEUE_NUM_PER_NEIGHBOR & (TSCH_QUEUE_NUM_PER_NEIGHBOR - 1)) != 0
#error TSCH_QUEUE_NUM_PER_NEIGHBOR must be power of two
#endif

/* We have as many packets are there are queuebuf in the system */
MEMB(packet_memb, struct tsch_packet, QUEUEBUF_NUM);
NBR_TABLE(struct tsch_neighbor, tsch_neighbors);

/* Broadcast and EB virtual neighbors */
struct tsch_neighbor *n_broadcast;
struct tsch_neighbor *n_eb;

static void tsch_queue_flush_nbr_queue(struct tsch_neighbor *n);

#if BUILD_WITH_LAYERED_FLOW
volatile uint32_t tsch_flow_error = 0;
#endif

/*---------------------------------------------------------------------------*/
/* Add a TSCH neighbor */
struct tsch_neighbor *
tsch_queue_add_nbr(const linkaddr_t *addr)
{
  struct tsch_neighbor *n = NULL;
  /* If we have an entry for this neighbor already, we simply update it */
  n = tsch_queue_get_nbr(addr);
  if(n == NULL) {
    if(tsch_get_lock()) {
      /* Allocate a neighbor */
      n = (struct tsch_neighbor *)nbr_table_add_lladdr(tsch_neighbors, addr, NBR_TABLE_REASON_MAC, NULL);
      if(n != NULL) {
        /* Do not allow to garbage collect this neighbor by external code!
         * The garbage collection is not aware of the tsch_lock, so is not interrupt safe.
         */
        nbr_table_lock(tsch_neighbors, n);
        /* Initialize neighbor entry */
        memset(n, 0, sizeof(struct tsch_neighbor));
        ringbufindex_init(&n->tx_ringbuf, TSCH_QUEUE_NUM_PER_NEIGHBOR);
        n->is_broadcast = linkaddr_cmp(addr, &tsch_eb_address)
          || linkaddr_cmp(addr, &tsch_broadcast_address);
        tsch_queue_backoff_reset(n);
      }
      tsch_release_lock();
    }
  }
  return n;
}
/*---------------------------------------------------------------------------*/
/* Get a TSCH neighbor */
struct tsch_neighbor *
tsch_queue_get_nbr(const linkaddr_t *addr)
{
  if(!tsch_is_locked()) {
    return (struct tsch_neighbor *)nbr_table_get_from_lladdr(tsch_neighbors, addr);
  }
  return NULL;
}
/*---------------------------------------------------------------------------*/
/* Get a TSCH time source (we currently assume there is only one) */
struct tsch_neighbor *
tsch_queue_get_time_source(void)
{
  if(!tsch_is_locked()) {
    struct tsch_neighbor *curr_nbr = (struct tsch_neighbor *)nbr_table_head(tsch_neighbors);
    while(curr_nbr != NULL) {
      if(curr_nbr->is_time_source) {
        return curr_nbr;
      }
      curr_nbr = (struct tsch_neighbor *)nbr_table_next(tsch_neighbors, curr_nbr);
    }
  }
  return NULL;
}
/*---------------------------------------------------------------------------*/
linkaddr_t *
tsch_queue_get_nbr_address(const struct tsch_neighbor *n)
{
  return nbr_table_get_lladdr(tsch_neighbors, n);
}
/*---------------------------------------------------------------------------*/
/* Update TSCH time source */
int
tsch_queue_update_time_source(const linkaddr_t *new_addr)
{
  if(!tsch_is_locked()) {
    if(!tsch_is_coordinator) {
      struct tsch_neighbor *old_time_src = tsch_queue_get_time_source();
      struct tsch_neighbor *new_time_src = NULL;

      if(new_addr != NULL) {
        /* Get/add neighbor, return 0 in case of failure */
        new_time_src = tsch_queue_add_nbr(new_addr);
        if(new_time_src == NULL) {
          return 0;
        }
      }

      if(new_time_src != old_time_src) {
        LOG_INFO("update time source: ");
        LOG_INFO_LLADDR(tsch_queue_get_nbr_address(old_time_src));
        LOG_INFO_(" -> ");
        LOG_INFO_LLADDR(tsch_queue_get_nbr_address(new_time_src));
        LOG_INFO_("\n");

        /* Update time source */
        if(new_time_src != NULL) {

          // Purge queue of the old time source/parent.
          // This to avoid stale packets laying in queue until next
          // time we associate with this source. TODO could be avoided
          // if we had queues per flow. Not necessary when we hack queue.
//          tsch_queue_flush_nbr_queue(old_time_src);

          new_time_src->is_time_source = 1;
          /* (Re)set keep-alive timeout */
          tsch_set_ka_timeout(TSCH_KEEPALIVE_TIMEOUT);
        } else {
          /* Stop sending keepalives */
          tsch_set_ka_timeout(0);
        }

        if(old_time_src != NULL) {
          old_time_src->is_time_source = 0;
        }

        tsch_stats_reset_neighbor_stats();

#ifdef TSCH_CALLBACK_NEW_TIME_SOURCE
        TSCH_CALLBACK_NEW_TIME_SOURCE(old_time_src, new_time_src);
#endif
      }

      return 1;
    }
  }
  return 0;
}
/*---------------------------------------------------------------------------*/
/* Flush a neighbor queue */
static void
tsch_queue_flush_nbr_queue(struct tsch_neighbor *n)
{
  while(!tsch_queue_is_empty(n)) {
    struct tsch_packet *p = tsch_queue_remove_packet_from_queue(n);
    if(p != NULL) {
      /* Set return status for packet_sent callback */
      p->ret = MAC_TX_ERR;
      LOG_WARN("! flushing packet\n");
      /* Call packet_sent callback */
      mac_call_sent_callback(p->sent, p->ptr, p->ret, p->transmissions);
      /* Free packet queuebuf */
      tsch_queue_free_packet(p);
    }
  }
}
/*---------------------------------------------------------------------------*/
/* Remove TSCH neighbor queue */
static void
tsch_queue_remove_nbr(struct tsch_neighbor *n)
{
  if(n != NULL) {
    if(tsch_get_lock()) {

      tsch_release_lock();

      /* Flush queue */
      tsch_queue_flush_nbr_queue(n);

      /* Free neighbor */
      nbr_table_remove(tsch_neighbors, n);
    }
  }
}
/*---------------------------------------------------------------------------*/
/* Add packet to neighbor queue. Use same lockfree implementation as ringbuf.c (put is atomic) */
struct tsch_packet *
tsch_queue_add_packet(const linkaddr_t *addr, uint8_t max_transmissions,
                      mac_callback_t sent, void *ptr)
{
  struct tsch_neighbor *n = NULL;
  int16_t put_index = -1;
  struct tsch_packet *p = NULL;

#ifdef TSCH_CALLBACK_PACKET_READY
  /* The scheduler provides a callback which sets the timeslot and other attributes */
  if(TSCH_CALLBACK_PACKET_READY() < 0) {
    /* No scheduled slots for the packet available; drop it early to save queue space. */
    LOG_ERR("tsch_queue_add_packet(): rejected by the scheduler\n");
    return NULL;
  }
#endif

  linkaddr_t addr_to_use = {0};
  linkaddr_copy(&addr_to_use, addr);

  if(!tsch_is_locked()) {

#if BUILD_WITH_LAYERED_FLOW
    // If this packet is going in a flow, put it in a flow-neighbor queue
    // instead of the next-hop neighbor
    linkaddr_t flow_address = {0};
    bool packet_belongs_to_a_flow =
        layered_get_flow_address_for_packet(
            packetbuf_attr(PACKETBUF_ATTR_FRAME_TYPE),
            packetbuf_dataptr(), packetbuf_datalen(),
            &flow_address);

    if(packet_belongs_to_a_flow) {
      // Add next-hop neighbor
      // (had problem with the next-hop neighbor being deleted (since next-hop
      // neighbor has nothing in its queues). Removed cleaning up of nbrs.
      // If using time-source neighbor strategy in tx-slot-operation the below
      // can be comment (if so, we assume upwards convergecast)
      if(tsch_queue_add_nbr(&addr_to_use) ==  NULL) {
        tsch_flow_error++;
        LOG_ERR("!asdERR add neighbor failed!\n");
        return NULL;
      }

      // Replace address with the flow address so that flow-addr
      // is added as neighbor and packet is put in the flow-neighbor queue
      tsch_schedule_convert_to_flow_address(&flow_address);
      linkaddr_copy(&addr_to_use, &flow_address);
    }
#endif

#if BUILD_WITH_LAYERED
    // If this is a RPL packet, change the addr to a broadcast-addr such that
    // all RPL packets (including unicast) ends up in the broadcast queue
    // This will reduce reliability of unicast RPL packets
    // Note that this does not change the actual address in the packet
    if(packetbuf_attr(PACKETBUF_ATTR_TEST) == LAYERED_PACKET_TYPE_RPL) {
      tsch_queue_add_nbr(&addr_to_use);
      linkaddr_copy(&addr_to_use, &tsch_broadcast_address);
      //LOG_DBG("asd Added RPL packet to broadcast queue\n");
    }

    // Do same for TSCH keepalive packets
    if(packetbuf_attr(PACKETBUF_ATTR_TEST) == LAYERED_PACKET_TYPE_KEEPALIVE) {
      tsch_queue_add_nbr(&addr_to_use);
      linkaddr_copy(&addr_to_use, &tsch_broadcast_address);
      //LOG_DBG("asd Added TSCH KA packet to broadcast queue\n");
    }
#endif

    n = tsch_queue_add_nbr(&addr_to_use);
    if(n != NULL) {
      put_index = ringbufindex_peek_put(&n->tx_ringbuf);
      if(put_index != -1) {
        p = memb_alloc(&packet_memb);
        if(p != NULL) {
          /* Enqueue packet */
          p->qb = queuebuf_new_from_packetbuf();
          if(p->qb != NULL) {
            p->sent = sent;
            p->ptr = ptr;
            p->ret = MAC_TX_DEFERRED;
            p->transmissions = 0;
            p->max_transmissions = max_transmissions;
            /* Add to ringbuf (actual add committed through atomic operation) */
            n->tx_array[put_index] = p;
            ringbufindex_put(&n->tx_ringbuf);
            LOG_DBG("packet is added put_index %u, packet %p\n", put_index, p);
            return p;
          } else {
            memb_free(&packet_memb, p);
          }
        }
      }
    }
  }
  LOG_ERR("! add packet failed: %u %p %d %p %p\n", tsch_is_locked(), n, put_index, p, p ? p->qb : NULL);
  return NULL;
}
/*---------------------------------------------------------------------------*/
/* Returns the number of packets currently in any TSCH queue */
int
tsch_queue_global_packet_count(void)
{
  return QUEUEBUF_NUM - memb_numfree(&packet_memb);
}
/*---------------------------------------------------------------------------*/
/* Returns the number of packets currently in the queue */
int
tsch_queue_nbr_packet_count(const struct tsch_neighbor *n)
{
  if(n != NULL) {
    return ringbufindex_elements(&n->tx_ringbuf);
  }
  return -1;
}
/*---------------------------------------------------------------------------*/
/* Remove first packet from a neighbor queue */
struct tsch_packet *
tsch_queue_remove_packet_from_queue(struct tsch_neighbor *n)
{
  if(!tsch_is_locked()) {
    if(n != NULL) {
      /* Get and remove packet from ringbuf (remove committed through an atomic operation */
      int16_t get_index = ringbufindex_get(&n->tx_ringbuf);
      if(get_index != -1) {
        return n->tx_array[get_index];
      } else {
        return NULL;
      }
    }
  }
  return NULL;
}
/*---------------------------------------------------------------------------*/
/* Free a packet */
void
tsch_queue_free_packet(struct tsch_packet *p)
{
  if(p != NULL) {
    queuebuf_free(p->qb);
    memb_free(&packet_memb, p);
  }
}
/*---------------------------------------------------------------------------*/
/* Updates neighbor queue state after a transmission */
int
tsch_queue_packet_sent(struct tsch_neighbor *n, struct tsch_packet *p,
                      struct tsch_link *link, uint8_t mac_tx_status)
{
  int in_queue = 1;
  int is_shared_link = link->link_options & LINK_OPTION_SHARED;
  int is_unicast = !n->is_broadcast;

#if BUILD_WITH_LAYERED
  // If this was a RPL or KA packet it originated from the broadcast queue
  // and not the unicast-destination queue.
  int packet_attr_type = queuebuf_attr(p->qb, PACKETBUF_ATTR_TEST);
  if(packet_attr_type == LAYERED_PACKET_TYPE_RPL ||
      packet_attr_type == LAYERED_PACKET_TYPE_KEEPALIVE) {
    n = n_broadcast;
  }
#endif
#if BUILD_WITH_LAYERED_FLOW
  // If this packet was in a flow, we should remove the packet from the
  // flow-neighbor queue
  struct tsch_neighbor* flow_neighbor = NULL;
  if(tsch_schedule_link_is_flow_link(link)) {
    flow_neighbor = tsch_queue_get_nbr(&link->addr);
    if(flow_neighbor == NULL) {
      // This should not happen
      tsch_flow_error++;
      TSCH_LOG_ADD(tsch_log_message,
                    snprintf(log->message, sizeof(log->message),
                             "!asdERR no flow neighbor when dequeuing"));
    }
    else {
      n = flow_neighbor;
      is_unicast = true;
    }
  }
#endif


  if(mac_tx_status == MAC_TX_OK) {
    /* Successful transmission */
      tsch_queue_remove_packet_from_queue(n);

    in_queue = 0;

    /* Update CSMA state in the unicast case */
    if(is_unicast) {
      if(is_shared_link || tsch_queue_is_empty(n)) {
        /* If this is a shared link, reset backoff on success.
         * Otherwise, do so only is the queue is empty */
        tsch_queue_backoff_reset(n);
      }
    }
  } else {
    /* Failed transmission */
    if(p->transmissions >= p->max_transmissions) {
      /* Drop packet */
      tsch_queue_remove_packet_from_queue(n);
      in_queue = 0;
    }
    /* Update CSMA state in the unicast case */
    if(is_unicast) {
      /* Failures on dedicated (== non-shared) leave the backoff
       * window nor exponent unchanged */
      if(is_shared_link) {
        /* Shared link: increment backoff exponent, pick a new window */
        tsch_queue_backoff_inc(n);
      }
    }
  }

  return in_queue;
}
/*---------------------------------------------------------------------------*/
/* Flush all neighbor queues */
void
tsch_queue_reset(void)
{
  /* Deallocate unneeded neighbors */
  if(!tsch_is_locked()) {
    struct tsch_neighbor *n = (struct tsch_neighbor *)nbr_table_head(tsch_neighbors);
    while(n != NULL) {
      struct tsch_neighbor *next_n = (struct tsch_neighbor *)nbr_table_next(tsch_neighbors, n);
      /* Flush queue */
      tsch_queue_flush_nbr_queue(n);
      /* Reset backoff exponent */
      tsch_queue_backoff_reset(n);
      n = next_n;
    }
  }
}
/*---------------------------------------------------------------------------*/
/* Deallocate neighbors with empty queue */
void
tsch_queue_free_unused_neighbors(void)
{
  /* Deallocate unneeded neighbors */
  if(!tsch_is_locked()) {
    struct tsch_neighbor *n = (struct tsch_neighbor *)nbr_table_head(tsch_neighbors);
    while(n != NULL) {
      struct tsch_neighbor *next_n = (struct tsch_neighbor *)nbr_table_next(tsch_neighbors, n);
      /* Queue is empty, no tx link to this neighbor: deallocate.
       * Always keep time source and virtual broadcast neighbors. */
      if(!n->is_broadcast && !n->is_time_source && !n->tx_links_count
         && tsch_queue_is_empty(n)) {
        tsch_queue_remove_nbr(n);
      }
      n = next_n;
    }
  }
}
/*---------------------------------------------------------------------------*/
/* Is the neighbor queue empty? */
int
tsch_queue_is_empty(const struct tsch_neighbor *n)
{
  return !tsch_is_locked() && n != NULL && ringbufindex_empty(&n->tx_ringbuf);
}
/*---------------------------------------------------------------------------*/

#if BUILD_WITH_LAYERED_HACK
volatile uint32_t tsch_hack_errors = 0;
volatile uint32_t tsch_hack_deleted_packets = 0;

static bool scheduler_calculate_packet_cell(
    uint16_t* packet_slotframe, uint16_t* packet_timeslot,
    uint16_t* packet_channel_offset, struct queuebuf* packet_qbuf) {

  layered_packet_type_t packet_type = 0;
  uint16_t frame_type = queuebuf_attr(packet_qbuf, PACKETBUF_ATTR_FRAME_TYPE);
  uint8_t* data = ((uint8_t*)queuebuf_dataptr(packet_qbuf)) + 21; // TODO queuebuf does not remove header
  uint16_t data_len = queuebuf_datalen(packet_qbuf);

  // TODO maybe frame802154_hdrlen can be used
  // TODO maybe queuebuf_to_packetbuf()

//  LOG_DBG("Sender: ");
//  LOG_DBG_LLADDR(queuebuf_addr(packet_qbuf, PACKETBUF_ADDR_SENDER));
//  LOG_DBG("\n");
//
//  LOG_DBG("Receiver: ");
//  LOG_DBG_LLADDR(queuebuf_addr(packet_qbuf, PACKETBUF_ADDR_RECEIVER));
//  LOG_DBG("\n");

  if(!layered_calc_packet_cell(frame_type, data, data_len,
      packet_slotframe, packet_timeslot, packet_channel_offset,
      &packet_type)) {
    return false;
  }
  return true;
}

static struct tsch_packet* hack2(
    struct tsch_neighbor *n, uint16_t curr_timeslot, uint16_t curr_channel) {

  // Goal is to see if there are packets for the current cell in the queue
  // And delete those that have no corresponding link
  // We cannot peak through the ringbuf, so we have to read it all out
  // and then reconstruct
  uint8_t packet_for_cell = 0xff;

  if(tsch_is_locked()) {
    TSCH_LOG_ADD(tsch_log_message,
                 snprintf(log->message, sizeof(log->message),
                   "!asdERR locked!"));
    tsch_hack_errors++;
    return NULL;
  }

  // Read out the queue into an array and check for match
  struct tsch_packet* packet_pointers[TSCH_QUEUE_NUM_PER_NEIGHBOR] = {0};
  uint8_t num_packets = 0;
  while(ringbufindex_elements(&n->tx_ringbuf)) {
    int16_t index_of_packet = ringbufindex_get(&n->tx_ringbuf);
    if(index_of_packet == -1) {
      TSCH_LOG_ADD(tsch_log_message,
                   snprintf(log->message, sizeof(log->message),
                     "!asdERR ringbuf get failed!"));
      tsch_hack_errors++;
      return NULL;
    }

    // Calculate cell coordinates
    uint16_t packet_slotframe = 0;
    uint16_t packet_timeslot = 0;
    uint16_t packet_channel_offset = 0;

    if(!scheduler_calculate_packet_cell(
        &packet_slotframe, &packet_timeslot, &packet_channel_offset,
        n->tx_array[index_of_packet]->qb)) {
      TSCH_LOG_ADD(tsch_log_message,
                   snprintf(log->message, sizeof(log->message),
                            "!asdERR calc-err!"));
      tsch_hack_errors++;
      return NULL;
    }

    // Check if packet matches current cell
    if(packet_timeslot == curr_timeslot && packet_channel_offset == curr_channel) {
      packet_for_cell = num_packets;
      packet_pointers[num_packets] = n->tx_array[index_of_packet];
      num_packets++;
      continue;
    }

    // 4. If no match, check if TS/CH matches any link. If no, delete pckt.
    struct tsch_link* link =
        tsch_schedule_get_link_by_timeslot(
            tsch_schedule_get_slotframe_by_handle(packet_slotframe),
            packet_timeslot, packet_channel_offset);
    if(link == NULL) {
      TSCH_LOG_ADD(tsch_log_message,
                   snprintf(log->message, sizeof(log->message),
                            "!asd delete packet!, %u/%u",
                            packet_timeslot, packet_channel_offset));
      tsch_hack_deleted_packets++;
      tsch_queue_free_packet(n->tx_array[index_of_packet]);
      continue;
    }

    packet_pointers[num_packets] = n->tx_array[index_of_packet];
    num_packets++;
  }

  // We now have an array of all the packets and their pointers
  // If found packet for current cell, add it to front of new queue
  if(packet_for_cell != 0xff) {
    int16_t new_index_of_packet = ringbufindex_peek_put(&n->tx_ringbuf);
    if(new_index_of_packet != -1) {
      n->tx_array[new_index_of_packet] = packet_pointers[packet_for_cell];
      ringbufindex_put(&n->tx_ringbuf);
    }
    else {
      TSCH_LOG_ADD(tsch_log_message,
                   snprintf(log->message, sizeof(log->message),
                     "!asdERR ringbuf put failed"));
      tsch_hack_errors++;
      return NULL;
    }
  }

  // Now add all the other packets back in
  for(uint8_t i = 0; i < num_packets; i++) {
    // Don't add the timeslot-packet two times
    if(i == packet_for_cell) {
      continue;
    }

    int16_t new_index_of_packet = ringbufindex_peek_put(&n->tx_ringbuf);
    if(new_index_of_packet != -1) {
      n->tx_array[new_index_of_packet] = packet_pointers[i];
      ringbufindex_put(&n->tx_ringbuf);
    }
    else {
      TSCH_LOG_ADD(tsch_log_message,
                   snprintf(log->message, sizeof(log->message),
                     "!asdERR ringbuf put rest failed"));
      tsch_hack_errors++;
      return NULL;
    }
  }

  if(packet_for_cell != 0xff) {
    return packet_pointers[packet_for_cell];
  }

  return NULL;


}
#endif

#if BUILD_WITH_DEPLOYMENT
#include "os/services/deployment/deployment.h"
#endif

#if BUILD_WITH_LAYERED_HACK
/* Returns the first packet from a neighbor queue */
// Note that if neighbor is broadcast, the packet may belong to a different
// unicast neighbor because we put all RPL and KA packets into
// broadcast queue.
struct tsch_packet *
tsch_queue_get_packet_for_nbr(struct tsch_neighbor *n, struct tsch_link *link)
{
  if(!tsch_is_locked()) {
    int is_shared_link = link != NULL && link->link_options & LINK_OPTION_SHARED;
    if(n != NULL) {
      int16_t get_index = ringbufindex_peek_get(&n->tx_ringbuf);
      if(get_index != -1 &&
          !(is_shared_link && !tsch_queue_backoff_expired(n))) {    /* If this is a shared link,
                                                                    make sure the backoff has expired */

        // If this is the EB-queue we do not check the TS since we know
        // the link will be an advertising cell and we only have one of those.
        // This avoid having a stale EB in the queue where packet is added
        // with TS, then scheduled is changed and TS does not match.
        // TODO There is a chance some stale packets have wrong channel?
        // Channel is set by the packet-attribute, not by the link. (Possibly remove this?)
        if(n == n_eb) {
          return n->tx_array[get_index];
        }

        // If this is the broadcast-queue, we send it immediately if this
        // is a common slot. No need to check the TS.
        if(n == n_broadcast && is_shared_link) {
          return n->tx_array[get_index];
        }

        // If this is the broadcast-queue, but not a common slot, we skip TODO verify
        if(n == n_broadcast && !is_shared_link) {
          return NULL;
        }

        // We are only left with unicast-queues. If this is a shared link, skip.
        if(is_shared_link) {
          return NULL;
        }

        // Then we are left with unicast-queues. In these queues
        // there are packets going to all kind of end-destinations, thus they
        // have differing TS which we need to respect. A common situation
        // is probably that the packet in front of the queue is not for this
        // TS. Then we would need the hack to see if there is a packet
        // for the current TS. Need to consider: We could be called for
        // any unicast address (as long as we go with broadcast addr cells),
        // including old parent. If it was old parent stuff,

        // 1. Check if it is for this TS
        // 2. Try to find via hack?
        // 3. Nothing found, try to re-set TS? Re-set for which packet?!
        //    * Reset for all which is in a different queue?! Different from what?
        //      current Unicast cell?
        // 4. If re-set to non-existing cell, delete packet?

        // If this is from a queue towards current neighbor
        // 1. May match
        // 2. May find
        // 3. Re-set
        // 4. May happen (if route has been removed)

        // If this is from a queue towards an old neighbor
        // 1. May match (if depth has not changed)
        // 2. May find (if depth has not changed)
        // 3. Re-set
        // 4. May happen (if route has been removed)

        // New version:
        // 0. We have broadcast cell so that we get called by any_unicast()
        // 1. Check the first packet in the queue
        // 2. Calculate TS and channel.
        // 3. Does packet match current link? If yes, transmit it.
        // 4. Do hack and go through entire queue
        //    4.1. Calculate TS and channel
        //    4.2. Does it match current link? If yes, move to first of queue.
        //    4.3. Any packets without corresponding link? If yes, delete
        // 5. Transmit matching packet, or if none, return.

        // For the above to work, channel must be set by link, not packet.

        // Get qbuf for convenience
        struct queuebuf* packet_qbuf = n->tx_array[get_index]->qb;

        // Sanity check that we are dealing only with application packets
        int packet_attr_type = queuebuf_attr(packet_qbuf, PACKETBUF_ATTR_TEST);
        if(packet_attr_type != 1) {
          TSCH_LOG_ADD(tsch_log_message,
                       snprintf(log->message, sizeof(log->message),
                                "!asdERR no-app!"));
          tsch_hack_errors++;
        }

        // Sanity check that we are dealing only dedicated links
        if(is_shared_link) {
          TSCH_LOG_ADD(tsch_log_message,
                       snprintf(log->message, sizeof(log->message),
                                "!asdERR no-dedicated!"));
        }

        // Skip if this packet is for a different slotframe
        // TODO reconsider if this is necessary (if we will use select_packet() at all)
        // if remove, add check below at item 3 instead
        int packet_attr_slotframe =
            queuebuf_attr(packet_qbuf, PACKETBUF_ATTR_TSCH_SLOTFRAME);
        if(packet_attr_slotframe != 0xffff &&
            packet_attr_slotframe != link->slotframe_handle) {
          TSCH_LOG_ADD(tsch_log_message,
                       snprintf(log->message, sizeof(log->message),
                                "!asdERR wrong-sf!"));
          tsch_hack_errors++;
          return NULL;
        }

        // 1. Check the first packet in the queue
        // 2. Calculate TS and channel.
        uint16_t packet_slotframe = 0;
        uint16_t packet_timeslot = 0;
        uint16_t packet_channel_offset = 0;
        if(!scheduler_calculate_packet_cell(
            &packet_slotframe, &packet_timeslot, &packet_channel_offset, packet_qbuf)) {
          TSCH_LOG_ADD(tsch_log_message,
                       snprintf(log->message, sizeof(log->message),
                                "asdERR calc-err2!"));
          tsch_hack_errors++;
          return NULL;
        }

        // 3. Does packet match current link? If yes, transmit it.
        if(packet_timeslot == link->timeslot &&
            packet_channel_offset == link->channel_offset) {
          return n->tx_array[get_index];
        }

        // 4. Do hack and go through entire queue
        //    4.1. Calculate TS and channel
        //    4.2. Does it match current link? If yes, move to first of queue.
        //    4.3. Any packets without corresponding link? If yes, delete
        // TODO proper solution would be to implement per-flow queues

        // No need to go through queue if it is only the packet we checked above
        if(ringbufindex_elements(&n->tx_ringbuf) <= 1) {
          return NULL;
        }

        struct tsch_packet* packet_for_this_cell = NULL;
        packet_for_this_cell = hack2(n, link->timeslot, link->channel_offset);

        return packet_for_this_cell;

        // For debugging only
//        uint8_t p_seq_no = queuebuf_attr(packet_qbuf, PACKETBUF_ATTR_MAC_SEQNO);
        // 5. Transmit matching packet, or if none, return.
//        if(packet_for_this_cell == NULL) {
////                     TSCH_LOG_ADD(tsch_log_message,
////                                 snprintf(log->message, sizeof(log->message),
////                                     "!asdNO seq-no: %u, %u/%u",
////                                     p_seq_no,
////                                       link->timeslot,
////                                       link->channel_offset));
//          return NULL;
//        }
//        else {
//       //              int timeslot = queuebuf_attr(packet_for_this_timeslot->qb,
//       //                                           PACKETBUF_ATTR_TSCH_TIMESLOT);
//       //              uint8_t p_seq_no = queuebuf_attr(n->tx_array[get_index]->qb,
//       //                                               PACKETBUF_ATTR_MAC_SEQNO);
////                     TSCH_LOG_ADD(tsch_log_message,
////                                     snprintf(log->message, sizeof(log->message),
////                                         "!asdYES seq-no: %u, %u/%u",
////                                         p_seq_no,
////                                           link->timeslot,
////                                           link->channel_offset));
//          return packet_for_this_cell;
//        }
      }
    }
  }
  return NULL;
}
#else
/* Returns the first packet from a neighbor queue */
struct tsch_packet *
tsch_queue_get_packet_for_nbr(const struct tsch_neighbor *n, struct tsch_link *link)
{
  if(!tsch_is_locked()) {
    int is_shared_link = link != NULL && link->link_options & LINK_OPTION_SHARED;
    if(n != NULL) {
      int16_t get_index = ringbufindex_peek_get(&n->tx_ringbuf);
      if(get_index != -1 &&
          !(is_shared_link && !tsch_queue_backoff_expired(n))) {    /* If this is a shared link,
                                                                    make sure the backoff has expired */
#if TSCH_WITH_LINK_SELECTOR && !BUILD_WITH_LAYERED_FLOW
        int packet_attr_slotframe = queuebuf_attr(n->tx_array[get_index]->qb, PACKETBUF_ATTR_TSCH_SLOTFRAME);
        int packet_attr_timeslot = queuebuf_attr(n->tx_array[get_index]->qb, PACKETBUF_ATTR_TSCH_TIMESLOT);
        if(packet_attr_slotframe != 0xffff && packet_attr_slotframe != link->slotframe_handle) {
          return NULL;
        }
        if(packet_attr_timeslot != 0xffff && packet_attr_timeslot != link->timeslot) {
          return NULL;
        }
#endif
        return n->tx_array[get_index];
      }
    }
  }
  return NULL;
}
#endif
/*---------------------------------------------------------------------------*/
/* Returns the head packet from a neighbor queue (from neighbor address) */
struct tsch_packet *
tsch_queue_get_packet_for_dest_addr(const linkaddr_t *addr, struct tsch_link *link)
{
  if(!tsch_is_locked()) {
    return tsch_queue_get_packet_for_nbr(tsch_queue_get_nbr(addr), link);
  }
  return NULL;
}

#if BUILD_WITH_LAYERED_FLOW
static bool
neighbor_is_flow_neighbor(const struct tsch_neighbor *n) {
  return tsch_schedule_addr_is_for_flow(tsch_queue_get_nbr_address(n));
}
#endif

/*---------------------------------------------------------------------------*/
/* Returns the head packet of any neighbor queue with zero backoff counter.
 * Writes pointer to the neighbor in *n */
struct tsch_packet *
tsch_queue_get_unicast_packet_for_any(struct tsch_neighbor **n, struct tsch_link *link)
{
  if(!tsch_is_locked()) {
    struct tsch_neighbor *curr_nbr = (struct tsch_neighbor *)nbr_table_head(tsch_neighbors);
    struct tsch_packet *p = NULL;

    while(curr_nbr != NULL) {
#if BUILD_WITH_LAYERED_FLOW
      // Do not pick a flow-neighbor - we do not want flow-packets
      // on any other cells than the dedicated ones
      if(!curr_nbr->is_broadcast &&
          curr_nbr->tx_links_count == 0 &&
          !neighbor_is_flow_neighbor(curr_nbr)) {
#else
      if(!curr_nbr->is_broadcast && curr_nbr->tx_links_count == 0) {
#endif
        /* Only look up for non-broadcast neighbors we do not have a tx link to */
        p = tsch_queue_get_packet_for_nbr(curr_nbr, link);
        if(p != NULL) {
          if(n != NULL) {
            *n = curr_nbr;
          }

//          char address[10] = {0};
//          linkaddr_t *lladdr = &(link->addr);
//          if(lladdr == NULL || linkaddr_cmp(lladdr, &linkaddr_null)) {
//              sprintf(address, "LL-NULL");
//          }
//          else {
//            #if BUILD_WITH_DEPLOYMENT
//            sprintf(address, "LL-%04x", deployment_id_from_lladdr(lladdr));
//            #else /* BUILD_WITH_DEPLOYMENT */
//            #if LINKADDR_SIZE == 8
//            sprintf(address, "LL-%04x", UIP_HTONS(lladdr->u16[LINKADDR_SIZE/2-1]));
//            #elif LINKADDR_SIZE == 2
//            sprintf(address, "LL-%04x", UIP_HTONS(lladdr->u16));
//            #endif
//            #endif /* BUILD_WITH_DEPLOYMENT */
//          }
//
//          char address2[10] = {0};
//          lladdr = tsch_queue_get_nbr_address(*n);
//          if(lladdr == NULL || linkaddr_cmp(lladdr, &linkaddr_null)) {
//              sprintf(address2, "LL-NULL");
//          }
//          else {
//#if BUILD_WITH_DEPLOYMENT
//sprintf(address2, "LL-%04x", deployment_id_from_lladdr(lladdr));
//#else /* BUILD_WITH_DEPLOYMENT */
//#if LINKADDR_SIZE == 8
//sprintf(address2, "LL-%04x", UIP_HTONS(lladdr->u16[LINKADDR_SIZE/2-1]));
//#elif LINKADDR_SIZE == 2
//sprintf(address2, "LL-%04x", UIP_HTONS(lladdr->u16));
//#endif
//#endif /* BUILD_WITH_DEPLOYMENT */
//          }
//
//          TSCH_LOG_ADD(tsch_log_message,
//                        snprintf(log->message, sizeof(log->message),
//                            "asd! for any: %u/%u, a-l: %s, a-n: %s",
//                              link->timeslot,
//                              link->channel_offset, address, address2));
          return p;
        }
      }
      curr_nbr = (struct tsch_neighbor *)nbr_table_next(tsch_neighbors, curr_nbr);
    }
  }
  return NULL;
}
/*---------------------------------------------------------------------------*/
/* May the neighbor transmit over a shared link? */
int
tsch_queue_backoff_expired(const struct tsch_neighbor *n)
{
  return n->backoff_window == 0;
}
/*---------------------------------------------------------------------------*/
/* Reset neighbor backoff */
void
tsch_queue_backoff_reset(struct tsch_neighbor *n)
{
  n->backoff_window = 0;
  n->backoff_exponent = TSCH_MAC_MIN_BE;
}
/*---------------------------------------------------------------------------*/
/* Increment backoff exponent, pick a new window */
void
tsch_queue_backoff_inc(struct tsch_neighbor *n)
{
  /* Increment exponent */
  n->backoff_exponent = MIN(n->backoff_exponent + 1, TSCH_MAC_MAX_BE);
  /* Pick a window (number of shared slots to skip). Ignore least significant
   * few bits, which, on some embedded implementations of rand (e.g. msp430-libc),
   * are known to have poor pseudo-random properties. */
  n->backoff_window = (random_rand() >> 6) % (1 << n->backoff_exponent);
  /* Add one to the window as we will decrement it at the end of the current slot
   * through tsch_queue_update_all_backoff_windows */
  n->backoff_window++;
}
/*---------------------------------------------------------------------------*/
/* Decrement backoff window for all queues directed at dest_addr */
void
tsch_queue_update_all_backoff_windows(const linkaddr_t *dest_addr)
{
  if(!tsch_is_locked()) {
    int is_broadcast = linkaddr_cmp(dest_addr, &tsch_broadcast_address);
    struct tsch_neighbor *n = (struct tsch_neighbor *)nbr_table_head(tsch_neighbors);
    while(n != NULL) {
      if(n->backoff_window != 0 /* Is the queue in backoff state? */
         && ((n->tx_links_count == 0 && is_broadcast)
             || (n->tx_links_count > 0 && linkaddr_cmp(dest_addr, tsch_queue_get_nbr_address(n))))) {
        n->backoff_window--;
      }
      n = (struct tsch_neighbor *)nbr_table_next(tsch_neighbors, n);
    }
  }
}
/*---------------------------------------------------------------------------*/
/* Initialize TSCH queue module */
void
tsch_queue_init(void)
{
  nbr_table_register(tsch_neighbors, NULL);
  memb_init(&packet_memb);
  /* Add virtual EB and the broadcast neighbors */
  n_eb = tsch_queue_add_nbr(&tsch_eb_address);
  n_broadcast = tsch_queue_add_nbr(&tsch_broadcast_address);
}
/*---------------------------------------------------------------------------*/
/** @} */
