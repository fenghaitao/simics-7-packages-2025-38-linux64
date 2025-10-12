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


import signal, sys
import conf, simics, terminal_frontend
import fcntl, termios, struct
import os, threading, platform

def get_terminal_size():
    s = struct.pack("HHHH", 0, 0, 0, 0)
    try:
        lines, cols = struct.unpack("HHHH",
                                    fcntl.ioctl(sys.__stdout__.fileno(),
                                                termios.TIOCGWINSZ, s))[:2]
    except IOError:
        cols, lines = (80, 24)
    return (cols if cols else 80, lines if lines else 24)

class unix_frontend:
    def __init__(self, obj):
        self.new_size = True # make sure we read the terminal size at startup
        try:
            signal.signal(signal.SIGWINCH, self.window_size_signal)
        except ValueError:
            # From Python doc: "When threads are enabled, this function
            # [i.e. signal.signal] can only be called from the main thread of
            # the main interpreter; attempting to call it from other threads
            # will cause a ValueError exception to be raised." We get here when
            # 'simics' module is executed not from the main thread of the Python
            # interpreter (which may happen when embedding Simics into a Python
            # application). For simplicity, we just ignore this error and thus
            # will "ignore" SIGWINCH signals.
            print("Failed to start tracking console size changes",
                  file=sys.__stderr__)

    def window_size_signal(self, signo, frame):
        self.new_size = True

    def update_terminal_size(self):
        x, y = get_terminal_size()
        self.term_iface.set_size(x, y)

    def output_text(self, text):
        sys.__stdout__.write(text)
        if text and not text.endswith('\n'):
            sys.__stdout__.flush()

    def terminal_write(self, text):
        try:
            self.output_text(text)
        except Exception as ex:
            print("Failed writing to stdout: %s" % ex, file=sys.__stderr__)

    def terminal_disconnect(self):
        sys.__stdout__.write('\n')
        simics.SIM_quit(0)

    def get_term_frontend(self):
        return self.term_frontend

    def set_term_frontend(self, val):
        try:
            self.term_iface = simics.SIM_get_interface(
                val, simics.TERMINAL_SERVER_INTERFACE)
        except Exception:
            simics.SIM_attribute_error("The %s object does not implement the "
                                       "%s interface"
                                       % (val.name,
                                          simics.TERMINAL_SERVER_INTERFACE))
            return simics.Sim_Set_Interface_Not_Found
        self.term_frontend = val
        return simics.Sim_Set_Ok

    def cmdline_input_avail(self, obj):
        try:
            chars = sys.__stdin__.read()
        except IOError:
            return
        if not chars:
            simics.SIM_quit(0)
        if self.new_size:
            self.new_size = False
            self.update_terminal_size()
        self.term_iface.write(chars)

    def start_input(self, obj):
        simics.SIM_notify_on_descriptor(
            0, simics.Sim_NM_Read, 0,
            self.cmdline_input_avail, obj)

# class

allocated = False

def init_object_wrapper(obj):
    global allocated
    if allocated:
        print("Can only have one instance of the <cmdline_frontend> class.")
        return None
    allocated = True
    return unix_frontend(obj)

def finalize_instance_wrapper(obj):
    obj.object_data.start_input(obj)

    # override standard raw_input function with a function adapted for Simics
    raw_input_orig = input
    def sim_raw_input(*message):
        simics.SIM_notify_on_descriptor(0, simics.Sim_NM_Read, 0, None, obj)

        term_attrs_sim = termios.tcgetattr(0)
        term_attrs_new = termios.tcgetattr(0)
        term_attrs_new[3] = term_attrs_sim[3] | termios.ECHO | termios.ICANON
        termios.tcsetattr(0, termios.TCSANOW, term_attrs_new)

        std_sim = (sys.stdin, sys.stdout, sys.stderr)
        std_new = (sys.__stdin__, sys.__stdout__, sys.__stderr__)
        (sys.stdin, sys.stdout, sys.stderr) = std_new

        try:
            ret_val = raw_input_orig(*message)
        finally:
            (sys.stdin, sys.stdout, sys.stderr) = std_sim
            termios.tcsetattr(0, termios.TCSANOW, term_attrs_sim)
            obj.object_data.start_input(obj)

        return ret_val

    import builtins
    builtins.input = sim_raw_input

class_data = simics.class_info_t(
    init        = init_object_wrapper,
    finalize    = finalize_instance_wrapper,
    kind        = simics.Sim_Class_Kind_Pseudo,
    description = ("Class implementing the native Simics command line on"
                   " Linux systems."),
)
simics.SIM_create_class('cmdline_frontend', class_data)

# attributes

def get_term_frontend_wrapper(obj):
    return obj.object_data.get_term_frontend()

def set_term_frontend_wrapper(obj, val):
    return obj.object_data.set_term_frontend(val)

simics.SIM_register_attribute(
    'cmdline_frontend', 'terminal_frontend',
    get_term_frontend_wrapper,
    set_term_frontend_wrapper,
    simics.Sim_Attr_Required | simics.Sim_Attr_Internal,
    "o",
    "The terminal frontend object that provides access to a Simics "
    "command line with a VT100/ANSI interface.")

# interfaces

term_iface = simics.terminal_client_interface_t(
    write      = lambda obj, id, str: obj.object_data.terminal_write(str),
    disconnect = lambda obj, id: obj.object_data.terminal_disconnect())
simics.SIM_register_interface('cmdline_frontend',
                              simics.TERMINAL_CLIENT_INTERFACE, term_iface)

def init_cmdline():
    term = simics.pre_conf_object('sim.cmdline.term', 'terminal_frontend')
    cmd = simics.pre_conf_object('sim.cmdline', 'cmdline_frontend')
    term.frontend = cmd
    term.session_id = 0
    term.colorize = (sys.__stdout__.isatty()
                     and conf.classes.terminal_frontend.colorize_default)
    term.interactive = (sys.__stdout__.isatty()
                        and not simics.SIM_get_batch_mode())
    term.primary = True
    cmd.terminal_frontend = term
    simics.SIM_add_configuration([term, cmd], None)
    simics.VT_add_permanent_object(conf.sim.cmdline)
    simics.VT_add_permanent_object(conf.sim.cmdline.term)
    sys.__stdout__.flush()
