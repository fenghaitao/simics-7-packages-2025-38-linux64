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
import re
import simics
import cli
from . import jobs
from . import channel as chn
from . import handle as hndl
from . import manager as mgr
from . import exceptions as ex


class AgentManagerEnable:
    """Agent Manager helper class for enable/disable commands"""

    def __init__(self, matic_obj, force=False):
        self.force = force
        self.obj = matic_obj

    def what(self):
        return "agent_manager"

    def is_enabled(self):
        return self.obj.object_data.enabled

    def set_enabled(self, enable):
        if enable:
            self.obj.object_data.enable()
        else:
            self.obj.object_data.disable()

    def done(self):
        pass


def init_agent_manager(obj, data):
    amobj = mgr.AgentManager(obj)
    return amobj

def finalize_agent_manager(obj):
    obj.object_data.enable()

def matic_info(obj):
    return obj.object_data.get_info()

def matic_status(obj):
    return obj.object_data.get_status()

def init_agent_handle(obj, data):
    simics.VT_set_object_checkpointable(obj, False)
    ahobj = hndl.AgentHandle(obj)
    return ahobj

def free_agent_handle(obj):
    del obj
    return 0

def agent_handle_info(obj):
    return obj.object_data.get_info()

def agent_handle_status(obj):
    return obj.object_data.get_status()

def register_classes():
    agent_manager_data = simics.class_data_t(
        init_object = init_agent_manager,
        finalize_instance = finalize_agent_manager,
        class_desc = "the agent_manager",
        description = """\
    The <class>agent_manager</class> class is used by <i>Matic</i> to support
    communication with Simics Agents, which run on target systems. The manager
    creates and controls Agent Handles for those agents. There may only exist
    <i>one</i> agent manager in the simulation.

    Matic requires the simulation to run, allowing Simics Agents on the
    target systems to run and respond. However, if the simulation is not
    running, any commands will be queued on the <class>agent_handle</class>
    objects and run eventually.

    The <cmd><nref
    label="__rm_command_start-agent-manager">start-agent-manager</nref></cmd>
    command will load the required module and create and start an agent
    manager.

    <b>See also:</b> <cite>Simics User's Guide</cite> as well as the
    <class><nref label="__rm_class_agent_handle">agent_handle</nref></class>
    class.""")

    amc = simics.SIM_register_class("agent_manager", agent_manager_data)
    cli.new_info_command("agent_manager", matic_info)
    cli.new_status_command("agent_manager", matic_status)

    agent_manager_attributes(amc)
    agent_manager_commands()

    agent_handle_data = simics.class_data_t(
        init_object = init_agent_handle,
        delete_instance = free_agent_handle,
        class_desc = "the agent_handle",
        description = """\
    The <class>agent_handle</class> class is used by <i>Matic</i> to resemble
    connections with Simics Agents, which are running on target systems. A
    handle provides the user with commands so that she can interact with the
    agent of the handle.

    An agent handle can only be connected to one Simics Agent but an agent may
    be connected to several handles.

    Matic requires the simulation to run, allowing Simics Agents on the
    target systems to run and respond. However, if the simulation is not
    running, any commands will be queued on the agent handle until they are
    run eventually.

    The
    <cmd><nref label="__rm_command__lt_agent_manager_gt_.connect-to-agent">
    &lt;agent_manager&gt;.connect-to-agent</nref></cmd> command creates an
    agent handle that will be associated with an agent as soon as possible.
    Agent handles should be deleted when they no longer are needed.

    The <attr>stale_timeout</attr> attribute controls the timeout period after
    the end of an agent poll interval until the Simics Agent is declared dead
    unless it has made contact. The setting applies individually to each Simics
    Agent, but control is shared among its handles. Once dead, all its handles
    will become stale and all their commands will be canceled. New commands
    cannot be given to a stale handle.

    The handle also provides some other attributes: <attr>connected_to</attr>,
    <attr>magic</attr>, <attr>stale</attr>, <attr>state</attr> and
    <attr>windows</attr>. See the help text for each attribute for more
    information.

    <b>See also:</b> <cite>Simics User's Guide</cite> as well as the
    <class><nref label="__rm_class_agent_manager">agent_manager</nref></class>
    class.""")

    ahc = simics.SIM_register_class("agent_handle", agent_handle_data)
    cli.new_info_command("agent_handle", agent_handle_info)
    cli.new_status_command("agent_handle", agent_handle_status)

    agent_handle_attributes(ahc)
    agent_handle_commands()

def agent_manager_attributes(cls):

    def infos_getter(arg, obj, idx):
        return obj.object_data.get_agent_infos()
    def infos_setter(arg, obj, val, idx):
        return obj.object_data.set_agent_infos(val)

    simics.SIM_register_typed_attribute(cls, "infos",
                                        infos_getter, None,
                                        infos_setter, None,
                                        simics.Sim_Attr_Optional, '[s*]', None,
                                        "Information about each Simics Agent.")

    def pipe_getter(arg, obj, idx):
        return obj.object_data.get_pipe()

    simics.SIM_register_typed_attribute(cls, "pipe",
                                        pipe_getter, None, None, None,
                                        simics.Sim_Attr_Pseudo, 'o|n', None,
                                        "The connected magic pipe object.")

def agent_manager_commands():

    def connect_to_agent_cmd(agent_manager, name, identifier):
        agman = agent_manager.object_data
        if not agman.enabled:
            raise cli.CliError("'%s' is disabled." % agent_manager.name)
        if not name:
            name = agman.new_handle_name()
        try:
            hobj = simics.SIM_create_object("agent_handle", name, [])
        except simics.SimExc_General as e:
            raise cli.CliError(str(e))
        except ex.ManagerException as e:
            raise cli.CliError("Unable to create handle: %s" % str(e))
        hndl = hobj.object_data
        hndl.connect_to(name, identifier)
        msg = hndl.print_connection()
        return cli.command_return(value=hobj, message=msg)

    cli.new_command("connect-to-agent", connect_to_agent_cmd,
                    args = [cli.arg(cli.str_t, "name", "?", None),
                            cli.arg(cli.str_t, "identifier", "?", None)],
                    cls = "agent_manager",
                    type = ["Matic"],
                    see_also = ["<agent_manager>.list-agents"],
                    short = "create a handle for a Simics Agent",
                    doc = """
    Create an <class>agent_handle</class> object and connect it to a Simics
    Agent that is running on a target machine. If an agent is not found or the
    simulation is not running, the agent_handle object is immediately returned
    and ready to accept commands; the connection is finished eventually.

    The <arg>name</arg> must be unique. If not given it defaults to
    'matic<i>N</i>', where '<i>N</i>' is an integer.

    The <arg>identifier</arg> is a string that is used to filter for an
    agent. The first agent that matches the argument will be selected. If no
    agent is found, an agent_handle object is immediately returned and the
    command will finish when a match is found, if ever. Without argument,
    the first found agent is selected.

    An identifier may take any of three forms and it is matched in this order:

    The identifier may be an <b>agent-id</b> on the form 'agent-name<i>N</i>',
    where '<i>N</i>' is an integer. An underscore is inserted before <i>N</i> if
    the agent name ends with a digit. The 'agent-id' is generated by the agent
    manager when a new agent is found. This is the only unique identifier.

    The identifier may be the <b>agent-name</b> with which the Simics Agent
    announces itself. By default that is the host name of the target system,
    but it can also be given as a command line argument when starting the
    Simics Agent on the target system.

    The identifier may be any part of a <b>hierarchical name</b> that
    identifies where in the configuration the Simics Agent is running. For
    example, 'cpu0' may work, or maybe the longer 'viper0.mb.cpu0' is
    needed. Avoid being too specific about the processor core, since the
    operating system of the target system may schedule the agent
    differently.

    <b>See also:</b> <class><nref label="__rm_class_agent_manager">
    agent_manager</nref></class> and <class><nref
    label="__rm_class_agent_handle">agent_handle</nref></class>.""")



    cli.new_command("disable", cli.disable_cmd(AgentManagerEnable),
                    args = [cli.arg(cli.flag_t, "-force")],
                    cls = "agent_manager",
                    type = ["Matic"],
                    see_also = ["<agent_manager>.enable"],
                    short = "disable the manager and delete handles",
                    doc = """
    Disable the <class>agent_manager</class>, stop communicating with Simics
    Agents, and delete all <class>agent_handle</class> objects. Queued
    commands are deleted together with the handles. If there are any ongoing
    jobs, this command will fail.

    This command does not notify any Simics Agents running on target systems
    but those will soon switch to idle state.

    The <tt>-force</tt> flag will immediately disable the agent manager. Any
    ongoing jobs are left behind to finish eventually. Remember that agents
    may retain any amount of output.""")

    cli.new_command("enable", cli.enable_cmd(AgentManagerEnable),
                    cls = "agent_manager",
                    type = ["Matic"],
                    see_also = ["<agent_manager>.disable",
                                "<agent_manager>.connect-to-agent"],
                    short = "enable the agent_manager",
                    doc = """
    Enable the <class>agent_manager</class>, making it listening for Simics
    Agents which are running on target systems. This command will not recreate
    any earlier <class>agent_handle</class> objects.""")



    def list_agents_cmd(agent_manager, pattern, info, verbose=False):
        if not agent_manager.object_data.enabled:
            raise cli.CliError("The '%s' is disabled." % agent_manager.name)
        if info != "name" and not pattern:
            raise cli.CliError("Error: 'info' without 'pattern'.")
        if not agent_manager.object_data.chan:
            return cli.command_return(value = [])

        msg = ""
        chns = agent_manager.object_data.get_agent_list()
        if pattern:
            found = set()
            for nfo in info.split(','):
                if nfo == "id":
                    found |= set([x for x in chns
                                  if re.search(pattern, x.id)])
                else:
                    try:
                        found |= set([x for x in chns
                                  if re.search(pattern, x.info[nfo])])
                    except KeyError:
                        msg += ("WARNING: One or more Simics Agents lack"
                                " '%s' information" % nfo)
            chns = list(found)
        chns.sort(key=lambda x: x.id)
        if verbose:
            msg = '\n'.join('%s\t%s' % (c.id, c.long_description())
                            for c in chns)
        else:
            msg = '\n'.join('%s\t%s' % (c.id, c.short_description())
                            for c in chns)
        return cli.command_verbose_return(value=[x.id for x in chns],
                                          message=msg)

    cli.new_command("list-agents", list_agents_cmd,
                    args = [cli.arg(cli.str_t, "pattern", "?", None),
                            cli.arg(cli.str_t, "info", "?", "name"),
                            cli.arg(cli.flag_t, "-verbose", "?", False)],
                    synopsis = [
                        cli.Markup.Keyword("&lt;agent_manager>.list-agents"),
                        " [", cli.Markup.Arg('"pattern"'),
                        " [", cli.Markup.Arg('"info"'),
                        "]] [", cli.Markup.Arg("-verbose"), "]"],
                    cls = "agent_manager",
                    type = ["Matic"],
                    see_also = ["<agent_manager>.connect-to-agent"],
                    short = "list all known Simics Agents",
                    doc = """
    List all known Simics Agents that are alive and can be immediately connected
    to.

    The <arg>pattern</arg> argument (a regular expression) will filter the
    list based on the <arg>info</arg> argument, which defaults to "name". Use
    the <arg>info</arg> argument to specify another info type, or a string of
    several comma-separated types. Info types depend on the target systems, as
    well as the Simics Agents, but will at least include: agent, capabilities,
    hostname, machine, name, release, system.

    A Simics Agent is declared dead and removed from the list, if it fails to
    make contact within a timeout period after the end of the agent poll
    interval. This timeout is defined per Simics Agent and can be controlled
    via the <attr>stale_timeout</attr> attribute on any of the connected agent
    handles. When an agent is declared dead, its handles will become stale and
    their commands will be canceled. New commands cannot be given to a stale
    handle.

    With the <tt>-verbose</tt> flag, some additional information is
    included.""")



def agent_handle_attributes(cls):

    def connection_getter(arg, obj, idx):
        return obj.object_data.get_connection()

    def magic_getter(arg, obj, idx):
        return obj.object_data.get_magic()

    def pwd_getter(arg, obj, idx):
        return obj.object_data.get_pwd()
    def pwd_setter(arg, obj, val, idx):
        return obj.object_data.set_pwd(val)

    def stale_getter(arg, obj, idx):
        return obj.object_data.is_stale()

    def stale_timeout_getter(arg, obj, idx):
        return obj.object_data.get_stale_timeout()
    def stale_timeout_setter(arg, obj, val, idx):
        return obj.object_data.set_stale_timeout(val)

    def state_getter(arg, obj, idx):
        return obj.object_data.get_state()

    def windows_getter(arg, obj, idx):
        return obj.object_data.is_windows()
    def windows_setter(arg, obj, val, idx):
        return obj.object_data.set_windows(val)

    simics.SIM_register_typed_attribute(cls, "connected_to",
                                        connection_getter, None, None, None,
                                        simics.Sim_Attr_Pseudo, 's', None,
                                        "The agent-id of the connected agent.")

    simics.SIM_register_typed_attribute(cls, "magic",
                                        magic_getter, None, None, None,
                                        simics.Sim_Attr_Pseudo, 'i|n', None,
                                        "The Simics Agent magic id number.")

    simics.SIM_register_typed_attribute(cls, "path",
                                        pwd_getter, None,
                                        pwd_setter, None,
                                        simics.Sim_Attr_Pseudo, 's', None,
                                        "The private working directory on the"
                                        " target system.")

    simics.SIM_register_typed_attribute(cls, "stale",
                                        stale_getter, None, None, None,
                                        simics.Sim_Attr_Pseudo, 'b', None,
                                        "True, if the handle has become stale.")

    simics.SIM_register_typed_attribute(cls, "stale_timeout",
                                        stale_timeout_getter, None,
                                        stale_timeout_setter, None,
                                        simics.Sim_Attr_Pseudo, 'i|f', None,
                                        "Stale handle timeout, in seconds,"
                                        " started at the end of the poll"
                                        " interval. Requires an active"
                                        " connection.")

    simics.SIM_register_typed_attribute(cls, "state",
                                        state_getter, None, None, None,
                                        simics.Sim_Attr_Pseudo, 's', None,
                                        "The current state of the handle.")

    simics.SIM_register_typed_attribute(cls, "windows",
                                        windows_getter, None,
                                        windows_setter, None,
                                        simics.Sim_Attr_Pseudo, 'b|n', None,
                                        "True, if running on a Windows system.")

def get_agent_handle(jqueue_obj, allow_stale):
    hndl = jqueue_obj.object_data
    if allow_stale or not hndl.is_stale():
        return hndl
    raise cli.CliError("Aborted: Handle is stale")

def agent_handle_commands():

    def agent_cmd_ret(hndl, jid, job):
        return cli.command_return(
            value=jid,
            message="%s:job %d (%s)" % (hndl, jid, job))

    def poll_interval_cmd(jqueue_obj, interval):
        hndl = get_agent_handle(jqueue_obj, allow_stale=False)
        if not interval:
            poll_ms = hndl.get_poll_interval_ms()
            if poll_ms is None:
                raise cli.CliError("handle is not connected yet")
            return cli.command_return(value=poll_ms,
                message="%s:agent-poll-interval is %d ms" %(hndl, poll_ms))
        try:
            job = jobs.PollIntervalJob(jqueue_obj, interval)
            jid = hndl.new_job(job)
        except ex.JobException as e:
            raise cli.CliError(str(e))
        return agent_cmd_ret(hndl, jid, job)

    cli.new_command("agent-poll-interval", poll_interval_cmd,
                    args = [cli.arg(cli.range_t(10, 1000*60*60,
                                        "milliseconds (10 ms to 1 hour)"),
                                "ms", "?", None)],
                    cls = "agent_handle",
                    type = ["Matic"],
                    short = "set the agent's polling interval",
                    doc = """
    Set the polling interval for this handle's Simics Agent. When an agent is
    sleeping in idle mode, it will wake up periodically and poll for new
    commands. The polling interval has no effect on a working agent with
    pending commands.

    Without the <arg>ms</arg> argument, the command just prints and returns
    the current poll-interval time, in milliseconds.

    With the <arg>ms</arg> argument, specify an interval in milliseconds
    between each polling attempt. The interval can be set from 10 ms to 1
    hour.

    Remember, the polling interval is a trade-off between the responsiveness
    of a sleeping agent, and the performance taxing on a target system with a
    "restless" agent. Remember also, the exact interval will depend
    on how the target system schedules user-space processes.

    This command can be posted on <i>any</i> <class>agent_handle</class>
    object that is associated with the wanted Simics Agent.""")



    def quit_agent_cmd(jqueue_obj):
        hndl = get_agent_handle(jqueue_obj, allow_stale=False)
        try:
            job = jobs.AgentQuitJob(jqueue_obj)
            jid = hndl.new_job(job)
        except ex.JobException as e:
            raise cli.CliError(str(e))
        # handles cannot be deleted until the job has finished successfully
        return agent_cmd_ret(hndl, jid, job)

    cli.new_command("agent-quit", quit_agent_cmd,
                    args = [],
                    cls = "agent_handle",
                    type = ["Matic"],
                    see_also = ["<agent_handle>.delete-handle"],
                    short = "quit the agent for this handle",
                    doc = """
    Gracefully terminate the Simics Agent that is associated with this
    handle. Any other <class>agent_handle</class> objects for that agent will
    become stale and unusable, with any pending or queued commands
    canceled.""")


    def restart_agent_cmd(jqueue_obj):
        hndl = get_agent_handle(jqueue_obj, allow_stale=False)
        try:
            job = jobs.AgentRestartJob(jqueue_obj)
            jid = hndl.new_job(job)
        except ex.JobException as e:
            raise cli.CliError(str(e))
        return agent_cmd_ret(hndl, jid, job)

    cli.new_command("agent-restart", restart_agent_cmd,
                    args = [],
                    cls = "agent_handle",
                    type = ["Matic"],
                    short = "restart the Simics target agent",
                    doc = """
    Restart the Simics Agent for this <class>agent_handle</class> object,
    using the same command line arguments it was initially started with. This
    command affects any other handles for the same agent running on the target
    machine. Any <i>active</i> jobs will be lost, no matter which handles they
    were posted at.

    Once the restarted agent has announced itself, the agent manager will
    reconnect all affected agent handles. Then, the manager will resume
    scheduling jobs from those handles.""")


    def hndl_cd_cmd(jqueue_obj, path):
        hndl = get_agent_handle(jqueue_obj, allow_stale=False)
        msg = hndl.set_pwd(path)
        return cli.command_return(value=msg, message=msg)

    cli.new_command("change-directory", hndl_cd_cmd,
                    alias = 'cd',
                    args = [cli.arg(cli.str_t, "target-path", "?", "/")],
                    cls = "agent_handle",
                    type = ["Matic"],
                    see_also = ["<agent_handle>.print-working-directory"],
                    short = "change this handle's working directory",
                    doc = """
    Change the current working directory for this <class>agent_handle</class>
    object.

    This command immediately takes effect since it only sets the path property
    of <i>this</i> agent handle. Hence, the Simics Agent for this handle is
    not notified, and no other handles for the same agent are affected. Any
    following commands posted on a handle will run relative to its working
    directory, unless they specify an absolute path.

    The <arg>target-path</arg> argument is an <i>absolute</i> path, or a path
    <i>relative</i> to this handle's current working directory. Without
    argument, on Linux the directory is changed to "/", and on other systems
    to its equivalent.

    The target-path must exist on the target system but no effort is made to
    validate the path. Hence, an invalid path may cause following commands to
    fail.""")


    def hndl_delete_obj_cmd(jqueue_obj):
        hndl = get_agent_handle(jqueue_obj, allow_stale=True)
        hndl.disconnect()
        msg = "%s deleted" % hndl.name
        simics.SIM_delete_object(jqueue_obj)
        return cli.command_return(value=False, message=msg)

    cli.new_command("delete-handle", hndl_delete_obj_cmd,
                    args = [],
                    cls = "agent_handle",
                    type = ["Matic"],
                    see_also = ["<agent_handle>.agent-quit"],
                    short = "delete this agent handle",
                    doc = """
    Delete this <class>agent_handle</class> object. This command will also
    delete any pending or queued commands on this handle. Any ongoing job is left
    unfinished and any upcoming result from it is ignored.""")



    def discard_jobs_cmd(jqueue_obj, jobs_list):
        hndl = get_agent_handle(jqueue_obj, allow_stale=True)
        try:
            hndl.discard_jobs(jobs_list)
            msg = "%s jobs discarded" % ("Specified" if jobs_list else "All")
            return cli.command_return(value=True, message=msg)
        except ex.JobException as e:
            raise cli.CliError(str(e))

    cli.new_command("discard-jobs", discard_jobs_cmd,
                    args = [cli.arg(cli.int_t, "job-id", "*")],
                    cls = "agent_handle",
                    type = ["Matic"],
                    see_also = ["<agent_handle>.list-jobs"],
                    short = "discard jobs from this agent handle",
                    doc = """
    Discard all or specified commands from this <class>agent_handle</class>
    object. Any ongoing job is left behind and any upcoming result from it is
    ignored.

    A command posted on an agent handle is given an integer ID which is unique
    per agent handle. With the <arg>job-id</arg> argument, specify one or more
    IDs for the commands to be discarded.""")



    def download_cmd(jqueue_obj, overwrite, targ_src, host_dest):
        hndl = get_agent_handle(jqueue_obj, allow_stale=False)
        try:
            job = jobs.DownloadJob(jqueue_obj, targ_src, host_dest, overwrite)
            jid = hndl.new_job(job)
        except ex.JobException as e:
            raise cli.CliError(str(e))
        return agent_cmd_ret(hndl, jid, job)

    cli.new_command("download", download_cmd,
                    args = [cli.arg(cli.flag_t, "-overwrite"),
                            cli.arg(cli.str_t, "from"),
                            cli.arg(cli.filename_t(dirs=True), "to", "?", None)],
                    cls = "agent_handle",
                    type = ["Matic"],
                    see_also = ["<agent_handle>.download-dir",
                                "<agent_handle>.print-file",
                                "<agent_handle>.upload"],
                    short = "download file from system to host",
                    doc = """
    Copy a file to the host from the target system, where the Simics Agent
    connected to this <class>agent_handle</class> object is running.

    The <arg>from</arg> argument is mandatory and must refer to an existing
    readable file in the target system. The path is relative to this agent
    handle's current working directory, unless it is an absolute path.

    The optional <arg>to</arg> argument, allows the user to override the current
    working directory of Simics and provide an alternate destination path. A
    provided destination path must refer to an existing directory where the user
    has write permission. The path is taken as relative to the current working
    directory on the host, unless it is absolute.

    The <tt>-overwrite</tt> flag is required to overwrite any existing file in
    the host system. Otherwise, the command will fail if the destination file
    already exists.

    Note: The user who is running Simics must have permissions to create and
    write files in the host system. The user will be given ownership and
    access permissions of the downloaded contents.""")


    def download_dir_cmd(jqueue_obj, follow, no_hidden, overwrite, verbose,
                         targpath, hostpath):
        hndl = get_agent_handle(jqueue_obj, allow_stale=False)
        if not hndl.version_min(1.3):
            raise cli.CliError(
                "Aborted: Simics agent version 1.3 or later required")
        try:
            job = jobs.DownloadDirJob(jqueue_obj, targpath, hostpath, follow,
                                      no_hidden, overwrite, verbose)
        except ex.JobException as e:
            raise cli.CliError(str(e))
        jid = hndl.new_job(job)
        return agent_cmd_ret(hndl, jid, job)

    cli.new_command("download-dir", download_dir_cmd,
                    args = [
                        cli.arg(cli.flag_t, "-follow"),
                        cli.arg(cli.flag_t, "-no-hidden"),
                        cli.arg(cli.flag_t, "-overwrite"),
                        cli.arg(cli.flag_t, "-verbose"),
                        cli.arg(cli.str_t, "from"),
                        cli.arg(cli.filename_t(dirs=True), "to", "?", None)],
                    cls = "agent_handle",
                    type = ["Matic"],
                    see_also = ["<agent_handle>.download",
                                "<agent_handle>.upload",
                                "<agent_handle>.upload-dir"],
                    short = "download directory from target to host",
                    doc = """
    Copy a directory tree from the target system, where the Simics Agent
    connected to this <class>agent_handle</class> object is running, to the
    host. Files and directories that the user do not have permission to access
    will be ignored.

    The <arg>from</arg> argument is mandatory and must refer to an existing
    directory on the target system. The directory and all its contents will be
    downloaded to the host system.

    The optional <arg>to</arg> argument can be used to override the default
    destination, which is the current working directory on the host system. If
    provided, the given directory path is taken relative to the handle's current
    working directory, unless the path is absolute. The destination directory on
    the target system must exist and allow the user to write to it, or this
    command will fail.

    By default the command will copy soft-links "as is" and not the files that
    they point to, but this behavior can be altered with the <tt>-follow</tt>
    flag. Note that soft-links to files within the upload tree will cause the
    files to be duplicated when soft-links are followed. <b>WARNING: Beware of
    circular soft-links when the flag is used!</b> A circular soft-link will be
    traversed until the maximum target system recursion is exceeded.

    Any hidden files (beginning with a dot) in the upload tree will be treated
    just like regular files, unless the <tt>-no-hidden</tt> flag is given, in
    which case they are ignored.

    The <tt>-overwrite</tt> flag is required if the user wants existing target
    system files to be overwritten. Otherwise, without the flag, all existing
    target system files will remain untouched and the host files are skipped.

    The <tt>-verbose</tt> flag, will cause the name of uploaded files and
    directories to be printed as they have been created or fully uploaded.

    Note: The Simics Agent must have permissions to create and write files in
    the destination directory on the target system. The uploaded contents will
    be given ownership and the access permissions of the <i>user</i> who is
    running the Simics Agent.""")


    def get_captured_output_cmd(jqueue_obj, jid, overwrite, filename):
        hndl = get_agent_handle(jqueue_obj, allow_stale=True)
        if jid < 0:  # No job selected, list them all instead
            caplist = hndl.captured_list()
            val = [jid for (jid, _) in caplist]
            msg = "\n".join("Job %d: %s" % (jid, msg) for (jid, msg) in caplist)
            if msg:
                msg = "Captured output available for the following jobs:\n" + msg
                return cli.command_return(value=val, message=msg)
        else:
            (_, val) = hndl.captured_output(jid)
            if not val:
                return
            if filename:
                if val[-1] != '\n':  # Ends with a line break?
                    val += '\n'  # File is in text mode, do not use os.linesep
                fmode = 'w' if overwrite else 'a'
                with open(filename, fmode) as f:
                    f.write(val)
                return cli.command_return(value=val)
            return cli.command_return(value=val, message=val)

    cli.new_command("get-captured-output", get_captured_output_cmd,
                    args = [cli.arg(cli.int_t, "job-id", "?", -1),
                            cli.arg(cli.flag_t, "-overwrite"),
                            cli.arg(cli.filename_t(dirs=True, exist=False),
                                    "file", "?")],
                    cls = "agent_handle",
                    type = ["Matic"],
                    see_also = ["<agent_handle>.run-until-job",
                                "<agent_handle>.wait-for-job"],
                    short = "get or print the captured job output",
                    doc = """

    Once a job with captured data has completed, this command can be used to get
    its captured output. The user may choose to print it, assign it to a
    variable, or write it to a file. Note that the command has lost its copy of
    the captured data.

    The <arg>file</arg> argument will append the captured output to the
    specified file, unless the <tt>-overwrite</tt> flag is also specified.

    Without the <arg>job-id</arg> argument this command will list all remaining
    jobs with captured output.

    Apart from this command, there are two other commands that can return the
    captured output too: <cmd class="agent_handle">run-until-job</cmd> and
    <cmd class="agent_handle">wait-for-job</cmd>.""")



    def list_jobs_cmd(jqueue_obj):
        hndl = get_agent_handle(jqueue_obj, allow_stale=True)
        msg = ""
        for job in hndl.jobs:
            msg += "\t#%d\t%s, %s\n" % (job.id, job, job.get_state())
        val = [job.id for job in hndl.jobs]
        return cli.command_verbose_return(value=val, message=msg)

    cli.new_command("list-jobs", list_jobs_cmd,
                    # TODO: args = [cli.arg(cli.flag_t, "-verbose")],
                    cls = "agent_handle",
                    type = ["Matic"],
                    short = "list commands posted on this handle",
                    doc = """
    List all pending commands that are queued on this
    <class>agent_handle</class> object. The result will also include any
    ongoing, unfinished job. This command is run immediately.""")



    def hndl_ls_cmd(jqueue_obj, capture, target_dir):
        hndl = get_agent_handle(jqueue_obj, allow_stale=False)
        try:
            job = jobs.ReadDirJob(jqueue_obj, target_dir, capture)
            jid = hndl.new_job(job)
        except ex.JobException as e:
            raise cli.CliError(str(e))
        return agent_cmd_ret(hndl, jid, job)

    cli.new_command("list-files", hndl_ls_cmd,
                    alias = "ls",
                    args = [cli.arg(cli.flag_t, "-capture"),
                            cli.arg(cli.str_t, "target-dir", "?", None)],
                    cls = "agent_handle",
                    type = ["Matic"],
                    see_also = ["<agent_handle>.change-directory",
                                "<agent_handle>.print-working-directory"],
                    short = "list target directory contents",
                    doc = """
    List the contents of a directory on the target system that is associated
    with this <class>agent_handle</class> object.

    Optionally the <tt>-capture</tt> flag can be used to hold the output for
    later, instead of immediately printing it. The captured output is then
    accessed from the <cmd class="agent_handle">get-captured-output</cmd>
    command. Alternatively either
    <cmd class="agent_handle">run-until-job</cmd> or
    <cmd class="agent_handle">wait-for-job</cmd>, with the <tt>-capture</tt>
    flag, can be used.

    The <arg>target-dir</arg> argument may be a path relative to the current
    working directory of this agent handle, or an absolute path. Without
    argument, the current working directory of this agent handle will be
    used. If the directory does not exist on the target system, this command
    will fail.""")



    def print_file_cmd(jqueue_obj, capture, force, file_path):
        hndl = get_agent_handle(jqueue_obj, allow_stale=False)
        try:
            job = jobs.PrintFileJob(jqueue_obj, file_path, force, capture)
            jid = hndl.new_job(job)
        except ex.JobException as e:
            raise cli.CliError(str(e))
        return agent_cmd_ret(hndl, jid, job)

    cli.new_command("print-file", print_file_cmd,
                    args = [cli.arg(cli.flag_t, "-capture"),
                            cli.arg(cli.flag_t, "-force"),
                            cli.arg(cli.str_t, "target-file")],
                    cls = "agent_handle",
                    type = ["Matic"],
                    see_also = ["<agent_handle>.download"],
                    short = "print file contents on Simics CLI",
                    doc = """
    Print the contents of a text file to the Simics command line (CLI).

    The file contents will only be printed if the contents is determined to be
    text. The <tt>-force</tt> flag can be used to print it anyway.

    Optionally the <tt>-capture</tt> flag can be used to hold the output for
    later, instead of immediately printing it. The captured output is then
    accessed from the <cmd class="agent_handle">get-captured-output</cmd>
    command. Alternatively either
    <cmd class="agent_handle">run-until-job</cmd> or
    <cmd class="agent_handle">wait-for-job</cmd>, with the <tt>-capture</tt>
    flag, can be used.

    The <arg>target-file</arg> must be a readable file on the target
    system. The path is relative to this agent handle's current working
    directory, unless it is an absolute path.""")



    def hndl_pwd_cmd(jqueue_obj):
        hndl = get_agent_handle(jqueue_obj, allow_stale=False)
        msg = hndl.get_pwd()
        return cli.command_return(value=msg, message=msg)

    cli.new_command("print-working-directory", hndl_pwd_cmd,
                    alias = "pwd",
                    args = [],
                    cls = "agent_handle",
                    type = ["Matic"],
                    see_also = ["<agent_handle>.change-directory",
                                "<agent_handle>.list-files"],
                    short = "print this handle's working directory",
                    doc = """
    Print name of the current working directory for this
    <class>agent_handle</class> object. The default working directory, on
    Linux it is the root directory "/", and on other systems its equivalent.

    This command immediately returns the path property of this agent
    handle. For further information, see the
    <cmd class="agent_handle">change-directory</cmd> command.""")



    def target_run_cmd(jqueue_obj, capture, cmd_line):
        hndl = get_agent_handle(jqueue_obj, allow_stale=False)
        if not hndl.capable_of("POSIX"):
            raise cli.CliError(
                "Aborted: Command not supported by the Simics agent")
        try:
            job = jobs.RunJob(jqueue_obj, cmd_line, capture)
            jid = hndl.new_job(job)
        except ex.JobException as e:
            raise cli.CliError(str(e))
        return agent_cmd_ret(hndl, jid, job)

    cli.new_command("run", target_run_cmd,
                    args = [cli.arg(cli.flag_t, "-capture"),
                            cli.arg(cli.str_t, "cmd-line")],
                    cls = "agent_handle",
                    type = ["Matic"],
                    short = "execute a command on the target system",
                    doc = """
    Execute a command with command line arguments on the target system that is
    associated with this <class>agent_handle</class> object. The specified
    string will be executed just as if it was entered in a terminal console on
    the target system.

    Optionally the <tt>-capture</tt> flag can be used to hold the output for
    later, instead of immediately printing it. The captured output is then
    accessed from the <cmd class="agent_handle">get-captured-output</cmd>
    command. Alternatively either
    <cmd class="agent_handle">run-until-job</cmd> or
    <cmd class="agent_handle">wait-for-job</cmd>, with the <tt>-capture</tt>
    flag, can be used.

    The <arg>cmd-line</arg> must be one <i>quoted</i> argument string, which
    will be sent <i>as is</i> to the Simics Agent which will run the command.

    The format of the command line, as well as available features, depends on
    the target shell that will be executing the command.""")



    def run_until_job_cmd(jqueue_obj, capture, job_id):
        hndl = get_agent_handle(jqueue_obj, allow_stale=False)
        try:
            hndl.run_until_job(job_id)
        except ex.JobException as e:
            raise cli.CliError("Command canceled: %s" % str(e))
        if hndl.disconnected:
            hndl.disconnect()
        if capture:
            (_, msg) = hndl.captured_output(job_id)
            if msg:
                return cli.command_return(value=msg, message=msg)

    cli.new_command("run-until-job", run_until_job_cmd,
                    args = [cli.arg(cli.flag_t, "-capture"),
                            cli.arg(cli.int_t, "job-id", "?", -1)],
                    cls = "agent_handle",
                    type = ["Matic"],
                    see_also = ["<agent_handle>.wait-for-job"],
                    short = "run simulation until job completed",
                    doc = """
    Run the simulation until commands that are already posted on this
    <class>agent_handle</class> object have completed, and then stop the
    simulation.  If the simulation is not running, this command will start it.

    A command posted on an agent handle is given an integer ID which is unique
    per handle. With the <arg>job-id</arg> argument, specify a command that
    must have completed before the simulation is stopped. Without argument,
    this command will run the simulation until all commands have completed,
    those which were posted on this handle before this command.

    If the <tt>-capture</tt> flag was specified together with the
    <arg>job-id</arg> argument, then any captured output from that job will be
    returned from this command or printed. Note that the captured output will be
    discarded afterwards.

    Queued commands are run sequentially, meaning that the next command will
    start once the previous has completed. Thus, all commands that were posted
    before the specified argument are guaranteed to have completed
    successfully.

    If an error occurs, the execution is stopped and <i>all</i> pending
    commands that were posted on this handle are discarded, and the error is
    reported.

    <b>Notice:</b> This command is not intended for script-branches.""")


    def target_time_cmd(jqueue_obj, arg):
        hndl = get_agent_handle(jqueue_obj, allow_stale=False)
        try:
            if arg:
                (argtype, argval, argname) = arg
                if argname == "-capture":
                    job = jobs.TargetTimeJob(jqueue_obj, capture=argval)
                elif argname == "-now":
                    job = jobs.TargetTimeJob(jqueue_obj, now=argval)
                else:
                    job = jobs.TargetTimeJob(jqueue_obj, tm=argval)
            else:
                job = jobs.TargetTimeJob(jqueue_obj)
            jid = hndl.new_job(job)
        except ex.JobException as e:
            raise cli.CliError(str(e))
        return agent_cmd_ret(hndl, jid, job)

    cli.new_command("target-time", target_time_cmd,
                    args = [cli.arg((cli.flag_t, cli.flag_t, cli.str_t),
                                    ("-capture", "-now", "datetime"),
                                    "?", None)],
                    cls = "agent_handle",
                    type = ["Matic"],
                    short = "set or get target system date and time",
                    doc = """
    Set or get the date and time of the target system that is associated with
    this <class>agent_handle</class> object.

    Without argument, or with the <tt>-capture</tt> flag, this command will
    output the target date and time string according to the target's
    locale. With the optional flag the captured output string can be accessed
    from the <cmd class="agent_handle">get-captured-output</cmd> command.
    Alternatively either <cmd class="agent_handle">run-until-job</cmd> or
    <cmd class="agent_handle">wait-for-job</cmd>, with the <tt>-capture</tt>
    flag, can be used.

    With the <tt>-now</tt> flag, set the time using the host system's current
    date and time. With the <arg>datetime</arg> argument, set the date and time
    using a string that must be of the RFC2822-date format. For example
    "2014-01-31 14:15:16" or "Fri, 31 Jan 2014 14:15:16". The date string may
    contain a UTC timezone suffix.""")



    def upload_cmd(jqueue_obj, executable, flush, overwrite,
                   hostpath, to):
        hndl = get_agent_handle(jqueue_obj, allow_stale=False)
        try:
            job = jobs.UploadJob(jqueue_obj, hostpath, to, overwrite,
                                 flush, executable)
        except ex.JobException as e:
            raise cli.CliError(str(e))
        jid = hndl.new_job(job)
        return agent_cmd_ret(hndl, jid, job)

    cli.new_command("upload", upload_cmd,
                    args = [
                        cli.arg(cli.flag_t, "-executable"),
                        cli.arg(cli.flag_t, "-flush"),
                        cli.arg(cli.flag_t, "-overwrite"),
                        cli.arg(cli.filename_t(dirs=False, exist=True), "from"),
                        cli.arg(cli.str_t, "to", "?", None)],
                    cls = "agent_handle",
                    type = ["Matic"],
                    see_also = ["<agent_handle>.upload-dir",
                                "<agent_handle>.download"],
                    short = "upload file from host to target",
                    doc = """
    Copy a file from the host to the target system, where the Simics Agent
    connected to this <class>agent_handle</class> object is running.

    The <arg>from</arg> argument is mandatory and must refer to an existing
    readable file on the host system.

    The <arg>to</arg> argument is optional and without it the agent handle's
    current working directory will be used. If provided, the destination
    directory path is taken relative to the handle's current working directory,
    unless the path is absolute. The destination directory must exist on the
    target and the user must have write permission in it.

    When the <tt>-executable</tt> flag is given, the file mode bits will be
    updated so that all users who have read access to the file will also gain
    executable access to it.

    With the <tt>-flush</tt> flag, the Simics Agent will immediately commit
    each piece of data to the storage media before requesting the next piece of
    data to be transmitted. This allows readers of the destination file to read
    the data as each piece is transferred, at the expense of performance.

    The <tt>-overwrite</tt> flag is required to overwrite any existing
    destination file on the target system. Otherwise, the command will fail if
    the destination file already exists.

    Note: The Simics Agent must have permissions to create and write files in
    the destination directory on the target system. The uploaded contents will
    be given ownership and the access permissions of the <i>user</i> who is
    running the Simics Agent.""")



    def upload_dir_cmd(jqueue_obj, follow, no_hidden, overwrite, verbose,
                       hostpath, targpath):
        hndl = get_agent_handle(jqueue_obj, allow_stale=False)
        if not hndl.version_min(1.2):
            raise cli.CliError(
                "Aborted: Simics agent version 1.2 or later required")
        try:
            job = jobs.UploadDirJob(jqueue_obj, hostpath, targpath, follow,
                                    no_hidden, overwrite, verbose)
        except ex.JobException as e:
            raise cli.CliError(str(e))
        jid = hndl.new_job(job)
        return agent_cmd_ret(hndl, jid, job)

    cli.new_command("upload-dir", upload_dir_cmd,
                    args = [
                        cli.arg(cli.flag_t, "-follow"),
                        cli.arg(cli.flag_t, "-no-hidden"),
                        cli.arg(cli.flag_t, "-overwrite"),
                        cli.arg(cli.flag_t, "-verbose"),
                        cli.arg(cli.filename_t(dirs=True, exist=True), "from"),
                        cli.arg(cli.str_t, "to", "?", None)],
                    cls = "agent_handle",
                    type = ["Matic"],
                    see_also = ["<agent_handle>.upload",
                                "<agent_handle>.download",
                                "<agent_handle>.download-dir"],
                    short = "upload directory from host to target",
                    doc = """
    Copy a directory tree from the host to the target system, where the Simics
    Agent connected to this <class>agent_handle</class> object is running.
    Files and directories that the user do not have permission to will be
    ignored.

    The <arg>from</arg> argument is mandatory and must refer to an existing
    directory on the host system. The directory and all its contents will be
    uploaded to the target system.

    The optional <arg>to</arg> argument can be used to override the default
    destination, which is the handle's current working directory on the target
    system. If provided, the given directory path is taken relative to the
    handle's current working directory, unless the path is absolute. The
    destination directory on the target system must exist and allow the user to
    write to it, or this command will fail.

    By default the command will copy soft-links "as is" and not the files that
    they point to, but this behavior can be altered with the <tt>-follow</tt>
    flag. Note that soft-links to files within the upload tree will cause the
    files to be duplicated when soft-links are followed. <b>WARNING: Beware of
    circular soft-links when the flag is used!</b> A circular soft-link will be
    traversed until the maximum host system recursion is exceeded.

    Any hidden files (beginning with a dot) in the upload tree will be treated
    just like regular files, unless the <tt>-no-hidden</tt> flag is given, in
    which case they are ignored.

    The <tt>-overwrite</tt> flag is required if the user wants existing target
    system files to be overwritten. Otherwise, without the flag, all existing
    target system files will remain untouched and the host files are skipped.

    The <tt>-verbose</tt> flag, will cause the name of uploaded files and
    directories to be printed as they have been created or fully uploaded.

    Note: The Simics Agent must have permissions to create and write files in
    the destination directory on the target system. The uploaded contents will
    be given ownership and the access permissions of the <i>user</i> who is
    running the Simics Agent.""")


    def wait_for_job_cmd(jqueue_obj, capture, job_id):
        hndl = get_agent_handle(jqueue_obj, allow_stale=False)
        try:
            hndl.wait_for_job(job_id)
        except ex.JobException as e:
            raise cli.CliError("Command canceled: %s" % str(e))
        if hndl.disconnected:
            hndl.disconnect()
        if capture:
            (_, msg) = hndl.captured_output(job_id)
            if msg:
                return cli.command_return(value=msg, message=msg)

    cli.new_command("wait-for-job", wait_for_job_cmd,
                    args = [cli.arg(cli.flag_t, "-capture"),
                            cli.arg(cli.int_t, "job-id", "?", -1)],
                    cls = "agent_handle",
                    type = ["Matic"],
                    see_also = ["<agent_handle>.run-until-job"],
                    short = "suspend script branch until job completed",
                    doc = """
    Suspend execution of a script branch until commands that are already
    posted on this <class>agent_handle</class> object have completed.

    A command posted on an agent handle is given an integer ID which is unique
    per handle. With the <arg>job-id</arg> argument, specify a command that
    must have completed before the script branch may continue. Without
    argument, the script branch will be suspended until all commands have
    completed, those which were posted on this handle before this command.

    If the <tt>-capture</tt> flag was specified together with the
    <arg>job-id</arg> argument, then any captured output from that job will be
    returned from this command or printed. Note that the captured output will be
    discarded afterwards.

    Queued commands are run sequentially, meaning that the next command will
    start once the previous has completed. Thus, all commands that were posted
    before the specified argument are guaranteed to have completed
    successfully.

    If an error occurs, the execution is stopped and <i>all</i> pending
    commands that were posted on this handle are discarded, and the error
    is reported. This will also abort the script branch.

    <b>Notice:</b> This command works only in script branches. In each branch,
    create a local agent handle; that handle will not interfere with other
    handles.  Handles should be deleted before script branches finish.""")
