# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import collections

import simics

class UserDefinedAliases(collections.abc.MutableMapping):
    def __init__(self):
        self.aliases = {}

    def __len__(self):
        return len(self.aliases)

    def __iter__(self):
        return iter(self.aliases)

    def __getitem__(self, k):
        if k in self.aliases:
            return self.aliases[k]
        raise KeyError(k)

    def __setitem__(self, k, v):
        self.aliases[k] = v

    def __delitem__(self, k):
        del self.aliases[k]

    def __repr__(self):
        return repr(self.aliases)

    def visible_objects(self, iface):
        return [(alias, o)
                 for (alias, objname) in self.aliases.items()
                 for o in (simics.VT_get_object_by_name(objname),)
                 if o is not None
                 # Don't bother with this alias in the face of alias-to-alias
                 # and shadowing shenanigans
                 if objname.split('.')[0] not in self.aliases
                 if not iface or hasattr(o.iface, iface)]

    def completions(self, base, include_exact):
        matching = [x for x in self.aliases if x.startswith(base)]
        if not include_exact and base in matching:
            matching.remove(base)
        return matching

class ObjectAlias:
    def __init__(self, name, description):
        self.name = name
        self.description = description

    def eq(self, name):
        return self.name == name

    def startswith(self, base):
        return self.name.startswith(base)

    def get_object(self):
        assert False

    def missing_msg(self):
        return f"no object matches the '{self.name}' object alias"

class CpuObjectAlias(ObjectAlias):
    def __init__(self):
        super().__init__('cpu', 'the currently selected frontend object')

    def get_object(self):
        from cli_impl import current_frontend_object_null
        return current_frontend_object_null()

class ObjectAliases:
    def __init__(self):
        self.aliases = {}

    def add(self, alias):
        self.aliases[alias.name] = alias

    def has_alias(self, name):
        return name in self.aliases

    def completions(self, base, include_exact):
        matching = [x for x in self.aliases if x.startswith(base)]
        if not include_exact and base in matching:
            matching.remove(base)
        return matching

    def get_alias(self, name):
        return self.aliases.get(name, None)

    def descriptions(self):
        return {x: self.aliases[x].description for x in self.aliases}

    def get_object(self, name):
        if self.has_alias(name):
            return self.get_alias(name).get_object()
        for sep in ['.', '->']:
            split = name.split(sep)
            if len(split) == 1:
                continue
            if not self.has_alias(split[0]):
                continue
            top = self.get_alias(split[0]).get_object()
            if not top:
                continue
            obj_name = sep.join([top.name] + split[1:])
            return simics.VT_get_object_by_name(obj_name)
        return None

_user_defined_aliases = None

def user_defined_aliases():
    global _user_defined_aliases
    if _user_defined_aliases is None:
        _user_defined_aliases = UserDefinedAliases()
    return _user_defined_aliases

_obj_aliases = None

def obj_aliases():
    global _obj_aliases
    if _obj_aliases is None:
        _obj_aliases = ObjectAliases()
        _obj_aliases.add(CpuObjectAlias())
    return _obj_aliases

def cmd_aliases():
    """Return a dictionary mapping command aliases to command name."""
    from cli import simics_commands
    return {alias: cmd.name for cmd in simics_commands() for alias in cmd.alias}
