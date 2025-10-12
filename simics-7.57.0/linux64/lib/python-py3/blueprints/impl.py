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

import inspect
import itertools
import io
import logging
import re
import traceback

from typing import Any, Iterable, NamedTuple, Callable, cast
from types import GeneratorType, FunctionType
from .types import (OMIT_ATTRIBUTE, PriorityValue, Priority, Namespace,
                    BlueprintError, State, List, Dict, Binding, Config,
                    StateKey, ValueKey, Preset, StateT)
from .api import Builder, BlueprintFun
from .data import bp_name
from .simtypes import ConfObject
from .debug import _print_state

# Simics object, with attributes
class _Obj(NamedTuple):
    classname: str
    args: dict[str, Any]

# Blueprint, with arguments
class _Blueprint(NamedTuple):
    func: Callable
    args: dict[str, Any]

class _Alias(NamedTuple):
    iface: State
    attr: str
    def __repr__(self) -> str:
        return f"-> {self.iface!r}.{self.attr}"

def Alias(iface: StateT) -> StateT:
    """Return state which will provide aliases to the original state
    rather than actual values when its attributes are dereferenced."""
    class Builder:
        def _get_value(self, _, k):
            ret = _Alias(iface, k)
            return ret
        def _set_value(self, *_):
            raise TypeError("Alias state references cannot be modified")
    builder: Any = Builder()
    return iface._bind(builder=builder, key=("alias", ))

class _Value(NamedTuple):
    priority: Priority
    sequence: int
    value: Any
    user: str|None

def _get_state_defaults(iface: State) -> tuple[tuple[ValueKey, Any], ...]:
    # Recursively bind sub-state
    def bind(k: tuple, v: Any) -> Any:
        if isinstance(v, State):
            return v._bind(builder=iface._builder, key=k)
        elif isinstance(v, (list, tuple, GeneratorType)):
            if v == []:
                return bind(k, List())
            # Preserve subclasses of tuple (e.g. named tuples)
            factory = getattr(v, "_make", tuple)
            return factory(bind(k + (i,), x) for (i, x) in enumerate(v))
        elif isinstance(v, dict):
            return {f: bind(k + (f,), x) for (f, x) in v.items()}
        else:
            return v
    return tuple((iface._key + (k,), bind(iface._key + (k,), v))
            for (k, v) in iface._defaults.items())

def _sorted_state(state: dict):
    # The state key includes the module class which is not sortable;
    # replace class with name and module instead.
    def mysort(v):
        (k, _) = v
        return (k[0], k[1].__name__, k[1].__module__, *k[2:])
    return [v for (_, v) in sorted(state.items(), key=mysort)]

def _first(it: Iterable[str], f: Callable[[str], bool]) -> str|None:
    return next((i for i in it if f(i)), None)

def _lookup_sub_obj(parent, names):
    """ Look up sub-object in parent. This relies on that pre_conf_object uses
        VT_get_port_classes to allow assignments to such objects."""
    o = parent
    name = ""
    try:
        for n in names:
            if isinstance(n, int):
                name = f"{name}[{n}]"
                o = o[n]
            else:
                name = f"{name}.{n}"
                o = getattr(o, n)
        return o
    except AttributeError as ex:
        raise BlueprintError(
            f'Unknown sub-object "{name}" on "{parent.name}"'
            f' of class "{parent.classname}" referenced.'
            ' Module/class not built, or invalid use of bp.set?'
            f' Missing attribute: {ex}')

def _split_name(name: str) -> list:
    """ Split object name in sub-object names and indices suitable for
        consumption by _lookup_sub_obj."""
    names = name.split(".")
    output = []
    idx = re.compile(r"\[(\d+)\]")
    for n in names:
        found = idx.search(n)
        if found is not None:
            output.append(found.string[:found.start()])
            for m in idx.finditer(n):
                output.append(int(m.group(1)))
        else:
            output.append(n)
    return output

def _resolve_simics_obj(v: str, prefix: str) -> Any:
    import simics
    name = v.removeprefix(prefix + ".") if prefix else v
    return simics.SIM_get_object(name)

def _resolve_obj_ref(v: Namespace, objs: dict, logger: logging.Logger) -> Any:
    name = str(v)
    if name in objs:
        return objs[name]
    # Reverse sort to obtain closest ancestor
    ancestor = _first(reversed(sorted(objs.keys())),
                     lambda o: v.is_descendant_of(Namespace(o)))
    if ancestor:
        # v is referenced but has not been used in bp.set
        # Assume v is an implicitly created object
        names = _split_name(name[len(ancestor) + 1:])
        return _lookup_sub_obj(objs[ancestor], names)
    else:
        logger.warning("%s\n%s",
                       f"Warning: Object {v} not registered in any blueprint.",
                       "Returning object reference verbatim.")
        import configuration
        return configuration.OBJ(name)

def _resolve_value(v, objs: dict|None, refs: set[str], post_instantiate: bool,
                   logger: logging.Logger, prefix="") -> Any:
    """ Resolve an attribute value recursively (for lists and dicts).
        Scalar values are resolved to themselves.
        Object references are resolved as follows:
        1. to Simics objects if 'post_instantiate' is true
        2. using the 'objs' dictionary (whose values should be pre-objects),
           if not None.
        3. to Simics OBJ() references, to facilitate references outside the
           system created by the blueprint.

        'refs' is populated with all referenced object names."""
    if callable(getattr(v, "resolve", None)):
        return _resolve_value(v.resolve(), objs, refs, post_instantiate,
                              logger, prefix)
    elif isinstance(v, (int, float, type(None), bool, str)):
        # Base case, non-object reference: return resolved value.
        return v
    elif isinstance(v, Namespace):
        # Base case, object reference

        # Empty namespace acts as null object
        if not v:
            return None
        refs.add(str(v))
        if post_instantiate:
            return _resolve_simics_obj(str(v),
                                      str(prefix) if prefix is not None else "")
        elif objs is not None:
            return _resolve_obj_ref(v, objs, logger)
        else:
            import configuration
            return configuration.OBJ(v._name)
    elif isinstance(v, (list, List, tuple)):
        return [_resolve_value(x, objs, refs, post_instantiate,
                               logger, prefix) for x in v]
    elif isinstance(v, dict):
        return {k: _resolve_value(v[k], objs, refs, post_instantiate,
                                  logger, prefix) for k in v}
    elif isinstance(v, bytes):
        return tuple(v)
    elif isinstance(v, FunctionType):
        return v
    else:
        raise BlueprintError(f"unsupported type '{type(v)}' encountered")

def _obtain_attributes(name: str, obj: _Obj, refs: set,
                       logger: logging.Logger, prefix: str) -> list:
    """ Obtain attributes for the object 'name', as a list in the format
        expected by SIM_set_configuration:
        [name, classname, [attr1_name, attr1_value], ...]"""
    attr = ([k, _resolve_value(v, None, refs, False, logger, prefix)]
            for (k, v) in sorted(obj.args.items()) if v is not OMIT_ATTRIBUTE)
    return [f"{prefix}.{name}" if prefix else name, obj.classname, *attr]

def to_preobjs(objs: dict[str, _Obj], logger: logging.Logger,
               prefix: str, drop_non_existing: bool) -> list:
    import simics
    pre_objs: dict[str, simics.pre_conf_object] = {}
    sub_objs: dict[simics.pre_conf_object,
                   list[tuple[list, dict[str, Any]]]] = {}

    # Create all pre-objects
    for (name, o) in list(sorted(objs.items())):
        # Save implicit sub-objects for later
        if o.classname == '_non_existing_class' and drop_non_existing:
            # Reverse sort to obtain closest ancestor
            ancestor = _first(reversed(sorted(pre_objs.keys())),
                             lambda o: name.startswith(o))
            assert ancestor is not None
            names = _split_name(name[len(ancestor) + 1:])
            sub_objs.setdefault(pre_objs[ancestor], []).append((names, o.args))
            del objs[name]
        else:
            pre_obj = simics.pre_conf_object(f"{prefix}.{name}"
                                             if prefix else name,
                                             o.classname)
            pre_objs[name] = pre_obj

    def set_attrs(o: _Obj, args: dict[str, Any]):
        attr = {k: _resolve_value(v, pre_objs, set(), False,
                                  logger, prefix)
                for (k, v) in sorted(args.items())
                if v is not OMIT_ATTRIBUTE}
        for (k, v) in attr.items():
            setattr(o, k, v)

    # Set all regular attributes
    for (name, obj) in objs.items():
        set_attrs(pre_objs[name], obj.args)

    # Set all sub-object attributes
    for (parent, sub_data) in sub_objs.items():
        for (names, args) in sub_data:
            o = _lookup_sub_obj(parent, names)
            # Set attributes
            set_attrs(o, args)

    return list(pre_objs.values())

def _mark_pre_obj_root_blueprints(config: list, roots: dict[str, str]):
    objs = {o.name: o for o in config}
    for r in roots:
        # Maybe no object at the blueprint root, e.g. if no objects at all
        if r not in objs:
            continue
        if (objs[r].classname == "blueprint-namespace"
            and not hasattr(objs[r], "blueprint")):
            objs[r].blueprint = roots[r]

def _mark_obj_list_root_blueprints(config: list, roots: dict[str, str]):
    objs = {o[0]: o for o in config}
    for r in roots:
        # Maybe no object at the blueprint root, e.g. if no objects at all
        if r not in objs:
            continue
        o = objs[r]
        if o[1] == "blueprint-namespace":
            if len(o) > 2:
                attrs = dict(o[2:])
            else:
                o.append([])
                attrs = {}
            if "blueprint" not in attrs:
                o += [["blueprint", roots[r]]]

# Allow empty namespace objects to be added implicitly
def _add_missing_pre_obj_parents(config: list, prefix: str,
                                roots: dict[str, str]):
    import simics
    objs = set(x.name.removeprefix(prefix + ".") for x in config)
    work = list(objs)
    while work:
        par = work.pop().rpartition(".")[0]
        if par and par not in objs:
            objs.add(par)
            work.append(par)
            config.append(simics.pre_conf_object(
                f"{prefix}.{par}" if prefix else par,
                "blueprint-namespace" if par in roots else "namespace"))


def _add_missing_obj_list_parents(config: list, prefix: str,
                                 roots: dict[str, str]):
    objs = set(x[0].removeprefix(prefix + ".") for x in config)
    work = list(objs)
    while work:
        par = work.pop().rpartition(".")[0]
        if par and par not in objs:
            objs.add(par)
            work.append(par)
            config.append(
                [f"{prefix}.{par}" if prefix else par,
                 "blueprint-namespace" if par in roots else "namespace"])

class BlueprintBuilder:
    __slots__ = ("_comps", "_obj", "_state", "_vals", "_new_vals",
                 "_defaults", "_accessed", "_errors", "_binds", "_new_binds",
                "_seq", "_state_subs", "_post_instantiate", "_roots",
                 "_presets", "_funcs", "_cur_obj", "_all_comps", "_logger")
    def __init__(self, logger):
        self._seq: int = 0

        # Blueprint "output"
        self._comps: list[tuple[Namespace, _Blueprint]] = []
        self._funcs: dict[Any, str] = {}
        self._obj: dict[str, _Obj] = {}
        self._errors: list[list] = []

        # Objects added in current blueprint
        self._cur_obj: set[Namespace] = set()

        # All state
        self._state: dict[StateKey, State] = {}
        self._accessed: set[StateKey] = set()

        # State bindings
        self._binds: dict[StateKey, State] = {}
        self._new_binds: dict[StateKey, State] = {}

        # State subscriptions (for inspection)
        self._state_subs: list[tuple[Namespace, type[State], State|None]] = []

        # Callbacks
        self._post_instantiate: list[tuple[Namespace, Callable, dict]] = []

        # Values
        self._vals: dict[ValueKey, list[_Value]] = {}
        self._new_vals: dict[ValueKey, list[_Value]] = {}
        self._defaults: dict[ValueKey, Any] = {}

        # "Root" blueprints = those given directly to expand()
        self._roots: list[tuple[Namespace, Callable, dict]] = []

        # All seen blueprints
        self._all_comps: list[tuple[Namespace, _Blueprint]] = []

        # Presets used in all expand() calls
        self._presets: list[Preset] = []

        self._logger: logging.Logger = logger

    def _get_value(self, iface: State, key: str) -> Any:
        self._add_state(type(iface), iface._key)
        k = iface._key + (key,)
        val = max(self._vals[k]).value if k in self._vals else self._defaults[k]
        self._logger.debug('%s.%s -> %s', repr(iface), key, val)
        if isinstance(val, _Alias):
            return getattr(val.iface, val.attr)
        else:
            return val

    def _get_next_value(self, iface: State, key: str) -> Any:
        k = iface._key + (key,)
        if k in self._new_vals:
            val = max(self._new_vals[k]).value
            if isinstance(val, _Alias):
                return getattr(val.iface, val.attr)
            else:
                return val
        else:
            return self._get_value(iface, key)

    # Find current blueprint by looking at the stack frames
    def _find_user_blueprint(self) -> str|None:
        for r in inspect.stack():
            func = r.frame.f_code
            if func in self._funcs:
                return self._funcs[func]

    def _set_value(self, iface: State, key: str, val: Any, simplified=False):
        self._add_state(type(iface), iface._key)
        prio = Priority.NORMAL
        k = iface._key + (key,)
        if not simplified:
            if isinstance(val, PriorityValue):
                (prio, val) = (val.priority, val.val)
            elif isinstance(val, _Alias):
                prio = Priority.ALIAS
            cur = max(self._vals[k]).value if k in self._vals else None
            if isinstance(cur, _Alias) and not isinstance(val, _Alias):
                setattr(cur.iface, cur.attr, val)
                return

        self._logger.debug('%s.%s <- %s', repr(iface), key, val)
        self._new_vals.setdefault(k, []).append(_Value(
            priority=prio, sequence=-self._seq,
            value=val, user=self._find_user_blueprint()))

        if not simplified:
            for g in itertools.groupby(sorted(
                    self._new_vals[k],
                    key=lambda v: (v.priority, v.sequence)),
                                       key=lambda v: v.priority):
                # Only error if different values are written with
                # the same priority
                vals = list(g[1])
                if len(vals) > 1 and any(v.value != vals[0].value
                                         for v in vals[1:]):
                    users = [v.user for v in vals]
                    self.error([f"Multiple write to member '{key}' of"
                                f" state '{repr(iface)}' detected."
                                f" From blueprints {users}."])

    # key is of the form (namespace, statename, field1, field2, ...)
    def _add_state(self, iface: type[StateT], key: StateKey) -> StateT:
        if not key in self._state:
            i = self._state[key] = iface()._bind(builder=self, key=key)
            self._defaults.update(_get_state_defaults(i))
        self._accessed.add(key)
        return self._state[key] # type: ignore

    def add_state(self, ns: Namespace, iface: StateT|type[StateT]) -> StateT:
        if isinstance(iface, State):
            ret = iface
        else:
            ret = self._add_state(iface, (ns._name, iface))
        self._new_binds[(ns._name, type(ret))] = ret
        return ret

    def read_state_data(self, ns: Namespace, iface: type[StateT], *,
                        private=False, allow_local=False,
                        register_sub=True, peek_binding=False) -> StateT:
        if private:
            return self._add_state(iface, (ns._name, iface))
        else:
            ret = self._lookup(iface, ns)
            if not ret and not allow_local:
                self.error([f"State {iface.__name__} not provided at"
                            f" node {ns}"])
            if ret and isinstance(ret, Binding) and not peek_binding:
                for (node, _, ic) in self._state_subs:
                    if ret == ic:
                        self.error([f"Error reading Binding {iface.__name__}"
                                    f" at node {ns}: already read at"
                                    f" node {node}"])
            if register_sub:
                self._state_subs.append((ns, iface, ret))
            return ret or self.read_state_data(ns, iface, private=True)

    def _bound_state(self) -> dict[StateKey, State]:
        return {k: v for (k, v) in self._state.items() if v._key in self._binds}

    def _lookup(self, iface: type[StateT], ns: Namespace) -> StateT|None:
        name = ns._name
        while True:
            k = (name, iface)
            if k in self._binds:
                return cast(StateT, self._binds[k])
            if not name:
                break
            name = name.rpartition(".")[0]
        return None

    def _stable(self) -> bool:
        return (self._binds == self._new_binds
                and self._vals == self._new_vals)

    def _start(self, presets: Iterable[Preset]):
        self._vals = self._new_vals
        self._new_vals = {}
        self._binds = self._new_binds
        self._new_binds = {}
        self._errors.clear()
        self._obj.clear()
        self._accessed.clear()
        self._state_subs.clear()
        self._post_instantiate.clear()
        self._funcs.clear()
        self._seq = 0
        for (k, v) in presets:
            if isinstance(v, list):
                val = List()._bind(self, k)
                val.extend(v)
            elif isinstance(v, dict):
                val = Dict()._bind(self, k)
                val.update(v)
            else:
                val = v
            self._new_vals.setdefault(k, []).append(
                _Value(Priority.OVERRIDE, 0, val, "__preset__"))

    def add(self, ns: Namespace,
            kind: str|Callable|BlueprintFun, **kwd) -> ConfObject|None:
        if callable(kind) or isinstance(kind, BlueprintFun):
            func = kind.comp if isinstance(kind, BlueprintFun) else kind
            if func:
                data = (ns, _Blueprint(func, kwd))
                self._comps.append(data)
                self._all_comps.append(data)
                self._funcs[func.__code__] = func.__qualname__
        elif kind:
            if not ns._name:
                self.error([f'Adding unnamed object of class "{kind}".'])
            if ns._name in self._obj:
                self.error(["Multiple object creation in"
                            f" {ns._name} detected."])
            self._obj[ns._name] = _Obj(kind, kwd)
            self._cur_obj.add(ns)
            return ConfObject(ns)

    def set(self, ns: Namespace, **kwd) -> ConfObject|None:
        if any(ns.is_descendant_of(o) for o in self._cur_obj):
            if ns._name in self._obj:
                # TODO: Check for argument clashes?
                self._obj[ns._name].args.update(kwd)
                return ConfObject(ns)
            else:
                # Use a special non-existing class, which can replace later
                # before instantiation.
                return self.add(ns, '_non_existing_class', **kwd)
        else:
            self.error([f'Invalid bp.set: ancestor to "{ns}" must be added'
                        ' in the same blueprint.'])

    def error(self, args: list):
        self._errors.append(args)

    def at_post_instantiate(self, ns: Namespace, cb: Callable, kwds: dict):
        self._post_instantiate.append((ns, cb, kwds))

    def _expand_iteration(self, num: int, comp: Builder, verbose: int) -> bool:
        self._logger.info(f"Iteration start: {num}")
        self._start(self._presets)
        state = self._state if verbose >= 3 else self._bound_state()
        buf = io.StringIO()
        _print_state(_sorted_state(state), buf)
        self._logger.info(buf.getvalue().strip())
        for (ns, c, kwd_args) in self._roots:
            self.add(ns, c, **kwd_args)
        while self._comps:
            self._seq += 1
            (ns, c) = self._comps.pop(0)
            self._cur_obj.clear()
            comp_args = dict(c.args)
            sig = inspect.signature(c.func)
            for (k, v) in sig.parameters.items():
                if (k not in comp_args
                    and isinstance(v.annotation, type)
                    and v.default == inspect.Parameter.empty):
                    if issubclass(v.annotation, Config):
                        comp_args[k] = comp.get_config(ns, v.annotation)
                    elif issubclass(v.annotation, State):
                        comp_args[k] = comp.read_state(ns, v.annotation)
            c.func(comp, ns, **comp_args)
        self._logger.info(f"Iteration end: {num}")
        return self._stable()

    def expand(self, *args, presets: Iterable[Preset]=(),
               max_iterations=10, ignore_errors=False, verbose=0, **kwds):
        if len(args) != 2:
            raise BlueprintError("Expansion requires two arguments:"
                                 " <namespace> <blueprint>")
        (root, cls) = args
        self._logger.info(f'Expansion of blueprint "{cls.__name__}"'
                          f' at node "{root}"')
        global _last_built
        _last_built = self
        comp = Builder(self)
        self._presets += list(presets)
        self._roots.append((Namespace(root), cls, kwds))

        roots = [(name, bp_name(func), data)
                 for (name, func, data) in self._roots]
        self._logger.info(f"Expansion roots:\n{roots}")
        self._logger.info(f"Expansion presets:\n{self._presets}")

        # For now, hard limit on the iteration count
        for x in range(max_iterations):
            if self._expand_iteration(x, comp, verbose):
                break
        else:
            raise BlueprintError("Max blueprints iteration count reached!")

        for x in self._state.keys() - self._accessed:
            del self._state[x]

        if not ignore_errors:
            errors = bool(self._errors)
            for err in self._errors:
                self._logger.error("%s" * len(err), *err)
            if errors:
                raise BlueprintError("Failed building blueprints")

    def _make_config(self, prefix: str, drop_non_existing = True) -> tuple[list, list[list]]:
        refs = set()
        obj_list = [_obtain_attributes(path, o, refs, self._logger, prefix)
            for (path, o) in sorted(self._obj.items())]
        for x in sorted(refs - self._obj.keys()):
            if not any(Namespace(x).is_descendant_of(Namespace(o))
                       for o in self._obj):
                self._logger.warning(
                    f"Warning: Object {x} not registered in any blueprint"
                     " and not a descendant of a registered object.")
        roots = {f"{prefix}.{r[0]}" if prefix else str(r[0]):
                 bp_name(r[1].func) for r in self._all_comps if r[0]}
        _add_missing_obj_list_parents(obj_list, prefix, roots)
        _mark_obj_list_root_blueprints(obj_list, roots)
        config = to_preobjs(self._obj, self._logger, prefix, drop_non_existing)
        _add_missing_pre_obj_parents(config, prefix, roots)
        _mark_pre_obj_root_blueprints(config, roots)
        return (config, obj_list)

    def post_instantiate(self, prefix: str):
        ok = True
        for (ns, cb, kwds) in self._post_instantiate:
            try:
                args = {k: _resolve_value(v, {}, set(), True,
                                          self._logger, prefix=prefix)
                        for (k, v) in kwds.items()}
                cb(**args)
            except Exception as ex:
                self._logger.exception(
                    "%s\n%s",
                    f"Error in post-instantiate hook for node {ns}: {ex}",
                    "Configuration might be in a broken state.")
                ok = False
        if not ok:
            raise BlueprintError("post-instantiation failed")

    def instantiate(self, prefix: str=""):
        (config, *_) = self._make_config(prefix=prefix)
        import simics
        try:
            simics.SIM_add_configuration(config, None)
        except simics.SimExc_General as ex:
            raise BlueprintError(ex)
        else:
            self.post_instantiate(prefix)
            # Track top level blueprint classes
            roots = {str(r[0]) for r in self._roots}
            for obj in config:
                if obj.name in roots:
                    simics.VT_add_telemetry_data(
                        "core.platform", "top_level_classes+",
                        obj.classname)
                    simics.VT_add_telemetry_data_int("core.platform",
                                                     "num-top-level-comp&", 1)

# DEBUG support - keep reference to the most recent BlueprintBuilder object
_last_built = None     # type: BlueprintBuilder | None

def last_built() -> BlueprintBuilder|None:
    return _last_built
