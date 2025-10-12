# module_load.py

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


import cli
import simics
import os

simics.SIM_hap_add_type("Arinc429_Word", "", None, None,
                 "This hap is triggered on every word sent on a "
                 "arinc429_bus object. In the hap handler, the "
                 "last_word attribute can be read or modified. "
                 "Setting it to -1 will drop the packet.", 0)

def stringify_port(obj):
    if isinstance(obj, type([])):
        return "%s.%s"%(obj[0].name, obj[1])
    return obj[0].name

def get_bus_info(obj):
    return [("", [("Receivers",
                   list(map(stringify_port, obj.receivers)))])]

def get_bus_status(obj):
    return []

cli.new_info_command("arinc429_bus", get_bus_info)
cli.new_status_command("arinc429_bus", get_bus_status)

# Playback commands.

class playback_obj:
    # placeholder for things used during playback
    pass

def determine_format(u):
    line = pb_fileobj.readline()
    if line.startswith('Arinc-429 time-value pairs'):
        u.parse_entry = parse_simple_text
        return 1
    return 0

def parse_simple_text(u):
    while True:
        line = pb_fileobj.readline()
        if not line:
            return 0
        parts = line.split()
        if len(parts) != 4 or parts[0] != "cycle" or parts[2] != "data":
            print("Malformed line in playback data (%r) - skipped." % line)
            continue
        u.nexttime = int(parts[1])
        u.data = int(parts[3], 0)
        return 1

def playback_event(cpu, u):
    u.bus.iface.arinc429_bus.send_word(u.data, -1)
    skipped = 0
    record_time_now = (simics.SIM_cycle_count(u.bus)
        - u.sim_start_time + u.first_record_time)
    while True:
        valid = u.parse_entry(u)
        if not valid:
            print("Playback file %s exhausted." % u.given_filename)
            return
        if u.nexttime < record_time_now:
            skipped += 1
            continue
        break
    if skipped:
        print("Playback skipped %d events from the past." % skipped)
    simics.SIM_event_post_cycle(u.bus.queue, pb_event,
                         u.bus.queue, u.nexttime - record_time_now, u)

pb_event = simics.SIM_register_event("playback", None, simics.Sim_EC_Notsaved,
                              playback_event, None, None, None, None)
pb_fileobj = None
def playback_cmd(bus, filename):
    global pb_fileobj
    u = playback_obj()
    fullpath = simics.SIM_lookup_file(filename)
    if not fullpath:
        raise cli.CliError("File could not be found in Simics path: %s." % filename)
    u.given_filename = filename
    if pb_fileobj != None:
        print ("Playback is already started. "
               "Stop playback before starting a new playback.")
        return
    pb_fileobj = open(fullpath)
    if not determine_format(u):
        pb_fileobj.close()
        pb_fileobj = None
        raise cli.CliError("File format of %s not recognised." % filename)
    u.bus = bus
    u.freq_mhz = bus.queue.freq_mhz
    valid = u.parse_entry(u)
    if not valid:
        print("File %s contains no records." % filename)
        pb_fileobj.close()
        pb_fileobj = None
        return
    u.sim_start_time = simics.SIM_cycle_count(u.bus)
    u.first_record_time = u.nexttime
    playback_event(None, u)

def playback_stop_cmd(bus):
    global pb_fileobj
    simics.SIM_event_cancel_time(bus.queue, pb_event,
                          bus.queue, None, None)
    if pb_fileobj != None:
        pb_fileobj.close()
        pb_fileobj = None

def record_hap_handler(udata, bus):
    print("cycle %d data 0x%08x" % (
        simics.SIM_cycle_count(bus), bus.last_word), file=cap_fileobj)
    cap_fileobj.flush()

cap_fileobj = None
def record_cmd(bus, filename):
    global cap_fileobj
    if cap_fileobj != None:
        print ("Recording is already started. "
               "Stop recording before starting a new record.")
        return
    if os.path.exists(filename):
        cap_fileobj = open(filename, "a")
        print ("The file already exists, "
               "if this is not intended, run capture-stop to stop recording.")
    else:
        cap_fileobj = open(filename, "w")
        print(("Arinc-429 time-value pairs record of bus %s"
                               % bus.name), file=cap_fileobj)
    simics.SIM_hap_add_callback("Arinc429_Word", record_hap_handler, None)

def record_stop_cmd(bus):
    global cap_fileobj
    simics.SIM_hap_delete_callback("Arinc429_Word", record_hap_handler, None)
    if cap_fileobj != None:
        cap_fileobj.close()
        cap_fileobj = None

cli.new_command("capture-start", record_cmd,
            args = [cli.arg(cli.filename_t(), "filename")],
            short = "start traffic recorder",
            doc = "Starts recording bus traffic to a specified "
                  "<arg>filename</arg>. "
                  "A simple text format is used. If the file exists, "
                  "new data is appended to the file.",
            cls = "arinc429_bus",
            type = ["Recording"],
            see_also = ["<arinc429_bus>.capture-stop"])

cli.new_command("capture-stop", record_stop_cmd,
            args = [],
            short = "stop traffic recorder",
            doc = "Stop recording bus traffic previously started with "
                  "capture-start.",
            type = ["Recording"],
            cls = "arinc429_bus",
            see_also = ["<arinc429_bus>.capture-start"])

cli.new_command("playback-start", playback_cmd,
            args = [cli.arg(cli.filename_t(exist = 1), "filename")],
            short = "start traffic generator",
            type = ["Recording"],
            doc = "Starts generating bus traffic from the specified "
                   "<arg>filename</arg>. "
                  "The file should be in the simple text format like "
                  "the captured file with capture-start. The timestamp "
                  "of the first entry is used as the base time, i.e the "
                  "playback starts immediately.",
            cls = "arinc429_bus",
            see_also = ["<arinc429_bus>.capture-start",
                        "<arinc429_bus>.playback-stop"])

cli.new_command("playback-stop", playback_stop_cmd,
            args = [],
            short = "stop traffic generation",
            type = ["Recording"],
            doc = "Stop bus traffic generation previously started with "
                  "playback-start.",
            cls = "arinc429_bus",
            see_also = ["<arinc429_bus>.playback-start"])
