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


from typing import NamedTuple, TypeAlias
from .types import Namespace

#
# Tuple types used to represent Simics conf objects and similar constructs.
# The purpose of these types is to make it clearer what an interconnect field
# is supposed to contain.
#

class ConfObject(NamedTuple):
    "Python representation of a Simics object."
    obj: Namespace|None = None
    def resolve(self) -> Namespace:
        return self.obj if self.obj is not None else Namespace("")
    def __bool__(self) -> bool:
        return bool(self.obj)
    def __repr__(self) -> str:
        return f"{self.obj}" if self.obj is not None else "None"

ObjNS: TypeAlias = Namespace|ConfObject

class Port(NamedTuple):
    "Python representation of a Simics interconnect on a conf object."
    obj: ObjNS|None = None
    port: str|None = None
    def resolve(self) -> tuple[ObjNS, str]|ObjNS|None:
        return (self.obj, self.port) if self.port and self.obj else self.obj
    def __bool__(self) -> bool:
        return bool(self.obj)
    def __repr__(self) -> str:
        name = type(self).__name__
        if self.port:
            return f"{name}({self.obj!s}, {self.port!r})"
        else:
            return f"{name}({self.obj!s})"

class SignalPort(Port):
    "Python representation of a Simics signal interconnect on a conf object."

class MemMap(NamedTuple):
    "Tuple representing a memory-space mapping"
    base: int
    port: Port|ObjNS
    function: int
    offset: int
    length: int
    target: Port|ObjNS|None = None
    priority: int = 0
    align_size: int = 0
    byteswap: int = 0
    def resolve(self) -> tuple:
        t = tuple(self)
        return t if t[5:] != (None, 0, 0, 0) else t[:5]
    def __repr__(self) -> str:
        # Format number attributes as hex and other attributes as is.
        #
        # Due to limits on how f-strings can be nested prior to
        # Python 3.12 (see PEP 701), triple quotes are used to allow the
        # following expression to be broken into several lines.
        return f"""MemMap({', '.join(
            [f'{item:#x}' if isinstance(item, int) else str(item)
             for item in self.resolve()])})"""

class DefaultTarget(NamedTuple):
    "Tuple representing a memory-space default target"
    port: Port|ObjNS
    function: int = 0
    offset: int = 0
    target: Port|ObjNS|None = None
    align_size: int = 0
    byte_swap: int = 0
    def resolve(self) -> tuple:
        t = tuple(self)
        return t if t[4:] != (0, 0) else t[:4]
