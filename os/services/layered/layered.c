/*
 * Copyright (c) 2015, Swedish Institute of Computer Science.
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
 */

/**
 * \file
 *
 * \author Simon Duquennoy <simonduq@sics.se>
 */

#include "layered.h"

#if ROUTING_CONF_RPL_LITE
#error Only RPL CLASSIC supported
#endif

#include "contiki.h"
#include "net/packetbuf.h"
#include "net/ipv6/uip-icmp6.h"
#include "net/routing/routing.h"
#if ROUTING_CONF_RPL_CLASSIC
#include "net/routing/rpl-classic/rpl.h"
#include "net/routing/rpl-classic/rpl-private.h"
#endif

#include "sys/log.h"
#define LOG_MODULE "Layered"
#define LOG_LEVEL   LOG_LEVEL_LAYERED

/* The set of Layered rules in use */
const struct layered_rule *all_rules[] = LAYERED_RULES;
#define NUM_RULES (sizeof(all_rules) / sizeof(struct layered_rule *))

/*---------------------------------------------------------------------------*/
void
layered_callback_child_added(const linkaddr_t *addr)
{
  /* Notify all rules that a child was added */
  int i;
  for(i = 0; i < NUM_RULES; i++) {
    if(all_rules[i]->child_added != NULL) {
      all_rules[i]->child_added(addr);
    }
  }
}
/*---------------------------------------------------------------------------*/
void
layered_callback_child_removed(const linkaddr_t *addr)
{
  /* Notify all rules that a child was removed */
  int i;
  for(i = 0; i < NUM_RULES; i++) {
    if(all_rules[i]->child_removed != NULL) {
      all_rules[i]->child_removed(addr);
    }
  }
}
/*---------------------------------------------------------------------------*/
int
layered_callback_packet_ready(void)
{
  int i;
  /* By default, use any slotframe, any timeslot */
  uint16_t slotframe = 0xffff;
  uint16_t timeslot = 0xffff;
  /* The default channel offset 0xffff means that the channel offset in the scheduled
   * tsch_link structure is used instead. Any other value specified in the packetbuf
   * overrides per-link value, allowing to implement multi-channel */
  uint16_t channel_offset = 0xffff;
  int matched_rule = -1;

  /* Loop over all rules until finding one able to handle the packet */
  for(i = 0; i < NUM_RULES; i++) {
    if(all_rules[i]->select_packet != NULL) {
      if(all_rules[i]->select_packet(&slotframe, &timeslot, &channel_offset)) {
        matched_rule = i;
        break;
      }
    }
  }

  // TODO it seems this is not needed anymore as
  // 1. TSCH does not need the packet-ready to find correct ts/ch
  // 2. packet-type is set by TSCH
  // 3. ts/ch for stats is found via used_link

//#if TSCH_WITH_LINK_SELECTOR
  // Add attributes regardless because we use them for stats
  packetbuf_set_attr(PACKETBUF_ATTR_TSCH_SLOTFRAME, slotframe);
  packetbuf_set_attr(PACKETBUF_ATTR_TSCH_TIMESLOT, timeslot);
  packetbuf_set_attr(PACKETBUF_ATTR_TSCH_CHANNEL_OFFSET, channel_offset);
//#endif

  return matched_rule;
}
/*---------------------------------------------------------------------------*/
void
layered_callback_new_time_source(const struct tsch_neighbor *old,
                                 const struct tsch_neighbor *new)
{
  /* Assumes that the time source is also the RPL parent.
   * This is the case if the following is set:
   * #define RPL_CALLBACK_PARENT_SWITCH tsch_rpl_callback_parent_switch
   * */
  int i;
  for(i = 0; i < NUM_RULES; i++) {
    if(all_rules[i]->new_time_source != NULL) {
      all_rules[i]->new_time_source(old, new);
    }
  }
}
/*---------------------------------------------------------------------------*/
void
layered_init(void)
{
  int i;
  /* Initialize all rules */
  for(i = 0; i < NUM_RULES; i++) {
    LOG_INFO("Initializing rule %s (%u)\n", all_rules[i]->name, i);
    if(all_rules[i]->init != NULL) {
      all_rules[i]->init(i);
    }
  }

  LOG_INFO("Max nodes %u, layers %u, channels %lu, common slots %d, SF len %u\n",
           LAYERED_MAX_NUM_NODES, LAYERED_NUM_LAYERS,
           (unsigned long) LAYERED_NUM_CHANNELS,
           NUM_COMMON_SLOTS, LAYERED_SF_LEN);
}
