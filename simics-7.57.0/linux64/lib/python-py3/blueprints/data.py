# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

from dataclasses import dataclass
from typing import Callable, NamedTuple, TypeVar

@dataclass
class ParamBase:
    name: str
    desc: str
    def collapse(self):
        return self

T = TypeVar('T', bound=ParamBase)
class BlueprintRecord(NamedTuple):
    func: Callable
    params: dict[str, ParamBase] = {}
    name: str|None = None

_blueprints: dict[str, BlueprintRecord] = {}
_blueprint_names: dict[Callable, str] = {}

def _register_parameterised_blueprint(params: list[T], name: str, bp: Callable):
    params = [ p.collapse() for p in params ]
    flat = []
    for e in params:
        if isinstance(e, list):
            for ee in e:
                flat.append(ee)
        else:
            flat.append(e)
    _blueprints[name] = BlueprintRecord(
        bp, {p.name: p for p in flat}, name)

def blueprint(params: list[ParamBase]|None=None,
              name: str|None=None) -> Callable:
    """Decorator for adding blueprint parameters."""
    def inner(f: Callable) -> Callable:
        n = f.__name__ if not name else name
        p = [] if not params or callable(params) else params
        _register_parameterised_blueprint(p, n, f)
        _blueprint_names[f] = n
        return f

    # Allow using decorator without brackets
    if callable(params):
        return inner(params)
    else:
        return inner

def bp_name(bp: Callable) -> str:
    """Return registered name of blueprint function."""
    return _blueprint_names[bp] if bp in _blueprint_names else bp.__name__

def lookup_bp(name: str) -> Callable:
    """Return blueprint function from registered name."""
    return _blueprints[name].func

def bp_data(name: str) -> BlueprintRecord|None:
    return _blueprints.get(name)

def bp_expander(name: str) -> list[str]:
    return [x.name for x in _blueprints.values()
            if x.name is not None and x.name.startswith(name)]
