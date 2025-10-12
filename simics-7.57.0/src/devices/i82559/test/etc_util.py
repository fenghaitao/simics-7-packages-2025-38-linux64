# © 2012 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from functools import reduce

# Convert a 16-bit value to 2 bytes in little-endian order
def value_to_bytes_le16(val):
    return tuple((val >> (i * 8)) & 0xFF for i in range(2))

# Convert a 16-bit value to 2 bytes in big-endian order
def value_to_bytes_be16(val):
    return tuple((val >> ((1 - i) * 8)) & 0xFF for i in range(2))

# Convert a 32-bit value to 4 bytes in little-endian order
def value_to_bytes_le32(val):
    return tuple((val >> (i * 8)) & 0xFF for i in range(4))

# Convert a 32-bit value to 4 bytes in big-endian order
def value_to_bytes_be32(val):
    return tuple((val >> ((3 - i) * 8)) & 0xFF for i in range(4))

# Convert a 64-bit value to 8 bytes in little-endian order
def value_to_bytes_le64(val):
    return tuple((val >> (i * 8)) & 0xFF for i in range(8))

# Convert a 64-bit value to 8 bytes in big-endian order
def value_to_bytes_be64(val):
    return tuple((val >> ((7 - i) * 8)) & 0xFF for i in range(8))

# Convert 2 bytes in little-endian order to a 16-bit value
def bytes_to_value_le16(bytes):
    return reduce(lambda a, b: a << 8 | b, reversed(bytes))

# Convert 2 bytes in big-endian order to a 16-bit value
def bytes_to_value_be16(bytes):
    return reduce(lambda a, b: (a << 8) | b, bytes)

# Convert 4 bytes in little-endian order to a 32-bit value
def bytes_to_value_le32(bytes):
    return reduce(lambda a, b: a << 8 | b, reversed(bytes))

# Convert 4 bytes in big-endian order to a 32-bit value
def bytes_to_value_be32(bytes):
    return reduce(lambda a, b: (a << 8) | b, bytes)

# Convert 8 bytes in little-endian order to a 64-bit value
def bytes_to_value_le64(bytes):
    return reduce(lambda a, b: (a << 8) | b, reversed(bytes))

# Convert 8 bytes in big-endian order to a 64-bit value
def bytes_to_value_be64(bytes):
    return reduce(lambda a, b: (a << 8) | b, bytes)


# Test failure class
class Test_failure(Exception): pass
def expect(got, expected):
    if got != expected:
        raise Test_failure("got %s, expected %s" % (got, expected))
def expect_hex(got, expected):
    if got != expected:
        raise Test_failure("got 0x%x, expected 0x%x" % (got, expected))

import dev_util

class X_Bitfield_LE(dev_util.Bitfield_LE):
    def value_from_fields(self, fields):
        value = 0
        for key in list(fields.keys()):
            (start, stop) = self.field_ranges[key]

            assert(0 <= fields[key] and fields[key] < (1 << (stop + 1 - start)))

            # Insert field into final value
            value |= fields[key] << start
        return value | self.ones

# Converter between ethernet frame and Simics db buffer
def eth_to_db(eth_frame):
    return "".join(map(chr, eth_frame))

def db_to_eth(db_buffer):
    return list(map(ord, db_buffer))
