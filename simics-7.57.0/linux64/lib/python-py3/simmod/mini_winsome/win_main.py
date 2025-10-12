# © 2018 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import os, sys
import threading
from threading import Thread, Event, Lock
from collections.abc import Callable
import conf, wx, simmod.mini_winsome
import simics
import cli
from simicsutils.host import is_windows

def get_main_win():
    return _gui.main

OPEN_WINDOW_EVENT_ID = wx.Window.NewControlId()
REGISTER_EVENT_ID  = wx.Window.NewControlId()
TEXT_CONSOLE_EVENT_ID  = wx.Window.NewControlId()
GFX_CONSOLE_EVENT_ID  = wx.Window.NewControlId()
CONSOLES_READY_EVENT_ID  = wx.Window.NewControlId()

_gui = None
_thread = None

from .win_utils import *

def run_sync_in_gui_thread(fun, *args, **kwargs):
    """Run a callback in the GUI thread, and wait for it to return."""
    r = []
    wx.CallAfter(lambda: r.append(fun(*args, **kwargs)))
    if simics.SIM_process_work(lambda x: bool(r), None) < 0:
        simics.VT_user_interrupt(None, False)
    return r[0]

window_icons = {}

def get_window_icons(name = 'simics'):
    global window_icons
    if name in window_icons:
        return window_icons[name]
    window_icons[name] = wx.IconBundle()

    # we only have 256x256 icon for the regular Simics icon
    sizes = [16, 32, 48, 64]
    if name == 'simics' and is_windows():
        sizes.append(256)

    for size in sizes:
        filename = bitmap_path('%s-%dx%dx32.png' % (name, size, size))
        window_icons[name].AddIcon(filename, wx.BITMAP_TYPE_PNG)
    return window_icons[name]

window_types = {}
# for one per obj windows, window_list contains a dict {} indexed by obj name
# for multiple windows, window_list contains a list []
window_list = {}

class window_type:
    def __init__(self, name, win_cls):
        self.name = name
        self.win_cls = win_cls

class command_info:
    "Used to pass information for the CLI command of a window"
    def __init__(self, name, doc_str):
        self.name = name
        self.doc_str = doc_str

def open_window_cmd(window):
    open_window(window)
    return None

def create_command(window, cmd_info):
    def cmd_fun(hidden = False):
        return open_window_cmd(window)
    cli.new_command(cmd_info.name, cmd_fun, [],
                    short = "open a %s window" % cmd_info.doc_str,
                    doc = "Open a %s window." % cmd_info.doc_str)

def register_win_type(need_cpu, win_cls, cmd_info, multi = None):

    if not simmod.mini_winsome.check_wx.have_wx():
        # Do nothing if a window module is imported when there is no GUI
        return

    name = win_cls.window_name
    window_types[name] = window_type(name, win_cls)
    # multi corresponds to the entry kind in the window_list
    window_list[name] = multi
    if cmd_info:
        create_command(name, cmd_info)

import simmod.mini_winsome.appwindow
import simmod.mini_winsome.win_control
import simmod.mini_winsome.win_target_consoles
import simmod.mini_winsome.console_iface

_app_started = Event()

def add_window(w, win_type):
    window_list[win_type] = w

def existing_in_window_list(win_type):
    w = None
    if window_list[win_type]:
        w = window_list[win_type]
    return w

def window_name_exists(name):
    return name in window_types

def window_type_window(name):
    return window_types[name].win_cls

def open_window(name):
    event = wx.PyEvent(eventType = OPEN_WINDOW_EVENT_ID)
    event.win = name
    wx.PostEvent(_gui, event)

class text_console_event(wx.PyEvent):
    def __init__(self, name, args):
        wx.PyEvent.__init__(self)
        self.SetEventType(TEXT_CONSOLE_EVENT_ID)
        self.name = name
        self.args = args

class gfx_console_event(wx.PyEvent):
    def __init__(self, name, args):
        wx.PyEvent.__init__(self)
        self.SetEventType(GFX_CONSOLE_EVENT_ID)
        self.name = name
        self.args = args

####

class main_window(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, wx.ID_ANY, "Main Window",
                          name = "SimicsMain")

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

    def OnCloseWindow(self, evt):
        evt.Skip()

def set_c_locale():
    old = os.environ.get("LC_ALL", None)
    os.environ["LC_ALL"] = "C"
    return old

def restore_locale(old):
    if old is None:
        os.environ.pop("LC_ALL")
    else:
        os.environ["LC_ALL"] = old

# must be created from the thread!
class gui_app(wx.App):
    def __init__(self):

        # Temporarily reset $LC_ALL to "C" to avoid having wx.App() setting
        # a non-default locale for the entire Simics process with all the
        # trouble that would cause (see bug 20590).
        old_locale = set_c_locale()
        # Make sure to set redirect to false, this is the default on Linux but
        # not on Windows.
        wx.App.__init__(self, redirect = False)
        restore_locale(old_locale)
        self.register_event(OPEN_WINDOW_EVENT_ID, self.open_window_event)
        self.register_event(TEXT_CONSOLE_EVENT_ID, self.text_console_cb)
        self.register_event(GFX_CONSOLE_EVENT_ID, self.gfx_console_cb)
        self.register_event(CONSOLES_READY_EVENT_ID, self.consoles_ready)
        self.usage = False

    def open_window_event(self, event):
        if not window_name_exists(event.win):
            print("Open request for unknown window: %s" % event.win)
            return
        with simics_lock():
            if not self.usage:
                self.usage = True
                simics.VT_add_telemetry_data("core.features", "winsome", True)
            w = existing_in_window_list(event.win)
            if not w:
                win_cls = window_type_window(event.win)
                w = win_cls(self.main)
                if w:
                    add_window(w, event.win)
                    w.SetIcons(get_window_icons())
        # Show target console list if explicitly requested
        if (w and (event.win != simmod.mini_winsome.console_iface.WINDOW_NAME
                   or show_target_console_list())):
            w.Show() # after releasing lock
            w.Raise()

    def register_event(self, id, cb):
        self.Connect(wx.ID_ANY, wx.ID_ANY, id, cb)

    def register_event_cb(self, event):
        self.register_event(event.id, event.cb)

    def text_console_cb(self, event):
        simmod.mini_winsome.console_iface.handle_text_event(event.name, event.args)

    def gfx_console_cb(self, event):
        simmod.mini_winsome.console_iface.handle_gfx_event(event.name, event.args)

    def consoles_ready(self, event):
        console_window = simmod.mini_winsome.console_iface.create_console_window()
        if console_window:
            console_window.configuration_loaded()
        else:
            wx.PostEvent(_gui, wx.PyEvent(eventType = CONSOLES_READY_EVENT_ID))

    def start(self):
        # Always have a "main-window" (for events etc to work)
        self.main = main_window()
        _app_started.set()
        self.MainLoop()

def console_open():
    wx.PostEvent(_gui, wx.PyEvent(eventType = CONSOLES_READY_EVENT_ID))

def gui_thread_run():
    simics.VT_register_oec_thread()
    global _gui
    try:
        if not wx.App.IsDisplayAvailable():
            raise SystemError("")

        _gui = gui_app()
        _gui.start()
    except SystemError as inst:
        print(f"{inst}\n\nFailed to initialize GUI try running with -no-win",
              file=sys.stderr, flush=True)
        os._exit(-1)
    simics.VT_unregister_thread()

class gui_thread(Thread):
    def __init__(self):
        Thread.__init__(self, daemon = True)

    def run(self):
        simics.CORE_set_thread_name("simics-gui")
        gui_thread_run()

class gui_thread_osx:
    def run(self):
        global _thread
        _thread = threading.current_thread()
        gui_thread_run()

# Protects that thinks done during the startup of Winsome is only done
# once.

# _winsome_started means that the Winsome thread is started and that
# the gui object exists.

# _init means that the global variables are set. If simics isn't in
# 'no-gui' mode it also means that the _winsome_started tasks have
# been done.

_init = _winsome_started = False

def is_in_gui_thread():
    return threading.current_thread() == _thread

def assert_in_gui_thread():
    '''Asserts that the current thread is the GUI thread.'''

    assert is_in_gui_thread()

def assert_not_in_gui_thread():
    '''Asserts that the current thread is not the GUI thread.'''

    assert not is_in_gui_thread()

def _start_winsome():
    global _thread, _winsome_started
    if _winsome_started:
        return

    # We know the GUI will be used, create the gui object
    simics.SIM_create_object("gui", "sim.gui")
    simics.VT_add_permanent_object(conf.sim.gui)

    _thread = gui_thread()
    _thread.start()

    _app_started.wait()
    _winsome_started = True

###

def win_init():
    # called directly after project is set, before any preferences are loaded
    global _init
    if _init:
        return
    #
    _init = True

    _start_winsome()

def register_event(id, cb):
    'Register an event callback to be called when an event with id is received'
    event = wx.PyEvent(eventType = REGISTER_EVENT_ID)
    event.id = id
    event.cb = cb
    wx.PostEvent(_gui, event)

def post_event(event):
    wx.PostEvent(_gui, event)

def post_text_console_event(name, args):
    post_event(text_console_event(name, args))

def post_gfx_console_event(name, args):
    post_event(gfx_console_event(name, args))

# set to True when an event to freeze the GUI thread has (is about to)
# been posted
_thread_freeze_pending = False

# this event is set when the GUI really is frozen
_thread_frozen = Event()

def _actually_freeze_gui_thread():
    '''Puts the GUI into a permanent sleep and signals the
    _thread_frozen event.'''

    # do this before we risk causing any assertion, just in case
    _thread_frozen.set()

    # install something on the work queue to make sure the main thread wakes up
    simics.SIM_register_work(lambda x:None, None)

    global _thread_freeze_pending
    assert _thread_freeze_pending
    assert_in_gui_thread()

    # permasleep
    dummy = Event()
    dummy.wait()

def prepare_for_shutdown():
    '''Only call this from non-GUI threads if GUI initialized. Freezes the
    GUI thread permanently. Returns after the GUI thread has stopped.'''

    if _thread == None:
        return
    assert_not_in_gui_thread()

    global _thread_freeze_pending
    if not _thread_freeze_pending:
        _thread_freeze_pending = True

        # callback never happens if freeze_gui_thread_for_shutdown()
        # is called first
        wx.CallAfter(_actually_freeze_gui_thread)

    # Process work to avoid deadlocks while waiting until the GUI thread is
    # indeed frozen. Would be much better if we could use _thread_frozen.wait()
    # instead since SIM_process_work may call functions that will not behave
    # well during shutdown.
    simics.SIM_process_work(lambda x:_thread_frozen.is_set(), None)

def freeze_gui_thread_for_shutdown():
    '''Only call this from the GUI thread. Freezes said thread
    permanently. Does not return.'''

    assert_in_gui_thread()
    release_simics_lock_if_held()

    global _thread_freeze_pending
    _thread_freeze_pending = True
    _actually_freeze_gui_thread()

# Special function for the SPARK team primarily, allowing them to turn off
# expensive hap callbacks and related updates that will shut down all CPUs.
def disable_expensive_updates():
    pass

# Special functions to facilitate closing the target console
# list in a prorgrammatic way.

_show_target_console_list = None

def show_target_console_list(show=None):
    global _show_target_console_list
    val = _show_target_console_list
    if show is not None:
        _show_target_console_list = show
    return val

def close_console_list():
    w = existing_in_window_list("target-console")
    if w:
        w.Hide()

_cycle_obj_selector = None

def select_cycle_obj():
    global _cycle_obj_selector
    objs = list(simics.SIM_object_iterator_for_interface(['cycle']))
    assert objs
    if _cycle_obj_selector:
        return _cycle_obj_selector(objs)
    else:
        return objs[0]

# Backdoor function for graphics team primary to select cycle object from which
# the virtual time display in the status bar is taken.
def set_cycle_obj_selector(fun: Callable[[], simics.conf_object_t]):
    global _cycle_obj_selector
    _cycle_obj_selector = fun
