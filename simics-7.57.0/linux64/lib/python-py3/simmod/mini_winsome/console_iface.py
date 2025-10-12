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
import simics

# Window name for top-level console appwindow, i.e. console list
WINDOW_NAME = "target-console"

# Create and return top-level console window.
def create_console_window():
    # Top-level window is registered in the win_main functionality.
    main_window = simmod.mini_winsome.win_main.existing_in_window_list(
        WINDOW_NAME)
    if not main_window:
        simmod.mini_winsome.win_main.open_window(WINDOW_NAME)
        return simmod.mini_winsome.win_main.existing_in_window_list(WINDOW_NAME)
    else:
        return main_window

## Common backend event callbacks for text and graphics consoles

def set_visible_event(handle, visible):
    assert handle != None
    main_window = simmod.mini_winsome.win_main.existing_in_window_list(WINDOW_NAME)
    assert main_window != None
    main_window.set_console_visible(handle, visible)

def set_title_event(handle, short_title, long_title):
    assert handle != None
    main_window = simmod.mini_winsome.win_main.existing_in_window_list(WINDOW_NAME)
    assert main_window != None
    main_window.set_console_title(handle, short_title, long_title)

def console_close_event(handle):
    assert handle != None
    main_window = simmod.mini_winsome.win_main.existing_in_window_list(WINDOW_NAME)
    assert main_window != None
    main_window.close_console(handle)

# Event posted by update_thread in text or graphics console
def update_console_event(console):
    console.parent.ignore_activity_indicator = True

    # Wait until events are processed, to avoid flooding wxPython event queue.
    with console.event_cond:
        console.parent.on_new_console_data()
        console.processing_events = False
        console.event_cond.notify()

## Backend event callbacks for text consoles

def text_console_open_event(backend, handle):
    assert backend != None
    main_window = simmod.mini_winsome.win_main.existing_in_window_list(WINDOW_NAME)
    assert main_window != None
    main_window.open_text_console(backend, handle)

def text_set_max_scrollback_size_event(handle, num_lines):
    assert handle != None
    main_window = simmod.mini_winsome.win_main.existing_in_window_list(WINDOW_NAME)
    assert main_window != None
    w = main_window.lookup_console(handle)
    w.set_max_scrollback_size(num_lines)

def text_set_default_colours_event(handle, fg_col, bg_col):
    assert handle != None
    main_window = simmod.mini_winsome.win_main.existing_in_window_list(WINDOW_NAME)
    assert main_window != None
    w = main_window.lookup_console(handle)
    w.set_default_colours(fg_col, bg_col)

# Event posted by win_text_console.update_thread
def text_set_contents_cursor_event(console, left, top, right, bottom,
                                   data, attrib, cursor_x, cursor_y):
    # Wait until events are processed, to avoid flooding wxPython event queue.
    with console.event_cond:
        if not console.parent.IsIconized():
            # Message may contain a cursor update only
            if data is not None and len(data) > 0:
                console.set_contents(left, top, right, bottom, data, attrib)
            # Message may contain contents update only
            if cursor_x >= 0:
                console.move_cursor(cursor_x, cursor_y)
        console.processing_events = False
        console.event_cond.notify()

# Event posted by win_text_console.update_thread
def text_append_text_event(console, num_lines, text, attrib,
                           cursor_x, cursor_y):
    # Wait until events are processed, to avoid flooding wxPython event queue.
    with console.event_cond:
        if not console.parent.IsIconized():
            console.append_text(num_lines, text, attrib)
            # Message may contain text append only
            if cursor_x >= 0:
                console.move_cursor(cursor_x, cursor_y)
        console.processing_events = False
        console.event_cond.notify()

# Event posted by win_text_console.update_thread
def text_refresh_event(console, screen_text, screen_attrib,
                       sb_text, sb_attrib, sb_lines, cursor_x, cursor_y):
    # Wait until events are processed, to avoid flooding wxPython event queue.
    with console.event_cond:
        if not console.parent.IsIconized():
            console.refresh_contents(screen_text, screen_attrib,
                                     sb_text, sb_attrib, sb_lines)
            console.move_cursor(cursor_x, cursor_y)
        console.processing_events = False
        console.event_cond.notify()

def text_set_size_event(console, width, height):
    # Wait until events are processed, to avoid flooding wxPython event queue.
    with console.event_cond:
        if not console.parent.IsIconized():
            console.resize(width, height)
        console.processing_events = False
        console.event_cond.notify()

# Text console event handlers
text_handlers = {
    'console_open_event': text_console_open_event,
    'console_close_event': console_close_event,
    'set_title_event': set_title_event,
    'set_size_event': text_set_size_event,
    'set_max_scrollback_size_event': text_set_max_scrollback_size_event,
    'set_contents_cursor_event': text_set_contents_cursor_event,
    'set_default_colours_event': text_set_default_colours_event,
    'append_text_event': text_append_text_event,
    'refresh_event': text_refresh_event,
    'console_update_event': update_console_event,
    'set_visible_event': set_visible_event,
}

def handle_text_event(name, args):
    text_handlers[name](*args)

## Implementation of text_console_frontend interface.
## Interface calls are converted to wxPython events.
## This serialises them in time and avoids multi-threading,
## which does not work with wxPython.

def text_console_open(obj, backend):
    # Make sure window create event is queued as early as possible
    create_console_window()
    assert backend != None
    handle = wx.Window.NewControlId()
    simmod.mini_winsome.win_main.post_text_console_event("console_open_event",
                                                  [backend, handle])
    return handle

def text_console_close(obj, handle):
    simmod.mini_winsome.win_main.post_text_console_event("console_close_event",
                                                  [handle])

def text_set_title(obj, handle, short_title, long_title):
    simmod.mini_winsome.win_main.post_text_console_event(
        "set_title_event", [handle, short_title, long_title])

def text_set_max_scrollback_size(obj, handle, num_lines):
    simmod.mini_winsome.win_main.post_text_console_event(
        "set_max_scrollback_size_event", [handle, num_lines])

def text_set_default_colours(obj, handle, fg_col, bg_col):
    simmod.mini_winsome.win_main.post_text_console_event(
        "set_default_colours_event", [handle, fg_col, bg_col])

def text_set_visible(obj, handle, visible):
    simmod.mini_winsome.win_main.post_text_console_event(
        "set_visible_event", [handle, visible])

console_iface = simics.text_console_frontend_interface_t(
    start                   = text_console_open,
    stop                    = text_console_close,
    set_title               = text_set_title,
    set_max_scrollback_size = text_set_max_scrollback_size,
    set_default_colours     = text_set_default_colours,
    set_visible             = text_set_visible,
)

simics.SIM_register_interface(
    'gui', simics.TEXT_CONSOLE_FRONTEND_INTERFACE, console_iface)

## Backend event callbacks for graphics consoles

def gfx_console_open_event(backend, handle):
    assert backend != None
    main_window = simmod.mini_winsome.win_main.existing_in_window_list(WINDOW_NAME)
    assert main_window != None
    main_window.open_gfx_console(backend, handle)

# Event posted by win_gfx_console.update_thread
def gfx_set_contents_event(console, left, top, right, bottom,
                           data, text_mode):
    # Wait until events are processed, to avoid flooding wxPython event queue.
    with console.event_cond:
        if not console.parent.IsIconized():
            console.set_contents(left, top, right, bottom, data, text_mode)
        console.processing_events = False
        console.event_cond.notify()

def gfx_set_grab_mode_event(handle, active):
    assert handle != None
    main_window = simmod.mini_winsome.win_main.existing_in_window_list(WINDOW_NAME)
    assert main_window != None
    w = main_window.lookup_console(handle)
    w.set_grab_mode(active)

def gfx_set_grab_modifier_event(handle, modifier):
    assert handle != None
    main_window = simmod.mini_winsome.win_main.existing_in_window_list(WINDOW_NAME)
    assert main_window != None
    w = main_window.lookup_console(handle)
    w.set_grab_modifier(modifier)

def gfx_set_grab_button_event(handle, button):
    assert handle != None
    main_window = simmod.mini_winsome.win_main.existing_in_window_list(WINDOW_NAME)
    assert main_window != None
    w = main_window.lookup_console(handle)
    w.set_grab_button(button)

def gfx_set_mouse_pos_event(handle, x, y):
    assert handle != None
    main_window = simmod.mini_winsome.win_main.existing_in_window_list(WINDOW_NAME)
    assert main_window != None
    w = main_window.lookup_console(handle)
    w.WarpPointer(x, y)

def gfx_set_keyboard_leds_event(handle, led_state):
    assert handle != None
    main_window = simmod.mini_winsome.win_main.existing_in_window_list(WINDOW_NAME)
    assert main_window != None
    w = main_window.lookup_console_win(handle)
    w.set_keyboard_leds(led_state)

def gfx_set_size_event(console, width, height):
    # Wait until events are processed, to avoid flooding wxPython event queue.
    with console.event_cond:
        if not console.parent.IsIconized():
            console.resize(width, height)
        console.processing_events = False
        console.event_cond.notify()

# Graphics console event handlers
gfx_handlers = {
    'console_open_event': gfx_console_open_event,
    'console_close_event': console_close_event,
    'set_title_event': set_title_event,
    'set_size_event': gfx_set_size_event,
    'set_contents_event': gfx_set_contents_event,
    'set_grab_mode_event': gfx_set_grab_mode_event,
    'set_grab_modifier_event': gfx_set_grab_modifier_event,
    'set_grab_button_event': gfx_set_grab_button_event,
    'set_mouse_pos_event': gfx_set_mouse_pos_event,
    'console_update_event': update_console_event,
    'set_visible_event': set_visible_event,
    'set_keyboard_leds_event': gfx_set_keyboard_leds_event,
}

def handle_gfx_event(name, args):
    gfx_handlers[name](*args)

## Implementation of gfx_console_frontend interface.
## Interface calls are converted to wxPython events.
## This serialises them in time and avoids multi-threading,
## which does not work with wxPython.

def gfx_console_open(obj, backend):
    # Make sure window create event is queued as early as possible
    create_console_window()
    assert backend != None
    handle = wx.Window.NewControlId()
    simmod.mini_winsome.win_main.post_gfx_console_event("console_open_event",
                                                 [backend, handle])
    return handle

def gfx_console_close(obj, handle):
    simmod.mini_winsome.win_main.post_gfx_console_event("console_close_event",
                                                 [handle])

def gfx_set_title(obj, handle, short_title, long_title):
    simmod.mini_winsome.win_main.post_gfx_console_event(
        "set_title_event", [handle, short_title, long_title])

def gfx_set_grab_mode(obj, handle, active):
    simmod.mini_winsome.win_main.post_gfx_console_event("set_grab_mode_event",
                                                 [handle, active])

def gfx_set_grab_modifier(obj, handle, modifier):
    simmod.mini_winsome.win_main.post_gfx_console_event("set_grab_modifier_event",
                                                 [handle, modifier])

def gfx_set_grab_button(obj, handle, button):
    simmod.mini_winsome.win_main.post_gfx_console_event("set_grab_button_event",
                                                 [handle, button])

def gfx_set_mouse_pos(obj, handle, x, y):
    simmod.mini_winsome.win_main.post_gfx_console_event("set_mouse_pos_event",
                                                 [handle, x, y])

def gfx_set_visible(obj, handle, visible):
    simmod.mini_winsome.win_main.post_gfx_console_event("set_visible_event",
                                                 [handle, visible])

def gfx_set_keyboard_leds(obj, handle, led_state):
    simmod.mini_winsome.win_main.post_gfx_console_event("set_keyboard_leds_event",
                                                 [handle, led_state])

console_iface = simics.gfx_console_frontend_interface_t(
    start             = gfx_console_open,
    stop              = gfx_console_close,
    set_title         = gfx_set_title,
    set_grab_mode     = gfx_set_grab_mode,
    set_grab_modifier = gfx_set_grab_modifier,
    set_grab_button   = gfx_set_grab_button,
    set_mouse_pos     = gfx_set_mouse_pos,
    set_visible       = gfx_set_visible,
    set_keyboard_leds = gfx_set_keyboard_leds,
)

simics.SIM_register_interface(
    'gui', simics.GFX_CONSOLE_FRONTEND_INTERFACE, console_iface)

def winsome_console_update(params):
    con = params[0]
    update = params[1:]
    assert con != None
    con.post_message_event(update[0], update[1:])

def winsome_console_activity(*args):
    winsome_console_update((args[1], "console_update_event") + args[2:])

def winsome_console_gfx(*args):
    winsome_console_update((args[1], "set_contents_event") + args[2:])

def winsome_console_resize(*args):
    winsome_console_update((args[1], "set_size_event") + args[2:])

def winsome_console_refresh(*args):
    winsome_console_update((args[1], "refresh_event") + args[2:])

def winsome_console_append(*args):
    winsome_console_update((args[1], "append_text_event") + args[2:])

def winsome_console_text(*args):
    winsome_console_update((args[1], "set_contents_cursor_event") + args[2:])

winsome_iface = simics.winsome_console_interface_t(
    gfx = winsome_console_gfx,
    resize = winsome_console_resize,
    refresh = winsome_console_refresh,
    append = winsome_console_append,
    activity = winsome_console_activity,
    text = winsome_console_text,
)

simics.SIM_register_interface(
    'gui', simics.WINSOME_CONSOLE_INTERFACE, winsome_iface)
