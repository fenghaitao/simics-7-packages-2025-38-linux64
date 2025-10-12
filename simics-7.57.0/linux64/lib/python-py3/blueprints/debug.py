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

import io
from typing import Any
from .types import State, List

def _tostr(v: Any, level: int) -> str:
    if isinstance(v, int) and v >= 10:
        return f"0x{v:x}"
    elif isinstance(v, list) or type(v) is tuple:
        return f"[{', '.join(_tostr(x, level) for x in v)}]"
    elif isinstance(v, tuple):
        return f"{v!r}"
    elif isinstance(v, str):
        return f"{v!r}"
    elif isinstance(v, State):
        if level > 10:
            return '<Recursion limit reached>'
        buf = io.StringIO()
        _print_state([v], buf, level = level + 1)
        return buf.getvalue().strip() + ')'
    else:
        return f"{v!s}"

def _pretty_print(indent: str, val: Any, stream: io.TextIOBase, level: int, postfix=""):
    if isinstance(val, List) or type(val) is tuple:
        val = list(val)
    valstr = f"{_tostr(val, level)}{postfix}"
    if len(valstr) < 80 or not isinstance(val, list):
        print(f"{indent}{valstr}", file=stream)
    else:
        indent += "["
        for i, v in enumerate(val):
            _pretty_print(indent, v, stream, level,
                          postfix="]" if i == len(val) - 1 else ",")
            indent = " " * len(indent)

def _print_iface(iface: State, field_pat: str, stream: io.TextIOBase, level: int):
    for k in iface._keys:
        if not field_pat or field_pat in k:
            _pretty_print(f"{'  '*level}  {k:24}", getattr(iface, k), stream, level)

def _check_for_alias(iface: State) -> tuple[bool, str, State]:
    if isinstance(iface._get_ns(), str):
        return False, iface._name(), iface
    state = iface._builder.read_state_data(iface._get_ns(),
                                           iface._get_iface(),
                                           peek_binding = True,
                                           register_sub = False)
    aliased_name = state._name()
    prev_state = iface._name()
    while prev_state != state._name():
        prev_state = state._name()
        if isinstance(state._get_ns(), str):
            break
        state = state._builder.read_state_data(state._get_ns(), state._get_iface(),
                                               peek_binding = True,
                                               register_sub = False)
    return iface._name() != aliased_name, aliased_name, state

def _print_state(state: list, stream: io.TextIOBase,
                 field_pat="", iface_name="", pat="", level: int = 0):
    for iface in state:
        # Lists have been displayed "inline"
        if isinstance(iface, List):
            continue
        if level > 0:
            iface_str = iface_str = type(iface).__name__ + '('
            actual_state = iface
            is_alias = False
        else:
            iface_str = repr(iface)
            is_alias, aliased_name, actual_state = _check_for_alias(iface)

        if field_pat and not any(field_pat in k for k in iface._keys):
            continue
        iname = type(iface).__name__
        if (not iface_name or iname == iface_name) and pat in iface_str:
            print(iface_str, file=stream)
            if is_alias:
                print(f"{'  '*level}  ---> {aliased_name}", file=stream)
            _print_iface(actual_state, field_pat, stream, level)
