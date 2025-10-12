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


# The job classes in this file encapsulates a command issued by the user. These
# jobs are broken down into operations (transactions) and request/response
# messages. Each command may require one or more transaction to complete the
# task. The job will store the information require to expedite the work and any
# output resulting from it.
#

import os
import time
import simics
import calendar
import posixpath
import ntpath
from . import buffer
from . import exceptions as ex
from . import protocol as prot

class MaticJob:
    """Matic abstract job class"""
    name = "matic-job"

    def __init__(self, obj):
        self.id = None
        self.obj = obj
        self.hndl = self.obj.object_data
        self.reqs = 0
        self.haps = 0
        self.done = False
        self.cancel = False
        self.capture = False
        self.errno = 0
        self.errstr = ""
        self.errors = 0
        self.hid = None
        self.wid = None
        self.output = ""
        self.logstr = ""
        self.failed_error = True
        self.interactive = None
        self.ops = None
        self.op = None

    def __str__(self):
        return self.name

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def _parse_code(self, buf):
        request = buf.code >> 4
        response = buf.code & 0xf
        message = None
        if response in self.responses:
            message = self.responses[response]
        return (request, response, message)

    def get_pwd(self):
        return self.hndl.get_pwd()

    def finished(self):
        self.done = True
        if not self.cancel:
            self.hndl.job_done(self)

    def get_captured_output(self):
        return self.output if self.capture else ""

    def get_error_report(self):
        return self.errstr if self.errno else ""

    def get_log_string(self):
        return self.logstr

    def get_state(self):
        if not self.id:
            return "inactive"
        if self.is_done():
            return "complete"
        if self.is_cancelled():
            return "cancelled"
        if not self.reqs:
            return "queued"
        if self.is_active():
            return "active"
        return "in progress"

    def get_owner_name(self):
        return self.obj.name if hasattr(self.obj, "name") else str(self.obj)

    def _error_string(self, errmsg, errnfo):
        return "errno=%d: %s\n%s" % (self.errno, errmsg, errnfo)

    def report_error_buf(self, buf):
        (self.errno, errmsg, errnfo) = buf.get_error()
        self.errstr = self._error_string(errmsg, errnfo)

    def report_error(self, errnum, errmsg, errnfo):
        self.errno = errnum
        self.errstr = self._error_string(errmsg, errnfo)

    def block_add_hap(self, hap_id):
        assert self.hid == None
        self.hid = hap_id

    def block_rem_hap(self, hap_id):
        assert self.hid == hap_id
        self.hid = None

    def block_add_sb(self, sb_id):
        assert self.wid == None
        self.wid = sb_id

    def block_rem_sb(self, sb_id):
        assert self.wid == sb_id
        self.wid = None

    def do_output(self, text):
        if self.capture:
            self.output += text
        else:
            print(text)

    def has_captured_output(self):
        return self.capture and self.output

    def has_error_report(self):
        return self.errno and self.errstr

    def has_log_info(self):
        return bool(self.logstr)

    def is_active(self):
        return self.reqs > self.haps

    def is_async(self):
        return False

    def is_blocking(self):
        return self.hid != None or self.wid != None

    def is_cancelled(self):
        return self.cancel

    def is_connected(self):
        return self.hndl.is_connected()

    def is_done(self):
        return self.done

    def is_interactive(self):
        return self.interactive

    def is_mine(self, buf):
        if not self.op:
            return False
        return self.op.is_mine(buf)

    def is_windows(self):
        return self.hndl.is_windows()

    def get_hap_id(self):
        return self.hid

    def get_wait_id(self):
        return self.wid

    def print_state(self):
        return "%s %s, %d reqs, %d haps" % (
            self.name, self.get_state(), self.reqs, self.haps)

    def update_target_path(self, root, *paths):
        win = self.is_windows()
        assert win != None
        if not root:
            if win:
                root = ntpath.abspath(ntpath.join("c:", ntpath.sep))
            else:
                root = posixpath.abspath(posixpath.sep)
        if not paths:
            return root
        if win:
            path = ntpath.normpath(ntpath.join(*paths))
        else:
            path = posixpath.normpath(posixpath.join(*paths))
        if not path:
            return root
        if win:
            return ntpath.join(root, ntpath.normpath(path))
        return posixpath.join(root, posixpath.normpath(path))

    def target_basename(self, filepath):
        win = self.is_windows()
        if win == None:
            return filepath
        elif win:
            return ntpath.basename(filepath)
        else:
            return posixpath.basename(filepath)

    def _prepare_job(self):
        pass

    def _get_op(self):
        if not self.ops:
            self.ops = iter(self.next())
        if self.op != None and not self.op.is_done():
            return self.op
        # Get the next operation, if any.
        try:
            return next(self.ops)
        except StopIteration:
            self.done = True
            return None
        except ex.JobException as e:
            simics.SIM_log_error(self.obj, 0, str(e))

    def next_request(self, buf):
        """Write the next request in the buffer."""
        if self.done:
            raise ex.JobDoneException("Job done. No more requests")
        # Get the next request, if any.
        while True:
            op = self._get_op()
            if op == None:
                raise ex.JobDoneException("job %s ended. No operation remain." % self)
            try:
                op.send_request(buf)
            except ex.ProtEndException:
                simics.SIM_log_info(3, self.obj, 0,
                                     "%s operation %s ended" % (self, op))
                continue
            self.reqs += 1
            self.op = op  # Expect a reply
            break

    def next_response(self, buf):
        """Handle the Simics agent response in the buffer."""
        if self.done:
            raise ex.JobException("Job is already done. No responses expected")
        if self.op == None:
            raise ex.JobException("No operation in progress.")
        self.haps += 1
        if self.reqs != self.haps:
            raise ex.JobException("Request/reply mismatch (%d <> %d)" % (
                self.reqs, self.haps))
        try:
            self.op.parse_reply(buf)
        except ex.ProtError as e:
            self.done = True
            self.report_error(71, "EPROTO (71): Protocol error", str(e))
            simics.SIM_log_error(self.obj, 0,
                                "%s operation %s error %s" % (self, self.op, e))
        if self.op.failed() and self.failed_error:
            self.report_error_buf(buf)
        if self.op.is_done():
            self.op = None  # Do not expect any more replies from this operation

    def next(self):
        """Get the next operation."""
        self._prepare_job()
        for op in self._generate_ops():
            simics.SIM_log_info(3, self.obj, 0,
                                "%s started operation %s" % (self, op))
            yield op
            assert op.is_done()
            simics.SIM_log_info(3, self.obj, 0,
                                "%s completed operation %s" % (self, op))


class ConnectToJob(MaticJob):
    """Connect to the Simics agent job"""
    name = "connect-to"

    def __init__(self, obj, identity=None):
        MaticJob.__init__(self, obj)
        self.to = identity
        self.name += (" %s" % self.to) if self.to else ""

    def get_state(self):
        if self.is_done():
            return "complete"
        return "waiting"

    def next_request(self, buf):
        raise ex.JobException("Calling next_request for a ConnectToJob")

    def next_response(self, buf):
        raise ex.JobException("Calling next_response for a ConnectToJob")

    def connected(self, name):
        self.logstr = "connected to %s" % name
        self.done = True


class AgentQuitJob(MaticJob):
    """Quit the Simics agent job, with optional code"""
    name = "agent-quit"

    def __init__(self, obj, code=None, msg=None, quiet=False):
        MaticJob.__init__(self, obj)
        self.code = int(code) if code else 0
        self.msg = str(msg) if msg else "termination by user request"
        self.quiet = quiet

    def _generate_ops(self):
        quit_op = prot.QuitOp(self.code, self.msg)
        yield quit_op
        self.done = True
        if quit_op.failed():
            simics.SIM_log_error(self.obj, 0, "Quit operation failed")
        elif not self.quiet:
            self.logstr = "The Simics agent has terminated."


class AgentRestartJob(MaticJob):
    """Restart the Simics agent in the target system."""
    name = "agent-restart"

    def __init__(self, obj, quiet=False):
        MaticJob.__init__(self, obj)
        self.quiet = quiet

    def _generate_ops(self):
        rest_op = prot.RestartOp()
        yield rest_op
        self.done = True
        if rest_op.failed():
            simics.SIM_log_error(self.obj, 0, "Restart operation failed")
        elif not self.quiet:
            self.logstr = "The Simics agent has restarted."


class DownloadJob(MaticJob):
    """Download a file."""
    name = "download"

    def __init__(self, obj, targpath, hostpath=None, overwrite=False):
        MaticJob.__init__(self, obj)
        self.hostpath = os.path.join(os.getcwd(), hostpath if hostpath else "")
        self.targfile = targpath
        self.targsrc = (self.get_pwd(), targpath if targpath else "")
        self.overwrite = overwrite
        self.targpath = None
        self.outfile = None
        self.tickno = None
        self.last = False
        self._prepare_job()

    def __del__(self):
        if self.outfile:
            self.outfile.close()
            if self.errno != 0:
                os.unlink(self.hostpath)

    def __str__(self):
        return "%s %s" % (self.name, self.target_basename(self.targfile))

    def _prepare_job(self):
        if self.targpath:
            return  # Already prepared
        if not self.is_connected():
            return  # Postpone until connected
        self.targpath = self.update_target_path(*self.targsrc)
        if os.path.isdir(self.hostpath):
            if self.is_windows():
                targname = ntpath.basename(self.targpath)
            else:
                targname = posixpath.basename(self.targpath)
            self.hostpath = os.path.join(self.hostpath, targname)
        if os.path.isfile(self.hostpath):
            if not self.overwrite:
                raise ex.JobException("Host file '%s' exists" % (self.hostpath,))
        elif not os.path.isdir(os.path.dirname(self.hostpath)):
            raise ex.JobException("Host path '%s' does not exist" % (
                os.path.dirname(self.hostpath),))
        try:
            self.outfile = open(self.hostpath, 'wb')
        except IOError as e:
            raise ex.JobException(str(e))

    def _generate_ops(self):
        open_op = prot.OpenOp(self.targpath, 'rb')
        yield open_op
        if open_op.failed():
            raise ex.JobException("Could not open target file %s"
                                  % self.targpath)
        save_op = prot.ReadSaveOp(open_op.get_ticket(), self.hostpath,
                                  self.overwrite)
        yield save_op
        if save_op.failed():
            simics.SIM_log_error(self.obj, 0, "Host copy of target %s is"
                                 " truncated in %s" % (
                                     self.targpath, self.hostpath))

        # close file early, before the destructor is run - SIMICS-21158
        if self.outfile:
            self.outfile.close()

        close_op = prot.DiscardOp(open_op.get_ticket())
        yield close_op


class DownloadDirJob(MaticJob):
    """Recursively download a whole directory tree."""
    name = "download-dir"

    def __init__(self, obj, targpath, hostpath, follow=False, no_hidden=False,
                 overwrite=False, verbose=False):
        MaticJob.__init__(self, obj)
        simics.SIM_log_info(4, self.obj, 0,
                            "src=%s, dest=%s, %s, %s hidden/system, %s, %s" % (
                                targpath, hostpath,
                                "follow" if follow else "soft-link",
                                "no" if no_hidden else "all",
                                "overwrite" if overwrite else "preserve",
                                "verbose" if verbose else "quiet"))
        self.targbase = None
        self.srcpath = targpath
        self.targcwd = self.get_pwd()
        self.hostpath = hostpath if hostpath else "."
        if not os.path.isdir(self.hostpath):
            raise ex.JobException("Destination path %s not found" % hostpath)
        self.hostbase = os.path.abspath(self.hostpath)
        self.verbose = verbose
        self.no_hidden = no_hidden
        self.overwrite = overwrite
        self.follow = follow
        # Statistics
        self.hidden = 0
        self.skipped = 0
        self.unreadable = 0
        self.overwritten = 0
        self.new_dirs = 0
        self.new_files = 0
        self.new_links = 0

    def _prepare_job(self):
        if self.targbase:
            return  # Already prepared
        if not self.is_connected():
            return  # Postpone handling until connected
        if self.is_windows():
            (self.targpath, self.srcbase) = ntpath.split(
                ntpath.normpath(self.srcpath))
        else:
            (self.targpath, self.srcbase) = posixpath.split(
                posixpath.normpath(self.srcpath))
        if self.targpath:
            self.targbase = self.update_target_path(None, self.targcwd, self.targpath)
        else:
            self.targbase = self.update_target_path(None, self.targcwd)
        simics.SIM_log_info(4, self.obj, 0, "%s prepare target path %s ->"
                            " target %s, host %s" % (
                                self, self.srcpath,
                                self._targ_path(self.srcbase),
                                self._host_path(self.srcbase)))

    def _host_path(self, *parts):
        return os.path.normpath(os.path.join(self.hostbase, *parts).replace(
            ntpath.sep if self.is_windows() else posixpath.sep, os.path.sep))

    def _targ_path(self, *parts):
        if self.targbase == None:
            raise ex.JobException("Target type not yet known")
        if self.is_windows():
            return ntpath.normpath(ntpath.join(
                self.targbase, *parts).replace(posixpath.sep, ntpath.sep))
        else:
            return posixpath.normpath(posixpath.join(
                self.targbase, *parts).replace(ntpath.sep, posixpath.sep))

    def _log_item(self, stat, reason):
        upstr = stat.get_type()
        upstr += " for " if upstr.startswith('unknown') else " "
        upstr += "%s %s" % (stat.get_path(), reason)
        simics.SIM_log_info(1 if self.verbose else 2, self.obj, 0, upstr)

    def _expand_items(self, rdir):
        data = rdir.get_data()
        return [bytes(i).decode('utf-8') for i in data.split(b'\0')]

    def _stat_items(self, path, rdir):
        items = self._expand_items(rdir)
        simics.SIM_log_info(4, self.obj, 0, "Read Path %s: %s" % (path, items))
        for item in items:
            if not item:
                continue
            if item[-1] in ('|', '/', '@', '=', '\\'):
                item = item[:-1]  # Remove trailing decorator
            if item in ('.', '..'):
                continue  # Ignore . and .. directories
            if self.no_hidden and item.startswith('.'):
                self.hidden += 1
                simics.SIM_log_info(3, self.obj, 0, "Path %s is hidden" % item)
                continue
            targpath = self._targ_path(path, item)
            hostpath = self._host_path(path, item)
            relpath = os.path.join(path, item)
            simics.SIM_log_info(4, self.obj, 0, "Path %s: targ %s -> host %s" % (
                relpath, targpath, hostpath))
            yield prot.StatOp(relpath, targpath, hostpath, self.follow, False)

    def _copy_file(self, path, stat):
        opop = prot.OpenOp(stat.get_target_path(), "rb")
        yield opop
        if opop.failed():
            self.unreadable += 1
            self._log_item(stat, "cannot open target file %s" % (
                stat.get_target_path()))
            return  # nothing more to do
        try:
            rdop = prot.ReadSaveOp(opop.get_ticket(), stat.get_host_path(),
                                   self.overwrite)
        except ex.ProtError as e:
            self.unreadable += 1
            simics.SIM_log_error(self.obj, 0, "Cannot open %s on host: %s" % (
                stat.get_host_path(), str(e)))
            return
        yield rdop
        if rdop.failed():
            self.unreadable += 1
            self._log_item(stat, "target %s is unreadable" % (
                stat.get_target_path()))
        else:
            self._log_item(stat, "target %s copied to host %s" % (
                stat.get_target_path(), stat.get_host_path()))
        yield prot.DiscardOp(opop.get_ticket())

    # Generator for the next target file or directory.
    def _expand_path(self, path):
        targpath = self._targ_path(path)
        lsop = prot.ListDirOp(targpath, self.is_windows())
        yield lsop
        if lsop.failed():
            raise ex.JobException("Cannot read the source directory")
        assert lsop.is_done()
        rdir = prot.ReadOp(lsop.get_ticket())
        yield rdir
        if rdir.failed():
            self.skipped += 1
            simics.SIM_log_info(1 if self.verbose else 2, self.obj, 0,
                                "target directory %s is unreadable" % path)
            return  # Will raise StopIteration
        yield prot.DiscardOp(lsop.get_ticket())
        hostpath = self._host_path(path)
        simics.SIM_log_info(4, self.obj, 0,
                            "Expand path %s -> host path %s" % (path, hostpath))
        if not os.path.isdir(hostpath):
            try:
                os.mkdir(hostpath)
            except OSError as e:
                simics.SIM_log_error(
                    self.obj, 0, "Cannot create host destination directory"
                    " %s: %s" % (hostpath, str(e)))
                return
            simics.SIM_log_info(1 if self.verbose else 2, self.obj, 0,
                                "Created host directory %s" % hostpath)
        if len(rdir) == 0:
            simics.SIM_log_info(4, self.obj, 0, "Directory %s is empty" % path)
            return
        self.failed_error = False
        # Collect directory entries
        dirs = []
        files = []
        for stat in self._stat_items(path, rdir):
            yield stat
            if stat.failed():
                self.skipped += 1
                simics.SIM_log_error(
                    self.obj, 0, "Unable to find target %s" % (
                        stat.get_target_path()))
            elif stat.local_exists() and not stat.is_same_type():
                self.skipped += 1
                self._log_item(stat, "type differs from %s %s" % (
                    stat.get_host_type(), stat.get_host_path()))
            elif stat.local_exists() and not self.overwrite:
                self.skipped += 1
                self._log_item(stat, "not overwriting %s %s" % (
                    stat.get_host_type(), stat.get_host_path()))
            elif stat.is_file():
                self.new_files += 1
                files.append(stat)
            elif stat.is_dir():
                self.new_dirs += 1
                dirs.append(stat)
            elif stat.is_softlink():
                if self.is_windows() or self.follow:
                    self.new_files += 1
                else:
                    self.new_links += 1
                files.append(stat)
                self._log_item(stat, "soft-link copied: target %s -> host %s"
                               % (stat.get_target_path(), stat.get_host_path()))
            else:
                self.skipped += 1
                simics.SIM_log_error(
                    self.obj, 0, "unsupported type %s is ignored" % (
                        stat.get_target_type()))
        # Copy files first
        for fi in files:
            for item in self._copy_file(path, fi):
                yield item
        # Then recurse through directories and expand them
        for di in dirs:
            for item in self._expand_path(di.get_path()):
                yield item

    def _generate_ops(self):
        for op in self._expand_path(self.srcbase):
            yield op

    def finished(self):
        infos = []
        if self.new_dirs:
            infos += ["%d director%s created" % (
                self.new_dirs, "ies" if self.new_dirs > 1 else "y")]
        if self.new_files:
            infos += ["%d file%s uploaded" % (
                self.new_files, "s" if self.new_files > 1 else "")]
        if self.new_links:
            infos += ["%d soft-link%s created" % (
                self.new_links, "s" if self.new_links > 1 else "")]
        if self.hidden:
            infos += ["%d hidden file%s ignored" % (
                self.hidden, "s" if self.hidden > 1 else "")]
        if self.unreadable:
            infos += ["%d unreadable file%s ignored" % (
                self.unreadable, "s" if self.unreadable > 1 else "")]
        if self.skipped:
            infos += ["%d file%s skipped (use -overwrite to replace)" % (
                self.skipped, "s" if self.skipped > 1 else "")]
        if self.errors:
            infos += ["%d error%s" % (
                self.errors, "s" if self.errors > 1 else "")]
        if not infos:
            infos += ["nothing to do"]
        self.logstr = ", ".join(infos)
        MaticJob.finished(self)


class PollIntervalJob(MaticJob):
    """Update the poll interval time in the Simics agent."""
    name = "agent-poll-interval"

    def __init__(self, obj, ms):
        MaticJob.__init__(self, obj)
        self.name += " %d" % ms
        self.ms = ms

    def _time_string(self):
        h = self.ms // 3600000
        m = (self.ms // 60000) % 60
        s = (self.ms // 1000) % 60
        ms = self.ms % 1000
        if h:
            return "%d:%02d:%02d.%03d" % (h, m, s, ms)
        if m:
            return "%d:%02d.%03d" % (m, s, ms)
        return "%d.%03d" % (s, ms)

    # Called from MaticChannel
    def get_seconds(self):
        return float(self.ms) / 1000.0

    def _generate_ops(self):
        wake_op = prot.WakeOp(self.ms)
        yield wake_op
        if wake_op.succeeded():
            self.logstr = "Poll-interval set to %d ms (%s s)" % (
                self.ms, self._time_string())


class PrintFileJob(MaticJob):
    """Print a text file."""
    name = "print-file"
    badchrnum = list(range(9)) + list(range(14, 32)) + [11, 12, 127]
    badchrset = set([chr(x) for x in badchrnum])

    def __init__(self, obj, targpath, force=False, capture=False):
        MaticJob.__init__(self, obj)
        self.capture = bool(capture)
        self.targfile = targpath
        self.targsrc = (self.get_pwd(), targpath if targpath else "")
        self.path = None
        self.force = force
        self.last = False
        self.printable = None
        self._prepare_job()

    def __str__(self):
        return "%s %s" % (self.name, self.target_basename(self.targfile))

    def is_printable(self, text):
        return set(text[:256]).isdisjoint(self.badchrset)

    def check_output(self, text):
        if self.printable == None:
            self.printable = self.force or self.is_printable(text)
            if not self.printable:
                self.do_output(
                    "Output is not text. Use -force to print it anyway.")
        if self.printable:
            try:
                enstr = bytes(text).decode('utf-8')
            except UnicodeDecodeError:
                enstr = bytes(text).decode('latin-1')
            self.do_output(enstr)

    def _prepare_job(self):
        if self.path:
            return  # Already prepared
        if not self.is_connected():
            return  # wait until connected
        self.path = self.update_target_path(*self.targsrc)

    def _generate_ops(self):
        open_op = prot.OpenOp(self.path, "rt")
        yield open_op
        if open_op.failed():
            raise ex.JobException("Failed to open the source file: %s" % self.path)
        read_op = prot.ReadOp(open_op.get_ticket())
        yield read_op
        if open_op.failed():
            raise ex.JobException("Failed to read the source file: %s" % self.path)
        self.check_output(read_op.get_data())
        close_op = prot.DiscardOp(open_op.get_ticket())
        yield close_op
        if close_op.failed():
            simics.SIM_log_error(self.obj, 0, "Failed to close ticket#%d,"
                                 " got %s" % (open_op.get_ticket(), close_op))


class ReadDirJob(MaticJob):
    """List the contents of a directory"""
    name = "ls"

    def __init__(self, obj, path, capture=False):
        MaticJob.__init__(self, obj)
        self.capture = bool(capture)
        self.name += (" %s" % path) if path else ""
        self.path = None
        self.targpath = (self.get_pwd(), path if path else "")
        self.tickno = None
        self.last = False
        self.part = ""
        self.items = []
        self._prepare_job()

    def _expand_items(self, rdir):
        data = rdir.get_data()
        return [bytes(i).decode('utf-8') for i in data.split(b'\0')]

    def _generate_output(self):
        if self.part:
            self.items.append(self.part)
        items = [x for x in self.items if x]
        ostr = "\n".join(sorted(items))
        return ostr

    def _prepare_job(self):
        if self.path:
            return  # Path already prepared
        if not self.is_connected():
            return  # Postpone until connected
        self.path = self.update_target_path(*self.targpath)

    def _generate_ops(self):
        lsop = prot.ListDirOp(self.path, self.is_windows())
        yield lsop
        if lsop.failed():
            raise ex.JobException("Failed to open the directory: %s" % self.path)
        rdop = prot.ReadOp(lsop.get_ticket())
        yield rdop
        if rdop.succeeded():
            self.items = self._expand_items(rdop)
            self.do_output(self._generate_output())
        clop = prot.DiscardOp(lsop.get_ticket())
        yield clop
        if clop.failed():
            raise ex.JobException("Failed to close the directory: %s" % self.path)


class RunJob(MaticJob):
    """Execute a shell command-line."""
    name = "run"

    def __init__(self, obj, cmdline, capture=False):
        MaticJob.__init__(self, obj)
        self.capture = bool(capture)
        self.name += " %s" % cmdline.split()[0]
        self.targpath = self.get_pwd()
        self.cmdstr = cmdline
        self.cmdline = None
        self.tickno = None
        self.last = False
        self._prepare_job()

    def _prepare_job(self):
        if self.cmdline:
            return
        if not self.is_connected():
            return
        workpath = self.update_target_path(self.targpath, "")
        (drive, _) = ntpath.splitdrive(workpath)  # Works for unix paths too
        chpath = ("%s && " % drive) if drive else ""
        chpath += "cd \"%s\" && " % workpath.replace('\\', '\\\\')
        self.cmdline = chpath + self.cmdstr

    def _generate_ops(self):
        open_op = prot.SubprocOp(self.cmdline)
        yield open_op
        if open_op.failed():
            return
        stdout_op = prot.ReadTextOp(open_op.get_ticket(), self.capture)
        yield stdout_op
        if stdout_op.failed():
            simics.SIM_log_error(self.obj, 0,
                                 "Could not read standard out from subprocess")
        if self.capture:
            self.do_output(stdout_op.get_text())
        close_op = prot.DiscardOp(open_op.get_ticket())
        yield close_op


class TargetTimeJob(MaticJob):
    """Target date/time job"""
    name = "target-time"

    def __init__(self, obj, tm=None, now=False, capture=False):
        MaticJob.__init__(self, obj)
        if now:
            self.name += " -now"
            ts = time.localtime()
            self.sec = time.mktime(ts)
            self.date = time.strftime("%a, %d %b %Y %H:%M:%S %Z", ts)
        elif tm:
            self.name += " \"%s\"" % tm
            ts = None
            formats = ["%a, %d %b %Y %H:%M:%S %Z",
                       "%a, %d %b %Y %H:%M:%S",
                       "%Y-%m-%d %H:%M:%S %Z",
                       "%Y-%m-%d %H:%M:%S",
                       "%x %X %Z",
                       "%x %X",
                       "%c"]
            for frm in formats:
                try:
                    ts = time.strptime(tm, frm)
                    break
                except ValueError:
                    pass  # ignore errors
            if not ts:
                raise ex.JobException("Unrecognized date format: '%s'" % tm)
            if tm.endswith("UTC"):
                self.sec = calendar.timegm(ts)
            else:
                self.sec = time.mktime(ts)
            self.date = tm
        else:
            self.capture = bool(capture)
            self.date = None
            self.sec = None

    def _generate_ops(self):
        if self.sec:
            yield prot.SetTimeOp(self.sec)
        else:
            time_op = prot.GetTimeOp()
            yield time_op
            if time_op.succeeded():
                self.do_output(time_op.get_time())


class UploadJob(MaticJob):
    """Upload a file."""
    name = "upload"

    def __init__(self, obj, hostpath, targpath, overwrite=False, flush=False,
                 executable=False):
        MaticJob.__init__(self, obj)
        self.infile = None
        try:
            nfo = os.stat(hostpath)
        except OSError as e:
            raise ex.JobException(str(e))
        self.name += " %s" % os.path.basename(hostpath)
        self.hostpath = hostpath  # Known to be an existing file
        self.targdest = (self.get_pwd(), targpath if targpath else "",
                         os.path.basename(hostpath))
        self.targpath = None
        self.overwrite = overwrite
        self.executable = executable
        self.flush = flush
        self.exists = False if overwrite else None
        self.tickno = None
        self.last = False
        self.perm = False
        self.access = nfo.st_mode
        if executable:  # Set executable where readable
            self.access |= (nfo.st_mode & 0o444) >> 2
        self.infile = open(self.hostpath, 'rb')
        self._prepare_job()

    def __del__(self):
        if self.infile:
            self.infile.close()

    def _prepare_job(self):
        if self.targpath:
            return  # Already prepared
        if not self.is_connected():
            return  # Postpone handling until connected
        self.targpath = self.update_target_path(*self.targdest)

    def _generate_ops(self):
        open_op = prot.OpenOp(self.targpath, 'wb')
        yield open_op
        if open_op.failed():
            raise ex.JobException("Could not open target file %s"
                                  % self.targpath)
        write_op = prot.WriteOp(open_op.get_ticket(), self.hostpath, False)
        yield write_op
        if write_op.failed():
            simics.SIM_log_error(self.obj, 0, "Target copy %s is truncated" % (
                self.targpath))
        perm_op = prot.PermOp(open_op.get_ticket(), self.access)
        yield perm_op
        if perm_op.failed():
            simics.SIM_log_error(self.obj, 0, "Target %s permission defaulted"
                                 % (self.targpath))
        close_op = prot.DiscardOp(open_op.get_ticket())
        yield close_op


class UploadDirJob(MaticJob):
    """Recursively upload a whole directory tree."""
    name = "upload-dir"

    def __init__(self, obj, hostpath, targpath, follow=False, no_hidden=False,
                 overwrite=False, verbose=False):
        MaticJob.__init__(self, obj)
        self.targdest = (self.get_pwd(), targpath if targpath else "")
        self.targpath = None
        self.hostpath = hostpath
        self.hostbase = os.path.abspath(os.path.dirname(hostpath))
        self.verbose = verbose
        self.no_hidden = no_hidden
        self.overwrite = overwrite
        self.follow = follow
        if not os.path.isdir(hostpath):
            raise ex.JobException("Source path %s not found" % hostpath)
        # Statistics
        self.skipped = 0
        self.unreadable = 0
        self.overwritten = 0
        self.new_dirs = 0
        self.new_files = 0
        self.new_links = 0

    def _prepare_job(self):
        if self.targpath:
            return  # Already prepared
        if not self.is_connected():
            return  # Postpone handling until connected
        self.targpath = self.update_target_path(*self.targdest)

    def _host_path(self, *parts):
        return os.path.normpath(os.path.join(self.hostbase, *parts))

    def _targ_path(self, *parts):
        if self.targpath == None:
            raise ex.JobException("Target type not yet known")
        if self.is_windows():
            pth = ntpath.normpath(ntpath.join(self.targpath, *parts).replace(
                posixpath.sep, ntpath.sep))
            return pth
        else:
            pth = posixpath.normpath(posixpath.join(
                self.targpath, *parts).replace(ntpath.sep, posixpath.sep))
            return pth

    def _log_item(self, stat, reason):
        upstr = stat.get_type()
        upstr += " for " if upstr.startswith('unknown') else " "
        upstr += "%s %s" % (stat.get_path(), reason)
        simics.SIM_log_info(1 if self.verbose else 2, self.obj, 0, upstr)

    # Generator for the next file or directory.
    def _next_tree_item(self):
        def onerr(e):
            self.errors += 1
            simics.SIM_log_error(self.obj, 0, str(e))
        basedir = os.path.dirname(self.hostpath)
        for (path, _, files) in os.walk(self.hostpath, True, onerr, self.follow):
            reldir = os.path.relpath(path, basedir)
            yield (reldir, "")
            if self.no_hidden:
                files = [f for f in files if not f.startswith('.')]
            for f in files:
                yield (reldir, f)

    # Generate the next target stat operation.
    def _next_stat_op(self):
        """Create a list of StatOp's for all files and directories."""
        for (dp, fn) in self._next_tree_item():
            hpath = self._host_path(dp, fn)
            rpath = os.path.join(dp, fn)
            tpath = self._targ_path(dp, fn)
            simics.SIM_log_info(4, self.obj, 0, "path %s: host %s -> target %s"
                                % (rpath, hpath, tpath))
            try:
                yield prot.StatOp(rpath, tpath, hpath, self.follow, True)
            except OSError as e:
                self.skipped += 1
                simics.SIM_log_info(1, "%s skipped: %s" % (rpath, str(e)))

    # Generator for file operations: open, write and close.
    def _file_op(self, stat):
        if stat.target_exists() and not stat.is_same_type():
            assert self.overwrite
            rmfl = prot.RemoveOp(stat.get_target_path())
            yield rmfl
            if rmfl.failed():
                raise ex.JobException("Unable to remove %s %s" % (
                    stat.get_target_type(), stat.get_target_path()))
        fopen = prot.OpenOp(stat.get_target_path(), 'wb')
        yield fopen
        if fopen.failed():
            raise ex.JobException("Unable to open %s" % fopen.get_path())
        self.new_files += 1
        self._log_item(stat, "uploaded")
        try:
            wrop = prot.WriteOp(fopen.get_ticket(), stat.get_host_path())
        except ex.ProtIOError as e:
            simics.SIM_log_error(self.obj, 0, str(e))
            return
        yield wrop
        if wrop.failed():
            raise ex.JobException("Write to %s failed after %d bytes" % (
                wrop.get_file_name(), wrop.bytes_written()))
        dcop = prot.DiscardOp(fopen.get_ticket())
        yield dcop
        if dcop.failed():
            raise ex.JobException("Unable to close the ticket (%d) for %s" % (
                fopen.get_ticket(), fopen.get_path()))

    def _link_op(self, stat):
        if self.is_windows():
            self.skipped += 1
            self._log_item(stat, "skipped (not supported)")
            return
        if stat.target_exists():
            if self.overwrite:
                rmfl = prot.RemoveOp(stat.get_target_path())
                yield rmfl
                if rmfl.failed():
                    raise ex.JobException("Unable to remove soft-link %s" % (
                        stat.get_target_path()))
            else:
                self.skipped += 1
                self._log_item(stat, "skipped (already exists)")
                return
        link = prot.LinkOp(stat.get_link_path(), stat.get_target_path())
        yield link
        if link.failed():
            raise ex.JobException("Unable to create soft-link %s -> %s" % (
                stat.get_link_path(), stat.get_host_path()))
        self.new_links += 1
        self._log_item(stat, "created")

    def _generate_ops(self):
        for stat in self._next_stat_op():
            yield stat
            if stat.failed():
                simics.SIM_log_error(
                    self.obj, 0, "Unable to stat target %s" % (
                        stat.get_target_path()))
            elif (stat.target_exists() and not stat.is_same_type() and
                  not self.overwrite):  # parenthesis added for indentation
                raise ex.JobException(
                    "File type mismatch for %s (%s on host versus %s on target)"
                    % (stat.get_path(), stat.get_host_type(),
                       stat.get_target_type()))
            elif stat.target_exists() and stat.is_dir():
                pass  # existing directories are ok
            elif stat.target_exists() and not self.overwrite:
                self.skipped += 1
                self._log_item(stat, "skipped (already exists)")
            elif stat.is_dir():  # not existing
                mkd = prot.MkdirOp(stat.get_target_path(), stat.get_mode())
                yield mkd
                if mkd.succeeded():
                    self.failed_error = False  # At least one must succeed
                self.new_dirs += int(mkd.succeeded())
                self._log_item(stat, "created")
            elif stat.is_file():
                for op in self._file_op(stat):
                    yield op
            elif stat.is_softlink():  # not following the soft-link
                for op in self._link_op(stat):
                    yield op
            elif stat.is_special():
                self.skipped += 1
                self._log_item(stat, "skipped (not supported)")
            else:
                raise ex.JobException("Unknown file type (0x%x)"
                                          % stat.get_mode())

    def _get_status(self):
        return (self.hostpath, self.new_dirs, self.new_files, self.new_links,
                self.unreadable, self.skipped, self.errors)

    def finished(self):
        infos = []
        if self.new_dirs:
            infos += ["%d director%s created" % (
                self.new_dirs, "ies" if self.new_dirs > 1 else "y")]
        if self.new_files:
            infos += ["%d file%s uploaded" % (
                self.new_files, "s" if self.new_files > 1 else "")]
        if self.new_links:
            infos += ["%d soft-link%s created" % (
                self.new_links, "s" if self.new_links > 1 else "")]
        if self.unreadable:
            infos += ["%d unreadable file%s ignored" % (
                self.unreadable, "s" if self.unreadable > 1 else "")]
        if self.skipped:
            infos += ["%d file%s skipped (use -overwrite to replace)" % (
                self.skipped, "s" if self.skipped > 1 else "")]
        if self.errors:
            infos += ["%d error%s" % (
                self.errors, "s" if self.errors > 1 else "")]
        if not infos:
            infos += ["nothing to do"]
        self.logstr = ", ".join(infos)
        MaticJob.finished(self)
