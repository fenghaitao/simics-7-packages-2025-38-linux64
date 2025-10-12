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
from .win_utils import simics_lock
from . import console_util
import re

# Maximum number of ms between second and third mouse click to consider it
# a triple click.
TRIPLE_CLICK_MS = 200

# Different text mark modes, mimicing xterm behaviour:
# "char" is usual mark mode where individual characters can be marked.
# "word" is entered after a double click, and only whole words can be marked.
# "line" is entered after a triple click, and only whole lines can be marked.
MARK_CHAR = 0
MARK_WORD = 1
MARK_LINE = 2

# Super class of text and graphics consoles, providing text marking functions.
# Subclasses must define:
# - max_coord, a wx.Size object with the lower right screen coordinate
# - get_char(pos) -> char, screen character given a wx.Size
# - line_length(y) -> int, actual line length (until newline) given line number
# - line_wrap(y) -> bool, if line wraps (no ending newline) given line number
# - get_text_size() -> wx.Size, size of text screen, in characters
# - pixel_to_text(wx.Size) -> wx.Size, convert screen pos to text pos
# - refresh_text_rect(wx.Rect), queue refresh of given rectangle in text coords
# - refresh_all(), queue refresh of whole screen
# - get_rect_mark_str(int, int) -> str, return rectangular mark string
# - get_line_mark_str(int, int) -> str, return console mark string
class Console_panel:
    def __init__(self):
        # Mouse pixel position of active drag start, a wx.Point, or None.
        # These are used to indicate if a drag is ongoing that has started
        # within the screen.
        self.drag_start = None
        # Mouse pixel position of active drag stop, a wx.Point, or None.
        # Used to calculate mark positions in e.g. word mark mode.
        # Note that drag_stop can be above/left of drag_start.
        self.drag_stop = None
        # Character position of active mark start, a wx.Size, or None.
        self.mark_start = None
        # Character position of active mark stop, a wx.Size, or None.
        # Note that mark_stop can be above/left of mark_start.
        self.mark_stop = None
        # Have user performed a triple click?
        self.got_triple_click = False
        # Is rectangle mark mode active?
        self.rectangle_mark = False
        # Character mark mode
        self.mark_mode = MARK_CHAR
        # Regular expression for finding word boundary.
        self.whitespace_re = re.compile(r'\s')
        # Timeout that defines triple click after double click.
        self.click_timer = wx.Timer(self, wx.Window.NewControlId())
        self.Bind(wx.EVT_TIMER, self.triple_click, self.click_timer)

    # Triple click timeout callback.
    def triple_click(self, event):
        self.click_timer.Stop()
        self.got_triple_click = False

    # Refresh screen between the given mark start/stop character positions.
    def refresh_mark(self, start, stop):
        # We ignore mark modes and refresh bounding box.
        # TODO Refresh more selectively to increase performance.
        height = abs(stop.y - start.y) + 1
        self.refresh_text_rect(wx.Rect(
            0, min(start.y, stop.y), self.get_text_size().GetWidth(), height))

    # Is there currently marked text?
    def has_mark(self):
        return self.mark_start is not None and self.mark_stop is not None

    # Remove text mark.
    def remove_mark(self):
        self.mark_start = None
        self.mark_stop = None

    # Has user started a mouse drag inside the screen?
    def drag_started(self):
        return self.drag_start is not None

    # Return currently marked text.
    def get_mark_str(self):
        if self.rectangle_mark:
            rect = console_util.get_rect_mark_coords(
                self.mark_start, self.mark_stop)
            return self.get_rect_mark_str(
                rect.GetTopLeft(), rect.GetBottomRight())
        else:
            (start, stop) = console_util.get_mark_coords(
                self.mark_start, self.mark_stop, self.max_coord)
            return self.get_line_mark_str(start, stop)

    # Send currently marked text to clipboard.
    # If primary is True, then set the primary selection buffer, similar to
    # just marking text in X.
    def mark_to_clipboard(self, primary):
        console_util.set_clipboard_string(self.get_mark_str(), primary)

    # Set explicit text mark, and set clipboard.
    def set_mark(self, start, stop):
        self.mark_start = start
        self.mark_stop = stop
        if self.mark_start is not None and self.mark_stop is not None:
            self.mark_to_clipboard(True)
            self.refresh_mark(self.mark_start, self.mark_stop)
            self.parent.enable_copy_text(True)

    # Setup initial mark data on left mouse down.
    def setup_mark(self, pos, mark_mode, ctrl_down):
        if self.has_mark():
            self.refresh_mark(self.mark_start, self.mark_stop)
        # Set valid drag active
        self.drag_start = pos
        text_pos = self.pixel_to_text(pos)
        if mark_mode == MARK_WORD:
            (start_pos, end_pos) = self.word_boundary_at(pos)
            self.set_mark(start_pos, end_pos)
        elif mark_mode == MARK_LINE:
            # Mark whole line, including wrap
            mark_start_line = self.wrapped_line_begin(text_pos.y)
            self.set_mark(wx.Size(0, mark_start_line),
                          wx.Size(self.get_text_size().GetWidth() - 1,
                                  self.wrapped_line_end(text_pos.y)))
        else:
            self.rectangle_mark = ctrl_down
            self.set_mark(text_pos, None)
        self.mark_mode = mark_mode

    # Update mark data on mouse motion, when in char mark mode, given current
    # character position of mouse.
    def update_char_mark(self, text_pos):
        mark_start = self.pixel_to_text(self.drag_start)
        # The mouse position may be outside screen.
        mark_start = wx.Size(min(max(0, mark_start.x), self.max_coord.x),
                             min(max(0, mark_start.y), self.max_coord.y))

        if text_pos.y < mark_start.y:
            # Dragging upwards
            assert mark_start.y > 0
            first_line_len = self.line_length(mark_start.y)

            # Not allowed to mark outside line
            if first_line_len <= mark_start.x:
                self.mark_start = wx.Size(self.get_text_size().GetWidth() - 1,
                                          mark_start.y - 1)
            else:
                self.mark_start = mark_start
            # Not allowed to mark outside line
            if self.line_length(text_pos.y) <= text_pos.x:
                self.mark_stop = wx.Size(0, min(text_pos.y + 1,
                                                self.mark_start.y))
            else:
                self.mark_stop = text_pos
        elif text_pos.y > mark_start.y:
            # Dragging downwards
            assert mark_start.y < self.max_coord.y
            first_line_len = self.line_length(mark_start.y)
            # Not allowed to mark outside line
            if first_line_len <= mark_start.x:
                self.mark_start = wx.Size(0, mark_start.y + 1)
            else:
                self.mark_start = mark_start
            # Visibly mark line break
            if self.line_length(text_pos.y) <= text_pos.x:
                text_pos.x = self.get_text_size().GetWidth() - 1
            self.mark_stop = text_pos
        else:
            line_len = self.line_length(mark_start.y)
            # Not allowed to mark outside line
            if (line_len <= text_pos.x and line_len <= mark_start.x):
                self.mark_start = None
            else:
                # Visibly mark line break
                if line_len <= text_pos.x:
                    text_pos.x = self.get_text_size().GetWidth() - 1
                if line_len <= mark_start.x:
                    mark_start.x = self.get_text_size().GetWidth() - 1
                self.mark_start = mark_start
                self.mark_stop = text_pos

    # Update mark data on mouse motion, when in word mark mode, given current
    # character position of mouse.
    def update_word_mark(self, text_pos):
        (start_begin, start_end) = self.word_boundary_at(self.drag_start)
        (stop_begin, stop_end) = self.word_boundary_at(self.drag_stop)
        if start_begin.y == text_pos.y:
            # Dragging on original line
            if (stop_end.y > self.mark_start.y
                or stop_end.x > self.mark_start.x):
                # Dragging to the right of original position.
                self.mark_start = start_begin
                self.mark_stop = stop_end
            else:
                # Dragging to the left of original position.
                self.mark_stop = stop_begin
                self.mark_start = start_end
        elif start_begin.y < text_pos.y:
            # Dragging below original line.
            self.mark_stop = stop_end
            self.mark_start = start_begin
        else:
            # Dragging above original line.
            self.mark_stop = stop_begin
            self.mark_start = start_end

    # Update mark data on mouse motion, when in line mark mode, given current
    # character position of mouse.
    def update_line_mark(self, text_pos):
        # Find original line of mark_start
        mark_start_line = self.wrapped_line_begin(self.mark_start.y)
        if text_pos.y >= mark_start_line:
            # Dragging below original line.
            # Whole of original line should be included.
            self.mark_start = wx.Size(0, mark_start_line)
            # Make sure we mark whole wrapped lines.
            self.mark_stop = wx.Size(self.get_text_size().GetWidth() - 1,
                                     self.wrapped_line_end(text_pos.y))
        else:
            # Dragging above original line.
            # Whole of original line should be included.
            self.mark_stop = wx.Size(0, self.wrapped_line_begin(text_pos.y))
            # Make sure we mark whole wrapped lines.
            self.mark_start = wx.Size(self.get_text_size().GetWidth() - 1,
                                      self.wrapped_line_end(self.mark_start.y))

    # Is there a word boundary between the chars?
    def is_word_boundary(self, prev_char, char):
        if prev_char is not None:
            if (self.whitespace_re.match(char)
                or self.whitespace_re.match(prev_char)):
                return True
            else:
                return re.match(r'[%s]\b[%s]' % (re.escape(prev_char),
                                                    re.escape(char)),
                                '%s%s' % (prev_char, char))
        else:
            return self.whitespace_re.match(char)

    # Find start y of wrapped line.
    def wrapped_line_begin(self, line):
        while line >= 0:
            line -= 1
            if not self.line_wrap(line):
                break
        return line + 1

    # Find end y of wrapped line.
    def wrapped_line_end(self, line):
        while self.line_wrap(line):
            line += 1
        return line

    # Return start x of word at pos (wxPoint/wxSize),
    # if boundary is found on the same line.
    # Space is the only word boundary character.
    def word_start_at_line(self, pos):
        prev_char = (None if pos.x >= self.max_coord.x else
                     self.get_char(wx.Size(pos.x, pos.y)))
        pos.x -= 1
        while pos.x >= 0:
            char = self.get_char(pos)
            if self.is_word_boundary(prev_char, char):
                # If pos = end of line and space, still return pos, even
                # strictly not a word start.
                # This is for word marking to behave as expected.
                pos.x = min(pos.x + 1, self.line_length(pos.y) - 1)
                return (True, pos)
            else:
                prev_char = char
                pos.x -= 1
        # Word might continue on previous wrapped line.
        return (False, pos)

    # Return end x of word at pos (wxPoint/wxSize),
    # if boundary is found on the same line.
    # Space is the only word boundary character.
    def word_end_at_line(self, pos):
        assert pos.x < self.line_length(pos.y)
        prev_char = (None if pos.x <= 0 else
                     self.get_char(wx.Size(pos.x, pos.y)))
        pos.x += 1
        while pos.x < self.line_length(pos.y):
            char = self.get_char(pos)
            if self.is_word_boundary(prev_char, char):
                # If pos = start of line and space, return last char of
                # previous line, even though strictly not on this line.
                # This is for word marking to behave as expected.
                if pos.x == 0:
                    if pos.y > 0:
                        pos.y -= 1
                        pos.x = self.line_length(pos.y) - 1
                else:
                    pos.x -= 1
                return (True, pos)
            else:
                prev_char = char
                pos.x += 1
        # Word might continue on wrapped line.
        return (False, pos)

    # Find start and end positions of word at pixel position pos, taking
    # wrapped lines and actual line lengths into account.
    def word_boundary_at(self, pos):
        start_pos = self.pixel_to_text(pos)
        # It can happen that the mouse position is outside the screen area
        start_pos = wx.Size(min(max(0, start_pos.x), self.max_coord.x),
                           min(max(0, start_pos.y), self.max_coord.y))
        # Avoid empty line special case.
        if self.line_length(start_pos.y) == 0:
            return (wx.Size(0, start_pos.y),
                    wx.Size(self.max_coord.x, start_pos.y))

        start_pos.x = min(self.line_length(start_pos.y) - 1, start_pos.x)
        assert start_pos.x >= 0

        found = False
        while start_pos.y >= 0:
            # Find word start position on current line.
            (found, start_pos) = self.word_start_at_line(start_pos)
            if found:
                break
            # Try previous line, if it was wrapped.
            if start_pos.y > 0:
                if not self.line_wrap(start_pos.y - 1):
                    break
                else:
                    start_pos.x = self.line_length(start_pos.y - 1) - 1
            start_pos.y -= 1
        if not found:
            start_pos = wx.Size(0, max(0, start_pos.y))

        end_pos = self.pixel_to_text(pos)
        # It can happen that the mouse position is outside the screen area
        end_pos = wx.Size(min(max(0, end_pos.x), self.max_coord.x),
                          min(max(0, end_pos.y), self.max_coord.y))
        end_pos.x = min(self.line_length(end_pos.y) - 1, end_pos.x)
        assert end_pos.x >= 0

        found = False
        while end_pos.y <= self.max_coord.y:
            # Find word end position on current line.
            (found, end_pos) = self.word_end_at_line(end_pos)
            if found:
                break
            # Try next line if current line wraps.
            if not self.line_wrap(end_pos.y):
                end_pos.x = self.line_length(end_pos.y) - 1
                break
            end_pos.y += 1
            end_pos.x = 0
        if not found and end_pos.y > self.max_coord.y:
            end_pos = wx.Size(self.line_length(self.max_coord.y) - 1,
                              min(self.max_coord.y, end_pos.y))
        return (start_pos, end_pos)

    # Update mark on mouse motion.
    def on_mouse_motion(self, event, dc):
        if event.Dragging() and event.LeftIsDown() and self.drag_started():
            pos = event.GetLogicalPosition(dc)
            self.drag_stop = pos

            old_stop = self.mark_stop
            text_pos = self.pixel_to_text(pos)
            # The mouse position may be outside screen.
            text_pos = wx.Size(min(max(0, text_pos.x), self.max_coord.x),
                               min(max(0, text_pos.y), self.max_coord.y))

            # Update mark_start and mark_stop corresponding to new mouse
            # positions.
            if self.mark_mode == MARK_CHAR:
                self.update_char_mark(text_pos)
            elif self.mark_mode == MARK_WORD:
                self.update_word_mark(text_pos)
            else:
                self.update_line_mark(text_pos)

            # It can happen that mark should disappear.
            if self.has_mark():
                refresh_start = wx.Point(min(self.mark_start.x,
                                             self.mark_stop.x),
                                         min(self.mark_start.y,
                                             self.mark_stop.y))
                refresh_stop = wx.Point(max(self.mark_start.x,
                                            self.mark_stop.x),
                                        max(self.mark_start.y,
                                            self.mark_stop.y))
            if self.has_mark() and old_stop != None:
                refresh_start.x = min(old_stop.x, refresh_start.x)
                refresh_start.y = min(old_stop.y, refresh_start.y)
                refresh_stop.x = max(old_stop.x, refresh_stop.x)
                refresh_stop.y = max(old_stop.y, refresh_stop.y)

                self.refresh_mark(refresh_start, refresh_stop)
            else:
                self.refresh_all()

    # Handle drag/mark setup on mouse left button down.
    def on_left_down(self, event, dc):
        self.click_timer.Stop()
        pos = event.GetLogicalPosition(dc)
        text_pos = self.pixel_to_text(pos)
        # It can happen that the window is slightly larger in pixels than what
        # the character size determines, so that the character position also
        # is out of bounds.
        if console_util.is_valid_coord(text_pos, self.max_coord):
            # Setup mark start
            self.setup_mark(pos,
                            MARK_LINE if self.got_triple_click else MARK_CHAR,
                            event.ControlDown())
            self.got_triple_click = False

    # Handle word mark setup on mouse left button double click.
    def on_left_dbl_click(self, event, dc):
        pos = event.GetLogicalPosition(dc)

        # Setup word mark data.
        text_pos = self.pixel_to_text(pos)
        if console_util.is_valid_coord(text_pos, self.max_coord):
            # Setup mark start
            self.setup_mark(pos, MARK_WORD, False)
            # Start count down for triple click
            self.got_triple_click = True
            self.click_timer.Start(TRIPLE_CLICK_MS)

    # Handle mark/copy when releasing mouse button
    def on_left_up(self, event, dc):
        pos = event.GetLogicalPosition(dc)
        text_pos = self.pixel_to_text(pos)

        if self.has_mark():
            # Copy current mark to clipboard and flag that copy menu
            # can be enabled.
            self.set_mark(self.mark_start, self.mark_stop)
        else:
            # If no marked text, disable copy menu.
            self.parent.enable_copy_text(False)
            self.refresh_all()

        # It can happen that mouse position is outside active screen area.
        if console_util.is_valid_coord(text_pos, self.max_coord):
            self.drag_stop = pos
            # Set drag no longer active
            self.drag_start = None
            self.drag_stop = None
