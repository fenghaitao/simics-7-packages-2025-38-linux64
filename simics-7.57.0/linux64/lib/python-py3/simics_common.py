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


# File with Python code for simics-common. Run early at startup.
#



import ctypes, os, sys, time
import collections
import types
import socket
import importlib.resources
import platform
import __main__
import cli
import re
import simics
from simicsutils.host import is_windows
from simicsutils.internal import ensure_binary
import simmod
from collections.abc import Callable

from cli import (
    CliError,
    arg,
    doc,
    get_current_cmdline,
    new_command,
    pr,
    string_set_t,
    )
from simics import (
    CORE_acquire_cell,
    CORE_acquire_object,
    CORE_acquire_target,
    CORE_get_current_loading_module,
    CORE_get_py_class_data,
    CORE_host_cpuid_brand_string,
    CORE_host_cpuid_fms,
    CORE_host_hypervisor_info,
    CORE_num_execution_threads,
    CORE_num_sim_obj,
    CORE_python_free_map_target,
    CORE_set_py_class_data,
    CORE_set_settings_dir,
    CORE_get_settings_dir,
    CORE_object_iterator,
    CORE_object_iterator_for_class,
    CORE_object_iterator_for_interface,
    CORE_shallow_object_iterator,
    SIM_VERSION_5,
    SIM_add_notifier,
    SIM_continue,
    SIM_create_class,
    SIM_get_all_modules,
    SIM_get_all_processors,
    SIM_get_attribute,
    SIM_get_batch_mode,
    SIM_get_quiet,
    SIM_get_verbose,
    SIM_hap_add_callback,
    SIM_hap_add_type,
    SIM_hap_delete_callback,
    SIM_hap_occurred_always,
    SIM_license_file,
    SIM_load_module,
    SIM_log_message,
    SIM_notifier_type,
    SIM_quit,
    SIM_register_attribute,
    SIM_simics_is_running,
    SIM_time,
    SIM_version,
    SIM_version_base,
    SIM_version_major,
    SIM_vmxmon_version,
    Sim_Class_Kind_Pseudo,
    Sim_Log_Critical,
    Sim_Log_Error,
    Sim_Log_Warning,
    Sim_Log_Info,
    Sim_Log_Spec_Violation,
    Sim_Log_Unimplemented,
    VT_add_telemetry_data,
    VT_add_telemetry_data_int,
    VT_add_telemetry_data_str,
    VT_generate_object_name,
    VT_get_port_classes,
    VT_get_product_name,
    VT_get_transaction,
    VT_python_extension_data,
    class_info_t,
    map_target_t,
)
from deprecation import DEPRECATED
import cli_impl
from functools import cmp_to_key  # this import is used by old x86 CPUs packages
import confclass
import conf
from simics_session import VT_update_session_key, VT_add_session_handler


# import module to register its class
import terminal_frontend

# temporarily add scripts directory to Python's path
sys.path.append(os.path.join(conf.sim.simics_base, 'scripts'))
try:
    from project import (Project, project_up_to_date)
finally:
    sys.path.pop()

# Only used by modules built with an old 7 version. Remove in Simics 8.
class AliasFinder:
    assert simics.SIM_version_major() == '7'
    def __init__(self):
        self.aliases = {}

    def find_spec(self, name, path, target=None):
        if name in self.aliases:
            return importlib.util.spec_from_loader(name, self)
        return None

    def load_module(self, name):
        # TODO: Add a deprecation warning in the next major release. Bug 21609.
        return self.aliases[name]

    def add_module_alias(self, module, name):
        self.aliases[name] = module

finder = AliasFinder()
sys.meta_path.append(finder)
add_module_alias = finder.add_module_alias
del finder

def ensure_simmod_packages(names):
    '''Ensure that a package `name` exists under simmod, by creating a
    stub module if needed. This is needed by interface modules, which
    populate this package when loaded. */
    '''
    existing_dirs = {
        x.name for x in importlib.resources.files('simmod').iterdir()
        if x.is_dir()}
    for name in names:
        if name in existing_dirs:
            # python creates a package automatically
            continue
        qname = f'simmod.{name}'
        stub = types.ModuleType(qname)
        setattr(simmod, name, stub)
        sys.modules[qname] = stub

def add_to_simics_module(symbol, name=None):
    if name is None:
        name = symbol.__name__
    for mod in (simics, ):
        setattr(mod, name, symbol)

def _SIM_log_warning(dev, grp, msg):
    SIM_log_message(dev, 1, grp, Sim_Log_Warning, msg)

def _SIM_log_error(dev, grp, msg):
    SIM_log_message(dev, 1, grp, Sim_Log_Error, msg)

def _SIM_log_critical(dev, grp, msg):
    SIM_log_message(dev, 1, grp, Sim_Log_Critical, msg)

def _SIM_log_info(lvl, dev, grp, msg):
    SIM_log_message(dev, lvl, grp, Sim_Log_Info, msg)

def _SIM_log_spec_violation(lvl, dev, grp, msg):
    SIM_log_message(dev, lvl, grp, Sim_Log_Spec_Violation, msg)

def _SIM_log_unimplemented(lvl, dev, grp, msg):
    SIM_log_message(dev, lvl, grp, Sim_Log_Unimplemented, msg)

if is_windows():
    ext = '.dll'
else:
    ext = '.so'
h_libsimics = ctypes.CDLL('libsimics-common%s' % ext)
assert h_libsimics.pr_err
assert h_libsimics.pr_warn
assert h_libsimics.SIM_printf_warning
assert h_libsimics.SIM_printf_error
def pr_err(text):
    h_libsimics.pr_err(b"%s", ensure_binary(str(text)))
def pr_warn(text):
    h_libsimics.pr_warn(b"%s", ensure_binary(str(text)))
def _SIM_printf_warning(text):
    pr_warn(text)
def _SIM_printf_error(text):
    pr_err(text)
def _SIM_printf(text):
    pr(text)

add_to_simics_module(confclass.confclass)

add_to_simics_module(_SIM_log_error, "SIM_log_error")
add_to_simics_module(_SIM_log_warning, "SIM_log_warning")
add_to_simics_module(_SIM_log_critical, "SIM_log_critical")
add_to_simics_module(_SIM_log_info, "SIM_log_info")
add_to_simics_module(_SIM_log_spec_violation, "SIM_log_spec_violation")
add_to_simics_module(_SIM_log_unimplemented, "SIM_log_unimplemented")
add_to_simics_module(_SIM_printf, "SIM_printf")
add_to_simics_module(_SIM_printf_warning, "SIM_printf_warning")
add_to_simics_module(_SIM_printf_error, "SIM_printf_error")
add_to_simics_module(pr)
add_to_simics_module(pr_err)
add_to_simics_module(pr_warn)

_sim_continue = SIM_continue
def _SIM_continue(steps):
    # Support floating point numbers - users' code may rely on them a lot -
    # even though Python deprecated automatic float to int conversion.
    return _sim_continue(int(steps) if isinstance(steps, float) else steps)
add_to_simics_module(_SIM_continue, "SIM_continue")

def _SIM_object_data(obj): return obj.object_data
add_to_simics_module(_SIM_object_data, "SIM_object_data")

def _SIM_extension_data(obj, ext_cls):
    return VT_python_extension_data(obj, ext_cls)
add_to_simics_module(_SIM_extension_data, "SIM_extension_data")

# python implementation of SIM_free_map_target
def _SIM_free_map_target(map_target):
    if map_target is None:
        return
    if not isinstance(map_target, map_target_t):
        raise TypeError("not a map_target_t")
    CORE_python_free_map_target(map_target)
add_to_simics_module(_SIM_free_map_target, "SIM_free_map_target")

VT_create_object = simics.SIM_create_object
# Python implementation of SIM_create_object
def _SIM_create_object(*args, **kwargs):
    # TODO: in python 3.9 we can change arg syntax to
    # (cls, name, attrs=None, /, **kwargs)
    if len(args) not in [2, 3]:
        msg = ("SIM_create_object takes 2 to 3 positional"
               + f" arguments: ({len(args)} given)")
        raise TypeError(msg)

    cls, name, attrs, *dontcare = args + ([],)
    attrs += [[k, v] for k, v in kwargs.items()]
    return VT_create_object(cls, name, attrs)
add_to_simics_module(_SIM_create_object, "SIM_create_object")

# Python implementation of SIM_object_iterator
def _SIM_object_iterator(obj):
    return CORE_object_iterator(obj)
add_to_simics_module(_SIM_object_iterator, "SIM_object_iterator")

# Python implementation of SIM_shallow_object_iterator
def _SIM_shallow_object_iterator(obj):
    return CORE_shallow_object_iterator(obj, False)
add_to_simics_module(_SIM_shallow_object_iterator,
                     "SIM_shallow_object_iterator")

def _SIM_object_iterator_for_class(cls):
    return CORE_object_iterator_for_class(cls)
add_to_simics_module(_SIM_object_iterator_for_class,
                     "SIM_object_iterator_for_class")

def _SIM_object_iterator_for_interface(ifaces):
    return CORE_object_iterator_for_interface(ifaces)
add_to_simics_module(_SIM_object_iterator_for_interface,
                     "SIM_object_iterator_for_interface")

def _SIM_set_class_data(cls, data):
    CORE_set_py_class_data(cls, data)

def _SIM_get_class_data(cls):
    return CORE_get_py_class_data(cls)

add_to_simics_module(_SIM_set_class_data, "SIM_set_class_data")
add_to_simics_module(_SIM_get_class_data, "SIM_get_class_data")

# Convenience routine mainly used from tests
# returns 1 if the cpu has turbo support and it is enabled
# returns 0 otherwise
def VT_is_turbo_active(cpu):
    return getattr(cpu, 'turbo_execution_mode', 0)
add_to_simics_module(VT_is_turbo_active)

# Python implementation of SIM_ACQUIRE_*
def _SIM_acquire_target(
        obj, function="<unknown>", source_location="<python file>"):
    return CORE_acquire_target(obj, function, source_location)
def _SIM_acquire_object(
        obj, function="<unknown>", source_location="<python file>"):
    return CORE_acquire_object(obj, function, source_location)
def _SIM_acquire_cell(
        obj, function="<unknown>", source_location="<python file>"):
    return CORE_acquire_cell(obj, function, source_location)
add_to_simics_module(_SIM_acquire_target, "SIM_acquire_target")
add_to_simics_module(_SIM_acquire_object, "SIM_acquire_object")
add_to_simics_module(_SIM_acquire_cell, "SIM_acquire_cell")


# The gulp-generated python bindings don't have a way to manage the
# lifespan of lang_void * arguments, and will therefore conservatively
# incref it so it survives forever. However, in the case of
# SIM_run_alone we know that the reference is dropped after return. To
# work around this, we add _run_and_decref as an indirection, and pass
# both function and data in the lang_void argument. We can then use
# VT_python_decref to explicitly compensate for the reference leak.
def _run_and_decref(wrapped_callback):
    try:
        wrapped_callback()
    finally:
        simics.VT_python_decref(wrapped_callback)
_orig_SIM_run_alone = simics.SIM_run_alone
def _SIM_run_alone(callback, data):
    def wrapped_callback():
        callback(data)
    _orig_SIM_run_alone(_run_and_decref, wrapped_callback)
# Wanted to use @functools.wraps for this, but that caused pypredef failures
_SIM_run_alone.__doc__ = _orig_SIM_run_alone.__doc__

add_to_simics_module(_SIM_run_alone, "SIM_run_alone")

class CliMode:
    __name__ = "cli_mode"
    def __call__(self):
        import command_line
        id = get_current_cmdline()
        command_line.command_line_python_mode(id, False)
        print("Command line is now in CLI mode.")
    def __repr__(self):
        return "Use cli_mode() or Ctrl-D to return to Simics CLI."

cli_mode = CliMode()

# function to switch back from Python mode to CLI mode on a command line
add_to_simics_module(cli_mode)

class _AttrRelay:
    'A class representing the attribute space for a pre_conf_object.'
    __slots__ = ("__dict__", "_po")
    def __init__(self, po):
        self._po = po
        self.__dict__ = po._a
    def __dir__(self):
        return [k for k in self.__dict__ if k[0] != "_"]
    def __call__(self, **args):
        self.__dict__.update(**args)
    def __repr__(self):
        return '<%s attributes>' % self._po.name

class pre_conf_object(
        metaclass=doc(
            'class for Simics configuration object to instantiate',
            module = 'simics',
            synopsis = ('pre_conf_object(object_name, class_name,'
                        ' build_id = None)'),
            doc_id = 'simulator python configuration api')):
    '''A class representing a future Simics configuration object named
    <param>object_name</param>, of class <param>class_name</param>. If
    <param>object_name</param> is <tt>None</tt>, a unique name will be
    generated.

    The <param>build-id</param> of the object can be specified when using the
    <type>pre_conf_object</type> class during checkpoints update. Refer to
    <cite>Model Builder User's Guide</cite> for more information.

    Future configuration attributes are set using normal Python class members:
    <pre>
      a = pre_conf_object("test_object", "test-class")
      a.value = 42</pre>

    After using a <class>pre_conf_object</class> object to create a
    configuration object, the created object can be obtained by passing the
    <class>pre_conf_object</class>'s <tt>name</tt> member to
    <fun>SIM_get_object()</fun>.'''

    __slots__ = ('_a', '_o', '_d', '_p', '_pi', '_relname', '_parent',
                 '_change_monitor', '__dict__')
    def __init__(self, *args, **argv):
        _o = []
        _a = {}
        _d = {}
        self.__dict__ = _a
        if len(args) >= 2:
            (name, classname) = args[:2]
            if not name:
                name = VT_generate_object_name()
            if len(args) >= 3:
                _a["build_id"] = args[2]
                if len(args) > 3:
                    raise TypeError("pre_conf_object() takes at"
                                    " most 3 arguments")
        elif len(args) == 1:
            (name, classname) = ("", args[0])
        elif len(args) == 0:
            (name, classname) = ("", "namespace_root")
        if classname == "index_map":
            classname = "index-map"
        _a.update(
            __object_name__ = name,
            __class_name__ = classname,
            **argv
        )
        self._parent = None     # parent object
        self._a = _a            # { 'attr': value }
        self._d = _d            # hierarchy {'relname': pobj}
        self._o = _o            # child objects [ pre_obj, pre_obj, ... ]
        self._pi = None
        self._change_monitor = None
        self._rebuild_p_pi()

    def __new__(cls, *args, **argv):
        # this is needed to support pickling
        inst = object.__new__(cls)
        inst._a = {}
        inst._d = {}
        inst._p = {}
        return inst

    def __bool__(self):
        return True

    def _rebuild_p_pi(self):
        # port classes defined by parent
        par = self._parent
        from_par = par._pi.get(self._relname, []) \
            if par is not None and par._pi else []
        try:
            raw = VT_get_port_classes(self._a['__class_name__'])
            pc = [(path.replace("]", "").replace("[","."), cls)
                  for (path, cls) in raw.items()]
        except LookupError:
            pc = []
        pc.extend(from_par)

        p = {}
        pi = {}
        old_pi = self._pi
        for (path, cls) in pc:
            if not "." in path:
                p[path] = cls
            else:
                (name, _, path) = path.partition(".")
                ns = 'index-map' if '0' <= path[0] <= '9' else 'namespace'
                p.setdefault(name, ns)
                pi.setdefault(name, []).append((path, cls))

        self._p = p
        self._pi = pi

        # propagate changes to affected children
        if old_pi or pi:
            subs = set(pi)
            if old_pi:
                subs.update(old_pi)
            for name in subs:
                if name in self._d:
                    self._d[name]._rebuild_p_pi()

    def _lookup(self, key):
        p = self._d.get(key, None)
        if p is not None:
            return p
        cls = self._p.get(key, None)
        if cls is not None:
            p = pre_conf_object(cls)
            self._link(key, p)
            return p
        return None

    def __update_name(self, parname):
        if self._parent._a["__class_name__"] == "index-map":
            myname = parname + "[" + self._relname + "]"
        else:
            myname = (parname + "." + self._relname) if parname \
                     else self._relname
        self._a["__object_name__"] = myname
        for o in self._o:
            o.__update_name(myname)

    def _link(self, key, child):
        d = self._d
        old = d.get(key, None)
        if old == child:
            return
        elif old is not None:
            old._unlink()

        d[key] = child
        child._parent = self
        child._relname = key
        child.__update_name(self.name)
        self._o.append(child)

        # propagate port object information to the child
        if key in self._pi:
            child._rebuild_p_pi()

        # trigger notification (and propagation of _change_monitor)
        notifier = self._change_monitor
        if notifier is not None:
            def invoke_notifier(o):
                o._change_monitor = notifier
                notifier.object_added(o)
                for c in o._o:
                    invoke_notifier(c)
            invoke_notifier(child)

    def _unlink(self):
        # trigger notification (and removal of _change_monitor)
        mon = self._change_monitor
        if mon is not None:
            def invoke_mon(o):
                for c in o._o:
                    invoke_mon(c)
                o._change_monitor = None
                mon.object_removed(o)
            invoke_mon(self)

        par = self._parent
        if par is not None:
            self._parent = None
            # discard port object information obtained from old parent
            if self._relname in par._pi:
                self._rebuild_p_pi()
            del par._d[self._relname]
            par._o.remove(self)

    def __getattr__(self, k):
        v = self._lookup(k)
        if v is not None:
            return v
        if k in self._a:
            return self._a[k]
        raise AttributeError(k)

    def __setattr__(self, k, v):
        if k[0] == "_" or k == "name" or k == "classname":
            object.__setattr__(self, k, v)
        else:
            if isinstance(v, pre_conf_object) and v.name == "":
                self._link(k, v)
            elif k in self._d or k in self._p:
                raise ValueError(v)
            else:
                object.__setattr__(self, k, v)

    def __delattr__(self, k):
        if k[0] == "_":
            object.__delattr__(self, k)
        elif k in self._d:
            v = self._d[k]
            if isinstance(v, pre_conf_object):
                v._unlink()
        elif k in self._a:
            del self._a[k]
        else:
            raise AttributeError(k)

    def __setitem__(self, i, v):
        if self.classname != 'index-map':
            raise TypeError("Only 'index-map' pre"
                            " objects support item assignments")
        if not isinstance(v, pre_conf_object):
            raise ValueError("Only unbound pre_conf_objects may be assigned")
        self._link(str(i), v)

    def __getitem__(self, i):
        if self.classname != 'index-map':
            raise TypeError("Only 'index-map' pre objects support indexing")
        r = self._lookup(str(i))
        if r is None:
            raise IndexError("No such index")
        return r

    def __delitem__(self, i):
        if self.classname != 'index-map':
            raise TypeError("Only 'index-map' pre objects support indexing")
        k = str(i)
        if k in self._d:
            v = self._d[k]
            if isinstance(v, pre_conf_object):
                v._unlink()
        else:
            raise IndexError("No such index")

    def __len__(self):
        if self.classname != 'index-map':
            raise TypeError("Only 'index-map' pre objects support len()")
        return len(self._d.keys() | self._p.keys())

    # classname attribute
    def get_classname(self):
        return self._a['__class_name__']
    def set_classname(self, val):
        if self._change_monitor is not None:
            old = self._a['__class_name__']
            self._change_monitor.classname_changed(self, old, val)
        self._a['__class_name__'] = val
        self._rebuild_p_pi()
    classname = property(get_classname, set_classname, None, "classname")
    __class_name__ = property(get_classname, set_classname, None, "classname")
    del get_classname, set_classname

    # name attribute
    def get_name(self):
        return self._a['__object_name__']
    def set_name(self, val):
        self._a['__object_name__'] = val
    name = property(get_name, set_name, None, "object name")
    __object_name__ = property(get_name, set_name, None, "object name")
    del get_name, set_name

    @property
    def attr(self):
        return _AttrRelay(self)
    @attr.setter
    def attr(self, value):
        raise AttributeError("Cannot set 'attr' attribute;"
                             " use attr namespace for the access")

    def __call__(self, **args):
        _AttrRelay(self)(**args)

    @property
    def configured(self):
        return False

    @property
    def _parent_name(self):
        n = self.name
        r = max(n.rfind("["), n.rfind("."))
        return n[:r] if r != -1 else None

    def __ior__(self, child):
        "Add child object to pre conf object."
        relname = child.name.replace("[", ".").replace("]","").split(".")[-1]
        self._link(relname, child)

    def __str__(self):
        name = self.name
        if name:
            comp = self._a.get('component', '')
            slot = self._a.get('component_slot', '')
            if comp and slot:
                return "pre conf object %s (%s) of type %s" % (
                    comp.name + "." + slot, name, self.classname)
            else:
                return "pre conf object %s of type %s" % (name, self.classname)
        else:
            return "unbound conf object of type %s" % (self.classname)
    def __repr__(self):
        return "<%s>" % str(self)
    def __dir__(self):
        return list(self._a.keys()) + list(self._d.keys())

    @staticmethod
    def _linkup(d):
        names = sorted(d)
        for n in names:
            r = max(n.rfind("["), n.rfind("."))
            if r == -1:
                continue
            parname = n[:r]
            par = d.get(parname, None)
            if par is not None:
                par._link(n[r + 1:].replace("]",""), d[n])


add_to_simics_module(pre_conf_object)

class CriticalErrors(
        Exception,
        metaclass=doc(
            'represents critical errors caused by C code called from Python',
            module = 'simics',
            synopsis = 'CriticalErrors(args)')):
    '''This exception is raised when returning to Python from a C function
    that directly or indirectly caused one or more serious, but
    recoverable, errors. Elaborate error descriptions are
    printed when the errors occur, but because of error recovery, the
    C function will be able to continue without being aware of the error.

    A C function can cause more than one error; all these are combined
    into a single Python exception. The main purpose of the exception
    is to aid debugging, usually by providing a nice Python traceback.
    '''

    def __init__(self, errors, function = None):
        self.errors = errors
        self.function = function
        self.args = (self.errors,) + (
            (self.function,) if self.function else ())
        super(Exception, self).__init__(str(self))

    def __str__(self):
        plural = ["s",""][len(self.errors) == 1]
        return (
            "%d critical error%s%s: %s" % (
                len(self.errors), plural,
                ((" in call to %s" % (self.function,))
                 if self.function else ""),
                "; ".join(self.errors)))

add_to_simics_module(CriticalErrors)

import atexit
atexit.register(simics.SIM_shutdown)

def python_at_exit(_, obj):
    # If the simics module is imported into Python, the SIM_shutdown has
    # already been called as an the atexit() handler. Do not call it again.
    atexit.unregister(simics.SIM_shutdown)

    # At exit handlers should be called from Py_Finalize(), but that function
    # crashes when we try to use it. (Perhaps same as Python issue 6531). As
    # workaround, call the atexit handlers explicitly from here.
    try:
        atexit._run_exitfuncs()
    except Exception:
        # Any exception in the atexit handlers will be printed by the atexit
        # module. No need for us to report it again.
        pass

SIM_hap_add_callback("Core_At_Exit", python_at_exit, None)

### GUI Frontend Class

class_name = "gui"
class_data = class_info_t(
    init  = lambda obj: obj,
    description = ("Class used by the built-in GUI to communicate with "
                   "remote frontend handler in Simics."),
    short_desc = "communicates with the remote frontend handler",
    kind = Sim_Class_Kind_Pseudo,
)
cls = SIM_create_class(class_name, class_data)

#
# Project/preferences, etc.
#

def settings_dirname():
    return 'Simics' if is_windows() else '.simics'

# create a settings directory if not already there
def create_settings_dir(cur_dir):
    main_version = SIM_version_major()
    if not cur_dir:
        override = os.environ.get("SIMICS_SETTINGS_DIR", None)
        if override:
            cur_dir = override
    if not cur_dir:
        if is_windows():
            # Use obsolete CSIDL function to make code shorter. Please replace
            # it with better options if available. NB: we don't use
            # win32com since it calls CoInitializeEx which eats desktop heap
            # and on massive parallel Simics invocations may exhaust the heap.
            from ctypes import wintypes, windll, c_int
            CSIDL_APPDATA = 26
            SHGetFolderPath = windll.shell32.SHGetFolderPathW
            SHGetFolderPath.argtypes = [wintypes.HWND,
                                        c_int,
                                        wintypes.HANDLE,
                                        wintypes.DWORD, wintypes.LPCWSTR]

            path_buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            result = SHGetFolderPath(0, CSIDL_APPDATA, 0, 0, path_buf)
            if result != 0:
                raise Exception("Path to APPDATA not found.")
            base_path = path_buf.value
        else:
            base_path = os.path.expanduser('~')
        cur_dir = os.path.join(base_path, settings_dirname(), main_version)
    if not os.path.exists(cur_dir):
        try:
            os.makedirs(cur_dir)
        except OSError as e:
            if not SIM_get_quiet():
                print(f'Failed creating settings directory "{cur_dir}": {e}')
    return cur_dir

#
# Create a directory to save prefs, history, log, etc in
# Preferences are read once settings_dir has been set the first time
#

CORE_set_settings_dir(create_settings_dir(CORE_get_settings_dir()))

#
# Project updating
#

def check_project():
    if conf.sim.project:
        try:
            dirname = conf.sim.project
            if (not os.path.isdir(dirname)
                or not os.path.exists(os.path.join(
                        dirname, '.project-properties'))):
                # illegal project, do nothing
                if SIM_get_verbose():
                    print("Non-configured project: %s" % dirname)
                return
            sb = conf.sim.simics_base
            pl = conf.sim.package_list

            if not project_up_to_date(
                    Project(dirname), sb, pl,
                    sorted(x.strip()
                           for x in SIM_version().strip().split('\n'))):
                pr_err(f"Warning: Project '{dirname}' is not up-to-date.\n")
                if conf.sim.stop_on_error:
                    SIM_quit(1)
        except Exception as e:
            import traceback
            pr_err("Error checking project: {0}.\n{1}".format(
                e, traceback.format_exc()))

def read_license():
    filename = SIM_license_file(None)
    if not filename:
        raise Exception("Failed to find license file. Corrupt installation?\n")
    try:
        return open(filename).readlines()
    except Exception as msg:
        raise Exception("Failed to open the license file '%s'. Error was: '%s'"
                        % (filename, msg))

def freeze_gui_thread():
    try:
        ws = importlib.import_module("simmod.mini_winsome.check_wx")
    except ImportError:
        return
    else:
        ws.prepare_for_shutdown()

###

class ui_run_state:
    '''Keeps track of the simulation run state and signals changes using the
    UI_Run_State_Changed hap. This functionality is mainly intended to be used
    by frontends to show the user if the simulation is stopped or running and
    if it can be run forward or in reverse. There is not yet any way to query
    the current state for frontends that attach during a session.'''
    def __init__(self):
        self.run_state = "Stopped"
        self.script_active = False
        self.test_from_script = False
        self.change_hap = SIM_hap_add_type(
            "UI_Run_State_Changed",
            "s", "state", None,
            'Triggered when the run state changes; not triggered in batch mode.'
            ' The argument is one of:'
            '<dl>'
            '<dt><tt>"Stopped"</tt></dt>'
            '<dd>simulation stopped and may not run</dd>'
            '<dt><tt>"Stopped_Fwd"</tt></dt>'
            '<dd>stopped and may run forward</dd>'
            '<dt><tt>"Forwarding"</tt></dt>'
            '<dd>simulation is running forward</dd>'
            '</dl>',
            0)
        self.enabled = False


    def enable(self):
        if not self.enabled:
            SIM_hap_add_callback("Core_Continuation", self.sim_started, None)
            SIM_hap_add_callback("Core_Simulation_Stopped",
                                 self.stopped_change, None)
            ct_notifier = SIM_notifier_type("cell-thread-change")
            SIM_add_notifier(conf.sim, ct_notifier, None,
                             self.stopped_change_notify, None)
            self.enabled = True

    def change_state(self, new_state):
        if self.run_state != new_state:
            self.run_state = new_state
            SIM_hap_occurred_always(self.change_hap, None, 0, [new_state])

    def queue_exists(self):
        return CORE_num_execution_threads() > 0

    def simulation_running(self):
        return SIM_simics_is_running()

    def update_stopped_state(self):
        if self.simulation_running() or self.script_active:
            # + When the simulation is running, the run state is simply
            #   "Forwarding", no need to check details.
            # + Avoid toggling run state while running a script since there
            #   may be many changes (bug 7959). A script is usually only active
            #   a very short time anyway. The only exception is when running
            #   the simulation from a script, something we also handle.
            return
        may_forward = self.queue_exists()
        if may_forward:
            new_state = "Stopped_Fwd"
        else:
            new_state = "Stopped"
        self.change_state(new_state)

    def set_running_state(self):
        self.change_state("Forwarding")

    def sim_started(self, _, obj):
        self.set_running_state()

    def stopped_change(self, _, obj, *args):
        self.update_stopped_state()

    def stopped_change_notify(self, subscriber, notifier, data):
        self.update_stopped_state()

    def script_started(self):
        if not run_state.test_from_script:
            self.script_active = True
        self.update_stopped_state()

    def script_stopped(self):
        self.script_active = False
        self.update_stopped_state()

run_state = ui_run_state()
if not SIM_get_batch_mode():
    # Don't enable the state tracking in batch mode; it costs too much
    # (the Core_Continuation and Core_Simulation_Stopped haps in particular)
    # and should not be needed when running noninteractively.
    run_state.enable()

def run_state_script_started():
    run_state.script_started()

def run_state_script_stopped():
    run_state.script_stopped()

# allow to test from script
def test_run_state_from_script():
    run_state.enable()
    run_state.test_from_script = True
    run_state.script_active = False


# Register realtime enabled hap here since it is used by both the
# tcf-agent and the realtime module
SIM_hap_add_type("Realtime_Enabled",
                 "i",
                 "enabled",
                 None,
                 "Internal: Notifies change of realtime enabled status",
                 0)

###

# Package info with same format as conf.sim.package_info, but only one entry
# per package number.
collected_packages = {}

def all_packages():
    if not collected_packages:
        for pkg in conf.sim.package_info:
            nbr = pkg[2]
            if nbr not in collected_packages:
                collected_packages[nbr] = pkg
    for nbr in sorted(collected_packages.keys()):
        yield collected_packages[nbr]

def get_simics_packages():
    for (_, name, nbr, ver, _, build, host, _, _, path, *_) in all_packages():
        yield [name, nbr, ver, build, path]

def simics_packages():
    '''Used by Eclipse frontend to list installed packages'''
    for (name, nbr, ver,build, path) in get_simics_packages():
        print('Name:', name)
        print('Number:', nbr)
        print('Version:', ver)
        print('Build-id:', build)
        print('Path:', path)
        print()

def simics_products():
    '''Used by Eclipse frontend to list available products'''
    pass

simics.__doc__ = '''The simics module contains the API for interacting
with the Simics core.'''

# force help() to list all contents
simics.__all__ = sorted(k for k in dir(simics) if not k.startswith('_'))

# List of previously installed build-ids of all currently installed packages.
# If the package was not installed before, 0 is used.
previous_pkg_versions = {}

def previous_installed_build_id(pkg_number):
    # Should only be called with existing package numbers
    return previous_pkg_versions[pkg_number]

class pkgdata:
    def __init__(self, name, version, build_id, prev_build_id):
        self.name = name
        self.version = version
        self.build_id = build_id
        self.prev_build_id = prev_build_id

def pkg_versions_file():
    return os.path.join(conf.sim.settings_dir, "package-versions")

def read_pkg_versions():
    if not conf.sim.use_global_settings:
        return {}
    try:
        pkg_versions = {}
        with open(pkg_versions_file(), "r") as f:
            for l in f:
                try:
                    (pkg_nbr, build_id, prev_build_id) = [int(x.strip())
                                                          for x in l.split(":")]
                except:
                    continue # quiet on format errors
                pkg_versions[pkg_nbr] = pkgdata(None, None,
                                                build_id, prev_build_id)
        return pkg_versions
    except IOError:
        if SIM_get_verbose():
            print("Failed reading %s." % pkg_versions_file())
        return {} # quiet on error by default

def write_pkg_versions(pkg_versions):
    if not conf.sim.use_global_settings:
        return
    try:
        with open(pkg_versions_file(), "w") as f:
            for (pkg_no, pkg) in pkg_versions.items():
                f.write("%d:%d:%d\n" % (pkg_no, pkg.build_id,
                                        pkg.prev_build_id))
    except IOError:
        if SIM_get_verbose():
            print("Failed writing %s." % pkg_versions_file())
        return # quiet on error by default

def check_package_updates():
    global previous_pkg_versions
    known_pkgs = read_pkg_versions()
    cur_pkgs = {}
    for pkg in conf.sim.package_info:
        cur_pkgs[pkg[2]] = pkgdata(pkg[0], pkg[3], pkg[5], 0)
    # Check current packages and see if any were updates of existing ones.
    # Keep info on old packages in case user removes and reinstalls them.
    print_info = False
    for pkg_no in cur_pkgs:
        if not pkg_no in known_pkgs:
            # package not installed before, no previous version
            known_pkgs[pkg_no] = cur_pkgs[pkg_no]
        elif cur_pkgs[pkg_no].build_id > known_pkgs[pkg_no].build_id:
            # package updated, update previous build-id to what was installed
            known_pkgs[pkg_no].prev_build_id = known_pkgs[pkg_no].build_id
            known_pkgs[pkg_no].build_id = cur_pkgs[pkg_no].build_id
            if not SIM_get_quiet():
                print("%s updated to version %s" % (cur_pkgs[pkg_no].name,
                                                    cur_pkgs[pkg_no].version))
                print_info = True
        else:
            # Same package or older than the newest seen. No need to update.
            pass
        previous_pkg_versions[pkg_no] = known_pkgs[pkg_no].prev_build_id
    write_pkg_versions(known_pkgs)
    if print_info:
        print("Use the 'release-notes' command for additional information.")

# Set JIT threading parameters
def adjust_jit_thread_on_config_loaded(data, obj):
    for cell in _SIM_object_iterator_for_class('cell'):
        if cell.enable_cell_threading:
            return

    wt_before = conf.sim.actual_worker_threads
    if conf.sim.max_worker_threads is None:
        # Force a recalculation of the appropriate number of worker threads.
        conf.sim.max_worker_threads = None
        if conf.sim.actual_worker_threads == wt_before:
            return

    if conf.sim.actual_worker_threads > 0:
        th = 500
    else:
        th = 4000
    for cpu in SIM_get_all_processors():
        if hasattr(cpu, "default_turbo_threshold"):
            cpu.default_turbo_threshold = th
        elif hasattr(cpu, "turbo_threshold"):
            # Backward compatibility with old CPU models.
            cpu.turbo_threshold = th

SIM_hap_add_callback(
    "Core_Configuration_Loaded", adjust_jit_thread_on_config_loaded, None)

# Register additional sim.host_* attributes
def register_host_attributes():
    # Returns (ipv4, ipv6) address for the host.
    def host_ips(host_name):
        try:
            addrs = socket.getaddrinfo(host_name, None)
        except socket.gaierror:
            return (None, None)
        ip6 = [x for x in addrs if x[0] == socket.AF_INET6]
        ip4 = [x for x in addrs if x[0] == socket.AF_INET]
        ip4 = ip4[0][4][0] if ip4 else None
        ip6 = ip6[0][4][0] if ip6 else None
        return (ip4, ip6)

    def get_host_ipv4(obj):
        (ipv4, _) = host_ips(obj.host_name)
        return ipv4

    def get_host_ipv6(obj):
        (_, ipv6) = host_ips(obj.host_name)
        return ipv6

    SIM_register_attribute(
        "sim",
        "host_ipv4",
        get_host_ipv4, None,
        simics.Sim_Attr_Pseudo,
        "s|n",
        "The ipv4 address of the host.")

    SIM_register_attribute(
        "sim",
        "host_ipv6",
        get_host_ipv6, None,
        simics.Sim_Attr_Pseudo,
        "s|n",
        "The ipv6 address of the host.")

register_host_attributes()

def _produce_simics_hexversion(simics_version):
    '''Converts 'simics_version' which is expected to have "Simics x.y.z" format
       to a number - similar to sys.hexversion. In case of errors returns 0.
    '''
    m = re.match(r'Simics (\d+)\.(\d+)\.(\d+)$', simics_version)
    if m is None:
        return 0

    # To fit components we reserve 16 bits per component:
    # at the time of writing Simics version is already 6.0.188.
    return (int(m.group(1)) << 32) | (int(m.group(2)) << 16) | int(m.group(3))

# Send information to the separate telemetry collection module
def telemetry_initial_data():
    simics_version = SIM_version_base()
    VT_add_telemetry_data("core.environment", "simics_version",
                          simics_version)
    # We add also "simics_hexversion" number because handling a number is easier
    # than handling the "simics_version" string when processing telemetry data:
    VT_add_telemetry_data_int("core.environment", "simics_hexversion",
                              _produce_simics_hexversion(simics_version))
    vmp_version = SIM_vmxmon_version()
    if vmp_version:
        VT_add_telemetry_data_str("core.environment", "vmp-version",
                                  vmp_version)
    VT_add_telemetry_data("core.environment", "host_type", conf.sim.host_type)
    if is_windows():
        os_name = "Windows " + os_release()
        os_rel = platform.version()
    else:
        import distro
        try:
            (os_name, os_rel) = (distro.id(), distro.version())
        except:
            # Ignore any exceptions from distro and provide something reasonable
            (os_name, os_rel) = (platform.system(), platform.release())
    VT_add_telemetry_data("core.environment", "os", os_name)
    VT_add_telemetry_data("core.environment", "os_release", os_rel)
    host_hv_info = CORE_host_hypervisor_info()
    hypervisor = host_hv_info.vendor if host_hv_info.is_hv_detected else ""
    if "unknown" in hypervisor:  # report what we know (SIMICS-20681)
        hypervisor = (f"unknown ({host_hv_info.sig_b:x}"
                      f" {host_hv_info.sig_c:x} {host_hv_info.sig_d:x})")
    VT_add_telemetry_data("core.environment", "hypervisor", hypervisor)
    VT_add_telemetry_data("core.environment", "host_processor",
                          CORE_host_cpuid_brand_string())
    VT_add_telemetry_data_int("core.environment", "cpuid",
                              CORE_host_cpuid_fms())
    if os.cpu_count():
        VT_add_telemetry_data_int("core.environment", "cpu_count",
                                  os.cpu_count())
    for pkg in conf.sim.package_info:
        VT_add_telemetry_data_str("core.environment", "packages+",
                                  f"{pkg[2]}-{pkg[3]}")
    VT_add_telemetry_data("core.session", "command_line", sys.argv)
    VT_add_telemetry_data("core.session", "start_time", time.time())

    SIM_hap_add_callback("Core_Clean_At_Exit", telemetry_clean_at_exit, None)
    SIM_hap_add_callback("Core_At_Exit", telemetry_at_exit, None)

def telemetry_clean_at_exit(_, obj):
    max_vtime = 0.0
    cells = list(_SIM_object_iterator_for_interface(['cell_inspection']))
    for cell in [x for x in cells if x.current_cycle_obj]:
        max_vtime = max(max_vtime, SIM_time(cell.current_cycle_obj))
    VT_add_telemetry_data("core.session", "virtual_time", max_vtime)
    VT_add_telemetry_data_int("core.platform", "num-objects",
                              CORE_num_sim_obj())

    processors = list(_SIM_object_iterator_for_interface(["execute"]))
    VT_add_telemetry_data_int("core.platform", "num-processors",
                              len(processors))
    VT_add_telemetry_data("core.platform", "processors",
                          list(o.classname for o in processors))

def telemetry_at_exit(_, obj):
    VT_add_telemetry_data("core.session", "stop_time", time.time())
    VT_add_telemetry_data("core.session", "clean_exit", True) # no crash

def print_telemetry_notice():
    # Object does not exist if telemetry was turned off
    if hasattr(conf.sim, 'tlmtry'):
        conf.sim.tlmtry.object_data.print_notice()

def init_script_params():
    from targets import sim_params
    sim_params.init()

def os_release() -> str:
    '''Our version of platform.release() which on Windows 11 (where
       platform.release() returns "10") correctly returns "11".'''
    uname = platform.uname()
    if uname.system != 'Windows' or uname.release != '10':
        return uname.release
    try:
        (_, _, patch) = uname.version.split('.')
        patch = int(patch)
    except ValueError:
        return uname.release
    if patch >= 22000:
        return '11'
    return uname.release

add_to_simics_module(VT_update_session_key)
add_to_simics_module(VT_add_session_handler)

thread_init_callbacks = []

def VT_register_thread_init_callback(f: Callable[[], None]):
    '''Register callback to be run from each Simics thread, at the start of the
       thread execution.'''
    thread_init_callbacks.append(f)

def call_thread_init():
    for f in thread_init_callbacks:
        f()

add_to_simics_module(VT_register_thread_init_callback)
