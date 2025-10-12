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


import os
import collections
import threading
import simics
import cli
from . import jobs
from . import buffer
from . import exceptions as ex

class MaticChannel:
    """Matic channel class"""

    def __init__(self, mgr, pipe, cpu, info, debug=False):
        self.manager = mgr
        self.obj = mgr.obj
        self.buf = None
        self.magic = None
        self.haps = 1
        self.jobs = collections.deque()
        self.fin = 0
        self.info = info
        self.handles = set()
        self.debug = debug
        self.stale = False
        self.id = None
        self._last = (None, 0, "")
        self.hndl = None
        self.pipe = pipe
        self.timestamp = None
        self.lock = threading.Lock()
        self.suif = pipe.iface.magic_pipe_setup
        if self.debug:
            simics.SIM_log_info(4, self.obj, 0, "AGENT: %s" % info)
        try:
            self.name = self.info["name"]
            if not self.name:
                self.name = self.info["hostname"]
            self.cap = self.info["capabilities"].split(',')
            self.vers = self.info["agent"].split(' ')[0]
            self.magic = int(self.info.get("magic", 0), 0)
        except KeyError as e:
            raise ex.ChannelException("Missing agent information in: %s\n%s"
                                      % (info, str(e)))
        except ValueError as e:
            raise ex.ChannelException("Malformed agent information in: %s\n%s"
                                      % (info, str(e)))
        # Create unique name
        self.id = "%s%s%d" % (
            self.name, "_" if self.name[-1].isdigit() else "",
            mgr.make_channel_id(self.name, self.magic))
        # Register a hap timeout event, and start the hap timeout
        self.tmo_set = False
        self.tmo_name = self.id + "_hap_timeout"
        self.tmo_ev = None
        simics.SIM_run_alone(self.register_timeout_event, cpu)
        # Subscribe to the new magic identity
        if self.magic:
            self.suif.register_reserved_pipe(
                self.obj, self.magic, self.response, self.request)
        else:
            self.magic = self.suif.register_new_pipe(
                cpu, self.obj, self.response, self.request)
            self.info["magic"] = self.magic
        # Set poll time depending on target system architecture
        self.windows = "WINDOWS" in self.cap
        if self.windows:
            self.polltime = 1.0      # The graphics will make the system slow
            self.polltimeout = 20.0  # Windows has long scheduling periods
        else:
            self.polltime = 10.0    # Default poll time
            self.polltimeout = 5.0  # Default allowed delay in poll-time

    def __str__(self):
        return "%s (0x%016x)" % (self.id, self.magic)

    def _release_handles(self, _):
        with self.lock:
            handles = self.get_handles()
        for hndl in handles:
            hndl.disconnect()

    def _retire(self):
        self.suif.unregister_pipe(self.obj, self.magic)
        self.manager.discard_channel(self)
        self.manager = None
        self.handles = set()
        self.jobs = collections.deque()
        self.pipe = None
        self.suif = None

    def register_timeout_event(self, cpu):
        self.tmo_ev = simics.SIM_register_event(
            self.tmo_name, simics.SIM_object_class(self.obj),
            simics.Sim_EC_Notsaved, self.got_hap_timeout,
            None, None, None, None)
        if cpu:
            self.start_hap_timeout(cpu)

    def _log_buffer(self, buf, job):
        if job and job.is_cancelled():
            return
        (req, rno) = buf._get_request()
        (ply, pno) = buf._get_response()
        act = "got" if buf.code & 0xf else "sent"
        own = job.get_owner_name() if job else self.name
        simics.SIM_log_info(4, self.obj, 0,
                            "%s (0x%016x) %s %s-%s (0x%03x_%x) for '%s'" % (
                                own, self.magic, act, req, ply, rno, pno, job))

    def short_description(self):
        return "%s: %d queued jobs" % (self.get_state(), self.count_jobs())

    def long_description(self):
        ostr = "%s, %d haps, %d finished jobs (matic-%s)" % (
            self.short_description(), self.haps, self.fin, self.vers)
        jstr = self.print_jobs()
        return ostr + jstr

    def print_jobs(self):
        ostr = ""
        for job in self.jobs:
            ostr += "\n\t%s: %s (%s:job %d)" % (
                job, job.print_state(), job.get_owner_name(), job.id)
        return ostr

    def time_since_last_hap(self):
        # This function is only called from get_status in the handle, as a best
        # effort value to show the user in the status command. It does not have
        # to be totally accurate, and is just provided as a help for the user.
        if not self.timestamp:
            return 0
        (_, last_time) = self.timestamp
        # last_cpu may belong to another thread. Do not use it.
        # Pick the current frontend cpu instead, which may fail.
        cpu = cli.current_frontend_object(cpu=True)
        curr_time = simics.SIM_time(cpu)
        return curr_time - last_time

    def get_poll_time(self):
        return self.polltime

    def is_stale(self):
        return self.stale

    def get_stale_timeout(self):
        return self.polltimeout

    def set_stale_timeout(self, val):
        if val < 0.1:  # Minimum 100 ms
            return simics.Sim_Set_Illegal_Value
        self.polltimeout = float(val)
        simics.SIM_run_alone(self.update_hap_timeout, None)
        return simics.Sim_Set_Ok

    def queue_job(self, job):
        owner = job.get_owner_name()
        if owner not in self.handles:
            raise ex.ChannelException(
                "Agent Handle %s must connect to %s before queueing job %s"
                % (owner, self, job))
        with self.lock:
            pos = len(self.jobs)
            self.jobs.append(job)
        if pos > 0:
            qpo = "queue at position %d" % pos
        else:
            qpo = "head of queue"
        simics.SIM_log_info(4, self.obj, 0, "%s job added to %s for %s (0x%016x)"
                            % (job, qpo, self.id, self.magic))
        return pos

    def cancel_job(self, job):
        with self.lock:
            if not self.jobs:
                return
            first = self.jobs[0]
            if job is first and job.is_active():
                job.cancel = True
            else:
                self.jobs.remove(job)

    def count_jobs(self):
        jobs = [job for job in self.jobs if not job.is_cancelled()]
        return len(jobs)

    def get_state(self):
        if self.is_stale():
            return "stale"
        if not self.jobs:
            return "idle"
        if not self.jobs[0].haps:
            return "waiting"
        return "active"

    def get_info(self):
        if self.timestamp:
            (cpu, _) = self.timestamp
            self.info['last_cpu'] = cpu.name
        return self.info

    def start_hap_timeout(self, cpu, tmo=None):
        if self.tmo_set:
            return
        self.timestamp = (cpu, simics.SIM_time(cpu))
        if not tmo:
            tmo = self.polltime + self.polltimeout
        simics.SIM_event_post_time(cpu, self.tmo_ev, self.obj, tmo, None)
        self.tmo_set = True

    def reset_hap_timeout(self):
        if not self.tmo_set:
            return
        (cpu, _) = self.timestamp
        simics.SIM_event_cancel_time(cpu, self.tmo_ev, self.obj, None, None)
        self.tmo_set = False

    def restart_hap_timeout(self, cpu):
        self.reset_hap_timeout()
        self.start_hap_timeout(cpu)

    def update_hap_timeout(self, _):
        (cpu, start_time) = self.timestamp
        curr_time = simics.SIM_time(cpu)
        new_end_time = start_time + self.polltime + self.polltimeout
        tmo = new_end_time - curr_time if new_end_time > curr_time else 0
        self.reset_hap_timeout()
        self.start_hap_timeout(cpu, tmo)

    def got_hap_timeout(self, obj, data):
        simics.SIM_log_info(1, obj, 0, "Time-out for agent %s." % self)
        self.disconnect()

    def _debug_event(self, buf):
        (code, reps, msg) = self._last
        if buf.code != code:
            if reps >= 100:
                simics.SIM_log_info(3, self.obj, 0, "%s repeated %d times"
                                    % (msg, reps))
            msg = str(buf)
            self._last = (buf.code, 0, msg)
            simics.SIM_log_info(3, self.obj, 0, msg)
        else:
            simics.SIM_log_info(4, self.obj, 0, msg)
            self._last = (code, reps + 1, msg)

    def response(self, cpu, bufh, magic):
        assert self.magic == magic
        self.restart_hap_timeout(cpu)
        self.haps += 1
        try:
            self.buf = buffer.MaticBuffer(self.pipe, bufh)
        except ex.BufferException as e:
            simics.SIM_log_error(self.obj, 0, "Buffer " + str(e))
            return
        if self.debug:
            self._debug_event(self.buf)
        try:
            self._handle_response(self.buf)
        except ex.BufferException as e:
            simics.SIM_log_error(self.obj, 0, "Response " + str(e))
            job = self.jobs.popleft()  # remove the job from the queue
            job.finished()

    def _handle_response(self, buf):
        if not len(self.jobs):
            return  # no jobs, do nothing
        if buf.is_request():
            return  # Buffer is not in response to anything
        job = self.jobs[0]
        if not job.is_active() and not job.is_mine(buf):
            if buf.is_code(2):
                return  # ignore unexpected announcements
            simics.SIM_log_info(3, self.obj, 0, "Unexpected message\n%s:" % buf)
            return
        try:
            job.next_response(buf)
        except ex.JobException as e:
            simics.SIM_log_error(self.obj, 0,
                                 "got %s from %s for buf %s" % (e, job, buf))
        self._log_buffer(buf, job)
        if job.is_done() or job.is_cancelled():
            self.fin += 1  # Another finished job
            self._remove_job()
        else:
            self.jobs.rotate(-1)  # put the job at the end of the job queue

    def _remove_job(self):
        job = self.jobs.popleft()  # remove the job from the queue
        job.finished()
        # Some jobs require special handling...
        if job.is_done():
            if isinstance(job, jobs.PollIntervalJob):
                self.polltime = job.get_seconds()  # Update poll time
                self.restart_hap_timeout(self.timestamp[0])
            elif isinstance(job, jobs.AgentQuitJob):
                self.disconnect()

    def first_request(self, cpu, buf):
        self.timestamp = (cpu, simics.SIM_time(cpu))
        if len(self.jobs) > 0:
            self._handle_request(buf)
        else:
            # Respond with the new magic number for the agent, which will
            # prevent sleep and allow another opportunity for new jobs.
            buf._reset_data()
            buf.magic = self.magic
            buf.new_request(0, 0)
            buf._write_commit()
            self._log_buffer(buf, None)

    def request(self, cpu, bufh, magic):
        assert self.magic == magic
        assert self.buf
        assert self.buf.bufh == bufh
        if len(self.jobs) > 0:
            self._handle_request(self.buf)
        self.buf = None

    def _handle_request(self, buf):
        buf._reset_data()
        buf.magic = self.magic
        job = self.jobs[0]
        try:
            job.next_request(buf)
        except ex.JobDoneException:
            simics.SIM_log_info(3, self.obj, 0, "%s job %s done" % (self, job))
            self._remove_job()
            if len(self.jobs) > 0:
                self._handle_request(buf)
        else:
            self._log_buffer(buf, job)
            buf._write_commit()

    def connect(self, hndl, job=None):
        if hndl.is_disconnected():
            return
        if hndl.name in self.handles:
            raise ex.ChannelException(
                "Agent Handle %s is already connected to %s"
                % (hndl.name, self))
        self.handles.add(hndl.name)
        hndl.connected(self)
        if job:
            job.connected(self.id)
            hndl.job_done(job)

    def get_handles(self):
        objlist = [simics.VT_get_object_by_name(name) for name in self.handles]
        objlist += [self.hndl] if self.hndl else []
        return [obj.object_data for obj in objlist if obj]

    def _get_agent_handle(self):
        if not self.hndl:
            agman = list(simics.SIM_object_iterator_for_class(
                simics.SIM_get_class("agent_manager")))[0]
            name = agman.object_data.new_handle_name()
            self.hndl = simics.SIM_create_object("agent_handle", name, [])
            agth = self.hndl.object_data
            agth.connect_to(name, self.id)
            workpath = self.info.get("path", None)
            if workpath:
                agth.set_pwd(workpath)
            simics.SIM_log_info(4, self.obj, 0,
                                "New internal agent handle '%s' created."
                                % name)
        return self.hndl

    def discard_handle(self, name):
        with self.lock:
            self.handles.discard(name)
            if not self.handles:
                self._retire()

    def disconnect(self):
        self.stale = True
        self.reset_hap_timeout()
        simics.SIM_run_alone(self._release_handles, None)

    # From simulated target to host, i.e. agent upload
    def _matic_download(self, agent, src_path, dst_path, overwrite):
        try:
            job = jobs.DownloadJob(agent.obj, src_path, dst_path, overwrite)
        except ex.JobException as e:
            raise ex.MaticException(str(e))
        return (job, agent.new_job(job))

    # From host to simulated target, i.e. agent download
    def _matic_upload(self, agent, src, dest, overwrite, flush, executable):
        try:
            job = jobs.UploadJob(
                agent.obj, src, dest, overwrite, flush, executable)
        except ex.JobException as e:
            raise ex.MaticException(str(e))
        return (job, agent.new_job(job))

    # From simulated target to host, i.e. agent upload-dir
    def _matic_download_dir(self, agent, src_path, dst_path, follow, overwrite, verbose):
        try:
            job = jobs.DownloadDirJob(agent.obj, src_path, dst_path,
                                      follow, False, overwrite, verbose)
        except ex.JobException as e:
            raise ex.MaticException(str(e))
        return (job, agent.new_job(job))

    # From host to simulated target, i.e. agent download-dir
    def _matic_upload_dir(self, agent, src_path, dst_path, follow, overwrite, verbose):
        try:
            job = jobs.UploadDirJob(agent.obj, src_path, dst_path,
                                    follow, False, overwrite, verbose)
        except ex.JobException as e:
            raise ex.MaticException(str(e))
        return (job, agent.new_job(job))

    # From host to simulated target, i.e. agent download-dir
    def _matic_quit_agent(self, agent, errno, reason):
        if not reason:
            reason = "automatic termination upon completion"
        try:
            job = jobs.AgentQuitJob(agent.obj, errno, reason)
        except ex.JobException as e:
            simics.SIM_log_error(self.obj, 0, "Agent %s quit: %s"
                                 % (str(agent), str(e)))
            return
        jid = agent.new_job(job)
        agent.wait_for_job(jid)

    def _my_agent_transfer(self):
        error_code = None
        error_msg = None
        fm = self.info["from"]
        to = self.info.get("to", None)
        directory = bool(int(self.info.get("directory", "0")))
        download = not bool(int(self.info["download"]))  # Inverted from host
        vb = bool(int(self.info.get("verbose", 0)))
        ow = bool(int(self.info.get("overwrite", 0)))
        fw = bool(int(self.info.get("follow", 0)))
        fl = bool(int(self.info.get("flush", 0)))
        xe = bool(int(self.info.get("executable", 0)))
        stay = bool(int(self.info.get("stay", 0)))
        try:
            agent = self._get_agent_handle().object_data
            if directory:
                if download:
                    (job, jid) = self._matic_download_dir(agent, fm, to, fw, ow, vb)
                else:
                    (job, jid) = self._matic_upload_dir(agent, fm, to, fw, ow, vb)
            else:
                if download:
                    (job, jid) = self._matic_download(agent, fm, to, ow)
                else:
                    (job, jid) = self._matic_upload(agent, fm, to, ow, fl, xe)
            simics.SIM_log_info(4, self.obj, 0, "Adding job %s (%d) to agent %s"
                                % (job, jid, agent))
            agent.wait_for_job(jid)
            if job.errno:
                error_code = job.errno
                error_msg = job.output
        except ex.MaticException as e:
            simics.SIM_log_info(4, self.obj, 0,
                                "Target initiated transfer failed: %s"
                                % str(e))
            error_code = 71  # EPROTO (71): Protocol error
            error_msg = str(e)
        if not stay:
            self._matic_quit_agent(agent, error_code, error_msg)

    def run_embedded_command(self):
        if "download" in self.info:
            def run_transfer(args):
                (chn) = args
                chn.start_hap_timeout(self.timestamp[0])
                cli.sb_create(lambda: chn._my_agent_transfer(),
                          "target-initiated transfer")
            simics.SIM_run_alone(run_transfer, (self))
