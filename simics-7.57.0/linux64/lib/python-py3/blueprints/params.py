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

from copy import copy
from dataclasses import dataclass
from typing import Any, Callable, TypeVar, get_type_hints
from blueprints.types import BlueprintError, Namespace, Config, Preset
from blueprints.data import bp_data, ParamBase, bp_expander

class _ExplicitParamGroup(ParamBase):
    members: list[ParamBase] = []
    def collapse(self):
        rv = [ m.collapse() for m in self.members ]
        flat = []
        for e in rv:
            if isinstance(e, list):
                for ee in e:
                    ee.name =  f'{self.name}:{ee.name}'
                    flat.append(ee)
            else:
                e.name =  f'{self.name}:{e.name}'
                flat.append(e)
        return flat

    def __init__(self, name: str, desc: str, members: list[Any]):
        super().__init__(name, desc)
        self.members = members

    def __repr__(self):
        as_string = '['
        for m in self.members:
            as_string += f'{m}, '
        if len(as_string) > 1:
            as_string = as_string[0:-2]
        as_string += ']'
        return (f'_ExplicitParamGroup(name=\'{self.name}\', desc=\'{self.desc}\', '
               f'members={as_string}')

@dataclass
class ParamGroup(ParamBase):
    import_bp: str
    ns: str|None = None
    count: str|None = None
    enable: str|None = None

    def __new__(cls, *args, **kwargs):
        if len(args) == 2 and len(kwargs) == 0:
            assert isinstance(args[0], str)
            assert isinstance(args[1], list)
            return _ExplicitParamGroup(args[0], '', args[1])
        else:
            return super().__new__(cls)

T = TypeVar('T', bound=Config)
@dataclass(init=False)
class Param(ParamBase):
    ptype: type
    default: Any
    member_name: str
    allow_empty: bool
    _key: tuple[type, str]
    _ns: Namespace|None

    def __init__(self, name: str, desc: str,
                 config: Config, ptype=None, default=None, member_name=None,
                 allow_empty = True):
        if not issubclass(config, Config):
            raise BlueprintError(
                f"Blueprint parameter {name} cannot be bound to"
                f" non-configuration state {config}")

        super().__init__(name, desc)
        # throws if attribute is spelled incorrectly
        _ = getattr(config, member_name if member_name else name.split(':')[-1])
        value = default if default is not None else config._defaults[member_name if member_name else name.split(':')[-1]]
        hints = get_type_hints(config)
        if ptype:
            self.ptype = ptype
        elif name in hints:
            self.ptype = hints[name]
        else:
            if value is None:
                raise BlueprintError(
                    f"Blueprint parameter {name} from state {config} has"
                    " unknown type.")
            self.ptype = type(value)
        self.default = value
        self._key = (config, name)
        self._ns = None
        self.member_name = member_name
        self.allow_empty = allow_empty

def _expand_params(name: str, ns: Namespace,
                  values: dict[str, dict|Any]) -> dict[str, dict|Param]:
    def add_to_expanded(expanded, name, value):
        layer_dict = expanded
        for layer_item in name.split(':')[0:-1]:
            if not layer_item in layer_dict:
                layer_dict[layer_item]={}
            layer_dict = layer_dict[layer_item]
        layer_dict[name.split(':')[-1]] = value
    bp = bp_data(name)
    assert bp is not None
    expanded = {}
    for (name, p) in bp.params.items():
        if isinstance(p, ParamGroup):
            if p.ns is not None and p.ns in values:
                sub_name = values[p.ns]
                assert isinstance(sub_name, str)
                sub_ns = getattr(ns, sub_name)
            else:
                sub_ns = getattr(ns, name)
            if p.enable is not None:
                if p.enable in bp.params:
                    enabler = bp.params[p.enable]
                    assert isinstance(enabler, Param)
                    value = values.get(p.enable, enabler.default)
                    assert isinstance(value, bool)
                    if value:
                        add_to_expanded(expanded, p.name, _expand_params(p.import_bp,
                                                             sub_ns,
                                                             values.get(p.name, {})))
                else:
                    raise BlueprintError(f"Invalid enable name '{p.enable}' for"
                                         f" parameter {p.name}"
                                         f" in blueprint '{name}'")
            elif p.count is not None:
                if p.count in bp.params:
                    counter = bp.params[p.count]
                    assert isinstance(counter, Param)
                    value = values.get(p.count, counter.default)
                    assert isinstance(value, int)
                    for i in range(value):
                        key = f"{p.name}[{i}]"
                        add_to_expanded(expanded, key, _expand_params(p.import_bp,
                                                          sub_ns[i],
                                                          values.get(key, {})))
                else:
                    raise BlueprintError(f"Invalid counter '{p.count}'"
                                         f" for parameter {p.name}"
                                         f" in blueprint '{name}'")
            else:
                add_to_expanded(expanded, p.name, _expand_params(p.import_bp,
                                                     sub_ns,
                                                     values.get(p.name, {})))
        elif isinstance(p, Param):
            exp_p = copy(p)
            exp_p._ns = ns
            exp_p.name = p.name.split(':')[-1]
            exp_p._key = (exp_p._key[0], exp_p.name)
            add_to_expanded(expanded, p.name, exp_p)
        else:
            assert False
    return expanded

def _flatten_params(params: dict[str, dict|Any],
                    separator: str) -> dict[str, Any]:
    flattened = {}
    for (name, p) in params.items():
        if isinstance(p, dict):
            sub_params = _flatten_params(p, separator)
            for (n, s) in sub_params.items():
                flattened[f"{name}{separator}{n}"] = s
        else:
            flattened[name] = p
    return flattened

separator = ":"

# Used by blueprint adapter
def _get_flat_params(name: str, ns: Namespace|str,
                    values: dict[str, dict|Any]) -> dict[str, Param]:
    return _flatten_params(_expand_params(name, Namespace(str(ns)), values),
                          separator)

# Used by target parameter framework
def preset_from_args(ns: Namespace|str, name: str,
                     values: dict[str, dict|Any]) -> list[Preset]:
    """Obtain a blueprint preset from a nested dict in the
       format of the target parameter framework."""
    if bp_data(name):
        params = _get_flat_params(name, ns, values)
        vals = _flatten_params(values, separator)
        try:
            return [((str(params[k]._ns),)
                     + (params[k]._key[0],)
                     + (params[k].member_name if params[k].member_name else params[k]._key[1],),
                     vals[k]) for k in vals]

        except KeyError as k:
            raise BlueprintError(f'Blueprint "{name}" has no parameter "{k}"')
    else:
        raise BlueprintError(f"No parameters in blueprint '{name}'")

def params_from_config(state: Config) -> list[Param]:
    """Helper function for obtaining a blueprint parameter list
       from the members of a single state structure. """
    return [Param(name=k, desc="", config=state)
            for k in state._keys]

# Used by target parameter framework
def get_blueprint_params(name: str,
                         values: dict[str, dict|Any]) -> dict[str, dict|Param]:
    """Return blueprint user parameters as a nested dict in the format of the
       target parameter framework (i.e. param name -> param default value).
       Parameter values in the same format can be provided, which can
       influence dynamically defined parameters."""
    if bp_data(name):
        return _expand_params(name, Namespace(""), values)
    else:
        raise BlueprintError(f"No parameters in blueprint '{name}'")

# TODO: SIMICS-22599 Use the dynamic parameters
def list_params_cmd(name: str, *_):
    import cli
    import table
    data = _flatten_params(get_blueprint_params(name, {}), separator)
    headers = ["Name", "Type", "Default"]
    props = [(table.Table_Key_Columns, [[(table.Column_Key_Name, n)]
             for n in headers])]
    rows = [[name, p.ptype.__name__, str(p.default)
             if p.default is not None else ''] for (name, p) in data.items()]
    tbl = table.Table(props, rows)
    msg = tbl.to_string(rows_printed=0, no_row_column=True) if rows else ""
    return cli.command_return(msg, list(data.keys()))

unspecified_arg = object()

def bp_dynamic_args(bp: str, _) -> list:
    if not bp:
        return []
    try:
        params = _flatten_params(get_blueprint_params(bp, {}), separator)
    except BlueprintError:
        return []

    import cli

    # Parameter type -> CLI type
    cli_decl_types = {
        str: cli.str_t,
        int: cli.int_t,
        bool: cli.boolean_t,
        float: cli.float_t,
        list: cli.list_t,
    }

    return [cli.arg(cli_decl_types[p.ptype],
                    name, "?", default=unspecified_arg)
            for (name, p) in params.items()]

def register_param_commands():
    import cli
    cli.new_command("list-blueprint-params", list_params_cmd,
                    [cli.arg(cli.str_t, "blueprint", "1", doc="blueprint",
                             expander=bp_expander)],
                    dynamic_args=("blueprint", bp_dynamic_args),
                    type=["Configuration"], short="list blueprint parameters",
                    doc="""
List parameters for <arg>blueprint</arg>.
""")
