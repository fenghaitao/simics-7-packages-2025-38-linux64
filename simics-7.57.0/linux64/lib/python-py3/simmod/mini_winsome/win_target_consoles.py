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
from simmod.mini_winsome.win_utils import *
import simmod.mini_winsome.win_main
import conf
import simmod.mini_winsome.appwindow
import simmod.mini_winsome.win_text_console
import simmod.mini_winsome.win_gfx_console
import simmod.mini_winsome.console_iface
import operator

# Window info used in the win_main data structures.
WIN_CLASS_NAME = "win-" + simmod.mini_winsome.console_iface.WINDOW_NAME
WIN_CLASS_DESC = "Simics target console"
# Size of icons displayed in the console list.
ICON_SIZE = wx.Size(24, 24)
# Per-console indices of icons stored in the console list.
ICONS_PER_CONSOLE = 4
ICON_IDX = {'closed-idle': 0,
            'closed-output': 1,
            'open-idle': 2,
            'open-output': 3}
assert len(ICON_IDX) == ICONS_PER_CONSOLE

def get_prefs_tt_font(win):
    assert_simics_lock()
    return font_name(get_default_tt_font(win))

# Return index for given console and icon type (key in ICON_IDX)
def icon_idx(console_num, icon):
    return ICONS_PER_CONSOLE * console_num + ICON_IDX[icon]

# Return ICON_IDX as list of [key, value], sorted on values.
def sorted_icon_idx():
    # Sort icons by values in ICON_IDX
    return sorted(list(ICON_IDX.items()), key = operator.itemgetter(1))

# Given current icon index for console, return index of opposite icon.
def icon_idx_flip(cur_idx, console_num, to_output):
    idx = cur_idx - ICONS_PER_CONSOLE * console_num
    if to_output:
        if idx == ICON_IDX['closed-idle']:
            return (True, cur_idx - idx + ICON_IDX['closed-output'])
        elif idx == ICON_IDX['open-idle']:
            return (True, cur_idx - idx + ICON_IDX['open-output'])
    else:
        if idx == ICON_IDX['closed-output']:
            return (True, cur_idx - idx + ICON_IDX['closed-idle'])
        elif idx == ICON_IDX['open-output']:
            return (True, cur_idx - idx + ICON_IDX['open-idle'])
    return (False, 0)

class Target_consoles_window(wx.Frame, simmod.mini_winsome.appwindow.appwindow):
    window_name = simmod.mini_winsome.console_iface.WINDOW_NAME
    def __init__(self, parent):
        assert_simics_lock()
        # Console list size is controlled, hence no maximise.
        wx.Frame.__init__(
            self, parent, wx.ID_ANY, title = "Target Consoles",
            style = (wx.DEFAULT_FRAME_STYLE & ~wx.MAXIMIZE_BOX))
        # Console list
        # We store console handles as list item "data"
        # Hence we can lookup: console list index -> console handle
        self.console_list = wx.ListView(
            self, style = (wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER))
        self.console_list.InsertColumn(0, "Consoles")

        # Parent window
        self.parent = parent
        # Lookup table: console handle -> console window
        self.consoles = {}
        # Lookup table: console handle -> console list index
        self.list_items = {}
        # We must own image list, the console list does not.
        self.console_images = wx.ImageList(ICON_SIZE.width, ICON_SIZE.height)

        # Console list events
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.item_activate)
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.item_right_click)
        self.Bind(wx.EVT_SIZE, self.on_resize)

        # Set up console context menu
        self.list_item_menu = wx.Menu()
        info_id = wx.Window.NewControlId()
        status_id = wx.Window.NewControlId()
        self.console_open_close_id = wx.Window.NewControlId()
        self.list_item_menu.Append(self.console_open_close_id, "Open")
        self.list_item_menu.AppendSeparator()
        self.list_item_menu.Append(info_id, "Info")
        self.list_item_menu.Append(status_id, "Status")

        # Context menu events
        self.Bind(wx.EVT_MENU, self.on_console_show_hide, None,
                  self.console_open_close_id)
        self.Bind(wx.EVT_MENU, self.on_console_info, None, info_id)
        self.Bind(wx.EVT_MENU, self.on_console_status, None, status_id)

        # Font setup. Need font size for setting console list size manually.
        default_font = font_from_name(get_prefs_tt_font(self))
        dc = wx.ScreenDC()
        dc.SetFont(default_font)
        (self.font_width, self.font_height) = dc.GetTextExtent('M')

        simmod.mini_winsome.appwindow.appwindow.__init__(self)

    # Callback from Winsome when a console has been opened.
    # Because we take the Simics lock during console initialisation,
    # we are guaranteed that wxPython will have no time to process the event
    # that leads to this callback until Simics has loaded the configuration.
    def configuration_loaded(self):
        # If only one console in the configuration, we should display it,
        # unless auto show has been turned off by explicitly setting visibility
        # on some console.
        if len(self.consoles) == 1:
            # Obtain unique console
            (handle, console) = list(self.consoles.items())[0]
            # User can have explicitly turned off visibility in the backend.
            if console.enable_auto_show:
                # No need for a console list when only one console.
                self.Hide()
                self.show_console(handle)

    # Show specified console window, which is already in the list
    def show_console(self, handle):
        console_window = self.lookup_console_win(handle)
        console = self.lookup_console(handle)
        backend = console.backend
        # Show console unless -no-win was used.
        with simics_lock():
            show = ((not (conf.sim.hide_console_windows
                         or console_window.IsShown()))
                    and (backend and hasattr(backend, 'iface')))
        if show:
            # This appears to be show the window in the expected way.
            console_window.ShowWithoutActivating()
            console_window.SetFocus()
            # Always reset to "idle" status when showing a window
            item = self.handle_to_item(handle)
            item.SetImage(icon_idx(item.GetId(), 'open-idle'))
            self.console_list.SetItem(item)
            console_window.set_icon('open-idle')

    # Sort console list in alphabetic order on item texts.
    def sort_console_list(self):
        item_indices = list(self.list_items.values())
        items = [self.console_list.GetItem(i) for i in item_indices]
        indices = list(ICON_IDX.values())
        # Obtain a list where each item is a list [console, icon1,...icon4]
        item_list = [[item] + [self.console_images.GetBitmap(
            ICONS_PER_CONSOLE * item.GetId() + i) for i in indices]
                     for item in items]
        # Sort list on text
        item_list.sort(key=lambda x: x[0].GetText())

        # Replace console items with new ordered list
        for new_id in range(len(item_list)):
            item = item_list[new_id][0]
            icons = item_list[new_id][1:]
            old_img_idx = item.GetImage() - ICONS_PER_CONSOLE * item.GetId()
            item.SetId(new_id)
            # Set new index into image list
            item.SetImage(ICONS_PER_CONSOLE * new_id + old_img_idx)
            for j in range(len(indices)):
                self.console_images.Replace(
                    ICONS_PER_CONSOLE * new_id + indices[j], icons[j])
            # Replace console item
            self.console_list.SetItem(item)
            # Update lookup table
            self.list_items[item.GetData()] = item.GetId()
        # Replace image list with new ordered list
        self.console_list.SetImageList(self.console_images, wx.IMAGE_LIST_SMALL)

    # Update console list window size, after the console list widget has changed
    def update_window_size(self):
        # Heuristic to obtain sensible column width
        self.console_list.SetColumnWidth(0, wx.LIST_AUTOSIZE)
        self.console_list.SetColumnWidth(
            0, self.console_list.GetColumnWidth(0) + 2 * self.font_width)

        # Heuristic for setting list size
        list_min_size = wx.Size(self.console_list.GetColumn(0).GetWidth(),
                                self.font_height * 3
                                * min(self.console_list.GetItemCount(), 2))
        list_size = wx.Size(self.console_list.GetColumn(0).GetWidth(),
                            self.font_height * 3
                            * self.console_list.GetItemCount())
        self.console_list.SetMinSize(list_min_size)
        self.console_list.SetSize(list_size)

        # Set window size from console list size
        self.SetSizer(None)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.console_list)
        self.SetSizerAndFit(sizer)
        self.Layout()

        # Heuristic for a sensible minimum window size
        min_size = wx.Size(self.console_list.GetColumn(0).GetWidth(),
                           self.font_height * 3
                           * min(self.console_list.GetItemCount(), 10))
        self.SetMinSize(min_size)

    # Add a new console to the list
    def add_console(self, title, handle, console_window):
        from simmod.mini_winsome.win_main import show_target_console_list

        # Create new list item
        item = wx.ListItem()
        item.SetId(self.console_list.GetItemCount())
        item.SetData(handle)
        item.SetText(title)
        item.SetColumn(0)
        font = self.GetFont()
        font.SetWeight(wx.FONTWEIGHT_LIGHT)
        item.SetFont(font)

        # A icons for this console to the image list
        with simics_lock():
            icons = console_window.console_icons(ICON_SIZE)
            for icon in sorted_icon_idx():
                self.console_images.Add(icons[icon[0]])
        # Initial status is always "idle"
        item.SetImage(icon_idx(self.console_list.GetItemCount(), 'closed-idle'))
        # Update lookup tables
        self.consoles[handle] = console_window
        self.list_items[handle] = self.console_list.GetItemCount()
        # Add new console to list
        self.console_list.InsertItem(item)
        self.console_list.SetImageList(self.console_images,
                                       wx.IMAGE_LIST_SMALL)
        # Make sure list is sorted
        self.sort_console_list()
        # Titles might be long
        self.update_window_size()
        with simics_lock():
            # Show console list by default unless --no-win was used.
            if (len(self.consoles) > 1
                and not conf.sim.hide_console_windows
                # Auto show unless explicitly turned off
                and not (show_target_console_list() is False)):
                self.ShowWithoutActivating()
        # Notify Winsome that one console opened.
        # This leads to a configuration_loaded call some time later.
        simmod.mini_winsome.win_main.console_open()

    # Update console list item text
    def set_console_list_text(self, handle, text):
        item_idx = self.list_items[handle]
        if self.console_list.GetItemText(item_idx) != text:
            self.console_list.SetItemText(item_idx, text)

    # Change console icon between "idle" and "output"
    def switch_console_icon(self, handle, new_data):
        item = self.handle_to_item(handle)
        (switch, img) = icon_idx_flip(item.GetImage(), item.GetId(), new_data)
        if switch:
            item.SetImage(img)
        self.console_list.SetItem(item)
        console_window = self.lookup_console_win(handle)
        if console_window.IsShown():
            if new_data:
                console_window.set_icon('open-output')
            else:
                console_window.set_icon('open-idle')
        else:
            if new_data:
                console_window.set_icon('closed-output')
            else:
                console_window.set_icon('closed-idle')

    ## Lookup functions

    # Return console window for given handle, or None.
    def lookup_console_win(self, handle):
        if handle in self.consoles:
            return self.consoles[handle]
        else:
            return None

    # Return console class for given handle, or None.
    def lookup_console(self, handle):
        console_window = self.lookup_console_win(handle)
        if console_window is not None:
            return console_window.console
        else:
            return None

    # Return console window from console list index, or None.
    def list_idx_to_console(self, idx):
        if idx >= 0:
            item = self.console_list.GetItem(idx)
            return self.lookup_console_win(item.GetData())
        else:
            return None

    # Return console list item from console handle.
    def handle_to_item(self, handle):
        item_idx = self.list_items[handle]
        return self.console_list.GetItem(item_idx)

    ## Console window callbacks

    # Called by console from Console_window super class when new data arrives
    # from backend.
    def on_console_data(self, handle):
        self.switch_console_icon(handle, True)
        con = self.lookup_console_win(handle)
        # If window is invisible, ignore further activity indicators
        if not con.IsShown():
            con.ignore_activity_indicator = True

    # Called by console from Console_window super class when console
    # window is activated.
    def on_console_activate(self, handle):
        self.switch_console_icon(handle, False)
        con = self.lookup_console_win(handle)
        con.ignore_activity_indicator = False

    # Called by console from Console_window when console window is closed.
    def on_console_close(self, handle):
        item = self.handle_to_item(handle)
        # Update console list icon
        item.SetImage(icon_idx(item.GetId(), 'closed-idle'))
        self.console_list.SetItem(item)

    ## Backend callbacks

    # text_console_frontend.start
    def open_text_console(self, backend, handle):
        from simmod.mini_winsome.win_text_console import Text_console_window
        # Query backend for initial title.
        with simics_lock():
            if backend and hasattr(backend, 'name'):
                title = backend.name
            else:
                title = ""

        # Instantiate console window.
        console_window = Text_console_window(
            self, backend, handle, title)
        # Display console in list.
        self.add_console(title, handle, console_window)
        if backend and hasattr(backend, 'iface'):
            backend.iface.gui_console_backend.start(console_window.console)

    # gfx_console_frontend.start
    def open_gfx_console(self, backend, handle):
        from simmod.mini_winsome.win_gfx_console import Gfx_console_window
        # Query backend for initial title.
        with simics_lock():
            if backend and hasattr(backend, 'name'):
                title = backend.name
            else:
                title = ""

        # Instantiate console window.
        console_window = Gfx_console_window(self, backend, handle, title)
        # Display console in list.
        self.add_console(title, handle, console_window)
        if backend and hasattr(backend, 'iface'):
            backend.iface.gui_console_backend.start(console_window.console)

    # text_console_frontend.stop and gfx_console_frontend.stop
    def close_console(self, handle):
        # Look up console window
        console_window = self.lookup_console_win(handle)
        assert console_window is not None
        console = self.lookup_console(handle)
        assert console is not None
        # Hide window
        console_window.Hide()
        console_window.Destroy()

    # text_console_frontend.set_title and gfx_console_frontend.set_title
    def set_console_title(self, handle, short_title, long_title):
        # Update title
        self.set_console_list_text(handle, short_title)
        # List should be alphabetic on item text
        self.sort_console_list()
        # Titles might be long
        self.update_window_size()
        # Set console window title
        console_window = self.lookup_console_win(handle)
        assert console_window is not None
        console_window.SetTitle(long_title)

    # text_console_frontend.set_visible and gfx_console_frontend.set_visible
    def set_console_visible(self, handle, visible):
        console_window = self.lookup_console_win(handle)
        assert console_window is not None
        # Either this call arises by setting an attribute on the backend object,
        # or because the GUI called the backend upon a window show/hide.
        if not visible:
            # If this call comes from an initial visibility setting in the
            # backend, we must turn off automatic opening on startup.
            console_window.enable_auto_show = False
            if console_window.IsShown():
                # This will trigger on_console_close via events
                console_window.Close()
        else:
            self.show_console(handle)

    ## Context menu callbacks

    def on_console_show_hide(self, event):
        console_window = self.list_idx_to_console(
            self.console_list.GetFirstSelected())
        if console_window is not None:
            if console_window.IsShown():
                # This will trigger on_console_close via events
                console_window.Close()
            else:
                item = self.console_list.GetItem(
                    self.console_list.GetFirstSelected())
                self.show_console(item.GetData())

    # Show console info dialog
    def on_console_info(self, event):
        console_window = self.list_idx_to_console(
            self.console_list.GetFirstSelected())
        if console_window is not None:
            console_window.show_info_dialog()

    # Show console status dialog
    def on_console_status(self, event):
        console_window = self.list_idx_to_console(
            self.console_list.GetFirstSelected())
        if console_window is not None:
            console_window.show_status_dialog()

    ## Console list event callbacks

    # EVT_LIST_ITEM_ACTIVATED callback
    def item_activate(self, event):
        item = event.GetItem()
        console_window = self.lookup_console_win(item.GetData())
        assert console_window is not None
        if not console_window.IsShown():
            # Double-clicking a console opens it
            self.show_console(item.GetData())
            # And should put it at the top
            console_window.Raise()
            console_window.SetFocus()
        else:
            console_window.Close()

    # EVT_LIST_ITEM_RIGHT_CLICK callback
    def item_right_click(self, event):
        item = event.GetItem()
        # Even if we right click outside the list, we still get this event.
        if item.GetData():
            console_window = self.lookup_console_win(item.GetData())
            assert console_window is not None
            # Update context menu
            if console_window.IsShown():
                self.list_item_menu.SetLabel(
                    self.console_open_close_id, "Close")
            else:
                self.list_item_menu.SetLabel(
                    self.console_open_close_id, "Open")
            # Display context menu
            self.PopupMenu(self.list_item_menu, event.GetPoint())

    # EVT_SIZE callback
    def on_resize(self, event):
        # Resize console list when window is resized.
        self.console_list.SetMinSize(self.GetClientSize())
        event.Skip()

# Register console list in the Winsome system
from simmod.mini_winsome.win_main import command_info, register_win_type
cmd_info = command_info(WIN_CLASS_NAME, WIN_CLASS_DESC)
register_win_type(False, Target_consoles_window, cmd_info)
