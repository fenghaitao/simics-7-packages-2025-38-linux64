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


import sys
import cli
import conf
import simics
import importlib

is_tcf_module_loaded = False
def load_tcf_module():
    global is_tcf_module_loaded
    if not is_tcf_module_loaded:
        simics.SIM_load_module("tcf-agent")
        is_tcf_module_loaded = True

class Breakpoint:
    __slots__ = ('tcf_bp_id', 'is_break', 'planted', 'planted_msg', 'args')
    def __init__(self, tcf_bp_id, is_break, planted, planted_msg, args):
        self.tcf_bp_id = tcf_bp_id
        self.is_break = is_break
        self.planted = planted
        self.planted_msg = planted_msg
        self.args = args

class TCFBreakpoint:
    def __init__(self):
        self.bp_data = {}
        self.tcf_bp = {}
        self.next_bp = 1
        self._imported_tcf_modules = {}

    def _tcf_module(self, mod_name):
        if mod_name not in self._imported_tcf_modules:
            load_tcf_module()
            mod = importlib.import_module(f'simmod.tcf_agent.{mod_name}', None)
            self._imported_tcf_modules[mod_name] = mod

        return self._imported_tcf_modules[mod_name]

    def _tcf_common(self):
        return self._tcf_module('tcf_common')

    def _create_bp(self, tcf_bp_id, is_break, planted, planted_msg, args):
        bp_id = self.next_bp
        self.next_bp += 1
        self.bp_data[bp_id] = Breakpoint(tcf_bp_id, is_break, planted,
                                         planted_msg, args)
        self.tcf_bp[tcf_bp_id] = bp_id
        return bp_id

    def _get_props(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        bp = self.bp_data[bp_id]
        obj = bp.args[0]
        once = bp.args[-1]
        return {"temporary": once,
                "planted": bp.planted,
                "object": obj.name if obj else None,
                "description": self._describe_bp(bp_id)}

    # bp.delete callback, used for non-break case only
    def _delete_bm(self, _, bm_id):
        self._unregister_bp(conf.bp.iface.breakpoint_type.get_break_id(bm_id))

    def _delete_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        del self.bp_data[bp_id]
        del self.tcf_bp[bp.tcf_bp_id]

    def _unregister_bp(self, bp_id):
        assert bp_id in self.bp_data
        bp = self.bp_data[bp_id]
        tcf = simics.SIM_get_debugger()
        if bp.is_break:
            self._tcf_common().delete_bp(tcf, bp.tcf_bp_id)
        else:
            self._tcf_common().delete_ep(tcf, bp.tcf_bp_id)
        self._delete_bp(bp_id)

    def _bp_cb(self, *args):
        (_, tcf_bp_id, _) = args
        assert tcf_bp_id in self.tcf_bp
        conf.bp.iface.breakpoint_type.trigger(self.obj, self.tcf_bp[tcf_bp_id],
                                              None, None)

line_break_doc = """
Add a breakpoint at a given source code line. The <arg>line</arg> should be
given as filename:linenumber[:columnnumber].

Alternatively the file name, line number and column number can be specified
using the <arg>filename</arg>, <arg>line-number</arg>, and optional
<arg>column</arg> arguments. This will allow the filename to contain the colon
character, something the <arg>line</arg> argument cannot handle. If
<arg>filename</arg> is left out the file of the current stack frame will be
used.

The break condition will evaluate to true if any of the selected <tt>access
methods</tt> operates on the <tt>address</tt> of the <arg>line</arg> in the
<tt>target memory object</tt>. The default access method is <tt>execution</tt>
and the default target memory object is the <tt>virtual memory space</tt>
of the processor associated with the debug context.

To use other access methods, use any combination <tt>-r</tt> for read,
<tt>-w</tt> for write and <tt>-x</tt> for execute.

To change the target memory object from the <tt>virtual</tt> memory object
to the <tt>physical</tt> memory object of the processor for the debug
context, set the <tt>-p</tt> argument flag.

If <arg>line</arg> could not be resolved to an address among the added
symbol files, it is possible to make the command fail by
specifying <tt>-error-not-planted</tt>.

You can limit the debug contexts the breakpoint applies to by providing a
context query with <arg>context-query</arg>. It defaults to <tt>*</tt>, which
matches all debug contexts.

The command returns the <em>id</em> of the new breakpoint. This can be used to
manage and delete the breakpoint using the <obj>bp</obj> object."""

line_run_until_doc = """
Run until the specified line is reached or until simulation stops.
The <arg>line</arg> should be given as filename:linenumber[:columnnumber]

Alternatively the file name, line number and column number can be specified
using the <arg>filename</arg>, <arg>line-number</arg>, and optional
<arg>column</arg> arguments. This will allow the filename to contain the colon
character, something the <arg>line</arg> argument cannot handle. If
<arg>filename</arg> is left out the file of the current stack frame will be
used.

The simulation will run until any of the selected <tt>access
methods</tt> operates on the <tt>address</tt> of the <arg>line</arg> in the
<tt>target memory object</tt>. The default access method is <tt>execution</tt>
and the default target memory object is the <tt>virtual memory space</tt>
of the processor associated with the debug context.

To use other access methods, use any combination <tt>-r</tt> for read,
<tt>-w</tt> for write and <tt>-x</tt> for execute.

To change the target memory object from the <tt>virtual</tt> memory object
to the <tt>physical</tt> memory object of the processor for the debug
context, set the <tt>-p</tt> argument flag.

If <arg>line</arg> could not be resolved to an address among the added
symbol files, it is possible to make the command fail by
specifying <tt>-error-not-planted</tt>.

You can limit the debug contexts the breakpoint applies to by providing a
context query with <arg>context-query</arg>. It defaults to <tt>*</tt>, which
matches all debug contexts."""

line_wait_for_doc = """
Wait in the current script branch until specified line is reached.
The <arg>line</arg> should be given as filename:linenumber[:columnnumber].

Alternatively the file name, line number and column number can be specified
using the <arg>filename</arg>, <arg>line-number</arg>, and optional
<arg>column</arg> arguments. This will allow the filename to contain the colon
character, something the <arg>line</arg> argument cannot handle. If
<arg>filename</arg> is left out the file of the current stack frame will be
used.

The script branch will wait until any of the selected <tt>access
methods</tt> operates on the <tt>address</tt> of the <arg>line</arg> in the
<tt>target memory object</tt>. The default access method is <tt>execution</tt>
and the default target memory object is the <tt>virtual memory space</tt>
of the processor associated with the debug context.

To use other access methods, use any combination <tt>-r</tt> for read,
<tt>-w</tt> for write and <tt>-x</tt> for execute.

To change the target memory object from the <tt>virtual</tt> memory object
to the <tt>physical</tt> memory object of the processor for the debug
context, set the <tt>-p</tt> argument flag.

If <arg>line</arg> could not be resolved to an address among the added
symbol files, it is possible to make the command fail by
specifying <tt>-error-not-planted</tt>.

You can limit the debug contexts the breakpoint applies to by providing a
context query with <arg>context-query</arg>. It defaults to <tt>*</tt>, which
matches all debug contexts."""

line_trace_doc = """
Enable tracing of the events that the specified line is reached.
The <arg>line</arg> should be given as filename:linenumber[:columnnumber].

Alternatively the file name, line number and column number can be specified
using the <arg>filename</arg>, <arg>line-number</arg>, and optional
<arg>column</arg> arguments. This will allow the filename to contain the colon
character, something the <arg>line</arg> argument cannot handle. If
<arg>filename</arg> is left out the file of the current stack frame will be
used.

Any of the selected <tt>access methods</tt> operating on the
<tt>address</tt> of the <arg>line</arg> in the <tt>target memory
object</tt> will be traced. The default access method is
<tt>execution</tt> and the default target memory object is the
<tt>virtual memory space</tt> of the processor associated with the
debug context.

To use other access methods, use any combination <tt>-r</tt> for read,
<tt>-w</tt> for write and <tt>-x</tt> for execute.

To change the target memory object from the <tt>virtual</tt> memory object
to the <tt>physical</tt> memory object of the processor for the debug
context, set the <tt>-p</tt> argument flag.

If <arg>line</arg> could not be resolved to an address among the added
symbol files, it is possible to make the command fail by
specifying <tt>-error-not-planted</tt>.

You can limit the debug contexts the tracing applies to by providing a
context query with <arg>context-query</arg>. It defaults to <tt>*</tt>, which
matches all debug contexts."""

class LineBreakpoints(TCFBreakpoint):
    TYPE_DESC = "source code line breakpoints"
    cls = simics.confclass("bp-manager.src-line", doc=TYPE_DESC,
                           short_doc=TYPE_DESC, pseudo=True)

    @cls.objects_finalized
    def objects_finalized(self):
        conf.bp.iface.breakpoint_type.register_type(
            "source-line",
            self.obj,
            [[["str_t", "str_t"], ["line", "filename"], '?',
              None, None, "", None],
             ["uint_t", "line-number", "?", None, None, "", None],
             ["uint_t", "column", "?", None, None, "", None],
             ["flag_t", "-error-not-planted", '1', None, None, "", None],
             ["flag_t", "-r", '1', None, None, "", None],
             ["flag_t", "-w", '1', None, None, "", None],
             ["flag_t", "-x", '1', None, None, "", None],
             ["flag_t", "-p", '1', None, None, "", None],
             ["str_t", "context-query", "?", None, None, "", None]],
            None, 'symdebug',
            ["add breakpoint at a source code line", line_break_doc,
             "run until reaching source code line", line_run_until_doc,
             "wait until reaching source code line", line_wait_for_doc,
             "enable tracing of source code line reaches", line_trace_doc],
            False, False, False)

    def _breakpoint_utilities(self):
        return self._tcf_module('breakpoint_utilities')

    def _describe_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        return self._breakpoint_utilities().get_line_wait_data(bp.args)

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        tcf = simics.SIM_get_debugger()
        if bp.is_break:
            bm_id = self._tcf_common().register_bp(tcf, bp.tcf_bp_id)
            (planted, planted_msg) = self._tcf_common().get_planted_info(
                tcf, bp.tcf_bp_id, bm_id)
            bp.planted = planted
            bp.planted_msg = planted_msg
            error_not_planted = bp.args[4]
            if error_not_planted and not bp.planted:
                self._tcf_common().delete_bp(tcf, bp.tcf_bp_id)
                return 0
            return bm_id
        else:
            (planted, planted_msg) = self._tcf_common().get_planted_info(
                tcf, bp.tcf_bp_id, None)
            bp.planted = planted
            bp.planted_msg = planted_msg
            error_not_planted = bp.args[4]
            if error_not_planted and not bp.planted:
                self._tcf_common().delete_ep(tcf, bp.tcf_bp_id)
                return 0

            bpm_iface = conf.bp.iface.breakpoint_registration
            return bpm_iface.register_breakpoint(
                self._delete_bm, None, self._get_props, None, None, None,
                None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, flags, args):
        # Remove -once
        params = (['break'] if flags == simics.Breakpoint_Type_Break
                  else ['add']) + args[:-1]
        tcf = simics.SIM_get_debugger()
        try:
            attrs = self._breakpoint_utilities().create_line_attrs(*params)
            if flags == simics.Breakpoint_Type_Break:
                tcf_bp_id = self._tcf_common().new_bp(tcf, attrs)
            else:
                tcf_bp_id = self._tcf_common().create_ep(tcf, attrs,
                                                         self._bp_cb)
        except cli.CliError as ex:
            print(ex, file=sys.stderr)
            return 0

        (planted, planted_msg) = self._tcf_common().get_planted_info(
            tcf, tcf_bp_id, None)
        return self._create_bp(tcf_bp_id, flags == simics.Breakpoint_Type_Break,
                               planted, planted_msg, args)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        if bp.is_break:
            self._delete_bp(bp_id)
        else:
            self._unregister_bp(bp_id)

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        assert bp_id in self.bp_data
        bp = self.bp_data[bp_id]
        obj = bp.args[0]
        msg = self._breakpoint_utilities().get_line_wait_data(bp.args)
        if obj:
            return f"{obj.name}: {msg}"
        else:
            return msg

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return bp.planted_msg

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        assert bp_id in self.bp_data
        bp = self.bp_data[bp_id]
        return self._breakpoint_utilities().get_line_wait_data(bp.args)

location_break_doc = """
Add a breakpoint on a particular location.
The location is either <arg>location</arg>, which should specify a C expression
or <arg>address</arg>. In addition you can specify the length of the breakpoint,
i.e. how many consecutive memory addresses it should match with
<arg>length</arg>.

The break condition will evaluate to true if any of the selected <tt>access
methods</tt> operates on the <tt>address</tt> of the <arg>location</arg> in the
<tt>target memory object</tt>. The default access method is <tt>execution</tt>
and the default target memory object is the <tt>virtual memory space</tt>
of the processor associated with the debug context.

To use other access methods, use any combination <tt>-r</tt> for read,
<tt>-w</tt> for write and <tt>-x</tt> for execute.

To change the target memory object from the <tt>virtual</tt> memory object
to the <tt>physical</tt> memory object of the processor for the debug
context, set the <tt>-p</tt> argument flag.

If <arg>location</arg> could not be resolved to an address among the added
symbol files, it is possible to make the command fail by
specifying <tt>-error-not-planted</tt>.

You can limit the debug contexts the breakpoint applies to by providing a
context query with <arg>context-query</arg>. It defaults to <tt>*</tt>, which
matches all debug contexts.

The command returns the <em>id</em> of the new breakpoint. This can be used to
manage and delete the breakpoint using the <obj>bp</obj> object."""

location_run_until_doc = """
Run until the specified location is reached.
The location is either <arg>location</arg>, which should specify a C expression
or <arg>address</arg>. In addition you can specify the length of the breakpoint,
i.e. how many consecutive memory addresses it should match with
<arg>length</arg>.

The simulation will run until any of the selected <tt>access
methods</tt> operates on the <tt>address</tt> of the location argument in the
<tt>target memory object</tt>. The default access method is <tt>execution</tt>
and the default target memory object is the <tt>virtual memory space</tt>
of the processor associated with the debug context.

To use other access methods, use any combination <tt>-r</tt> for read,
<tt>-w</tt> for write and <tt>-x</tt> for execute.

To change the target memory object from the <tt>virtual</tt> memory object
to the <tt>physical</tt> memory object of the processor for the debug
context, set the <tt>-p</tt> argument flag.

If <arg>location</arg> could not be resolved to an address among the added
symbol files, it is possible to make the command fail by
specifying <tt>-error-not-planted</tt>.

You can limit the debug contexts the breakpoint applies to by providing a
context query with <arg>context-query</arg>. It defaults to <tt>*</tt>, which
matches all debug contexts."""

location_wait_for_doc = """
Wait in the current script branch until specified location is reached.
The location is either <arg>location</arg>, which should specify a C expression
or <arg>address</arg>. In addition you can specify the length of the breakpoint,
i.e. how many consecutive memory addresses it should match with
<arg>length</arg>.

The script branch will wait until any of the selected <tt>access
methods</tt> operates on the <tt>address</tt> of the location argument in the
<tt>target memory object</tt>. The default access method is <tt>execution</tt>
and the default target memory object is the <tt>virtual memory space</tt>
of the processor associated with the debug context.

To use other access methods, use any combination <tt>-r</tt> for read,
<tt>-w</tt> for write and <tt>-x</tt> for execute.

To change the target memory object from the <tt>virtual</tt> memory object
to the <tt>physical</tt> memory object of the processor for the debug
context, set the <tt>-p</tt> argument flag.

If <arg>location</arg> could not be resolved to an address among the added
symbol files, it is possible to make the command fail by
specifying <tt>-error-not-planted</tt>.

You can limit the debug contexts the breakpoint applies to by providing a
context query with <arg>context-query</arg>. It defaults to <tt>*</tt>, which
matches all debug contexts."""

location_trace_doc = """
Enable tracing of the events that the specified location is reached.
The location is either <arg>location</arg>, which should specify a C expression
or <arg>address</arg>. In addition you can specify the length of the breakpoint,
i.e. how many consecutive memory addresses it should match with
<arg>length</arg>.

Any of the selected <tt>access methods</tt> operating on the
<tt>address</tt> of the location argument in the <tt>target memory
object</tt> will be traced. The default access method is
<tt>execution</tt> and the default target memory object is the
<tt>virtual memory space</tt> of the processor associated with the
debug context.

To use other access methods, use any combination <tt>-r</tt> for read,
<tt>-w</tt> for write and <tt>-x</tt> for execute.

To change the target memory object from the <tt>virtual</tt> memory object
to the <tt>physical</tt> memory object of the processor for the debug
context, set the <tt>-p</tt> argument flag.

If <arg>location</arg> could not be resolved to an address among the added
symbol files, it is possible to make the command fail by
specifying <tt>-error-not-planted</tt>.

You can limit the debug contexts the breakpoint applies to by providing a
context query with <arg>context-query</arg>. It defaults to <tt>*</tt>, which
matches all debug contexts."""

class LocationBreakpoints(TCFBreakpoint):
    TYPE_DESC = "source code location breakpoints"
    cls = simics.confclass("bp-manager.src-location", short_doc=TYPE_DESC,
                           doc=TYPE_DESC, pseudo=True)

    @cls.objects_finalized
    def objects_finalized(self):
        conf.bp.iface.breakpoint_type.register_type(
            "source-location",
            self.obj,
            [[["str_t", "uint64_t"], ["location", "address"],
              '1', None, None, "", None],
             ["uint64_t", "length", "?", 1, None, "", None],
             ["flag_t", "-error-not-planted", '1', None, None, "", None],
             ["flag_t", "-r", '1', None, None, "", None],
             ["flag_t", "-w", '1', None, None, "", None],
             ["flag_t", "-x", '1', None, None, "", None],
             ["flag_t", "-p", '1', None, None, "", None],
             ["str_t", "context-query", "?", None, None, "", None]],
            None, 'symdebug',
            ["add breakpoint at a location", location_break_doc,
             "run until reaching location", location_run_until_doc,
             "wait until reaching location", location_wait_for_doc,
             "enable tracing of location reaches", location_trace_doc],
            False, False, False)

    def _breakpoint_utilities(self):
        return self._tcf_module('breakpoint_utilities')

    def _describe_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        return self._breakpoint_utilities().get_location_wait_data(bp.args)

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        tcf = simics.SIM_get_debugger()
        if bp.is_break:
            bm_id = self._tcf_common().register_bp(tcf, bp.tcf_bp_id)
            (planted, planted_msg) = self._tcf_common().get_planted_info(
                tcf, bp.tcf_bp_id, bm_id)
            bp.planted = planted
            bp.planted_msg = planted_msg
            error_not_planted = bp.args[3]
            if error_not_planted and not bp.planted:
                self._tcf_common().delete_bp(tcf, bp.tcf_bp_id)
                return 0
            return bm_id
        else:
            (planted, planted_msg) = self._tcf_common().get_planted_info(
                tcf, bp.tcf_bp_id, None)
            bp.planted = planted
            bp.planted_msg = planted_msg
            error_not_planted = bp.args[3]
            if error_not_planted and not bp.planted:
                self._tcf_common().delete_ep(tcf, bp.tcf_bp_id)
                return 0

            bpm_iface = conf.bp.iface.breakpoint_registration
            return bpm_iface.register_breakpoint(
                self._delete_bm, None, self._get_props, None, None, None,
                None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, flags, args):
        # Remove -once
        params = (['break'] if flags == simics.Breakpoint_Type_Break
                  else ['add']) + args[:-1]
        tcf = simics.SIM_get_debugger()

        try:
            (attrs, _) = self._breakpoint_utilities().create_location_attrs(*params)
            if flags == simics.Breakpoint_Type_Break:
                tcf_bp_id = self._tcf_common().new_bp(tcf, attrs)
            else:
                tcf_bp_id = self._tcf_common().create_ep(tcf, attrs,
                                                         self._bp_cb)
        except cli.CliError as ex:
            print(ex, file=sys.stderr)
            return 0

        (planted, planted_msg) = self._tcf_common().get_planted_info(
            tcf, tcf_bp_id, None)
        return self._create_bp(tcf_bp_id, flags == simics.Breakpoint_Type_Break,
                               planted, planted_msg, args)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        if bp.is_break:
            self._delete_bp(bp_id)
        else:
            self._unregister_bp(bp_id)

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        assert bp_id in self.bp_data
        bp = self.bp_data[bp_id]
        obj = bp.args[0]
        msg = self._breakpoint_utilities().get_location_wait_data(bp.args)
        if obj:
            return f"{obj.name}: {msg}"
        else:
            return msg

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return bp.planted_msg

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        assert bp_id in self.bp_data
        bp = self.bp_data[bp_id]
        return self._breakpoint_utilities().get_location_wait_data(bp.args)

def register_tcf_breakpoints(bpm_class):
    simics.SIM_register_port(bpm_class, "source_line",
                             LineBreakpoints.cls.classname,
                             LineBreakpoints.TYPE_DESC)
    simics.SIM_register_port(bpm_class, "source_location",
                             LocationBreakpoints.cls.classname,
                             LocationBreakpoints.TYPE_DESC)
