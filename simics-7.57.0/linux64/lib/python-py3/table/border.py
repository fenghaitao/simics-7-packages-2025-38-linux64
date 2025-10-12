# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


class Chars:
    def __init__(self, chars):
        assert len(chars) == 19
        (self.horizontal_dash,
         self.vertical_bar,
         self.top_left,
         self.top_right,
         self.row_left,
         self.row_left_other,
         self.row_right,
         self.row_right_other,
         self.bottom_left,
         self.bottom_right,
         self.conn_down,
         self.conn_down_other,
         self.conn_up,
         self.conn_up_other,
         self.conn_both,
         self.conn_both_other_same,
         self.conn_both_same_other,
         self.conn_both_other_other,
         self.column_separator) = chars

class BorderStyle:
    __slots__ = ('heavy', 'light')
    def __init__(self, heavy=None, light=None):
        self.heavy = heavy if heavy else light
        self.light = light

    def extra_width(self, cols):
        """Returns how many characters will be used for a row to render the
        border and column separators for the given 'cols' and based on the
        border-style of this instance"""
        border_width = max(len(self.heavy.vertical_bar),
                           len(self.light.vertical_bar))
        sep_width    = max(len(self.heavy.column_separator),
                           len(self.light.column_separator))
        extra_width = border_width * 2 + (cols - 1) * sep_width
        return extra_width

    # Create a line all in heavy (depends on style) and connect to
    # other lines above and below in heavy too.
    # Examples:
    # ┏━━━━━┳━━━━━┳━━━━━┓ up = [] down = [5,5,5]
    # ┣━━━━━┻━━━━━┻━━━━━┫ up = [5,5,5] down =[17]
    # ┣━━━━━┳━━━━━┳━━━━━┫ up = [17] down = [5,5,5]
    # ┣━━━━━╋━━━━━╋━━━━━┫ up & down = [5,5,5]
    # ┗━━━━━┻━━━━━┻━━━━━┛ up = [5,5,5] down = []
    def row_separator_heavy(self, up_widths, down_widths):
        (left_char, right_char) = self._left_right_chars(
            up_widths, down_widths)

        return self._row_separator_up_down(
            up_widths, down_widths,
            left_char,
            self.heavy.horizontal_dash,
            self.heavy.conn_up,
            self.heavy.conn_down,
            self.heavy.conn_both,
            right_char)

    # Create a heavy line. Connect to line above in light and
    # line below in heavy.
    # Examples:
    # ┏━━━━━┳━━━━━┳━━━━━┓ up = [] down = [5,5,5]
    # ┣━━━━━┷━━━━━┷━━━━━┫ up = [5,5,5] down =[17]
    # ┣━━━━━┳━━━━━┳━━━━━┫ up = [17] down = [5,5,5]
    # ┣━━━━━╈━━━━━╈━━━━━┫ up & down = [5,5,5]
    # ┗━━━━━┷━━━━━┷━━━━━┛ up = [5,5,5] down = []
    def row_separator_heavy_from_light(self, up_widths, down_widths):
        (left_char, right_char) = self._left_right_chars(
            up_widths, down_widths)

        return self._row_separator_up_down(
            up_widths, down_widths,
            left_char,
            self.heavy.horizontal_dash,
            self.heavy.conn_up_other,
            self.heavy.conn_down,
            self.heavy.conn_both_other_same,
            right_char)

    # Create a heavy line. Connect to line above in heavy and
    # line below in light.
    # Examples:
    # ┏━━━━━┯━━━━━┯━━━━━┓ up = [] down = [5,5,5]
    # ┣━━━━━┻━━━━━┻━━━━━┫ up = [5,5,5] down =[17]
    # ┣━━━━━┯━━━━━┯━━━━━┫ up = [17] down = [5,5,5]
    # ┣━━━━━╇━━━━━╇━━━━━┫ up & down = [5,5,5]
    # ┗━━━━━┻━━━━━┻━━━━━┛ up = [5,5,5] down = []
    def row_separator_heavy_to_light(self, up_widths, down_widths):
        (left_char, right_char) = self._left_right_chars(
            up_widths, down_widths)

        return self._row_separator_up_down(
            up_widths, down_widths,
            left_char,
            self.heavy.horizontal_dash,
            self.heavy.conn_up,
            self.heavy.conn_down_other,
            self.heavy.conn_both_same_other,
            right_char)

    # Create a line using some heavy characters (for the border)
    # Connect lines above and below with light connectors.
    # Examples:
    # ┏━━━━━┯━━━━━┯━━━━━┓ up = [] down = [5,5,5]
    # ┠─────┴─────┴─────┨ up = [5,5,5] down =[17]
    # ┠─────┬─────┬─────┨ up = [17] down = [5,5,5]
    # ┠─────┼─────┼─────┨ up & down = [5,5,5]
    # ┗━━━━━┷━━━━━┷━━━━━┛ up = [5,5,5] down = []
    def row_separator_heavy_light_light(self, up_widths, down_widths):
        assert up_widths or down_widths
        if not up_widths:
            # Start new table (┏, ┓)
            left_char = self.heavy.top_left
            right_char = self.heavy.top_right
        elif not down_widths:
            # End table (┗, ┛)
            left_char = self.heavy.bottom_left
            right_char = self.heavy.bottom_right
        else:
            # Within table (┠, ┨)
            left_char = self.heavy.row_left_other
            right_char = self.heavy.row_right_other

        if not up_widths or not down_widths:
            dash = self.heavy.horizontal_dash       # ━
            up = self.heavy.conn_up_other           # ┷
            down = self.heavy.conn_down_other       # ┯
            both = self.heavy.conn_both_other_other # ┿
        else:
            dash = self.light.horizontal_dash # ─
            up = self.light.conn_up           # ┴
            down = self.light.conn_down       # ┬
            both = self.light.conn_both       # ┼

        return self._row_separator_up_down(up_widths, down_widths,
                                           left_char, dash,
                                           up, down, both,right_char)

    # Utility function for starting a table
    # Example: ┏━━━━━┳━━━━━┳━━━━━┓
    def start_row_heavy(self, down_widths):
        return self.row_separator_heavy([], down_widths)

    # Utility function for ending a table
    # Example: ┗━━━━━┻━━━━━┻━━━━━┛
    def end_row_heavy(self, up_widths):
        return self.row_separator_heavy(up_widths, [])

    # Utility function for starting a table
    # Example: ┏━━━━━┯━━━━━┯━━━━━┓
    def start_row_light(self, down_widths):
        return self.row_separator_heavy_to_light([], down_widths)

    # Utility function for ending a table
    # Example: ┗━━━━━┷━━━━━┷━━━━━┛
    def end_row_light(self,up_widths):
        return self.row_separator_heavy_from_light(up_widths, [])

    # Generic helper function which creates row separators
    # connecting the table borders. up_widths and down_widths
    # are lists specifying the widths of the columns above
    # and columns below respectively.
    @staticmethod
    def _row_separator_up_down(up_widths, down_widths,
                              left_char,
                              dash_char,
                              conn_up_char,
                              conn_down_char,
                              conn_both_char,
                              right_char):

        # Returns a set where the separators should be positioned:
        # widths [10, 5, 7] -> (10, 16, 24)
        def separator_set(widths):
            start = 0
            s = set()
            for w in widths:
                # assumption col sep and conns have same width
                col_sep_len = len(conn_both_char)
                start += w
                s.add(start + 1)
                start += col_sep_len
            return s

        up_seps = separator_set(up_widths)
        down_seps = separator_set(down_widths)
        seps = sorted(up_seps.union(down_seps))
        s = left_char
        prev = 0
        for sep in seps:
            s += dash_char * (sep - prev - 1)
            if sep == list(seps)[-1]: # Last
                s += right_char
            elif sep in up_seps and sep in down_seps:
                s += conn_both_char
            elif sep in up_seps:
                s += conn_up_char
            else:
                s += conn_down_char
            prev = sep + len(conn_both_char) - 1

        if not s.strip(): # Remove border-less lines
            return ""
        return s + "\n"

    # Helper function for selecting the leftmost and
    # rightmost character of the separator row.
    def _left_right_chars(self, up_widths, down_widths):
        assert up_widths or down_widths
        if not up_widths:       # Start new table (┏,┓)
            return (self.heavy.top_left,
                    self.heavy.top_right)

        if not down_widths:     # End table (┗,┛)
            return (self.heavy.bottom_left,
                    self.heavy.bottom_right)

        # Inside the table (┣, ┫)
        return (self.heavy.row_left,
                self.heavy.row_right)

    # Return a row with data (in strs list) and separate the data
    # with heavy characters. The list of strings must already been
    # aligned/padded to the correct size for the table row.
    # ┃  A  ┃  B  ┃  C  ┃
    def data_row_heavy(self, strs):
        return self._data_row(
            strs, self.heavy.vertical_bar, self.heavy.column_separator)

    # ┃  A  │  B  │  C  ┃
    def data_row_heavy_light(self, strs):
        return self._data_row(
            strs, self.heavy.vertical_bar, self.light.column_separator)

    # Helper function for data_row_*
    @staticmethod
    def _data_row(strs, vertical_bar, column_separator):
        last = len(strs) - 1
        s = vertical_bar

        for i, e in enumerate(strs):
            s += e
            if i == last:   # Last
                s += vertical_bar
            else:
                s += column_separator

        if not s.strip(): # Remove border-less lines
            return ""
        return s + "\n"

# Must be kept in sync with the preferences.c preference
# cli_table_border_style setter.
border_style = {
    "thick": BorderStyle(
        Chars("━"   # horizontal_dash
              "┃"   # vertical_bar
              "┏"   # top_left
              "┓"   # top_right
              "┣"   # row_left
              "┠"   # row_left_other
              "┫"   # row_right
              "┨"   # row_right_other
              "┗"   # bottom_left
              "┛"   # bottom_right
              "┳"   # conn_down
              "┯"   # conn_down_other
              "┻"   # conn_up
              "┷"   # conn_up_other
              "╋"   # conn_both
              "╈"   # conn_both_other_same
              "╇"   # conn_both_same_other
              "┿"   # conn_both_other_other
              "┃"),  # column_separator
        Chars("─"   # horizontal_dash
              "│"   # vertical_bar
              "┌"   # top_left
              "┐"   # top_right
              "├"   # row_left
              "├"   # row_left_other
              "┤"   # row_right
              "┤"   # row_right_other
              "└"   # bottom_left
              "┘"   # bottom_right
              "┬"   # conn_down
              "┰"   # conn_down_other
              "┴"   # conn_up
              "┸"   # conn_up_other
              "┼"   # conn_both
              "╁"   # conn_both_other_same
              "╁"   # conn_both_same_other
              "╂"   # conn_both_other_other
              "│")   # column_separator
    ),

    "thin": BorderStyle(
        None,                   # No heavy, use light
        Chars("─"   # horizontal_dash
              "│"   # vertical_bar
              "┌"   # top_left
              "┐"   # top_right
              "├"   # row_left
              "├"   # row_left_other
              "┤"   # row_right
              "┤"   # row_right_other
              "└"   # bottom_left
              "┘"   # bottom_right
              "┬"   # conn_down
              "┬"   # conn_down_other
              "┴"   # conn_up
              "┴"   # conn_up_other
              "┼"   # conn_both
              "┼"   # conn_both_other_same
              "┼"   # conn_both_same_other
              "┼"   # conn_both_other_other
              "│")   # column_separator

    ),

    "ascii": BorderStyle(
        None,                   # No heavy, use light
        Chars("-"   # horizontal_dash
              "|"   # vertical_bar
              "+"   # top_left
              "+"   # top_right
              "+"   # row_left
              "+"   # row_left_other
              "+"   # row_right
              "+"   # row_right_other
              "+"   # bottom_left
              "+"   # bottom_right
              "+"   # conn_down
              "+"   # conn_down_other
              "+"   # conn_up
              "+"   # conn_up_other
              "+"   # conn_both
              "+"   # conn_both_other_same
              "+"   # conn_both_same_other
              "+"   # conn_both_other_other
              "|")   # column_separator

    ),

    "header_only_underline_ascii": BorderStyle(
        None,                   # No heavy, use light
        Chars(["=",   # horizontal_dash
              "",   # vertical_bar
              "",   # top_left
              "",   # top_right
              "",   # row_left
              "",   # row_left_other
              "",   # row_right
              "",   # row_right_other
              "",   # bottom_left
              "",   # bottom_right
              "==",   # conn_down
              "==",   # conn_down_other
              "==",   # conn_up
              "==",   # conn_up_other
              "==",   # conn_both
              "==",   # conn_both_other_same
              "==",   # conn_both_same_other
              "==",   # conn_both_other_other
              "  "])   # column_separator

    ),

    "borderless": BorderStyle(
        None,                   # No heavy, use light
        Chars(["", # horizontal_dash
               "", # vertical_bar
               "", # top_left
               "", # top_right
               "", # row_left
               "", # row_left_light
               "", # row_right
               "", # row_right_light
               "", # bottom_left
               "", # bottom_right
               "", # conn_down
               "", # conn_down_heavy
               "", # conn_up
               "", # conn_up_heavy
               "", # conn_both
               "", # conn_both_light_heavy
               "", # conn_both_heavy_light
               "", # conn_both_heavy_heavy
               "  "])   # column_separator
    ),

}

border_styles = border_style.keys()
