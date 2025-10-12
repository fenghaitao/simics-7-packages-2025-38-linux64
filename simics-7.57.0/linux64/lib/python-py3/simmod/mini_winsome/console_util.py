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
import time
import simics
from .win_utils import *

# Convert a character position (wx.Size/wx.Point) to pixel position
# using the given font size.
def text_to_pixel(size, font_width, font_height):
    # Use x,y to allow both Size and Point
    s = wx.Size(size.x, size.y)
    s.Scale(font_width, font_height)
    return s

# Convert a pixel position (wx.Size/wx.Point) to a character position
# using the given font size.
def pixel_to_text(size, font_width, font_height):
    # Use x,y to allow both Size and Point
    s = wx.Size(size.x, size.y)
    s.Scale(1.0 / font_width, 1.0 / font_height)
    s.x = int(s.x)
    s.y = int(s.y)
    return s

# Are the given coordinates point-wise bounded above by the given max coordinates?
def is_valid_coord(coord, max_coord):
    return all(a <= b for (a, b) in zip(coord.Get(), max_coord.Get()))

# Return a wx.Rect of the marked region defined by the given mark start/stop (wx.Size)
# assuming the mark mode is rectangular.
def get_rect_mark_coords(mark_start, mark_stop):
    left = min(mark_start.x, mark_stop.x)
    top = min(mark_start.y, mark_stop.y)
    right = max(mark_start.x, mark_stop.x)
    bottom = max(mark_start.y, mark_stop.y)
    return wx.Rect(left, top, right - left + 1, bottom - top + 1)

# Return a wx.Rect of the marked region defined by the given mark start/stop (wx.Size),
# assuming usual terminal style mark mode.
def get_mark_coords(mark_start, mark_stop, max_coord):
    if mark_start.y < mark_stop.y:
        start = wx.Size(mark_start.x, mark_start.y)
        end = wx.Size(mark_stop.x, mark_stop.y)
    elif mark_start.y > mark_stop.y:
        start = wx.Size(mark_stop.x, mark_stop.y)
        end = wx.Size(mark_start.x, mark_start.y)
    else:
        start = wx.Size(min(mark_start.x, mark_stop.x), mark_start.y)
        end = wx.Size(max(mark_start.x, mark_stop.x), mark_start.y)
    min_coord = wx.Size(0, 0)
    start.IncTo(min_coord)
    end.DecTo(max_coord)
    return (start, end)

# Set the system clipboard to the given text. Use the primary selection buffer if "primary"
# is set, which has a similar effect to marking text in X.
def set_clipboard_string(text, primary):
    if wx.TheClipboard.Open():
        text_obj = wx.TextDataObject()
        text_obj.SetText(text)
        wx.TheClipboard.UsePrimarySelection(primary)
        wx.TheClipboard.SetData(text_obj)
        wx.TheClipboard.Close()
    else:
        print("Could not open clipboard", file=sys.stderr)

# Return current string in the system clipboard, or in the primary selection buffer.
def get_clipboard_string(primary):
    if wx.TheClipboard.Open():
        text_obj = wx.TextDataObject()
        text = ''
        wx.TheClipboard.UsePrimarySelection(primary)
        if wx.TheClipboard.GetData(text_obj):
            text = text_obj.GetText()
        wx.TheClipboard.Close()
        return text
    else:
        print("Could not open clipboard", file=sys.stderr)
        return ''

# Copy the inverted contents of the text lines in rect in src_dc to dst_dc.
# Optionally scale the destination using the given factor.
def invert_text_lines(dst_dc, src_dc, rect, font_size, scale):
    for y in range(rect.y, rect.y + rect.height):
        coord = wx.Size(rect.x, y)
        text_size = wx.Size(rect.width, 1)
        src_start = text_to_pixel(coord, font_size.width, font_size.height)
        dst_start = wx.Size(src_start.x, src_start.y)
        dst_start.Scale(scale, scale)
        src_size = text_to_pixel(text_size, font_size.width, font_size.height)
        dst_size = wx.Size(src_size.x, src_size.y)
        dst_size.Scale(scale, scale)
        dst_dc.StretchBlit(
            dst_start.x, dst_start.y,
            dst_size.width, dst_size.height,
            src_dc, src_start.x, src_start.y, src_size.width, src_size.height,
            wx.SRC_INVERT)

# Draw the given marked text in dst_dc from src_dc, using an inverted blit.
def draw_rect_mark(dst_dc, src_dc, text_size, font_size,
                   mark_start, mark_stop, max_coord, scale):
    rect = get_rect_mark_coords(mark_start, mark_stop)
    if not rect.IsEmpty():
        invert_text_lines(dst_dc, src_dc, rect, font_size, scale)

# Draw the given marked text in dst_dc from src_dc, using an inverted blit.
def draw_mark(dst_dc, src_dc, text_size, font_size,
              mark_start, mark_stop, max_coord, scale):
    (start, stop) = get_mark_coords(mark_start, mark_stop, max_coord)
    if start.y < stop.y:
        # First line may have an unmarked prefix.
        invert_text_lines(
            dst_dc, src_dc,
            wx.Rect(start.x, start.y, text_size.width - start.x, 1),
            font_size, scale)
        if start.y < stop.y - 1:
            # Most lines must be completely marked.
            invert_text_lines(
                dst_dc, src_dc,
                wx.Rect(0, start.y + 1, text_size.width, stop.y - start.y - 1),
                font_size, scale)
        # Last line may have an unmarked suffix.
        invert_text_lines(dst_dc, src_dc,
                         wx.Rect(0, stop.y, stop.x + 1, 1),
                         font_size, scale)
    else:
        # Single line mark may have unmarked prefix and suffix.
        invert_text_lines(dst_dc, src_dc,
                          wx.Rect(start.x, start.y, stop.x - start.x + 1, 1),
                          font_size, scale)

# Set the system clipboard to the given wx.Bitmap
def set_clipboard_bitmap(bitmap):
    if wx.TheClipboard.Open():
        img_obj = wx.BitmapDataObject(bitmap)
        wx.TheClipboard.SetData(img_obj)
        wx.TheClipboard.Close()
    else:
        print("Could not open clipboard", file=sys.stderr)

# Return a dict key -> wx.Bitmap for each key in the filenames dict, whose values should
# be the filenames of the icons. Each icon is scaled to the given size.
def console_icons(filenames, size):
    icons = {}
    for key in filenames:
        image = wx.Image(filenames[key])
        image_scaled = image.Scale(size.width, size.height)
        icons[key] = wx.Bitmap(image_scaled)
    return icons

# Return a string representation of an entry in the info/status data structures.
def info_status_entry_str(entry):
    if entry != None:
        if isinstance(entry, simics.conf_object_t):
            return entry.name
        else:
            return str(entry)
    else:
        return ""

# Return a string representation of an info/status data structure.
def format_info_status(data):
    text = ""
    for section in data:
        heading = section[0]
        entries = section[1]
        formatted_entries = "\n".join(
            "%s: %s" % (entry[0], info_status_entry_str(entry[1]))
            for entry in entries)
        text += "%s%s\n\n" % ((heading + "\n") if heading != None else "",
                            formatted_entries)
    # Remove last line endings
    return text[ : -2]

# Python decodes some cp437 characters to control characters, not visible
# characters, when there is an overlap.
def ibm437_visible(data):
    return data.decode('ibm437').translate({
        0x00: " ",      0x01: "\u263A", 0x02: "\u263B", 0x03: "\u2665",
        0x04: "\u2666", 0x05: "\u2663", 0x06: "\u2660", 0x07: "\u2022",
        0x08: "\u25D8", 0x09: "\u25CB", 0x0a: "\u25D9", 0x0b: "\u2642",
        0x0c: "\u2640", 0x0d: "\u266A", 0x0e: "\u266B", 0x0f: "\u263C",
        0x10: "\u25BA", 0x11: "\u25C4", 0x12: "\u2195", 0x13: "\u203C",
        0x14: "\u00B6", 0x15: "\u00A7", 0x16: "\u25AC", 0x17: "\u21A8",
        0x18: "\u2191", 0x19: "\u2193", 0x1a: "\u2192", 0x1b: "\u2190",
        0x1c: "\u221F", 0x1d: "\u2194", 0x1e: "\u25B2", 0x1f: "\u25BC",
        0x7f: "\u2302",
    })

assert ibm437_visible(b'\x01') == '☺'

# Translate the given rect using the given transform
def transform_rect(transform, left, top, right, bottom):
    (x1, y1) = transform.TransformPoint(left, top)
    (x2, y2) = transform.TransformPoint(right, bottom)
    w = int(abs(x2 - x1) + 1)
    h = int(abs(y2 - y1) + 1)
    return wx.Rect(int(min(x1, x2)), int(min(y1, y2)), w, h)
