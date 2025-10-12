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


import simics
import sys

escape_strings = {
    '[A'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Up),
    '[B'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Down),
    '[C'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Right),
    '[D'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Left),
    'OA'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Up),
    'OB'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Down),
    'OC'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Right),
    'OD'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Left),
    '[1;2A' : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_Up),
    '[1;2B' : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_Down),
    '[1;2C' : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_Right),
    '[1;2D' : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_Left),
    '[1;5A' : (simics.Cmd_Line_Mod_Ctrl,  simics.Cmd_Line_Key_Up),
    '[1;5B' : (simics.Cmd_Line_Mod_Ctrl,  simics.Cmd_Line_Key_Down),
    '[1;5C' : (simics.Cmd_Line_Mod_Ctrl,  simics.Cmd_Line_Key_Right),
    '[1;5D' : (simics.Cmd_Line_Mod_Ctrl,  simics.Cmd_Line_Key_Left),
    '[1;3A' : (simics.Cmd_Line_Mod_Alt,   simics.Cmd_Line_Key_Up),
    '[1;3B' : (simics.Cmd_Line_Mod_Alt,   simics.Cmd_Line_Key_Down),
    '[1;3C' : (simics.Cmd_Line_Mod_Alt,   simics.Cmd_Line_Key_Right),
    '[1;3D' : (simics.Cmd_Line_Mod_Alt,   simics.Cmd_Line_Key_Left),
    '[1;4A' : (simics.Cmd_Line_Mod_Shift
               | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_Up),
    '[1;4B' : (simics.Cmd_Line_Mod_Shift
               | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_Down),
    '[1;4C' : (simics.Cmd_Line_Mod_Shift
               | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_Right),
    '[1;4D' : (simics.Cmd_Line_Mod_Shift
               | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_Left),
    '[1;2~' : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Home),
    '[5~'   : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_PgUp),
    '[5;2~' : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_PgUp),
    '[6~'   : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_PgDn),
    '[6;2~' : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_PgDn),
    '[5;5~' : (simics.Cmd_Line_Mod_Ctrl,  simics.Cmd_Line_Key_PgUp),
    '[6;5~' : (simics.Cmd_Line_Mod_Ctrl,  simics.Cmd_Line_Key_PgDn),
    '[5;3~' : (simics.Cmd_Line_Mod_Alt,   simics.Cmd_Line_Key_PgUp),
    '[6;3~' : (simics.Cmd_Line_Mod_Alt,   simics.Cmd_Line_Key_PgDn),
    '[H'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Home),
    'OH'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Home),

    'OP'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F1),
    'OQ'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F2),
    'OR'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F3),
    'OS'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F4),

    'Ow'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F5),
    'Ox'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F6),
    'Oy'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F7),
    'Om'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F8),
    'Ot'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F9),
    'Ou'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F10),
    'Ov'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F11),
    'Ol'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F12),

    '[15~'  : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F5),
    '[17~'  : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F6),
    '[18~'  : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F7),
    '[19~'  : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F8),
    '[20~'  : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F9),
    '[21~'  : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F10),
    '[23~'  : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F11),
    '[24~'  : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_F12),

    'O1;2P'  : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_F1),
    'O1;2Q'  : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_F2),
    'O1;2R'  : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_F3),
    'O1;2S'  : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_F4),
    '[15;2~' : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_F5),
    '[17;2~' : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_F6),
    '[18;2~' : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_F7),
    '[19;2~' : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_F8),
    '[20;2~' : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_F9),
    '[21;2~' : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_F10),
    '[23;2~' : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_F11),
    '[24;2~' : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_F12),

    'O1;5P'  : (simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F1),
    'O1;5Q'  : (simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F2),
    'O1;5R'  : (simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F3),
    'O1;5S'  : (simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F4),
    '[15;5~' : (simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F5),
    '[17;5~' : (simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F6),
    '[18;5~' : (simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F7),
    '[19;5~' : (simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F8),
    '[20;5~' : (simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F9),
    '[21;5~' : (simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F10),
    '[23;5~' : (simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F11),
    '[24;5~' : (simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F12),

    'O1;3P'  : (simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F1),
    'O1;3Q'  : (simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F2),
    'O1;3R'  : (simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F3),
    'O1;3S'  : (simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F4),
    '[15;3~' : (simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F5),
    '[17;3~' : (simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F6),
    '[18;3~' : (simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F7),
    '[19;3~' : (simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F8),
    '[20;3~' : (simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F9),
    '[21;3~' : (simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F10),
    '[23;3~' : (simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F11),
    '[24;3~' : (simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F12),

    'O1;6P'  : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F1),
    'O1;6Q'  : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F2),
    'O1;6R'  : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F3),
    'O1;6S'  : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F4),
    '[15;6~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F5),
    '[17;6~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F6),
    '[18;6~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F7),
    '[19;6~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F8),
    '[20;6~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F9),
    '[21;6~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F10),
    '[23;6~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F11),
    '[24;6~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_F12),

    'O1;4P'  : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F1),
    'O1;4Q'  : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F2),
    'O1;4R'  : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F3),
    'O1;4S'  : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F4),
    '[15;4~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F5),
    '[17;4~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F6),
    '[18;4~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F7),
    '[19;4~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F8),
    '[20;4~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F9),
    '[21;4~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F10),
    '[23;4~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F11),
    '[24;4~' : (simics.Cmd_Line_Mod_Shift
                | simics.Cmd_Line_Mod_Alt, simics.Cmd_Line_Key_F12),

    '[1;2H' : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Home),
    '[1~'   : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Home), # putty
    '[F'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_End),
    'OF'    : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_End),
    '[1;2F' : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_End),
    '[4~'   : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_End), # putty
    '[2~'   : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Ins),
    '[2;2~' : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Ins),
    '[Z'    : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_Tab),
    '[3~'   : (simics.Cmd_Line_Mod_None,  simics.Cmd_Line_Key_Del),
    '[3;2~' : (simics.Cmd_Line_Mod_Shift, simics.Cmd_Line_Key_Del),
    '[3;5~' : (simics.Cmd_Line_Mod_Ctrl,  simics.Cmd_Line_Key_Del),
    '[3;3~' : (simics.Cmd_Line_Mod_Alt,   simics.Cmd_Line_Key_Del),
    '[1;6A' : (simics.Cmd_Line_Mod_Shift
               |simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_Up),
    '[1;6B' : (simics.Cmd_Line_Mod_Shift
               |simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_Down),
    '[1;6C' : (simics.Cmd_Line_Mod_Shift
               |simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_Right),
    '[1;6D' : (simics.Cmd_Line_Mod_Shift
               |simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_Left),

    '[7~' : (simics.Cmd_Line_Mod_None, simics.Cmd_Line_Key_Home),  # rxvt
    '[8~' : (simics.Cmd_Line_Mod_None, simics.Cmd_Line_Key_End),   # rxvt
    'Od'  : (simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_Left),  # rxvt
    'Oc'  : (simics.Cmd_Line_Mod_Ctrl, simics.Cmd_Line_Key_Right), # rxvt
}

tag_strings = {
    "b"       : '\033[1m',
    "/b"      : '\033[0m', # TODO: do not restore other formatting
    "i"       : '\033[3m',
    "/i"      : '\033[0m', # TODO: do not restore other formatting
    "prompt"  : '\033[1m\033[34m',
    "/prompt" : '\033[0m',
    "select"  : '\033[7m\033[34m',
    "/select" : '\033[0m'
}

def ascii_to_key(val):
    if val < 27:
        return (simics.Cmd_Line_Mod_Ctrl, val + 96)
    elif val < 32:
        # not sure what 27 and 29 are
        keys = [0, ord('\\'), 0, ord('^'), ord('_')]
        key = keys[val - 27]
        if key == 0:
            key = ord('_') # pick some unmapped
        return (simics.Cmd_Line_Mod_Ctrl, key)
    else:
        return (simics.Cmd_Line_Mod_None, val)

def delete_term_object(obj):
    obj.frontend = None
    simics.SIM_delete_object(obj)

colorize_default = True

class terminal_frontend:
    # Instance constructor
    def __init__(self, obj):
        self.obj = obj
        self.frontend = None
        self.session_id = 0
        self.term_iface = None
        self.cmdline = -1
        self.reset_escape()
        self.colorize = colorize_default
        self.interactive = True
        self.primary = True
        self.width = 80
        self.row = 0 # cursor offset from prompt row
        self.col = 0 # current cursor column
        self.max_row = 0
        self.buf = []
        self.enable_output = True

    def finalize_instance(self):
        self.cmdline = simics.VT_command_line_create(self.obj,
                                                     self.interactive,
                                                     self.primary)

    def get_session_id(self):
        return self.session_id

    def set_session_id(self, val):
        self.session_id = val
        return simics.Sim_Set_Ok

    def get_interactive(self):
        return self.interactive

    def set_interactive(self, val):
        if self.obj.configured:
            return simics.Sim_Set_Illegal_Value
        self.interactive = val
        return simics.Sim_Set_Ok

    def get_primary(self):
        return self.primary

    def set_primary(self, val):
        if self.obj.configured:
            return simics.Sim_Set_Illegal_Value
        self.primary = val
        return simics.Sim_Set_Ok

    def get_frontend(self):
        return self.frontend

    def set_frontend(self, val):
        if not val:
            self.term_iface = None
            self.frontend = None
            return simics.Sim_Set_Ok
        try:
            self.term_iface = simics.SIM_get_interface(
                val, simics.TERMINAL_CLIENT_INTERFACE)
        except simics.SimExc_General:
            simics.SIM_attribute_error(
                "The %s object does not implement the %s interface"
                % (val.name, simics.TERMINAL_CLIENT_INTERFACE))
            return simics.Sim_Set_Interface_Not_Found
        self.frontend = val
        return simics.Sim_Set_Ok

    def get_colorize(self):
        return self.colorize

    def set_colorize(self, val):
        self.colorize = val
        return simics.Sim_Set_Ok

    def reset_escape(self):
        self.have_escape = False
        self.escape_string = ''

    def terminal_set_size(self, x, y):
        assert x > 0
        self.width = x
        simics.VT_command_line_set_size(self.cmdline, x, y)

    def terminal_input(self, text):
        # split in UTF-8 to send byte-by-byte to command-line
        self.buf = list(text.encode('UTF-8'))
        while self.buf:
            self.terminal_input_char(self.buf.pop(0))

    def terminal_input_char(self, ch):
        if self.have_escape:
            if self.escape_string == '' and ch not in (0x5b, 0x4f): # not [, O
                if ch == 0x08:
                    ch = simics.Cmd_Line_Key_Back
                elif ch == 0x0a:
                    ch = simics.Cmd_Line_Key_Enter
                elif ch == 0x7f:
                    ch = simics.Cmd_Line_Key_Del
                simics.VT_command_line_key(self.cmdline,
                                           simics.Cmd_Line_Mod_Alt, ch)
                self.reset_escape()
                return
            self.escape_string += chr(ch)
            if not self.escape_string in escape_strings:
                for esc in list(escape_strings.keys()):
                    if esc.startswith(self.escape_string):
                        # not done yet
                        return
                print((
                    "Got unsupported escape sequence: %s"
                    % " ".join('0x%02x' % ord(x)
                               for x in self.escape_string)), file=sys.__stderr__)
                self.reset_escape()
                return
            (mod, key) = escape_strings[self.escape_string]
            simics.VT_command_line_key(self.cmdline, mod, key)
            self.reset_escape()
            return

        if ch == 0x1b:
            self.have_escape = True
        elif ch == 0x7f:
            simics.VT_command_line_key(self.cmdline,
                                       simics.Cmd_Line_Mod_None,
                                       simics.Cmd_Line_Key_Back)
        else:
            (mod, key) = ascii_to_key(ch)
            try:
                simics.VT_command_line_key(self.cmdline, mod, key)
            except Exception as msg:
                print(("error sending key '0x%x' "
                                          "(0x%x 0x%x) to cmd-line: %s"
                                          % (ch, mod, key, msg)), file=sys.__stderr__)

    def raw_write(self, text):
        if self.enable_output:
            self.term_iface.write(self.session_id, text)

    def update_position(self, text):
        line_length = self.col + len(text)
        self.row += line_length // self.width
        if text.endswith('\n'):
            self.row += 1
        self.col = line_length % self.width
        self.max_row = max(self.row, self.max_row)
        return line_length == self.width

    def output_text(self, text):
        self.raw_write(text)
        if self.update_position(text):
            # the cursor doesn't wrap to the next line at once after writing
            # the last character (still a few cases where this does not work)
            self.raw_write('\033[%dD' % self.width) # left
            self.raw_write('\n')                    # down, force scroll at end

    def write_line(self, text):
        strs = text.split('\033')
        self.output_text(strs[0])
        for st in strs[1:]:
            if '>' in st:
                tag, txt = st.split('>', 1)
                if self.colorize:
                    self.raw_write(tag_strings.get(tag, ''))
            else:
                if self.colorize:
                    # keep any escape sequence unchanged in colorize mode
                    txt = '\033' + st
                else:
                    txt = st
            self.output_text(txt)

    def write(self, text):
        # do not choke the terminal with more that one line at a time
        lines = text.split('\n')
        for line in lines[:-1]:
            self.write_line(line)
            if self.col != 0 or len(line) == 0:
                # no new line if already wrapped
                self.raw_write('\n')
            self.row = 0
            self.col = 0
        self.write_line(lines[-1])

    def clear_screen(self):
        self.row = 0
        self.col = 0
        self.max_row = 0
        self.raw_write('\033[2J') # clear screen
        self.raw_write('\033[0;0H') # cursor to 0,0

    def prompt_end(self, pos):
        self.row = 0
        self.max_row = 0

    def bell(self):
        self.raw_write('\007')

    def cleanup(self):
        simics.VT_command_line_delete(self.cmdline)
        self.buf = []  #  drain the input buffer (bug 23860)
        self.cmdline = -1
        try:
            self.term_iface.disconnect(self.session_id)
        except Exception as msg:
            print(("Failed disconnecting session %d in %s: %s"
                   % (self.frontend, self.session_id, msg)))

    def disconnect(self):
        self.cleanup()
        simics.SIM_register_work(delete_term_object, self.obj)

    def delete_line(self):
        # delete current line, and all following lines
        self.raw_write('\033[K')              # delete eol
        if self.col:
            self.raw_write('\033[%dD' % self.col) # left
        for row in range(self.row, self.max_row):
            self.raw_write('\033[1B')                   # down
            self.raw_write('\033[K')                    # delete eol
        for row in range(self.row, self.max_row):
            self.raw_write('\033[1A')                   # up
        if self.col:
            self.raw_write('\033[%dC' % self.col)       # right
        self.max_row = self.row

    def cursor_left(self, count):
        if count > self.col:
            # wrap to previous line
            self.raw_write('\033[1A') # up
            self.raw_write('\033[%dC' % (self.width - self.col + 1)) # right
            self.row -= 1
            count -= self.col + 1
            self.col = self.width - 1
        while count > self.width:
            # up to destination line
            self.row -= 1
            self.raw_write('\033[1A') # up
            count -= self.width
        if count:
            # finally move left
            self.col -= count
            self.raw_write('\033[%dD' % count) # left

    def cursor_right(self, count):
        if self.col + count >= self.width:
            # wrap to next line
            self.raw_write('\033[1B')             # down
            self.raw_write('\033[%dD' % self.col) # left
            self.row += 1
            count -= self.width - self.col
            self.col = 0
        while self.col + count >= self.width:
            # down to destination line
            self.row += 1
            self.raw_write('\033[1B') # down
            count -= self.width
        if count:
            # finally move right
            self.col += count
            self.raw_write('\033[%dC' % count) # right

def get_colorize_default(conf_class):
    return colorize_default

def set_colorize_default(conf_class, val):
    global colorize_default
    colorize_default = val
    return simics.Sim_Set_Ok

def po(obj):
    return obj.object_data

def init_object_wrapper(obj):
    return terminal_frontend(obj)

def delete_instance(obj):
    if po(obj).cmdline != -1:
        # if deleted explicitly and not as part of normal disconnect
        po(obj).cleanup()
    po(obj).obj = None

class_data = simics.class_info_t(
    init      = init_object_wrapper,
    finalize  = lambda obj: po(obj).finalize_instance(),
    deinit    = delete_instance,
    kind      = simics.Sim_Class_Kind_Pseudo,
    short_desc = "access to Simics CLI",
    description = """\
(Internal)
The <class>terminal_frontend</class> class provides access to a Simics
command line using a generic VT100/ANSI interface. Input and output to the user
is handled by a separate object, specified by the <attr>frontend</attr>
attribute, that must implement the <iface>terminal_client</iface> interface
and communicate with the <class>terminal_frontend</class> object using the
<iface>terminal_server</iface> interface.
""")

simics.SIM_create_class('terminal_frontend', class_data)

# terminal server interface

term_iface = simics.terminal_server_interface_t(
    write      = lambda obj, text: po(obj).terminal_input(text),
    set_size   = lambda obj, x, y: po(obj).terminal_set_size(x, y),
    disconnect = lambda obj: po(obj).disconnect())
simics.SIM_register_interface('terminal_frontend',
                              simics.TERMINAL_SERVER_INTERFACE, term_iface)

# cmd-line frontend interface

cmd_line_iface = simics.cmd_line_frontend_interface_t(
    write        = lambda obj, text: po(obj).write(text),
    delete_line  = lambda obj: po(obj).delete_line(),
    disconnect   = lambda obj: po(obj).disconnect(),
    clear_screen = lambda obj: po(obj).clear_screen(),
    prompt_end   = lambda obj, pos: po(obj).prompt_end(pos),
    bell         = lambda obj: po(obj).bell(),
    cursor_left  = lambda obj, num: po(obj).cursor_left(num),
    cursor_right = lambda obj, num: po(obj).cursor_right(num))

simics.SIM_register_interface('terminal_frontend',
                              simics.CMD_LINE_FRONTEND_INTERFACE,
                              cmd_line_iface)

simics.SIM_register_attribute(
    'terminal_frontend', 'frontend',
    lambda obj: po(obj).get_frontend(),
    lambda obj, val: po(obj).set_frontend(val),
    simics.Sim_Attr_Required,
    "o|n",
    "Object responsible for presenting terminal output to the user and "
    "reading input. This object must implement the "
    "<iface>terminal_client</iface> interface.")

simics.SIM_register_attribute(
    'terminal_frontend', 'session_id',
    lambda obj: po(obj).get_session_id(),
    lambda obj, val: po(obj).set_session_id(val),
    simics.Sim_Attr_Required,
    "i",
    "The identifier of the session in the object specified by the "
    "<attr>frontend</attr> attribute. Needed since such objects may have "
    "multiple concurrent sessions active.")

simics.SIM_register_attribute(
    'terminal_frontend', 'interactive',
    lambda obj: po(obj).get_interactive(),
    lambda obj, val: po(obj).set_interactive(val),
    simics.Sim_Attr_Optional,
    "b",
    "Set to TRUE (default) if the command line is interactive.")

simics.SIM_register_attribute(
    'terminal_frontend', 'primary',
    lambda obj: po(obj).get_primary(),
    lambda obj, val: po(obj).set_primary(val),
    simics.Sim_Attr_Optional,
    "b",
    "Set to TRUE (default) if the command line is a primary one. In a primary "
    "command line the quit command will terminate the Simics process, "
    "something not allowed in secondary command-lines such as the "
    "telnet-frontend.")

simics.SIM_register_attribute(
    'terminal_frontend', 'colorize',
    lambda obj: po(obj).get_colorize(),
    lambda obj, val: po(obj).set_colorize(val),
    simics.Sim_Attr_Optional,
    "b",
    "Set to TRUE if the output should contain color and other formatting"
    " escape sequences. The <attr>colorize_default</attr> attribute is used"
    " as the initial value.")

simics.SIM_register_class_attribute(
    'terminal_frontend', 'colorize_default',
    get_colorize_default,
    set_colorize_default,
    simics.Sim_Attr_Pseudo,
    "b",
    "Default value for the <attr>colorize</attr> attribute when new objects"
    " are created.")
