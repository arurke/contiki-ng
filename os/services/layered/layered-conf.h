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
 *         Layered configuration
 *
 * \author Simon Duquennoy <simonduq@sics.se>
 */

#ifndef __LAYERED_CONF_H__
#define __LAYERED_CONF_H__

#include "project-conf.h"
#include <stdint.h>

#ifdef LOG_CONF_LEVEL_LAYERED
#define LOG_LEVEL_LAYERED   LOG_CONF_LEVEL_LAYERED
#else
#define LOG_LEVEL_LAYERED   LOG_LEVEL_INFO
#endif

#ifdef LAYERED_CONF_RULES
#define LAYERED_RULES LAYERED_CONF_RULES
#else /* LAYERED_CONF_RULES */
#define LAYERED_RULES { &layered_multi_channel }
#endif /* LAYERED_CONF_RULES */

// Including sink
#ifdef LAYERED_CONF_MAX_NUM_NODES
#define LAYERED_MAX_NUM_NODES       LAYERED_CONF_MAX_NUM_NODES
#else
#define LAYERED_MAX_NUM_NODES       50
#endif

#ifdef LAYERED_CONF_NUM_LAYERS
#define LAYERED_NUM_LAYERS      LAYERED_CONF_NUM_LAYERS
#else
#define LAYERED_NUM_LAYERS      2
#endif

#ifdef LAYERED_CONF_COMMON_SLOT_SPACING
#define LAYERED_COMMON_SLOT_SPACING   LAYERED_CONF_COMMON_SLOT_SPACING
#else
#define LAYERED_COMMON_SLOT_SPACING   37
#endif

#ifdef LAYERED_CONF_CHANNELS
#define LAYERED_CHANNELS              LAYERED_CONF_CHANNELS
#else
#define LAYERED_CHANNELS              (uint8_t[]){1,2}
#endif

#define LAYERED_NUM_CHANNELS          sizeof(LAYERED_CHANNELS)

// Num nodes * num layers + any common slots
#define COMMON_SLOT_SPACING     LAYERED_COMMON_SLOT_SPACING
#define LAYERED_RAW_SF_LEN      (LAYERED_MAX_NUM_NODES * LAYERED_NUM_LAYERS)
#define NUM_COMMON_SLOTS        (LAYERED_RAW_SF_LEN / COMMON_SLOT_SPACING)
#define LAYERED_SF_LEN          (LAYERED_RAW_SF_LEN + NUM_COMMON_SLOTS)
#define SCHED_SLOTFRAME_LEN     LAYERED_SF_LEN

/* The hash function used to assign timeslot to a given node (based on its link-layer address).
 * For rules with multiple channel offsets, it is also used to select the channel offset. */
#ifdef LAYERED_CONF_LINKADDR_HASH
#define LAYERED_LINKADDR_HASH                     LAYERED_CONF_LINKADDR_HASH
#else /* LAYERED_CONF_LINKADDR_HASH */
#if BUILD_WITH_DEPLOYMENT
#include "services/deployment/deployment.h"
#define LAYERED_LINKADDR_HASH(addr)               deployment_id_from_lladdr(addr)
#else
#define LAYERED_LINKADDR_HASH(addr)               ((addr != NULL) ? (addr)->u8[LINKADDR_SIZE - 1] : -1)
#endif
#endif /* LAYERED_CONF_LINKADDR_HASH */

#endif /* __LAYERED_CONF_H__ */
