# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import cli, conf, simics
import codecs, os, re, sys
import simicsutils.host
import unittest
from console_switch import switch_io_fd
from prompt_information import async_print_stop_info, print_stop_info

# TODO: if changed to run in a non-main thread, make sure to protect:
# * conf.prefs accesses (may be cached + prefs change hap)
# * prompt change callback
# * tab_complete() calls
# * conf.sim.history_file
# * The few SIM_ functions used

word_separators = ' !"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'

def cmdline_assert(tst, msg):
    'use instead of assert in this file since stderr is redirected here'
    if not tst:
        raise Exception('Command-line: %s' % msg)

# Regexp that matches a string that contains no unfinished quotations.
quoted_re = re.compile(
    r"""
    ^
    (?:
      [^"]       # Either a non-quote
     |
      "          # or a quoted string, containing...
      (?:
        [^"\\]    # either a non-quote, non-backslash
       |
        \\.       # or an escaped character.
      ) *
      "
    ) *         # any number of times.
    $
    """, re.X)

# Determine whether position pos in text is within a double-quoted string.
# It is true on the opening quote and false on the closing quote.
def in_quote(text, pos):
    return not quoted_re.match(text[: pos + 1])

class _test_in_quote(unittest.TestCase):
    def test_in_quote(self):
        def test(text, result):
            for pos, res in enumerate(result):
                self.assertEqual(in_quote(text, pos), res)
        # Note: last " is not considered part of the quote
        # string with no quotes
        test('abc', (0, 0, 0))
        # quotes in middle of string
        test('a "b" c', (0, 0, 1, 1, 0, 0, 0))
        # string ending with \ (bug in previous implementation)
        test('"a"\\', (1, 1, 0, 0))
        # quoted " is part is string
        test(' "\\"" ', (0, 1, 1, 1, 0, 0))
        # string with only quotes
        test('""', (1, 0))

class _test_command_history(unittest.TestCase):
    def write_lines(self, lines):
        import tempfile
        import locale
        import codecs
        tmp = tempfile.NamedTemporaryFile()
        encoding = locale.getpreferredencoding()
        for line in lines:
            tmp.write(codecs.encode(f'{line}\n', encoding, "replace"))
        tmp.file.flush()
        tmp.seek(0)
        return tmp

    def test_get_lines(self):
        """Test get_lines. Since no command updates the test history, this is
        simulated by using the last line as the last invocation of
        command-history, which should be excluded."""

        if simicsutils.host.is_windows():
            return  # not tested on Windows because of a problem with tempfile
        lines = [
            'a',
            'ab',
            'abc',
            'ac',
            'acd']
        hfile = self.write_lines(lines)
        history = command_history(True, hfile.name)
        history.history_from_file()

        all_but_last = lines[:-1]
        self.assertEqual(history.get_lines(1, None), ['ac'])
        self.assertEqual(history.get_lines(100, None), all_but_last)
        self.assertEqual(history.get_lines(4, None), all_but_last)
        self.assertEqual(history.get_lines(100, 'a'), all_but_last)
        self.assertEqual(history.get_lines(1, 'a'), ['ac'])
        self.assertEqual(history.get_lines(2, 'a'), ['abc', 'ac'])
        self.assertEqual(history.get_lines(100, ''), all_but_last)
        self.assertEqual(history.get_lines(100, 'b'), ['ab', 'abc'])
        self.assertEqual(history.get_lines(1, 'b'), ['abc'])
        self.assertEqual(history.get_lines(1, 't'), [])
        hfile.close()

word_break_chars = " (%$=;"

# Symbols that require quoting when part of a string
_re_must_quote = re.compile(r'[ !"#$%&\'()*+\,/;<=>?@\[\\\]^`{|}]')

def tab_complete(text, tail, python_mode):
    wstart = 0 # start of the item we're doing tab-completion on
    for wb in word_break_chars:
        candidate = text.rfind(wb, 0)
        # do not look for start of word if quoted!
        while candidate > -1 and in_quote(text, candidate):
            candidate = text.rfind(wb, 0, candidate)
        wstart = max(candidate + 1, wstart)
    (comps, filename_compl) = cli.tab_completions(text, python_mode)

    # Merge single tab complete suggestions with filename_t completions
    # that can be tuples
    new_comps = []
    for c in comps:
        if isinstance(c, (tuple, list)) and len(c) == 2:
            new_comps.append(c)
        else:
            new_comps.append((c, False))

    comps = new_comps

    if len(comps) == 0:
        return (None, 0, None, [])

    compstrs = [f for (f, _) in comps]
    prefix = cli.common_prefix(
                          compstrs,
                          not filename_compl or simicsutils.host.is_windows())

    if text[wstart:].startswith('"'):
        old_text = text[wstart + 1:].replace('\\\\', '\\')
        start_quote = True
    else:
        old_text = text[wstart:]
        start_quote = False

    if len(prefix) < len(old_text):
        # this will happen if completions differ in case; preserve the
        # original word and case, like readhist does
        prefix = old_text

    for c in compstrs:
        # force quoting if character after completion requires it
        if (len(c) > len(prefix)
            and _re_must_quote.search(c[len(prefix):len(prefix) + 1])
            and not c.endswith(" =")):
            start_quote = True

    if len(comps) == 1:
        [(_, isdir)] = comps
    else:
        isdir = False
    if (not tail and len(comps) == 1 and not isdir
        and prefix[-1] not in ('.', ':', os.sep)):
        space = ' '
    else:
        space = ''
    pathsep = os.path.sep

    # Check that wstart > 0 since we do not want to quote the command. This may
    # happen for the @ command and object names with [] in them.

    word_needs_quotes = ((start_quote
                          or (_re_must_quote.search(prefix[len(old_text):])
                              and not prefix.endswith(" =")))
                         and wstart > 0)

    if word_needs_quotes:
        # open quote
        prefix = '"' + prefix
        # backslash must be escaped in quoted string
        prefix = prefix.replace('\\', '\\\\')
        pathsep = pathsep.replace('\\', '\\\\')

    if len(comps) == 1:
        if isdir:
            prefix += pathsep
        elif word_needs_quotes:
            # close quote
            prefix += '"'

    cmd = text[:wstart] + prefix + space + tail
    return (cmd, wstart, prefix, compstrs)

debug = False

def unhandled_key(mod, key):
    if debug:
        print("unhandled ", mod, key, file=sys.stderr)

class command_history:
    def __init__(self, interactive, history_file=conf.sim.history_file):
        self.interactive = interactive
        self.history = []
        self.position = 0
        self.current  = ''
        self.file = history_file
        self.file_size = 0

    def update_file(self, text, append):
        if self.file:
            mode = "ab" if append else "wb"
            try:
                with codecs.open(self.file, mode, "utf-8") as f:
                    f.write(text)
            except OSError:
                # Silently ignore I/O errors; they are simply not
                # important enough to bother the user for.
                pass

    def history_from_file(self):
        if not self.interactive:
            return
        if self.file:
            try:
                with codecs.open(self.file, "rb", "utf-8") as f:
                    lines = f.readlines()
            except OSError:
                return

            self.history = [s.rstrip() for s in lines]
            self.file_size = len(self.history)
            self.position = len(self.history)

    def rewrite_file(self):
        self.update_file('\n'.join(self.history) + '\n', append=False)
        self.file_size = len(self.history)

    def add_line_to_file(self, text):
        self.update_file(text + '\n', append=True)
        self.file_size += 1

        if self.file_size > conf.prefs.history_lines * 1.5:
            self.rewrite_file()

    def add_command(self, text):
        if not self.interactive:
            return
        self.current = ''
        self.position = len(self.history)
        if not text:
            return
        if len(self.history) and self.history[-1] == text:
            return
        self.history.append(text)
        drop = len(self.history) - conf.prefs.history_lines
        if drop > 0:
            del self.history[:drop]
        self.position = len(self.history)
        self.add_line_to_file(text)

    def get_history_command(self):
        return self.history[self.position]

    def get_first_command(self):
        self.position = 0
        return self.history[self.position]

    def get_last_command(self):
        self.set_current_last()
        return self.current

    def step_prev(self, current_line):
        if self.position == len(self.history):
            self.current = current_line
        if self.position > 0:
            self.position -= 1
            return True
        return False

    def step_next(self):
        if self.position < (len(self.history) - 1):
            self.position += 1
            return True
        self.position = len(self.history)
        return False

    def get_current(self):
        return self.current

    def get_current_index(self):
        return self.position

    def set_current_index(self, idx):
        if idx <= len(self.history):
            self.position = idx

    def set_current_last(self):
        self.position = len(self.history)

    def find_previous(self, text):
        if self.position >= 1:
            for pos in range(self.position - 1, -1, -1):
                if text.lower() in self.history[pos].lower():
                    return pos
        return -1

    def get_lines(self, max_lines, substr):
        """Returns at most max_lines of history lines, where the last command
        (assumed to be command-history) has been excluded."""
        history = list(self.history)
        if substr is None:
            return history[-max_lines - 1:-1]
        else:
            matching = [x for x in history[:-1] if substr in x]
            return matching[-max_lines:]

def hap_at_exit_handler(cmd, obj): cmd.at_exit()
def hap_continuation_handler(cmd, obj): cmd.started()
def hap_simulation_stopped_handler(cmd, obj, exc, err): cmd.stopped()

class cmd_line:
    def __init__(self, obj, id, interactive, primary, prompt,
                 write, delete_line, disconnect,
                 clear_screen, # optional
                 prompt_end,   # optional
                 bell,
                 cursor_left, cursor_right):
        self.obj = obj
        self.id = id
        self.interactive = interactive
        self.prompt = prompt
        self.terminal_write = write
        self.terminal_delete_line = delete_line
        self.terminal_clear_screen = clear_screen
        self.terminal_cursor_left = cursor_left
        self.terminal_cursor_right = cursor_right
        self.terminal_disconnect = disconnect
        self.terminal_prompt_end = prompt_end
        self.terminal_bell = bell
        #
        self.terminal_new_selection = None
        self.terminal_to_clipboard = None
        #
        self.line = ''
        self.kill_buffer = ''
        self.pos = 0
        self.prompt_end = 0
        self.have_prompt = False
        self.cmd_in_progress = ''
        self.stopped_during_command = False
        self.is_redrawing_prompt = False
        #
        self.history = command_history(interactive)
        self.reverse_search = False
        self.reverse_chars = ''
        self.reverse_prevs = ''
        self.reverse_original_line = ''
        self.reverse_original_pos = 0
        #
        self.selection_left = 0
        self.selection_right = 0
        #
        self.partial_char = ''
        self.last_tab_with_many = False
        self.reset_undo()
        self.save_undo_on_input = False
        self.run_prompt = False # last prompt was printed as running
        self.python_mode = False
        cli.register_cmdline(id, True, interactive, primary)

        # Avoid registering bound methods because the registered callable may
        # not be freed (at least in 4.2); use static functions instead.
        simics.SIM_hap_add_callback("Core_At_Exit",
                                    hap_at_exit_handler, self)
        simics.SIM_hap_add_callback("Core_Continuation",
                                    hap_continuation_handler, self)
        simics.SIM_hap_add_callback("Core_Simulation_Stopped",
                                    hap_simulation_stopped_handler, self)

    def at_exit(self):
        if self.pos == self.prompt_end:
            self.delete_line(0)
        elif self.pos > self.prompt_end:
            self.terminal_write('\n')

    def cleanup(self):
        simics.SIM_hap_delete_callback("Core_At_Exit",
                                       hap_at_exit_handler, self)
        simics.SIM_hap_delete_callback("Core_Continuation",
                                       hap_continuation_handler, self)
        simics.SIM_hap_delete_callback("Core_Simulation_Stopped",
                                       hap_simulation_stopped_handler, self)
        self.at_exit()

    def to_clipboard(self, str):
        if not str:
            # empty strings are not added to clipboard (never?)
            return
        self.kill_buffer = str
        if self.terminal_to_clipboard:
            self.terminal_to_clipboard(str)

    def share_selection(self, new_selection, to_clipboard):
        self.terminal_new_selection = new_selection
        self.terminal_to_clipboard = to_clipboard

    def save_undo(self):
        self.undo_steps.append(self.line[self.prompt_end:])
        # save an undo buffer when getting new normal input
        self.save_undo_on_input = True

    def reset_undo(self):
        self.undo_steps = []
        self.save_undo_on_input = False

    def undo(self):
        if self.undo_steps:
            self.set_current_line(self.undo_steps.pop())
        else:
            self.set_current_line('')

    def started(self):
        self.redraw_prompt(running = True)

    def stopped(self):
        if self.have_prompt:
            self.redraw_prompt(
                lambda: async_print_stop_info(self.id, self.terminal_write),
                running = False)
        else:
            self.stopped_during_command = True

    def print_prompt(self, continuation = False, running = 'prev'):
        if running == 'prev':
            running = self.run_prompt
        self.terminal_write('\033prompt>')
        if self.reverse_search:
            prompt = "(reverse-search) '%s': " % self.reverse_chars
        else:
            prompt = simics.CORE_customize_prompt(
                "running" if running else self.prompt)
            prompt += '>>> ' if self.python_mode else '> '
        if continuation:
            prompt = '.' * (len(prompt) - 1) + " "
        self.last_prompt = prompt
        self.output_string(prompt)
        self.prompt_end = self.pos
        if self.terminal_prompt_end:
            self.terminal_prompt_end(self.pos)
        self.terminal_write('\033/prompt>')
        self.have_prompt = True
        self.run_prompt = running

    def output_string(self, str, restore_cursor = False):
        if self.pos < len(self.line):
            next = self.line[self.pos:]
            self.line = self.line[:self.pos]
        else:
            next = ''
        self.terminal_write(str)
        self.line += str
        self.pos += len(str)
        if next:
            self.output_string(next, True)
        if restore_cursor:
            self.cursor_left(len(str))

    def delete_line(self, start):
        if self.pos > start:
            self.cursor_left(self.pos - start)
        elif start > self.pos:
            self.cursor_right(start - self.pos)
        self.line = self.line[:start]
        if self.interactive:
            self.terminal_delete_line()
        self.pos = len(self.line)

    def delete_left(self, count):
        cmdline_assert(self.pos >= count, 'delete past leftmost position')
        keep = self.line[self.pos:]
        self.delete_line(self.pos - count)
        self.output_string(keep, True)

    def delete_right(self, count):
        cmdline_assert(self.pos + count <= len(self.line),
                       'delete past rightmost position')
        keep = self.line[self.pos + count:]
        self.delete_line(self.pos)
        self.output_string(keep, True)

    def cursor_left(self, count):
        cmdline_assert(self.pos >= count, 'move past leftmost position')
        self.terminal_cursor_left(count)
        self.pos -= count

    def cursor_right(self, count):
        cmdline_assert(self.pos + count <= len(self.line),
                       'move past rightmost position')
        self.terminal_cursor_right(count)
        self.pos += count

    def clear_screen(self):
        if not self.terminal_clear_screen:
            return
        self.terminal_clear_screen()
        old_pos = self.pos
        self.pos = 0
        line = self.line
        self.line = ''
        self.print_prompt()
        self.set_current_line(line[self.prompt_end:])
        self.cursor_left(len(line) - old_pos)

    def char_input_reverse(self, ch):
        new = self.reverse_chars + ch
        # allow search in current one by moving one back
        self.history.set_current_index(self.history.get_current_index() + 1)
        idx = self.history.find_previous(new)
        if idx >= 0:
            self.reverse_chars = new
            self.history.set_current_index(idx)
            self.set_current_line(self.history.get_history_command())
        self.redraw_prompt()

    def char_input(self, ch):
        if self.save_undo_on_input:
            self.save_undo()
            self.save_undo_on_input = False
        self.delete_selection()
        # handle UTF-8
        if self.partial_char:
            char = self.partial_char + bytes([ch])
            self.partial_char = b''
        else:
            char = bytes([ch])
        try:
            ch = codecs.decode(char, 'utf-8')
        except UnicodeDecodeError as msg:
            # is there a better way to find incomplete sequence?
            if 'unexpected end' in str(msg):
                self.partial_char = char
                return
            else:
                print(("Illegal utf-8 sequence: %s" %
                       " ".join('0x%02x' % x for x in char)))
                return

        if self.reverse_search:
            self.char_input_reverse(ch)
        else:
            self.output_string(ch)

    def set_size(self, cols, rows):
        cli.cmdline_set_size(self.id, cols, rows)
        self.redraw_prompt()

    def key_input(self, mod, key):
        if not self.have_prompt:
            return
        if self.reverse_search:
            if mod == simics.Cmd_Line_Mod_Ctrl:
                if key in (ord('m'), ord('j'), ord('a')):
                    self.reverse_ready()
                else:
                    self.control_input_reverse(chr(key))
                    return
            elif mod == simics.Cmd_Line_Mod_None:
                if key == simics.Cmd_Line_Key_Enter:
                    self.reverse_ready()
                elif key == simics.Cmd_Line_Key_Back:
                    self.control_input_reverse('h')
                    return
                elif key < 0x20:
                    self.reverse_ready()
            elif mod == simics.Cmd_Line_Mod_Shift:
                if key < 0x20:
                    self.reverse_ready()
            elif mod == simics.Cmd_Line_Mod_Alt:
                self.reverse_ready()

        if (key != simics.Cmd_Line_Key_Tab
            and not (mod == simics.Cmd_Line_Mod_Ctrl and key == ord('i'))):
            self.last_tab_with_many = False

        if mod == simics.Cmd_Line_Mod_None:
            if key >= 0x20:
                # ordinary text input
                self.char_input(key)
            else:
                self.unmodified_key(key)
        elif mod == simics.Cmd_Line_Mod_Shift:
            self.shift_key(key)
        elif mod == simics.Cmd_Line_Mod_Ctrl:
            ch = chr(key)
            if ch == 'g':
                switch_io_fd()
            elif ch == 'v':
                # overwrite
                self.save_undo()
                self.delete_selection()
            elif ch == 'y' and conf.prefs.readline_shortcuts:
                # overwrite
                self.save_undo()
                self.delete_selection()
            elif ch == 'h':
                if self.selection_left:
                    self.save_undo()
                    self.delete_selection()
                    return
            elif ch not in ('c', 'x'):
                # not for copy and cut
                self.clear_selection()
            if conf.prefs.readline_shortcuts:
                self.readline_control_input(ch)
            else:
                self.windows_control_input(ch)
        elif mod == simics.Cmd_Line_Mod_Alt:
            self.alt_key(key)
        elif mod == simics.Cmd_Line_Mod_Shift | simics.Cmd_Line_Mod_Ctrl:
            self.shift_control_key(key)
        elif mod == simics.Cmd_Line_Mod_Shift | simics.Cmd_Line_Mod_Alt:
            unhandled_key("shift + alt + key", key)

    def unmodified_key(self, key):
        if self.selection_left:
            if key in (simics.Cmd_Line_Key_Back, simics.Cmd_Line_Key_Del):
                self.save_undo()
                self.delete_selection()
                return
            else:
                self.clear_selection()

        if key == simics.Cmd_Line_Key_Up:
            # previous in history
            self.history_previous()
        elif key == simics.Cmd_Line_Key_Down:
            # next in history
            self.history_next()
        elif key == simics.Cmd_Line_Key_Right:
            # move cursor forward
            if self.pos < len(self.line):
                self.cursor_right(1)
        elif key == simics.Cmd_Line_Key_Left:
            # move cursor backward
            if self.pos > self.prompt_end:
                self.cursor_left(1)
        elif key == simics.Cmd_Line_Key_PgUp:
            # first in history
            if self.history.step_prev(self.line[self.prompt_end:]):
                self.set_current_line(self.history.get_first_command())
        elif key == simics.Cmd_Line_Key_PgDn:
            # last in history
            self.set_current_line(self.history.get_last_command())
        elif key == simics.Cmd_Line_Key_Home:
            # move to start of line
            self.cursor_left(self.pos - self.prompt_end)
        elif key == simics.Cmd_Line_Key_End:
            # move to end of line
            self.cursor_right(len(self.line) - self.pos)
        elif key == simics.Cmd_Line_Key_Back:
            # backspace
            self.save_undo()
            if self.pos > self.prompt_end:
                self.delete_left(1)
        elif key == simics.Cmd_Line_Key_Del:
            # delete
            self.save_undo()
            if self.pos < len(self.line):
                self.delete_right(1)
        elif key == simics.Cmd_Line_Key_Tab:
            # tab complete
            self.save_undo()
            self.tab_key()
        elif key == simics.Cmd_Line_Key_Enter:
            self.enter_line()
        elif key == simics.Cmd_Line_Key_Ins:
            pass
        else:
            unhandled_key("key", key)

    def shift_key(self, key):
        if key == simics.Cmd_Line_Key_Left and self.pos > self.prompt_end:
            # select character left
            self.change_selection_left(1)
            self.cursor_left(1)
        elif key == simics.Cmd_Line_Key_Right and self.pos < len(self.line):
            # select character right
            self.change_selection_right(1)
            self.cursor_right(1)
        elif key == simics.Cmd_Line_Key_Home and self.pos > self.prompt_end:
            # select to start of line
            diff = self.pos - self.prompt_end
            self.change_selection_left(diff)
            self.cursor_left(diff)
        elif key == simics.Cmd_Line_Key_End and self.pos < len(self.line):
            # select to end of line
            diff = len(self.line) - self.pos
            self.change_selection_right(diff)
            self.cursor_right(diff)
        elif key == simics.Cmd_Line_Key_Del:
            # cut text
            self.save_undo()
            self.cut_text()
        elif key == simics.Cmd_Line_Key_Ins:
            # paste text
            self.save_undo()
            self.output_string(self.kill_buffer)
        else:
            unhandled_key("shift + key", key)

    def letters_left(self, pos):
        while pos >= self.prompt_end and self.line[pos] not in word_separators:
            pos -= 1
        return pos

    def whitespace_left(self, pos):
        while pos >= self.prompt_end and self.line[pos] in word_separators:
            pos -= 1
        return pos

    def letters_right(self, pos):
        while pos < len(self.line) and self.line[pos] not in word_separators:
            pos += 1
        return pos

    def whitespace_right(self, pos):
        while pos < len(self.line) and self.line[pos] in word_separators:
            pos += 1
        return pos

    def word_left_pos(self, pos = -1):
        if pos < 0:
            pos = self.pos - 1
        return self.letters_left(self.whitespace_left(pos)) + 1

    def word_right_pos(self, pos = -1):
        if pos < 0:
            pos = self.pos
        return self.letters_right(self.whitespace_right(pos))

    def non_ascii_control_input(self, key):
        if key != simics.Cmd_Line_Key_Ins:
            self.save_undo()
            self.clear_selection()
        if key == simics.Cmd_Line_Key_Left and self.pos > self.prompt_end:
            # move word left
            self.cursor_left(self.pos - self.word_left_pos())
        elif key == simics.Cmd_Line_Key_Right and self.pos < len(self.line):
            # move word right
            self.cursor_right(self.word_right_pos() - self.pos)
        elif key == simics.Cmd_Line_Key_Back and self.pos > self.prompt_end:
            # delete word left
            self.save_undo()
            word_start = self.word_left_pos()
            self.to_clipboard(self.line[word_start:self.pos])
            self.delete_left(self.pos - word_start)
        elif key == simics.Cmd_Line_Key_Del and self.pos < len(self.line):
            # delete word right
            self.save_undo()
            word_start = self.word_right_pos()
            self.to_clipboard(self.line[self.pos:word_start])
            self.delete_right(word_start - self.pos)
        elif key == simics.Cmd_Line_Key_Ins:
            self.save_undo()
            # copy text
            self.copy_text()
        elif key == simics.Cmd_Line_Key_Home and self.pos > self.prompt_end:
            # delete to start of line
            self.save_undo()
            self.to_clipboard(self.line[self.prompt_end:self.pos])
            self.delete_left(self.pos - self.prompt_end)
        elif key == simics.Cmd_Line_Key_End and self.pos < len(self.line):
            # delete to end of line
            self.save_undo()
            self.to_clipboard(self.line[self.pos:])
            self.delete_line(self.pos)
        else:
            unhandled_key("ctrl + key", key)

    def transpose_word(self):
        second_end = self.word_right_pos()
        second_start = self.letters_left(second_end - 1) + 1
        if second_start == self.prompt_end:
            # no word to the left
            return
        middle_start = self.whitespace_left(second_start - 1) + 1
        if middle_start == self.prompt_end:
            # no word to the left
            return
        first_start = self.word_left_pos(middle_start - 1)
        first = self.line[first_start:middle_start]
        middle = self.line[middle_start:second_start]
        second = self.line[second_start:second_end]
        rest = self.line[second_end:]
        if self.whitespace_right(second_start) == second_end:
            # second word was only spaces, no real word
            return
        self.delete_line(first_start)
        self.output_string(second + middle + first + rest)
        self.cursor_left(len(rest))

    def alt_key(self, key):
        self.clear_selection()
        if (key in (simics.Cmd_Line_Key_Back, simics.Cmd_Line_Key_Del)
            and self.pos > self.prompt_end):
            # delete word left
            self.save_undo()
            word_start = self.word_left_pos()
            self.to_clipboard(self.line[word_start:self.pos])
            self.delete_left(self.pos - word_start)
        elif key == ord('r'):
            # revert line
            self.reset_undo()
            self.delete_line(self.prompt_end)
        elif key == ord('b'):
            # move word left
            self.cursor_left(self.pos - self.word_left_pos())
        elif key == ord('d'):
            # delete word right
            self.save_undo()
            word_start = self.word_right_pos()
            self.to_clipboard(self.line[self.pos:word_start])
            self.delete_right(word_start - self.pos)
        elif key == ord('f'):
            # move word right
            self.cursor_right(self.word_right_pos() - self.pos)
        elif key == ord('?'):
            # show completions
            self.terminal_write('\n')
            cmps = cli.tab_completions(self.line[self.prompt_end:self.pos])[0]
            cli.print_columns([cli.Just_Left], cmps,
                              has_title = 0, wrap_space = "  ")
            self.redraw_prompt()
        elif key == ord('t'):
            self.transpose_word()
        elif key == ord('u'):
            # uppercase word
            self.save_undo()
            word_end = self.word_right_pos()
            self.line = (self.line[:self.pos]
                         + self.line[self.pos:word_end].upper()
                         + self.line[word_end:])
            self.cursor_right(word_end - self.pos)
            self.redraw_prompt()
        elif key == ord('l'):
            # lowercase word
            self.save_undo()
            word_end = self.word_right_pos()
            self.line = (self.line[:self.pos]
                         + self.line[self.pos:word_end].lower()
                         + self.line[word_end:])
            self.cursor_right(word_end - self.pos)
            self.redraw_prompt()
        elif key == ord('c'):
            # capitalize word
            self.save_undo()
            while (self.pos < len(self.line)
                   and self.line[self.pos] in word_separators):
                self.cursor_right(1)
            word_end = self.word_right_pos()
            self.line = (self.line[:self.pos]
                         + self.line[self.pos:word_end].capitalize()
                         + self.line[word_end:])
            self.cursor_right(word_end - self.pos)
            self.redraw_prompt()
        elif key == ord('<'):
            # first in history
            if self.history.step_prev(self.line[self.prompt_end:]):
                self.set_current_line(self.history.get_first_command())
        elif key == ord('>'):
            # last in history
            self.set_current_line(self.history.get_last_command())
        else:
            unhandled_key("alt + key", key)

    def shift_control_key(self, key):
        # do not clear previous selection since all alternatives extend it
        if key == simics.Cmd_Line_Key_Left and self.pos > self.prompt_end:
            # select word left
            self.change_selection_left(self.pos - self.word_left_pos())
            self.cursor_left(self.pos - self.word_left_pos())
        elif key == simics.Cmd_Line_Key_Right and self.pos < len(self.line):
            # select word right
            self.change_selection_right(self.word_right_pos() - self.pos)
            self.cursor_right(self.word_right_pos() - self.pos)
        elif key == ord('t'):
            self.transpose_word()
        else:
            unhandled_key("shift + ctrl + key", key)

    def set_selection_color(self):
        self.terminal_write('\033select>')

    def set_unselected_color(self):
        self.terminal_write('\033/select>')

    def clear_selection(self):
        clear = self.selection_left > 0
        self.selection_left = 0
        self.selection_right = 0
        if clear:
            # do not redraw unless needed (less confusing for scripted
            # sessions in non-interactive)
            self.redraw_selection(self.selection_left, clear = True)

    def delete_selection(self):
        if self.selection_left == 0:
            return
        self.line = (self.line[:self.selection_left]
                     + self.line[self.selection_right:])
        keep = self.line[self.selection_left:]
        self.delete_line(self.selection_left)
        self.clear_selection() # tell frontend about the change
        self.output_string(keep, restore_cursor = True)

    def redraw_selection(self, leftmost, clear = False):
        if self.selection_left > self.selection_right:
            r = self.selection_right
            self.selection_right = self.selection_left
            self.selection_left = r

        if self.terminal_new_selection:
            # do not highlight selection if handled by frontend
            self.terminal_new_selection(self.selection_left,
                                        self.selection_right)
            return
        elif self.selection_left == 0:
            old_pos = self.pos
            keep = self.line[self.prompt_end:]
            self.delete_line(self.prompt_end)
            self.output_string(keep)
            self.move_cursor(old_pos)
            return

        keep = self.line
        old_pos = self.pos
        self.delete_line(leftmost)
        self.output_string(keep[leftmost:self.selection_left])
        if not clear:
            self.set_selection_color()
        self.output_string(keep[self.selection_left:self.selection_right])
        if not clear:
            self.set_unselected_color()
        self.output_string(keep[self.selection_right:])
        self.move_cursor(old_pos)

    def change_selection_left(self, num):
        if self.pos == self.selection_left:
            self.selection_left -= num
        elif self.pos == self.selection_right:
            self.selection_right -= num
        else:
            # no previous selection
            self.selection_left = self.pos - num
            self.selection_right = self.pos
        self.redraw_selection(self.selection_left)

    def change_selection_right(self, num):
        old_left = self.selection_left
        if self.pos == self.selection_right:
            self.selection_right += num
        elif self.pos == self.selection_left:
            self.selection_left += num
        else:
            # no previous selection
            self.selection_left = self.pos
            self.selection_right = self.pos + num
            old_left = self.selection_left
        self.redraw_selection(min(old_left, self.selection_left))

    def move_cursor(self, new_pos):
        # move cursor to absolute position new_pos
        if new_pos < self.pos:
            self.cursor_left(self.pos - new_pos)
        else:
            self.cursor_right(new_pos - self.pos)

    def reverse_ready(self):
        self.reverse_prevs = self.reverse_chars
        self.reverse_search = False
        self.redraw_prompt()

    def control_input_reverse(self, ch):
        if ch == 'g':
            # stop search
            self.reverse_search = False
            self.reverse_chars = ''
            self.delete_line(0)
            self.print_prompt()
            pos = self.reverse_original_pos
            self.output_string(self.reverse_original_line)
            self.cursor_left(self.pos - pos)
            self.history.set_current_last() # move to end of history
        elif ch == 'r':
            # search for next
            if not self.reverse_chars:
                self.reverse_chars = self.reverse_prevs
                self.redraw_prompt()
            if self.reverse_chars:
                idx = self.history.find_previous(self.reverse_chars)
            else:
                idx = -1
            if idx >= 0:
                self.history.set_current_index(idx)
                line = self.history.get_history_command()
                self.set_current_line(line)
        elif ch == 'h':
            if self.reverse_chars:
                self.reverse_chars = self.reverse_chars[:-1]
                self.redraw_prompt()
        else:
            self.reverse_ready()

    def new_line(self):
        self.cursor_right(len(self.line) - self.pos)
        self.terminal_write('\n')
        self.pos = 0

    def _tab_key(self):
        text = self.line[self.prompt_end:self.pos]
        tail = self.line[self.pos:]
        (cmd, wstart, prefix, comps) = tab_complete(text, tail,
                                                    self.python_mode)
        if not cmd:
            return
        word = text[wstart:]
        if len(comps) > 1:
            if len(prefix) <= len(word):
                if not self.last_tab_with_many:
                    if self.terminal_bell:
                        self.terminal_bell()
                    self.last_tab_with_many = True
                    return
                old_pos = self.pos
                self.new_line()
                cli.print_columns([cli.Just_Left], sorted(set(comps)),
                                  has_title = 0, wrap_space = "  ")
                self.cursor_right(old_pos - self.pos)
            else:
                self.delete_left(len(word))
                self.output_string(prefix)
        else:
            self.set_current_line(cmd)
            if tail:
                self.cursor_left(self.pos - len(prefix) - self.prompt_end
                                 - wstart)

    def tab_key(self):
        old = cli.set_cmdline(self.id)
        self._tab_key()
        cli.set_cmdline(old)

    def cut_text(self):
        if self.selection_left:
            copy = self.line[self.selection_left:self.selection_right]
            self.to_clipboard(copy)
            self.delete_selection()

    def copy_text(self):
        if self.selection_left:
            copy = self.line[self.selection_left:self.selection_right]
            self.to_clipboard(copy)

    def common_control_input(self, ch):
        if ch == 'b':
            # move cursor backward
            if self.pos > self.prompt_end:
                self.cursor_left(1)
        elif ch == 'c':
            # copy text
            self.copy_text()
        elif ch == 'd':
            self.save_undo()
            # delete to the right
            if self.pos < len(self.line):
                self.delete_right(1)
            elif self.pos == len(self.line) and self.pos == self.prompt_end:
                if self.python_mode:
                    self.set_python_mode(False)
                elif simics.SIM_simics_is_running():
                    simics.VT_stop_user(None)
                else:
                    self.terminal_disconnect()
        elif ch == 'e':
            # move to end of line
            self.cursor_right(len(self.line) - self.pos)
        elif ch == 'f':
            # move cursor forward
            if self.pos < len(self.line):
                self.cursor_right(1)
        elif ch == 'g':
            if self.terminal_bell:
                self.terminal_bell()
            if self.cmd_in_progress:
                # interrupt input at the ... prompt
                self.cmd_in_progress = ''
                self.delete_line(0)
                self.print_prompt(continuation = False)
        elif ch == 'h':
            # already saved undo
            # delete to the left
            if self.pos > self.prompt_end:
                self.delete_left(1)
        elif ch == 'i':
            self.save_undo()
            self.tab_key()
        elif ch == 'j':
            self.enter_line()
        elif ch == 'k':
            # kill rest of line
            self.save_undo()
            self.to_clipboard(self.line[self.pos:])
            self.delete_line(self.pos)
        elif ch == 'l':
            # clear screen
            self.clear_screen()
        elif ch == 'm':
            self.enter_line()
        elif ch == 'n':
            # next in history
            self.history_next()
        elif ch == 'o':
            pass
        elif ch == 'p':
            # previous in history
            self.history_previous()
        elif ch == 'q':
            pass
        elif ch == 'r':
            self.reverse_search = True
            self.reverse_chars = ''
            self.reverse_original_line = self.line[self.prompt_end:]
            self.reverse_original_pos = self.pos
            self.redraw_prompt()
        elif ch == 's':
            pass
        elif ch == 't':
            self.save_undo()
            # swap previous two characters
            if self.pos < self.prompt_end + 1:
                pass
            else:
                if self.pos < len(self.line):
                    self.cursor_right(1)
                a = self.line[self.pos - 2]
                b = self.line[self.pos - 1]
                self.delete_left(2)
                self.output_string(b + a)
        elif ch == 'u':
            self.save_undo()
            # delete to start of line
            self.to_clipboard(self.line[self.prompt_end:self.pos])
            self.delete_left(self.pos - self.prompt_end)
        elif ch == 'v':
            # already saved undo
            # paste text
            self.output_string(self.kill_buffer)
        elif ch == 'w':
            self.save_undo()
            # delete word left
            word_start = self.word_left_pos()
            self.to_clipboard(self.line[word_start:self.pos])
            self.delete_left(self.pos - self.word_left_pos())
        elif ch == 'x':
            self.save_undo()
            # cut text
            self.cut_text()
        elif ch == '_':
            # undo changes
            self.undo()
        else:
            self.non_ascii_control_input(ord(ch))

    def windows_control_input(self, ch):
        # some standard ctrl keys at http://support.microsoft.com/kb/126449
        if ch == 'a':
            # select all
            # first move to end of line
            self.cursor_right(len(self.line) - self.pos)
            self.selection_left = self.prompt_end
            self.selection_right = self.pos
            self.redraw_selection(self.selection_left)
        elif ch == 'y':
            pass# windows standard for redo
        elif ch == 'z':
            # windows standard for undo
            self.undo()
        else:
            self.common_control_input(ch)

    def readline_control_input(self, ch):
        if ch == 'a':
            # move to start of line
            self.cursor_left(self.pos - self.prompt_end)
        elif ch == 'y':
            # yank line from kill buffer
            self.output_string(self.kill_buffer)
        elif ch == 'z':
            pass
        else:
            self.common_control_input(ch)

    def redraw_prompt(self, func = lambda: (), running = 'prev'):
        # it is difficult to script sessions if asynchronous output redraws
        # the prompt, only do it in interactive mode
        if (not self.have_prompt or not self.interactive
            or self.is_redrawing_prompt):
            func()
            return
        self.is_redrawing_prompt = True
        line = self.line[self.prompt_end:]
        from_end = len(self.line) - self.pos
        self.delete_line(0)
        func()
        self.print_prompt(running = running)
        self.output_string(line)
        self.cursor_left(from_end)
        self.is_redrawing_prompt = False

    def change_prompt(self, new_prompt):
        self.prompt = new_prompt
        self.redraw_prompt()

    def do_command(self, cmd):
        # Running a blocking command, such as 'continue' in a non-interactive
        # console, will make that console active. cmdline_run_command will
        # temporarily set this console as active. Force output on this console
        # when printing errors since the command was issued in this console
        # (bug 15304).
        if self.python_mode:
            cmd = '@' + cmd
        try:
            error = cli.cmdline_run_command(self.id, cmd.strip())
        except Exception:
            # Catch unexpected errors here, or the command line may end up in
            # an unusable state.
            import traceback
            traceback.print_exc()
            error = None
        if error:
            self.output_from_simics(error + '\n', force = True)
        if self.stopped_during_command:
            # if simulation was run during a command, print new location info
            self.stopped_during_command = False
            print_stop_info(self.id, self.terminal_write)
        self.print_prompt()

    def enter_line(self):
        self.reset_undo()
        self.new_line()
        new_line = self.line[self.prompt_end:]

        cmd = self.cmd_in_progress + new_line + '\n'
        self.history.add_command(new_line)

        self.pos = 0
        self.line = ''
        self.have_prompt = False

        if (cli.complete_command_prefix(cmd, self.python_mode)
            # an empty line ends multi-line input (similar to ctrl-g)
            or (new_line == '' and self.cmd_in_progress)):
            self.cmd_in_progress = ''
            self.do_command(cmd)
        else:
            self.print_prompt(continuation = True)
            self.cmd_in_progress = cmd

    def set_current_line(self, line):
        cmdline_assert(self.pos >= self.prompt_end, 'illegal current position')
        self.delete_line(self.prompt_end)
        self.output_string(line)

    # The force flag can be used to force the message to be printed, even if
    # the console is not active.
    def output_from_simics(self, msg, force = False):
        if not cli.other_cmdline_active(self.id) or force:
            self.redraw_prompt(lambda: self.terminal_write(msg))

    def history_next(self):
        if self.history.step_next():
            cmd = self.history.get_history_command()
        else:
            cmd = self.history.get_current()
        self.set_current_line(cmd)

    def history_previous(self):
        if self.history.step_prev(self.line[self.prompt_end:]):
            self.set_current_line(self.history.get_history_command())

    def get_history(self, max_lines, substr):
        return self.history.get_lines(max_lines, substr)

    def disconnect(self):
        self.terminal_disconnect()

    def new_position(self, pos):
        self.pos = pos

    def selection_from_frontend(self, start, stop):
        self.selection_left = start
        self.selection_right = stop

    def clipboard_from_frontend(self, str):
        self.kill_buffer = str

    def set_python_mode(self, python_mode):
        self.python_mode = python_mode
        self.redraw_prompt()

    def in_python_mode(self):
        return self.python_mode

    def reset(self):
        # called after simics crash
        self.run_prompt = False
        self.reset_undo()
        self.delete_line(0)
        self.print_prompt()

cmdlines = []
next_cmdline = 0

def cmd_output_from_simics(cmd, msg, length):
    cmd.output_from_simics(msg)

def catch_simics_output(cmd_line):
    # Don't register a bound method to avoid a memory leak in 4.2 (bug 15825).
    simics.SIM_add_output_handler(cmd_output_from_simics, cmd_line)
    cmd_line.history.history_from_file()

def command_line_create(obj, interactive, primary):
    if os.getenv("SIMICS_EXPRESS"):
        # Some licenses do not allow the use of command lines
        print("*** Command line error.", file=sys.stderr)
        simics.SIM_quit(1)
    global next_cmdline
    iface = getattr(obj.iface, simics.CMD_LINE_FRONTEND_INTERFACE, None)
    if not iface:
        # error message to C function
        raise Exception("The %s object does not implement the "
                        "%s interface"
                        % (obj.name, simics.CMD_LINE_FRONTEND_INTERFACE))
    cmdline_assert(len(cmdlines) == next_cmdline, 'next_cmdline not in sync')
    cmdlines.append(cmd_line(obj, next_cmdline, interactive, primary,
                             conf.sim.prompt,
                             iface.write, iface.delete_line, iface.disconnect,
                             iface.clear_screen, iface.prompt_end,
                             iface.bell,
                             iface.cursor_left, iface.cursor_right))
    iface = getattr(obj.iface, simics.CMD_LINE_SELECTION_INTERFACE, None)
    if iface:  # optional interface
        cmdlines[next_cmdline].share_selection(iface.new_selection,
                                               iface.to_clipboard)
    catch_simics_output(cmdlines[next_cmdline])
    cmdlines[next_cmdline].print_prompt(running =
                                        simics.SIM_simics_is_running())
    next_cmdline += 1
    return next_cmdline - 1

def command_line_delete(id):
    try:
        cmd_line = cmdlines[id]
        if cmd_line:
            cmd_line.cleanup()
            simics.SIM_remove_output_handler(cmd_output_from_simics, cmd_line)
            # Cannot remove element, since ID is used elsewhere
            cmdlines[id] = None
    except Exception as msg:
        print("Unexpected error in command_line_delete:", msg, file=sys.__stderr__)

def command_line_key(id, mod, key):
    try:
        cmdlines[id].key_input(mod, key)
    except Exception as msg:
        print("Unexpected error in command_line_key:", msg, file=sys.__stderr__)
        print(id, mod, key, file=sys.__stderr__)
        import traceback
        traceback.print_exc()

def command_line_set_size(id, cols, rows):
    try:
        cmdlines[id].set_size(cols, rows)
    except Exception as msg:
        print("Unexpected error in set_screen_size:", msg, file=sys.__stderr__)

def command_line_new_selection(id, left, right):
    try:
        cmdlines[id].selection_from_frontend(left, right)
    except Exception as msg:
        print(("Unexpected error in "
               "command_line_new_selection: %s" % (msg,)), file=sys.__stderr__)

def command_line_new_position(id, pos):
    try:
        cmdlines[id].new_position(pos)
    except Exception as msg:
        print(("Unexpected error in "
               "command_line_new_position: %s" %  (msg,)), file=sys.__stderr__)

def command_line_to_clipboard(id, str):
    try:
        cmdlines[id].clipboard_from_frontend(str)
    except Exception as msg:
        print(("Unexpected error in "
               "command_line_to_clipboard: %s" % (msg,)), file=sys.__stderr__)

def command_line_prompt_changed(new_prompt):
    for cmdline in cmdlines:
        if cmdline:
            cmdline.change_prompt(new_prompt)

def command_line_reset_all():
    for cmdline in cmdlines:
        if cmdline:
            cmdline.reset()

def command_line_reset_io(id):
    # Reset screen
    sys.__stdout__.buffer.write(b"\x1bc")
    sys.__stdout__.flush()
    cmdlines[id].delete_line(0)
    cmdlines[id].print_prompt()

def command_line_in_python_mode(id):
    try:
        return cmdlines[id].in_python_mode()
    except Exception as msg:
        print(("Unexpected error in "
               "command_line_in_python_mode: %s" % (msg,)), file=sys.__stderr__)

def command_line_python_mode(id, python_mode):
    try:
        cmdlines[id].set_python_mode(python_mode)
    except Exception as msg:
        print(("Unexpected error in "
               "command_line_python_mode: %s" % (msg,)), file=sys.__stderr__)

# used by commands.py
def command_line_disconnect(id):
    try:
        cmdlines[id].disconnect()
    except Exception as msg:
        print(("Unexpected error in "
               "command_line_python_mode: %s" % (msg,)), file=sys.__stderr__)

# used by commands.py
def get_command_history(id, max_lines, substr):
    if id >= 0:
        return cmdlines[id].get_history(max_lines, substr)
    else:
        # called before any command-line created
        history = command_history(True)
        history.history_from_file()
        return history.get_lines(max_lines, substr)

###### only used for testing

def debug_get_line(id):
    return cmdlines[id].line

def debug_set_line(id, text):
    cmdlines[id].line = text

def debug_get_pos(id):
    return cmdlines[id].pos

def debug_set_pos(id, pos):
    cmdlines[id].pos = pos

def debug_get_selection(id):
    return (cmdlines[id].selection_left, cmdlines[id].selection_right)

def debug_get_clipboard(id):
    return cmdlines[id].kill_buffer

def debug_set_clipboard(id, text):
    cmdlines[id].kill_buffer = text

def debug_get_prompt(id):
    i = cmdlines[id].interactive
    cmdlines[id].interactive = True
    cmdlines[id].redraw_prompt()
    cmdlines[id].interactive = i
    return cmdlines[id].last_prompt

def default_prompt_customizer(prompt):
    p = cli.get_component_path()
    return prompt + ":" + ".".join(p) if len(p) else prompt

def init_command_line():
    simics.VT_set_prompt_customizer(default_prompt_customizer)
