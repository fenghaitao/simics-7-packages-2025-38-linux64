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


# Implementation of simics.confclass (a Python API for creating Simics classes)

import cli, simics, collections, traceback
import pyclass_common

def _wrap(f):
    if f is not None:
        def wrap(obj, *args):
            return f(simics.SIM_object_data(obj), *args)
        return wrap

class _InterfaceMethod:
    __slots__ = ('_name', '_d')
    def __init__(self, d, name):
        self._name = name
        self._d = d

    def __set__(self, f):
        self._d[self._name] = f

    def __call__(self, f):
        self._d[self._name] = f
        return f

class _Interface:
    __slots__ = ("_methods")
    def __init__(self):
        self._methods = {}

    def _copy(self):
        i = _Interface()
        i._methods = self._methods.copy()
        return i

    def __getattr__(self, name):
        return _InterfaceMethod(self._methods, name)

    def __call__(self, *args, **kwd):
        for f in args:
            k = getattr(f, "__name__", None)
            if not callable(f) or not k:
                raise TypeError("__call__() only takes"
                                " named interface functions as arguments")
            self._methods[k] = f
        self._methods.update(kwd)

    def _register(self, cls, key):
        (iface, port) = key
        m = self._methods
        itype = simics.SIM_get_python_interface_type(iface)
        if not itype:
            raise TypeError("Interface %s is not available in Python"
                            % iface)
        methods = itype(**{k: _wrap(m[k]) for k in m})
        if port:
            simics.SIM_register_port_interface(cls, iface, methods, port, None)
        else:
            simics.SIM_register_interface(cls, iface, methods)

class _InterfaceNS:
    def __init__(self, d, port = ""):
        self._d = d
        self._port = port
    def __getattr__(self, name):
        k = (name, self._port)
        if k not in self._d:
            self._d[k] = _Interface()
        return self._d[k]

class _PortsNS:
    def __init__(self, d):
        self._d = d
    def __getattr__(self, port):
        return _InterfaceNS(self._d, port)


_unset = object()

def _is_unset(arg):
    return arg is _unset

def _is_set(arg):
    return arg is not _unset

class _Attribute:
    __slots__ = ('_clsname', '_target', '_getter', '_setter', '_kind',
                 '_type', '_default', 'doc')

    def __init__(self, classname, target):
        self._clsname = classname
        self._target = target
        self._getter = _unset
        self._setter = _unset
        self._kind = simics.Sim_Attr_Required
        self._type = _unset     # type string
        self.doc = None
        self._default = _unset

    def _copy(self, classname):
        a = _Attribute(classname, self._target)
        a._getter = self._getter
        a._setter = self._setter
        a._kind = self._kind
        a._type = self._type
        a.doc = self.doc
        a._default = self._default
        return a

    def _desc(self):
        return '%s.%s' % (self._clsname, self._target)

    # @cls.attr.name.getter decorator
    @property
    def getter(self):
        if self._getter is None:
            raise simics.SimExc_Attribute(
                f"The attribute {self._desc()} is write-only and cannot provide"
                " an attribute getter.")
        def getter(f):
            self._getter = f
            if f.__doc__:
                self.doc = f.__doc__
        return getter

    # cls.attr.name.getter assignment
    @getter.setter
    def getter(self, val):
        self._getter = val

    # @cls.attr.name.setter decorator
    @property
    def setter(self):
        if self._setter is None:
            raise simics.SimExc_Attribute(
                f"The attribute {self._desc()} is read-only and cannot provide"
                " an attribute setter.")
        def setter(f):
            self._setter = f
            if f.__doc__:
                self.doc = f.__doc__
        return setter

    # cls.attr.name.setter assignment
    @setter.setter
    def setter(self, val):
        self._setter = val

    # cls.attr.name.default attribute
    @property
    def default(self):
        return self._default
    @default.setter
    def default(self, value):
        if (self._kind & 7) == simics.Sim_Attr_Required:
            self._kind = (self._kind & ~7) | simics.Sim_Attr_Optional
        self._default = value
    @default.deleter
    def default(self):
        self._default = _unset

    # cls.attr.name('type', ...) attribute declaration
    def __call__(self, attr_type, *, kind = _unset,
                 optional = _unset, pseudo = False,
                 doc = _unset, default = _unset, setter = _unset,
                 getter = _unset, read_only = False, write_only = False):

        if _is_unset(kind):
            kind = self._kind
        if optional is False:
            kind = (kind & ~7) | simics.Sim_Attr_Required
        elif optional is True:
            kind = (kind & ~7) | simics.Sim_Attr_Optional
        if pseudo:
            kind = (kind & ~7) | simics.Sim_Attr_Pseudo
        self._kind = kind

        if read_only:
            if _is_set(setter) and setter is not None:
                raise ValueError(
                    f"Since the '{self._desc()}' attribute was created with the"
                    " 'read_only' argument set to true, the 'setter' argument"
                    " should not be set, or be set to None.")
            setter = None

        if write_only:
            if _is_set(getter) and getter is not None:
                raise ValueError(
                    f"Since the '{self._desc()}' attribute was created with the"
                    " 'write_only' argument set to true, the 'getter' argument"
                    " should not be set, or be set to None.")
            getter = None

        if _is_set(setter):
            self._setter = setter
        if _is_set(getter):
            self._getter = getter

        self._type = attr_type
        if _is_set(doc):
            self.doc = doc
        if _is_set(default):
            self.default = default

    def _register(self, cls, name):
        tgt = self._target
        getter = self._getter
        if _is_unset(getter):
            def getter(self):
                return getattr(self, tgt)

        setter = self._setter
        if _is_unset(setter):
            def setter(self, val):
                setattr(self, tgt, val)
                return simics.Sim_Set_Ok

        def _wrap_getter(desc, f):
            if f is not None:
                def wrap(obj):
                    py_obj = simics.SIM_object_data(obj)
                    return pyclass_common.handle_attr_get_errors(
                        desc, f, py_obj)
                return wrap

        def _wrap_setter(desc, f):
            if f is not None:
                def wrap(obj, value):
                    py_obj = simics.SIM_object_data(obj)
                    return pyclass_common.handle_attr_set_errors(
                        desc, f, py_obj, value)
                return wrap
        desc = '%s.%s' % (cls.classname, name)
        simics.SIM_register_attribute(
            cls, name, _wrap_getter(desc, getter), _wrap_setter(desc, setter),
            self._kind, self._type, self.doc)


class _AttrNS:
    __slots__ = ("_clsname","_check_conflict", "_d")
    def __init__(self, classname, check_conflict, d):
        self._clsname = classname
        self._check_conflict = check_conflict
        self._d = d
    def __getattr__(self, name):
        if name not in self._d:
            self._check_conflict(name)
            self._d[name] = _Attribute(self._clsname, name)
        return self._d[name]

class _Command:
    __slots__ = ("_cmd_name", "_method")
    def __init__(self, cmd_name):
        assert cmd_name in ["info", "status"]
        self._method = None
        self._cmd_name = cmd_name

    def _copy(self):
        clone = _Command(self._cmd_name)
        clone._method = self._method.copy()
        return clone

    def __getattr__(self, name):
        assert name == self._cmd_name
        return self._method

    def __call__(self, fun):
        decorator = f"The <confclass>.command.{self._cmd_name}"
        if not callable(fun):
            raise TypeError(f"{decorator} must be used on a function.")
        if not getattr(fun, "__name__", False):
            raise TypeError(f"{decorator} must be used on a named function.")
        self._method = fun

    def _register(self, cls, key):
        reg_fun = cli.new_info_command if self._cmd_name == "info" else (
            cli.new_status_command)
        reg_fun(cls.classname, _wrap(self._method))

class _CommandNS:
    __slots__ = ("_d")
    def __init__(self, d):
        self._d = d
    def __getattr__(self, name):
        supported = ["info", "status"]
        if name not in supported:
            raise TypeError(
                f"Custom commands ({name}) are not supported."
                f" Only {' and '.join(supported)} commands are supported.")
        if name not in self._d:
            self._d[name] = _Command(name)
        return self._d[name]

class _ConfigMethod:
    __slots__ = ("_d", "_name")
    def __init__(self, d, name):
        self._d = d
        self._name = name
    def __call__(self, f):
        self._d[self._name] = f
        return f

class _PortObject:
    __slots__ = ("_cls", "_desc")
    def __init__(self, cls, desc):
        assert isinstance(cls, str) or isinstance(cls, confclass)
        self._cls = cls
        self._desc = desc

    def _has_shared_object_data(self):
        return isinstance(self._cls, confclass)

    # Register port object
    def _register(self, ccls, relname):
        pcls = self._cls
        if self._has_shared_object_data():
            def port_constructor(obj):
                return simics.SIM_port_object_parent(obj).object_data
            pcls.register(constructor = port_constructor)
            pcls = pcls.classname
        simics.SIM_register_port(ccls, relname, pcls, self._desc or None)

    def _copy(self, par):
        cls = self._cls
        if isinstance(cls, confclass):
            cls = confclass(cls._clsname, parent = cls, opar = par)
        return _PortObject(cls, self._desc)

class _ObjNS:
    __slots__ = ("_cls", "_base")
    def __init__(self, cls, base):
        self._cls = cls
        self._base = base
    def __getattr__(self, name):
        base = f"{self._base}.{name}" if self._base else name
        return _ObjNS(self._cls, base)
    def __call__(self, classname = "", desc = "", port = ""):
        if port and self._base:
            port = f"{self._base}.{port}"
        else:
            port = self._base + port
        d = self._cls._objs

        # Support retrieving an existing port object definition, which
        # is primarily useful when the definition is inherited
        if not classname and port in d:
            po = d[port]
            if isinstance(po._cls, confclass):
                if desc:
                    po._desc = desc
                return po._cls

        if classname and not classname.startswith("."):
            cls = classname
        elif classname:
            cls = confclass(classname, opar = self._cls)
        else:
            cls = confclass("." + port.rpartition(".")[2], opar = self._cls)
        d[port] = _PortObject(cls, desc)
        if isinstance(cls, confclass):
            return cls


class confclass:
    "Confclass Documentation"
    __slots__ = ("_clsname", "_constructor", "_objs",
                 "_config", "_attr", "_command", "_iface", "_extension",
                 "_class_kind", "_class_desc", "_description",
                 "_opar", "_auto_register")

    def __init__(self, classname = "", parent = None, **kwd):
        self._constructor = None
        if parent is not None:
            self._config = parent._config.copy()
            self._attr = collections.OrderedDict(
                (k, x._copy(classname)) for (k, x) in parent._attr.items())
            self._command = parent._command.copy()
            self._iface = dict(
                (k, x._copy()) for (k, x) in parent._iface.items())
            self._extension = list(parent._extension)
            kind = parent._class_kind
            self._class_desc = parent._class_desc
            self._description = parent._description
            self._objs = dict(
                (k, x._copy(self)) for (k, x) in parent._objs.items())
        else:
            self._config = {}
            self._attr = collections.OrderedDict()
            self._command = {}
            self._iface = {}
            self._extension = []
            kind = simics.Sim_Class_Kind_Vanilla
            self._class_desc = None
            self._description = None
            self._objs = {}             # port objects
        self._clsname = classname

        if kwd.pop('pseudo', False):
            kind = simics.Sim_Class_Kind_Pseudo
        self._class_kind = kind

        if 'doc' in kwd:
            self.doc = kwd.pop('doc')
        if 'short_doc' in kwd:
            self.short_doc = kwd.pop('short_doc')

        self._opar = kwd.pop('opar', None)
        self._auto_register = kwd.pop('register', bool(classname))
        if kwd:
            raise TypeError("illegal keyword argument")

    def __repr__(self):
        return "<confclass %s>" % self.classname

    def _objs_sharing_object_data(self):
        """Returns all confclass:es that share object_data."""
        parent_obj = self._opar if (self._opar is not None) else self
        objs = [obj._cls for obj in parent_obj._objs.values()
                if (obj._has_shared_object_data() and obj._cls is not self)]
        if parent_obj is not self:
            objs.append(parent_obj)
        return objs

    def _check_attr_conflict(self, name):
        """Raise an exception if adding an attribute named 'name' would conflict
        with another attribute with the same name in classes that share the same
        object data."""
        for other_obj in self._objs_sharing_object_data():
            other_attrs = [attr._target for attr in other_obj._attr.values()]
            if name in other_attrs:
                raise TypeError(
                    f"Attribute conflict for attribute '{name}' between class"
                    f" '{other_obj.classname}' and '{self.classname}'")

    @property
    def iface(self):
        return _InterfaceNS(self._iface)

    @property
    def ports(self):
        return _PortsNS(self._iface)

    @property
    def o(self):
        return _ObjNS(self, "")

    @property
    def command(self):
        return _CommandNS(self._command)

    @property
    def attr(self):
        return _AttrNS(self.classname, self._check_attr_conflict, self._attr)

    def extend(self, ext):
        "Wrapper of SIM_extend_class(ext)"
        self._extension.append(ext)

    @property
    def init(self):
        "Decorator for 'init' class method."
        return _ConfigMethod(self._config, "init")
    @property
    def finalize(self):
        "Decorator for 'finalize' class method."
        return _ConfigMethod(self._config, "finalize")
    @property
    def objects_finalized(self):
        "Decorator for 'objects_finalized' class method."
        return _ConfigMethod(self._config, "objects_finalized")
    @property
    def deinit(self):
        "Decorator for 'deinit' class method."
        return _ConfigMethod(self._config, "deinit")

    @property
    def class_constructor(self):
        def ret(f):
            self._config["class_constructor"] = f
            return staticmethod(f)
        return ret

    @property
    def constructor(self):
        return _ConfigMethod(self._config, "constructor")

    @property
    def classname(self):
        if self._clsname.startswith(".") and self._opar:
            return self._opar.classname + self._clsname
        return self._clsname

    @classname.setter
    def classname(self, classname):
        self._clsname = classname

    @property
    def kind(self):
        return self._class_kind
    @kind.setter
    def kind(self, val):
        self._class_kind = val

    @property
    def doc(self):
        "Class documentation (long)."
        return self._description
    @doc.setter
    def doc(self, desc):
        self._description = desc

    @property
    def short_doc(self):
        "Class documentation (one line)."
        return self._class_desc
    @short_doc.setter
    def short_doc(self, desc):
        self._class_desc = desc

    # Automatic class registration
    def __set_name__(self, owner, name):
        if self._auto_register and not self._opar:
            self._config["default_constructor"] = owner
            try:
                self.register()
            except Exception:
                traceback.print_exc()
                raise

    def register(self, constructor = None):
        c = self._config
        if constructor:
            c["constructor"] = constructor
        defaults = tuple(
            (k, v.default)
            for (k, v) in self._attr.items()
            if _is_set(v.default))

        constructor = c.get("constructor",
                            c.get("default_constructor", None))

        # Pick class description from class object doc string.
        if (self._description is None and isinstance(constructor, type)
            and hasattr(constructor, "__doc__")):
            self._description = constructor.__doc__

        def make_init_object():
            init_object = c.get("init", lambda x:x)
            def init_object_wrapper(obj):
                if isinstance(constructor, type):
                    pobj = constructor.__new__(constructor)
                    # make 'obj' and default attributes available in __init__
                    pobj.obj = obj
                    for (k, v) in defaults:
                        setattr(pobj, k, v() if callable(v) else v)
                    pobj.__init__()
                else:
                    pobj = constructor(obj)
                    for (k, v) in defaults:
                        setattr(pobj, k, v() if callable(v) else v)
                ret = init_object(pobj)
                return pobj if ret is None else ret

            return init_object_wrapper

        def make_delete_instance():
            wrap_del_instance = _wrap(c.get("deinit", lambda x:None))
            def wrap_delete_instance(obj):
                wrap_del_instance(obj)
            return wrap_delete_instance

        cd = simics.class_info_t(
            init = make_init_object(),
            finalize = _wrap(c.get("finalize", None)),
            objects_finalized = _wrap(c.get("objects_finalized", None)),
            deinit = make_delete_instance(),
            kind = self._class_kind,
            description = self._description,
            short_desc = self.short_doc,
        )

        # Register class
        ccls = simics.SIM_create_class(self.classname, cd)

        for (aname, a) in self._attr.items():
            a._register(ccls, aname)
        for (cmd_name, cmd_obj) in self._command.items():
            cmd_obj._register(ccls, cmd_name)
        for (k, i) in self._iface.items():
            i._register(ccls, k)

        # Register class extensions
        for ext in self._extension:
            simics.SIM_extend_class(ccls, ext)

        for (relname, p) in self._objs.items():
            p._register(ccls, relname)

        # Hook for additional class declarations
        cls_constructor = c.get("class_constructor", None)
        if cls_constructor:
            cls_constructor(ccls)
