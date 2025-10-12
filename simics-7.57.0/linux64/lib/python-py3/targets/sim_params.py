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


# This file defines the script parameter Simics object and other
# functionality that can only run inside Simics.

import collections
from pathlib import Path
from io import StringIO
from typing import Union
from deprecation import DEPRECATED

import cli
import simics
import conf
import table

from . import script_params
from . import targets
from .script_params import (separator, flatten_name, flatten_params,
                            unflatten_name, flatten_declarations,
                            set_flattened_param, unflatten_params)

def lookup_file(f, **kwargs):
    required = kwargs.pop('required')
    found, path = cli.expand_path_markers(f, **kwargs)
    # Keep %simics% markers in file names in checkpoints
    if found and kwargs.get('keep_simics_ref') and f.startswith('%simics%'):
        path = f
    if not found and required:
        raise ValueError(f"File lookup failed: '{f}'")
    return path

def get_packages():
    prio_pkgs = [(p[0], p[9]) for p in conf.sim.package_info if p[12]]
    pkgs = [(p[0], p[9]) for p in conf.sim.package_info if not p[12]]
    return (prio_pkgs, pkgs)

def get_target_list():
    (prio_pkgs, pkgs) = get_packages()
    return targets.get_target_list(conf.sim.project, prio_pkgs,
                                   pkgs, lookup_file)

def get_preset_list():
    (prio_pkgs, pkgs) = get_packages()
    return targets.get_preset_list(conf.sim.project, prio_pkgs,
                                   pkgs, lookup_file)

def lookup_file_required(f, **kwargs):
    kwargs.setdefault('required', True)
    return lookup_file(f, **kwargs)

def parse_script(fn: Union[str, Path], args=None, ignore_blueprints=False):
    p = Path(fn)
    # Replace %script% in import specifications etc with current script path
    return script_params.parse_script(
        p, lookup_file_required, get_target_list(),
        args, ignore_blueprints=ignore_blueprints)

def is_inside_script():
    obj = conf.params.object_data
    return obj._view._fn is not None

def default_ns(tree: dict, script_file: Path) -> str:
    t = script_file
    while t.suffix:
        t = t.with_suffix('')
    ns = t.stem.replace('-', '_')

    # Automatically attach a suffix to allow loading multiple targets
    # without having to specify namespace
    if ns in tree:
        for i in range(1000):
            suffixed_ns = f"{ns}{i}"
            if suffixed_ns not in tree:
                return suffixed_ns
    else:
        return ns

def collect_bp(bp_list, values):
    from blueprints import expand
    from blueprints.params import preset_from_args
    from blueprints.data import lookup_bp
    data = []
    presets = []
    builders = []
    if 'blueprint' in bp_list:
        args = script_params.dump_arguments(values)
        bp = bp_list['blueprint']
        ns = bp_list['ns']
        preset = preset_from_args(ns, bp, args)
        if bp_list.get('use-new-builder'):
            new_builder = expand(ns, lookup_bp(bp), presets=preset)
            builders.append(new_builder)
        else:
            data.append((lookup_bp(bp), ns))
            presets +=  preset
        return (data, presets, builders)
    else:
        for (ns, sub_bp) in bp_list.items():
            (sub_data, sub_preset, new_builders) = collect_bp(
                sub_bp, values.get(ns))
            data += sub_data
            presets += sub_preset
            builders += new_builders
        return (data, presets, builders)

def instantiate_bp(fn, blueprints, values):
    from blueprints import expand, Namespace, BlueprintError
    bp = script_params.resolve_blueprints(fn, blueprints, values)
    # Obtain blueprint list and corresponding preset
    # Also builders for blueprints that need their own
    (data, presets, builders) = collect_bp(bp, values)

    # Use one top level blueprint for efficiency
    def top_level_blueprint(bp, ns):
        for (blueprint, namespace) in data:
            bp.expand(Namespace(namespace), "", blueprint)

    main_builder = expand("", top_level_blueprint, presets=presets)

    # Instantiate all blueprints
    try:
        for builder in ([main_builder] + builders):
            builder.instantiate()
    except BlueprintError as ex:
        raise script_params.TargetParamError(ex)

# Setup script parameters when a script is run
def setup_script(fn: Path, namespace, cmdline_args):
    try:
        script_data = parse_script(fn, unflatten_params(cmdline_args),
                                   ignore_blueprints=is_inside_script())
    except script_params.TargetParamError as ex:
        raise ex

    if not script_data['code']:
        raise script_params.TargetParamError(f'No code found in target "{fn}"')

    decls = script_data['params']
    args = script_data['args']

    blueprints = script_data['blueprints']
    from . import target_commands
    ns = conf.params.object_data._script_enter(
        fn, namespace, decls, args)
    target_commands.config.add_script(fn, ns)
    return (script_data['code'], blueprints, ns)

# Should be called after a script has finished
def finish_script(fn: Path):
    conf.params.object_data._script_exit()

def tree_size(tree):
    size = len(tree)
    for v in tree.values():
        if isinstance(v, dict):
            size += tree_size(v)
    return size

def params_log(msg):
    simics.SIM_log_info(3, conf.params, 0, msg)

class ParamView(collections.abc.Mapping):
    def __init__(self, parent, decls, tree, fn=None, _lookup_file=None,
                 code_fn=None):
        # param name -> Decl or dict
        self._decls = decls
        # param name -> param value or dict
        self._tree = tree
        # Current script name
        self._fn = fn
        # Code file name
        self._code_fn = code_fn
        # Current lookup file function
        self._lookup_file = _lookup_file
        # Parent view
        self._parent = parent
        if self._parent is not None:
            self._parent._children.append(self)
        self._children = []
        self._flatten(self)

    def _flatten(self, caller):
        # Flattened param name -> param value
        script_params.resolve_param_refs(self._fn, self._tree)
        script_params.check_param_cycles(self._tree)
        self._values = flatten_params(self._tree)
        self._flat_decls = flatten_declarations(self._decls)
        # Flatten other views
        other = [o for o in [self._parent] + self._children
                 if o is not None and o is not caller]
        for o in other:
            o._flatten(self)

    # Functions that implement the dict interface

    def __getitem__(self, name):
        try:
            return self._values[name].get_value()
        except script_params.TargetParamError:
            # Unassigned reference, report as non-existing
            raise KeyError(name)

    def __iter__(self):
        return iter({k: v.get_value() for (k, v) in self._values.items()
                     if not v.is_unresolved_ref()})

    def __len__(self):
        return len(self._values)

    def tree(self):
        return self._tree

    def __repr__(self):
        return self._dump()

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as ex:
            raise AttributeError(ex)

    @staticmethod
    def _resolve_namespace(ns, decls, values):
        ns_list = unflatten_name(ns)
        ns_ok = True
        for n in ns_list:
            if n in decls:
                decls = decls[n]
                if n in values:
                    values = values[n]
                else:
                    assert not values
                    # Python has reference arguments => make copy
                    values = dict()
            else:
                ns_ok = False
                break
        if ns_ok and isinstance(decls, script_params.InnerDecl):
            return (decls, values)
        else:
            return None

    # Create and return sub-view
    def view(self, ns='', **kwargs):
        kwargs.setdefault('fn', self._fn)
        kwargs.setdefault('code_fn', self._code_fn)
        kwargs.setdefault('_lookup_file', self._lookup_file)
        if ns:
            data = self._resolve_namespace(ns, self._decls, self._tree)
            return ParamView(self, *data, **kwargs) if data else None
        else:
            return ParamView(self, self._decls, self._tree, **kwargs)

    # Save given parameters as YAML file
    def save(self, fn, overwrite=False, all_args=False):
        with Path(fn).open(mode=("w" if overwrite else "x"),
                           encoding='utf-8') as f:
            script_params.write_parameters(
                script_params.save_parameters(
                    self._tree, user_only=not all_args), self._code_fn, f)

    # Dump parameter tree for user inspection
    def _dump(self):
        return script_params.write_yaml(
            script_params.dump_parameters(self._decls, self._tree), None)

    @staticmethod
    def _list(tree, flat_decls, decls_only, verbose=False, advanced=1):
        flat_values = flatten_params(tree)
        # TODO This breaks encapsulation of Params.dump
        flat = []

        # The Table API doesn't handle lists in cells
        def convert_list(val):
            return str(val) if isinstance(val, list) else val

        if verbose:
            header = ["Name", "Type", "Value", "State", "File", "Description"]
            def output(d, p):
                return [d['full-type'],
                        convert_list(p.get('value', '<unassigned>')),
                        p['state'], p.get('file', ''),
                        d.get('description', '')]
            def no_data(d):
                return [d['full-type'], "<unassigned>", "<unassigned>", "",
                        d.get('description', '')]
        else:
            if decls_only:
                header = ["Name", "Type", "Description", "Default"]
            else:
                header = ["Name", "Type", "Value"]
            def output(d, p):
                return [d['full-type'],
                        convert_list(p.get('value', '<unassigned>'))]
            def no_data(d):
                if decls_only:
                    return [d['full-type'], d.get("description", ""),
                            convert_list(d.get('default', ''))]
                else:
                    return [d['full-type'], "<unassigned>"]

        for (n, v) in flat_values.items():
            if isinstance(v, script_params.Param):
                d = flat_decls[n].dump(advanced)
                p = v.dump()
                flat.append([n] + output(d, p))
            else:
                flat.append([n] + no_data(v.dump(advanced)))
        return (tree, header, sorted(flat))

    def _list_cmd(self, verbose=False, substr="", only_changed=False,
             include_outputs=False, advanced=1, yml=False):
        if yml:
            return self._dump()

        tree = script_params.filter_parameters(
            self._decls, self._tree, substr=substr,
            only_changed=only_changed, include_outputs=include_outputs,
            advanced=advanced)
        return self._list(tree, self._flat_decls, False,
                          verbose=verbose, advanced=advanced)

    def list(self, verbose=False, substr="", only_changed=False,
             include_outputs=False, advanced=1, yml=False):
        ret = self._list_cmd(
            verbose=verbose, substr=substr, only_changed=only_changed,
            include_outputs=include_outputs, advanced=advanced, yml=yml)
        if not yml:
            (tree, header, data) = ret
            # Convert to "plain" dict, without Params or Decl objects.
            tree = script_params.dump_parameters(self._decls, tree)
            return (tree, header, data)
        else:
            return ret

    def _help_cmd(self, substr="", advanced=1):
        tree = script_params.filter_declarations(
            self._decls, substr=substr, advanced=advanced)
        return self._list(tree, self._flat_decls,
                          True, advanced=advanced)

    def help(self, substr="", advanced=1):
        (tree, header, data) = self._help_cmd(substr=substr,
                                              advanced=advanced)
        # Convert to "plain" dict, without Params or Decl objects.
        tree = script_params.dump_parameters(self._decls, tree)
        return (tree, header, data)

    # Return YAML definition of specified parameter
    def describe(self, name):
        data = self._flat_decls[name].dump(self._flat_decls[name].advanced)
        if name in self._values:
            data.update(self._values[name].dump())
        else:
            data.update({'state': '<unassigned>'})
        return data

    def _set_value(self, decl, flat_name, param):
        try:
            param.root = (self._decls, self._tree)
            lookup_ref = lambda p: script_params.lookup_param(
                self._code_fn, self._decls, self._values, p)
            # Set parameter in tree. This results in the value being
            # visible in all parameter views.
            set_flattened_param(
                self._tree, flat_name,
                param.check(
                    self._code_fn, decl,
                    lookup_file=self._lookup_file,
                    lookup_ref=lookup_ref,
                    prefix=separator.join(flat_name.split(separator)[:-1]),
                    logger=params_log))
        except script_params.TargetParamError as ex:
            raise simics.SimExc_General(str(ex))
        self._flatten(self)

    # Set default value of specified parameter
    def setdefault(self, flat_name, value):
        if flat_name in self._flat_decls:
            # Parameters are write-once, except that NIL can be overwritten
            if (flat_name not in self._values
                or self._values[flat_name].value is None):
                name = flat_name.split(separator)[-1]
                self._set_value(self._flat_decls[flat_name], flat_name,
                                script_params.Param(name, value, 'script'))
        else:
            raise simics.SimExc_General(
                f'No parameter "{flat_name}" in script "{self._code_fn}"')

    def names(self):
        return list(self._flat_decls.keys())

# The underlying Python object of the Simics script-params object
class Params(collections.abc.Mapping):
    _cls = simics.confclass("script-params", pseudo=True,
                            doc=("Singleton that contains parameters"
                                 " of the current script"),
                            short_doc="script parameters")
    _cls.attr.current("[s*]", setter=None, pseudo=True)

    def __init__(self):
        self._view = ParamView(None, {}, {})
        # Parameter environment call stack
        self._param_envs = []
        # Current parameter prefix
        self._prefix = []

    # Move into sub-tree specified by namespace
    def _resolve_namespace(self, fn, ns, _lookup_file):
        view = self.view(ns, fn=fn, _lookup_file=_lookup_file, code_fn=fn)
        if view is not None:
            return view
        else:
            raise script_params.TargetParamError(
                f'Invalid namespace "{ns}" provided when calling "{fn}"'
                f' from "{self._view._fn}"')

    def _script_enter(self, fn, namespace, decls, args):
        p = Path(fn)
        _lookup_file = script_params.lookup_file_from_path(
            p, lookup_file_required)

        if self._view._fn:
            # Already inside a script, parameters already resolved
            # Use existing declaration and argument tree

            # Take current declarations and values from parent
            if not namespace:
                view = self.view(fn=fn, _lookup_file=_lookup_file, code_fn=fn)
                assert view is not None
                ns = ""
            else:
                ns = namespace
                view = self._resolve_namespace(fn, ns, _lookup_file)
        else:
            # Use input namespace if specified
            if namespace:
                ns = namespace
            else:
                ns = default_ns(self._view._tree, p)
            if ns in self._view._tree:
                raise script_params.TargetParamError(
                    f'The namespace "{ns}" already used, when running "{fn}"')

            # Match arguments values against declarations
            # Note that args is modified
            errors = {}
            values = script_params.resolve_parameters(
                fn, decls, args, errors, _lookup_file, params_log)
            if errors:
                raise script_params.TargetParamError(
                    "\n".join(errors.values()))
            script_params.resolve_param_refs(fn, values)
            script_params.check_param_cycles(values)

            if args:
                unused = flatten_params(args)
                raise script_params.TargetParamError(
                    'Arguments provided for non-declared parameters'
                    f' in "{fn}": {list(unused)}')
            # Top level parameter view
            view = ParamView(None, decls, values,
                             fn=fn, _lookup_file=_lookup_file)

        self._param_envs.append([self._view])
        self._view = view
        self._prefix.append(ns)
        return ns

    def _script_exit(self):
        values = dict(self._view._values)
        decls = self._view._decls

        (self._view,) = self._param_envs.pop()

        ns = self._prefix[-1]
        self._prefix.pop()

        if not self._view._fn:
            # At top level
            # Store declarations and values for later inspection
            assert ns not in self._view._decls
            self._view._decls[ns] = decls
            for (name, param) in values.items():
                flat = flatten_name(ns, name)
                set_flattened_param(self._view._tree, flat, param)
            self._view._flatten(None)

    def _set_code_fn(self, fn):
        self._view._code_fn = fn

    # Functions that implement the dict interface

    def __getitem__(self, name):
        return self._view[name]

    def __iter__(self):
        return iter(self._view)

    def __len__(self):
        return len(self._view)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as ex:
            raise AttributeError(ex)

    # Create sub-view
    def view(self, ns='', **kwargs):
        if ns:
            return self._view.view(ns, **kwargs)
        else:
            return self._view

    # Return YAML declarations in script file
    def _help_cmd(self, fn: str, yml=False, substr="", advanced=1, namespace=""):
        try:
            ret = parse_script(fn)
            decls = ret['params']
        except script_params.TargetParamError as ex:
            raise simics.SimExc_General(str(ex))
        except FileNotFoundError as ex:
            raise simics.SimExc_General(str(ex))

        if not yml:
            p = Path(fn)
            _lookup_file = script_params.lookup_file_from_path(
                p, lookup_file_required)
            view = ParamView(None, decls, ret['args'],
                             fn=fn, _lookup_file=_lookup_file)
            if namespace:
                ns = unflatten_name(namespace)
                for n in ns:
                    view = view.view(n)
                    if view is None:
                        raise simics.SimExc_General(
                            f"Non-existing namespace {namespace}")
            return view._help_cmd(substr, advanced)
        if decls:
            return script_params.write_yaml(
                script_params.dump_declarations(decls, advanced), None)
        else:
            raise simics.SimExc_General(f'No parameters in "{fn}"')

    def help(self, fn: str, yml=False, substr="", advanced=1, namespace=""):
        return self._help_cmd(fn, yml, substr, advanced, namespace)

    def setdefault(self, flat_name, value):
        self._view.setdefault(flat_name, value)

    def save(self, fn, overwrite=False, all_args=False, namespace=''):
        view = self._namespace_view(namespace)
        return view.save(fn, overwrite, all_args)

    def _namespace_view(self, namespace):
        view = self._view
        if namespace:
            ns = unflatten_name(namespace)
            for n in ns:
                view = view.view(n)
                if view is None:
                    raise simics.SimExc_General(
                        f"Non-existing namespace {namespace}")
        return view

    def _list_cmd(self, *args, namespace="", **kwargs):
        view = self._namespace_view(namespace)
        return view._list_cmd(*args, **kwargs)

    def list(self, *args, namespace="", **kwargs):
        view = self._namespace_view(namespace)
        return view.list(*args, **kwargs)

    def describe(self, name):
        return self._view.describe(name)

    def _writable_params(self):
        return list(set(self._view._flat_decls.keys()) - set(self.keys()))

    def assigned(self):
        return list(self.keys())

    # Simics object attribute getter
    @_cls.attr.current.getter
    def _current(self):
        return self.assigned()

# Wrapper functions for CLI commands

def print_tree(tree, prefix, name_prefix, name, output, decls_only):
    if isinstance(tree, script_params.Param):
        print(f"{name_prefix}{name}= {tree.value}", file=output)
        return
    elif isinstance(tree, script_params.Decl):
        extra = "= <unassigned>" if not decls_only else ""
        print(f"{name_prefix}{name}{extra}", file=output)
        return
    else:
        sub_trees = [(k, v) for (k, v) in tree.items()]
        if sub_trees:
            print(f"{name_prefix}{name}┐", file=output)
    spaces = " " * len(name)

    for (i, t) in enumerate(sub_trees):
        (k, v) = t
        if i == len(sub_trees) - 1:
            print_tree(v, f"{prefix}{spaces} ",
                       f"{prefix}{spaces}└", f" {k} ",
                       output, decls_only=decls_only)
        else:
            print_tree(v, f"{prefix}{spaces}│",
                       f"{prefix}{spaces}├", f" {k} ",
                       output, decls_only=decls_only)

def save_params_cmd(params, fn, overwrite, all_args, ns):
    try:
        params.object_data.save(fn, overwrite=overwrite, all_args=all_args,
                                namespace=ns)
    except FileExistsError:
        raise cli.CliError(f'Output file "{fn}" already exists')

def list_cmd(tree, header, data, output_tree, decls_only,
             border_style=None, table_width=None):
    if output_tree:
        output = StringIO()
        print_tree(tree, "", "", "", output, decls_only)
        msg = output.getvalue()
        output.close()
        return cli.command_verbose_return(message=msg, value=data)
    else:
        props = [(table.Table_Key_Columns,
                  [[(table.Column_Key_Name, n),
                    (table.Column_Key_Alignment, "left")]
                   for n in header])]
        output = table.Table(props, data)
        msg = output.to_string(rows_printed=0, no_row_column=True,
                               border_style=border_style,
                               force_max_width=table_width)
        return cli.command_verbose_return(message=msg, value=data)

def list_params_cmd(params, output_tree, verbose, substr, namespace,
                    only_changed, include_outputs, advanced, yml):
    try:
        data = params.object_data._list_cmd(
            verbose, substr, only_changed, include_outputs, advanced, yml,
            namespace=namespace)
        if not yml:
            return list_cmd(*data, output_tree, False)
        else:
            return cli.command_verbose_return(message=data)
    except simics.SimExc_General as ex:
        raise cli.CliError(ex)

def help_params_cmd(params, arg, yml, advanced, output_tree,
                    substr, namespace):
    assert isinstance(arg, tuple) and len(arg) == 3
    if arg[2] == 'file':
        fn = arg[1]
    else:
        fn = targets.get_script_file(arg[1], get_target_list())
        if fn is None or not fn.is_file():
            raise cli.CliError(f"Non-existing target '{arg[1]}'")
    try:
        data = params.object_data.help(fn, yml, substr, advanced, namespace)
        if not yml:
            return list_cmd(*data, output_tree, True)
        else:
            return cli.command_verbose_return(message=data)
    except simics.SimExc_General as ex:
        raise cli.CliError(ex)

# Used by command line options
def help_for_script(fn: str, border_style=None, table_width=None):
    global params
    data = params.help(fn)
    return list_cmd(*data, False, True,
                    border_style=border_style,
                    table_width=table_width).get_message()

def describe_params_cmd(params, name):
    if name in params.object_data._view.names():
        data = params.object_data.describe(name)
        return cli.command_verbose_return(
            value=list(list(x) for x in data.items()),
            message=script_params.write_yaml(data, None))
    else:
        raise cli.CliError(f'No such parameter: "{name}"')

def get_param_cmd(params, name):
    if name in params.object_data.view().names():
        return params.object_data.get(name)
    else:
        raise cli.CliError(f'No such parameter: "{name}"')

def setdefault_param_cmd(params, name, value):
    try:
        params.object_data.setdefault(name, value)
    except simics.SimExc_General as ex:
        raise cli.CliError(ex)

def info_cmd(params):
    return [(None, [])]

def status_cmd(params):
    if params:
        return [("Script parameters",
                 [("Number of parameters", len(params.object_data)),
                  ("Number of tree nodes",
                   tree_size(params.object_data.view().tree()))])]
    else:
        return [(None, [])]

def assigned_params_cmd(params):
    return params.object_data.assigned()

# Expanders for CLI commands

def param_expander(s, params):
    return cli.get_completions(s, params.object_data.keys())

def set_param_expander(s, params):
    return cli.get_completions(s, params.object_data._writable_params())

def decl_expander(s, params):
    return cli.get_completions(s, params.object_data._view.names())

def target_expander(prefix):
    target_info = get_target_list()
    return cli.get_completions(prefix, set(target_info.keys()))

def set_default_value_expander(s, params, prev_args):
    name = prev_args[0]
    if (params.object_data._view
        and params.object_data._view._flat_decls
        and name in params.object_data._view._flat_decls):
        decl = params.object_data._view._flat_decls[name]
        if decl.type == bool:
            return cli.boolean_t.expand(s)
        elif decl.values:
            return cli.get_completions(s, [str(v) for v in decl.values])
    return []

# Exposed Python params object
params = None

def init():
    from . import target_commands
    cli.new_info_command(Params._cls.classname, info_cmd)
    cli.new_status_command(Params._cls.classname, status_cmd)

    obj = simics.pre_conf_object('params', Params._cls.classname)
    simics.SIM_add_configuration([obj], None)
    simics.VT_add_permanent_object(conf.params)

    global params
    params = conf.params.object_data

    script_params.init()
    target_commands.init()

    cli.new_command(
        'get', get_param_cmd,
        [cli.arg(cli.str_t, 'name', expander=param_expander)],
        cls=Params._cls.classname,
        type=["CLI", "Parameters"],
        see_also=['run-script', 'load-target'],
        short="get parameter value",
        doc="""
        Get value of parameter <arg>name</arg>. If the
        parameter is not assigned, <tt>NIL</tt> is returned.""")

    cli.new_command(
        'setdefault', setdefault_param_cmd,
        [cli.arg(cli.str_t, 'name', expander=set_param_expander),
         cli.arg(cli.poly_t('value', cli.str_t, cli.int_t, cli.float_t,
                            cli.list_t, cli.boolean_t), 'value',
                 expander=set_default_value_expander)],
        cls=Params._cls.classname,
        type=["CLI", "Parameters"],
        see_also=['run-script', 'load-target'],
        short="set parameter value default",
        doc="""
Set default value of parameter <arg>name</arg> to be <arg>value</arg>.""")

    cli.new_command(
        'save', save_params_cmd,
        [cli.arg(cli.filename_t(), 'file'),
         cli.arg(cli.flag_t, '-overwrite'),
         cli.arg(cli.flag_t, '-all'),
         cli.arg(cli.str_t, 'namespace', '?', '', expander=decl_expander)],
        cls=Params._cls.classname,
        type=["CLI", "Parameters"],
        see_also=['run-script', 'load-target'],
        short="save parameter values",
        doc="""
Save parameter values in YAML format in
<arg>file</arg>. If <tt>-overwrite</tt> is specified, the file is
overwritten if it already exists.

The <arg>namespace</arg> argument can be used to
only save the sub-tree defined by that namespace value.

Only the non-default parameter values are saved, unless <tt>-all</tt>
is specified.""")

    cli.new_command(
        'help', help_params_cmd,
        [cli.arg((cli.str_t, cli.filename_t(exist=True)), ('target', 'file'),
                 expander=(target_expander, None)),
         cli.arg(cli.flag_t, '-yml'),
         cli.arg(cli.uint_t, 'advanced', spec='?', default=1),
         cli.arg(cli.flag_t, '-tree'),
         cli.arg(cli.str_t, 'substr', '?', ''),
         cli.arg(cli.str_t, 'namespace', '?', '')],
        cls=Params._cls.classname,
        type=["CLI", "Parameters"],
        see_also=['run-script', 'load-target'],
        short="display script parameters",
        doc="""
        Display available script parameter tree in script
        <arg>file</arg> or target <arg>target</arg>.

        If <tt>-tree</tt> is specified, the parameter tree structure is
        displayed. Otherwise the parameters are displayed in a table.

        The <arg>namespace</arg> argument can be used to
        only display the sub-tree defined by that namespace value.

        Only parameters whose <tt>advanced</tt> setting is less than
        or equal to the value of the <arg>advanced</arg> argument will
        be displayed.

        The <arg>substr</arg> argument can be used to only display parameters
        whose names contain the specified sub-string.

        If the <tt>-yml</tt> flag is specified, the output will be pure YAML,
        suitable for parsing.""")

    cli.new_command(
        'describe', describe_params_cmd,
        [cli.arg(cli.str_t, 'name', expander=decl_expander)],
        cls=Params._cls.classname,
        type=["CLI", "Parameters"],
        see_also=['run-script', 'load-target'],
        short="display parameter information",
        doc="""
Display information about parameter <arg>name</arg>.""")

    cli.new_command(
        'assigned', assigned_params_cmd,
        [],
        cls=Params._cls.classname,
        type=["CLI", "Parameters"],
        see_also=['run-script', 'load-target'],
        short="return names of assigned parameters",
        doc="return names of assigned parameters")

    cli.new_command(
        'list', list_params_cmd,
        [cli.arg(cli.flag_t, '-tree'),
         cli.arg(cli.flag_t, '-verbose'),
         cli.arg(cli.str_t, 'substr', '?', ''),
         cli.arg(cli.str_t, 'namespace', '?', '', expander=decl_expander),
         cli.arg(cli.flag_t, '-only-changed'),
         cli.arg(cli.flag_t, '-include-outputs'),
         cli.arg(cli.uint_t, 'advanced', spec='?', default=1),
         cli.arg(cli.flag_t, '-yml')],
        cls=Params._cls.classname,
        type=["CLI", "Parameters"],
        see_also=['run-script', 'load-target'],
        short="list parameter values",
        doc="""
List parameter values.

If <tt>-tree</tt> is specified, the parameter tree structure is
displayed. Otherwise the parameters are displayed in a table.

The <arg>namespace</arg> argument can be used to
only display the sub-tree defined by that namespace value.

Only parameters whose <tt>advanced</tt> setting is less than
or equal to the value of the <arg>advanced</arg> argument will
be displayed.

The <arg>substr</arg> argument can be used to only display parameters
whose names contain the specified sub-string. The flag
<tt>-only-changed</tt> can also be specified to only display
parameters whose values are non-default. The <tt>-include-outputs</tt>
flag can be used to display output parameters. The flag
<tt>-verbose</tt> can be specified to display more information about
each parameter.

If the <tt>-yml</tt> flag is specified, the output will be pure YAML,
suitable for parsing.""")
