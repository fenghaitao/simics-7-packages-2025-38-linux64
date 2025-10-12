# © 2017 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# The operation classes in this file encapsulates transactions with the Simics
# Agent. These transactions can consist of one or more request response pairs.
# The classes will craft and parse the protocol messages and store all the
# information passed to and from the Simics Agent.
#

import os
import stat
import time
from . import exceptions as ex
import ntpath, posixpath

class ProtOp:
    """The base class for all protocol operations/messages."""
    name = "prot-op"
    request = 0
    msgs = {
        0x0: "request",
        0x1: "ok",
        0x2: "data",
        0x3: "ticket",
        0xe: "error",
        0xf: "failure",
    }
    def __init__(self):
        self.req = 0
        self.ply = 0
        self.last = False
        self.error = False
    def __str__(self):
        return "%s<%s>" % (self.name, self.get_state())
    def _code_name(self, code=None):
        return "%s-%s" % (self.name,
                          self.msgs[code if code else self.request])
    def check_request(self, buf):
        self.req += 1
        if buf.code != self.request:
            raise ex.ProtUnplyError(buf, "non-request %s-%s" % (
                self.name, self.msgs[self.request]))
    def parse_reply_code(self, buf):
        self.ply += 1
        if buf.code == self.request:
            raise ex.ProtUnplyError(buf, "non-request %s-%s" % (
                self.name, self.msgs[self.request]))
        try:
            return self.msgs[buf.code]
        except KeyError:
            codes = [c for c in self.msgs if c != self.request]
            expt = "either a %s-" % self.name
            expt += "/-".join([self.msgs[c] for c in codes])
            raise ex.ProtUnplyError(buf, expt)
    def is_mine(self, buf):
        return buf.code in self.msgs
    def is_started(self):
        return self.req > 0
    def is_active(self):
        return self.req > self.ply
    def failed(self):
        return self.error
    def succeeded(self):
        return not self.error
    def is_done(self):
        return self.last or self.error
    def get_state(self):
        if self.failed():
            return "failed"
        if self.is_done():
            return "done"
        if self.is_active():
            return "active"
        if self.is_started():
            return "started"
        return "ready"
    def parse_reply(self, buf):
        """Handle the reply message."""
        assert buf == None  # This should never be executed
    def send_request(self, buf):
        """Create the request message."""
        assert buf == None  # This should never be executed

class StatOp(ProtOp):
    """File (stat) information for one target file.

    This operation will send a request for file (stat) information to the target
    and then parse and store the result. Only the portable least common
    denominator of the information will be transmitted.

    This includes:
      - file type (regular file or directory)
      - file size (in bytes)
      - last modification time (float seconds, since the epoch)

    """
    name = "file-stat"
    request = 0x0040
    msgs = {
        0x0040: "request",
        0x0041: "ok",
        0x004e: "error",
    }
    def __init__(self, relfile, targfile, hostfile, follow=False, local=True):
        ProtOp.__init__(self)
        self.rpath = relfile   # Relative path
        self.hpath = hostfile  # Local file path on host
        self.local = local  # Whether the source file is local or remote
        self.hstat = None
        if local or self.local_exists():
            self.hstat = os.stat(self.hpath) if follow else os.lstat(self.hpath)
        self.tpath = targfile  # Remote target system path
        self.exists = None  # Whether target file exists, or not
        # Target stat values
        self.mode = 0
        self.size = 0
        self.s = 0
        self.ns = 0
    def __str__(self):
        op = "%s(%s)" % (ProtOp.__str__(self), self.rpath)
        if not self.local:
            tgtype = (self.get_target_type() if self.target_exists() else
                      "not found") if self.is_done() else "still unknown"
            return "%s: %s (on target %s)" % (op, tgtype, self.tpath)
        return "%s: %s (on host %s)" % (op, self.get_host_type(), self.hpath)
    def send_request(self, buf):
        buf.new_request(self.request, 0)
        buf.write_string(self.tpath)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        if msg == "ok":
            self.exists = True
            self.mode = buf.num
            (self.size, self.s, self.ns) = buf.read_struct(0, "QQQ")
        else:
            assert msg == "error", "got %s in %s" % (msg, buf)
            if buf.num in (0, 2):  # No such file or directory
                self.exists = False
            else:
                self.error = True
        self.last = True

    def _mode(self):
        return self.hstat.st_mode if self.local else self.mode
    def is_blkdev(self):
        return stat.S_ISBLK(self._mode())
    def is_chardev(self):
        return stat.S_ISCHR(self._mode())
    def is_dir(self):
        return stat.S_ISDIR(self._mode())
    def is_file(self):
        return stat.S_ISREG(self._mode())
    def is_special(self):
        return (self.is_blkdev() or self.is_chardev() or self.is_pipe()
                or self.is_socket())
    def is_pipe(self):
        return stat.S_ISFIFO(self._mode())
    def is_socket(self):
        return stat.S_ISSOCK(self._mode())
    def is_softlink(self):
        return stat.S_ISLNK(self._mode())

    def _file_type(self, mode):
        if stat.S_ISBLK(mode):
            return "block device"
        if stat.S_ISCHR(mode):
            return "character device"
        if stat.S_ISDIR(mode):
            return "directory"
        if stat.S_ISFIFO(mode):
            return "named pipe"
        if stat.S_ISREG(mode):
            return "regular file"
        if stat.S_ISSOCK(mode):
            return "socket"
        if stat.S_ISLNK(mode):
            return "symbolic link"
        return "unknown type"
    def _same_type(self, mode1, mode2):
        if stat.S_ISDIR(mode1) and stat.S_ISDIR(mode2):
            return True
        if stat.S_ISREG(mode1) and stat.S_ISREG(mode2):
            return True
        if stat.S_ISLNK(mode1) and stat.S_ISLNK(mode2):
            return True
        if stat.S_ISCHR(mode1) and stat.S_ISCHR(mode2):
            return True
        if stat.S_ISBLK(mode1) and stat.S_ISBLK(mode2):
            return True
        if stat.S_ISFIFO(mode1) and stat.S_ISFIFO(mode2):
            return True
        if stat.S_ISSOCK(mode1) and stat.S_ISSOCK(mode2):
            return True
        return False

    def local_exists(self):
        return os.path.exists(self.hpath)
    def target_exists(self):
        return self.exists
    def is_newer(self):
        return self._float_time() > self.hstat.st_mtime
    def is_same_size(self):
        return self.hstat.st_size == self.size
    def is_same_time(self):
        return self._float_time() == self.hstat.st_mtime  # mtime is float
    def is_same_type(self):
        if self.error:
            return False
        return self._same_type(self.mode, self.hstat.st_mode)

    def get_mode(self):
        if self.local:
            return self.hstat.st_mode
        elif self.exists:
            return self.mode
        else:
            return 0
    def get_size(self):
        return self.size
    def get_struct_time(self):
        return time.localtime(self.s)
    def get_ctime_string(self):
        return time.ctime(self.s)
    def _float_time(self):
        return float(self.s) + float(self.ns) * 1e-9
    def get_path(self):
        return self.rpath
    def get_host_path(self):
        return self.hpath
    def get_target_path(self):
        return self.tpath
    def get_link_path(self):
        return os.readlink(self.hpath)
    def get_type(self):
        if self.exists and not self.error:
            return self.get_target_type()
        return self.get_host_type()
    def get_host_type(self):
        return self._file_type(self.hstat.st_mode if self.hstat else 0)
    def get_target_type(self):
        return self._file_type(self.mode)

class ListDirOp(ProtOp):
    name = "read-dir"
    request = 0x1010
    msgs = {
        0x1010: "request",
        0x1013: "ticket",
        0x101e: "error",
    }
    def __init__(self, targpath, windows=False):
        ProtOp.__init__(self)
        self.windows = windows
        if self.windows:
            self.targpath = ntpath.normpath(targpath)
        else:
            self.targpath = posixpath.normpath(targpath)
        self.size = 0
        self.ticket = None
        self.mode = 0
        self.path = ""
    def __str__(self):
        return "%s(%s)" % (ProtOp.__str__(self), self.targpath)
    def send_request(self, buf):
        buf.new_request(self.request, 0)
        buf.write_string(self.targpath)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        self.last = True
        if msg == "ticket":
            if buf.num != 1:
                raise ex.ProtError(buf, "Too many tickets (%d)" % buf.num)
            (self.size, self.ticket, self.mode, self.path) = buf.next_ticket()
        else:
            assert msg == "error"
            self.error = True
    def get_ticket(self):
        return self.ticket
    def get_size(self):
        return self.size
    def get_mode(self):
        return self.mode
    def get_name(self):
        return self.path
    def get_target_path(self):
        return self.targpath

class LinkOp(ProtOp):
    name = "file-link"
    request = 0x0050
    msgs = {
        0x0050: "request",
        0x0051: "ok",
        0x005e: "error",
    }
    def __init__(self, targpath, linkpath):
        ProtOp.__init__(self)
        self.targpath = targpath
        self.linkpath = linkpath
    def __str__(self):
        return "%s(%s -> %s)" % (
            ProtOp.__str__(self), self.linkpath, self.targpath)
    def send_request(self, buf):
        buf.new_request(self.request, 0)
        buf.write_string(self.targpath)
        buf.write_string(self.linkpath)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        if msg != "ok":
            assert msg == "error"
            self.error = True
        self.last = True
    def get_path(self):
        return self.path
    def get_mode(self):
        return self.mode

class MknodOp(ProtOp):
    name = "file-make"
    request = 0x0060
    msgs = {
        0x0060: "request",
        0x0061: "ok",
        0x006e: "error",
    }
    def __init__(self, targpath, mode, dev):
        ProtOp.__init__(self)
        self.path = targpath
        self.mode = mode
        self.major = os.major(dev)
        self.minor = os.minor(dev)
    def __str__(self):
        return "%s(%s, 0x%x, %d:%d)" % (
            ProtOp.__str__(self), self.path, self.mode, self.major, self.minor)
    def send_request(self, buf):
        buf.new_request(self.request, self.mode)
        buf.write_struct("II", self.major, self.minor)
        buf.write_string(self.path)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        if msg != "ok":
            assert msg == "error"
            self.error = True
        self.last = True
    def get_device(self):
        return os.makedev(self.major, self.minor)
    def get_major(self):
        return self.major
    def get_minor(self):
        return self.minor
    def get_mode(self):
        return self.mode
    def get_path(self):
        return self.path

class RemoveOp(ProtOp):
    name = "file-remove"
    request = 0x00f0
    msgs = {
        0x00f0: "request",
        0x00f1: "ok",
        0x00fe: "error",
    }
    def __init__(self, targpath):
        ProtOp.__init__(self)
        self.path = targpath
    def __str__(self):
        return "%s(%s)" % (
            ProtOp.__str__(self), self.path)
    def send_request(self, buf):
        buf.new_request(self.request, 0)
        buf.write_string(self.path)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        if msg != "ok":
            assert msg == "error"
            self.error = True
        self.last = True
    def get_path(self):
        return self.path

class MkdirOp(ProtOp):
    """Make directory on the target.

    This operation will call the mkdir POSIX function and take its the arguments
    as is from this object's creator. Creating parent directories is not
    supported, therefore in a chain of directories care must be taken to create
    them in the correct order.

    """
    name = "dir-make"
    request = 0x1030
    msgs = {
        0x1030: "request",
        0x1031: "ok",
        0x103e: "error",
    }
    def __init__(self, targpath, mode):
        ProtOp.__init__(self)
        self.path = targpath
        self.mode = mode
    def __str__(self):
        return "%s(%s, 0x%x)" % (ProtOp.__str__(self), self.path, self.mode)
    def send_request(self, buf):
        buf.new_request(self.request, self.mode)
        buf.write_string(self.path)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        if msg != "ok":
            assert msg == "error"
            self.error = True
        self.last = True
    def get_path(self):
        return self.path
    def get_mode(self):
        return self.mode

class OpenOp(ProtOp):
    """Open a target file, for reading, writing, or both.

    This transaction will use the C-standard fopen call to perform the operation
    and the arguments are taken as is in the call. A successful operation will
    provide a ticket number, which can be used to read or write to the file
    according to its mode.

    """
    name = "file-open"
    request = 0x0030
    msgs = {
        0x0030: "request",
        0x0033: "ticket",
        0x003e: "error"
    }
    def __init__(self, filename, mode):
        ProtOp.__init__(self)
        self.path = filename
        self.ticket = None
        self.mode = mode
        self.size = 0
    def send_request(self, buf):
        buf.new_request(self.request, 0)
        buf.write_string(self.path)
        buf.write_string(self.mode)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        if msg == "ticket":
            if buf.num != 1:
                raise ex.ProtError(buf, "Too many tickets (%d)" % buf.num)
            (self.size, self.ticket, mode, path) = buf.next_ticket()
            if path != self.path:
                raise ex.ProtError(buf, "Wrong ticket %s <> %s"
                                % (path, self.path))
        else:
            assert msg == "error"
            self.error = True
        self.last = True
    def get_ticket(self):
        return self.ticket
    def get_size(self):
        return self.size
    def get_mode(self):
        return self.mode
    def get_path(self):
        return self.path

class ReadOp(ProtOp):
    """Read the data of a ticket.

    This operation takes a ticket number and then requests blocks of data until
    the data contained in the ticket is drained. The user may pop the data as it
    is obtained or wait for the whole data to be compiled first.

    """
    name = "ticket-read"
    request = 0x0110
    msgs = {
        0x0110: "request",
        0x0112: "last",
        0x0114: "more",
        0x011e: "error",
    }
    ENODATA = 61
    def __init__(self, tickno):
        ProtOp.__init__(self)
        if int(tickno) <= 0:
            raise ex.ProtError("Not a valid ticket number: %s" % tickno)
        self.ticket = tickno
        self.data = bytearray()
    def __str__(self):
        return "%s: ticket#%08x%s" % (
            ProtOp.__str__(self), self.ticket,
            ", got %d bytes" % len(self.data) if self.ply else "")
    def __len__(self):
        return len(self.data)
    def send_request(self, buf):
        buf.new_request(self.request, self.ticket)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        size = buf.data_length()
        if msg == "more":
            if size == 0:
                raise ex.ProtError(buf, "No data in response")
            self.data += buf.read_binary()
        elif msg == "last":
            if size > 0:
                self.data += buf.read_binary()
            self.last = True
        else:
            assert msg == "error"
            self.error = (buf.num != self.ENODATA)
            self.last = True
    def get_data(self):
        return self.data
    def clear_data(self):
        self.data = bytearray()

class ReadSaveOp(ProtOp):
    """Read the data of a ticket and save it to a file.

    This operation takes a ticket number and then requests blocks of data until
    the data contained in the ticket is drained. The data is written to the file
    per block as it is received. No data is kept in this object.

    """
    name = "ticket-read"
    request = 0x0110
    msgs = {
        0x0110: "request",
        0x0112: "last",
        0x0114: "more",
        0x011e: "error",
    }
    def __init__(self, tickno, destfile, overwrite):
        self.out = None
        ProtOp.__init__(self)
        if int(tickno) <= 0:
            raise ex.ProtError("Not a valid ticket number: %s" % tickno)
        self.ticket = tickno
        self.bytes = 0
        try:
            self.out = open(destfile, "wb")
        except IOError as e:
            raise ex.ProtIOError("host " + destfile, str(e))
    def __len__(self):
        return self.bytes
    def __str__(self):
        return "%s: ticket#%08x, received %d bytes" % (
            ProtOp.__str__(self), self.ticket, self.bytes)
    def send_request(self, buf):
        buf.new_request(self.request, self.ticket)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        size = buf.data_length()
        if size > 0:
            self.out.write(buf.read_binary())
            self.bytes += size
        elif size == 0 and msg == "more":
            raise ex.ProtError(buf, "No data in response")
        if msg != "more":
            self.last = True
            self.out.close()
        if msg not in ("more", "last"):
            assert msg == "error"
            self.error = True

class ReadTextOp(ProtOp):
    """Read the data of a ticket.

    This operation takes a ticket number and then requests blocks of data until
    the data contained in the ticket is drained. The user may pop the data as it
    is obtained or wait for the whole data to be compiled first.

    """
    name = "ticket-read"
    request = 0x0110
    msgs = {
        0x0110: "request",
        0x0112: "last",
        0x0114: "more",
        0x011e: "error",
    }
    def __init__(self, tickno, capture=True):
        ProtOp.__init__(self)
        if int(tickno) <= 0:
            raise ex.ProtError("Not a valid ticket number: %s" % tickno)
        self.ticket = tickno
        self.capture = bool(capture)
        self.text = ""
        self.got = 0
    def __str__(self):
        return "%s: ticket#%08x%s" % (
            ProtOp.__str__(self), self.ticket,
            (", got %d bytes" % self.got) if self.ply else "")
    def __len__(self):
        return self.got
    def send_request(self, buf):
        buf.new_request(self.request, self.ticket)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        size = buf.data_length()
        if msg == "more":
            if size == 0:
                raise ex.ProtError(buf, "No data in response")
            self._buf_text(buf)
        elif msg == "last":
            if size > 0:
                self._buf_text(buf)
            self.last = True
        elif msg == "error":
            if buf.num == self.ENODATA:
                self.last = True
            else:
                self.error = True
        else:
            raise ex.ProtError(buf, "Unknown response code")
    def _buf_text(self, buf):
        txt = buf.next_string()
        while txt:
            self.got += len(txt)
            if self.capture:
                self.text += txt
            elif self.last:
                print(txt)
            else:
                print(txt, end=' ')
            txt = buf.next_string()
    def get_text(self):
        return self.text
    def clear_text(self):
        self.text = ""

class WriteOp(ProtOp):
    """Write data to a ticket.

    Fill the buffer with data to be sent to the target ticket. Continue sending
    data until the whole data has been sent.

    """
    name = "ticket-write"
    request = 0x0120
    msgs = {
        0x0120: "request",
        0x0121: "ok",
        0x012e: "error",
    }
    def __init__(self, tickno, filepath, flush=False):
        ProtOp.__init__(self)
        self.ticket = tickno
        self.filepath = filepath
        self.infile = None
        try:
            self.infile = open(filepath, 'rb')
        except IOError:
            raise ex.ProtIOError(filepath)
        self.flush = flush
        self.bytes_written = 0
    def __del__(self):
        if self.infile:
            self.infile.close()
    def send_request(self, buf):
        data = self.infile.read(buf._max_data_size())
        if len(data) == 0:
            self.last = True
            raise ex.ProtEndException()
        buf.new_request(self.request, self.ticket)
        written = buf.write_binary(bytearray(data))
        self.bytes_written += written
        assert written == len(data)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        if msg != self.msgs[self.request | 1]:
            assert msg == "error"
            self.error = True
            self.last = True
    def get_file_name(self):
        return os.path.basename(self.filepath)
    def bytes_written(self):
        return self.bytes_written

class DiscardOp(ProtOp):
    """Discard an obsolete ticket.

    Sends a request to free all the resources associated with the ticket. After
    a successful transaction the ticket number will be invalid.

    """
    name = "ticket-discard"
    request = 0x0100
    msgs = {
        0x0100: "request",
        0x0101: "ok",
        0x010e: "error"
    }
    def __init__(self, tickno):
        ProtOp.__init__(self)
        self.ticket = tickno
    def send_request(self, buf):
        buf.new_request(self.request, 1)
        buf.write_struct("I", self.ticket)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        if msg != "ok":
            assert msg == "error"
            self.error = True
        self.last = True

class PermOp(ProtOp):
    """Change the file permissions.

    A file associated with a ticket can have its permissions changed by this
    transaction. The POSIX function chmod is used to implement this operation
    with the mode argument from this object.

    """
    name = "file-permission"
    request = 0x1020
    msgs = {
        0x1020: "request",
        0x1021: "ok",
        0x102e: "error",
    }
    def __init__(self, tickno, perm):
        ProtOp.__init__(self)
        self.ticket = tickno
        self.perm = perm
    def send_request(self, buf):
        buf.new_request(self.request, self.ticket)
        buf.write_struct("H", self.perm)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        if msg != "ok":
            assert msg == "error"
            self.error = True
        self.last = True

class GetTimeOp(ProtOp):
    """Get and set the target system time.

    Note that administrative privileges may be required.
    """
    name = "get-time"
    request = 0x0020
    msgs = {
        0x0020: "request",
        0x0022: "data",
        0x002e: "error",
    }
    def __init__(self):
        ProtOp.__init__(self)
        self.timestr = ""
    def send_request(self, buf):
        buf.new_request(self.request, 0)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        if msg == "data":
            self.timestr = buf.read_string(0)
        else:
            assert msg == "error"
            self.error = True
        self.last = True
    def get_time(self):
        return self.timestr

class SetTimeOp(ProtOp):
    """Get and set the target system time.

    Note that administrative privileges may be required.
    """
    name = "target-time"
    request = 0x1000
    msgs = {
        0x1000: "request",
        0x1001: "ok",
        0x100e: "error",
    }
    def __init__(self, sec):
        ProtOp.__init__(self)
        self.sec = int(sec)
    def send_request(self, buf):
        buf.new_request(self.request, 0)
        buf.write_struct("Q", self.sec)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        if msg != "ok":
            assert msg == "error"
            self.error = True
        self.last = True

class WakeOp(ProtOp):
    """Set the Simics Agent slumber time, i.e. the polling interval.

    This will define how interactive the agent will be, because the agent will
    not notice any new commands until it wakes up again.
    """
    name = "agent-slumber"
    request = 0x0010
    msgs = {
        0x0010: "request",
        0x0011: "ok",
    }
    def __init__(self, millisec):
        ProtOp.__init__(self)
        self.ms = millisec
    def send_request(self, buf):
        buf.new_request(self.request, self.ms)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        if msg != "ok":
            self.error = True
        self.last = True

class QuitOp(ProtOp):
    """Tell the Simics Agent to quit and cease all operations."""
    name = "agent-quit"
    request = 0xfff0
    msgs = {
        0xfff0: "request",
        0xfff1: "ack",
    }
    def __init__(self, code, reason):
        ProtOp.__init__(self)
        self.code = code
        self.reason = "User request" if not reason else reason
    def send_request(self, buf):
        buf.new_request(self.request, self.code)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        if msg != "ack":
            self.error = True
        self.last = True


class RestartOp(ProtOp):
    """Restart the Simics Agent in the target system."""
    name = "agent-restart"
    request = 0x17f0
    msgs = {
        0x17f0: "request",
        0x0002: "announce",
    }
    def __init__(self):
        ProtOp.__init__(self)
    def send_request(self, buf):
        buf.new_request(self.request, 0)
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        if msg != "announce":
            self.error = True
        self.last = True

class SubprocOp(ProtOp):
    """Start a subprocess command in a shell."""
    name = "subproc"
    request = 0x1800
    msgs = {
        0x1800: "request",
        0x1803: "ticket",
        0x180e: "error",
    }

    def __init__(self, cmdline):
        ProtOp.__init__(self)
        self.cmdline = cmdline
        self.ticket = None
    def send_request(self, buf):
        buf.new_request(self.request, 0)
        buf.write_string(self.cmdline)
        buf.write_string('r')
        self.check_request(buf)
    def parse_reply(self, buf):
        msg = self.parse_reply_code(buf)
        if msg == "ticket":
            (_, self.ticket, _, _) = buf.next_ticket()
        else:
            assert msg == "error"
            self.error = True
        self.last = True
    def get_ticket(self):
        return self.ticket
    def get_command(self):
        return self.cmdline
