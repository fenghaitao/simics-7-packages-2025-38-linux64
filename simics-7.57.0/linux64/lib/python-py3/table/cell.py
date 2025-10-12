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


# Implements the Cell class representing each cell's contents in the
# table which are formatted from the original data to a pretty-printed
# string representation showed in the generated table.

import cli
import simics
from . import cell_props
from .common import (TableException,)
from math import log10

class Cell:
    '''Representation of all cells, converted to strings. Handles new-line
    characters in the input string and converts these to multiple
    lines instead. If lines are longer than a certain max_width, long
    lines are wrapped into multiple lines. All strings are represented
    as unidecoded utf-8 strings to properly handle strange characters.'''
    __slots__ = (
        'alignment',            # 'left', 'right', 'center'
        'org_lines',            # original list of lines
        'lines',                # reformatted list of lines
        'max_length',           # length of longest line
        'delimiters'            # Delimiters for the cell
    )

    def __init__(self, s, props, override_alignment=None):
        s = s.replace('\t', ' ') # Tabs are tricky, just make a space
        if override_alignment:
            col_align = override_alignment
        else:
            col_align = props.p_alignment.get()

        self.alignment = col_align if col_align else self._default_alignment

        self.delimiters = props.p_word_delimiters.get()
        self.org_lines = s.split('\n')
        self.lines = self.org_lines[:]
        self.max_length = max(len(l) for l in self.lines)

    def narrow_width(self, max_width, force_max_width):
        '''Try to make the cells row fit within max_width, by creating
        multiple lines. If force_max_width is False, we allow a delimiter
        character to included on the same line even if this makes the
        line one character longer than max_width'''
        def eat_spaces(l):
            while len(l) > max_width:
                p = l.find("  ")
                if p >= 0:
                    l = l[:p] + l[p+1:]
                else:
                    return l
            return l

        nl = []
        for l in self.org_lines:
            if len(l) <= max_width:
                nl.append(l)
                continue

            l = eat_spaces(l)
            if len(l) <= max_width:
                nl.append(l)
                continue

            s = self._make_multiline(l, max_width, force_max_width)
            nl.extend(s.split('\n'))

        self.lines = nl
        self.max_length = max(len(l) for l in self.lines)

    def max_len(self):
        '''string length of the longest string'''
        return self.max_length

    def num_lines(self):
        '''number of lines the string represents'''
        return len(self.lines)

    def line(self, i):
        if i < len(self.lines):
            return self.lines[i]
        return ""

    def aligned_line(self, i, width):
        # The <str>.center() sometimes prioritize spaces before the
        # word rather than after, which we don't like. Hence our
        # own implementation.
        def center(s, width):
            if len(s) >= width:
                return s
            add = width - len(s)
            head = " " * (add // 2)
            tail = " " * ((add // 2) + (add % 2))
            return head + s + tail

        s = self.line(i)
        if self.alignment == 'left':
            return "%-*s" % (width, s)
        if self.alignment == 'right':
            return "%*s" % (width, s)
        if self.alignment == 'center':
            s = s.strip()
            return "%s" % (center(s, width))
        assert(0)
        return ""

    def _make_multiline(self, orig, max_width, force_max_width):
        '''Split up a long string to a string with additional \n characters.
        Try to break the string intelligently, keeping the text still readable.
        If force_max_width is False, we accept the delimiter to be placed last,
        makeing the string one character longer than max_width
        (producing slightly more readable format).'''

        class WrappedText:
            text = ""           # Multi-line output
            line_len = 0        # Current work-line length

        def is_delimiter(c):    # Let some characters to be part of the word
            return c in self.delimiters

        def printed_delimiter(d): # Skip some delimiters at end of line
            return '' if d == ' ' else d

        def wordify(text):
            '''returns [(word, delimiter)*] for entire text'''
            out = []
            word = ""
            for t in text:
                if is_delimiter(t):
                    out.append((word, t))
                    word = ""
                else:
                    word += t
            if word:
                out.append((word, '')) # Last word without delimiter
            return out

        def place_word(wt, w, d):
            while True:
                if wt.line_len == 0 and len(w) > max_width:      # longlongwor|d
                    wt.text += w[:max_width] + '\n'
                    w = w[max_width:]
                elif wt.line_len + len(w) + len(d) == max_width: # ......word-|
                    wt.text += w + d + '\n'
                    wt.line_len = 0
                    return
                elif wt.line_len + len(w) + len(d) < max_width:  # ...word-...|
                    wt.text += w + d
                    wt.line_len += len(w) + len(d)
                    return
                elif wt.line_len + len(w) == max_width:          # .......word|-
                    pdel = printed_delimiter(d)
                    if force_max_width:
                        wt.text += w + '\n' + pdel
                        wt.line_len = len(pdel)
                    else:
                        wt.text += w + pdel + '\n'
                        wt.line_len = 0
                    return
                else:                                            # .........wo|rd
                    if len(w) > max_width: # Word must be split anyway
                        p = max_width - wt.line_len
                        wt.text += w[:p] + '\n'
                        w = w[p:]
                    else:
                        wt.text += '\n'
                    wt.line_len = 0

        def wrapped_text_from_words(words):
            wt = WrappedText()
            for (w, d) in words:
                place_word(wt, w, d)
            return wt

        words = wordify(orig)
        wt = wrapped_text_from_words(words)
        res = wt.text.rstrip('\n') # we do not want the cell to end with '\n'
        return res

class BoolCell(Cell):
    __slots__ = ()
    _default_alignment = "center"

    def __init__(self, b, col_align):
        s = str(b).lower()
        super().__init__(s, col_align)

class IntCell(Cell):
    __slots__ = ()
    _default_alignment = "right"

    def __init__(self, i, props):
        grouping = None if props.p_grouping.get() else 0
        radix = props.p_radix.get()
        pad_width = props.p_pad_width.get()

        # radix: None = user preferences, otherwise 2, 10, 16
        s = cli.number_str(i, radix, grouping, precision=pad_width)
        super().__init__(s, props)

class PercentCell(Cell):
    __slots__ = ()
    _default_alignment = "right"

    def __init__(self, f, props, decimals):
        s = "%.*f%%" % (decimals, 100 * f)
        super().__init__(s, props)

class FloatCell(Cell):
    __slots__ = ()
    _default_alignment = "right"

    def __init__(self, f, props, decimals):
        s = "%.*f" % (decimals, f)
        super().__init__(s, props)

class MetricCell(Cell):
    __slots__ = ()
    _default_alignment = "right"

    def __init__(self, f, props, decimals, metric_unit):
        new, prefix = self._get_prefix(f, decimals)
        s = "%.*f %s%s%s" % (decimals, new, prefix, metric_unit,
                             "" if prefix else " ")
        super().__init__(s, props)

    @staticmethod
    def _get_prefix(val, decimals):
        def rounds_up_to_one(val):
            return round(abs(val * 1000.0), decimals) >= 1000.0

        def handle_large_prefixes(val):
            e = 1.0
            for p in ["", "k", "M", "G", "T", "P", "E", "Z", "Y"]:
                if abs(val) < e*1000:
                    return (val / e, p)
                e *= 1000
            # out of prefixes, use exponent instead
            exp = int(log10(abs(val)))
            return (val / (10.0 ** exp), f"e{exp}")

        def handle_small_prefixes(val):
            e = 1000.0
            for p in ["m", "µ", "n", "p", "f", "a", "z", "y"]:
                if abs(val * e) >= 1.0 or rounds_up_to_one(val * e):
                    return (val * e, p)
                e *= 1000.0
            # out of prefixes, use 10 exponent instead
            exp = int(log10(abs(val)) - 0.5) # want negative exponents round down
            return (val / (10.0 ** exp), f"e{exp}")

        if val == 0:
            return (val, "")
        elif abs(val) >= 1.0 or rounds_up_to_one(val):
            return handle_large_prefixes(val)
        else:
            return handle_small_prefixes(val)

class TimeCell(Cell):
    __slots__ = ()
    _default_alignment = "right"

    def __init__(self, val, props, decimals):
        # Format *HH:MM:SS.ss
        negative = val < 0
        val = abs(float(val))
        val = val * (10 ** decimals) # scale to decimal point
        val = val + 0.5              # prepare rounding
        val = int(val)               # chop of decimals
        val = val / (10 ** decimals) # scale back decimal point

        hours = int(val // 3600)
        minutes = int((val - (hours * 3600)) // 60)
        seconds = val - hours * 3600 - minutes * 60

        s = f"{'-' if negative else ''}"
        if decimals:
            s += f"{hours:02}:{minutes:02}:{seconds:0{3+decimals}.{decimals}f}"
        else:
            s += f"{hours:02}:{minutes:02}:{seconds:0{2}.{0}f}"
        super().__init__(s, props)

class BinaryCell(Cell):
    __slots__ = ()
    _default_alignment = "right"

    def __init__(self, f, props, decimals, metric_unit):
        new, prefix = self._get_bi_prefix(f)
        s = "%.*f %s%s%s" % (decimals, new, prefix, metric_unit,
                             "" if prefix else "  ")
        super().__init__(s, props)

    @staticmethod
    def _get_bi_prefix(val):
        e = 1.0
        for p in ["", "ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi", "Yi"]:
            if abs(val) < e*1024:
                return (val / e, p)
            e *= 1024
        return (val, "")

class StrCell(Cell):
    __slots__ = ()
    _default_alignment = "left"

    def __init__(self, s, props, override_alignment=None):
        # TODO: check for <b> etc.
        super().__init__(s, props, override_alignment)


def data_to_cell(data, decimals, format_props):

    # If no decimals set, take the number of decimals from the props
    if decimals == None:
        decimals = format_props.p_float_decimals.get()

    # Create various Cells depending on type of the data
    if isinstance(data, bool): # Must be checked before int
        return BoolCell(data, format_props)

    elif isinstance(data, int) or isinstance(data, float):

        # Common for both int/float
        metric_prefix = format_props.p_metric_prefix.get()
        if metric_prefix != None:
            return MetricCell(data, format_props, decimals, metric_prefix)

        binary_prefix = format_props.p_binary_prefix.get()
        if binary_prefix != None:
            return BinaryCell(data, format_props, decimals, binary_prefix)

        if format_props.p_time_format.get():
            return TimeCell(data, format_props, decimals)

        if isinstance(data, int):
            return IntCell(data, format_props)
        else:
            if format_props.p_float_percent.get():
                return PercentCell(data, format_props,
                                   decimals)
            return FloatCell(data, format_props,
                             decimals)

    elif isinstance(data, str):
        return StrCell(data, format_props)

    elif isinstance(data, simics.conf_object_t):
        return StrCell(data.name, format_props)

    elif isinstance(data, type(None)):
        return StrCell(str(data), format_props)

    else:
        raise TableException(
            f"unsupported cell type: {type(data)} contents: {data}")
