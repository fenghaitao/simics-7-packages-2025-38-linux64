#!/usr/bin/env python3

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
import sys, os, os.path
from pathlib import Path
from simicsutils.internal import is_checkpoint_bundle

def path_components(path):
    """The components of an (absolute) directory path, starting with
    the root."""

    # handle trailing slashes first
    (d, b) = os.path.split(path)
    if b == '':
        path = d

    comps = []
    while True:
        (dname, bname) = os.path.split(path)
        if dname == path:
            return [dname] + comps
        else:
            comps = [bname] + comps
            path = dname

def test_path_components():
    def expect(dir, expected_comps):
        pc = path_components(dir)
        if pc != expected_comps:
            raise Exception("path_components(%r): expected %r, got %r"
                            % (dir, expected_comps, pc))

    if sys.platform == 'win32':
        expect('c:\\', ['c:\\'])
        expect('c:\\alfa', ['c:\\', 'alfa'])
        expect('c:\\alfa\\', ['c:\\', 'alfa'])
        expect('c:\\alfa\\beta', ['c:\\', 'alfa', 'beta'])
        expect('c:\\alfa\\beta\\', ['c:\\', 'alfa', 'beta'])
    else:
        expect('/', ['/'])
        expect('/alfa', ['/', 'alfa'])
        expect('/alfa/', ['/', 'alfa'])
        expect('/alfa/beta', ['/', 'alfa', 'beta'])
        expect('/alfa/beta/', ['/', 'alfa', 'beta'])

test_path_components()

mswindows = (sys.platform == 'win32')
if mswindows:
    import win32file

def drive_letters():
    drives = win32file.GetLogicalDrives()
    return [chr(ord('A') + i) for i in range(26) if drives & (1 << i)]

class Item:
    def __init__(self, dir, name):
        self.dir = dir
        self.name = name
        full = os.path.join(dir, name)
        self.is_dir = os.path.isdir(full)
        self.is_bundle = is_checkpoint_bundle(Path(full))
        if mswindows:
            # hide system/hidden (but not root directories)
            self.hidden = (dir != ''
                           and (win32file.GetFileAttributes(full) & 6) != 0)
        else:
            self.hidden = False
    def openable_dir(self):
        return self.is_dir and not self.is_bundle
    def visible(self):
        return self.name[0] != '.' and not self.hidden
    def icon(self):
        if self.openable_dir():
            return "folder"
        elif self.is_bundle:
            return "checkpoint"
        else:
            return "doc"
    def sortkey(self):
        return (not self.openable_dir(), self.name.lower())


# A filter that accepts all files
class Filter_all:
    label = "All files"
    def accept(self, item):
        return True

# A filter that only accepts checkpoints
class Filter_checkpoint:
    label = "Simics checkpoints"
    def accept(self, item):
        return item.is_bundle

# A filter that only accepts files having a given suffix
class Filter_suffix:
    def __init__(self, suffix, label=None):
        self.suffix = suffix
        self.label = label
    def accept(self, item):
        return item.name.endswith(self.suffix)

# Filter including files in any of multiple filters
class Filter_union:
    def __init__(self, filters, label=None):
        self.filters = filters
        self.label = label
    def accept(self, item):
        return any(f.accept(item) for f in self.filters)

# Filter including files in all of multiple filters
class Filter_intersection:
    def __init__(self, filters, label=None):
        self.filters = filters
        self.label = label
    def accept(self, item):
        return all(f.accept(item) for f in self.filters)

def allowed_filename_char(c):
    if mswindows:
        return c not in ':/\\<>"|?*'
    else:
        return c != '/'

class File_selector(wx.Dialog):
    def __init__(self, parent, title, starting_dir, filters = [Filter_all()],
                 save_name=None, allow_overwrite=True,
                 image_path=['.'], select_suffix=False):
        wx.Dialog.__init__(self, parent, -1, title)

        self.dir = starting_dir
        self.filters = filters
        self.saving = save_name != None
        self.allow_overwrite = allow_overwrite

        self.topsizer = wx.BoxSizer(wx.VERTICAL)

        self.choice = wx.Choice(self, wx.ID_ANY)

        self.hsizer_left = wx.BoxSizer(wx.HORIZONTAL)
        self.hsizer_left.Add(self.choice, proportion=1,
                             flag = wx.RIGHT | wx.EXPAND)

        self.up_button = wx.Button(self, wx.ID_ANY, "Up")
        self.Bind(wx.EVT_BUTTON, self.up_pressed, self.up_button)
        self.hsizer_left.Add(self.up_button, proportion=0,
                             flag=wx.LEFT, border=16)

        self.topsizer.Add(self.hsizer_left, proportion = 0,
                          flag = wx.ALL | wx.EXPAND, border = 16)

        self.Bind(wx.EVT_CHOICE, self.dir_selected, self.choice)

        st = (wx.LC_REPORT | wx.LC_NO_HEADER | wx.LC_SINGLE_SEL | wx.VSCROLL
              | wx.BORDER_SIMPLE)
        self.lbox = wx.ListCtrl(self, -1, style=st)
        self.lbox.InsertColumn(0, '')
        self.lbox.SetColumnWidth(0, 24)
        self.lbox.InsertColumn(1, '')
        self.lbox.SetColumnWidth(1, 340)

        def lookup_image(f):
            for d in image_path:
                path = os.path.join(d, f)
                if os.path.exists(path):
                    return path

        self.icons = {}
        self.il = wx.ImageList(16, 16)
        for ic in ["folder", "doc", "checkpoint"]:
            img = wx.Bitmap(lookup_image("fsel-" + ic + ".png"),
                            wx.BITMAP_TYPE_PNG)
            self.icons[ic] = self.il.Add(img)

        self.lbox.SetImageList(self.il, wx.IMAGE_LIST_SMALL)

        sbar_width = wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X, self.lbox)
        self.lbox.SetMinSize((364 + sbar_width + 2, 320))

        self.topsizer.Add(self.lbox, proportion = 1,
                          flag = wx.LEFT | wx.RIGHT, border = 16)

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.item_selected, self.lbox)
        self.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.item_deselected, self.lbox)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.item_activated, self.lbox)

        self.cancel_button = wx.Button(self, wx.ID_CANCEL)
        self.confirm_button = wx.Button(self, wx.ID_OPEN)

        if self.saving:
            self.entry_label = wx.StaticText(self, wx.ID_ANY,
                                             label = "Save as:")
            self.entry_field = wx.TextCtrl(self, wx.ID_ANY)
            self.Bind(wx.EVT_TEXT, self.text_entry_changed, self.entry_field)
            self.entry_field.Bind(wx.EVT_CHAR, self.text_entry_key)
            self.entry_field.SetValue(save_name)

            self.entry_sizer = wx.BoxSizer(wx.HORIZONTAL)
            self.entry_sizer.Add(self.entry_label,
                                 flag = wx.ALIGN_CENTRE_VERTICAL)
            self.entry_sizer.Add(self.entry_field, proportion = 1,
                                 flag = wx.EXPAND | wx.LEFT,
                                 border = 16)
            self.topsizer.Add(self.entry_sizer,
                              flag = wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND,
                              border = 16)
            self.entry_field.SetFocus()
            if '.' in save_name and not select_suffix:
                endsel = save_name.rindex('.')
            else:
                endsel = len(save_name)
            self.entry_field.SetSelection(0, endsel)

        if self.saving:
            self.confirm_button.SetLabel("Save")
        self.confirm_button.SetDefault()
        self.Bind(wx.EVT_BUTTON, self.open_pressed, self.confirm_button)

        self.butsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.filter = filters[0]
        if self.saving:
            self.new_button = wx.Button(self, wx.ID_ANY,
                                        label = "New folder")
            self.Bind(wx.EVT_BUTTON, self.new_pressed, self.new_button)
            self.butsizer.Add(self.new_button, proportion = 0,
                              flag = wx.RIGHT, border = 16)
        else:
            if len(filters) > 1:
                self.filter_choice = wx.Choice(
                    self, wx.ID_ANY,
                    choices=[f.label for f in filters])
                self.filter_choice.SetSelection(0)
                self.Bind(wx.EVT_CHOICE, self.filter_changed,
                          self.filter_choice)
                self.butsizer.Add(self.filter_choice, proportion = 0,
                                  flag = wx.RIGHT, border = 16)

        self.butsizer.AddStretchSpacer()
        if mswindows:
            self.butsizer.Add(self.confirm_button, proportion = 0,
                              flag = wx.RIGHT, border = 16)
            self.butsizer.Add(self.cancel_button, proportion = 0)
        else:
            self.butsizer.Add(self.cancel_button, proportion = 0,
                              flag = wx.RIGHT, border = 16)
            self.butsizer.Add(self.confirm_button, proportion = 0)

        self.topsizer.Add(self.butsizer, proportion = 0,
                          flag = wx.ALL | wx.EXPAND, border = 16)

        self.enter_normal_dir(starting_dir)

        self.SetSizerAndFit(self.topsizer)
        if not self.saving:
            self.lbox.SetFocus()

    # file name entry field has been changed
    def text_entry_changed(self, e):
        val = self.entry_field.GetValue()
        self.confirm_button.Enable(val != "")

    # filter allowed keys in the file name entry field
    def text_entry_key(self, e):
        key = e.GetKeyCode()
        if (key < wx.WXK_SPACE or key == wx.WXK_DELETE or key > 255
            or allowed_filename_char(chr(key))):
            e.Skip()

    def error_message(self, msg):
        dlg = wx.MessageDialog(self, msg,
                               style = wx.CANCEL | wx.ICON_EXCLAMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def new_pressed(self, e):
        name = self.get_new_folder_name()
        if name != None:
            path = os.path.join(self.dir, name)
            if os.path.exists(path):
                self.already_exists(name)
            else:
                try:
                    os.mkdir(path)
                except OSError as exc:
                    self.error_message(f"Error creating directory:\n{exc}")
                    return
                self.enter_normal_dir(self.dir)

    def get_new_folder_name(self):
        dlg = wx.TextEntryDialog(self, "Create folder named:",
                                 "New folder",
                                 style = wx.OK | wx.CANCEL)
        ret = dlg.ShowModal()
        val = dlg.GetValue()
        if ret == wx.ID_OK:
            return val
        else:
            return None

    # when the user changes the filter
    def filter_changed(self, e):
        idx = e.GetInt()
        new_filter = self.filters[idx]
        if new_filter != self.filter:
            self.filter = new_filter
            self.redisplay_dir_contents()

    # when the user marks an item in the listbox
    def item_selected(self, e):
        idx = e.GetIndex()
        it = self.items[idx]
        self.current_item = it
        if self.saving:
            if it.openable_dir():
                pass
            else:
                self.entry_field.SetValue(it.name)
        else:
            self.confirm_button.Enable()

    # when the user unmarks an item (or marks another)
    def item_deselected(self, e):
        self.current_item = None
        if not self.saving:
            self.confirm_button.Disable()

    # when the user double-clicks on an item (which will already be marked)
    def item_activated(self, e):
        idx = e.GetIndex()
        self.activate(self.items[idx])

    def confirm_overwrite(self, name):
        # FIXME: make a dialogue box with proper button names (not yes/no)
        dlg = wx.MessageDialog(self,
                               '"%s" already exists. Replace it?' % name,
                               'Item exists',
                               wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        ret = dlg.ShowModal()
        dlg.Destroy()
        return ret == wx.ID_YES

    def already_exists(self, name):
        # FIXME: wxwidgets bug - we get an OK button instead of Cancel here
        dlg = wx.MessageDialog(
            self,
            '"%s" already exists and cannot be overwritten.' % name,
            'Item exists',
            wx.CANCEL | wx.ICON_EXCLAMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def end_dialogue(self, name):
        if not self.dir:
            return
        sel = os.path.join(self.dir, name)
        if self.saving:
            if os.path.exists(sel):
                if self.allow_overwrite:
                    if not self.confirm_overwrite(name):
                        return
                else:
                    self.already_exists(name)
                    return

        self.selection = sel
        self.EndModal(wx.ID_OPEN)

    # when the user presses the Open button
    def open_pressed(self, e):
        if self.saving:
            name = self.entry_field.GetValue()
            if name:
                self.end_dialogue(name)
        else:
            self.activate(self.current_item)

    def activate(self, it):
        if it:
            if it.openable_dir():
                self.enter_normal_dir(os.path.join(self.dir, it.name))
            else:
                if not self.saving:
                    self.end_dialogue(it.name)

    def enter_dir_idx(self, idx):
        if idx == len(self.dircomps):
            self.enter_drive_dir()   # only happens on Windows
        else:
            comps = self.dircomps[idx:]
            self.enter_normal_dir(os.path.join(*reversed(comps)))

    # when the user selects an entry in the directory drop-down menu
    def dir_selected(self, e):
        idx = e.GetInt()
        if idx > 0:
            self.enter_dir_idx(idx)

    # when the user presses the Up button
    def up_pressed(self, e):
        self.enter_dir_idx(1)

    # enter an ordinary directory
    def enter_normal_dir(self, path):
        self.dir = path
        self.dircomps = list(reversed(path_components(self.dir)))
        self.dir_contents = os.listdir(self.dir)
        self.enter_dir()

    # enter the synthetic "drive letter directory" on Windows
    def enter_drive_dir(self):
        self.dir = ''
        self.dircomps = []
        roots = [d + ":\\" for d in drive_letters()]
        self.dir_contents = [r for r in roots if os.path.isdir(r)]
        self.enter_dir()

    def enter_dir(self):
        self.choice.Clear()
        if True:
            for s in self.dircomps:
                self.choice.Append(s)
        else:
            # experimental
            for i in range(len(self.dircomps)):
                self.choice.Append(os.path.join(*reversed(self.dircomps[i:])))
        if mswindows:
            self.choice.Append('Computer')
        self.choice.SetSelection(0)
        self.up_button.Enable(self.choice.GetCount() > 1)
        self.redisplay_dir_contents()

    def redisplay_dir_contents(self):
        items = [Item(self.dir, f) for f in self.dir_contents]
        self.items = sorted((it for it in items
                             if it.visible() and (it.openable_dir()
                                                  or self.filter.accept(it))),
                            key = lambda it: it.sortkey())

        self.lbox.DeleteAllItems()
        for (i, it) in enumerate(self.items):
            self.lbox.InsertItem(i, '')
            self.lbox.SetItemImage(i, self.icons[it.icon()])
            self.lbox.SetItem(i, 1, it.name)
            if self.saving and not it.openable_dir():
                self.lbox.SetItemTextColour(i, '#666666')

        self.item_deselected(None)


def select_file(app, title, dir, **kw):
    """ Select a file to open or save. Return the full path name, or None if
    the operation was cancelled."""

    if not os.path.isdir(dir):
        # maybe the dir has gone away without the caller knowing it
        dir = os.path.abspath('.')      # more likely to be present
    dlg = File_selector(app, title, dir, **kw)
    val = dlg.ShowModal()
    dlg.Destroy()
    if val == wx.ID_CANCEL:
        return None
    else:
        return dlg.selection


def main():
    app = wx.App()
    frame = wx.Frame(None, wx.ID_ANY, "fsel demo")
    sizer = wx.BoxSizer(wx.HORIZONTAL)
    but1 = wx.Button(frame, wx.ID_ANY, "open")
    sizer.Add(but1)
    but2 = wx.Button(frame, wx.ID_ANY, "save")
    sizer.Add(but2)
    frame.SetSizerAndFit(sizer)

    def select_open(app, evt):
        f = select_file(app, "Please open vely nice file", os.getcwd(),
                        filters=[Filter_all(),
                                 Filter_checkpoint(),
                                 Filter_union([Filter_suffix(".c"),
                                               Filter_suffix(".h")],
                                              "C source")])
        print("selected file:", repr(f))

    def select_save(app, evt):
        f = select_file(app, "Saving something!", os.getcwd(),
                        save_name="Ohne Titel")
        print("selected file:", repr(f))

    frame.Bind(wx.EVT_BUTTON, lambda e: select_open(frame, e), but1)
    frame.Bind(wx.EVT_BUTTON, lambda e: select_save(frame, e), but2)
    frame.Show(True)
    app.MainLoop()

if __name__ == '__main__':
    main()
