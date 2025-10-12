# © 2018 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import struct
import binascii

class PcapFileException(Exception): pass

class pcap_hdr:
    size = 24
    def __init__(self, buf, byte_order_prefix):
        (magic_number, version_major, version_minor, thiszone, sigfigs,
         snaplen, network) = struct.unpack_from(byte_order_prefix +"IHHiIII",
                                                buf)
        self.magic_number = magic_number
        self.version_major = version_major
        self.thiszone = thiszone
        self.sigfigs = sigfigs
        self.snaplen = snaplen
        self.network = network


class pcaprec_hdr:
    size = 16
    def __init__(self, buf, byte_order_prefix, has_nano_sec = False):
        (ts_sec, ts_usec, incl_len,
         orig_len) = struct.unpack_from(byte_order_prefix + "IIII", buf)
        self.ts_sec = ts_sec
        self.ts_usec = ts_usec
        self.incl_len = incl_len
        self.orig_len = orig_len
        self.has_nano_sec = has_nano_sec

class Packet:
    def __init__(self, header, data):
        self.header = header
        self.data = data
        self.crc_appended = False

    def get_time(self):
        return (float(self.header.ts_sec)
                + ((float(self.header.ts_usec) / 1000000000.0) \
                if self.header.has_nano_sec else \
                   (float(self.header.ts_usec) / 1000000.0)))

    def calculate_crc(self):
        checksum = binascii.crc32(self.data[:-4])
        self.data = self.data[:-4] + struct.pack("i", checksum)

    def append_crc(self):
        if self.crc_appended:
            return
        self.data += b"\x00\x00\x00\x00"
        self.crc_appended = True

    def correct_crc(self):
        checksum = binascii.crc32(self.data[:-4])
        return self.data[-4:] == struct.pack("I", checksum)

    def has_nano_sec_resolution(self):
        return self.header.has_nano_sec

def parse_pcap(filename):
    def nextPacket(file, has_nano_sec):
        header_data = file.read(pcaprec_hdr.size)
        if not header_data:
            return None
        hdr = pcaprec_hdr(header_data, byte_order, has_nano_sec)
        packet_data = file.read(hdr.incl_len)
        if not packet_data:
            raise PcapFileException("pcap file truncated")
        return Packet(hdr, packet_data)

    packets = []

    try:
        f = open(filename, 'rb')
    except IOError:
        raise PcapFileException("Failed to open %s" % filename)

    ghdr_data = f.read(pcap_hdr.size)
    if not ghdr_data:
        raise PcapFileException("Failed reading global header from %s"
                                % filename)
    byte_order = "<"
    global_header = pcap_hdr(ghdr_data, byte_order)
    if (global_header.magic_number != 0xa1b2c3d4
        # for nano-second support
        and global_header.magic_number != 0xa1b23c4d):
        byte_order = ">"
        global_header = pcap_hdr(ghdr_data, byte_order)
        if (global_header.magic_number != 0xa1b2c3d4
            and global_header.magic_number != 0xa1b23c4d):
            raise PcapFileException("pcap magic mismatch")

    if global_header.magic_number == 0xa1b2c3d4:
        has_nano_sec = False
    else: # global_header.magic_number == 0xa1b23c4d:
        has_nano_sec = True

    while True:
        packet = nextPacket(f, has_nano_sec)
        if packet == None:
            break
        packets.append(packet)

    f.close()
    return packets
