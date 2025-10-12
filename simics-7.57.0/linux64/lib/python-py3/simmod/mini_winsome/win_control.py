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

import wx
import cli
import copy
import os
from os.path import abspath
import simics
import sim_commands
import conf
import target_info
from simicsutils.host import is_windows
from targets import sim_params
import subprocess

import simmod.mini_winsome.win_main as win_main
from simmod.mini_winsome.appwindow import appwindow
from simmod.mini_winsome.win_utils import *
import simmod.mini_winsome.fsel as fsel

ID_MENU_NEW_EMPTY = wx.Window.NewControlId()
ID_MENU_TARGET = wx.Window.NewControlId()
ID_MENU_NEW = wx.Window.NewControlId()
ID_MENU_OPEN = wx.Window.NewControlId()
ID_MENU_SAVE = wx.Window.NewControlId()
ID_MENU_CONSOLES = wx.Window.NewControlId()

ID_TOOL_NEW = wx.Window.NewControlId()
ID_TOOL_OPEN = wx.Window.NewControlId()
ID_TOOL_SAVE = wx.Window.NewControlId()
ID_TOOL_RUN = wx.Window.NewControlId()
ID_TOOL_STOP = wx.Window.NewControlId()

STATUS_TIMER_INTERVAL = 1000

def all_glob():
    return "*.*" if is_windows() else "*"

MACHINE_BORDER = 2

class BackgroundPanel(wx.Panel):
    def __init__(self, parent, id, background_color, style):
        wx.Panel.__init__(self, parent, id, style = style)
        self.bg_color = background_color
        self.bg_pen = wx.Pen(self.bg_color)
        self.bg_brush = wx.Brush(self.bg_color)
        self.SetBackgroundColour(self.bg_color)
        self.Bind(wx.EVT_PAINT, self.OnPaint)

    def OnPaint(self, evt):
        dc = wx.BufferedPaintDC(self)
        size = dc.GetSize()
        sx = size.GetWidth()
        sy = size.GetHeight()
        dc.SetPen(self.bg_pen)
        dc.SetBrush(self.bg_brush)
        dc.DrawRectangle(0, 0, sx, sy)

def add_machine_desc(win, tsizer, desc, value):
    tsizer.SetRows(tsizer.GetRows() + 1)
    txt = wx.StaticText(win, wx.ID_ANY, desc + ':')
    font = txt.GetFont()
    font.SetWeight(wx.FONTWEIGHT_BOLD)
    txt.SetFont(font)
    tsizer.Add(txt, flag = wx.ALL, border = 2)
    txt = wx.StaticText(win, wx.ID_ANY, value)
    tsizer.Add(txt, flag = wx.ALL, border = 2)

def create_machine_view(win, info):
    desc, icon, props = info
    sizer = wx.BoxSizer(wx.VERTICAL)
    panel = BackgroundPanel(win, wx.ID_ANY,
                            wx.TheColourDatabase.FindColour("WHITE"),
                            wx.SIMPLE_BORDER)
    psizer = wx.BoxSizer(wx.VERTICAL)
    psizer.Add(wx.StaticText(panel, wx.ID_ANY, desc),
               flag = wx.LEFT, border = 12)
    msizer = wx.BoxSizer(wx.HORIZONTAL)
    bm = wx.StaticBitmap(panel, wx.ID_ANY, get_bitmap(icon))
    msizer.Add(bm, flag = wx.ALIGN_CENTER)
    tsizer = wx.FlexGridSizer(2)
    for key, value in props:
        add_machine_desc(panel, tsizer, key, value)
    msizer.Add(tsizer, proportion = 1, flag = wx.EXPAND)
    dummysizer = wx.BoxSizer(wx.HORIZONTAL)
    psizer.Add(msizer)
    psizer.Add(dummysizer, proportion = 1, flag = wx.EXPAND)
    panel.SetSizerAndFit(psizer)
    sizer.Add(panel, proportion = 1, flag = wx.EXPAND)
    return sizer

class machine_window(wx.ScrolledWindow):
    def __init__(self, parent, info):
        wx.ScrolledWindow.__init__(self, parent, wx.ID_ANY,
                                   style = wx.SIMPLE_BORDER)
        self.SetBackgroundColour(wx.WHITE)
        msizer = wx.BoxSizer(wx.VERTICAL)
        if len(info) == 0:
            info = [['No machine loaded', 'empty_machine.png',
                     [['System', ''],
                      ['Processor', ''],
                      ['Memory', ''],
                      ['Ethernet', ''],
                      ['Storage', '']]]]
        # TODO: check for huge # of machines and use simpler view...
        for i in info:
            msizer.Add(create_machine_view(self, i),
                       proportion = 1, flag = wx.EXPAND | wx.ALL,
                       border = MACHINE_BORDER)
        self.num_machines = len(info)
        if self.num_machines > 1:
            self.SetScrollRate(0, 20)
        self.SetSizerAndFit(msizer)

def host_close_string():
    if is_windows():
        return '&Close Window\tCtrl-F4'
    else:
        return '&Close Window\tCtrl-W'

def host_exit_string():
    if is_windows():
        return 'E&xit\tAlt-F4'
    else:
        return '&Quit\tCtrl-Q'

def cycle_obj_exists():
    return bool(list(simics.SIM_object_iterator_for_interface(['cycle'])))

def step_obj_exists():
    return bool(list(simics.SIM_object_iterator_for_interface(['step'])))

def queue_exists():
    return cycle_obj_exists() or step_obj_exists()

def first_cycle_obj():
    if cycle_obj_exists():
        return win_main.select_cycle_obj()
    else:
        return None

def time_to_string(seconds):
    try:
        hrs = int(seconds // 3600)
        mins = int((seconds - (hrs * 3600)) // 60)
        seconds -= hrs * 3600 + mins * 60
        hstr = '%d h ' % hrs if hrs else ''
        mstr = '%d min ' % mins if mins else ''
    except OverflowError:
        return "-" # happens if seconds is inf
    return "%s%s%.3f s" % (hstr, mstr, seconds)

def configuration_exists():
    for o in simics.SIM_object_iterator(None):
        if not simics.CORE_is_permanent_object_name(o.name) and not o.name == 'gui':
            return True
    return False

def _restart_simics_callback(data):
    (filename, argv) = data
    argv += ['-e', 'win-control']
    try:
        sim_commands.restart_simics_cmd(filename, False, False, argv)
    except Exception as msg:
        print("Failed restarting Simics: %s" % msg)

def _restart_callback(arg_list):
    simics.SIM_thread_safe_callback(_restart_simics_callback, arg_list)
    win_main.freeze_gui_thread_for_shutdown()

def restart_simics(filename = None, argv = []):
    wx.CallAfter(lambda: _restart_callback((filename, argv)))

def quiet_start_simulation(arg):
    try:
        # may throw SimExc_Break that is handled specially by c->python
        # exception translation
        simics.SIM_continue(0)
    except Exception as ex:
        print("Unexpected Error", "%s" % ex)

def image_dirs():
    with simics_lock():
        path = conf.sim.module_searchpath
    return [d for d in (os.path.join(p, 'images') for p in path)
            if os.path.isdir(d)]

class control_window(wx.Frame, appwindow):
    window_name = "control"
    def __init__(self, parent):
        self.extractor = target_info.TargetInfoExtractor()
        self.old_info = None
        self.title = 'Intel® Simics® Simulator - Control'
        wx.Frame.__init__(self, parent, wx.ID_ANY, self.title,
                          style = wx.DEFAULT_FRAME_STYLE,
                          name = "SimicsControl")
        self.default_checkpoint_dir = abspath('.')
        self.forwarding = simics.SIM_simics_is_running()

        assert_simics_lock()
        # Status bar
        self.CreateStatusBar(2)
        # Sunken not supported in wxPython 3, only raised
        self.GetStatusBar().SetStatusStyles([wx.SB_RAISED] * 2)

        ellipsis = "\N{HORIZONTAL ELLIPSIS}"
        # Menu
        self.filemenu = wx.Menu()
        self.filemenu.Append(ID_MENU_TARGET,
                             'Load &Target%s\tCtrl-T'
                             % ellipsis,
                             'Load target into a new session')
        self.filemenu.Append(ID_MENU_NEW_EMPTY,
                             "New &Empty Session",
                             'Create a new empty session')
        self.filemenu.Append(ID_MENU_NEW,
                             '&New Session from Script%s\tCtrl-N'
                             % ellipsis,
                             'New session from a script')
        self.filemenu.AppendSeparator()
        self.filemenu.Append(ID_MENU_OPEN,
                             '&Open Checkpoint%s\tCtrl-O' % ellipsis,
                             'Open a checkpoint')
        self.filemenu.Append(ID_MENU_SAVE,
                             '&Save Checkpoint%s\tCtrl-S' % ellipsis,
                             'Save a checkpoint')

        self.viewmenu = wx.Menu()
        self.viewmenu.Append(ID_MENU_CONSOLES, '&Target consoles',
                             'Open target console window')
        self.first_window_idx = 6 # update when adding other entries first
        #
        self.menubar = wx.MenuBar()
        self.menubar.Append(self.filemenu, '&File')
        self.menubar.Append(self.viewmenu, '&Tools')
        self.SetMenuBar(self.menubar)
        self.Bind(wx.EVT_MENU, self.empty_session, None, ID_MENU_NEW_EMPTY)
        self.Bind(wx.EVT_MENU, self.load_target, None, ID_MENU_TARGET)
        self.Bind(wx.EVT_MENU, self.new_session, None, ID_MENU_NEW)
        self.Bind(wx.EVT_MENU, self.open_checkpoint, None, ID_MENU_OPEN)
        self.Bind(wx.EVT_MENU, self.save_checkpoint, None, ID_MENU_SAVE)
        self.menu_window(ID_MENU_CONSOLES, "target-console")
        #

        if not queue_exists():
            self.configuration_loaded = False
            self.filemenu.Enable(ID_MENU_SAVE, False)
        else:
            self.configuration_loaded = True

        # Toolbar
        self.toolbar = self.CreateToolBar(wx.TB_HORIZONTAL)
        self.toolbar.SetMargins([2, 2])
        tsize = self.toolbar.GetToolBitmapSize()
        if tsize[0] < 32 or tsize[1] < 32:
            self.toolbar.SetToolBitmapSize((32, 32))
        new_tool = get_bitmap('gtk-new.png')
        open_tool = get_bitmap('gtk-open.png')
        save_tool = get_bitmap('gtk-save-as.png')
        self.toolbar.AddTool(ID_TOOL_NEW, '',
                             new_tool, wx.NullBitmap, wx.ITEM_NORMAL,
                             'New target session')
        self.toolbar.AddTool(ID_TOOL_OPEN, '',
                             open_tool, wx.NullBitmap, wx.ITEM_NORMAL,
                             'Open a checkpoint')
        self.toolbar.AddTool(ID_TOOL_SAVE, '',
                             save_tool, wx.NullBitmap, wx.ITEM_NORMAL,
                             'Save a checkpoint')
        self.toolbar.AddSeparator()
        self.toolbar.AddTool(ID_TOOL_STOP, '',
                             get_bitmap('gtk-media-pause.png'),
                             wx.NullBitmap, wx.ITEM_RADIO,
                             'Stop the simulation')
        self.toolbar.AddTool(ID_TOOL_RUN, '',
                             get_bitmap('gtk-media-play-ltr.png'),
                             wx.NullBitmap, wx.ITEM_RADIO,
                             'Run the simulation forwards')
        self.toolbar.AddSeparator()
        #
        self.toolbar.Realize()
        self.toolbar.Fit()
        # cache the size since it keeps growing on Windows for some reason
        self.toolbar_width = self.toolbar.GetSize()[0]

        self.toolbar.Bind(wx.EVT_TOOL, self.load_target, None, ID_TOOL_NEW)
        self.toolbar.Bind(wx.EVT_TOOL, self.open_checkpoint, None, ID_TOOL_OPEN)
        self.toolbar.Bind(wx.EVT_TOOL, self.save_checkpoint, None, ID_TOOL_SAVE)
        self.toolbar.Bind(wx.EVT_TOOL, self.toolbar_stop, None, ID_TOOL_STOP)
        self.toolbar.Bind(wx.EVT_TOOL, self.toolbar_run, None, ID_TOOL_RUN)

        self.run_state = ""
        self.update_run_state(self.initial_run_state())

        install_hap_callback("UI_Run_State_Changed", self.run_state_changed)
        install_hap_callback("Core_Configuration_Loaded", self.sim_loaded)
        self.set_up_expensive_haps()

        if not queue_exists():
            self.toolbar.EnableTool(ID_TOOL_SAVE, False)

        self.Bind(wx.EVT_WINDOW_CREATE, self.on_window_create)

        # Status Update
        self.ptime = 0
        self.show_status_time(True)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.status_timer = wx.Timer(self, wx.Window.NewControlId())
        self.set_status_timer_state(True)
        self.Bind(wx.EVT_ICONIZE, self.iconize_event)
        self.Bind(wx.EVT_TIMER, self.show_status_time_cb)

        self.menu_width = 0
        for i in range(self.menubar.GetMenuCount()):
            t = self.menubar.GetMenu(i).GetTitle()
            self.menu_width += self.menubar.GetTextExtent(t)[0]
            # approximate space between menus with two characters, the title
            # includes one of them, an additional _.
            self.menu_width += self.menubar.GetTextExtent('x')[0]
        # some space around it
        self.menu_width += self.menubar.GetTextExtent('xx')[0]
        self.scrolled = None
        self.SetSizerAndFit(sizer)
        self.empty_height = self.GetClientSize()[1]
        self.update_machine_list()
        appwindow.__init__(self)

    def set_up_expensive_haps(self):
        # TODO: redrawing everything is too slow, should optimize
        target_info.ensure_target_info_changed_hap()
        install_hap_callback("Target_Info_Changed", self.target_info_changed)

    def set_status_timer_state(self, start):
        # Use a one-shot timer to avoid generating extra timer events when
        # the callback is slower than the update interval
        if start:
            self.status_timer.Start(STATUS_TIMER_INTERVAL, wx.TIMER_ONE_SHOT)
        else:
            self.status_timer.Stop()

    def iconize_event(self, event):
        self.set_status_timer_state(not event.IsIconized())

    def on_show(self, event):
        self.set_status_timer_state(event.IsShown())

    def on_window_create(self, ev):
        if ev.Window == self:
            self.Unbind(wx.EVT_WINDOW_CREATE)    # Event only needed once.

            # Wait for the window to actually be created before attempting
            # to change the console window grouping: on Unix, the creation
            # must be pushed to the X11 server because the console
            # collection code performs its window grouping through a
            # separate display connection (bug 23978).
            wx.GetApp().Yield()
        ev.Skip()

    def target_info_changed(self, obj):
        self.update_machine_list()

    def update_size(self):
        machine_height = (self.scrolled.GetVirtualSize()[1]
                         // self.scrolled.num_machines)
        borders = self.empty_height + 2 * MACHINE_BORDER
        # show up to two machines
        show_machines = min(2, self.scrolled.num_machines)
        width = max(self.toolbar_width, self.GetSize()[0],
                    self.menu_width, self.scrolled.GetSize()[0])
        # Use the client size, since the total window size does not include the
        # window manager-added border (at least on Linux, wx 3.0, GTK 2, etc.)
        # when the window is created, leading to the wrong size later.
        self.SetClientSize((width, borders + machine_height * show_machines))
        self.Layout()
        cur_x, cur_y = self.GetSize()
        y_other = cur_y - machine_height * show_machines
        min_y = y_other + machine_height
        max_y = y_other + machine_height * self.scrolled.num_machines
        self.SetSizeHints(cur_x, min_y, -1, max_y)

    def update_machine_list(self):
        sizer = self.GetSizer()
        info = self.extractor.strip_property_value(self.extractor.target_info())
        if self.old_info == info:
            return
        self.old_info = copy.deepcopy(info)
        self.Freeze()
        if self.scrolled:
            # remove and destroy old machine list window
            sizer.Detach(self.scrolled)
            self.scrolled.Destroy()
        self.scrolled = machine_window(self, info)
        sizer.Add(self.scrolled, proportion = 0, flag = wx.EXPAND)
        self.update_size()
        self.Thaw()

    def initial_run_state(self):
        if simics.SIM_simics_is_running():
            return "Forwarding"
        else:
            new_state = "Stopped"
            if queue_exists():
                new_state += "_Fwd"
            return new_state

    def update_run_state(self, new_state):
        if new_state == self.run_state:
            return
        self.run_state = new_state
        self.forwarding = "Forwarding" in self.run_state
        self.update_toolbar()

    def update_toolbar(self):
        assert_simics_lock()

        # On Windows with Aero theme it is not possible to have a
        # disabled button pressed down (at least not with the current
        # wxPython).
        may_fwd = "_Fwd" in self.run_state
        running = self.forwarding
        stopped_may_run = "Stopped_Fwd" in self.run_state
        #
        self.toolbar.ToggleTool(ID_TOOL_RUN, self.forwarding)
        self.toolbar.EnableTool(ID_TOOL_RUN,
                                may_fwd or self.forwarding)
        #
        self.toolbar.ToggleTool(ID_TOOL_STOP, not running)
        self.toolbar.EnableTool(ID_TOOL_STOP,
                                running or stopped_may_run)

    def update_title(self):
        if self.forwarding:
            self.SetTitle(self.title + " : " + "Running")
        else:
            self.SetTitle(self.title)

    def run_state_changed(self, obj, new_state):
        stopped = "Stopped" in new_state
        self.update_run_state(new_state)
        self.toolbar.EnableTool(ID_TOOL_NEW, stopped)
        self.toolbar.EnableTool(ID_TOOL_OPEN, stopped)
        self.toolbar.EnableTool(ID_TOOL_SAVE, stopped)
        self.filemenu.Enable(ID_MENU_NEW_EMPTY, stopped)
        self.filemenu.Enable(ID_MENU_NEW, stopped)
        self.filemenu.Enable(ID_MENU_OPEN, stopped)
        self.filemenu.Enable(ID_MENU_SAVE, stopped)

    def sim_loaded(self, obj):
        if not self.configuration_loaded and queue_exists():
            self.configuration_loaded = True
            self.toolbar.EnableTool(ID_TOOL_SAVE, True)
            self.filemenu.Enable(ID_MENU_SAVE, True)

    def restart_ok(self, text):
        with no_simics_lock():
            dlg = wx.MessageDialog(
                self,
                ('Simics has to be restarted to %s. ' % text)
                + 'The current session will be lost. Continue?',
                'Restart Simics?',
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
            ok = dlg.ShowModal() == wx.ID_YES
        return ok

    def new_session(self, event, filename = None):
        with simics_lock():
            if (configuration_exists() and
                not self.restart_ok('start a new session')):
                return
            if os.path.isdir('targets'):
                # in a project
                defaultdir = os.path.abspath('targets')
            else:
                defaultdir = '.'
        if not filename:
            dlg = wx.FileDialog(self, 'Select start script',
                                wildcard = ('Simics scripts (*.simics)|*.simics'
                                            '|All files (' + all_glob() + ')|'
                                            + all_glob()),
                                style = wx.FD_OPEN,
                                defaultDir = abspath(defaultdir))
            if dlg.ShowModal() != wx.ID_OK:
                return
            filename = dlg.GetPath()

        with simics_lock():
            restart_simics(filename)

    def load_target(self, event):
        with simics_lock():
            if (configuration_exists() and
                not self.restart_ok('start from a new target')):
                return
            targets = list(sim_params.get_target_list().keys())
        dlg = wx.SingleChoiceDialog(self,
                                    'Target Selection',
                                    'Select target to load into a new session',
                                    targets)
        if dlg.ShowModal() == wx.ID_OK and dlg.GetSelection() >= 0:
            target = targets[dlg.GetSelection()]
            with simics_lock():
                restart_simics(target)

    def open_checkpoint(self, event):
        with simics_lock():
            if (configuration_exists() and
                not self.restart_ok('start from a new checkpoint')):
                return
        filename = fsel.select_file(
            self, 'Select checkpoint',
            self.default_checkpoint_dir,
            filters=[fsel.Filter_union([fsel.Filter_checkpoint(),
                                        fsel.Filter_suffix(".conf"),
                                        fsel.Filter_suffix(".ckpt")],
                                       "Simics checkpoints"),
                     fsel.Filter_all()],
            image_path = image_dirs())
        if filename == None:
            return

        with simics_lock():
            restart_simics(filename)

    def save_checkpoint(self, event):
        filename = fsel.select_file(self, 'Save checkpoint',
                                    self.default_checkpoint_dir,
                                    save_name = 'Untitled.ckpt',
                                    allow_overwrite = False,
                                    image_path = image_dirs())
        if filename == None:
            return

        self.default_checkpoint_dir = abspath(os.path.dirname(filename))
        with simics_lock():
            try:
                simics.SIM_write_configuration_to_file(filename, 0)
            except Exception as ex:
                display_error(self,
                              'Failed saving checkpoint "%(file)s":\n\n'
                              '%(msg)s'
                              % {'file' : filename, 'msg' : ex})

    def toolbar_stop(self, event):
        simics.SIM_thread_safe_callback(
            lambda x: simics.VT_user_interrupt(x, 0), None)

    def toolbar_run(self, event):
        if not self.forwarding:
            simics.SIM_thread_safe_callback(quiet_start_simulation, None)

    def show_status_time(self, force):
        # This function may be called both when the Simics lock is taken ,e.g.,
        # while showing a dialog window with the lock taken, and when the lock
        # not taken. We therefore need to check whether the lock is already
        # taken and only take it if it is not.
        #
        # An alternative solution would be to always release the Simics lock
        # when doing something that returns control to the wxPython event loop,
        # e.g., showing a dialog window.
        def time_cmp(now, last):
            return now > last

        take_lock = get_simics_lock_count() == 0
        if take_lock:
            acquire_simics_lock()

        try:
            cpu = first_cycle_obj()
            ptime = simics.SIM_time(cpu) if cpu else 0.0
            if force or time_cmp(ptime, self.ptime):
                self.ptime = ptime
                status = time_to_string(ptime) + ' (virtual time)'
                self.SetStatusText(status, 1)
        finally:
            if take_lock:
                release_simics_lock()

    def show_status_time_cb(self, force):
        self.show_status_time(force)
        self.set_status_timer_state(True)

    def empty_session(self, event):
        with simics_lock():
            if (configuration_exists() and not self.restart_ok(
                'close the current session and start a new')):
                return
            restart_simics()

    def on_close(self, event):
        self.set_status_timer_state(False)

    def menu_window(self, menu_id, window_name, cpu = False):
        if cpu:
            menu_cb = lambda event: win_main.open_window(
                window_name, obj = call_with_simics_lock(cli.current_cpu_obj))
        else:
            menu_cb = lambda event: win_main.open_window(window_name)
        self.Bind(wx.EVT_MENU, menu_cb, None, menu_id)

cmd_info = win_main.command_info('win-control',
                                 # This text is inserted into a full sentence
                                 # in win_main.py, hence the strange wording.
                                 'legacy GUI control window. This command and'
                                 ' the corresponding view will be removed once'
                                 ' the standalone Simics GUI has been'
                                 ' released. The legacy GUI in Simics 7 only'
                                 ' consists of target consoles and the control')
win_main.register_win_type(False, control_window, cmd_info)
