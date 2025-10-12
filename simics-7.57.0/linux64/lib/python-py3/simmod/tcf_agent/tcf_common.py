# © 2020 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from simmod.os_awareness.interfaces import nodepath
import conf
import simics
import cli
import json
import simics_common
import collections
import re
from . import expressions_formatter

bp_id = 0
def next_bp_id():
    global bp_id
    bp_id += 1
    return 'simics-breakpoint-%d' % bp_id

def create_ep(tcf, attrs, callback):
    '''Creates and returns the id of an eventpoint with specified attributes
    and callbacks.'''
    a = {k: json.dumps(v) for (k, v) in list(attrs.items())}
    (ok, ep) = tcf.iface.tcf_breakpoints.create_eventpoint(a, callback, None)
    if not ok:
        raise cli.CliError(ep)
    return ep

def delete_ep(tcf, ep):
    '''Deletes the eventpoint ep..'''
    ok = tcf.iface.tcf_breakpoints.delete_eventpoint(ep)
    if not ok:
        raise cli.CliError(ep)

def new_bp(tcf, attrs):
    a = dict((k, json.dumps(v)) for (k, v) in list(attrs.items()))

    # Create breakpoint.
    (ok, bp) = tcf.iface.tcf_breakpoints.create_breakpoint(a)
    if not ok:
        raise cli.CliError(bp)
    return bp

def register_bp(tcf, bp):
    # Register breakpoint in breakpoint manager if requested and return tuple
    # of (TCF ID Attribute value, Breakpoint Manager ID).
    (ok, bm_id) = tcf.iface.tcf_breakpoints.register_breakpoint(bp)
    if not ok:
        raise cli.CliError(bm_id)
    return bm_id

def create_bp(tcf, attrs):
    '''Create a breakpoint with the attrs attributes and
    registers it in the breakpoint manager. Returns on success a tuple that
    consists of TCF breakpoint id attribute value and the breakpoint manager
    breakpoint identity.'''
    bp = new_bp(tcf, attrs)
    bm_id = register_bp(tcf, bp)
    return (bp, bm_id)

def delete_bp(tcf, bp):
    '''Delete a breakpoint specified by the TCF breakpoint id in bp.'''
    ok = tcf.iface.tcf_breakpoints.delete_breakpoint(bp)
    if not ok:
        raise cli.CliError(bp)

def get_planted_info(tcf, bp_id, bm_id):
    '''Return tuple with (planted, msg) where msg is a string describing
    the breakpoint or eventpoint identity followed by planted state.'''
    (ok, status) = tcf.iface.tcf_breakpoints.get_breakpoint_status(bp_id)
    planted = ok and status.get('planted')
    msg = "0x%x" % bm_id if bm_id else ""
    return (planted, msg + " (%splanted)" % ("" if planted else "not "))

def simics_query_reformat(query):
    if query:
        return '\''.join([elem.replace('\'', '\"')
                          for elem in query.split('\\\'')])
    else:
        return None

class Debug_state:
    debug_states = {}

    @staticmethod
    def debug_state(dbg_obj):
        d = Debug_state.debug_states.get(dbg_obj)
        if not d:
            d = Debug_state.debug_states[dbg_obj] = Debug_state(dbg_obj)
        d.update()
        return d

    def __init__(self, st):
        self.steps = object()
        self.pc = object()
        self.st = st

        # The currently selected stack frame.
        self.frame = 0

        # The (steps, pc) pair for which .frame is valid. When we
        # leave this spot, .frame should be reset.
        self.frame_steps_pc = (object(), object())

    def get_debug_object(self):
        return self.st

    def update(self):
        (success, cpu) = self.st.iface.symdebug.current_processor()
        if success:
            self.pc = self.st.iface.symdebug.current_pc()
            self.steps = simics.SIM_step_count(cpu)
            if self.frame_steps_pc != (self.steps, self.pc):
                self.frame_steps_pc = (self.steps, self.pc)
                self.frame = 0

def get_frame_string(st, frame_no, frame):
    pc = frame['addr']
    if frame_no >= 0:
        output = "#%d 0x%x in " % (frame_no, pc)
    else:
        frame_no = 0
        output = ""
    output += (frame.get('func') or '??') + '('
    (success, args) = st.iface.symdebug.stack_arguments(frame_no, 0)
    if success:
        separator = ""
        for arg in args:
            output += separator + arg
            (success, data) = sym_value_impl(st.cid, frame_no, arg)
            if success:
                (value_str, _) = data
                output += f'={value_str}'
            separator = ", "
    output += ")"
    line = frame.get('line', 0)
    if line:
        path = frame.get('fullname', None) or frame.get('file', '??')
        output += " at %s:%d" % (path, line)
    return output

def is_x86_cpu(cpu_obj):
    # The object is considered x86 if it has cpu_obj.iface.x86
    return getattr(getattr(cpu_obj, "iface", object), "x86", None)

# Collects all strings that are to be printed.
# Item order:
# 1. debug object description
# 2. current frame string (even if it's empty!)
# 3. source code and line number  OR
#    function and function offset OR
#    function                     OR
#    disassembly                  OR
#    "No source available"
# Should always be filled with all items. It is then up to PromptPrinter to
# decided whether to print all items or just a subset.
def collect_prompt(ds):
    symdebug = ds.get_debug_object().iface.symdebug
    new_collection = []

    new_collection.append(format_debug_object_string(ds.get_debug_object()))

    (success, is_thread) = symdebug.is_thread()
    if not success or not is_thread:
        return [] # signal badness to PromptPrinter

    (success, frames) = symdebug.stack_frames(0, 0)
    if success and len(frames):
        [frame] = frames
        func = frame['func'] if 'func' in frame else None
        line = frame['line'] if 'line' in frame else 0
        path = frame['fullname'] if 'fullname' in frame else None
        filename = frame['file'] if 'file' in frame else "??"
        frame_string = get_frame_string(ds.get_debug_object(), -1, frame)
    else:
        func = None
        line = 0
        path = None
        filename = None
        frame_string = ""

    new_collection.append(frame_string)

    if path is None: # Sometimes fullname is not defined, use file instead.
        path = filename
    if path and line:
        (success, path) = symdebug.source_path(path)
        if success:
            new_collection.append(format_source_line_string(line, path))
            return new_collection

    (success, cpu) = symdebug.current_processor()
    if not success:
        cpu = None

    (success, pc) = symdebug.current_pc()
    if not success:
        pc = None

    disasm = ""
    if cpu:
        if is_x86_cpu(cpu):
            # Use logical address to disassemble even if current_pc is the
            # linear variant.
            da_pc = cpu.iface.processor_info_v2.get_program_counter()
        else:
            da_pc = pc
        if da_pc is not None:
            disasm = simics.SIM_disassemble_address(cpu, da_pc, 1, 0)[1]

    (success, func_addr) = symdebug.lvalue_address(0, 0, func)
    if not success:
        func_addr = None

    if pc != None and func and func_addr != None:
        new_collection.append(format_function_offset_string(pc, func,
                                                pc - func_addr,
                                                disasm))
        return new_collection

    if pc != None and func:
        new_collection.append(format_function_string(pc, func, disasm))
        return new_collection

    if disasm:
        new_collection.append(format_disassembly_string(disasm))
        return new_collection

    new_collection.append(format_no_source_pos_string())
    return new_collection

frontend_prompts = {}

def print_prompt_to_frontend(frontend_id, p, output_function):
    prompt_printer = get_prompt_printer_for_frontend(frontend_id)
    prompt_printer.print_prompt(p, output_function)

def get_prompt_printer_for_frontend(frontend_id):
    if frontend_id not in frontend_prompts:
        frontend_prompts[frontend_id] = PromptPrinter()

    return frontend_prompts[frontend_id]

# return list of nlines lines from filename (without newlines),
# starting at line starting_line (first line is line 1).
# May return a list shorter than nlines (even []) if outside the file.
def getlines(filename, starting_line, nlines):
    native_filename = simics.SIM_native_path(filename)
    try:
        f = open(native_filename, errors="replace")
    except IOError:
        return ["(%s not found)" % filename]
    with f:
        for i in range(starting_line - 1):
            f.readline()
        lines = []
        for i in range(nlines):
            line = f.readline()
            if not line:
                break
            lines.append(line.rstrip('\n\r'))
        return lines

class NodeTraverse(nodepath.NodePathNode):
    def __init__(self, node_tree, node_id):
        self.node_tree = node_tree
        self.node_id = node_id
        self.get = node_tree.iface.osa_node_tree_query.get_node(node_id).get
        self.props = node_tree.iface.osa_node_tree_query.get_node(node_id)
    def parent(self):
        parent_id = self.node_tree.iface.osa_node_tree_query.get_parent(self.node_id)
        if parent_id is not None:
            return NodeTraverse(self.node_tree, parent_id)
        else:
            return None
    def get_nodepath_node(self):
        return nodepath.NodePathNode(
            self.node_id, self.props, self.get_parent_nodepath_node)
    def get_parent_nodepath_node(self):
        parent = self.parent()
        if parent is None:
            return None
        return parent.get_nodepath_node()

def describe_debug_object(obj):
    t = obj.desc[0]
    o = obj.desc[1]
    if t == 'simobj':
        return 'the %s %s' % (o.classname, o.name)
    elif t == 'sw-node':
        node_id = obj.desc[2]
        if o.iface.osa_node_tree_query.get_node(node_id):
            np = nodepath.node_path(o, NodeTraverse(o, node_id))
        else:
            np = '<unknown node>'
        return '%s on %s' % (np, o.name)
    else:
        raise Exception('Unknown type %r' % t)

def format_debug_object_string(obj):
    return "Now debugging %s" % describe_debug_object(obj)

def format_source_line_string(line, path):
    return "%d\t%s" % (line,'\n'.join(getlines(path, line, 1)))

def format_function_offset_string(pc, function, offset, disassembly = None):
    return "0x{0:<16x} {1:<30} {2}".format(pc,
                "({0} + 0x{1:x})".format(function, offset), disassembly or "")

def format_function_string(pc, function, disassembly = None):
    return "0x{0:<16x} in {1:<27} {2}".format(
        pc, function, disassembly or "")

def format_disassembly_string(disassembly):
    return (" " * 50) + disassembly

def format_no_source_pos_string():
    return "No program location available"

class PromptPrinter:
    def __init__(self):
        self.last_collection = []

    def print_prompt(self, new_collection, writer):
        # Need this to differentiate between loop finish and loop break on last
        # item
        diff_found = False

        if len(new_collection) == 0:
            return

        for (i, new_item) in enumerate(new_collection):
            try:
                if new_item != self.last_collection[i]:
                    diff_found = True
                    break
            except IndexError:
                diff_found = True
                break

        if diff_found:
            for j in range(i, len(new_collection)):
                if len(new_collection[j]) > 0:
                    writer("%s\n" % new_collection[j])

        self.last_collection = new_collection[:]

def have_uefi_support():
    return bool(simics.VT_get_all_implementing_modules("uefi_tracker"))

def run_command(cmd):
    '''Run a command and catch the result, output and errors'''
    try:
        (res, msg) = cli.quiet_run_command(cmd)
        return [True, res, msg]
    except cli.CliError as e:
        return [False, str(e)]

def get_run_state():
    return simics_common.run_state.run_state

def get_base_type(tcf, ctx_id, addr, etype):
    if not isinstance(etype, list) or etype[0] != "typedef":
        return etype
    (err, base_type) = tcf.iface.debug_symbol.type_info(ctx_id, addr, etype[1])
    if err != simics.Debugger_No_Error:
        return None

    return get_base_type(tcf, ctx_id, addr, base_type)

def expr_info_loop(tcf, ctx_id, addr, etype, evalue, res, name):
    btype = get_base_type(tcf, ctx_id, addr, etype)
    if not btype:
        return (simics.Debugger_Incorrect_Type,
                "Could not get base type for '%s'" % name)
    if isinstance(btype, list):
        if btype[0] in ("struct", "union"):
            (err, disp_type) = tcf.iface.debug_symbol.type_to_string(etype)
            if err != simics.Debugger_No_Error:
                disp_type = "%s %s" % (btype[0], btype[1])
            sub_dict = collections.OrderedDict()
            if isinstance(res, list):
                res.append((sub_dict, disp_type))
            else:
                res[name] = (sub_dict, disp_type)
            members = btype[-1]
            for i in range(len(members)):
                member_type = members[i][0]
                member_val = evalue[i]
                member_name = members[i][1]
                (err, err_str) = expr_info_loop(tcf, ctx_id, addr, member_type,
                                                member_val, sub_dict,
                                                member_name)
                if err != simics.Debugger_No_Error:
                    return (err, err_str)
            return (simics.Debugger_No_Error, None)
        elif btype[0] == "[]":
            (array_size, array_member_type) = btype[1:]
            array_member_base = get_base_type(tcf, ctx_id, addr,
                                              array_member_type)

            if (isinstance(array_member_base, list)
                and array_member_type[0] in ("[]", "struct", "union")):
                (err, disp_type) = tcf.iface.debug_symbol.type_to_string(etype)
                if err != simics.Debugger_No_Error:
                    disp_type = "%s[%d]" % (array_member_type, array_size)
                array_list = list()
                res[name] = (array_list, disp_type)
                for i in range(array_size):
                    member_val = evalue[i]
                    sub_dict = collections.OrderedDict()
                    (err, err_str) = expr_info_loop(
                        tcf, ctx_id, addr, array_member_type, member_val,
                        sub_dict, None)
                    if err != simics.Debugger_No_Error:
                        return (err, err_str)
                    array_list.append(sub_dict)
                return (simics.Debugger_No_Error, None)
    (err, type_str) = tcf.iface.debug_symbol.type_to_string(etype)
    if err != simics.Debugger_No_Error:
        type_str = None
    res[name] = (evalue, type_str)
    return (simics.Debugger_No_Error, None)

def expression_info(ctx_id, expr, frame, addr):
    if not cli.unsupported_enabled("internals"):
        return (simics.Debugger_Failed_To_Evaluate_Expression,
                "Feature not supported")
    if not isinstance(ctx_id, str):
        return (simics.Debugger_Unknown_Id, "Bad type for context id")
    tcf = simics.SIM_get_debugger()
    (err, has_state) = tcf.iface.debug_query.context_has_state(ctx_id)
    if err != simics.Debugger_No_Error:
        return (err, has_state)
    if not has_state:
        return (simics.Debugger_Context_Does_Not_Have_State,
                "Context does not have state")

    (err, etype) = tcf.iface.debug_symbol.expression_type(
        ctx_id, frame, addr, expr)
    if err != simics.Debugger_No_Error:
        return (err, etype)

    (err, evalue) = tcf.iface.debug_symbol.expression_value(
        ctx_id, frame, addr, expr)
    if err != simics.Debugger_No_Error:
        return (err, evalue)

    res = collections.OrderedDict()
    (err, err_str) = expr_info_loop(tcf, ctx_id, addr, etype, evalue, res, expr)
    if err != simics.Debugger_No_Error:
        return (err, err_str)
    return (simics.Debugger_No_Error, res)

def expression_info_cpu(cpu, expr, frame, addr):
    tcf = simics.SIM_get_debugger()
    (err, ctx_id) = tcf.iface.debug_query.context_id_for_object(cpu)
    if err != simics.Debugger_No_Error:
        return (err, ctx_id)
    return expression_info(ctx_id, expr, frame, addr)

def expr_value_format(ctx_id, frame, addr, expr):
    def expr_error(err, err_msg):
        assert err != simics.Debugger_No_Error
        return [False, err_msg]

    debugger = simics.SIM_get_debugger()
    (err, e_type) = debugger.iface.debug_symbol.expression_type(
        ctx_id, frame, addr, expr)
    if err != simics.Debugger_No_Error:
        return expr_error(err, e_type)

    (err, e_val) = debugger.iface.debug_symbol.expression_value(
        ctx_id, frame, addr, expr)
    if err != simics.Debugger_No_Error:
        return expr_error(err, e_val)

    formatter = expressions_formatter.decode_value_from_api(ctx_id, e_type,
                                                            e_val)
    if expressions_formatter.is_unknown_value(formatter):
        return [False, 'Unknown value type']
    return [True, formatter.expr_value_formatter()]

def expr_type_format(ctx_id, frame, addr, expr):
    def expr_type_error(err, err_msg):
        assert err != simics.Debugger_No_Error
        return [False, err_msg]

    debugger = simics.SIM_get_debugger()
    (err, e_type) = debugger.iface.debug_symbol.expression_type(
        ctx_id, frame, addr, expr)
    if err != simics.Debugger_No_Error:
        return expr_type_error(err, e_type)

    res = expressions_formatter.decode_type_from_api(e_type)
    if expressions_formatter.is_unknown_type(res):
        return [False, 'Unknown type']
    return [True, res.expr_type_formatter()]

def sym_value_format(ctx_id, e_type, e_val):
    formatter = expressions_formatter.decode_value_from_api(ctx_id, e_type,
                                                            e_val)
    return [True, (formatter.sym_value_formatter(), e_val)]

def sym_value_impl(ctx_id, frame, expr):
    debugger = simics.SIM_get_debugger()
    (err, e_type) = debugger.iface.debug_symbol.expression_type(
        ctx_id, frame, 0, expr)
    if err != simics.Debugger_No_Error:
        return (False, e_type)

    (err, e_val) = debugger.iface.debug_symbol.expression_value(
        ctx_id, frame, 0, expr)
    if err != simics.Debugger_No_Error:
        return (False, e_val)

    return sym_value_format(ctx_id, e_type, e_val)

def sym_type_format(e_type):
    type_formatter = expressions_formatter.decode_type_from_api(e_type)
    return [True, type_formatter.sym_type_formatter()]

def sym_type_impl(ctx_id, frame, expr):
    debugger = simics.SIM_get_debugger()
    (err, e_type) = debugger.iface.debug_symbol.expression_type(
        ctx_id, frame, 0, expr)
    if err != simics.Debugger_No_Error:
        return (False, e_type)
    return sym_type_format(e_type)

def sym_list_impl(ctx_id, frame, substr, regex, list_globals,
                  list_locals, list_funcs, *table_args):

    class symbol_list:
        def __init__(self, ctx_id, frame, substr, regex):
            self._ctx_id = ctx_id
            self._frame = frame
            self._substr = substr
            self._regex = regex
            self._syms = []
            self._dbgs = simics.SIM_get_debugger().iface.debug_symbol

        def _get_symbol_address(self, name, address):
            if not address:
                (err, address) = self._dbgs.expression_value(self._ctx_id,
                                                             self._frame, 0,
                                                             f"&{name}")
                if err != simics.Debugger_No_Error:
                    return ''
            return address

        def _get_symbol_type(self, name):
            (err, e_type) = self._dbgs.expression_type(self._ctx_id,
                                                       self._frame,
                                                       0, name)
            if err == simics.Debugger_No_Error:
                return sym_type_format(e_type)[1]
            return ''

        def _get_symbol_size(self, name, size):
            if not size:
                (err, size) = self._dbgs.expression_value(self._ctx_id,
                                                          self._frame, 0,
                                                          f"sizeof({name})")
                if err != simics.Debugger_No_Error or not size:
                    return ''
            return size

        def _add_sym_info_to_list(self, name, kind, address, size):
            if self._regex and not self._regex.match(name):
                return
            if self._substr and not self._substr in name:
                return
            self._syms.append([name, kind, self._get_symbol_type(name),
                               self._get_symbol_address(name, address),
                               self._get_symbol_size(name, size)])

        def add_complex_syms(self, kind, err, gs):
            if err == simics.Debugger_No_Error:
                for s in gs:
                    self._add_sym_info_to_list(s['symbol'], kind,
                                               s['address'], s['size'])
                return True, ''
            return False, "Error getting {kind} symbols: {err}"

        def add_simple_syms(self, kind, err, gs):
            if err == simics.Debugger_No_Error:
                for s in gs:
                    self._add_sym_info_to_list(s, kind, None, None)
                return True, ''
            return False, "Error getting {kind} symbols: {err}"

        def syms(self):
            return self._syms

        def dbgs(self):
            return self._dbgs

    if regex:
        try:
            pattern = re.compile(substr)
            substr = None
        except re.error as e:
            return False, f"Error compiling regex: {e.msg}", []
    else:
        pattern = None

    syms = symbol_list(ctx_id, frame, substr, pattern)
    ok = True

    if list_globals:
        (err, ls) = syms.dbgs().list_global_variables(ctx_id)
        (ok, msg) = syms.add_complex_syms('global', err, ls)

    if ok and list_locals :
        (err, ls) = syms.dbgs().local_variables(ctx_id, frame)
        (ok, msg) = syms.add_simple_syms('local', err, ls)

        if ok:
            (err, ls) = syms.dbgs().local_arguments(ctx_id, frame)
            (ok, msg) = syms.add_simple_syms('argument', err, ls)

    if ok and list_funcs:
        (err, ls) = syms.dbgs().list_functions(ctx_id)
        (ok, msg) = syms.add_complex_syms('function', err, ls)

    return (ok, syms.syms() if ok else msg)


def proxyname(name):
    return cli.get_available_object_name('dbg') if name is None else name

def proxy_for_node(node_tree, node_id, name=None):
    apf = simics.SIM_get_debugger().iface.agent_proxy_finder
    return apf.proxy_for_osa_node(node_tree, node_id, proxyname(name))

def proxy_for_object(obj, name=None):
    apf = simics.SIM_get_debugger().iface.agent_proxy_finder
    return apf.proxy_for_object(obj, proxyname(name))

def proxy_for_id(ctx_id, name=None):
    apf = simics.SIM_get_debugger().iface.agent_proxy_finder
    return apf.proxy_for_id(ctx_id, proxyname(name))

def calculate_current_debug_object(cpu=None):
    cpu = cpu or cli.current_cpu_obj_null()
    if not cpu:
        return None
    for nt in simics.SIM_object_iterator(None):
        if not hasattr(nt.iface, 'osa_node_tree_query'):
            continue
        sw = nt.iface.osa_node_tree_query
        root_nodes = sw.get_root_nodes()
        for root_nid in root_nodes:
            for n in reversed(sw.get_current_nodes(root_nid, cpu) or []):
                if not sw.get_node(n).get('multiprocessor', True):
                    proxy = proxy_for_node(nt, n)
                    if proxy:
                        return proxy
    return proxy_for_object(cpu)


class CurrentDebugContext:
    def __init__(self):
        # Either the current tcf debug object or None if debugger is
        # not enabled.
        self.__current_object = None

        self.__enabled = False
        self.__has_been_enabled = False

    def set_debug_object(self, obj, enabled=True):
        self.__current_object = obj
        self.__enabled = enabled
        if self.__has_been_enabled or not enabled:
            return

        self.__has_been_enabled = True

        # Only report telemetry and install hap callbacks first time a debug
        # object is set.
        simics.VT_add_telemetry_data_bool(
            'core.tcf', 'cli-debugger-enabled', True)

        simics.SIM_hap_add_callback('Core_Simulation_Stopped',
                                    self.__stopped_callback, 0)

    def get_debug_object(self):
        return self.__current_object

    def update_debug_object(self, cpu=None):
        if self.__enabled:
            self.set_debug_object(calculate_current_debug_object(cpu))

    def __stopped_callback(self, data, obj, exc, err):
        if self.__enabled:
            self.set_debug_object(calculate_current_debug_object())

_curr_debug = CurrentDebugContext()

set_debug_object = _curr_debug.set_debug_object
get_debug_object = _curr_debug.get_debug_object
update_debug_object = _curr_debug.update_debug_object
