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

import cli
import simics
import itertools as it
import debugger_commands
import re
import table
from . import tcf_common as tcfc

def sym_write_cmd(st, variable_name, value):
    use_integer_value = isinstance(value, int)
    if use_integer_value:
        floating_point_value = 0
        integer_value = cli.global_cmds.unsigned64(int=value)
    else:
        integer_value = 0
        floating_point_value = value

    # write new value
    (ok, res) = st.iface.symdebug.lvalue_write(
        tcfc.Debug_state.debug_state(st).frame, 0, variable_name,
        use_integer_value, integer_value, floating_point_value)
    if not ok:
        raise cli.CliError(res)

    # read value and return
    (ok, data) = tcfc.sym_value_impl(
        st.cid, tcfc.Debug_state.debug_state(st).frame, variable_name)
    if not ok:
        raise cli.CliError(value)
    (value_str, value) = data
    return cli.command_return(
        value = value, message = f'{variable_name} = {value_str}')


def print_frame(st, frame_no, frame):
    print(tcfc.get_frame_string(st, frame_no, frame))

def stack_trace_cmd(st, maxdepth):
    (success, frames) = st.iface.symdebug.stack_frames(0, maxdepth - 1)
    if not success:
        raise cli.CliError("Failed getting stack-trace: %s" % frames)
    for (i, f) in enumerate(frames):
        print_frame(st, i, f)


def frame_cmd(st, frame_no):
    if frame_no == None:
        frame_no = tcfc.Debug_state.debug_state(st).frame
    if frame_no < 0:
        print("Cannot go that far down the stack.")
        return
    (success, frames) = st.iface.symdebug.stack_frames(frame_no, frame_no)
    if not success or not frames:
        raise cli.CliError('Frame %d not found' % frame_no)
    else:
        print_frame(st, frame_no, frames[0])
    tcfc.Debug_state.debug_state(st).frame = frame_no


def up_cmd_repeat(st, _):
    # Repeat with one step at a time regardless of initial n.
    up_cmd(st, 1)

def up_cmd(st, n):
    f = tcfc.Debug_state.debug_state(st).frame
    frame_cmd(st, f + n)


def down_cmd_repeat(st, _):
    # Repeat with one step at a time regardless of initial n.
    down_cmd(st, 1)

def down_cmd(st, n):
    f = tcfc.Debug_state.debug_state(st).frame
    frame_cmd(st, f - n)


def sym_value_cmd(st, expr):
    ctx_id = st.cid
    frame = tcfc.Debug_state.debug_state(st).frame
    (success, data) = tcfc.sym_value_impl(ctx_id, frame, expr)
    if not success:
        raise cli.CliError(data)
    (value_str, value) = data
    return cli.command_return(value = value, message = value_str)


def sym_type_cmd(st, expr):
    ctx_id = st.cid
    frame = tcfc.Debug_state.debug_state(st).frame
    (success, res) = tcfc.sym_type_impl(ctx_id, frame, expr)
    if not success:
        raise cli.CliError(res)
    return cli.command_return(value = res, message = res)


def sym_list_cmd(st, glbls, lcls, fncts, substr, regex,
                 sort_by_address, show_all_rows):
    ctx_id = st.cid
    frame = tcfc.Debug_state.debug_state(st).frame
    if not glbls and not lcls and not fncts:
        glbls = True
        lcls = True
    (success, value) = tcfc.sym_list_impl(ctx_id, frame, substr,
                                          regex, glbls, lcls, fncts)

    if not success:
        raise cli.CliError(value)

    if sort_by_address:
        value.sort(key = lambda a : [a[3] if isinstance(a[3], int) else 0, a])
    else:
        value.sort()

    properties = [(table.Table_Key_Columns, [
        [(table.Column_Key_Name, "Symbol")],
        [(table.Column_Key_Name, "Kind")],
        [(table.Column_Key_Name, "Type")],
        [(table.Column_Key_Name, "Address"),
         (table.Column_Key_Int_Radix, 16),
         (table.Column_Key_Int_Pad_Width, 16)],
        [(table.Column_Key_Name, "Size")]])]

    max_rows = 0 if show_all_rows else 100

    tbl = table.Table(properties, value)
    msg = tbl.to_string(no_row_column=True, rows_printed=max_rows)
    return cli.command_verbose_return(message = msg, value = value)


def sym_address_cmd(st, poly):
    path = None
    expr = None
    if poly[0] == cli.uint_t:
        line = poly[1]
    else:
        mo = re.match(r'(.*?):(\d*)', poly[1])
        if mo and len(mo.groups()) == 2:
            try:
                line = int(mo.group(2))
                path = mo.group(1)
            except ValueError:
                pass
        if not path:
            expr = poly[1]
    if expr:
        (success, value) = st.iface.symdebug.lvalue_address(
            tcfc.Debug_state.debug_state(st).frame, 0, expr)
    else:
        if not path:
            frame_no = tcfc.Debug_state.debug_state(st).frame
            (success, frames) = st.iface.symdebug.stack_frames(frame_no,
                                                               frame_no)
            if success and len(frames):
                [frame] = frames
                path = (frame['fullname'] if 'fullname' in frame
                        else frame['file'] if 'file' in frame else None)
            else:
                raise cli.CliError("Cannot find current stack frame")
        if not path:
            raise cli.CliError(
                "Cannot find source file for current stack frame")
        (success, value) = st.iface.symdebug.source_address(path, line)
    if not success:
        raise cli.CliError(value)
    return value[0]['start_addr'] if isinstance(value, list) else value


def string_return(value):
    return cli.command_return(value = value, message = cli.format_attribute(
        value, True))

def string_from_address(symdebug, addr):
    (success, value) = symdebug.address_string(addr)
    if not success:
        raise cli.CliError(value)
    return string_return(value)

def char_array_to_string(char_type_array):
    assert isinstance(char_type_array, list), f'Not a list: {char_type_array}'
    char_array = [c for (_, c) in char_type_array]
    string_end = char_array.index(0) if 0 in char_array else len(char_array)
    return "".join([chr(c) for c in char_array[:string_end]])

def string_from_expression(symdebug, frame, expr):
    (success, value) = symdebug.expr_value(frame, 0, expr)
    if not success:
        raise cli.CliError(value)

    if not ((isinstance(value, list)
             and (value[0] == '*' or value[0] == '[]')
             and 'char' in value[1])):
        raise cli.CliError(f"'{expr}' does not reference a string.")

    if value[0] == '[]': # a char array
        str_value = char_array_to_string(value[2])
        return string_return(str_value)

    addr = value[-1]
    return string_from_address(symdebug, addr)

def sym_string_cmd(st, poly):
    if isinstance(poly[0], cli.range_t):
        return string_from_address(st.iface.symdebug, poly[1])
    return string_from_expression(
        st.iface.symdebug, tcfc.Debug_state.debug_state(st).frame, poly[1])


def source_by_address(st, addr):
    (success, value) = st.iface.symdebug.address_source(addr)
    if not success:
        raise cli.CliError(value)
    if not value:
        raise cli.CliError('No source found')
    [_, _, filename, line, _, _, _, func] = value[0]
    return (filename, line, func)

def find_source_location(st, poly):
    if poly[0] == cli.uint64_t:
        addr = poly[1]
    else:
        (success, value) = st.iface.symdebug.expr_type(
            tcfc.Debug_state.debug_state(st).frame, 0, poly[1])
        if not success:
            raise cli.CliError("Undefined symbol: %s" % poly[1])
        if (not isinstance(value, list) or (value[0] not in ['()', '*']) or (value[0] == '*' and not isinstance(value[1], list) and value[1][0] != '()')):
            raise cli.CliError("Symbol %s is not a function" % poly[1])

        (success, addr) = st.iface.symdebug.lvalue_address(
            tcfc.Debug_state.debug_state(st).frame, 0, poly[1])
        if not success:
            raise cli.CliError(addr)
    return source_by_address(st, addr)

def sym_source_cmd(st, poly):
    (file, line, func) = find_source_location(st, poly)
    if not file and not func:
        ref = "0x%x" % poly[1] if poly[0] == cli.uint64_t else poly[1]
        raise cli.CliError("No source found for %s" % ref)
    if not func:
        # if no function found, file is probably None as well
        func = '??'
    if poly[0] == cli.uint64_t:
        output = "0x%x in %s" % (poly[1], func)
    else:
        if not func:
            raise cli.CliError("No source found for %s" % poly[1])
        output = "%s" % func
    if file:
        (success, path) = st.iface.symdebug.source_path(file)
        if not success:
            # If we can't find the source file just give the file name
            # from the debug information as a fallback
            path = file
        output += " at %s:%d" % (path, line)
    else:
        path = None
    return cli.command_return(value = [path, line, func], message = output)


def sym_file_cmd(st, poly):
    (file, line, func) = find_source_location(st, poly)
    if not file:
        ref = "0x%x" % poly[1] if poly[0] == cli.uint64_t else poly[1]
        raise cli.CliError('No source file found for %s' % ref)
    (success, path) = st.iface.symdebug.source_path(file)
    if not success:
        raise cli.CliError(path)
    return path


def sym_line_cmd(st, poly):
    (file, line, func) = find_source_location(st, poly)
    if not line:
        ref = "0x%x" % poly[1] if poly[0] == cli.uint64_t else poly[1]
        raise cli.CliError('No source line found for %s' % ref)
    return line


def sym_function_cmd(st, addr):
    (file, line, func) = source_by_address(st, addr)
    if not func:
        raise cli.CliError('No function found for address 0x%x' % addr)
    return func


def source_lines(lines, line, endline=None):
    """Generate and number the lines in lines between line and endline.

    The lines are numbered from 1, as they are expected to come from a
    source file."""
    for (i, l) in enumerate(lines, 1):
        if i < line:
            continue  # forward to the first requested line
        if not endline or i < endline:
            yield (i, l.rstrip())
        else:
            return  # we are done

def marked_source(f, line, current_line):
    with f:  # ensures that file will be closed once reading is done
        for (i, l) in source_lines(f, line):
            yield f"{'->' if i == current_line else '  '} {i:5d}  {l}"

def addr_prefix(dbg):
    (ok, linear) = dbg.currently_uses_linear_addresses()
    return 'l' if (ok and linear) else 'v'

def disasm_lines(dbg, cpu, address, current_address, print_source=False):
    """Generate disassembly listing with the current instruction highlighted.

    Optionally include the source lines.
    """
    prev_line = None
    prev_file = None
    di = cpu.iface.processor_cli
    if not di:
        raise cli.CliError("Disassembly not supported by %s" % cpu.name)
    prefix = addr_prefix(dbg)
    get_disassembly = lambda a: di.get_disassembly(prefix, a, False, None)

    # The interfaces used here require that the address fits inside a 64-bit
    # word. Therefor we check that address is strictly less than (1 << 64)
    # (bug 23397).
    limit = 1 << 64
    while address < limit:
        (ok, res) = dbg.address_source(address)
        if ok and res:
            # We only expect one code area for each address. Ignore
            # additional areas.
            [start, end, file, first_line, _, last_line, _, _] = res[0]
            if print_source and (prev_line != first_line or prev_file != file):
                if prev_file != file:
                    yield file
                (ok, xlated) = dbg.source_path(file)
                if ok:
                    # Avoid keeping the file open while yielded
                    with open(xlated, errors="replace") as f:
                        lines = list(source_lines(f, first_line, last_line))
                    for (i, l) in lines:
                        yield "{0:5d} {1}".format(i, l)
                prev_line = first_line
                prev_file = file
        else:
            # Set 'end' to be an exclusive minimal limit for a disassembly
            # range inside the 64-bit memory space (bug 23397).
            end = min(address + 1, limit)

        while address < end:
            (size, disasm) = get_disassembly(address)
            marker = '->' if address == current_address else '  '
            yield '%s %s' % (marker, disasm)
            if size <= 0:
                return
            address += size

def list_generated(gen, maxlines):
    count = 0
    while count < maxlines:
        try:
            print(next(gen))
        except StopIteration:
            return
        count += 1

def get_frame_location(symdebug, frame):
    (success, frames) = symdebug.stack_frames(frame, frame)
    if success and frames:
        (addr, file, line) = tuple(frames[0][k]
                                   for k in ('addr', 'file', 'line'))
        if (addr or (file and line)):
            return (addr, file, line)
    raise cli.CliError('No current location, so a location must be specified')

def parse_location(symdebug, frame, location):
    '''Parse location into (addr, filename, line).

    If the function fails it will raise a CliError. If it succeeds
    it will return either a valid addr or valid filename and line
    (or all three will be valid).
    '''
    if location:
        location = location[1]

    if isinstance(location, str):
        location = location.rsplit(':', 1)
        if len(location) == 2 and location[1].isdigit():
            # it's a file:line
            return (None, location[0], int(location[1]))
        elif len(location) == 1 and location[0].isdigit():
            # it's a line number
            (_, filename, _) = get_frame_location(symdebug, frame)
            if not filename:
                raise cli.CliError(
                    'No file found for the selected stack frame')
            return (None, filename, int(location[0]))
        elif len(location) == 2:
            # It's file:function. We don't have an API to look up
            # functions scoped to a particular file. Let's bail
            # for now.
            raise cli.CliError(
                'Looking up function scoped to a file not supported')
        else:
            # it's a plain location expression
            func = location[0]
            (success, addr) = symdebug.lvalue_address(frame, 0, func)
            if not success:
                raise cli.CliError(addr)
            return (addr, None, None)
    elif isinstance(location, int):
        return (location, None, None)
    else:
        return get_frame_location(symdebug, frame)

def list_cmd(st, flags, location, maxlines):
    s_flag = (flags and flags[2] == '-s')
    d_flag = (flags and flags[2] == '-d')

    if not maxlines:
        maxlines = 5

    symdebug = st.iface.symdebug
    frame = tcfc.Debug_state.debug_state(st).frame

    (addr, filename, line) = parse_location(symdebug, frame, location)

    # Address must fit inside a 64-bit word because this is required by the
    # used interfaces (bug 23397).
    if addr is not None and addr >= 1 << 64:
        raise cli.CliError("Address 0x%x is out of range" % addr)

    if s_flag or d_flag:
        if addr is None:
            (ok, res) = symdebug.source_address(filename, line)
            if not ok:
                raise cli.CliError(res)
            addr = res[0]['start_addr']
        (ok, pc) = symdebug.current_pc()
        if not ok:
            pc = None
        (ok, cpu) = symdebug.current_processor()
        if not ok:
            raise cli.CliError(cpu)
        gen = disasm_lines(symdebug, cpu, addr, pc, s_flag)
    else:
        if not line:
            (filename, line, _) = source_by_address(st, addr)

        current_line = None
        (success, frames) = st.iface.symdebug.stack_frames(frame, frame)
        if success and frames:
            current_filename = frames[0]['file']
            current_line = frames[0]['line']
            if current_filename != filename:
                current_line = None

        line = int(line) - maxlines // 2

        (success, new_path) = st.iface.symdebug.source_path(filename)
        if success:
            try:
                gen = marked_source(open(new_path, errors="replace"), line,
                                    current_line)
            except IOError as e:
                raise cli.CliError("Unable to open '%s' (%s)"
                                   % (new_path, e.strerror))
        else:
            raise cli.CliError("Unable to locate file: %s" % filename)

    try:
        list_generated(gen, maxlines)
    except IOError as e:
        raise cli.CliError("Unable to access source file (%s)" % (e.strerror))
    cli.set_repeat_data(list_cmd, (gen, maxlines))

def list_cmd_repeat(_ns, _flags, _arg, _maxlines):
    # We ignore all the arguments. All the data is saved in the repeat
    # data. The maxlines may change from what is passed in in
    # list_cmd, so we save it in the repeat data to avoid duplicating
    # the calculation.
    (gen, maxlines) = cli.get_repeat_data(list_cmd)
    list_generated(gen, maxlines)
    cli.set_repeat_data(list_cmd, (gen, maxlines))


def step_cmd(st, iface_method):
    step = getattr(st.iface.run_control, iface_method)
    (success, reason) = step()
    if not success:
        raise cli.CliError(reason)
    if reason != "finished":
        raise cli.CliError("Command interrupted: %s" % reason)


class ProxyCommands:
    __sym_commands = {
        'stack-trace':
        [stack_trace_cmd,
         [cli.arg(cli.range_t(0, 1000, 'max stack depth'),
                  'maxdepth', '?', 64)], None,
         ['bt', 'where'], ['frame'],
         'display stack trace',
         '''Displays a stack trace in the current context of the
         specified processor, or the current processor if none was
         specified. At most <arg>maxdepth</arg> frames are shown, 64 by
         default.'''],

        'frame':
        [frame_cmd,
         [cli.arg(cli.uint_t, 'frame-number', '?', None)], None,
         ['f'], ['stack-trace', 'up', 'down'],
         'change current stack frame',
         '''Changes current stack frame to <arg>frame-number</arg>, or
         displays the current frame.'''],

        'up':
        [up_cmd,
         [cli.arg(cli.uint_t, 'N', '?', 1)], up_cmd_repeat,
         [], ['frame', 'down', 'stack-trace'],
         'go up N stack frames',
         '''Moves <arg>N</arg> frames up the stack (towards the outermost
         frame). <i>N</i> defaults to one.'''],

        'down':
        [down_cmd,
         [cli.arg(cli.uint_t, 'N', '?', 1)], down_cmd_repeat,
         [], ['frame', 'up', 'stack-trace'],
         'go down N stack frames',
         '''Moves <arg>N</arg> frames down the stack (towards the
         innermost frame). <i>N</i> defaults to one.'''],

        'list':
        [list_cmd,
         [cli.arg((cli.flag_t, cli.flag_t), ('-s', '-d'), '?'),
          cli.arg((cli.uint_t, cli.str_t), ('address', 'location'), '?', None),
          cli.arg(cli.uint_t, 'maxlines', '?')],
         list_cmd_repeat, [], ['disassemble', 'sym-source', 'sym-value'],
         'list source and/or disassemble',
         '''List the source code corresponding to a given address,
         function or line. The <arg>location</arg> can be specified as
         <i>line</i> or <i>file</i><tt>:</tt><i>line</i> (list from
         that line); <i>function</i> or
         <i>file</i><tt>:</tt><i>function</i> (list that function); or
         <arg>address</arg> (list from that address).

         At most <arg>maxlines</arg> lines of source or asm are printed.
         <tt>-s</tt> produces source intermixed with disassembly, and
         <tt>-d</tt> disassembly only.'''],

        'sym-value':
        [sym_value_cmd,
         [cli.arg(cli.str_t, 'expression')], None, [],
         ['stack-trace', 'frame', 'sym-type', 'sym-address', 'sym-string'],
         'evaluate symbolic expression',
         '''Evaluates <arg>expression</arg> in the current stack
         frame. The argument may have to be surrounded by double
         quotes if it contains certain meta-characters. When
         <cmd>sym-value</cmd> is used in a CLI expression, the value
         of the supplied expression is returned. When used
         stand-alone, the value is pretty-printed.'''],

        'sym-type':
        [sym_type_cmd,
         [cli.arg(cli.str_t, 'expression')], None, [],
         ['sym-value', 'sym-address', 'sym-string'],
         'return the type of a symbolic expression',
         '''Returns the type of the symbol, or the evaluated
         <arg>expression</arg>, in the current stack frame. The
         argument may have to be surrounded by double quotes if it
         contains certain meta-characters.'''],

        'sym-address':
        [sym_address_cmd,
         [cli.arg((cli.uint_t, cli.str_t), ('line', 'expression'))], None, [],
         ['sym-value', 'sym-type', 'sym-string', 'sym-source'],
         'return the address of expression or source line',
         '''Returns the address of the <arg>line</arg> or the evaluated
         <arg>expression</arg>, for example a symbol, in the current
         stack frame or the source reference in the <tt>file:line</tt>
         or <tt>line</tt> format. The argument may have to be
         surrounded by double quotes if it contains certain
         meta-characters.'''],

        'sym-string':
        [sym_string_cmd,
         [cli.arg((cli.str_t, cli.uint64_t), ('expression', 'address'))],
         None, [], ['sym-value', 'sym-type', 'sym-address'],
         'evaluate symbolic expression',
         '''Interprets <arg>address</arg> or the value of
         <arg>expression</arg> as a pointer to a string in target
         memory, returning the string. The expression, if used, is
         evaluated in the current stack frame. The argument may have
         to be surrounded by double quotes if it contains certain
         meta-characters.'''],

        'sym-source':
        [sym_source_cmd,
         [cli.arg((cli.str_t, cli.uint64_t), ('function', 'address'))],
         None, [], ['sym-file', 'sym-line', 'sym-function', 'sym-address'],
         'print source location for function or address',
         '''Prints the source file, line and function for <arg>function</arg>
         or <arg>address</arg>.'''],

        'sym-file':
        [sym_file_cmd,
         [cli.arg((cli.str_t, cli.uint64_t), ('function', 'address'))],
         None, [], ['sym-function', 'sym-line', 'sym-source', 'sym-address'],
         'return source file for function or address',
         """Returns the source file with complete path in the host
         machine's file system for <arg>function</arg> or <arg>address</arg>.
         """],

        'sym-line':
        [sym_line_cmd,
         [cli.arg((cli.str_t, cli.uint64_t), ('function', 'address'))],
         None, [], ['sym-function', 'sym-file', 'sym-source', 'sym-address'],
         'return source line for function or address',
         '''Returns the source line for <arg>function</arg> or
         <arg>address</arg>.'''],

        'sym-function':
         [sym_function_cmd,
         [cli.arg(cli.uint64_t, 'address')], None, [],
         ['sym-file', 'sym-line', 'sym-source', 'sym-address'],
         'return function at a given address',
         '''Returns the function at the specified <arg>address</arg>
         in memory.'''],

        'sym-write':
        [sym_write_cmd,
         [cli.arg(cli.str_t, 'variable'),
          cli.arg(cli.poly_t('value', cli.int64_t, cli.float_t), 'value')],
         None, [], ['sym-address', '<memory_space>.write', 'set'],
         'write value to variable',
         '''Writes the <arg>value</arg> to the <arg>variable</arg> with the
         size of the variable. If the value is greater than the size of the
         variable, the behavior is undefined. Only variables with basic type
         or pointer type may be written to. When writing floating point values,
         the variable must be of floating point type.
         '''],

        'sym-list':
        [sym_list_cmd,
         [cli.arg(cli.flag_t, '-globals'),
          cli.arg(cli.flag_t, '-locals'),
          cli.arg(cli.flag_t, '-functions'),
          cli.arg(cli.str_t, 'substr', '?'),
          cli.arg(cli.flag_t, '-regex'),
          cli.arg(cli.flag_t, '-sort-by-address'),
          cli.arg(cli.flag_t, '-show-all-rows')],
         None, [], ['sym-address', 'sym-type', 'sym-value'],
         'list symbols',
         '''List symbols visible from current context together with type,
            address and size. Not all symbols have type, address or size.

            With the options the set of symbols listed can be controlled,
            <tt>-globals</tt> includes global data symbols, <tt>-locals</tt>
            includes local symbols and arguments currently visible, and
            <tt>-functions</tt> includes function symbols.
            Default is to list global and local symbols.

            If <arg>substr</arg> is specified, just symbols whose names
            contain the given substring (case sensitive) are included in
            the list.

            If <tt>-regex</tt> is specified <arg>substr</arg> is treated as
            a Python regular expression.

            Symbols are listed in alphabetical order unless
            <tt>-sort-by-address</tt> flag is specified.

            By default max 100 symbols are listed. With the
            <tt>-show-all-rows</tt> flag all symbols are included.
         '''],
        }

    __step_commands = {
        'step-into':
            [True, ['step', 's', 'step-line'], 'run to the next source line',
             '<cmd>step-into</cmd> causes the simulation to run until it '
             + 'reaches another source line.', "step_line"],
        'step-into-instruction':
            [False, ['stepi', 'si', 'step-instruction'],
             'run to the next instruction',
             '<cmd iface="symdebug">step-into-instruction</cmd> causes the '
             + 'simulation to run one instruction.', "step_instruction"],
        'step-over':
            [True, ['next', 'n', 'next-line'],
             'run to the next source line, skipping subroutine calls',
             '<cmd>step-over</cmd> causes the simulation to run until it '
             + 'reaches another source line, but will not stop in subroutine '
             + 'calls.', "next_line"],
        'step-over-instruction':
            [True, ['nexti', 'ni', 'next-instruction'],
             'run to the next instruction, skipping subroutine calls',
             '<cmd>step-over-instruction</cmd> causes the simulation to run '
             + 'until it reaches another instruction, but will not stop in '
             + 'subroutine calls.', 'next_instruction'],
        'step-out':
            [True, ['finish', 'fin', 'finish-function'],
             'finish the current function',
             '<cmd>step-out</cmd> causes the simulation to run until '
             + 'the current function has returned.', 'finish_function'],
        }

    def __init__(self):
        self.__all_commands = (tuple(self.__sym_commands)
                               + tuple(self.__step_commands))

    def register_global_commands(self):
        for name in self.__all_commands:
            self.__register_global(name)

    def __step_see_also(self, name, global_cmd):
        cmds = []
        iface_prefix = "" if global_cmd else "<symdebug>."
        for c in self.__step_commands:
            if c == name:
                continue
            if global_cmd and not self.__step_commands[c][0]:
                continue
            cmds.append(f"{iface_prefix}{c}")
        return sorted(cmds)

    # Register a global command that calls the matching namespaced
    # command on the first of the current debug object that has such
    # a command.
    def __register_global(self, name):
        def fun_wrapper(*args):
            obj = tcfc.get_debug_object()
            if not obj:
                raise cli.CliError('No current debug object')
            return cmd_fun(obj, *args)

        def repeat_wrapper(*args):
            obj = tcfc.get_debug_object()
            if not obj:
                raise cli.CliError(f"No debug object when repeating {name}")
            return repeat_fun(obj, *args)

        if name in self.__sym_commands:
            (cmd_fun, args, repeat_fun, alias, see_also, short_doc,
             doc) = self.__sym_commands[name]
        else:
            (register_global, alias, short_doc,
             doc, iface_method) = self.__step_commands[name]
            if not register_global:
                return
            args = []
            see_also = self.__step_see_also(name, True)
            cmd_fun = lambda st: step_cmd(st, iface_method)
            repeat_fun = cmd_fun
        should_repeat = bool(repeat_fun)
        assert cmd_fun
        cli.new_command(name, fun_wrapper, args, alias = alias,
                        repeat = repeat_wrapper if should_repeat else None,
                        type = ['Debugging'],
                        see_also = see_also, short = short_doc, doc = doc)

    def __register_proxy_cmd(self,  name):
        iface = 'symdebug'
        if name in self.__sym_commands:
            (cmd_fun, args, repeat, alias, see_also, short_doc,
             doc) = self.__sym_commands[name]
        else:
            assert name in self.__step_commands, f"Bad {name}"
            (_, alias, short_doc, doc, iface_method) = self.__step_commands[
                name]
            args = []
            cmd_fun = lambda st: step_cmd(st, iface_method)
            repeat = cmd_fun
            see_also = self.__step_see_also(name, False)

        cli.new_command(
                name, cmd_fun, args, iface = iface, alias = alias,
                type = ['Debugging'], repeat = repeat,
                see_also = see_also, short = short_doc, doc = doc)

    def register_all_proxy_cmds(self):
        for name in self.__all_commands:
            self.__register_proxy_cmd(name)


def proxy_info(obj):
    properties = [("TCF Agent", obj.agent.name),
                  ("Context ID", obj.cid)]
    finder_iface = obj.agent.iface.agent_proxy_finder
    ctx_info = finder_iface.get_context_info(obj.cid)
    properties.append(("Context Exists", bool(ctx_info)))
    if ctx_info:
        properties.extend([
            ("Context Name", ctx_info['Name']),
            ("Context Full Name", finder_iface.context_full_name(obj.cid)),
            ("Context Has State", ctx_info['HasState']),
            ("Context Is OSA Node", ctx_info['IsNode']),
        ])
    return [(None, properties)]

def add_info_status_cmds():
    cli.new_info_command("tcf-context-proxy", proxy_info)
    cli.new_status_command("tcf-context-proxy", lambda o: [])


def register_proxy_cmds():
    _proxy_cmds.register_all_proxy_cmds()
    add_info_status_cmds()


def register_global_proxy_cmds():
    _proxy_cmds.register_global_commands()

# The single instance of ProxyCommands.
_proxy_cmds = ProxyCommands()
