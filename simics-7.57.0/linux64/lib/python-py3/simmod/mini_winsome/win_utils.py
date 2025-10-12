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

import os, sys, traceback
from threading import Event, Lock

import wx

import simics
import conf
from simicsutils.host import is_windows
import simmod.mini_winsome
from .win_main import get_main_win

# Notes on threading:
# * The GUI has its own thread
# * Always have the Simics lock when opening new windows to simplify
#   initialization.
# * Keep lock for complete operations to avoid Simics changes behind the
#   GUI-threads back.
# * Use the thread save hap callback defined in this file to get Simics events
# * Always use a finally clause to call release_simics_lock

_simics_api_gui  = Event()
_simics_api_main = Event()

def simics_lock_callback(arg):
    _simics_api_gui.set() # let the gui thread run
    _simics_api_main.wait()
    _simics_api_main.clear()

_lock_count = 0

def assert_simics_lock():
    if _lock_count == 0:
        print("[GUI] Error: Simics lock not held!")
        raise Exception("Lock error")

def assert_no_simics_lock():
    if _lock_count != 0:
        print("[GUI] Error: Simics lock held!")
        raise Exception("Lock error")

def inc_simics_lock():
    global _lock_count
    _lock_count += 1

def dec_simics_lock():
    global _lock_count
    _lock_count -= 1

def get_simics_lock_count():
    return _lock_count

def acquire_simics_lock():
    inc_simics_lock()
    if _lock_count > 1:
        print("[GUI] Info: recursive lock (new state %d)" % _lock_count, file=sys.stderr)
        traceback.print_stack(file = sys.stderr)
        return
    simics.SIM_thread_safe_callback(simics_lock_callback, None)
    _simics_api_gui.wait() # wait for the lock callback
    _simics_api_gui.clear()

def release_simics_lock():
    global _lock_count
    dec_simics_lock()
    if _lock_count > 0:
        print("[GUI] Info: recursive unlock (new state %d)" % _lock_count, file=sys.stderr)
        traceback.print_stack(file = sys.stderr)
        return
    elif _lock_count < 0:
        _lock_count = 0
        print("[GUI] Error: Simics lock count negative!")
        return
    _simics_api_main.set() # api back to main thread

class simics_lock:
    def __enter__(self):
        acquire_simics_lock()
        return None

    def __exit__(self, type, value, traceback):
        release_simics_lock()

class no_simics_lock:
    def __enter__(self):
        release_simics_lock()
        return None

    def __exit__(self, type, value, traceback):
        acquire_simics_lock()

def release_simics_lock_if_held():
    if not _lock_count:
        return False
    release_simics_lock()
    return True

def call_with_simics_lock(func, *args, **kw):
    '''Calls func(*args, **kw) with the Simics lock held. Returns its
    return value.'''
    if get_simics_lock_count() > 0:
        return func(*args, **kw)
    with simics_lock():
        return func(*args, **kw)

class Fifo:
    def __init__(self):
        self.elements = []
    def enqueue_unique(self, data):
        '''Enqueues data if different from the last element added.'''
        if not self.elements or self.elements[-1] != data:
            self.elements.append(data)
    def dequeue(self):
        '''Dequeues one element from the FIFO. Raises IndexError if
        empty.'''
        return self.elements.pop(0)
    def is_empty(self):
        '''True if the FIFO is empty.'''
        return not self.elements

def call_after_with_simics_lock(func, *args, **kw):
    '''Calls func() with wx.CallAfter(), holding the Simics lock.'''

    def _callback_with_simics_lock():
        # Lock may be held if when CallAfter calls are made; e.g.,
        # from a modal MessageDialog.
        call_with_simics_lock(func, *args, **kw)

    wx.CallAfter(_callback_with_simics_lock)

_pending_hap_lock = Lock()
_pending_haps = Fifo()

def _process_haps():
    while True:
        _pending_hap_lock.acquire()
        try:
            if _pending_haps.is_empty():
                return
            (func, args) = _pending_haps.dequeue()
        finally:
            _pending_hap_lock.release()
        try:
            func(*args)
        except:
            print("Exception in hap handler", file=sys.stderr)
            traceback.print_exc(file = sys.stderr)

def _hap_callback(func, *args):
    do_call = False
    _pending_hap_lock.acquire()
    try:
        do_call = _pending_haps.is_empty()
        _pending_haps.enqueue_unique((func, args))
    finally:
        _pending_hap_lock.release()
    if do_call:
        call_after_with_simics_lock(_process_haps)

def install_hap_callback(hap, func):
    assert_simics_lock()
    return simics.SIM_hap_add_callback(hap, _hap_callback, func)

def remove_hap_callback(hap, func):
    assert_simics_lock()
    simics.SIM_hap_delete_callback(hap, _hap_callback, func)

def bitmap_path_ignore_lock(file):
    """Returns the path for the specified bitmap.
    Only call this if running in the GUI thread."""
    for p in [os.path.join(conf.sim.simics_home, 'lib')] + list(
            conf.sim.module_searchpath):
        f = os.path.join(p, 'images', file)
        if os.path.exists(f):
            return f
    # lets hope this one is still there
    return os.path.join(conf.sim.simics_home, 'lib', 'images',
                        'gtk-missing-image.png')

def bitmap_path(file):
    """Returns the path for the specified bitmap."""
    assert_simics_lock()
    return bitmap_path_ignore_lock(file)

def get_bitmap(name):
    return wx.Image(bitmap_path(name),wx.BITMAP_TYPE_PNG).ConvertToBitmap()

def get_default_tt_font(win):
    if is_windows():
        face = "Consolas"
    else:
        face = "Monospace"
    return wx.Font(win.GetFont().GetPointSize(),
                   wx.FONTFAMILY_TELETYPE,
                   wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL,
                   faceName = face)

def font_from_name(name):
    info = [s.strip() for s in name.split(',')]
    face = info[0]
    style = wx.FONTSTYLE_ITALIC if 'italic' in info[1:] else wx.FONTSTYLE_NORMAL
    weight = wx.FONTWEIGHT_BOLD if 'bold' in info[1:] else wx.FONTWEIGHT_NORMAL
    points = int(info[-1])
    return wx.Font(points, wx.FONTFAMILY_DEFAULT, # wx.FONTFAMILY_TELETYPE,
                   style = style, weight = weight, faceName = face)

def font_name(font):
    name = font.GetFaceName()
    if font.GetStyle() in (wx.SLANT, wx.ITALIC):
        name += ', italic'
    if font.GetWeight() == wx.BOLD:
        name += ', bold'
    name += ', ' + str(font.GetPointSize())
    return name

__all__ = [
    "assert_simics_lock",
    "assert_no_simics_lock",
    "get_simics_lock_count",
    "acquire_simics_lock",
    "release_simics_lock",
    "simics_lock",
    "no_simics_lock",
    "release_simics_lock_if_held",
    "release_simics_lock_if_held",

    "install_hap_callback",
    "remove_hap_callback",

    "bitmap_path",
    "get_bitmap",

    "get_default_tt_font",
    "font_from_name",
    "font_name",
]
