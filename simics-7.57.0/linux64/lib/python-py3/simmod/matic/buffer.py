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


import sys
import struct
import array
from . import exceptions as ex
from simicsutils.internal import ensure_binary

class MaticBuffer:
    """MaTIC buffer class"""

    majorvec = [
        (0, 0xb6cde764dc5add),
        (1, 0x1b90f02e10d514) ]
    codedb = {
        0x0000: "announce-agent",
        0x0010: "set-poll-interval",
        0x0020: "time-get",
        0x0030: "file-open",
        0x0040: "file-stat",
        0x0050: "file-link",
        0x0060: "file-make",
        0x1020: "file-perm",
        0x00f0: "file-remove",
        0x0100: "ticket-discard",
        0x0110: "ticket-read",
        0x0120: "ticket-write",
        0x0130: "ticket-sync-write",
        0x0150: "ticket-getpos",
        0x0160: "ticket-setpos",
        0x1000: "time-set",
        0x1010: "read-dir",
        0x1030: "make-dir",
        0x17f0: "restart-agent",
        0x1800: "process-open",
        0xfff0: "quit-agent",
        }
    respdb = {
        0x0: "request",
        0x1: "ok",
        0x2: "data",
        0x3: "ticket",
        0x4: "custom",
        0xe: "error",
        0xf: "failure",
        }
    HEADSIZE = 16
    debug = False

    def __init__(self, pipe, bufh):
        self.rdif = pipe.iface.magic_pipe_reader
        self.wrif = pipe.iface.magic_pipe_writer
        self.bufh = bufh
        self._set_byte_order()
        used = self.rdif.read_buffer_size(bufh)
        self.size = self.wrif.write_buffer_size(bufh)
        if used:
            self.data = bytearray(self.rdif.read_data_copy(bufh, 0, used))
            self._read_header()
        else:
            self.data = bytearray()
            self.reset_magic()
            self.code = 0
            self.num = 0

    def _set_byte_order(self):
        if sys.byteorder == 'little':
            if self.rdif.is_byte_swap_needed(self.bufh):
                self._bo = ">"  # big-endian
            else:
                self._bo = "<"  # little-endian
        elif sys.byteorder == 'big':
            if self.rdif.is_byte_swap_needed(self.bufh):
                self._bo = "<"  # little-endian
            else:
                self._bo = ">"  # big-endian
        else:
            raise ex.BufferException('Unknown system byte order: %s'
                                     % sys.byteorder)

    def __str__(self):
        (req, rno) = self._get_request()
        (ply, pno) = self._get_response()
        return "matic buffer (0x%016x) size=%d %s-%s (0x%03x_%x) number %d" % (
            self.magic, len(self.data), req, ply, rno, pno, self.num)

    def _dump_header(self):
        return ex.debug_dump_mem(self.data, 0, self.HEADSIZE)

    def _dump_payload(self, length=None):
        if not length:
            length = len(self.data) - self.HEADSIZE
        if length < 1:
            return ""
        return ex.debug_dump_mem(self.data, self.HEADSIZE, length)

    def _max_data_size(self):
        return self.size - MaticBuffer.HEADSIZE

    def _read_bytevec(self, size, offset):
        if offset >= len(self.data):
            raise ex.BufferException("Offset outside of valid data: offset=%d"
                                     " >= size=%d" % (offset, len(self.data)))
        if offset + size > len(self.data):
            raise ex.BufferException("Size is larger than available data: offset"
                                     " %d + size %d = %d > valid %d"
                                     % (offset, size, offset + size,
                                        len(self.data)))
        return self.data[offset : offset + size]

    def _read_struct(self, offset, fmt):
        raw_size = struct.calcsize(fmt)
        raw_arry = self._read_bytevec(raw_size, offset)
        raw_data = array.array("B", raw_arry)
        return struct.unpack_from("%s%s" % (self._bo, fmt), raw_data)

    def _read_header(self):
        (self.magic, _, self.code, self.num) = self._read_struct(0, "QHHI")
        for (major, magic) in self.majorvec:
            majic = self.magic >> 8
            if majic == magic:
                self.major = major
                self.minor = self.magic & 0xff
                self.vers = "%d.%d" % (self.major, self.minor)
        if len(self.data) > self.size:
            raise ex.BufferException("Illegal payload data size: %d"
                                     % len(self.data), self._dump_header())

    def _reset_data(self):
        self.data = bytearray([0] * self.HEADSIZE)

    def _write_bytevec(self, data, offset):
        if offset >= self.size:
            raise ex.BufferException("Offset outside of buffer: offset=%d >="
                                     " size=%d" % (offset, self.size))
        left = self.size - offset
        if len(data) > left:
            data = data[:left]
        more = offset + len(data) - len(self.data)
        if more > 0:
            self.data.extend([0] * more)
            self.update_length()
        self.data[offset : offset + len(data)] = data
        return len(data)

    def _write_struct(self, offset, fmt, *args):
        packed_data = struct.pack("%s%s" % (self._bo, fmt), *args)
        return self._write_bytevec(packed_data, offset)

    def _write_commit(self):
        s = bytes(self.data)
        self.wrif.write_data_copy(self.bufh, s)

    def _get_request(self):
        req_name = self.codedb.get(self.code & 0xfff0, "<unknown>")
        return (req_name, self.code >> 4)

    def _get_response(self):
        respname = self.respdb.get(self.code & 0xf, "<response>")
        return (respname, self.code & 0xf)

    def _set_request_by_name(self, name):
        for (code, req) in list(self.codedb.items()):
            if name == req:
                self.code = code
                self._write_struct(10, "H", code)
                return
        raise ex.BufferException("Unknown request: %s" % name)

    def _set_request_code(self, code):
        if code not in self.codedb:
            raise ex.BufferException("Invalid request code %x" % code)
        self.code = code
        self._write_struct(10, "H", self.code)

    def data_length(self):
        return len(self.data) - self.HEADSIZE

    def space_left(self):
        return self.size - len(self.data)

    def update_length(self):
        assert self.size >= len(self.data)
        self._write_struct(8, "H", self.data_length())

    def reset_magic(self, vers=None):
        if vers != None:
            for (v, major) in self.majorvec:
                if vers == v:
                    self.magic = major << 8
                    return
            raise ex.BufferException("Unknown major version number %d" % vers)
        (v, major) = self.majorvec[-1]
        self.magic = major << 8

    def new_request(self, code, num):
        resp = code & 0xf
        if resp:
            raise ex.BufferException("Response code %s attempted for a request"
                                     % hex(resp))
        self.data = bytearray([0] * self.HEADSIZE)
        self.code = code
        self.num = num
        assert self.data_length() == 0
        self._write_struct(0, "QHHI",
                           self.magic, self.data_length(), self.code, self.num)

    def get_request_name(self):
        return self.codedb[self.code & 0xfff0]

    def is_request(self, req=None):
        if req is None:
            return (self.code & 0xf) == 0
        if isinstance(req, str):
            for code in self.codedb:
                if req == self.codedb[code]:
                    return (self.code & 0xfff0) == code
            return False
        if isinstance(req, list):
            return (self.code & 0xfff0) in [(x & 0xfff0) for x in req]
        return (self.code & 0xfff0) == (req & 0xfff0)

    def is_response(self, resp=None):
        if resp is None:
            return (self.code & 0xf) != 0
        if isinstance(resp, list):
            return (self.code & 0xf) in [(x & 0xf) for x in resp]
        return (self.code & 0xf) == (resp & 0xf)

    def is_code(self, expt):
        if isinstance(expt, list):
            return self.code in expt
        return self.code == expt

    def read_binary(self, offset=0):
        offset += self.HEADSIZE
        used = len(self.data) - offset
        return self._read_bytevec(used, offset)

    def read_string(self, offset=0):
        offset += self.HEADSIZE
        if offset == len(self.data):
            return ""
        if offset > len(self.data):
            raise ex.BufferException(
                "Read offset %d is outside of data size %d"
                % (offset, len(self.data)))
        end = offset
        while end < len(self.data) and self.data[end]:
            end += 1
        return bytes(self.data[offset : end]).decode('utf-8', errors='replace')

    def read_struct(self, offset, fmt):
        offset += self.HEADSIZE
        return self._read_struct(offset, fmt)

    def set_response_code(self, num):
        self.code = (self.code & 0xfff0) | (num & 0xf)
        self._write_struct(10, "H", self.code)

    def write_binary(self, data):
        size = self._write_bytevec(data, len(self.data))
        return size

    # Does not support unicode strings
    def write_string(self, text):
        left = self.space_left()
        if left <= 0:
            raise ex.BufferException(
                "No space left in buffer: left=%d (of %d)"
                % (left, self._max_data_size()))
        raw = bytearray(ensure_binary(text))[:left]
        if len(raw) < left:
            raw.extend([0])  # Add a terminator, at the end, if it fits
        return self._write_bytevec(raw, len(self.data))

    def write_struct(self, fmt, *args):
        return self._write_struct(len(self.data), fmt, *args)

    def get_error(self):
        errmsg = self.next_string()
        errnfo = self.next_string()
        return (self.num, errmsg, errnfo)

    def next_string(self):
        if not hasattr(self, "_stroffs"):
            self._stroffs = 0
        if self._stroffs >= self.data_length():
            return None
        text = self.read_string(self._stroffs)
        if not text:
            return None
        self._stroffs += len(text) + 1
        return text

    def next_ticket(self):
        if not hasattr(self, "_toffs"):
            self._toffs = 0
        if self._toffs >= self.data_length():
            return None
        (size, ticket, mode) = self.read_struct(self._toffs, "QIH")
        offs = self._toffs + 14
        name = self.read_string(offs)
        offs += len(name) + 1
        self._toffs = (offs + 7) & 0xfff8
        return (size, ticket, mode, name)

    def parse_info(self):
        info = {}
        while True:
            k = self.next_string()
            if not k:
                break
            v = self.next_string()
            info[k] = v
        return info
