/*
  crc.c

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <simics/device-api.h>
#include "crc.h"

static uint32 *ethernet_crc_table = NULL;

void
init_ethernet_crc_table()
{
        if (ethernet_crc_table)
                return;

        uint32 polynomial = 0x04c11db7;
        int i;
        int j;

        ethernet_crc_table = MM_MALLOC(0x100, uint32);

        for (i = 0; i <= 0xff; i++) {
                ethernet_crc_table[i] = (uint32)reverse_bits8(i) << 24;
                for (j = 0; j < 8; j++)
                        ethernet_crc_table[i] = (ethernet_crc_table[i] << 1)
                                ^ (ethernet_crc_table[i] & ((uint32)1 << 31)
                                   ? polynomial : 0);
                ethernet_crc_table[i] = reverse_bits32(ethernet_crc_table[i]);
        }
}

FORCE_INLINE uint32
incremental_crc(uint32 crc, const uint8 *buf, size_t buflen, bool reverse_bits)
{
        for (size_t i = 0; i < buflen; i++)
                crc = (crc >> 8) ^ ethernet_crc_table[(crc & 0xff)
                                                      ^ (reverse_bits
                                                         ? reverse_bits8(buf[i])
                                                         : buf[i])];
        return crc;
}

FORCE_INLINE uint32
ethernet_crc_inline_dbuf(dbuffer_t *frame, size_t start, size_t length,
                         bool reverse_bits)
{
        uint32 crc = 0xffffffff;
        size_t end = start + length;
        size_t index = start;

        while (index < end) {
                size_t read_length;
                const uint8 *read_buffer =
                        dbuffer_read_some(frame, index, end - index,
                                          &read_length);
                crc = incremental_crc(crc, read_buffer, read_length,
                                      reverse_bits);
                index += read_length;
        }

        return crc ^ 0xffffffff;
}

uint32
ethernet_crc_dbuf(dbuffer_t *frame, size_t start, size_t length)
{
        return ethernet_crc_inline_dbuf(frame, start, length, false);
}

uint32
token_ring_crc_dbuf(dbuffer_t *frame, size_t start, size_t length)
{
        /* The Token Ring CRC is calculated just like the Ethernet CRC, but the
           bits in each byte are reversed. */
        return ethernet_crc_inline_dbuf(frame, start, length, true);
}

uint32
get_ethernet_crc_dbuf(dbuffer_t *frame)
{
        size_t len = dbuffer_len(frame);
        return UNALIGNED_LOAD_LE32(dbuffer_read(frame, len - 4, 4));
}

void
update_ethernet_crc_dbuf(dbuffer_t *frame)
{
        size_t len = dbuffer_len(frame);
        uint32 crc = ethernet_crc_dbuf(frame, 0, len - 4);
        UNALIGNED_STORE_LE32(dbuffer_replace(frame, len - 4, 4), crc);
}

// Frags versions:

FORCE_INLINE uint32
ethernet_crc_inline_frags(const frags_t *frame, size_t start, size_t length,
                          bool reverse_bits)
{
        uint32 crc = 0xffffffff;
        for (frags_it_t it = frags_it(frame, start, length);
             !frags_it_end(it);
             it = frags_it_next(it))
                crc = incremental_crc(crc,
                                      frags_it_data(it),
                                      frags_it_len(it),
                                      reverse_bits);

        return crc ^ 0xffffffff;
}

uint32
ethernet_crc_frags(const frags_t *frame, size_t start, size_t length)
{
        return ethernet_crc_inline_frags(frame, start, length, false);
}

uint32
token_ring_crc_frags(const frags_t *frame, size_t start, size_t length)
{
        /* The Token Ring CRC is calculated just like the Ethernet CRC, but the
           bits in each byte are reversed. */
        return ethernet_crc_inline_frags(frame, start, length, true);
}

uint32
get_ethernet_crc_frags(const frags_t *frame)
{
        return frags_extract_le32(frame, frags_len(frame) - 4);
}

