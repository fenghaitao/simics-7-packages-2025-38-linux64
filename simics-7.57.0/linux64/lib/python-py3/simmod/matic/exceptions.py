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


import simics

def debug_dump_mem(data, offs, length=0x10):
    ostr = ""
    for row in range(offs, offs + length, 8):
        ostr += "0x%08x: 0x" % row
        byvec = []
        max_col = min(8, len(data) - row)
        for col in range(max_col):
            val = data[row + col]
            if col > 0 and (col % 4) == 0:
                ostr += " "
                byvec.append(0x20)
            ostr += "%02x" % val
            if val < 0x20:
                byvec.append(0x2e)
            elif val >= 0x7f:
                byvec.append(0x2e)
            else:
                byvec.append(val)
        if max_col < 7:  # Add spaces to fill out the row
            left = 7 - max_col
            ostr += " " * (2 * left + left // 4)
            byvec += [0x20] * (left + left // 4)
        ostr += " [" + str(bytearray(byvec)) + "]\n"
    return ostr

class BufferException(Exception):
    def __init__(self, message, dump=None):
        self.text = message
        self.dump = dump

    def __str__(self):
        ostr = "%s: %s" % (self._my_class_name(), self.text)
        if self.dump:
            ostr += "\n%s" % self.dump
        return ostr

    def _my_class_name(self):
        return str(self.__class__).split("'")[1].rsplit('.', 1)[1]

class ChannelException(Exception):
    pass

class ManagerException(Exception):
    pass

class MaticException(Exception):
    pass

class JobException(Exception):
    pass

class JobDoneException(JobException):
    pass

class ProtError(Exception):
    """General Protocol error"""
    def __init__(self, buf, reason=None):
        self.buf = buf
        self.msg = reason if reason else self._my_class_name()
    def __str__(self):
        return "%s in %s" % (self.msg, self.buf)
    def _my_class_name(self):
        return str(self.__class__).split("'")[1].rsplit('.', 1)[1]

class ProtUnplyError(ProtError):
    """Unexpected protocol reply error"""
    def __init__(self, buf, expt):
        ProtError.__init__(self, buf, "Expected %s reply" % expt)

class ProtEndException(ProtError):
    """End of Protocol transaction reached"""
    def __init__(self):
        self.msg = "End of data"
        self.buf = self._my_class_name()

class ProtIOError(ProtError):
    """Protocol Data I/O Error"""
    def __init__(self, path, msg=None):
        self.msg = "Data I/O error for %s" % path
        self.msg += (": " + msg) if msg else ""
        self.buf = self._my_class_name()

class JobAsyncException(Exception):
    """This is an indication that the job has no new request at this time."""
    pass
