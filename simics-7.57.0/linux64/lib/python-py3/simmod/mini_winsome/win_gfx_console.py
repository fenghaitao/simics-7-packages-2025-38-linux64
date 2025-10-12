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
import simmod.mini_winsome.win_main
import simmod.mini_winsome.keycodes
import threading
import sys
from simmod.mini_winsome.win_utils import *
import simmod.mini_winsome.console_util
import gfx_console_common
import simmod.mini_winsome.console_window
import simmod.mini_winsome.console_panel
from fractions import Fraction
import gfx_console_commands
import simics
import time
from simicsutils.internal import ensure_text
import conf

# Initial screen size.
# Backend changes these immediately.
DEFAULT_SIZE = wx.Size(640, 480)
DEFAULT_FONT_SIZE = wx.Size(7, 14)
DEFAULT_TEXT_SIZE = wx.Size(80, 25)
# Min and max window scale factors
MAX_SCALE = Fraction(4, 1)
MIN_SCALE = Fraction(1, 2)
# Dash definition for rectangle mark mode pen.
MARK_DASHES = [[5, 10, 10, 5], [10, 5, 5, 10]]
# Time-out for timer used to render rectangular mark in marching ants style.
MARCHING_ANT_MS = 500

# Class encapsulating the main Simics console GUI behaviour: a panel with
# scrollbars, handling the communication between frontend and backend, but
# it is not a top window with menus etc.
class Gfx_console(wx.ScrolledWindow, simmod.mini_winsome.console_panel.Console_panel):
    def __init__(self, parent, backend):
        with simics_lock():
            wx.ScrolledWindow.__init__(self, parent)
            # Top-level window.
            self.parent = parent
            # Winsome part of backend, a conf_object_t.
            self.winsome_backend = backend
            if backend and hasattr(backend, 'iface'):
                # Actual console backend conf_object_t.
                self.backend = simics.SIM_object_parent(self.winsome_backend)
                assert self.backend is not None
                assert self.backend.iface.gfx_console_backend is not None
                assert self.backend.iface.screenshot is not None
                assert self.backend.iface.gfx_break is not None
            else:
                self.backend = None

            # This panel contains another panel where the drawing is done
            # WANTS_CHARS necessary to obtain all key down events
            self.panel = wx.Panel(self, style = wx.WANTS_CHARS)

            # All events go to the inner panel.
            self.panel.Bind(wx.EVT_MOUSE_EVENTS, self.mouse_event)
            self.panel.Bind(wx.EVT_CHAR, self.char_input)
            self.panel.Bind(wx.EVT_KEY_DOWN, self.key_down)
            self.panel.Bind(wx.EVT_KEY_UP, self.key_up)
            self.panel.Bind(wx.EVT_PAINT, self.repaint)
            self.panel.Bind(wx.EVT_LEFT_DOWN, self.left_down)
            self.panel.Bind(wx.EVT_LEFT_UP, self.left_up)
            self.panel.Bind(wx.EVT_LEFT_DCLICK, self.left_dbl_click)
            self.panel.Bind(wx.EVT_MIDDLE_DOWN, self.middle)
            self.panel.Bind(wx.EVT_MOTION, self.mouse_motion)

            # Internal buffer with the same size as the backend.
            # Drawing is done on this, and it is then the source of the
            # rendering to self.panel (which may have different size depending
            # on scale and rotation)
            self.buffer = wx.Bitmap(DEFAULT_SIZE.width,
                                    DEFAULT_SIZE.height)
            # Corresponding dimmed buffer, used when simulation is stopped.
            self.dimmed_buffer = wx.Bitmap(DEFAULT_SIZE.width,
                                           DEFAULT_SIZE.height)
            # Clear buffers
            dc = wx.MemoryDC(self.buffer)
            dc.SetBackground(wx.Brush(wx.BLACK))
            dc.Clear()
            dc = wx.MemoryDC(self.dimmed_buffer)
            dc.Clear()

            # Avoid erase background events.
            self.panel.SetBackgroundStyle(wx.BG_STYLE_PAINT)
            # Initial frontend background colour.
            # Typically overwritten immediately by the backend on init.
            self.SetBackgroundColour(wx.BLACK)
            # Must catch this event when using WarpCursor, which we use
            # when grabbing the mouse.
            self.panel.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self.mouse_lost)

            # Should self.dimmed_buffer be used as rendering source instead
            # of self.buffer? (typically when simulation is stopped)
            self.dimmed = False
            # Is the mouse currently grabbed?
            self.grab_mode = False
            # Is the mouse grab being paused because the simulation is stopped?
            self.grab_mode_paused = False
            # Did we just receive a "mouse lost" event (Windows only)?
            # Used to avoid calling ReleaseMouse in that case.
            self.got_mouse_lost = False
            # Cursor to use when not in text mode and when cursor is visible
            # i.e. when not grabbing the mouse.
            self.cursor = self.GetCursor()
            # Is the current graphics mode a text mode (hence display text
            # cursor and allow mark etc)
            self.text_mode = False
            # Window scale factor, between MAX_SCALE and MIN_SCALE.
            # Used to compute window transform and for StretchBlit.
            self.scale = 1
            # Window rotation, multiply by pi/2 to get angle.
            # Used to compute window transform.
            self.rotation = 0
            # wx.GraphicsMatrix mapping self.buffer coordinates to
            # self.panel coordinates
            self.transform = None
            # self.transform inverse
            self.inv_transform = None
            # Text font size when in text mode, used to render mark etc.
            self.font_size = DEFAULT_FONT_SIZE
            # Size of screen in characters, when in text mode.
            self.text_size = DEFAULT_TEXT_SIZE
            # Text contents of screen, when in text mode.
            self.text = [[b' ' * self.text_size.width] * self.text_size.height]
            # On Windows the text mode pointer ("ibeam") might be all black,
            # hence invisible if the background is also black.
            # We provide our own pointer in that case.
            self.ibeam_img = wx.Image(bitmap_path("ibeam.png"))
            # wx.Cursor object to be used in text mode
            self.text_cursor = None
            # Condition variable which is flagged when there are no threaded
            # console events that are being processed. These events are
            # the ones posted by win_text_console.update_thread
            self.event_cond = threading.Condition()
            # Associated predicate to the condition variable.
            self.processing_events = False
            # Are we currently in rectangular (breakpoint) mark mode?
            self.gfx_mark_mode = False
            # wx.Pen used when drawing rectangular mark
            self.mark_pen = wx.Pen(wx.LIGHT_GREY, style = wx.PENSTYLE_USER_DASH)
            # Brush used when in rectangle mark mode.
            self.mark_brush = wx.Brush(wx.BLACK, wx.TRANSPARENT)
            # Current dash rotation for self.mark_pen
            self.mark_dash_num = 1
            # Timer used for animating the rectangular mark, marching ants style
            self.mark_timer = wx.Timer(self, wx.Window.NewControlId())
            self.Bind(wx.EVT_TIMER, self.marching_ants, self.mark_timer)
            # True for physical, false for symbolic keyboard mode.
            self.phys_kbd_mode = False
            # Grab mode detection
            self.grab_modifier = None
            self.grab_button = None
            self.grab_got_modifier = False
            # Preferences change notifier
            self.prefs_notifier = None
            simmod.mini_winsome.console_panel.Console_panel.__init__(self)

        self.set_size(DEFAULT_SIZE.width, DEFAULT_SIZE.height)

    def Destroy(self):
        super(wx.ScrolledWindow, self).Destroy()

    def is_text_mark_supported(self):
        return (self.text_mode and self.rotation == 0)

    def prefs_should_dim(self):
        try:
            return conf.prefs.iface.preference.get_preference_for_module_key(
                "graphcon", "dim-on-stop")
        except simics.SimExc_Attribute:
            return True

    def update_dimming(self):
        # Is dimming turned off via preferences?
        should_dim = self.prefs_should_dim()
        # Text marking cannot be used with the dimmed buffer
        self.dimmed = (not self.text_mode and not self.gfx_mark_mode
                       and should_dim)

    # Callback from Simics when simulation stops
    def simulation_stopped(self, obj, exception, error_string):
        # Immediately update dimmed buffer
        self.update_dimmed_buffer()
        self.update_dimming()
        # Temporarily exit grab mode
        if self.grab_mode:
            self.set_grab_mode(False)
            self.grab_mode_paused = True
        self.refresh_all()

    # Callback from Simics when simulation continues after a stop
    def continuation(self, obj):
        # Dimmed buffer is only used when paused
        self.dimmed = False
        # Continue with grab mode if was on before the stop
        if self.grab_mode_paused:
            self.set_grab_mode(True)
            self.grab_mode_paused = False
        self.refresh_all()

    # Update the dimmed buffer from the main buffer.
    # This operation is expensive.
    def update_dimmed_buffer(self):
        image = self.buffer.ConvertToImage()
        self.dimmed_buffer = wx.Bitmap(image.ConvertToGreyscale())

    # Call backend to do a screenshot to the given filename.
    def screenshot(self, filename):
        with simics_lock():
            if self.backend and hasattr(self.backend, 'iface'):
                return self.backend.iface.screenshot.save_png(filename)

    # Set physical/symbolic keyboard mode.
    def set_kbd_mode(self, phys_mode):
        self.phys_kbd_mode = phys_mode

    # Main update from backend.
    # Replace specified screen rectangle with new data.
    # Corresponding to gfx_console_frontend.set_contents.
    # Also indicates if we are in text mode.
    def set_contents(self, left, top, right, bottom, data, text_mode):
        width = right - left + 1
        height = bottom - top + 1

        dc = wx.MemoryDC(self.buffer)
        # Can only render from a Bitmap, hence we must copy input.
        bitmap = wx.Bitmap.FromRGBA(width, height)
        bitmap.CopyFromBuffer(data, wx.BitmapBufferFormat_RGB32)
        # Render into self.buffer
        dc.DrawBitmap(bitmap, left, top)

        # Refresh dirty rectangle only.
        self.refresh(wx.Rect(left, top, width, height))
        self.set_text_mode(text_mode)

        # Updating the dimmed buffer is expensive, so only do it when necessary.
        if self.parent.IsShown():
            self.update_dimmed_buffer()
        # Immediate paint event
        self.Update()

    def repaint(self, event):
        # Cannot use GraphicsContext functionality if we want to also support
        # text marking, since no method of inverse rendering.
        # Hence only support marking when not rotated.
        # Scaling is ok since we can use StretchBlit.
        if self.text_mode and self.rotation == 0:
            # Use double buffering on Windows
            dc = wx.AutoBufferedPaintDC(self.panel)
            src = wx.MemoryDC(self.buffer)
            # Render internal buffer to screen
            dc.StretchBlit(0, 0, self.panel.GetSize().GetWidth(),
                           self.panel.GetSize().GetHeight(),
                           src, 0, 0, self.buffer.GetSize().GetWidth(),
                           self.buffer.GetSize().GetHeight())
            # Use inverse render/blit to draw text mark.
            # We cannot re-draw characters as in the text console, since we
            # have no available font data.
            if self.has_mark():
                src = wx.MemoryDC(self.buffer)
                if self.rectangle_mark:
                    simmod.mini_winsome.console_util.draw_rect_mark(
                        dc, src, self.text_size, self.font_size,
                        self.mark_start, self.mark_stop,
                        self.max_coord, self.scale)
                else:
                    simmod.mini_winsome.console_util.draw_mark(
                        dc, src, self.text_size, self.font_size,
                        self.mark_start, self.mark_stop,
                        self.max_coord, self.scale)
            # Render graphics breakpoint rectangle
            if self.has_gfx_mark():
                # draw_gfx_mark expects a translated device context
                dc = wx.PaintDC(self.panel)
                gc = wx.GCDC(dc)
                context = gc.GetGraphicsContext()
                context.SetTransform(self.transform)
                self.draw_gfx_mark(context)
        else:
            # Use GraphicsContext functionality to easily obtain scale
            # and rotation via the generic transformation matrix.
            dc = wx.PaintDC(self.panel)
            gc = wx.GCDC(dc)
            context = gc.GetGraphicsContext()
            context.SetTransform(self.transform)
            if not self.dimmed:
                context.DrawBitmap(self.buffer, 0, 0,
                                   self.buffer.GetSize().GetWidth(),
                                   self.buffer.GetSize().GetHeight())
            else:
                context.DrawBitmap(self.dimmed_buffer, 0, 0,
                                   self.dimmed_buffer.GetSize().GetWidth(),
                                   self.dimmed_buffer.GetSize().GetHeight())
            if self.has_gfx_mark():
                self.draw_gfx_mark(context)

    ## Rotation/scale functions

    # Update window transform corresponding to the current rotation and scale.
    def update_transform(self):
        dc = wx.MemoryDC(self.buffer)
        context = wx.GraphicsContext.Create(dc)
        w = self.buffer.GetSize().GetWidth()
        h = self.buffer.GetSize().GetHeight()
        s = self.scale

        # Set corresponding rotation+scale matrix
        # We only use rotations where the matrix has integer entries.
        if self.rotation == 1:
            # pi/2
            self.transform = context.CreateMatrix(0, s, -s, 0, h * s, 0)
            self.inv_transform = context.CreateMatrix(0, s, -s, 0, h * s, 0)
        elif self.rotation == 2:
            # pi
            self.transform = context.CreateMatrix(-s, 0, 0, -s, w * s, h * s)
            self.inv_transform = context.CreateMatrix(
                -s, 0, 0, -s, w * s, h * s)
        elif self.rotation == 3:
            # 3pi/2
            self.transform = context.CreateMatrix(0, -s, s, 0, 0, w * s)
            self.inv_transform = context.CreateMatrix(0, -s, s, 0, 0, w * s)
        else:
            self.transform = context.CreateMatrix(s, 0, 0, s, 0, 0)
            self.inv_transform = context.CreateMatrix(s, 0, 0, s, 0, 0)
        self.inv_transform.Invert()

    # Set window scale
    def update_scale(self, scale):
        self.scale = scale
        self.clear_gfx_mark()
        # Resize window using new scale
        self.resize(self.buffer.GetSize().GetWidth(),
                    self.buffer.GetSize().GetHeight())

    # Set window rotation
    def update_rotation(self, rotation):
        self.rotation = rotation
        self.clear_gfx_mark()
        # Resize window using new rotation
        self.resize(self.buffer.GetSize().GetWidth(),
                    self.buffer.GetSize().GetHeight())

    ## Cursor functions

    # Change console cursor
    def set_cursor(self, cursor):
        # Only set cursor on the inner panel. Continue with normal cursor
        # on any scrollbars.
        self.panel.SetCursor(cursor)

    # Return the text cursor for this platform
    def get_text_cursor(self):
        if sys.platform.lower().startswith('win'):
            # Scale our bespoke ibeam to the correct font size
            img = self.ibeam_img.Scale(
                self.font_size.width, self.font_size.height)
            # Cursor hotspot is more or less in the middle.
            img.SetOption(wx.IMAGE_OPTION_CUR_HOTSPOT_X,
                          self.font_size.width // 2)
            img.SetOption(wx.IMAGE_OPTION_CUR_HOTSPOT_Y,
                          self.font_size.height // 2)
            return wx.Cursor(img)
        else:
            # On Linux it seems the system ibeam is fine.
            return wx.Cursor(wx.CURSOR_IBEAM)

    # Change cursor to the text mode cursor.
    def set_text_cursor(self):
        self.set_cursor(self.get_text_cursor())

    # Enable/disable mouse grab mode
    def set_grab_mode(self, active):
        self.grab_mode = active
        if active:
            # Target and host cursor will not be in sync.
            self.set_cursor(wx.Cursor(wx.CURSOR_BLANK))
            # Mouse must stay in this window for grab calculations to work.
            self.panel.CaptureMouse()
        else:
            if not self.got_mouse_lost:
                self.panel.ReleaseMouse()
            else:
                self.got_mouse_lost = False
            self.set_cursor(self.cursor)

    def set_grab_modifier(self, modifier):
        self.grab_modifier = simmod.mini_winsome.keycodes.convert_grab_modifier(modifier)
        self.grab_got_modifier = False

    def set_grab_button(self, button):
        self.grab_button = simmod.mini_winsome.keycodes.convert_grab_button(button)

    ## Text mode functions

    # Convert text into a format suitable for the clipboard
    def encode_clipboard_text(self, text):
        # Assume vga device has the cp437 characters loaded.
        return simmod.mini_winsome.console_util.ibm437_visible(text)

    # Read text mode related data from the backend.
    def update_text_data(self):
        if self.backend and hasattr(self.backend, 'iface'):
            # No need to lock here, since locking is done in the backend.
            data = self.backend.iface.gfx_console_backend.text_data()
            self.line_lengths = data[1]
            width = data[3]
            height = data[2]
            self.text_size = wx.Size(width, height)
            self.font_size = wx.Size(data[4], data[5])
            self.max_coord = wx.Size(width - 1, height - 1)
            self.text = [data[0][i * self.text_size.width :
                                 (i + 1) * self.text_size.width]
                         for i in range(self.text_size.height)]

    # Enter/leave text mode
    def set_text_mode(self, text_mode):
        self.text_mode = text_mode
        # Notify parent of mode, to facilitate menu updates
        self.parent.set_text_mode(text_mode)

        # Set correct cursor.
        # Breakpoint mode and mouse grab overrides text mode cursor.
        if not self.gfx_mark_mode:
            if self.text_mode:
                if not self.grab_mode:
                    self.set_text_cursor()
            else:
                if not self.grab_mode:
                    self.set_cursor(self.cursor)
                self.remove_mark()

    ## Window size functions

    # Set new size of buffers and windows. Given size should be un-translated,
    # i.e. size coming from backend.
    def set_size(self, width, height):
        # Update internal buffers
        image = self.buffer.ConvertToImage()
        image = image.Scale(width, height)
        self.buffer = wx.Bitmap(image)
        self.update_dimmed_buffer()
        # Transform depends on self.buffer size
        self.update_transform()
        # Update on-screen window size
        (w, h) = self.transform.TransformDistance(width, height)
        size = wx.Size(int(abs(w)), int(abs(h)))
        # Update widgets to new sizes
        self.update_window_size(size)

    # Update size of widgets after internal buffer sizes have been set
    def update_window_size(self, size):
        # Update inner panel
        self.panel.SetMaxSize(size)
        self.panel.SetMinSize(size)
        self.panel.SetSize(size)
        # Update outer panel
        self.SetSizer(None)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.panel, flag = wx.ALL, border = 0)
        self.SetSizerAndFit(sizer)
        self.refresh_all()
        # Will show scrollbars on demand
        self.SetScrollbars(1, 1, size.width, size.height)

    # gfx_console_frontend.set_size
    def resize(self, width, height):
        with simics_lock():
            self.set_size(width, height)
            self.parent.update_window_size()

    ## Rectangle/breakpoint mark functions

    # Do we have a valid breakpoint mark?
    def has_gfx_mark(self):
        return (self.gfx_mark_mode and self.drag_start is not None
                and self.drag_stop is not None)

    # Return currently marked graphics breakpoint rectangle in internal
    # buffer coordinates.
    def gfx_mark_rect(self):
        assert self.has_gfx_mark()
        # self.drag_start and self.drag_stop are in on-screen coordinates,
        # hence convert back to buffer coordinates
        return simmod.mini_winsome.console_util.transform_rect(
            self.inv_transform,
            self.drag_start.x, self.drag_start.y,
            self.drag_stop.x, self.drag_stop.y)

    # Rectangle mark timer callback
    def marching_ants(self, event):
        # Update selected pen dashes, resulting in "marching ants" animation
        self.mark_dash_num = (self.mark_dash_num + 1) % len(MARK_DASHES)
        if self.has_gfx_mark():
            self.refresh_all()

    # Draw the graphics breakpoint rectangle on the given device context,
    # which must be an internal buffer, not an on-screen translated context.
    def draw_gfx_mark(self, dc):
        assert self.has_gfx_mark()
        # Set rectnagle bruch and pen
        dc.SetBrush(self.mark_brush)
        self.mark_pen.SetDashes(MARK_DASHES[self.mark_dash_num])
        dc.SetPen(self.mark_pen)
        # Obtain and draw rectangle in un-translated coordinates
        rect = self.gfx_mark_rect()
        dc.DrawRectangle(rect.x, rect.y, rect.width, rect.height)

    # Copy contents of selected rectangle to the clipboard.
    def copy_gfx_mark(self):
        assert self.has_gfx_mark()
        # Copy from internal buffer, not on-screen data, for consistency.
        context = wx.MemoryDC(self.buffer)
        rect = self.gfx_mark_rect()
        # Must make a copy of the data since the clipboard stores a reference.
        bitmap = wx.Bitmap(rect.width, rect.height)
        memory = wx.MemoryDC(bitmap)
        memory.Blit(0, 0, rect.width, rect.height, context, rect.x, rect.y)
        simmod.mini_winsome.console_util.set_clipboard_bitmap(bitmap)

    # Remove selected rectangle
    def clear_gfx_mark(self):
        self.drag_start = None
        self.drag_stop = None
        self.parent.on_gfx_mark(self.has_gfx_mark())

    # Enter/exit graphics breakpoint mark mode.
    def set_gfx_mark_mode(self, enable):
        self.clear_gfx_mark()
        self.gfx_mark_mode = enable
        if self.gfx_mark_mode:
            self.mark_timer.Start(MARCHING_ANT_MS)
            self.set_cursor(wx.Cursor(wx.CURSOR_CROSS))
        else:
            self.mark_timer.Stop()
            # Go back to text mode if we were there earlier.
            self.set_text_mode(self.text_mode)
        self.refresh_all()

    ## Refresh window functions

    # Refresh a rectangle given in un-translated pixel coordinates,
    # i.e. self.buffer coordinates.
    def refresh(self, rect):
        # Convert to on-screen coordinates
        self.panel.RefreshRect(
            simmod.mini_winsome.console_util.transform_rect(
                self.transform, rect.GetLeft(), rect.GetTop(),
                rect.GetRight(), rect.GetBottom()), False)

    # Complete screen refresh
    def refresh_all(self):
        self.panel.Refresh(False)

    # Request screen update from backend
    def refresh_screen(self):
        if self.backend and hasattr(self.backend, 'iface'):
            with simics_lock():
                self.backend.iface.gfx_console_backend.request_refresh()
            self.refresh_all()

    ## Functions required by console_panel super class

    def get_text_size(self):
        return self.text_size

    def text_to_pixel(self, size):
        return simmod.mini_winsome.console_util.text_to_pixel(
            size, self.font_size.width, self.font_size.height)

    def pixel_to_text(self, pos):
        return simmod.mini_winsome.console_util.pixel_to_text(
            pos, self.font_size.width * self.scale,
            self.font_size.height * self.scale)

    def get_char(self, pos):
        return ensure_text(bytes((self.text[pos.y][pos.x],)))

    def line_length(self, line):
        return self.line_lengths[line]

    def line_wrap(self, line):
        # Heuristic: consider all full length lines to be wrapping
        return self.line_length(line) == self.text_size.width

    def get_line_mark_str(self, start, stop):
        if start.y < stop.y:
            line_len = self.line_length(start.y)
            substr = self.encode_clipboard_text(
                self.text[start.y][start.x : start.x + line_len])
            if not self.line_wrap(start.y):
                substr += "\n"
            for y in range(start.y + 1, stop.y):
                line_len = self.line_length(y)
                substr += self.encode_clipboard_text(self.text[y][: line_len])
                if not self.line_wrap(y):
                    substr += "\n"
            line_len = self.line_length(stop.y)
            substr += self.encode_clipboard_text(
                self.text[stop.y][: min(stop.x + 1, line_len)])
            if stop.x + 1 > line_len:
                substr += "\n"
        else:
            line_len = self.line_length(stop.y)
            substr = self.encode_clipboard_text(
                self.text[start.y][start.x : min(stop.x + 1, line_len)])
            if stop.x + 1 > line_len:
                substr += "\n"
        return substr

    def get_rect_mark_str(self, start, stop):
        return "\n".join(self.encode_clipboard_text(
            self.text[y][start.x : stop.x + 1])
                         for y in range(start.y, stop.y))

    def refresh_text_rect(self, rect):
        # Convert character positions to pixel coordinates
        start = self.text_to_pixel(wx.Size(rect.x, rect.y))
        size = self.text_to_pixel(wx.Size(rect.width, rect.height))
        self.refresh(wx.Rect(start.x, start.y,
                             start.x + size.width, start.y + size.height))

    ## Mouse event callbacks

    # EVT_MOUSE_LOST callback
    def mouse_lost(self, event):
        self.got_mouse_lost = True
        # Force exit grab mode in backend
        simics.SIM_thread_safe_callback(self.simics_notify_grab_keys, [])

    # EVT_LEFT_DOWN callback
    def left_down(self, event):
        if self.gfx_mark_mode:
            dc = wx.ClientDC(self.panel)
            self.drag_start = event.GetLogicalPosition(dc)
            self.drag_stop = None
            self.refresh_all()
            self.parent.on_gfx_mark(self.has_gfx_mark())
        elif self.is_text_mark_supported():
            # Read latest text data from backend.
            with simics_lock():
                self.update_text_data()
            dc = wx.ClientDC(self.panel)
            self.on_left_down(event, dc)
        # Make sure we receive key events
        event.Skip()

    # EVT_LEFT_UP callback
    def left_up(self, event):
        if self.gfx_mark_mode:
            self.refresh_all()
            self.parent.on_gfx_mark(self.has_gfx_mark())
        elif self.text_mode and self.is_text_mark_supported():
            with simics_lock():
                self.update_text_data()
            dc = wx.ClientDC(self.panel)
            self.on_left_up(event, dc)
        # Make sure we receive key events
        event.Skip()

    # EVT_LEFT_DCLICK callback
    def left_dbl_click(self, event):
        if self.text_mode and self.is_text_mark_supported():
            with simics_lock():
                self.update_text_data()
            dc = wx.ClientDC(self.panel)
            self.on_left_dbl_click(event, dc)
        event.Skip()

    # EVT_MOUSE_MOTION callback
    def mouse_motion(self, event):
        if (self.gfx_mark_mode and event.Dragging() and event.LeftIsDown()
            and self.drag_started()):
            dc = wx.ClientDC(self.panel)
            self.drag_stop = event.GetLogicalPosition(dc)
            self.refresh_all()
            self.parent.on_gfx_mark(self.has_gfx_mark())
        elif self.is_text_mark_supported():
            with simics_lock():
                self.update_text_data()
            dc = wx.ClientDC(self.panel)
            self.on_mouse_motion(event, dc)
        # Make sure we receive key events
        event.Skip()

    # EVT_MIDDLE_DOWN callback
    def middle(self, event):
        self.parent.paste_from_primary()
        event.Skip()

    # Send mouse event to Simics. Must be run in the Simics thread.
    def mouse_to_simics(self, args):
        if (self.backend and hasattr(self.backend, 'iface')
            and simics.SIM_simics_is_running()):
            self.backend.iface.gfx_console_backend.mouse_event(*args)

    def simics_notify_grab_keys(self, args):
        if self.backend and hasattr(self.backend, 'iface'):
            self.backend.iface.gfx_console_backend.got_grab_keys()

    # EVT_MOUSE_EVENTS callback
    def mouse_event(self, event):
        if self.grab_got_modifier and event.ButtonDown(self.grab_button):
            simics.SIM_thread_safe_callback(self.simics_notify_grab_keys, [])

        # Convert to gfx_console_mouse_button_t
        buttons = (
            (0, simics.Gfx_Console_Mouse_Button_Left)[event.LeftIsDown()]
            | (0, simics.Gfx_Console_Mouse_Button_Right)[event.RightIsDown()]
            | (0, simics.Gfx_Console_Mouse_Button_Middle)[event.MiddleIsDown()]
        )
        if event.GetWheelRotation() != 0:
            wheel = event.GetWheelRotation() // event.GetWheelDelta()
        else:
            wheel = 0
        # Convert mouse coordinates to usual coordinate system
        (x, y) = self.inv_transform.TransformPoint(event.GetX(), event.GetY())
        if (x < 0):
            x = 0
        elif (x > self.buffer.GetSize().GetWidth()):
            x = self.buffer.GetSize().GetWidth()
        if (y < 0):
            y = 0
        elif (y > self.buffer.GetSize().GetHeight()):
            y = self.buffer.GetSize().GetHeight()
        # Send mouse events to backend
        simics.SIM_thread_safe_callback(
            self.mouse_to_simics, (int(x), int(y), wheel, buttons))
        # Needed to also receive keyboard events
        event.Skip()

    ## Functions required by console_window super class

    # Used by info dialog
    def get_info(self):
        return gfx_console_commands.get_info(self.backend)

    # Used by status dialog
    def get_status(self):
        return gfx_console_commands.get_status(self.backend)

    # Callback for clipboard paste functions.
    def paste_text(self, text):
        simics.SIM_thread_safe_callback(self.string_to_simics, text)

    # Callback for menu item.
    def copy_screen(self):
        if self.text_mode:
            # Read latest text data from backend.
            with simics_lock():
                self.update_text_data()
            # In text mode we copy the text contents of the screen.
            simmod.mini_winsome.console_util.set_clipboard_string(
                    self.get_rect_mark_str(wx.Size(0, 0), self.text_size),
                False)
        else:
            # In graphics mode we copy the graphics screen, as seen by the
            # simulation, not the scaled/rotated version, for consistency.
            context = wx.MemoryDC(self.buffer)
            (w, h) = self.GetClientSize()
            bitmap = wx.Bitmap(w, h)
            memory = wx.MemoryDC(bitmap)
            memory.Blit(0, 0, w, h, context, 0, 0)
            simmod.mini_winsome.console_util.set_clipboard_bitmap(bitmap)

    # Send string to Simics. Must be run in the Simics thread.
    def string_to_simics(self, text):
        data = gfx_console_common.string_to_keystrokes(text)
        if data:
            for (ch, stroke) in data:
                (up, code) = stroke
                self.key_to_simics((code, up == 0))
        else:
            # TODO What to do here?
            print(("String contains characters that cannot"
                                 " be translated to keystrokes."), file=sys.stderr)

    def prefs_update(self, subscriber, notifier, _):
        self.update_dimming()
        self.refresh_all()

    # Callback for user show/hide of console GUI window.
    # Notifies console backend of visibility state.
    def set_visible(self, visible):
        with simics_lock():
            # The console backend may be deleted
            if self.backend and hasattr(self.backend, 'iface'):
                self.backend.iface.gfx_console_backend.set_visible(visible)
            if visible:
                # We need notification from Simics when simulation stops/starts
                # to decide if we should dim the screen.
                install_hap_callback("Core_Simulation_Stopped",
                                     self.simulation_stopped)
                install_hap_callback("Core_Continuation", self.continuation)
                notifier = simics.SIM_notifier_type("pref-change")
                assert notifier is not None
                self.prefs_notifier = simics.SIM_add_notifier(
                    conf.prefs, notifier, None, self.prefs_update, None)
                assert self.prefs_notifier is not None
            else:
                remove_hap_callback("Core_Simulation_Stopped",
                                    self.simulation_stopped)
                remove_hap_callback("Core_Continuation", self.continuation)
                if self.prefs_notifier is not None:
                    simics.SIM_delete_notifier(conf.prefs, self.prefs_notifier)
                    self.prefs_notifier = None
        if visible:
            # Request complete refresh from backend
            self.refresh_screen()

    ## Keyboard input functions

    # Convert a raw physical key to the corresponding Simics key
    def physical_key(self, rawcode):
        # Use the mapping from the physical keyboard layout dialog
        return self.parent.phys_mapping_dialog.lookup_key(rawcode)

    # Send key to Simics. Must be run in the Simics thread.
    def key_to_simics(self, data):
        if (self.backend and hasattr(self.backend, 'iface')
            and simics.SIM_simics_is_running()):
            (code, down) = data
            self.backend.iface.gfx_console_backend.kbd_event(code, down)

    # Send a single key event for a Simics keycode to the device.
    # If down is true, it's a make (press), otherwise a break (release).
    def emit_key_to_model(self, sim_key, down):
        simics.SIM_thread_safe_callback(self.key_to_simics, (sim_key, down))

    # Emit a make/break pair for a Simics keycode code, with possible
    # wx modifiers.
    def emit_make_break(self, sim_key, modifiers):
        codes = simmod.mini_winsome.keycodes.convert_modifiers(modifiers)
        codes.append(sim_key)

        for c in codes:
            self.emit_key_to_model(c, True)
        for c in reversed(codes):
            self.emit_key_to_model(c, False)

    # EVT_CHAR callback
    def char_input(self, event):
        # We only use char events in symbolic keyboard mode.
        if not self.phys_kbd_mode:
            kc = event.GetKeyCode()
            k = simmod.mini_winsome.keycodes.symbolic_char_key(kc)
            if k is not None:
                (sim_key, mods) = k
                # Keep event modifiers except shift, which is assumed to be part
                # of the symbol generation.
                ev_mods = event.GetModifiers() & ~wx.MOD_SHIFT
                self.emit_make_break(sim_key, mods | ev_mods)
            else:
                print(("Cannot map wx keycode %d"
                                     " to a physical key" % kc), file=sys.stderr)

    # EVT_KEY_DOWN callback
    def key_down(self, event):
        if self.text_mode:
            self.remove_mark()

        kc = event.GetKeyCode()
        if kc == self.grab_modifier:
            self.grab_got_modifier = True

        if self.phys_kbd_mode:
            sim_key = self.physical_key(event.GetRawKeyFlags())
            if sim_key is not None:
                self.emit_key_to_model(sim_key, True)
        else:
            # Use the EVT_KEY_DOWN event for keys that would not be
            # distinguished from other keys in EVT_CHAR. For example,
            # backspace (as opposed to Ctrl-H), return (vs Ctrl-M), and so on.

            # wxPython gives the same key code for left Alt and Windows key
            if kc == wx.WXK_ALT and event.MetaDown():
                kc = wx.WXK_WINDOWS_LEFT
                # Must send Windows key without modifiers
                event.SetMetaDown(False)
            k = simmod.mini_winsome.keycodes.symbolic_function_key(kc)
            ev_mods = event.GetModifiers()
            if k is not None:
                (sim_key, mods) = k
                self.emit_make_break(sim_key, mods | ev_mods)
                return

            # Let EVT_CHAR handle the key instead.
            event.Skip()

    # EVT_KEY_UP callback
    def key_up(self, event):
        if event.GetKeyCode() == self.grab_modifier:
            self.grab_got_modifier = False
        if self.phys_kbd_mode:
            sim_key = self.physical_key(event.GetRawKeyFlags())
            if sim_key is not None:
                self.emit_key_to_model(sim_key, False)

    def post_message_event(self, update, args):
        with self.event_cond:
            self.processing_events = True
            simmod.mini_winsome.win_main.post_gfx_console_event(
                update, (self,) + args)
            while self.processing_events:
                self.event_cond.wait()

# Class encapsulating the top-level console GUI window, with menus etc.
class Gfx_console_window(wx.Frame, simmod.mini_winsome.console_window.Console_window):
    def __init__(self, parent, backend, handle, title):
        # Graphics console size change is strictly controlled,
        # hence no maximise or resize option.
        if backend and hasattr(backend, 'iface'):
            console = simics.SIM_object_parent(backend)
            name = console.name
        else:
            name = ""

        wx.Frame.__init__(
            self, parent, wx.ID_ANY, title = title, name = name,
            style = (wx.DEFAULT_FRAME_STYLE & ~wx.MAXIMIZE_BOX
                     & ~wx.RESIZE_BORDER))

        # Actual graphics console, a wx.ScrolledWindow.
        self.console = Gfx_console(self, backend)
        # Super class that takes care of some menus.
        simmod.mini_winsome.console_window.Console_window.__init__(
            self, parent, handle, self.console)

        # Set up Edit menu
        screenshot_id = wx.Window.NewControlId()
        self.editmenu.Append(screenshot_id, "Save screen...")
        self.gfx_mark_mode_id = wx.Window.NewControlId()
        self.save_bp_img_id = wx.Window.NewControlId()
        self.editmenu.AppendSeparator()
        self.editmenu.AppendCheckItem(
            self.gfx_mark_mode_id, "Rectangle mark mode")
        self.editmenu.Append(self.save_bp_img_id, "Save breakpoint image")
        self.editmenu.Enable(self.save_bp_img_id, False)

        # Set up View menu
        self.scale_up_id = wx.Window.NewControlId()
        self.scale_down_id = wx.Window.NewControlId()
        rotate_clockwise_id = wx.Window.NewControlId()
        rotate_anticlockwise_id = wx.Window.NewControlId()
        self.viewmenu.AppendSeparator()
        self.viewmenu.Append(self.scale_up_id, "Scale up")
        self.viewmenu.Append(self.scale_down_id, "Scale down")
        self.viewmenu.AppendSeparator()
        self.viewmenu.Append(rotate_clockwise_id,
                             "Rotate clockwise 90 deg")
        self.viewmenu.Append(rotate_anticlockwise_id,
                             "Rotate counterclockwise 90 deg")

        # Set up Settings menu
        self.settings_menu = wx.Menu()
        self.sym_mode_id = wx.Window.NewControlId()
        self.phys_mode_id = wx.Window.NewControlId()
        self.phys_mapping_id = wx.Window.NewControlId()
        self.settings_menu.AppendRadioItem(self.sym_mode_id,
                                           "Symbolic keyboard mode")
        self.settings_menu.AppendRadioItem(self.phys_mode_id,
                                           "Physical keyboard mode")
        self.settings_menu.AppendSeparator()
        self.settings_menu.Append(self.phys_mapping_id,
                                  "Physical keyboard mapping...")
        self.menubar.Append(self.settings_menu, "Settings")

        # Menu item callbacks
        self.Bind(wx.EVT_MENU, self.on_screenshot, None, screenshot_id)
        self.Bind(wx.EVT_MENU, self.on_scale_up, None, self.scale_up_id)
        self.Bind(wx.EVT_MENU, self.on_scale_down, None, self.scale_down_id)
        self.Bind(wx.EVT_MENU, self.on_rotate_clock, None,
                  rotate_clockwise_id)
        self.Bind(wx.EVT_MENU, self.on_rotate_anticlock, None,
                  rotate_anticlockwise_id)
        self.Bind(wx.EVT_MENU, self.gfx_mark_mode, None,
                  self.gfx_mark_mode_id)
        self.Bind(wx.EVT_MENU, self.save_bp_img, None, self.save_bp_img_id)
        self.Bind(wx.EVT_MENU, self.on_sym_mode, None, self.sym_mode_id)
        self.Bind(wx.EVT_MENU, self.on_phys_mode, None, self.phys_mode_id)
        self.Bind(wx.EVT_MENU, self.on_phys_mapping, None, self.phys_mapping_id)

        self.Bind(wx.EVT_SET_FOCUS, self.set_console_focus)

        # Status bar LEDs for Caps/Num/Scroll lock
        self.led_off_colour = wx.Colour(0x88, 0x99, 0x88, 0xff)
        self.led_on_colour = wx.GREEN
        self.setup_statusbar()

        # Initialise scaling state
        self.update_scaling(1)
        # Initialise window size. Must happen after self.console init
        self.update_window_size()

        # Physical keyboard setup dialog
        self.phys_mapping_dialog = simmod.mini_winsome.keycodes.Phys_mapping_dialog(self)

        # Will console be opened automatically if it is the only one?
        self.enable_auto_show = True

        self.set_icon('open-idle')

    def Destroy(self):
        self.console.Destroy()
        super(wx.Frame, self).Destroy()

    def set_console_focus(self, event):
        self.console.SetFocus()

    # Update widget sizes, after containing console has updated its widgets.
    def update_window_size(self):
        self.SetSizer(None)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.console)
        # Must first remove earlier max/min sizes, to avoid crash in Fit()
        self.SetMaxSize(wx.Size(-1, -1))
        self.SetMinSize(wx.Size(-1, -1))
        self.SetSizer(sizer)
        self.Layout()
        self.Fit()
        self.SetMinSize(self.GetSize())
        self.SetMaxSize(self.GetSize())
        self.statusbar_update()

    # Callback from console when leaving/entering text mode.
    def set_text_mode(self, text_mode):
        if text_mode:
            self.editmenu.SetLabel(self.copy_screen_id, "&Copy screen text")
        else:
            self.editmenu.SetLabel(self.copy_screen_id, "&Copy screen")
        self.statusbar_update()

    # Return current default screenshot filename for the console,
    # using specified filename extension. This queries Simics for the
    # current time on the clock connected to the console.
    def default_screenshot_filename(self, ext = "png"):
        with simics_lock():
            backend = self.console.backend
            return ("%s_%d_%s.%s"
                    % (backend.name, backend.queue.cycles,
                       time.strftime("%Y%m%d%H%M%S"), ext))

    def default_gfx_bp_filename(self, ext = "brk"):
        with simics_lock():
            backend = self.console.backend
            return ("%s_%d.%s" % (backend.name, backend.queue.cycles, ext))

    # Display system "save" dialog to obtain filename, with given default.
    def screenshot_dialog(self, default_filename):
        dialog = wx.FileDialog(
            self, "Screenshot",
            defaultFile = default_filename,
            style = wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if dialog.ShowModal() == wx.ID_OK and dialog.GetPath():
            return dialog.GetPath()
        else:
            return None

    # Change console window scale factor
    def update_scaling(self, scale):
        self.viewmenu.Enable(self.scale_up_id, scale < MAX_SCALE)
        self.viewmenu.Enable(self.scale_down_id, scale > MIN_SCALE)
        self.console.update_scale(scale)

    # Callback from console when user has changed breakpoint rectangle mark.
    def on_gfx_mark(self, has_mark):
        self.editmenu.Enable(self.save_bp_img_id, has_mark)
        self.enable_copy_text(has_mark)

    # Function required by Console_window super class.
    def icon_filenames(self):
        return {'closed-idle': "gfx-closed-idle.png",
                'closed-output': "gfx-closed-output.png",
                'open-idle': "gfx-open-idle.png",
                'open-output': "gfx-open-output.png"}

    ## Menu item callbacks

    # Override menu callback in console_window
    def on_copy_text(self, event):
        if self.editmenu.IsChecked(self.gfx_mark_mode_id):
            self.console.copy_gfx_mark()
        else:
            Console_window.on_copy_text(self, event)

    def on_sym_mode(self, event):
        self.console.set_kbd_mode(False)
        self.statusbar_update()

    def on_phys_mode(self, event):
        self.console.set_kbd_mode(True)
        self.statusbar_update()

    def on_phys_mapping(self, event):
        self.phys_mapping_dialog.Show()
        self.phys_mapping_dialog.Raise()

    def gfx_mark_mode(self, event):
        gfx_mark_mode = self.editmenu.IsChecked(self.gfx_mark_mode_id)
        self.console.set_gfx_mark_mode(gfx_mark_mode)
        event.Skip()

    def save_bp_img(self, event):
        # Obtain destination path
        path = self.screenshot_dialog(self.default_gfx_bp_filename())
        if path:
            # Call backend to store breakpoint file.
            with simics_lock():
                backend = self.console.backend
                if backend and hasattr(backend, 'iface'):
                    rect = self.console.gfx_mark_rect()
                    if not backend.iface.gfx_break.store(
                            path, rect.GetLeft(), rect.GetTop(),
                            rect.GetRight(), rect.GetBottom()):
                        wx.MessageBox("Could not store graphical"
                                      " breakpoint to %s" % path)

    def on_scale_up(self, event):
        self.update_scaling(min(self.console.scale * 2, MAX_SCALE))

    def on_scale_down(self, event):
        self.update_scaling(max(self.console.scale * Fraction(1, 2), MIN_SCALE))

    def on_rotate_clock(self, event):
        self.console.update_rotation((self.console.rotation + 1) % 4)

    def on_rotate_anticlock(self, event):
        self.console.update_rotation((self.console.rotation - 1) % 4)

    def on_screenshot(self, event):
        path = self.screenshot_dialog(self.default_screenshot_filename())
        if path:
            if not self.console.screenshot(path):
                wx.MessageBox("Could not store screenshot to %s" % path)

    ## Status bar related functions

    def setup_statusbar(self):
        self.statusbar = self.CreateStatusBar()

        # Set up status bar fields
        self.statusbar_fields = {
            'size': 1, 'mode': 2,'keyboard': 3, 'leds': 4}
        self.statusbar.SetFieldsCount(len(self.statusbar_fields) + 1)
        self.statusbar.SetStatusStyles([wx.SB_FLAT]
                                       * (len(self.statusbar_fields) + 1))
        self.statusbar.Bind(wx.EVT_SIZE, self.statusbar_resize)

        ## Set up LED panel

        self.led_panel = wx.Panel(self.statusbar)
        self.caps_led = wx.Panel(self.led_panel)
        self.num_led = wx.Panel(self.led_panel)
        self.scroll_led = wx.Panel(self.led_panel)
        self.caps_text = wx.StaticText(self.led_panel, wx.ID_ANY, "Caps")
        self.num_text = wx.StaticText(self.led_panel, wx.ID_ANY, "Num")
        self.scroll_text = wx.StaticText(self.led_panel, wx.ID_ANY, "Scroll")

        # For easier lookup during LED state change.
        self.leds = {simics.Gfx_Console_Led_Caps: self.caps_led,
                     simics.Gfx_Console_Led_Num: self.num_led,
                     simics.Gfx_Console_Led_Scroll: self.scroll_led}
        for led in self.leds:
            # TODO More dynamic LED size?
            self.leds[led].SetMinSize(wx.Size(20, 10))
            # Initially LED off
            self.leds[led].SetBackgroundColour(self.led_off_colour)

        # 2 pixel border between controls
        led_sizer = wx.BoxSizer(wx.HORIZONTAL)
        border = 2
        flags = wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT
        led_sizer.Add(self.caps_text, 0, flag = flags, border = border)
        led_sizer.Add(self.caps_led, 0, flag = flags, border = border)
        led_sizer.Add(self.num_text, 0, flag = flags, border = border)
        led_sizer.Add(self.num_led, 0, flag = flags, border = border)
        led_sizer.Add(self.scroll_text, 0, flag = flags, border = border)
        led_sizer.Add(self.scroll_led, 0, flag = flags, border = border)
        self.led_panel.SetSizer(led_sizer)
        self.led_panel.Layout()
        self.led_panel.Fit()

        # Allow user to change Caps/Scroll/Num lock status using mouse
        self.caps_led.Bind(wx.EVT_LEFT_DOWN, self.caps_click)
        self.caps_text.Bind(wx.EVT_LEFT_DOWN, self.caps_click)
        self.scroll_led.Bind(wx.EVT_LEFT_DOWN, self.scroll_click)
        self.scroll_text.Bind(wx.EVT_LEFT_DOWN, self.scroll_click)
        self.num_led.Bind(wx.EVT_LEFT_DOWN, self.num_click)
        self.num_text.Bind(wx.EVT_LEFT_DOWN, self.num_click)

        self.caps_led.Bind(wx.EVT_SET_FOCUS, self.set_console_focus)
        self.scroll_led.Bind(wx.EVT_SET_FOCUS, self.set_console_focus)
        self.num_led.Bind(wx.EVT_SET_FOCUS, self.set_console_focus)

        # Set status bar field widths after LED panel has sized itself
        self.statusbar.SetStatusWidths(
            [1] + ([-1] * (len(self.statusbar_fields) - 1))
            + [self.led_panel.GetSize().GetWidth() + border * 2])

    # Callback for updating the statusbar. Must be called whenever any data
    # displayed on the status bar has changed.
    def statusbar_update(self):
        size = self.console.buffer.GetSize()
        text_mode = self.console.text_mode
        keyb_mode = self.console.phys_kbd_mode
        status_text = "%d×%d (%.1fx)" % (size.width, size.height,
                                         self.console.scale)
        self.statusbar.SetStatusText(status_text, self.statusbar_fields['size'])
        self.statusbar.SetStatusText("Text mode" if text_mode else "",
                                     self.statusbar_fields['mode'])
        self.statusbar.SetStatusText(
            "Keyboard: %s" % ("Physical" if keyb_mode else "Symbolic"),
                              self.statusbar_fields['keyboard'])

    # Event callback
    def statusbar_resize(self, event):
        # Move LED panel to position of status bar field.
        rect = self.statusbar.GetFieldRect(self.statusbar_fields['leds'])
        (w, h) = self.led_panel.GetSize()
        ypad = (rect.height - h) // 2
        self.led_panel.SetPosition((rect.x, rect.y + ypad))
        event.Skip()

    # gfx_console_frontend.set_keyboard_leds
    def set_keyboard_leds(self, led_state):
        for led in self.leds:
            if (led_state & led) > 0:
                self.leds[led].SetBackgroundColour(self.led_on_colour)
            else:
                self.leds[led].SetBackgroundColour(self.led_off_colour)
            self.leds[led].Refresh()

    # Send simulated down/up events to the console backend.
    def led_click(self, sim_key):
        self.console.emit_make_break(sim_key, 0)

    # LED mouse click events

    def caps_click(self, event):
        self.led_click(simics.SK_CAPS_LOCK)
        event.Skip()

    def scroll_click(self, event):
        self.led_click(simics.SK_SCROLL_LOCK)
        event.Skip()

    def num_click(self, event):
        self.led_click(simics.SK_NUM_LOCK)
        event.Skip()
