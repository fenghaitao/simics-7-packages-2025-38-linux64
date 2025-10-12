# © 2016 Intel Corporation
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
from . import console_util
from .win_utils import *
import simics

# Dialog that displays info or status of a console.
class Info_status_dialog(wx.Dialog):
    # info_status should be the output of either the info or status commands.
    def __init__(self, parent, title, console, info_status):
        wx.Dialog.__init__(self, parent, title = title)

        # Border between grid bag cells.
        border = 2
        # Text style used by StaticText header widgets.
        self.header_style = wx.ALIGN_LEFT
        # Text style used by markable TextCtrl widgets.
        self.data_style = (wx.TE_RIGHT | wx.TE_READONLY
                           | wx.TE_NOHIDESEL | wx.BORDER_NONE)

        sizer = wx.GridBagSizer(border, border)
        # Sizer flags.
        flags = wx.EXPAND | wx.LEFT | wx.RIGHT

        # Display console name at the top.
        row = 0
        sizer.Add(self.header("Console", True), (row, 0),
                  flag = flags | wx.ALIGN_LEFT, border = border)
        sizer.Add(self.data(console.name), (row, 1),
                  flag = flags | wx.ALIGN_LEFT, border = border)

        # Then some empty space.
        row += 1
        empty = wx.StaticText(self, wx.ID_ANY, "")
        sizer.Add(empty, (row, 0), wx.GBSpan(2, 2),
                  flag = flags, border = border)
        row += 2

        num_sections = len(info_status)

        # Display lines with data from info or status.
        # Each section of info/status is separated with empty space.
        for idx in range(num_sections):
            section = info_status[idx]
            header = section[0]
            entries = section[1]

            # Section often have a header, unless it is unique.
            if header != None:
                sizer.Add(self.header(header, True), (row, 0), wx.GBSpan(1, 2),
                          flag = flags | wx.ALIGN_LEFT, border = border)
                row += 1

            # Display lines for each entry in this section.
            for entry in entries:
                data = self.data(console_util.info_status_entry_str(entry[1]))

                # Make sure window will be reduced in case the text is short.
                font_size = data.GetTextExtent("M")
                data.SetMinSize(wx.Size(len(data.GetValue())
                                        * font_size[0], -1))
                sizer.Add(self.header(entry[0], False), (row, 0),
                          flag = flags | wx.ALIGN_LEFT, border = border)
                sizer.Add(data, (row, 1),
                          flag = flags | wx.ALIGN_LEFT, border = border)
                row += 1

            # Empty space between sections.
            if idx < num_sections - 1:
                empty = wx.StaticText(self, wx.ID_ANY, "")
                sizer.Add(empty, (row, 0), wx.GBSpan(2, 2),
                          flag = flags, border = border)
                row += 2

        # OK button at the bottom of the window.
        buttons = self.CreateButtonSizer(wx.OK)
        sizer.Add(buttons, (row, 0), wx.GBSpan(1, 2),
                  flag = (wx.ALIGN_CENTER_VERTICAL
                          | wx.ALIGN_CENTER_HORIZONTAL
                          | wx.ALL),
                  border = border)

        self.SetSizerAndFit(sizer)
        # Window should not be resizable.
        self.SetMaxSize(self.GetSize())
        self.Bind(wx.EVT_CLOSE, self.on_close)

    # Return control for header texts.
    def header(self, text, bold):
        ctrl = wx.StaticText(self, wx.ID_ANY, text, style = self.header_style)
        if bold:
            font = ctrl.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            ctrl.SetFont(font)
        return ctrl

    # Return control for markable data texts.
    def data(self, text):
        ctrl = wx.TextCtrl(self, wx.ID_ANY, text, style = self.data_style)
        ctrl.SetBackgroundColour(self.GetBackgroundColour())
        return ctrl

    # EVT_CLOSE callback
    def on_close(self, event):
        self.Destroy()

# Super class of text and graphics console windows, providing common menus,
# copy/paste and info/status functionality.
class Console_window:
    def __init__(self, parent, handle, console):
        # Parent window, i.e. console list
        self.parent = parent
        # Handle identifying this console in the console list
        self.handle = handle
        # Console class contained in this window.
        self.console = console

        # Set up Edit menu
        paste_id = wx.Window.NewControlId()
        self.copy_text_id = wx.Window.NewControlId()
        self.copy_screen_id = wx.Window.NewControlId()
        self.editmenu = wx.Menu()
        self.editmenu.Append(self.copy_text_id, "Copy")
        self.editmenu.Append(paste_id, "Paste")
        self.editmenu.AppendSeparator()
        self.editmenu.Append(self.copy_screen_id, "Copy screen")

        # Set up View menu
        info_id = wx.Window.NewControlId()
        status_id = wx.Window.NewControlId()
        self.viewmenu = wx.Menu()
        self.viewmenu.Append(info_id, "Info")
        self.viewmenu.Append(status_id, "Status")

        # Set up menu bar
        self.menubar = wx.MenuBar()
        self.menubar.Append(self.editmenu, "Edit")
        self.menubar.Append(self.viewmenu, "View")
        self.SetMenuBar(self.menubar)

        # Set up events
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_SHOW, self.on_show)
        self.Bind(wx.EVT_MENU, self.on_paste, None, paste_id)
        self.Bind(wx.EVT_MENU, self.on_copy_screen, None, self.copy_screen_id)
        self.Bind(wx.EVT_MENU, self.on_copy_text, None, self.copy_text_id)
        self.Bind(wx.EVT_MENU, self.on_info, None, info_id)
        self.Bind(wx.EVT_MENU, self.on_status, None, status_id)
        self.Bind(wx.EVT_ACTIVATE, self.on_activate)
        self.Bind(wx.EVT_SET_FOCUS, self.on_focus)
        self.Bind(wx.EVT_ICONIZE, self.on_iconize)

        # Initially disable Edit->Copy, until some text is marked.
        self.enable_copy_text(False)

        # Ignore activity indicator messages from backend?
        self.ignore_activity_indicator = False

    # Display an info or status dialog, given title and info/status data structure.
    def info_status_dialog(self, title, info_status):
        dialog = Info_status_dialog(self, title, self.console.backend,
                                    info_status)
        dialog.Show()

    # Display console info dialog
    def show_info_dialog(self):
        # Must wait until console is in a consistent state.
        with simics_lock():
            self.info_status_dialog("Info", self.console.get_info())

    # Display console status dialog
    def show_status_dialog(self):
        # Must wait until console is in a consistent state.
        with simics_lock():
            self.info_status_dialog("Status", self.console.get_status())

    # Menu item callbacks
    def on_info(self, event):
        self.show_info_dialog()

    def on_status(self, event):
        self.show_status_dialog()

    def on_copy_screen(self, event):
        self.console.copy_screen()

    def on_copy_text(self, event):
        self.console.mark_to_clipboard(False)

    def on_paste(self, event):
        self.paste_from_clipboard()

    # Event callbacks

    def on_activate(self, event):
        # Let console list update console activity indicator.
        if event.GetActive():
            self.parent.on_console_activate(self.handle)

    def on_focus(self, event):
        # Let console list update console activity indicator.
        self.parent.on_console_activate(self.handle)

    def on_iconize(self, event):
        # Let console list update console activity indicator.
        if not self.IsIconized():
            self.parent.on_console_activate(self.handle)
        self.console.set_visible(not self.IsIconized())

    def on_close(self, event):
        # Hide GUI window
        self.Hide()
        # Notify console backend that window is invisible, to e.g. turn off display events.
        self.console.set_visible(False)
        # Let console list update console activity indicator.
        self.parent.on_console_close(self.handle)

    # This can be both show and hide.
    def on_show(self, event):
        # Notify console backend about window visibility.
        self.console.set_visible(event.IsShown())
        self.update_window_size()
        event.Skip()

    # Enable/disable Edit->Copy menu item.
    def enable_copy_text(self, enable):
        self.editmenu.Enable(self.copy_text_id, enable)

    # Paste from system clipboard, like in Windows.
    def paste_from_clipboard(self):
        self.console.paste_text(console_util.get_clipboard_string(False))

    # Paste text from primary selection, i.e. like middle click in X.
    def paste_from_primary(self):
        # Paste from primary selection if non-empty
        text = console_util.get_clipboard_string(True)
        if not text:
            text = console_util.get_clipboard_string(False)
        self.console.paste_text(text)

    # Return console icons.
    def console_icons(self, size):
        filenames = self.icon_filenames()
        return console_util.console_icons(
            {key: bitmap_path(filenames[key]) for key in filenames}, size)

    # Callback when some data has arrived to this console from the simulation.
    def on_new_console_data(self):
        # Let console list update activity indicator, unless console window already active.
        if (((not self.IsActive()) and (not self.HasFocus()))
            or self.IsIconized()):
            self.parent.on_console_data(self.handle)

    def set_icon(self, name):
        with simics_lock():
            image = wx.Image(bitmap_path(self.icon_filenames()[name]),
                             wx.BITMAP_TYPE_PNG)
            self.SetIcon(wx.Icon(image.ConvertToBitmap()))
