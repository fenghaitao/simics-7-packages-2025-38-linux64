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


import collections
import posixpath
import ntpath
import simics
import cli
from . import jobs
from . import exceptions as ex
from simicsutils.internal import ensure_text

class AgentHandle:
    """Agent Handle class"""

    def __init__(self, obj):
        self.obj = obj
        self.chan = None
        self.ids = {}
        self._next_id = 0
        self.manager = None
        self.jobs = collections.deque()
        self.capture = {}
        self.completed = 0
        self.cancelled = 0
        self.name = None
        self.path = ""
        self.windows = None
        self.pending_tmo = None
        self.disconnected = False

    def __str__(self):
        return self.name

    def connect_to(self, name, connect_to=None):
        self.name = name
        job = jobs.ConnectToJob(self.obj, connect_to)
        if not self.manager:
            mc_obj = list(simics.SIM_object_iterator_for_class(
                simics.SIM_get_class("agent_manager")))[0]
            self.manager = mc_obj.object_data
        ok = self.manager.connect_to_agent(self, job)
        if not ok:
            self.new_job(job)
        else:
            self._next_id += 1
        return ok

    def print_connection(self):
        if self.chan:
            return "%s connected to %s" % (self.name, self.chan)
        else:
            return self._job_print(self.jobs[0])

    def connected(self, chn):
        if self.chan:
            raise ex.JobException("%s is already connected to %s, ignoring %s"
                                  % (self.name, self.chan, chn))
        self.chan = chn
        if not self.path:
            self.path = self.initial_path()
        if self.pending_tmo:
            self.chan.set_stale_timeout(self.pending_tmo)
            self.pending_tmo = None

    def initial_path(self):
        if self.is_windows():
            return ntpath.normpath('c:\\')
        return posixpath.normpath('/')

    def capable_of(self, cap):
        if not self.chan:
            return True
        if cap in self.chan.cap:
            return True
        return False

    def version_min(self, ver):
        if not self.chan:
            return None
        v = float(self.chan.info['agent'].split(' ')[0])
        return v >= float(ver)

    def version_max(self, ver):
        if not self.chan:
            return None
        v = float(self.chan.info['agent'].split(' ')[0])
        return v <= float(ver)

    def disconnect(self, _=None):
        self.disconnected = True
        if self.jobs:
            self.discard_all_jobs()
        if self.unblock():
            return False  # Postpone handling until awoken
        if self.chan:
            simics.SIM_log_info(1, self.obj, 0,
                                "disconnected from %s" % self.chan)
            self.chan.discard_handle(self.name)
            self.chan = None
        elif self.manager and self.jobs:
            self.manager.stop_waiting_for_agent(self)
        self.manager = None
        return True

    def unblock(self):
        job = self._blocking_job()
        if not job:
            return False
        self._cancel_job(job)
        return True

    # Can only be blocking on one job
    def _blocking_job(self):
        for job in self.jobs:
            if job.is_blocking():
                return job
        return None

    def is_connected(self):
        if not self.disconnected:
            return self.chan != None
        return False

    def is_disconnected(self):
        return self.disconnected

    def is_blocking(self):
        return self._blocking_job() != None

    def get_magic(self):
        if not self.chan:
            return None
        return self.chan.magic

    def is_stale(self):
        if self.disconnected:
            return True
        if not self.chan:
            return False
        return self.chan.is_stale()

    def get_stale_timeout(self):
        if self.disconnected or not self.chan:
            return 0.0
        return self.chan.get_stale_timeout()

    def set_stale_timeout(self, val):
        if self.disconnected:
            return simics.Sim_Set_Not_Writable
        if not self.chan:
            self.pending_tmo = val
            return simics.Sim_Set_Ok
        return self.chan.set_stale_timeout(val)

    def is_windows(self):
        if self.windows != None:
            return self.windows
        if self.disconnected or not self.chan:
            return None
        return self.chan.windows

    def set_windows(self, val):
        self.windows = val

    def _cancel_job(self, job):
        job.cancel = True
        first = self.jobs[0]
        self.jobs.remove(job)
        del self.ids[job.id]
        self.cancelled += 1
        simics.SIM_log_info(1, self.obj, 0, "%s cancelled"
                            % self._job_string(job))
        self._signal_hap(job)
        if job is first:
            if self.chan:
                self.chan.cancel_job(job)
            return True
        return False

    def _schedule_job(self):
        if self.is_stale():
            self.discard_all_jobs()
        elif self.jobs and self.chan:
            job = self.jobs[0]
            simics.SIM_log_info(4, self.obj, 0,
                                "scheduled the next job, %s (#%d)"
                                % (job, job.id))
            self.chan.queue_job(job)

    def _signal_hap(self, job):
        hapt = self.manager.job_hap_t
        if job.get_hap_id() != None:
            simics.SIM_hap_occurred_always(hapt, self.obj, job.id, [])
        if job.get_wait_id() != None:
            cli.sb_signal_waiting(job.get_wait_id())

    def new_job(self, job):
        if self.is_stale():
            raise ex.JobException("Handle is stale")
        job.id = self._next_id
        self._next_id += 1
        self.ids[job.id] = job
        self.jobs.append(job)
        if len(self.jobs) == 1:
            self._schedule_job()
        return job.id

    def discard_jobs(self, jids=[]):
        if not self.jobs:
            raise ex.JobException("The job queue is empty")
        if not jids:
            self.discard_all_jobs()
            return
        for jid in jids:
            if jid not in self.ids:
                raise ex.JobException("Unknown job ID: %d" % jid)
        resched = False
        for jid in jids:
            job = self.ids[jid]
            if self._cancel_job(job):
                resched = True
        if resched:
            self._schedule_job()

    def discard_all_jobs(self):
        self.cancelled += len(self.jobs)
        if self.jobs and self.chan:
            job = self.jobs[0]
            self.chan.cancel_job(job)
            if job.is_blocking():
                self._signal_hap(job)
        for job in self.jobs:
            simics.SIM_log_info(1, self.obj, 0, "%s cancelled"
                                % self._job_string(job))
        self.jobs = collections.deque()

    # Called only by the MaticChannel
    def job_done(self, job):
        job_name = self._job_string(job)
        if job.get_owner_name() != self.name:
            raise ex.ManagerException("%s belongs to %s, not me (%s)" % (
                job_name, job.get_owner_name(), self.name))
        if job.is_done():
            self.completed += 1
            if job.has_captured_output():
                self.capture[job.id] = (
                    str(job), ensure_text(job.get_captured_output()))
            if job.has_log_info():
                simics.SIM_log_info(1, self.obj, 0, job.get_log_string())
            failed = job.has_error_report()
            if failed:
                simics.SIM_log_error(self.obj, 0, "%s error message: %s" % (
                    job_name, job.get_error_report()))
            simics.SIM_log_info(3, self.obj, 0, "%s %s" % (
                job_name, "failed" if failed else "completed"))
        else:
            self.cancelled += 1
            simics.SIM_log_info(1, self.obj, 0, "%s already cancelled by %s" % (
                job_name, self.chan))
        del self.ids[job.id]
        first = self.jobs.popleft()
        if not job is first:
            raise ex.ManagerException("%s is not first in queue: (#%d) '%s'"
                                      % (job_name, first.id, first))
        self._schedule_job()
        self._signal_hap(job)

    def get_info(self):
        if self.chan:
            rows = [("Connected to", self.get_connection())]
            rows += list(self.chan.info.items())
        elif self.jobs:
            to = self.jobs[0].to if self.jobs[0].to else "*"
            rows = [("Connecting to", to)]
        else:
            rows = [("Connection", "Disconnected")]
        return [(None, rows)]

    def get_poll_interval_ms(self):
        return round(self.chan.get_poll_time() * 1000) if self.chan else None

    def get_status(self):
        rows = [("State", self.get_state())]
        if self.chan:
            poll = self.chan.get_poll_time()
            last = self.chan.time_since_last_hap()
            rows += [("Poll time", "%.3f s when idle" % poll)]
            if last < poll:
                rows += [("Next update", "in %.3f s" % (poll - last))]
            else:
                rows += [("Last update", "%.3f s ago" % last)]
        rows += [("Completed Jobs", str(self.completed))]
        rows += [("Cancelled Jobs", str(self.cancelled))]
        rows += [("Queued Jobs", str(len(self.jobs)))]
        for job in self.jobs:
            rows.append(("#%d" % job.id, job.print_state()))
        return [(None, rows)]

    def get_state(self):
        if self.is_stale():
            return "disconnected"
        if not self.chan:
            return "connecting"
        if not self.jobs:
            return "idle"
        job = self.jobs[0]
        if job.reqs > job.haps:
            return "working"
        elif job.haps:
            return "waiting"
        return "queueing"

    def get_connection(self):
        return self.chan.id if self.chan else ""

    def get_pwd(self):
        return self.path

    def set_pwd(self, path):
        if self.is_windows():
            self.path = ntpath.normpath(ntpath.join(self.path, path))
        else:
            self.path = posixpath.normpath(posixpath.join(self.path, path))
        return self.path

    def captured_output(self, job_id):
        return self.capture.pop(job_id, (None, None))

    def captured_list(self):
        return [(key, self.capture[key][0]) for key in sorted(self.capture)]

    def _job_string(self, job):
        return "Job %d (%s)" % (job.id, job)

    def _job_print(self, job):
        return "%s:j%s" % (self.name, self._job_string(job)[1:])

    def _get_job(self, jid):
        if jid and jid > 0:
            try:
                job = self.ids[jid]
            except KeyError:
                raise ex.JobException("%s:job %d does not exist" % (self, jid))
        else:
            try:
                job = self.jobs[-1]
            except IndexError:
                raise ex.JobException("Job queue is empty")
        return job

    def run_until_job(self, jid):
        job = self._get_job(jid)
        if simics.SIM_simics_is_running():
            raise ex.JobException("Simics is already running")
        if self.is_stale():
            raise ex.JobException("Handle is stale")
        if job.is_blocking():
            raise ex.JobException("Handle is already blocking")

        def run_until_done(job, obj):
            simics.VT_stop_finished("%s finished" % self._job_print(job))

        hap = "Internal_Matic_Run_Until"
        hap_id = simics.SIM_hap_add_callback_obj_index(
            hap, self.obj, 0, run_until_done, job, job.id)
        job.block_add_hap(hap_id)
        try:
            simics.SIM_continue(0)
        finally:
            simics.SIM_hap_delete_callback_id(hap, hap_id)
            job.block_rem_hap(hap_id)

    def wait_for_job(self, jid):
        job = self._get_job(jid)
        if self.is_stale():
            raise ex.JobException("Handle is stale")
        if job.is_blocking():
            raise ex.JobException("Handle is already blocking")
        wid = cli.sb_get_wait_id()
        job.block_add_sb(wid)
        try:
            cli.sb_wait("wait-for-job", wid, wait_data="%d" % jid)
        finally:
            job.block_rem_sb(wid)
