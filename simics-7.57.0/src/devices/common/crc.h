/*
  crc.h

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef CRC_H
#define CRC_H

#include <simics/util/dbuffer.h>
#include <simics/util/frags.h>

#if defined(__cplusplus)
extern "C" {
#endif

/* Calculate CRC for a frame (excluding the CRC itself) */
uint32 ethernet_crc_dbuf(dbuffer_t *frame, size_t start, size_t length);
uint32 token_ring_crc_dbuf(dbuffer_t *frame, size_t start, size_t length);

/* Return the CRC for an ethernet frame */
uint32 get_ethernet_crc_dbuf(dbuffer_t *frame);

/* Recalculate the CRC for a frame and write it in the last four bytes */
void update_ethernet_crc_dbuf(dbuffer_t *frame);

uint32 ethernet_crc_frags(const frags_t *frame, size_t start, size_t length);
uint32 token_ring_crc_frags(const frags_t *frame, size_t start, size_t length);
uint32 get_ethernet_crc_frags(const frags_t *frame);

void init_ethernet_crc_table();

#if defined(__cplusplus)
}
#endif

#endif  /* ! CRC_H */
