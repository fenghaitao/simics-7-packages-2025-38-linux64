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

from typing import Callable, NamedTuple, TypeAlias, Union
from .types import Namespace, Config, BlueprintError, StateT, ConfigT, BindingT
from .simtypes import ConfObject

class Builder:
    __slots__ = ("_builder")
    """A Blueprint class instance is passed as the first argument to a
    blueprints function. Its methods are primarily used to add objects and
    sub-blueprints and to handle state."""

    def __init__(self, builder: "BlueprintBuilder"):
        self._builder = builder

    def create_config(self, name: Namespace, config: type[ConfigT]) -> ConfigT:
        """This method is analogous to expose_state,
           but for Config sub-types."""
        if not issubclass(config, Config):
            raise BlueprintError(f"{config} is not a configuration state class")
        state = self.expose_state(name, config)
        state._allow_write = True
        return state

    def get_config(self, name: Namespace, config: type[ConfigT]) -> ConfigT:
        """This method is analogous to read_state, but for Config sub-types."""
        state = self._builder.read_state_data(
            name, config, allow_local=True, register_sub=False)
        if isinstance(state, Config):
            state._allow_write = False
        return state

    def expose_state(self, name: Namespace,
                     state: StateT|type[StateT]) -> StateT:
        """Binds a state structure to the namespace node 'ns' and returns it.

        If 'state' is a state type, then an instance of this state
        is created and bound to the node.

        If 'state' is a state instance, then that instance is bound
        to the specified node. Note that a specific state instance can be
        bound to multiple nodes."""
        return self._builder.add_state(name, state)

    def read_state(self, name: Namespace, state: type[StateT], *,
                   private=False, allow_local=False) -> StateT:
        """Returns a state instance of type 'state'
        obtained from the node 'ns'. If the node 'ns' does not
        provide the state, then the state is obtained from the first
        hierarchical ancestor which provides it.

        If no ancestor provides the state, or if 'private' is set
        to True, then a local state instance is created and returned
        instead. The same state instance will always be returned for a
        specific value of 'ns'. A local state is not accepted if 'allow_local'
        is set to True.

        State instances are bound to a specific node with the 'expose_state'
        method."""
        s = self._builder.read_state_data(
            name, state, private=private, allow_local=allow_local)
        if isinstance(s, Config):
            s._allow_write = False
        return s

    def alias_state(self, src: Namespace, type: type[StateT],
                    dst: Namespace) -> StateT:
        """Re-binds the state structure of type 'type' bound at 'src' to the
        node at 'dst'. This is typically done when connecting sub-systems.
        The transferred state is returned."""
        state = self._builder.read_state_data(src, type, register_sub=False)
        return self.expose_state(dst, state)

    def establish_binding(self, type: type[BindingT], src: Namespace,
                          dst: Namespace) -> StateT:
        """Reads the Binding of type 'type', which must have been
        exposed at node 'src' and re-exposes it at node `dst".

        This facilitates "connecting" blueprints expanded at these nodes.

        Note that a Binding is a 1-1 channel and hence can only be read once.
        """
        return self.alias_state(src, type, dst)

    def obj(self, name: Namespace, conf_class: str, **kwd) -> ConfObject|None:
        """Add an object to the blueprint, with a name derived from the
        'ns' namespace object. Any supplied keyword parameters represent
        object attributes."""
        return self._builder.add(name, conf_class, **kwd)

    def expand(self, parent: Namespace, name: str,
               kind: Union[Callable, "BlueprintFun"], **kwd):
        """Expand a blueprint at the node 'name' under the
        'parent' namespace. Any supplied keyword parameters represent
        blueprint arguments."""
        if str(parent):
            if name:
                ns = Namespace(f"{parent}.{name}")
            else:
                ns = parent
        else:
            if name:
                ns = Namespace(name)
            else:
                ns = parent
        self._builder.add(ns, kind, **kwd)

    def set(self, name: Namespace, **kwd) -> ConfObject|None:
        """Set attributes on an object. This must be a descendant of
        an object already registered using obj(). Any supplied keyword
        parameters represent object attributes."""
        return self._builder.set(name, **kwd)

    def error(self, *args):
        """Report an error."""
        self._builder.error(list(args))

    def at_post_instantiate(self, name: Namespace, cb: Callable, **kwds):
        """Register a post-instantiate callback at the node 'ns'.
        The callbacks will be called in registration order after the
        configuration has been instantiated, and the 'kwds' parameters will be
        provided. If any callback throws an exception, a warning is printed,
        but all post-instantiate callbacks will run."""
        self._builder.at_post_instantiate(name, cb, kwds)

class BlueprintFun(NamedTuple):
    "Container type which holds a blueprint function"
    comp: Callable[[Builder, Namespace], None]|None = None
    def __bool__(self):
        return bool(self.comp)

CompFunc: TypeAlias = Callable[[Builder, Namespace], None]

from .impl import BlueprintBuilder
