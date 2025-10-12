# © 2014 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import cli
import simics
import simicsutils.host
import os
import threading
import math
import struct
import errno
import signal
import subprocess
import conf

class Pcap:
    def __init__(self, fileobj, linktype, ns_resolution = False):
        self.__file = fileobj
        self.lock = threading.Lock()
        self.ns_resolution = ns_resolution
        self.__write_header(linktype, ns_resolution)

    def __write_header(self, linktype, ns_resolution):
        if ns_resolution:
            magic = 0xa1b23c4d
        else:
            magic = 0xa1b2c3d4
        major = 2
        minor = 4
        thiszone = 0
        sigfigs = 0
        snaplen = 2048
        self.__file.write(struct.pack('IHHIIII', magic, major, minor, thiszone,
                                      sigfigs, snaplen, linktype))

    def write_frame(self, clock, frame):
        with self.lock:
            fsec, isec = math.modf(simics.SIM_time(clock))
            self.__file.write(struct.pack('IIII', int(isec), int(1e9 * fsec) \
                                          if self.ns_resolution else \
                                          int(1e6 * fsec), len(frame) + 4,
                                          len(frame) + 4))

            # Add preamble
            self.__file.write(struct.pack('I', 0))

            self.__file.write(frame)

    def close(self):
        with self.lock:
            self.__file.close()

ongoing_pcap_dumps = {}

def check_obj_instantiated(obj):
    if hasattr(obj.iface, 'component') and not obj.instantiated:
        raise cli.CliError("object '%s' is not instantiated" % obj)

def fullpath(binary):
    binary_paths = [x for x in
                    [os.path.join(y, binary)
                     for y in os.environ['PATH'].split(':')]
                    if os.path.exists(x)]
    return binary_paths[0] if binary_paths else None

def kill_process(pid):
    if simicsutils.host.is_windows():
        import win32api, win32con
        try:
            h = win32api.OpenProcess(win32con.PROCESS_TERMINATE, 0, pid)
            if h != None:
                win32api.TerminateProcess(h, 1)
                win32api.CloseHandle(h)
        except win32api.error:
            # The process probably no longer exists - no complaints.
            pass
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            # The process probably no longer exists - no complaints.
            pass

def try_start_program(args, **kwords):
    try:
        return subprocess.Popen(args, **kwords)
    except OSError as e:
        # Python translates windows errors from CreateProcess to Posix
        # error codes in e.errno.
        if e.errno == errno.ENOENT:
            return None
        raise cli.CliError(f'OSError: {e}')

def start_capture(pcap, probe, pid=None):
    print("Starting capture on %s" % probe)
    def write_frame(clock, frame):
        try:
            pcap.write_frame(clock, frame)
        except OSError as e:
            print(f"Failed writing frame: {e.strerror} (error code {e.errno})")
            # If the write fails, just close the capture to avoid further
            # errors. stop_capture needs to run in Global Context.
            simics.SIM_run_alone(lambda d: stop_capture(probe), None)

    def callback(user_data, probe, to_side, frame, rssi,
                 channel_page, channel_number, crc_status):
        write_frame(probe.queue, frame)

    probe.iface.ieee_802_15_4_probe.attach_snooper(callback, None)
    ongoing_pcap_dumps[repr(probe)] = (pcap, pid)

def pcap_dump_start(probes, filename, linktype, ns_resolution):
    for l in probes:
        stop_capture(l)
    try:
        pcap = Pcap(open(filename, 'wb', 0), linktype, ns_resolution)
    except Exception as ex:
        raise cli.CliError("Failed starting pcap: %s" % ex)
    for l in probes:
        start_capture(pcap, l, None)

def capture_stop_cmd(obj):
    stop_capture(obj)

def stop_capture(probe):
    try:
        pcap, pid = ongoing_pcap_dumps[repr(probe)]
    except KeyError:
        # No pcap dump in progress for this link
        return
    del ongoing_pcap_dumps[repr(probe)]
    print("Stopping capture on %s" % probe)

    # find out if pcap and pid are still used for other links
    destroy_pcap = True
    kill_pid = True
    for k in ongoing_pcap_dumps:
        o_pcap, o_pid = ongoing_pcap_dumps[repr(k)]
        if o_pcap == pcap:
            destroy_pcap = False
        if o_pid == pid:
            kill_pid = False

    if pid and kill_pid:
        kill_process(pid)

    probe.iface.ieee_802_15_4_probe.detach()

    # close all capture files
    if destroy_pcap:
        try:
            pcap.close()
        except OSError:
            # if this was a pipe, it was probably already broken
            pass

def pcap_dump_cmd(obj, filename, linktype, ns_resolution):
    check_obj_instantiated(obj)
    pcap_dump_start([obj], filename, linktype, ns_resolution)

def external_capture(probes, read_fd, write_fd, args, linktype):
    pid = os.fork()
    if pid == 0:
        os.close(write_fd)
        os.setsid()
        os.execl(*args)
    else:
        os.close(read_fd)
        pcap = Pcap(os.fdopen(write_fd, 'wb', 0), linktype)
        for p in probes:
            start_capture(pcap, p, pid)

def tcpdump_start(probes, flags, linktype):
    for p in probes:
        stop_capture(p)
    xterm_path = fullpath("xterm")
    if not xterm_path:
        raise cli.CliError("No 'xterm' binary found in PATH")
    tcpdump_path = fullpath("tcpdump")
    if not tcpdump_path:
        raise cli.CliError("No 'tcpdump' binary found in PATH.")
    (read_fd, write_fd) = os.pipe()
    external_capture(probes, read_fd, write_fd,
                    [xterm_path, 'xterm', '-title', 'tcpdump', '-e',
                     'tcpdump -r - %s <&%d' % (flags, read_fd)],
                     linktype)


def tcpdump_cmd(obj, flags, linktype):
    check_obj_instantiated(obj)
    tcpdump_start([obj], flags, linktype)

def ethereal_cmd(obj, flags, linktype):
    check_obj_instantiated(obj)
    ethereal_start([obj], flags, linktype)

def ethereal_start(probes, flags, linktype):
    for probe in probes:
        stop_capture(probe)

    def preexec():
        if 'setsid' in dir(os):
            os.setsid()

    win = simicsutils.host.is_windows()
    for prog in ["wireshark", "ethereal"]:
        if win:
            # We don't have a good stdout/stderr when running in GUI mode
            # on Windows; use a null file to keep subprocess from crashing
            # (bug 18837).
            out = subprocess.DEVNULL
            err = subprocess.STDOUT

            if not conf.prefs.wireshark_path and 'PATH' in os.environ:
                for x in os.environ['PATH'].split(';'):
                    p = os.path.join(x, prog+".exe")
                    if os.path.exists(p):
                        prog = p
                        break
        else:
            out = err = None
        if conf.prefs.wireshark_path:
            prog = os.path.join(conf.prefs.wireshark_path, prog)

        args = ['-k', '-i', '-']
        if prog == "wireshark":
            win_title = ', '.join(p.name for p in probes)
            args += ['-o', 'gui.window_title:%s' % win_title]

        p = try_start_program([prog] + args + flags.split(),
                              stdin=subprocess.PIPE, stdout=out, stderr=err,
                              close_fds=not win,
                              preexec_fn=preexec if not win else None)
        if p:
            break

    if not p:
        raise cli.CliError("Neither 'wireshark' nor 'ethereal' could be"
                       " started. Set the prefs->wireshark_path to"
                       " specify the directory where the wireshark"
                       " binaries are install or include that directory"
                       " in the PATH environment variable.")
    pcap = Pcap(p.stdin, linktype)
    for probe in probes:
        start_capture(pcap, probe, p.pid)
