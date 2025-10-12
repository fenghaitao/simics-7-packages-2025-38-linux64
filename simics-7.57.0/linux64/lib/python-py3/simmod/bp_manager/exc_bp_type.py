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


import sys
import cli
import conf
import simics

break_doc = """
Enables breaking simulation on exceptions.

The <arg>name</arg> or <arg>number</arg> parameter specify which
exception should break the simulation. The available exceptions depend
on the simulated target. Instead of an exception, the <tt>-all</tt>
flag may be given. This will enable break on all exceptions.

If no processor object is specified, the currently selected processor is used.
"""

run_until_doc = """
Run the simulation until the specified exception occurs.

The <arg>name</arg> or <arg>number</arg> parameter specify which
exception should stop the simulation. The available exceptions depend
on the simulated target. Instead of an exception, the <tt>-all</tt>
flag may be given. This will stop the simulation on all
exceptions.

If no processor object is specified, the currently selected processor is used.
"""

wait_for_doc = """
Postpones execution of a script branch until the specified
exception occurs.

The <arg>name</arg> or <arg>number</arg> parameter specify which
exception the script branch should wait on. The available exceptions depend
on the simulated target. Instead of an exception, the <tt>-all</tt>
flag may be given. The script branch will then wait on any exception.

If no processor object is specified, the currently selected processor is used.
"""

trace_doc = """
Enables tracing of exceptions. When this
is enabled, every time the specified exception occurs
during simulation, a message is printed.

The <arg>name</arg> or <arg>number</arg> parameter specify which
exception the script branch should wait on. The available exceptions depend
on the simulated target. Instead of an exception, the <tt>-all</tt>
flag may be given, which results in all exceptions being traced.

If no processor object is specified, the currently selected processor is used.
"""

def _exception_iface(obj):
    return getattr(obj.iface, 'exception', None)

class ExcArgument:
    def __init__(self, exc_cli_arg):
        self.all = exc_cli_arg and exc_cli_arg[2] == '-all'
        self.number = exc_cli_arg[1] if (
            exc_cli_arg and exc_cli_arg[2] == 'number') else None
        self.name = exc_cli_arg[1] if (
            exc_cli_arg and exc_cli_arg[2] == 'name') else None

    def is_all(self):
        return self.all

    def is_number(self):
        return self.number is not None

    def is_name(self):
        return self.name is not None

class ExceptionError(Exception):
    def __init__(self, msg):
        self.msg = msg

class Exceptions:
    def __init__(self):
        self.exc_objects = None
        self.exc_info = None

    @staticmethod
    def _exc_info_per_cpu(exc_objects):
        info = {}
        for cpu in exc_objects:
            cpu_info = info.setdefault(cpu, {})
            cpu_info['arch'] = cpu.iface.processor_info_v2.architecture()
            exc_iface = cpu.iface.exception
            cpu_info['name-to-number'] = dict(
                [[exc_iface.get_name(x), x] for x in (
                    exc_iface.all_exceptions())])
            cpu_info['number-to-name'] = dict(
                [[x, exc_iface.get_name(x)] for x in (
                    exc_iface.all_exceptions())])
        return info

    @staticmethod
    def _org_name_info(per_cpu_info):
        info = {}
        for (cpu, cpu_info) in per_cpu_info.items():
            for (name, num) in cpu_info['name-to-number'].items():
                name_info = info.setdefault(name, {})
                num_info = name_info.setdefault(num, {})
                cpu_list = num_info.setdefault(cpu_info['arch'], [])
                cpu_list.append(cpu)
        return info

    @staticmethod
    def _unique_name_info(org_name_info):
        def only_cpus(arches_and_cpus):
            return [x for y in arches_and_cpus.values() for x in y]

        def num_and_cpus(number, arches_and_cpus):
            return {'number': number, 'cpus': only_cpus(arches_and_cpus)}

        info = {}
        for (name, number_info) in org_name_info.items():
            single_number = len(number_info) == 1
            if single_number:
                number = list(number_info.keys())[0]
                arches_and_cpus = number_info[number]
                info[name] = num_and_cpus(number, arches_and_cpus)
            else:
                for (number, arches_and_cpus) in number_info.items():
                    postfix = ','.join(arches_and_cpus.keys())
                    unique_name = f'{name}-{postfix}'
                    info[unique_name] = num_and_cpus(
                        number, arches_and_cpus)
        return info

    @staticmethod
    def _objects_filtered(objects, filters):
        return [x for x in objects if all([f(x) for f in filters])]

    @staticmethod
    def _keep_prefixed_objects(objs, prefix):
        return [x for x in objs if (
            prefix is None or x.name.startswith(prefix))]

    def _exc_for_cpu(self, cpu):
        result = {'name-to-number': {}, 'number-to-name': {}}
        for (name, info) in self.exc_info.items():
            if not cpu in info['cpus']:
                continue
            result['name-to-number'][name] = info['number']
            result['number-to-name'][info['number']] = name
        return result

    def _exc_names_for_cpus(self, cpus):
        names = set()
        for cpu in cpus:
            names.update(self._exc_for_cpu(cpu)['name-to-number'].keys())
        return list(names)

    @staticmethod
    def _children_and_parents(children):
        def obj_and_parents(obj, result):
            if obj is None:
                return
            if obj.classname != 'index-map':
                result.add(obj)
            obj_and_parents(simics.SIM_object_parent(obj), result)

        objs = set()
        for obj in children:
            obj_and_parents(obj, objs)
        return sorted(objs, key=lambda x: x.name)

    def should_update(self):
        if self.exc_objects is None:
            return True
        if (set(self.exc_objects)
            != set(simics.SIM_object_iterator_for_interface(
                ['exception']))):
            return True
        return False

    def update(self):
        self.exc_objects = list(simics.SIM_object_iterator_for_interface(
            ['exception']))
        per_cpu_info = self._exc_info_per_cpu(self.exc_objects)
        org_name_info = self._org_name_info(per_cpu_info)
        self.exc_info = self._unique_name_info(org_name_info)

    def objects_with_exc_iface(self, parent):
        return self._objects_filtered(self.exc_objects, [
            lambda x: parent is None or x.name.startswith(parent.name)])

    def exc_name_from_number(self, obj, number):
        if not obj in self.exc_objects:
            raise ExceptionError(
                f"The object '{obj.name}' does not implent the 'exceptions'"
                " interface.")
        number_to_name = self._exc_for_cpu(obj)['number-to-name']
        if not number in number_to_name:
            raise ExceptionError(f"The object '{obj.name}' has no exception"
                                 f" with number {number}.")
        return self._exc_for_cpu(obj)['number-to-name'][number]

    def exc_number_from_name(self, name):
        if not name in self.exc_info:
            raise ExceptionError(f"The exception '{name}' is not valid.")
        return self.exc_info[name]['number']

    def objects_with_exc_name(self, name, prefix):
        if not name in self.exc_info:
            raise ExceptionError(f"The exception '{name}' is not valid.")
        return self._keep_prefixed_objects(
            [x for x in self.exc_info[name]['cpus']], prefix)

    def expand_exc_number(self, obj):
        assert(obj)
        return [str(x) for x in self._exc_for_cpu(obj)['number-to-name']]

    def expand_exc_name(self, obj, recursive):
        if recursive:
            objs = self._objects_filtered(
                self.exc_objects, [lambda x: x.name.startswith(
                    obj.name) if obj else True])
            names = self._exc_names_for_cpus(objs)
        else:
            names = self._exc_for_cpu(obj)['name-to-number'].keys()
        return sorted(names)

    def expand_obj_name(self, exc_arg, recursive, prefix):
        if exc_arg.is_name():
            if exc_arg.name in self.exc_info:
                objs_with_exc = [x for x in self.exc_info[exc_arg.name]['cpus']]
            else:
                objs_with_exc = []
        elif exc_arg.is_number():
            objs_with_exc = self._objects_filtered(self.exc_objects, [
                lambda x: exc_arg.number in (
                    self._exc_for_cpu(x)['number-to-name'])])
        else:
            objs_with_exc = self.exc_objects

        objs_with_exc = self._keep_prefixed_objects(objs_with_exc, prefix)

        if recursive:
            objs = self._objects_filtered(
                self._children_and_parents(objs_with_exc),
                [lambda x: prefix is None or (
                    x.name.count('.') <= (prefix.count('.') + 1))])
        else:
            objs = objs_with_exc

        return [x.name for x in objs]

class Breakpoint:
    __slots__ = ('hap_ids', 'exc_nr', 'exc_name',
                 'track_all', 'once', 'last_exc', 'last_cpu')
    def __init__(self, hap_ids, exc_nr, exc_name, track_all, once):
        self.hap_ids = hap_ids
        self.exc_nr = exc_nr
        self.exc_name = exc_name
        self.track_all = track_all
        self.once = once
        self.last_exc = None
        self.last_cpu = None

    def __str__(self):
        name = "any" if self.track_all else f"'{self.exc_name}'"
        return f"{name} exception"

    def cpus(self):
        return sorted(self.hap_ids.keys())

    def cpu_names(self):
        return [x.name for x in self.cpus()]

    def cpu_names_fmt(self, sep=', '):
        if len(self.cpus()) == 1:
            return self.cpus()[0].name
        return sep.join(self.cpu_names())

class ExcBreakpoints:
    TYPE_DESC = "exception breakpoints"
    cls = simics.confclass("bp-manager.exc", doc=TYPE_DESC,
                           short_doc=TYPE_DESC, pseudo=True)
    HAP_NAME = "Core_Exception"

    def __init__(self):
        self.bp_data = {}
        self.next_id = 1
        self.exceptions = None

    @cls.objects_finalized
    def objects_finalized(self):
        conf.bp.iface.breakpoint_type.register_type(
            "exception", self.obj,
            [[["str_t", "int_t", "flag_t"], ["name", "number", "-all"],
              '1', None, None, "", [True, True, None]]],
            None, 'exception', [
                "set break on exception", break_doc,
                "run until specified exception occurs", run_until_doc,
                "wait for specified exception", wait_for_doc,
                "enable tracing of exceptions", trace_doc],
            False, False, True)

    def _delete_bp(self, _, bm_id):
        self.remove_bp(conf.bp.iface.breakpoint_type.get_break_id(bm_id))

    def _describe_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        cpu_names = bp.cpu_names_fmt(sep='\n')
        return f"Break on {bp} on the following objects:\n{cpu_names}"

    def _get_props(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        bp = self.bp_data[bp_id]
        return {"temporary": bp.once,
                "planted": True,
                "object": bp.cpu_names(),
                "description": self._describe_bp(bp_id)}

    def _create_bp(self, cpus, track_all, exc_name, exc_num, once):
        bp_id = self.next_id
        self.next_id += 1
        hap_ids = {}
        for cpu in cpus:
            if track_all:
                hap_ids[cpu] = simics.SIM_hap_add_callback_obj(
                    self.HAP_NAME, cpu, 0, self._bp_cb, bp_id)
            else:
                hap_ids[cpu] = simics.SIM_hap_add_callback_obj_index(
                    self.HAP_NAME, cpu, 0, self._bp_cb, bp_id, exc_num)

        self.bp_data[bp_id] = Breakpoint(hap_ids, exc_num, exc_name, track_all,
                                         once)
        return bp_id

    def _bp_cb(self, bp_id, cpu, exc_nr):
        bp = self.bp_data[bp_id]
        bp.last_exc = exc_nr
        bp.last_cpu = cpu
        cli.set_current_frontend_object(bp.last_cpu, True)
        conf.bp.iface.breakpoint_type.trigger(self.obj, bp_id, cpu,
                                              self.trace_msg(bp_id))
        return 1

    def _get_exceptions(self):
        if not self.exceptions:
            self.exceptions = Exceptions()
        if self.exceptions.should_update():
            self.exceptions.update()
        return self.exceptions

    @staticmethod
    def _current_cpu():
        cpu = cli.current_cpu_obj_null()
        if cpu and _exception_iface(cpu):
            return cpu
        raise ExceptionError(
            "No object implementing the 'exception' interface provided in"
            " 'object' argument, and the current processor could not be used.")

    @staticmethod
    def _check_recursive_args(obj, exc_arg):
        if not obj:
            raise ExceptionError("To break with '-recursive', the 'object'"
                                 " argument must be specified.")
        if exc_arg.is_number():
            raise ExceptionError("Only exception names can be specified when"
                                 " using '-recursive'.")

    @staticmethod
    def _check_recursive_cpus(obj, cpus):
        if not cpus:
            raise ExceptionError(
                f"Found no CPUs to break on under '{obj.name}'.")

    @staticmethod
    def _check_non_recursive_args(obj):
        if not _exception_iface(obj):
            raise ExceptionError(
                f"The object '{obj.name}' does not implement the 'exception'"
                " interface, and cannot be used for planting breakpoint."
                " Either use specify an object which implements 'exception'"
                " or use '-recursive'.")

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bpm_iface = conf.bp.iface.breakpoint_registration
        return bpm_iface.register_breakpoint(
            self._delete_bp, None, self._get_props, None, None, None,
            None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, flags, args):
        (obj, exc_cli_arg, recursive) = args[:3]
        once = False if flags == simics.Breakpoint_Type_Trace else args[3]
        exc_arg = ExcArgument(exc_cli_arg)

        exceptions = self._get_exceptions()
        try:
            if recursive:
                self._check_recursive_args(obj, exc_arg)
            else:
                if not obj:
                    obj = self._current_cpu()
                else:
                    self._check_non_recursive_args(obj)

            if exc_arg.is_all():
                (exc_name, exc_number) = (None, None)
                cpus = exceptions.objects_with_exc_iface(obj) if (
                    recursive) else [obj]
            elif exc_arg.is_number():
                exc_number = exc_arg.number
                exc_name = exceptions.exc_name_from_number(obj, exc_number)
                cpus = [obj]
            elif exc_arg.is_name():
                exc_name = exc_arg.name
                exc_number = exceptions.exc_number_from_name(exc_name)
                if recursive:
                    cpus = exceptions.objects_with_exc_name(
                        exc_name, obj.name)
                else:
                    cpus = [obj]

            if recursive:
                self._check_recursive_cpus(obj, cpus)

        except ExceptionError as e:
            print(e.msg)
            return 0

        return self._create_bp(
            cpus, exc_arg.is_all(), exc_name, exc_number, once)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        for (cpu, hap_id) in bp.hap_ids.items():
            simics.SIM_hap_delete_callback_obj_id(self.HAP_NAME, cpu, hap_id)
        del self.bp_data[bp_id]

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        # This can be called before any access, e.g. from test-trigger
        if bp.last_exc is not None:
            exc_name = bp.last_cpu.iface.exception.get_name(bp.last_exc)
            return f"{exc_name}({bp.last_exc}) exception triggered"
        else:
            return ""

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        cpu_names = bp.cpu_names_fmt(sep='\n')
        return f"Break on {bp} for the following objects:\n{cpu_names}"

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"{bp.cpu_names_fmt()} waiting on {bp}"

    @cls.iface.breakpoint_type_provider.values
    def values(self, arg, prev_args):
        prefix = prev_args[-1]
        (obj, exc_cli_arg, recursive) = prev_args[1:4] if (
            prev_args[0] == conf.bp.exception) else prev_args[:3]
        exceptions = self._get_exceptions()
        result = []

        if arg == 'number':
            # Numbers are not supported in combination with -recursive.
            if not obj and not recursive:
                try:
                    obj = self._current_cpu()
                except ExceptionError:
                    pass
            if obj:
                result = exceptions.expand_exc_number(obj)
        elif arg == 'name':
            try:
                if not obj and not recursive:
                    obj = self._current_cpu()
                result = exceptions.expand_exc_name(obj, recursive)
            except ExceptionError:
                pass
        elif arg == 'object':
            result = exceptions.expand_obj_name(
                ExcArgument(exc_cli_arg), recursive, prefix)
        return result

    @cls.iface.breakpoint_type_provider.break_data
    def break_data(self, bp_id):
        bp = self.bp_data[bp_id]
        if bp.last_exc is not None:
            return bp.last_cpu.iface.exception.get_name(bp.last_exc)
        else:
            return None

def register_exc_breakpoints(bpm_class):
    simics.SIM_register_port(bpm_class, "exception",
                             ExcBreakpoints.cls.classname,
                             ExcBreakpoints.TYPE_DESC)
