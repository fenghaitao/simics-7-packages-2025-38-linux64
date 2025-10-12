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

import collections.abc
from enum import IntEnum
from typing import (Any, Generic, Iterable, Iterator, NamedTuple,
                    TypeVar, TypeAlias)
from dataclasses import dataclass

class BlueprintError(Exception): pass

@dataclass(frozen=True, order=True)
class Namespace:
    """The Namespace class represents a hierarchical name where
    Simics objects and blueprints can be added. Basically a string."""
    __slots__ = ("_name")
    _name: str
    def __getattr__(self, name: str) -> "Namespace":
        xname = f"{self._name}.{name}" if self._name else name
        return type(self)(xname)
    def __getitem__(self, index: int) -> "Namespace":
        return type(self)(f"{self._name}[{index}]")
    def __repr__(self) -> str:
        return self._name if self._name else "<namespace-root>"
    def __str__(self) -> str:
        return self._name
    def __matmul__(self, v) -> "Namespace":
        return type(self)(f"{self._name}{v:}")
    def is_descendant_of(self, ns: "Namespace"):
        """Is ns an ancestor of self?"""
        return str(self).startswith(str(ns))
    def __bool__(self) -> bool:
        return bool(str(self))
    # Must explicitly disallow iteration, since we implement __getitem__
    def __iter__(self):
        raise TypeError('Object is not iterable')

class State:
    """Base class for all blueprint state classes. Each state class is a
    fixed collection of fields, a shared data structure.
    It can also carry configurational information."""
    __slots__ = ("_key", "_builder")
    _key: "StateKey"
    _builder: Any
    _defaults: dict[str, Any] = {}
    _keys: tuple[str, ...] = ()
    def __init__(self):
        self._key = ("unbound", str)
        self._builder = None  # type: ignore

    def __setattr__(self, k: str, v: Any):
        # Lockdown the class to forbid unregistered attributes
        if k not in self._defaults and not k.startswith("_"):
            raise AttributeError(f"{self} object has no field '{k}'")
        super().__setattr__(k, v)

    def __init_subclass__(cls, **kwargs):
        cls.__slots__ = ()
        super().__init_subclass__(**kwargs)
        defaults = {}
        keys = ()
        for base in cls.__bases__:
            if issubclass(base, State):
                defaults.update(base._defaults)
                keys += base._keys
        def make_property(k: str):
            def getter(self: State) -> Any:
                return self._builder._get_value(self, k)
            def setter(self: State, val: Any):
                self._builder._set_value(self, k, val)
            return property(getter, setter, None)

        members = [(k, v) for (k, v) in cls.__dict__.items()
            if k[0] != '_' and not callable(v)]
        defaults.update(members)
        keys += tuple(k for (k, _) in members)
        for (k, _) in members:
            setattr(cls, k, make_property(k))
        cls._defaults = defaults
        cls._keys = keys

    def _get_ns(self) -> Namespace|str:
        if len(self._key) == 2:
            return Namespace(self._key[0])
        else:
            return "<unbound>"

    def _get_iface(self) -> Any:
        return self._key[1]

    def _name(self) -> str:
        def_iface = self._key[1].__name__
        node = f"[{self._key[0]}]"
        rest = '.'.join(str(x) for x in (node, *self._key[2:]))
        return f"{def_iface}{rest}"

    def __repr__(self) -> str:
        iface = type(self).__name__
        if len(self._key) == 2:
            return self._name()
        else:
            return f"<unbound> <{iface}>"

    def __str__(self) -> str:
        return (f"{self._name()} state\nCurrent: {self.asdict()}\n"
                f"Next: {self.next_iter()}")

    def _bind_factory(self) -> "State":
        # Needs to be overridden by state taking mandatory parameters
        return type(self)()
    def _bind(self, builder, key: tuple) -> "State":
        ret = self._bind_factory()
        ret._builder = builder
        ret._key = key
        return ret

    def __iter__(self) -> Iterator[str]:
        return sorted(self._defaults.keys()).__iter__()

    def asdict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self}

    def next_iter(self) -> dict[str, Any]:
        return {k: self._builder._get_next_value(self, k) for k in self}

StateT = TypeVar('StateT', bound=State)
StateKey: TypeAlias = tuple[str, type[StateT]]
ValueKey: TypeAlias = tuple[str, type[StateT], str]
Preset: TypeAlias = tuple[ValueKey, Any]

T = TypeVar('T')
class NSState(State, Generic[T]):
    "State which accepts any field names."
    __slots__= ()
    def __getattr__(self, k: str) -> T:
        if k[0] != '_':
            try:
                return self._builder._get_value(self, k)
            except:
                raise AttributeError(f"attribute '{k}' has not been set")
        else:
            return object.__getattribute__(self, k)
    def __setattr__(self, k: str, val: T):
        if k[0] != '_':
            self._builder._set_value(self, "[keys]", k, simplified=True)
            if k[0] != '_':
                self._builder._set_value(self, k, val)
        else:
            return object.__setattr__(self, k, val)
    def __iter__(self) -> Iterator[str]:
        vals = self._builder._vals.get(self._key + ("[keys]",), [])
        keys = set(v.value for v in vals) | set(super().__iter__())
        return sorted(keys).__iter__()

class List(State, Generic[T], collections.abc.Sequence):
    """List type, to be used in state definitions. Multiple blueprints
    can contribute elements to the same list. Created automatically for
    state values which has an empty list as default value."""
    __slots__= ()
    def _get(self) -> list[T]:
        if not self._builder:
            return []
        values = self._builder._vals.get(self._key + ("[list]",), [])
        return [item for v in values for item in v.value]
    def extend(self, vals: Iterable[T]):
        self._builder._set_value(self, "[list]", list(vals), simplified=True)
    def append(self, val: T):
        self.extend([val])
    def __iter__(self) -> Iterator[T]:
        return iter(self._get())
    def __len__(self) -> int:
        return len(self._get())
    def __repr__(self) -> str:
        return repr(self._get())
    def __eq__(self, b) -> bool:
        return self._get() == b
    def __getitem__(self, i) -> T:
        return self._get()[i]

K = TypeVar('K')
class Dict(State, Generic[K, T], collections.abc.Mapping):
    """Dict type, to be used in state definitions. Multiple blueprints
    can contribute elements to the same dict."""
    __slots__ = ()
    def _get(self) -> dict[K, T]:
        if not self._builder:
            return {}
        values = self._builder._vals.get(self._key + ("[dict]",), [])
        return {k: v for (k,v) in [x.value for x in reversed(values)]}
    def __setitem__(self, key: K, val: T):
        self._builder._set_value(self, "[dict]", (key, val), simplified=True)
    def __getitem__(self, key: K) -> T:
        return self._get()[key] # type: ignore
    def __iter__(self) -> Iterator[K]:
        return iter(self._get())
    def __len__(self) -> int:
        return len(self._get())

class Set(State, Generic[T], collections.abc.Set):
    """Set type, to be used in state definitions. Multiple blueprints
    can add elements to the same set."""
    __slots__ = ()
    def _get(self) -> set[T]:
        if not self._builder:
            return set()
        values = self._builder._vals.get(self._key + ("[set]",), [])
        return set(x.value for x in values)
    def add(self, val: T):
        self._builder._set_value(self, "[set]", val, simplified=True)
    def __contains__(self, val: T) -> bool:
        return val in self._get()
    def __iter__(self) -> Iterator[T]:
        return iter(self._get())
    def __len__(self) -> int:
        return len(self._get())

class StateMap(State, Generic[T, StateT]):
    __slots__= ("_iface_type", )
    def __init__(self, iface_type: type[StateT]):
        self._iface_type = iface_type
        super().__init__()
    def __getitem__(self, i: T) -> StateT:
        return self._builder._add_state(
            self._iface_type, self._key + (i,))
    def _bind_factory(self):
        return type(self)(self._iface_type)

class Config(State):
    """Blueprint configuration state."""
    __slots__ = ("_allow_write")

    def __init__(self):
        self._allow_write = False
        super().__init__()

    def __setattr__(self, k: str, v: Any):
        # Configuration state is read-only
        if not (k.startswith("_") or self._allow_write):
            raise AttributeError(f"Configuration state {self}"
                                 " cannot be modified.")
        else:
            super().__setattr__(k, v)

ConfigT = TypeVar('ConfigT', bound=Config)

class Binding(State):
    """1-1 connection between two blueprints."""
    __slots__ = ()

BindingT = TypeVar('BindingT', bound=Binding)

class Priority(IntEnum):
    DEFAULT = -100
    NORMAL = 0
    OVERRIDE = 100
    ALIAS = 200

class PriorityValue(NamedTuple):
    val: Any
    priority: Priority = Priority.NORMAL

def Default(val: T) -> T:
    "Function used to attach DEFAULT priority to the value 'val'."
    ret = PriorityValue(val, Priority.DEFAULT)
    return ret # type: ignore

def Override(val: T) -> T:
    "Function used to attach OVERRIDE priority to the value 'val'."
    ret = PriorityValue(val, Priority.OVERRIDE)
    return ret # type: ignore

class _Omit:
    "Value which can be assigned to an object attribute in order to ensure"
    " that the attribute is not set."
    __slots__ = ()
OMIT_ATTRIBUTE = _Omit()

class Undefined:
    "Class used to represent an undefined value."
    __slots__ = ()
    def __bool__(self) -> bool:
        return False
UNDEFINED = Undefined()
