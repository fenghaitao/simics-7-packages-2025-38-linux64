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


from cli import (
    arg,
    filename_t,
    get_completions,
    int_t,
    new_command,
    obj_t,
    str_t,
)
from simics import *
import os

classname = "state-assertion"

try:
    temp_filename = "/tmp/state-assertion-" + os.environ['USER'] + ".gz" # nosec
except:
    temp_filename = "/tmp/state-assertion.gz"  # nosec

def get_sa_name(name):
    if not name:
        name = "sa0"
        seq = 0
        try:
            while True:
                SIM_get_object(name)
                seq = seq + 1
                name = "sa%d" % seq
        except:
            pass
    return name

compr_strings = {0: "guess", 1: "none", 3: "gz"}

def compr_expander(string):
    return get_completions(string, list(compr_strings.values()))

def get_sa_compr(compression):
    if compression == "guess":
        return 0
    elif compression == "no" or compression == "none":
        return 1
    elif compression == "gz":
        return 3
    else:
        print("Unknown compression: %s" % compression)
        return 0

def get_compr_from_filename(file):
    if (file.endswith(".gz")):
        return 3
    else:
        return 1

def state_assertion_cf_common(file, compression, name, align, postev):
    name = get_sa_name(name)

    compr_nb = get_sa_compr(compression)
    if (compr_nb == 0):
        compr_nb = get_compr_from_filename(file)
    sa = SIM_create_object(classname, name, [])
    print("Creating file '%s' with compression '%s'"%(file, compr_strings[compr_nb]))
    sa.create = [file, compr_nb, "", -1, align, postev]
    return sa

# create a new assertion object
def state_assertion_create_file(file, compression, name, align, postev):
    sa = state_assertion_cf_common(file, compression, name, align, postev)
    print(sa.name, "created. You probably want to add some objects or memory space now with 'add' and 'add-mem-lis', then run 'start' to begin the assertion process.")

new_command("state-assertion-create-file", state_assertion_create_file,
            [arg(filename_t(exist=False), "file"),
             arg(str_t, "compression", "?", "guess", expander = compr_expander),
             arg(str_t, "name", "?", ""),
             arg(int_t, "align", "?", 8),
             arg(int_t, "post_events", "?", 1)],
            type = ["Debugging"],
            short = "record a state assertion file",
            doc = """
            This command creates a state assertion file.

            - <arg>file</arg> is the name of the file to be created, default is <file>/tmp/state-assertion-$USER.gz</file><br/>
            - <arg>compression</arg> is the compression used (none, gz), default is a guess based on file name<br/>
            - <arg>name</arg> is the name of the object to be created, default is saX where X is a number.<br/>
            - <arg>align</arg> is the alignment of the structures inside the file, default is 8. It can be useful to set it so that objects saving their state are sure to get correctly aligned structures.<br/>
            - <arg>post_events</arg> tells state-assertion to post events by itself for recording and comparing, default is true.
            """)

# connect a server to drive a state-assertion
def state_assertion_connect(server, port, compression, align, postev, name):
    name = get_sa_name(name)

    compr_nb = get_sa_compr(compression)
    # no way to guess here, so we just patch
    if (compr_nb == 0):
        compr_nb = 1
    sa = SIM_create_object(classname, name, [])
    sa.create = ["", compr_nb, server, port, align, postev]
    print(name, "connected. You probably want to add some objects or memory space now with 'add' and 'add-mem-lis', then run 'start' to begin the assertion process.")
    return sa

new_command("state-assertion-connect", state_assertion_connect,
            [arg(str_t, "server", "?", "localhost"),
             arg(int_t, "port", "?", 6666),
             arg(str_t, "compression", "?", "none", expander = compr_expander),
             arg(int_t, "align", "?", 8),
             arg(int_t, "post_events", "?", 1),
             arg(str_t, "name", "?", "")],
            type = ["Debugging"],
            short = "connect to a state-assertion receiver",
            doc = """
This command connects to a state-assertion receiver so that all data gathered
during the state recording will be sent over to the receiver.

- <arg>server</arg> receiver host waiting for the connection, default is
  "localhost"<br/>
- <arg>port</arg> port number on which the receiver is waiting for a
  connection, default is 6666<br/>
- <arg>compression</arg> is the compression used (none, gz), default is
  "none"<br/>
- <arg>align</arg> is the alignment of the structures inside the file, default
  is 8. It can be useful to set it so that objects saving their state are sure
  to get correctly aligned structures.<br/>
- <arg>post_events</arg> tells state-assertion to post events by itself for
  recording and comparing, default is true.<br/>
- <arg>name</arg> is the name of the object to be created, default is saX
  where X is a number.
""")

def state_assertion_of_common(file, compression, name, postev):
    name = get_sa_name(name)

    compr_nb = get_sa_compr(compression)
    if (compr_nb == 0):
        compr_nb = get_compr_from_filename(file)
    sa = SIM_create_object(classname, name, [])
    print("Opening file '%s' with compression '%s'"%(file, compr_strings[compr_nb]))
    sa.open = [file, compr_nb, -1, postev]
    return sa

# open a state assertion file
def state_assertion_open_file(file, compression, name, postev):
    sa = state_assertion_of_common(file, compression, name, postev)
    print(sa.name, "opened. You should run 'start' to begin the assertion process.")

new_command("state-assertion-open-file", state_assertion_open_file,
            [arg(filename_t(exist=True), "file"),
             arg(str_t, "compression", "?", "guess", expander = compr_expander),
             arg(str_t, "name", "?", ""),
             arg(int_t, "post_events", "?", 1)],
            type = ["Debugging"],
            short = "open a state assertion file for comparing",
            doc = """
            Open a state assertion file to compare with the current execution.

            - <arg>file</arg> is the name of the file to be created, default is <file>/tmp/state-assertion-$USER.gz</file><br/>
            - <arg>compression</arg> is the compression used (none, gz), default is a guess based on file name<br/>
            - <arg>name</arg> is the name of the object to be created, default is saX where X is a number.<br/>
            - <arg>post_events</arg> tells state-assertion to post events by itself for recording and comparing, default is true.
            """)

def state_assertion_open_server(port, compression, name, postev):
    name = get_sa_name(name)

    compr_nb = get_sa_compr(compression)
    if compr_nb == 0:
        compr_nb = 1
    sa = SIM_create_object(classname, name, [])
    sa.open = ["", compr_nb, port, postev]
    print(name, "connected. You should run start to begin the assertion process.")

new_command("state-assertion-receive", state_assertion_open_server,
            [arg(int_t, "port", "?", 6666),
             arg(str_t, "compression", "?",  "none", expander = compr_expander),
             arg(str_t, "name", "?", ""),
             arg(int_t, "post_events", "?", 1)],
            type = ["Debugging"],
            short = "wait for a connection from a state assertion sender",
            doc = """
Wait for a connection (state-assertion-connect) from a sender. The data
received from the sender will be compared against the current execution.

- <arg>port</arg> indicates where Simics should wait for the connection,
  default is 6666<br/>
- <arg>compression</arg> is the compression used on the file (none, gz),
  default is "none"<br/>
- <arg>name</arg> is the name of the object, default is saX is where X is a
  number.<br/>
- <arg>post_events</arg> tells state-assertion that sender posts events for
  comparing, default is true.
""")

# add an conf object for assertion
def state_assertion_add_cmd(sa, obj, steps, type, attr, step_obj):
    sa.add = [obj, steps, type, attr, step_obj]

new_command("add", state_assertion_add_cmd,
            [arg(obj_t("object"), "obj"),
             arg(int_t, "steps"),
             arg(int_t, "type", "?", 1),
             arg(str_t, "attribute", "?", ""),
             arg(obj_t("object"), "step-obj", "?", None)],
            type = ["Debugging"],
            short = "add an object to be asserted",
            cls = classname,
            doc = """
            Add an object to a state assertion file so its state will be recorded.<br/>
            - <arg>obj</arg> is the name of the object to be added.<br/>
            - <arg>steps</arg> is the number of steps between each save.<br/>
            - <arg>type</arg> is the type of state saved in the file (for devices that provide several, the most complete state is saved by default).<br/>
            - <arg>attribute</arg> is the attribute to save. If specified, the save_state interface is not used and the attribute is saved instead. This is useful for object not implementing the <iface>save_state</iface> interface.<br/>
            - <arg>step-obj</arg> is the object that implements the event queue you want to post the event to. If not specified, the obj must implement step interface.
            """)

# add an conf object for assertion
def state_assertion_add_mem_lis_cmd(sa, memory_space):
    sa.addmemlis = [memory_space]

new_command("add-mem-lis", state_assertion_add_mem_lis_cmd,
            [arg(str_t, "memory_space")],
            type = ["Debugging"],
            short = "add a memory listener on the specified memory space",
            cls = classname,
            doc = """
            Add a memory listener to a memory space so that all memory transactions will be recorded in the file.<br/>
            - <arg>memory_space</arg> is the name of the memory space to listen to.
            """)





# fforward an assertion file
def state_assertion_ff_cmd(sa, obj, steps):
    sa.fforward = [obj.name, steps]

new_command("fforward", state_assertion_ff_cmd,
            [arg(obj_t("object"), "object"),
             arg(int_t, "steps")],
            type = ["Debugging"],
            short = "fast-forward a state assertion file when comparing",
            cls = classname,
            doc = """
            Fast-forward a state assertion file. The contents of the file are
            ignored until the <arg>object</arg> has skipped <arg>steps</arg>
            steps. The simulation is not fast-forwarded. Other objects in the
            file are fast-forwarded along.  """)

# start trace assertion
def state_assertion_start_cmd(sa):
    sa.start = 1

new_command("start", state_assertion_start_cmd,
            [],
            type = ["Debugging"],
            short = "start trace asserting/comparing",
            cls = classname,
            doc = """
            Start the recording/comparison.
            """)

# stop trace assertion
def state_assertion_stop_cmd(sa):
    sa.stop = 1

new_command("stop", state_assertion_stop_cmd,
            [],
            type = ["Debugging"],
            short = "stop trace asserting/comparing and close the file",
            cls = classname,
            doc = """
            Stop the recording/comparison, flush the buffers and close the file.
            """)

# stop trace assertion
def state_assertion_info_cmd(sa):
    sa.info = 1

new_command("info", state_assertion_info_cmd,
            [],
            short = "provide information about the state assertion",
            cls = classname,
            doc = """
            Describe the state assertion performed by the current object.
            """)


# stop trace assertion
def state_assertion_status_cmd(sa):
    sa.status = 1

new_command("status", state_assertion_status_cmd,
            [],
            short = "provide the status of the current state assertion",
            cls = classname,
            doc = """
            Describe the status of the state assertion performed by the
            current object.
            """)

# simple record
def state_assertion_record(file, compression, object, steps, type):
    sa = state_assertion_cf_common(file, compression, "", 8, 1)
    state_assertion_add_cmd(sa, object, steps, type, "", object)
    state_assertion_start_cmd(sa)

new_command("state-assertion-simple-record", state_assertion_record,
            [arg(filename_t(exist=False), "file", "?", temp_filename),
             arg(str_t, "compression", "?",
                 "guess", expander = compr_expander),
             arg(obj_t("object", "save_state"), "object"),
             arg(int_t, "steps", "?", 1),
             arg(int_t, "type", "?", 1)],
            type = ["Debugging"],
            short = "record the state of an object every x steps",
            doc = """
Record the state of an object to file every x steps. You just have to run 'c'
afterwards to begin the recording.

- <arg>file</arg> is the file to write to, default is
  <file>/tmp/state-assertion-$USER.gz</file><br/>
- <arg>compression</arg> is the compression used on the file (none, gz),
  default is a guess based on file name<br/>
- <arg>object</arg> is the simics object whose state will be recorded, the
  object must implement the <iface>save_state</iface> interface<br/>
- <arg>steps</arg> is the number of steps between each state recording,
  default is 1.<br/>
- <arg>type</arg> is the type of state saved in the file (for devices that
  provide several, the most complete state is saved by default).
""")

# simple assert
def state_assertion_assert(file, compression, post):
    sa = state_assertion_of_common(file, compression, "", post)
    state_assertion_start_cmd(sa)

new_command("state-assertion-simple-assert", state_assertion_assert,
            [arg(filename_t(exist=True), "file", "?", temp_filename),
             arg(str_t, "compression", "?", "guess", expander = compr_expander),
             arg(int_t, "post_event", "?", 1)],
            type = ["Debugging"],
            short = "assert the file",
            doc = """
This command asserts the current run against the file. You just have to run
'c' afterwards to begin the assertion process.

- <arg>file</arg> is the file to read the configuration from, default is the
  temporary file created by state-assertion starting commands<br/>
- <arg>compression</arg> is the compression used on the file (none, gz),
  default is a guess based on file name<br/>
- <arg>post_event</arg> tells state-assertion that sender posts events for
  comparing, default is true.
""")
