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


# Linux only probes where we dig out useful information from the /proc filesystem

import os
import simicsutils
import conf
from simics import *

from .common import listify
from .probe_cache import cached_probe_read

from . import sketch

# Read all /proc/self/task/*/stat files and return list of the contents
# Only works on linux
def read_all_thread_stats():
    base_dir = '/proc/self/task'
    stats = []
    for d in os.listdir(base_dir):
        # Read the stat file to get statistics on each thread
        # See man procfsGet hold of how much time it has been scheduled
        try:
            with open(os.path.join(base_dir, d, 'stat')) as f:
                stats.append(f.read().strip())
        except FileNotFoundError:
            continue            # Thread has died
    return stats

# Per thread object with statistics
class ThreadInfo:
    __slots__ = ('tid', 'thread_name', 'jiffies')
    def __init__(self, tid, thread_name, jiffies):
        self.tid = tid
        self.thread_name = thread_name
        self.jiffies =  jiffies # both user and system time

    def update(self, tid, thread_name, jiffies):
        assert self.tid == tid
        assert self.thread_name == thread_name
        self.jiffies = jiffies

# Singlton object remembering all the threads and thread groups
class ThreadGroups:
    __slots__ = ('thread_groups', 'known_tids')
    def __init__(self, stat_list):
        self.thread_groups = {} # { threadgroup: [ThreadInfo*] }
        self.known_tids = {}    # { tid: ThreadInfo }
        self.update(stat_list)

    def update(self, stat_list):
        for stat in stat_list:
            # The comm-string is surrounded by "()" (string could have spaces)
            fields = stat.split(') ')
            # Add an empty field first to get indexing according to man page
            fields = [None] + fields[0].split(' (') + fields[1].split()
            tid = int(fields[1])
            comm = fields[2]
            utime = int(fields[14])
            stime = int(fields[15])

            jiffies = utime + stime
            thread_name = comm
            self.thread_groups.setdefault(thread_name, set())

            if tid in self.known_tids:
                t_info = self.known_tids[tid]
                t_info.update(tid, thread_name, jiffies)
            else:
                t_info = ThreadInfo(tid, thread_name, jiffies)
                self.thread_groups[thread_name].add(t_info)
                self.known_tids[tid] = t_info

    def report(self):
        l = []
        for g in self.thread_groups:
            jiffies = sum([t.jiffies for t in self.thread_groups[g]])
            seconds = jiffies / float(jiffies_per_second)
            l.append([g, seconds])
        return l

# Singelton object remembering all threads seen
class Threads:
    __slots__ = ('known_tids')
    def __init__(self, stat_list):
        self.known_tids = {}    # { tid: ThreadInfo }
        self.update(stat_list)

    def update(self, stat_list):
        for stat in stat_list:
            # The comm-string is surrounded by "()" (string could have spaces)
            fields = stat.split(') ')
            # Add an empty field first to get indexing according to man page
            fields = [None] + fields[0].split(' (') + fields[1].split()
            tid = int(fields[1])
            comm = fields[2]
            utime = int(fields[14])
            stime = int(fields[15])

            jiffies = utime + stime
            thread_name = comm
            if tid in self.known_tids:
                t_info = self.known_tids[tid]
                t_info.update(tid, thread_name, jiffies)
            else:
                t_info = ThreadInfo(tid, thread_name, jiffies)
                self.known_tids[tid] = t_info

    def report(self):
        return [[f"{t.thread_name}-{t.tid}", t.jiffies / float(jiffies_per_second)]
                for t in self.known_tids.values()]


class ProcfsCache:
    @cached_probe_read
    def read(self):
        return read_all_thread_stats() if is_linux else []

# We cache the procfs time in its own singleton object
# This is needed when we share the cache over multiple different probes
# in different classes
procfs_cache = ProcfsCache()

class ThreadGroupHistogram:
    cls = confclass("probe_thread_group_histogram", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for thread execution histogram.")

    @cls.iface.probe
    def value(self):
        stat_list = procfs_cache.read()
        thread_groups.update(stat_list)
        return thread_groups.report()

    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "sim.process.thread_group_histogram"),
             (Probe_Key_Display_Name, "Thread Group Histogram"),
             (Probe_Key_Unit, "s"),
             (Probe_Key_Float_Decimals, 2),
             (Probe_Key_Description,
              "Linux only. Returns a histogram of the different thread groups"
              " in Simics and how much time each thread group have been"
              " scheduled in Linux."
              " Each thread group can consist of multiple threads."),
             (Probe_Key_Type, "histogram"),
             (Probe_Key_Categories, ["process", "thread"]),
             (Probe_Key_Width, 40),
             (Probe_Key_Owner_Object, conf.sim)])

class ThreadExecutionHistogram:
    cls = confclass("probe_thread_histogram", pseudo = True,
                    short_doc = "internal class",
                    doc = "Probe class for thread execution histogram.")

    @cls.iface.probe
    def value(self):
        stat_list = procfs_cache.read()
        threads.update(stat_list)
        return threads.report()

    @cls.iface.probe
    def properties(self):
        return listify(
            [(Probe_Key_Kind, "sim.process.thread_histogram"),
             (Probe_Key_Display_Name, "Thread Histogram"),
             (Probe_Key_Unit, "s"),
             (Probe_Key_Float_Decimals, 2),
             (Probe_Key_Description,
              "Linux only. Returns a histogram of the different threads"
              " in Simics and how much time each thread have been "
              " scheduled by Linux."),
             (Probe_Key_Type, "histogram"),
             (Probe_Key_Categories, ["process", "thread"]),
             (Probe_Key_Width, 40),
             (Probe_Key_Owner_Object, conf.sim)])

def create_probe_sketches():
    objs = []
    objs += sketch.new("probe_thread_histogram",
                       "sim.probes.sim.process.thread_histogram")
    objs += sketch.new(
        "probe_thread_group_histogram",
        "sim.probes.sim.process.thread_group_histogram")

    return objs


is_linux = simicsutils.host.is_linux()
if is_linux:
    # Jiffies reported in procfs depends on the frequency
    n = os.sysconf_names['SC_CLK_TCK']
    jiffies_per_second = os.sysconf(n)

# Create our singleton objects early, to see the threads we have initially
stat_list = read_all_thread_stats() if is_linux else []
thread_groups = ThreadGroups(stat_list)
threads = Threads(stat_list)
