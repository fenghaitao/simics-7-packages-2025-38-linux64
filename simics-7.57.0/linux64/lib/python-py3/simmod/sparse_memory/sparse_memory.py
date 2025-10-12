# © 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import simics


class sparse_memory:
    """A memory in which every address can contain a byte or be empty.
    To be used, for example, when testing devices that do DMA. Empty
    addresses can be written, but not read. The memory can optionally
    be sized."""

    cls = simics.confclass(
        'sparse-memory', short_doc="sparse memory, for testing")
    cls.attr.size('i|n', default=None, doc="The size of the memory")
    cls.attr.mem('[[id]*]', default=list,
                 doc="""The chunks of data, a sorted list of discrete and
                 non-adjacent [offset, data] pairs.""")
    cls.attr.ignore_zero_sized_read(
        'b', default=False, kind=simics.Sim_Attr_Internal)

    @cls.attr.mem.getter
    def memget(self):
        return [[a, tuple(d)] for a, d in self.mem]

    @cls.attr.mem.setter
    def memset(self, value):
        self.mem = [(a, list(d)) for a, d in value]

    @cls.iface.transaction.issue
    def issue(self, t, addr):
        if t.read:
            return self._read(addr, t)
        else:
            return self._write(addr, t)

    def _read(self, addr, t):
        """Read n bytes starting at addr"""
        if t.size == 0 and self.ignore_zero_sized_read:
            return simics.Sim_PE_No_Exception
        if self.size is not None and addr + t.size > self.size:
            return simics.Sim_PE_IO_Not_Taken
        for (start, chunk) in self.mem:
            size = len(chunk)
            if (start <= addr < start + size and addr + t.size <= start + size):
                t.data = bytes(chunk[addr - start:addr - start + t.size])
                return simics.Sim_PE_No_Exception
        return simics.Sim_PE_IO_Not_Taken

    def _write(self, addr, t):
        """Write data to addr"""
        if self.size is not None and addr + t.size > self.size:
            return simics.Sim_PE_IO_Not_Taken
        for (i, (start, chunk)) in enumerate(self.mem):
            size = len(chunk)
            if start <= addr <= start + size:
                chunk[addr - start:addr - start + t.size] = list(t.data)
                self._merge(i)
                return simics.Sim_PE_No_Exception

            if start > addr:
                break  # insert new chunk here
        else:
            i = len(self.mem)
        self.mem[i:i] = [(addr, list(t.data))]  # create new chunk
        self._merge(i)
        return simics.Sim_PE_No_Exception

    def _merge(self, index):
        """Merge chunk with the following one if it overlaps or touches"""
        (start, chunk) = self.mem[index]
        end = start + len(chunk)
        nxt = index + 1
        while nxt < len(self.mem):
            (nxt_start, nxt_chunk) = self.mem[nxt]
            if nxt_start > end:
                break
            # this chunk subsumed by the one at index
            if end < nxt_start + len(nxt_chunk):
                chunk += nxt_chunk[end - nxt_start:]
            del self.mem[nxt]
