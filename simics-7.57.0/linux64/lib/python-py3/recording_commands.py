# © 2010 Intel Corporation
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
import conf
import cli
import simics
import table
from conf_commands import (
    wrap_write_configuration,
    )
from simics_common import pre_conf_object

def rec_filename(prefix, obj):
    return prefix + "." + obj.name

def recording_active():
    return any(x.recording
               for x in simics.SIM_object_iterator_for_class('recorder'))

def playback_active():
    return any(x.playback for x in simics.SIM_object_iterator_for_class('recorder'))

def get_all_objs(class_name, cli_error = False):
    recs = list(simics.SIM_object_iterator_for_class(class_name))
    if not recs:
        raise cli.CliError("No %ss in the system" % class_name)
    return recs

def get_all_recorders():
    return get_all_objs('recorder', cli_error = True)

def get_session():
    try:
        return simics.SIM_get_object("session_info")
    except simics.SimExc_General:
        return simics.SIM_create_object("session", "session_info")

def cleanup_recfile(recfile):
    try:
        os.remove(recfile)
    except OSError:
        pass

def start_recording(recfile):
    if recording_active():
        raise cli.CliError("Already recording input")
    if os.path.exists(recfile):
        raise cli.CliError("File %s already exists" % recfile)
    recs = get_all_recorders()
    # Create a global file with the names of all individual recorder files in.
    # 'start-playback' is easier to use when a single file is to be selected.
    for rec in recs:
        f = rec_filename(recfile, rec)
        if os.path.exists(f):
            raise cli.CliError("File %s already exists" % f)
    try:
        with open(recfile, "w") as f:
            for rec in recs:
                f.write(os.path.basename(rec_filename(recfile, rec) + '\n'))
    except Exception as ex:
        cleanup_recfile(recfile)
        raise cli.CliError("Failed writing to file '%s': %s" % (recfile, ex))
    # Enable all recorders in the system
    for rec in recs:
        try:
            rec.out_file = rec_filename(recfile, rec)
            rec.recording = True
        except Exception as ex:
            for r in recs:
                r.recording = False
            cleanup_recfile(recfile)
            raise cli.CliError("Error starting recording: %s" % ex)
    # flush comments if Simics exits before stop-recording
    simics.SIM_hap_add_callback("Core_At_Exit", save_session_comments, False)
    return "Recording of asynchronous input started"

def start_recording_cmd(recfile):
    return cli.command_return(start_recording(recfile))

cli.new_command("start-recording", start_recording_cmd,
                [cli.arg(cli.filename_t(exist = False), "file")],
                type  = ["Recording"],
                short = "record all asynchronous input to file",
                see_also = ("stop-recording", "start-playback"),
                doc = """
Start recording all asynchronous input to the system to the file
<arg>file</arg>. Asynchronous input includes keyboard and mouse events and
network traffic from the real host. All recorder objects in the
system, typically one for each simulation cell, will be enabled and will write
their recording data to individual files associated with the main recording
file. Recording is stopped using the <cmd>stop-recording</cmd> command.
""")

checkpoint_path = None

def save_session_comments(obj, exception_on_error):
    simics.SIM_hap_delete_callback("Core_At_Exit", save_session_comments, False)
    global checkpoint_path
    if not checkpoint_path:
        return
    # create a dummy sim object to save in the comments file
    sim = pre_conf_object(
        "sim", "sim",
        session_comments = list(conf.sim.session_comments))
    try:
        simics.CORE_write_pre_conf_objects(
            os.path.join(checkpoint_path, "session_comments"), [sim],
            simics.Sim_Save_No_Gzip_Config)
    except Exception as ex:
        filename = os.path.join(checkpoint_path, "session_comments")
        msg = "Failed saving session comment file '%s': %s" % (filename, ex)
        if exception_on_error:
            raise cli.CliError(msg)
        else:
            print("Error: " + msg)

def stop_recording():
    if not recording_active():
        raise cli.CliError("Not recording any input")
    for rec in get_all_recorders():
        rec.recording = False
    # Now stop the session recording if active
    global checkpoint_path
    if checkpoint_path:
        try:
            save_session_comments(None, True)
        finally:
            session_name = os.path.basename(checkpoint_path)
            checkpoint_path = None
        return "Recording of session %s stopped" % session_name
    else:
        return "Recording of asynchronous input stopped"

def stop_recording_cmd():
    return cli.command_return(stop_recording())

cli.new_command("stop-recording", stop_recording_cmd,
                [],
                type  = ["Recording"],
                short = "stop recording of session or asynchronous input",
                see_also = ("start-playback", "start-recording"),
                doc = """
Stop the recording of a session or of asynchronous input only, previously
started with the <cmd>record-session</cmd> or <cmd>start-recording</cmd>
commands.
""")

def start_playback_cmd(recfile, no_stop=False):
    if playback_active():
        raise cli.CliError("Already replaying input")
    recs = get_all_recorders()
    # List of all recorder files in the saved recording
    with open(recfile, "r") as f:
        old_rec_files = {l.strip() for l in f.readlines()}
    # Recorder files according to current setup
    new_rec_files  = {rec_filename(os.path.basename(recfile), rec)
                          for rec in recs}
    # The set of recorder files to actually use
    rec_files = old_rec_files.intersection(new_rec_files)
    # Check that recording matches this configuration
    if not rec_files:
        raise cli.CliError("The recorders listed in '%s' do not exist in the"
                           " current configuration" % recfile)
    elif old_rec_files != new_rec_files:
        # Allow playback even if user has extended or removed parts of setup
        print(("Warning: The set of recorders in '%s' does not exactly match"
               " the current configuration." % recfile))
    # Add the path to all recording files
    rec_files = {os.path.join(os.path.dirname(recfile), f)
                     for f in rec_files}
    for f in rec_files:
        if not os.path.exists(f):
            raise cli.CliError("File %s not found" % f)
    started = set()
    for rec in recs:
        if rec_filename(recfile, rec) not in rec_files:
            # Skip recorders not part of the saved recording
            continue
        try:
            if no_stop:
                rec.stop_at_end_of_recording = False
            rec.in_file = rec_filename(recfile, rec)
            rec.playback = True
            started.add(rec_filename(recfile, rec))
        except Exception as ex:
            for r in recs:
                r.playback = False
            raise cli.CliError("Error starting playback: %s" % ex)
    # make sure all recorders are started as expected
    assert started == rec_files
    return cli.command_return("Playback of recorded async input started")

cli.new_command("start-playback", start_playback_cmd,
                [cli.arg(cli.filename_t(exist = True), "file"),
                 cli.arg(cli.flag_t, "-no-stop")],
                type  = ["Recording"],
                short = "play back previously recorded input from a file",
                see_also = ("stop-playback", "start-recording"),
                doc = """
Start playback of recorded asynchronous input from file <arg>file</arg>,
created by the <cmd>start-recording</cmd> command. The simulated system
configuration must match the one that the recording was created for. The
playback can be stopped prematurely by issuing <cmd>stop-playback</cmd>.
The simulation is automatically stopped when the replay reaches the end
of a recording, but this can be avoided with the <tt>-no-stop</tt>
flag.""")

def stop_playback_cmd():
    if not playback_active():
        raise cli.CliError("Not replaying any input")
    for rec in get_all_recorders():
        rec.playback = False
    return cli.command_return("Playback of asynchronous input stopped")

cli.new_command("stop-playback", stop_playback_cmd,
                [],
                type  = ["Recording"],
                short = "stop playback of asynchronous input from a file",
                see_also = ("start-playback", "start-recording"),
                doc = """
Stop replaying asynchronous input, previously started with the
<cmd>start-playback</cmd> command.""")

def record_session(filename, u, standalone, comment):
    if recording_active():
        raise cli.CliError("Already recording input")
    return basic_record_session(filename, u, standalone, comment)

def record_session_cmd(filename, uflag, standalone, comment):
    return cli.command_return(record_session(filename,
                                             uflag,
                                             standalone,
                                             comment))

cli.new_command("record-session", record_session_cmd,
                [cli.arg(cli.filename_t(checkpoint=True), "file"),
                 cli.arg(cli.flag_t, "-u"),
                 cli.arg(cli.flag_t, "-independent-checkpoint"),
                 cli.arg(cli.str_t, "comment", "?", None)],
                type  = ["Configuration"],
                short = "save configuration including a recording",
                see_also = ["read-configuration", "write-configuration",
                            "start-recording", "stop-recording"],
                doc = """
Save the current machine configuration to <arg>file</arg> together with a
recording of the upcoming simulation session. The session includes all
asynchronous input and any session comments. The recording continues until the
<cmd>stop-recording</cmd> command is issued. The saved session can
be loaded using the <cmd>read-configuration</cmd> command.

Use the <tt>-u</tt> flag to store uncompressed files when saving image
data in craff format.

Use the <tt>-independent-checkpoint</tt> flag for saving the complete image
data independent of earlier checkpoints, instead of just the modified data
(which is the default).

To add a description to the checkpoint, use the <arg>comment</arg>
argument. The comment is saved in the <file>info</file> file in the checkpoint
bundle.
""")

def basic_record_session(filename, u, standalone, comment):
    wrap_write_configuration(filename, u, False, standalone, comment)
    # Remember the path where the session file will be saved later
    global checkpoint_path
    checkpoint_path = os.path.abspath(filename)
    return start_recording(os.path.join(filename, "recording"))

def add_comment_cmd(comment):
    processors = simics.SIM_get_all_processors()
    if not processors:
        raise cli.CliError("This command requires a processor to be defined.")
    # should store time on all cpus, but for now, time on the cpu that is
    # furthest will cause least confusion when shown along bookmarks, etc
    clock = max(processors, key = lambda x: simics.SIM_time(x))
    steps = [[p, simics.SIM_step_count(p)] for p in processors]
    conf.sim.session_comments_obj.append([simics.SIM_time(clock),
                                          clock, steps, comment])

cli.new_command("add-session-comment", add_comment_cmd,
                [cli.arg(cli.str_t, "comment")],
                type  = ["Recording"],
                short = "add a time-stamped user comment",
                see_also = ["list-session-comments", "record-session",
                            "start-recording", "stop-recording"],
                doc = """
Add a <arg>comment</arg> to the session at the current time. If a session is
being recorded, for example using the <cmd>record-session</cmd> command, the
comment will be saved with the session checkpoint for replay at a later time.
""")

def list_comments_cmd():
    if not conf.sim.session_comments_obj:
        return cli.command_return("No user comments added", [])
    # read out the list of comments from the attribute, sort by time-stamp
    comments = sorted(list(conf.sim.session_comments_obj), key=lambda x: x[0])
    props = [(table.Table_Key_Columns,
              [[(table.Column_Key_Name, "Time"),
                (table.Column_Key_Float_Decimals, 6)],
               [(table.Column_Key_Name, "Comment")]])]
    data = [[ts, comment] for (ts, _, _, comment) in comments]
    tbl = table.Table(props, data)
    ret_str = tbl.to_string(rows_printed=0, no_row_column=True)
    return cli.command_verbose_return(ret_str, data)

cli.new_command("list-session-comments", list_comments_cmd,
                [],
                type  = ["Recording"],
                short = "list all time-stamped session comments",
                see_also = ["add-session-comment", "record-session",
                            "start-recording", "stop-recording"],
                doc = """
List all session comments and their corresponding time-stamp. When used in an
expression, the command returns a list of [&lt;time stamp>, &lt;comment>]
pairs.
""")
