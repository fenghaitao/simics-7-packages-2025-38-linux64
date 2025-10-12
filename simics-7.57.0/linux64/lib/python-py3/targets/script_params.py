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


# This file contains script parameter functionality that does not require
# anything in Simics.

import ast
import collections
import json
import pathlib
import yaml
import re
import typing
import sys
import copy
from typing import Dict, List, TextIO, Tuple, Optional, Union, Callable, Any
from scriptdecl import parse_suffixed_int

# The public script parameter functions
__all__ = [
    'Decl',
    'dump_declarations',
    'dump_parameters',
    'init',
    'Param',
    'parse_script',
    'resolve_parameters',
    'save_parameters',
    'write_parameters',
    'write_yaml',
]

resolve_callback = None

def register_resolve_callback(cb):
    global resolve_callback
    resolve_callback = cb

# Separator in flat argument names
separator = ':'

def flatten_name(prefix, name):
    if prefix:
        if name:
            return f"{prefix}{separator}{name}"
        else:
            return prefix
    else:
        return name

def unflatten_name(flat_name):
    return flat_name.split(separator)

def set_flattened_param(tree, key, val):
    cur_params = tree
    parts = key.split(separator)
    for k in parts[:-1]:
        cur_params = cur_params.setdefault(k, {})
    name = parts[-1]
    cur_params[name] = val

def unflatten_params(values):
    params = {}
    for (key, val) in values.items():
        set_flattened_param(params, key, val)
    return params

def flatten_params_impl(flat, prefix, values):
    for (name, val) in values.items():
        param = flatten_name(prefix, name)
        if isinstance(val, dict):
            flatten_params_impl(flat, param, val)
        else:
            flat[param] = val

def flatten_params(values, prefix=""):
    flat = {}
    flatten_params_impl(flat, prefix, values)
    return flat

class TargetParamError(Exception):
    pass

# There is no built-in encoder for pathlib objects
class PathJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, pathlib.PurePath):
            return str(o)
        else:
            return super().default(o)

LookupFile = Callable[[str], str]

# Generate lookup_file wrapper suitable for parse_script
def lookup_file_from_path(p: pathlib.Path, lookup_file: LookupFile):
    def script_lookup_file(f, **kwargs):
        kwargs.setdefault('cur_path', str(p.parent))
        return lookup_file(f, **kwargs)
    return script_lookup_file

# Make sure multi-line strings are displayed correctly
def str_presenter(dumper, data):
    try:
        dlen = len(data.splitlines())
        if (dlen > 1):
            return dumper.represent_scalar('tag:yaml.org,2002:str',
                                           data, style='|')
    except TypeError:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

class UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        mapping = set()
        for (key_node, value_node) in node.value:
            if ':merge' in key_node.tag:
                continue
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise ValueError(f"Duplicate {key!r} key found in YAML.")
            mapping.add(key)
        return super().construct_mapping(node, deep)

def extract_yaml_decl(fn: str, data: str,
                      warnings=True) -> Optional[Tuple[str, int]]:
    lines = data.splitlines()
    start_marker = re.compile(r"@?'''")
    params_start = None
    for (i, l) in enumerate(lines):
        if start_marker.fullmatch(l):
            params_start = i
            break

    if params_start is not None:
        maybe_header = [l.rstrip()
                        for l in lines[params_start + 1 : params_start + 3]]
        if not maybe_header:
            return None
        if maybe_header[0] == '%YAML 1.2':
            if (len(maybe_header) == 1
                or maybe_header[1] != '---'):
                print('Found YAML marker but no parameter'
                      f' section start ("---") on the next line, in "{fn}".'
                      ' Did you intend to write YAML parameters?',
                      file=sys.stderr)
                return None
        else:
            return None
    else:
        return None

    params_end = None
    for (i, l) in enumerate(lines[params_start + 3:]):
        if l.rstrip() == "'''":
            params_end = i + params_start + 3
            break

    if params_end is None:
        if warnings:
            print(f'Found YAML parameter section start but not end, in "{fn}".'
                  ' Did you intend to write YAML parameters?', file=sys.stderr)
        return None

    return ("\n".join(lines[params_start + 3 : params_end]), params_end + 1)

def looks_like_embedded_yaml_script(fn: str, data: str,
                                    warnings=True) -> bool:
    unwrap = extract_yaml_decl(fn, data, warnings=warnings)
    return unwrap is not None

def looks_like_pure_yaml(fn: str, data: str, warnings=True) -> bool:
    lines = data.splitlines()
    params_start = None
    for (i, l) in enumerate(lines):
        ll = l.strip()
        if ll.startswith("%YAML 1.2"):
            params_start = i
            break
        elif not ll or ll.startswith('#'):
            continue
        else:
            break

    if params_start is not None:
        maybe_header = [l.rstrip()
                        for l in lines[params_start : params_start + 2]]
        if not maybe_header:
            return None
        if maybe_header[0] == '%YAML 1.2':
            if (len(maybe_header) == 1
                or maybe_header[1] != '---'):
                print('Found YAML marker but no document'
                      f' start marker ("---") on the next line, in "{fn}".'
                      ' Did you intend to write YAML parameters?',
                      file=sys.stderr)
                return None
        else:
            return None
    else:
        return None

    params_end = None
    for (i, l) in enumerate(lines[params_start + 2:]):
        if l.rstrip() == "...":
            params_end = i + params_start + 2
            break

    if params_end is None:
        if warnings:
            print(f'Found YAML document start but no end, in "{fn}".'
                  ' Did you intend to write YAML parameters?', file=sys.stderr)
        return None

    return True

def looks_like_yaml_script(fn: pathlib.Path,
                           data: str, warnings=True) -> bool:
    return (looks_like_pure_yaml(str(fn), data, warnings=warnings)
            or looks_like_embedded_yaml_script(
                str(fn), data, warnings=warnings))

def parse_embedded_params_script(fn: pathlib.Path,
                                 data: str) -> Tuple[Dict, str, int]:
    unwrapped = extract_yaml_decl(str(fn), data, warnings=False)
    if unwrapped is None:
        raise TargetParamError(f'"{fn}" is not a valid target:'
                               ' incorrect YAML declarations')
    (param_section, code_start_line) = unwrapped
    code_lines = data.splitlines()[code_start_line:]
    code_text = "\n".join(code_lines)

    # Verify only one parameter section
    if extract_yaml_decl(str(fn), code_text, warnings=False) is not None:
        raise TargetParamError(f'"{fn}" is not a valid target:'
                               ' duplicate parameter sections')
    try:
        try:
            params = yaml.load(param_section, Loader=UniqueKeyLoader) # nosec
        except ValueError as ex:
            raise TargetParamError(f'Could not parse target "{fn}": {ex}')
        if not isinstance(params, dict):
            raise TargetParamError(f'Not a valid target: "{fn}"')
        return (params, code_text, code_start_line)
    except yaml.YAMLError as ex:
        raise TargetParamError(f"Error parsing YAML parameters: {ex}")

def parse_yaml_string(fn: pathlib.Path, data: str) -> Tuple[Dict, str, int]:
    """ Parse the script given as <arg>data</arg> and return a 3-tuple:
    parameter section as a dict, code section as a (possibly empty) string and
    the line number where the code section starts, or <tt>None</tt>
    if no code. Raises an exception if the input is not a valid script."""

    if looks_like_embedded_yaml_script(fn, data, warnings=False):
        # YAML section at the top of a script
        return parse_embedded_params_script(fn, data)
    elif not looks_like_yaml_script(fn, data, warnings=False):
        raise TargetParamError(
            f'"{fn}" is not a valid target: file must have YAML format'
            ' specifier and document start and end markers.')
    try:
        # If the whole file is valid YAML, we have parameters only
        try:
            docs = list(yaml.load_all(data, Loader=UniqueKeyLoader)) # nosec
        except ValueError as ex:
            raise TargetParamError(f'Could not parse target "{fn}": {ex}')
        if len(docs) != 1:
            raise TargetParamError(
                f'Target "{fn}" must contain 1 YAML document')
        if not isinstance(docs[0], dict):
            raise TargetParamError(f'Not a valid target: "{fn}"')
        return (docs[0], "", None)
    except yaml.YAMLError as ex:
        raise TargetParamError(ex)

def parse_yaml_file(yaml_file: pathlib.Path) -> Tuple[Dict, str, int]:
    """ This does the same as <fun>parse_yaml_string</fun> but takes a file
    instead of a string."""
    try:
        return parse_yaml_string(yaml_file,
                                 yaml_file.read_text(encoding='utf-8'))
    except TargetParamError as ex:
        raise TargetParamError(f"Error when parsing '{yaml_file}': {ex}")

def write_yaml(data: Dict, output_file: TextIO) -> Optional[str]:
    """ Encode <arg>data</arg> as YAML and write to the
    stream <arg>output_file</arg>, or to stdout if <tt>None</tt>."""
    if output_file is None:
        return yaml.dump(data, sort_keys=False, allow_unicode=True)
    else:
        yaml.dump(data, output_file, sort_keys=False, allow_unicode=True)
        return None

def validate_integer(x: Any, **kwds) -> int:
    # YAML may have parsed it already
    if isinstance(x, int):
        return x
    elif isinstance(x, str):
        try:
            val = parse_suffixed_int(x)
        except ValueError:
            # Re-raise below
            pass
        else:
            if val is not None:
                return val
    raise ValueError(f'Argument "{x}" not an integer representation.')

def validate_fixed_size_integer(val: Any, is_signed: bool,
                                bits: int) -> int:
    x = validate_integer(val)
    if ((is_signed and (x >= -(1 << (bits - 1)) and x < (1 << (bits - 1))))
        or (not is_signed and (x >= 0 and x < (1 << bits)))):
        return x
    else:
        s = "i" if is_signed else "u"
        raise ValueError(f"Argument 0x{x:x} not in {s}{bits} range.")

def validate_list(l: Any, **kwds) -> List:
    # YAML may have parsed it already
    if isinstance(l, list):
        return l
    elif isinstance(l, str):
        try:
            return ast.literal_eval(l)
        except ValueError:
            # Fall through
            pass
        except SyntaxError:
            # Fall through
            pass
    raise ValueError(f"Argument {l} not a list representation.")

def validate_file(f: Any, lookup_file=None, required=True, **kwds) -> str:
    assert lookup_file is not None
    if isinstance(f, str):
        return lookup_file(f, required=required, keep_simics_ref=True)
    else:
        raise ValueError(f"Argument {f} is not a file name.")

# The YAML 1.2 spec only recognises true/false as booleans.
# We also allow CLI values.
valid_true = re.compile(r"true|TRUE")
valid_bool = re.compile(r"true|TRUE|false|FALSE")

def validate_bool(l: Any, **kwds) -> bool:
    # YAML parse has typically already converted the value
    if isinstance(l, bool):
        return l
    # But we may set parameters by other means, e.g. command line parameters
    elif (isinstance(l, str) and valid_bool.fullmatch(l)):
        return valid_true.fullmatch(l)
    else:
        raise ValueError(f"Argument {l} is not a boolean.")

def validate_array_size(l: Any, **kwds) -> bool:
    x = validate_integer(l, **kwds)
    if x > 0:
        return x
    else:
        raise ValueError('Array size not a positive integer.')

valid_types = {
    'str': (str, lambda x, **kwds: x),
    'int': (int, validate_integer),
    'bool': (bool, validate_bool),
    'float': (float, lambda x, **kwds: x),
    'i8': (int, lambda x, **kwds: validate_fixed_size_integer(x, True, 8)),
    'u8': (int, lambda x, **kwds: validate_fixed_size_integer(x, False, 8)),
    'i16': (int, lambda x, **kwds: validate_fixed_size_integer(x, True, 16)),
    'u16': (int, lambda x, **kwds: validate_fixed_size_integer(x, False, 16)),
    'i32': (int, lambda x, **kwds: validate_fixed_size_integer(x, True, 32)),
    'u32': (int, lambda x, **kwds: validate_fixed_size_integer(x, False, 32)),
    'i64': (int, lambda x, **kwds: validate_fixed_size_integer(x, True, 64)),
    'u64': (int, lambda x, **kwds: validate_fixed_size_integer(x, False, 64)),
    'i128': (int, lambda x, **kwds: validate_fixed_size_integer(x, True, 128)),
    'u128': (int, lambda x, **kwds: validate_fixed_size_integer(x, False, 128)),
    'i256': (int, lambda x, **kwds: validate_fixed_size_integer(x, True, 256)),
    'u256': (int, lambda x, **kwds: validate_fixed_size_integer(x, False, 256)),
    'list': (list, validate_list),
    'file': (str, validate_file),
}

class InnerDecl(collections.abc.MutableMapping):
    __slots__ = ('description', 'children', 'name',
                 'advanced', 'fn')
    def __init__(self, name, fn, desc, advanced, prefix, children={}):
        self.name = name
        self.description = desc
        self.advanced = advanced
        self.children = dict(children)
        # Filename for inner decl necessary to calculate
        # parameter reference roots, which are per file
        self.fn = str(fn)
        if not isinstance(self.description, str):
            raise TargetParamError(
                f'Description for "{flatten_name(prefix, self.name)}" is not a'
                f' string, in target "{fn}"')

    def __len__(self):
        return len(self.children)

    def __iter__(self):
        return iter(self.children)

    def __getitem__(self, k):
        return self.children[k]

    def __setitem__(self, k, v):
        self.children[k] = v

    def __delitem__(self, k):
        del self.children[k]

    def __repr__(self):
        return repr(self.children)

    def dump(self, advanced, prune=True):
        output = {}
        if advanced is None or self.advanced <= advanced:
            if self.description:
                output['description'] = self.description
            for (k, v) in self.items():
                if advanced is None or v.advanced <= advanced:
                    if isinstance(v, dict):
                        output[k] = dump_declarations(
                            v, advanced=advanced, prune=prune)
                    else:
                        output[k] = v.dump(advanced, prune=prune)
        return output

    def __deepcopy__(self, memo):
        cp = copy.copy(self)
        cp.children = copy_parameters(self)
        return cp

class Decl:
    __slots__ = ('type', 'default', 'required', 'name', 'output', 'fn',
                 'description', 'validate', 'values',
                 'input_type', 'advanced', 'allow_empty', 'explicit_default',
                 'extra_data')
    def __init__(self, decl_type, arg_validator, input_type, default,
                 required, name, output, desc, values, advanced,
                 # Use keyword argument since VP code uses this class directly
                 fn, allow_empty=False, explicit_default=False, extra_data={}):
        self.type = decl_type
        self.validate = arg_validator
        self.default = default
        self.required = required
        self.name = name
        self.output = output
        self.description = desc
        self.values = values
        self.advanced = advanced
        self.allow_empty = allow_empty
        self.input_type = input_type
        self.explicit_default = explicit_default
        self.fn = str(fn)
        self.extra_data = extra_data
        if self.output:
            self.required = False

    def dump(self, advanced, prune=True):
        assert advanced is None or self.advanced <= advanced

        data = {
            'type': self.type.__name__,
            'full-type': self.input_type,
            'required': self.required,
            'output': self.output,
            'default': self.default,
            'values': self.values,
            'advanced': self.advanced,
        }
        if self.description:
            data['description'] = self.description
        if prune:
            # Do not display values that are not set
            return {k: v for (k, v) in data.items() if v is not None}
        else:
            return data

    def __repr__(self):
        return (f'Decl({self.name} of "{self.type.__name__}" type'
                f', default={self.default})')

class Param:
    __slots__ = ('name', 'value', 'state', 'decl', 'fn', 'root',
                 'is_ref', 'ref')
    def __init__(self, name, value, state, decl=None, fn=None):
        self.state = state
        self.decl = decl
        self.name = name
        self.fn = fn
        self.root = None
        self.is_ref = self.is_ref_val(value)
        self.ref = None
        if self.is_ref:
            self.value = value[1:]
        else:
            self.value = value

    def __deepcopy__(self, _):
        if self.is_ref:
            if self.ref:
                value = self.ref
            else:
                value = f"^{self.value}"
        else:
            value = self.value
        return Param(self.name, value, self.state)

    @staticmethod
    def is_ref_val(value):
        return (value is not None and isinstance(value, str)
                and value.startswith('^'))

    def check_ref(self, fn, decl, lookup_ref=None, **kwds):
        # lookup_ref not set until after initial parameter resolution

        # value is Param if referenced is resolved
        assert isinstance(self.value, Param) or isinstance(self.value, str)
        if lookup_ref and isinstance(self.value, str):
            ref = lookup_ref(self.value)
            # Referred parameter may be unassigned
            if isinstance(ref, Param):
                if self.decl.type == ref.decl.type:
                    if self.decl.allow_empty == ref.decl.allow_empty:
                        # Remember reference target name
                        self.ref = self.value
                        self.value = ref
                    else:
                        raise TargetParamError(
                            f'Parameter "{self.name}" cannot refer to'
                            f' parameter "{ref.name}": allow_empty mismatch,'
                            f' in target "{fn}"')
                else:
                    raise TargetParamError(
                        f'Parameter "{self.name}" of type'
                        f' "{self.decl.type.__name__}" cannot refer to'
                        f' parameter "{ref.name}" of other type'
                        f' "{ref.decl.type.__name__}" in target "{fn}"')
        return self

    def check(self, fn, decl, **kwds):
        # Save the file where parameter was set
        if self.fn is None:
            self.fn = str(fn)
        if decl:
            self.decl = decl
        if self.is_ref:
            return self.check_ref(fn, decl, **kwds)
        prefix = kwds.pop('prefix', '')
        logger = kwds.pop('logger', None)
        try:
            if not (decl.allow_empty and self.value is None):
                self.value = decl.type(decl.validate(self.value, **kwds))
                if self.decl.values and self.value not in self.decl.values:
                    raise TargetParamError(
                        f'Invalid value "{self.value}" for parameter'
                        f' "{flatten_name(prefix, self.name)}",'
                        f' in target "{fn}". Choices are: {self.decl.values}')
            if logger:
                logger(f'Parameter "{flatten_name(prefix, self.name)}" assigned'
                       f' value "{self.value}" in target "{fn}"')
            return self
        except (TypeError, ValueError) as ex:
            raise TargetParamError(
                f'Could not set "{self.value}" for parameter'
                f' "{flatten_name(prefix, self.name)}" in target "{fn}": {ex}')

    # Classic algorithm for finding cycles in a linked list
    def check_cycles(self):
        turtle = hare = self
        while isinstance(hare, Param) and hare.is_ref:
            turtle = turtle.value
            hare = hare.value
            if isinstance(hare, Param) and hare.is_ref:
                hare = hare.value
            else:
                break
            if hare == turtle:
                raise TargetParamError(
                    'Circular parameter references found, when parameter'
                    f' "{self.name}" refers to "{self.value.name}"')
        return self

    def resolve_ref(self):
        p = self
        while p.is_ref:
            if isinstance(p.value, Param):
                p = p.value
            else:
                raise TargetParamError(
                    f'Parameter "{p.name}" refers to unassigned parameter'
                    f' "{p.value}"')
        return p

    # Return parameter value. Throws exception on unresolved reference.
    def get_value(self):
        p = self.resolve_ref()
        if resolve_callback:
            return resolve_callback(p)
        else:
            return p.value

    # Return parameter value. Returns None on unresolved reference.
    def get_value_weak_ref(self):
        try:
            return self.get_value()
        except TargetParamError:
            return None

    def is_unresolved_ref(self):
        try:
            _ = self.resolve_ref()
            return False
        except TargetParamError:
            return True

    def dump(self):
        # self.fn is the resolved absolute path
        val = self.get_value_weak_ref()
        if val is not None or (self.decl.allow_empty
                               and not self.is_unresolved_ref()):
            data = {'value': val, 'state': self.state, 'file': self.fn}
        else:
            data = {'state': '<unassigned>', 'file': self.fn}
        # Include reference target
        if self.is_ref:
            if isinstance(self.value, Param):
                assert self.ref is not None
                data['ref'] = self.ref
            else:
                data['ref'] = self.value
        return data

    def __repr__(self):
        return f"Param({self.name}={self.get_value_weak_ref()})"

T = typing.TypeVar('T')
DeclNode = Union[Decl, Dict]
DeclTree = Dict[str, DeclNode]
ArgNode = Union[Param, Dict]
ArgTree = Dict[str, ArgNode]

def flatten_declarations_impl(decls: DeclTree, prefix: str, flat: str):
    for (name, decl) in decls.items():
        if isinstance(decl, Decl):
            flat[flatten_name(prefix, decl.name)] = decl
        else:
            flatten_declarations_impl(decl, flatten_name(prefix, name), flat)

def flatten_declarations(decls: DeclTree):
    flat = {}
    flatten_declarations_impl(decls, "", flat)
    return flat

def validate_default(fn: pathlib.Path, decl: Decl, default: T,
                     prefix: str, **kwds):
    if Param.is_ref_val(default):
        return

    if decl.allow_empty and default is None:
        return

    try:
        decl.validate(default, **kwds)
    except ValueError as ex:
        raise TargetParamError(
            f'Invalid default value "{default}" for parameter'
            f' "{flatten_name(prefix, decl.name)}" in target "{fn}": {ex}')
    if decl.values and default not in decl.values:
        raise TargetParamError(
            f'Invalid default value "{default}" for parameter'
            f' "{flatten_name(prefix, decl.name)}", in target "{fn}".'
            f' Choices are: {decl.values}')

def validate_choices(fn: pathlib.Path, decl: Decl, values: List[T],
                     prefix: str, **kwds):
    if not isinstance(values, list):
        raise TargetParamError(
            f'Allowed values for parameter "{flatten_name(prefix, decl.name)}"'
            f' must be a list in target "{fn}"')
    for v in values:
        if not isinstance(v, decl.type):
            raise TargetParamError(
                f'Invalid types for allowed value "{v}" of parameter'
                f' "{flatten_name(prefix, decl.name)}" in target "{fn}"')
        try:
            decl.validate(v, **kwds)
        except ValueError as ex:
            raise TargetParamError(
                f'Invalid allowed value "{v}" for parameter'
                f' "{flatten_name(prefix, decl.name)}" in target "{fn}": {ex}')

list_type_re = re.compile(r"^(\w+)\s*(\[(([\[\]]|\w)+)\])?$")

def construct_decl_type(fn: pathlib.Path, name: str,
                        t: str) -> Tuple[T, Callable[[T], T]]:
    pattern = list_type_re.fullmatch(t)
    if (not pattern or not pattern.group(1) in valid_types
        or (pattern.group(2) and pattern.group(1) != 'list')):
        raise TargetParamError(
            f'Invalid type specification "{t}" for parameter'
            f' "{name}" in target "{fn}"')
    main_type = pattern.group(1)
    (decl_type, arg_validator) = valid_types[main_type]
    if decl_type == list and pattern.group(2):
        (_, elem_validator) = construct_decl_type(fn, name, pattern.group(3))
        arg_validator = lambda l, **kwds: [elem_validator(x, **kwds)
                                           for x in validate_list(l)]
    return (decl_type, arg_validator)

def validate_and_construct_decl(
        fn: pathlib.Path,
        decl: Dict, name: str, lookup_file: LookupFile, prefix: str,
        parent: Union[Decl, InnerDecl]) -> Decl:
    extra_keys = {k for k in decl if k.startswith('x-')}
    unknown_keys = set(decl.keys()) - {
        'type', 'default', 'required', 'description',
        'values', 'output', 'advanced', 'allow_empty'} - extra_keys
    if unknown_keys:
        raise TargetParamError(
            f'Unknown keys "{unknown_keys}" in parameter specification'
            f' "{flatten_name(prefix, name)}" in target "{fn}"')

    if 'type' not in decl:
        raise TargetParamError(
            f'Missing type specification for parameter'
            f' "{flatten_name(prefix, name)}" in target "{fn}"')
    try:
        advanced = validate_integer(decl.get('advanced', parent.advanced))
    except ValueError as ex:
        raise TargetParamError(
            "Invalid 'advanced' setting for parameter"
            f' {flatten_name(prefix, name)}" in target "{fn}": {ex}"')

    (decl_type, arg_validator) = construct_decl_type(
        fn, flatten_name(prefix, name), decl['type'])
    d = Decl(decl_type, arg_validator, decl['type'],
             decl.get('default'),
             decl.get('required', 'default' not in decl), name,
             decl.get('output', False),
             decl.get('description', ""),
             decl.get('values', []),
             advanced,
             fn,
             allow_empty=decl.get('allow_empty', False),
             explicit_default=('default' in decl),
             extra_data={k: decl[k] for k in extra_keys})
    if 'values' in decl:
        validate_choices(fn, d, decl['values'], prefix,
                         lookup_file=lookup_file, required=False)
    if 'default' in decl:
        validate_default(fn, d, decl['default'], prefix,
                         lookup_file=lookup_file, required=False)
    return d

# Parameter inner node name format
# Leaf nodes must have empty group 3
array_ns_re = re.compile(r"^((\w|[\.-])+)(\[((\w|[\.-])+)\])?$")

def parse_array_ns(fn: pathlib.Path, ns: str) -> Optional[str]:
    pattern = array_ns_re.fullmatch(ns)
    if not pattern:
        raise TargetParamError(
            f'Invalid namespace "{ns}", in target "{fn}"')
    if pattern.group(3) is not None:
        return pattern.group(4)
    return None

def verify_param_name(fn: pathlib.Path, prefix: str, name: str):
    try:
        ret = parse_array_ns(fn, name)
    except TargetParamError:
        ret = ""
    if ret is not None:
        raise TargetParamError(
            (f'Invalid parameter name "{flatten_name(prefix, name)}"'
             f', in target "{fn}"'))

def set_non_required(fn: pathlib.Path, node: DeclNode, provided: list):
    for p in provided:
        parts = unflatten_name(p)
        n = node
        for k in parts[:-1]:
            if not isinstance(n, InnerDecl) or k not in n:
                raise TargetParamError(
                    f'Non-existing provided parameter'
                    f' "{p}" in target "{fn}"')
            n = n[k]
        k = parts[-1]
        if k not in n or not isinstance(n[k], Decl):
            raise TargetParamError(
                f'Non-existing provided parameter'
                f' "{p}" in target "{fn}"')
        n[k].required = False

def override_default(fn: pathlib.Path, node: DeclNode,
                     val: Any, lookup_file: LookupFile, prefix: str):
    if isinstance(node, InnerDecl):
        if not isinstance(val, dict):
            raise TargetParamError(
                'Invalid default override of'
                f' "{flatten_name(prefix, node.name)}" in target "{fn}"')
        for (k, v) in val.items():
            if k in node:
                override_default(fn, node[k], v, lookup_file, prefix)
            else:
                raise TargetParamError(
                    f'Default override for non-existing imported parameter'
                    f' "{flatten_name(prefix, k)}" in target "{fn}"')
    else:
        validate_default(fn, node, val, prefix, lookup_file=lookup_file,
                         required=False)
        node.default = val
        node.explicit_default = True
        node.fn = str(fn)

def override_filenames(node: DeclNode, old: pathlib.Path, new: pathlib.Path):
    if isinstance(node, InnerDecl):
        for (k, v) in node.items():
            override_filenames(v, old, new)
    if str(node.fn) == str(old):
        node.fn = str(new)

import_cache = {}

def copy_parameters(tree: DeclTree|ArgTree) -> Dict:
    output = {}
    for (k, v) in tree.items():
        if isinstance(v, dict):
            output[k] = copy_parameters(v)
        else:
            output[k] = copy.deepcopy(v)
    return output

def parse_import(fn: pathlib.Path, data: Dict, name: str, input_args: ArgTree,
                 lookup_file: LookupFile, ignore_blueprints: bool, prefix: str,
                 targets: list) -> Tuple[DeclTree, ArgTree, str, Dict]:
    unknown_keys = set(data.keys()) - {'import', 'provides', 'defaults'}
    if unknown_keys:
        raise TargetParamError(
            f'Unknown keys "{unknown_keys}" in import definition'
            f' "{flatten_name(prefix, name)}" in target "{fn}"')

    import_fn = data['import']
    try:
        full_fn = lookup_file(import_fn)
    except ValueError:
        full_fn = None
    if not full_fn:
        raise TargetParamError(
            f'Imported file "{import_fn}" cannot be found'
            f' in target "{fn}"')

    p = pathlib.Path(full_fn).absolute()
    import_lookup_file = lookup_file_from_path(p, lookup_file)
    key = (str(p), json.dumps(targets, sort_keys=True, cls=PathJSONEncoder),
           json.dumps(input_args, sort_keys=True, cls=PathJSONEncoder),
           ignore_blueprints)
    if key in import_cache:
        import_data = import_cache[key]
    else:
        import_data = parse_script(p, import_lookup_file, targets,
                                   input_args, ignore_blueprints)
        import_cache[key] = import_data
    imports = copy.deepcopy(import_data['params'])
    args = copy_parameters(import_data['args'])
    script = ""
    blueprints = import_data['blueprints']
    if not imports:
        raise TargetParamError(
            f'Imported file "{import_fn}" invalid, in target "{fn}"')

    # Change requiredness for computed parameters
    set_non_required(fn, imports, data.get('provides') or [])

    # Change defaults when specified
    override_default(fn, imports, data.get('defaults') or {}, lookup_file, "")

    # Make sure parameters are marked as coming from the current file.
    # This is important to make parameter reference resolution work.
    if not name:
        override_filenames(imports, p, fn)
    return (imports, args, script, blueprints)

def parse_blueprint_import(fn: pathlib.Path,
                           data: Dict, name: str, args: ArgTree,
                           lookup_file: LookupFile, prefix: str,
                           parent: Union[Decl, InnerDecl]) -> DeclTree:
    unknown_keys = set(data.keys()) - {'blueprint', 'module',
                                       'defaults', 'namespace'}
    if unknown_keys:
        raise TargetParamError(
            f'Unknown keys "{unknown_keys}" in blueprint import'
            f' "{flatten_name(prefix, name)}" in target "{fn}"')

    # we need below import of simics to ensure later module imports work
    import simics as _
    import importlib
    from blueprints import BlueprintError
    from blueprints.params import get_blueprint_params
    importlib.import_module(data['module'])
    bp = data['blueprint']
    ns = data.get('namespace', '')
    bp_args = dict(args)
    bp_args.update(data.get('defaults') or {})

    def convert_bp_params(params):
        imports = {}
        for (k, p) in params.items():
            if isinstance(p, dict):
                imports[k] = InnerDecl(k, fn, '', 1, prefix,
                                       children=convert_bp_params(p))
            else:
                imports[k] = validate_and_construct_decl(
                    fn, {'type': p.ptype.__name__,
                         'allow_empty': p.allow_empty,
                         'default': p.ptype(p.default)
                         if p.default is not None else p.default,
                         'description': p.desc},
                    k, lookup_file, prefix, parent)
        return InnerDecl(name, fn, '', 1, prefix, children=imports)

    try:
        imports = convert_bp_params(get_blueprint_params(bp, bp_args))
    except BlueprintError as ex:
        raise TargetParamError(ex)

    # Change defaults when specified
    override_default(fn, imports, data.get('defaults') or {}, lookup_file, "")
    return (imports, {'blueprint': bp, 'ns': ns})

def verify_array_size(fn: pathlib.Path, name: str, sibling_decls: DeclTree,
                      prefix: str):
    # name is empty at top level
    if name:
        param_name = parse_array_ns(fn, name)
        if param_name is not None:
            if (param_name not in sibling_decls
                or not (sibling_decls[param_name].type == int
                        and (sibling_decls[param_name].required
                             or sibling_decls[param_name].default))):
                raise TargetParamError(
                    'Array namespace'
                    f'"{flatten_name(prefix, param_name)}"'
                    ' must use required integer parameter as length,'
                    f' in target "{fn}"')
            # Set special validator for array size parameter
            sibling_decls[param_name].validate = validate_array_size

def parse_decl(fn: pathlib.Path, name: str,
               decl: DeclTree, sibling_decls: DeclTree, input_args: ArgTree,
               lookup_file: LookupFile, ignore_blueprints: bool, prefix: str,
               targets: list) -> Tuple[DeclTree, ArgTree, Optional[str], Dict]:
    if name is not None and not name.isascii():
        raise TargetParamError(
            f'Parameter name "{flatten_name(prefix, name)}",'
            f' is not ASCII, in target "{fn}"')

    if 'type' in decl and isinstance(decl['type'], str):
        assert name
        verify_param_name(fn, prefix, name)
        # Simple parameter
        decls = validate_and_construct_decl(
            fn, decl, name, lookup_file, prefix, sibling_decls)
        return (decls, {}, None, {})
    elif 'blueprint' in decl:
        assert name
        verify_param_name(fn, prefix, name)
        if not ignore_blueprints:
            (decls, bp) = parse_blueprint_import(
                fn, decl, name, input_args, lookup_file, prefix, sibling_decls)
            return (decls, {}, None, bp)
        else:
            return (InnerDecl(name, fn, "", 1, prefix), {}, None, {})
    elif 'import' in decl:
        # Import from other script

        if not isinstance(input_args, dict):
            raise TargetParamError(
                f'Cannot set nested parameter "{flatten_name(prefix, name)}",'
                f' to value {input_args}, in target "{fn}"')
        verify_array_size(fn, name, sibling_decls, prefix)
        return parse_import(fn, decl, name, input_args,
                            lookup_file, ignore_blueprints, prefix, targets)
    else:
        if not decl:
            return (InnerDecl(name, fn, "", 1, prefix), {}, None, {})

        sub_decls = InnerDecl(name, fn, decl.pop('description', ''),
                              decl.pop('advanced',
                                       sibling_decls.advanced),
                              prefix)
        if not decl:
            raise TargetParamError(
                'Incomplete declaration in nested parameter'
                f' "{flatten_name(prefix, name)}", in target "{fn}"')

        if not isinstance(input_args, dict):
            raise TargetParamError(
                f'Cannot set nested parameter "{flatten_name(prefix, name)}",'
                f' to value {input_args}, in target "{fn}"')

        verify_array_size(fn, name, sibling_decls, prefix)

        sub_args = {}
        sub_scripts = {}
        sub_blueprints = {}
        for (sub_param_name, sub_decl) in decl.items():
            # PyYAML may have parsed the parameter to an int
            sub_name = str(sub_param_name)
            if not isinstance(sub_decl, dict):
                raise TargetParamError(
                    'Incomplete declaration in nested parameter'
                    f' "{flatten_name(prefix, flatten_name(name, sub_name))}",'
                    f' in target "{fn}"')
            # Complex parameter
            sub_input_args = input_args.get(sub_name, {})
            (parsed_decls, args, script, blueprints) = parse_decl(
                fn, sub_name, sub_decl, sub_decls, sub_input_args,
                lookup_file, ignore_blueprints, flatten_name(prefix, name),
                targets)
            sub_decls[sub_name] = parsed_decls
            if args:
                sub_args[sub_name] = args
            if script:
                sub_scripts[sub_name] = script
            if blueprints:
                sub_blueprints[sub_name] = blueprints
        if len(sub_scripts) > 1:
            raise TargetParamError(
                'Multiple script references found during import parse,'
                f' in target "{fn}"')
        elif sub_scripts:
            script = list(sub_scripts.values())[0]
        else:
            script = None
        return (sub_decls, sub_args, script, sub_blueprints)

def parse_declarations(fn: pathlib.Path, params: DeclTree, input_args: ArgTree,
                       lookup_file: LookupFile,
                       ignore_blueprints: bool,
                       targets: list) -> Tuple[DeclTree, ArgTree, str, Dict]:
    root = InnerDecl("", fn, "", 1, "")
    return parse_decl(fn, "", params, root, input_args, lookup_file,
                      ignore_blueprints, "", targets)

def resolve_parameters(fn: pathlib.Path, decls: DeclTree,
                       args: ArgTree, errors: dict,
                       lookup_file: LookupFile,
                       logger: Callable[[str], None],
                       roots: Optional[Dict] = None, prefix="") -> ArgTree:
    """Resolve arguments <arg>args</arg> against the declaration tree
    <arg>decls</arg> for the script <arg>fn</arg> and return an
    argument tree. Assigned values are removed from <arg>args</args>.
    Throws <tt>Exception</tt> on error (such as invalid type or
    missing value for a required parameter)."""
    values = {}
    imports = {}
    if roots is None:
        roots = {}

    # Remember root point for each file
    # References are relative to root in each file
    roots.setdefault(decls.fn, (decls, values))

    for (name, decl) in decls.items():
        if isinstance(decl, Decl):
            if decl.fn not in roots:
                # This can happen when import: is directly under the root
                root = (decls, values)
            else:
                root = roots[decl.fn]
            if name in args:
                p = args[name]
                try:
                    values[p.name] = p.check(fn, decl,
                                             lookup_file=lookup_file,
                                             prefix=prefix, logger=logger)
                    del args[name]
                except TargetParamError as ex:
                    errors[flatten_name(prefix, name)] = str(ex)
                p.root = root
            else:
                try:
                    if decl.explicit_default:
                        p = Param(name, decl.default, 'default', fn=decl.fn)
                        values[name] = p.check(fn, decl,
                                               lookup_file=lookup_file,
                                               prefix=prefix, logger=logger)
                        p.root = root
                    elif decl.required:
                        raise TargetParamError(
                            f'Missing value for required parameter'
                            f' "{flatten_name(prefix, name)}" in target "{fn}"')
                except TargetParamError as ex:
                    errors[flatten_name(prefix, name)] = str(ex)
        else:
            ns_param = parse_array_ns(fn, name)
            if ns_param:
                imports[name] = (ns_param, decl)
            else:
                values[name] = resolve_parameters(
                    fn, decl, args.get(name, {}), errors, lookup_file, logger,
                    roots=roots, prefix=flatten_name(prefix, name))
                if name in args and not args[name]:
                    del args[name]

    # Extend array declarations
    for (ns, (ns_param, sub_decls)) in imports.items():
        # Array index may be unset if it had validation errors
        # Ignore the whole sub-tree in that case
        if ns_param in values:
            for i in range(values[ns_param].value):
                val_ns = ns.replace(f'[{ns_param}]', f'[{i}]')
                decls[val_ns] = copy.deepcopy(sub_decls)
                values[val_ns] = resolve_parameters(
                    fn, decls[val_ns], args.pop(val_ns, {}),
                    errors, lookup_file,
                    logger, roots=roots, prefix=flatten_name(prefix, val_ns))
            del decls[ns]
    return values

def lookup_from_flat(tree, flat_name):
    cur = tree
    parts = flat_name.split(separator)
    for k in parts:
        if k in cur:
            cur = cur[k]
        else:
            # Parameter unassigned, retain string for later lookup
            return flat_name
    return cur

def lookup_param(fn: pathlib.Path, decls: DeclTree,
                 args: ArgTree, flat_name: Union[Param,str]) -> Param:
    decl = decls
    # If parameter is already assigned, we have a reference Param object
    if isinstance(flat_name, Param):
        return flat_name
    parts = flat_name.split(separator)
    for k in parts:
        if k not in decl:
            raise TargetParamError(f"Unknown parameter name {flat_name}"
                                   f" used in reference, in target {fn}")
        decl = decl[k]
    if not isinstance(decl, Decl):
        raise TargetParamError(f"Reference to parameter {flat_name}"
                               f" which is not a leaf, in target {fn}")

    # Parameter exists, but may be unassigned
    return lookup_from_flat(args, flat_name)

# Resolve references between parameters in the tree
def resolve_param_refs(fn: pathlib.Path, args: ArgTree, prefix=""):
    for (name, param) in args.items():
        if isinstance(param, Param):
            if param.is_ref:
                param.check(fn, param.decl,
                            lookup_ref=lambda p: lookup_param(
                                fn, *param.root, p),
                            prefix=prefix)
        else:
            resolve_param_refs(fn, param, prefix=flatten_name(prefix, name))

# Check parameter tree for cycles
def check_param_cycles(args: ArgTree):
    for (name, param) in args.items():
        if isinstance(param, Param):
            param.check_cycles()
        else:
            check_param_cycles(param)

def resolve_blueprints(fn: pathlib.Path,
                       blueprints: Dict, values: ArgTree,
                       new_builder=False) -> Dict:
    output = {}
    if 'blueprint' in blueprints:
        output = dict(blueprints)
        output['use-new-builder'] = new_builder
    else:
        for (ns, bp) in blueprints.items():
            ns_param = parse_array_ns(fn, ns)
            if ns_param:
                for i in range(values[ns_param].value):
                    val_ns = ns.replace(f'[{ns_param}]', f'[{i}]')
                    output[val_ns] = resolve_blueprints(fn, bp, values[val_ns],
                                                        new_builder=True)
            else:
                output[ns] = resolve_blueprints(fn, bp, values[ns],
                                                new_builder=new_builder)
    return output

def save_parameters(tree: ArgTree, user_only=True, resolve_refs=True) -> Dict:
    """Return tree of argument values from the argument tree
    <arg>tree</arg>, including only those arguments that were set
    explicitly by the user."""
    output = {}
    for (k, v) in tree.items():
        if isinstance(v, Param):
            if ((v.decl is None or not v.decl.output)
                and (v.state == 'user' or not user_only)):
                output[k] = (v.get_value() if resolve_refs
                             else v.get_value_weak_ref())
        elif not isinstance(v, Decl):
            data = save_parameters(v, user_only=user_only,
                                   resolve_refs=resolve_refs)
            if data:
                output[k] = data
    return output

def dump_arguments(tree: ArgTree) -> Dict:
    return save_parameters(tree, user_only=False, resolve_refs=False)

def filter_parameters(decls: DeclTree, tree: ArgTree, substr: str="",
                      only_changed=False, include_outputs=True,
                      advanced=1, include_refs=True) -> Dict:
    return filter_substring(substr, collect_parameters(
        decls, tree, only_changed=only_changed, include_outputs=include_outputs,
        advanced=advanced, include_refs=include_refs))

def collect_parameters(
        decls: DeclTree, tree: ArgTree, only_changed=False,
        include_outputs=True, advanced=1, include_refs=True) -> Dict:
    output = {}
    for (k, v) in tree.items():
        if isinstance(v, Param):
            if ((advanced is None or decls[k].advanced <= advanced)
                and (include_outputs or not decls[k].output)
                and (not only_changed or v.state =='user')
                and (include_refs or not v.is_ref)):
                output[k] = v
        else:
            if decls:
                ns = collect_parameters(
                    decls[k], v, only_changed=only_changed,
                    include_outputs=include_outputs, advanced=advanced,
                    include_refs=include_refs)
            else:
                # At top level, no declarations
                ns = collect_parameters(
                    decls, v, only_changed=only_changed,
                    include_outputs=include_outputs, advanced=advanced,
                    include_refs=include_refs)
            if ns:
                output[k] = ns
    for (k, v) in decls.items():
        if (k not in tree and isinstance(v, Decl) and not only_changed
            and (advanced is None or v.advanced <= advanced)
            and (include_outputs or not v.output)):
            output[k] = v
    return output

def filter_declarations(
        decls: DeclTree, substr: str="",
        include_outputs=True, advanced=1) -> Dict:
    return filter_substring(substr, collect_declarations(
        decls, include_outputs=include_outputs, advanced=advanced))

def collect_declarations(
        decls: DeclTree, include_outputs=True, advanced=1) -> Dict:
    output = {}
    for (k, v) in decls.items():
        if isinstance(v, Decl):
            if ((advanced is None or v.advanced <= advanced)
                and (include_outputs or not v.output)):
                output[k] = v
        else:
            ns = collect_declarations(
                v, include_outputs=include_outputs, advanced=advanced)
            if ns:
                output[k] = ns
    return output

def filter_substring(substr: str, tree: Dict) -> Dict:
    """Returns a dictionary containing only paths in the tree that contains the
    specified substring."""
    if not substr:
        return dict(tree)
    result = {}
    for (key, value) in flatten_params(tree).items():
        if substr not in key:
            continue
        set_flattened_param(result, key, value)
    return result

def dump_parameters(decls: DeclTree, tree: ArgTree,
                    include_unassigned=True) -> Dict:
    """Return dump tree of the argument tree <arg>tree</arg>,
    corresponding to the declaration tree <arg>decls</arg>, i.e. a
    tree with the output of <fun>dump</fun> for each
    <class>Param</class> leaf node. For unassigned parameters a
    similar dump structure is added. """
    output = {}
    for (k, v) in tree.items():
        if isinstance(v, Param):
            output[k] = v.dump()
        elif isinstance(v, Decl):
            if include_unassigned and k not in output:
                output[k] = {'state': '<unassigned>'}
        else:
            if decls:
                ns = dump_parameters(decls[k], v)
            else:
                # At top level, no declarations
                ns = dump_parameters(decls, v)
            if ns:
                output[k] = ns
    if include_unassigned:
        for (k, v) in decls.items():
            if k not in output and isinstance(v, Decl):
                output[k] = {'state': '<unassigned>'}
    return output

def dump_declarations(decls: DeclTree, advanced: Optional[int],
                      prune=True) -> Dict:
    """Return dump tree of the declaration tree <arg>decls</arg>, i.e.
    a tree with the output of <fun>dump</fun> for each
    <class>Decl</class> leaf node."""
    assert isinstance(decls, dict) or isinstance(decls, InnerDecl)
    if isinstance(decls, dict):
        decls = InnerDecl('', '', '', advanced, '',
                          children=decls)
    return decls.dump(advanced, prune)

def advanced_levels(decls: DeclTree) -> list:
    if isinstance(decls, Decl):
        return [decls.advanced]
    else:
        return list(set.union(*[set(advanced_levels(v))
                                for v in decls.values()])) if decls else []

def parse_arguments(fn: pathlib.Path, name: str,
                    args: Dict[str, str], input_args: ArgTree,
                    lookup_file: LookupFile,
                    ignore_blueprints: bool,
                    targets: list) -> Tuple[DeclTree, ArgTree, str, Dict]:
    if 'import' in args:
        import_fn = args['import']
        try:
            full_fn = lookup_file(str(import_fn))
        except ValueError:
            full_fn = None
        if not import_fn:
            raise TargetParamError(
                f'Imported file "{import_fn}" cannot be found'
                f' in target "{fn}"')
        p = pathlib.Path(full_fn)
        data = parse_script(p, lookup_file_from_path(p, lookup_file), targets,
                            input_args, ignore_blueprints)
        decls = data['params']
        output = data['args']
        script = data['code']['file'] if data['code'] else None
        blueprints = data['blueprints']
        del args['import']
    else:
        decls = InnerDecl(name, fn, '', 1, '')
        output = {}
        script = None
        blueprints = {}

    for (key, value) in args.items():
        # Complex parameter or import
        if isinstance(value, dict):
            (import_decls, import_output, import_script,
             import_blueprints) = parse_arguments(
                 fn, key, value, input_args, lookup_file, ignore_blueprints,
                 targets)
            if import_decls:
                decls[key] = import_decls
            if import_output:
                # Arguments specified in this script, which could come from
                # nested imports, override those coming from an import at
                # the top level of the script.
                output[key] = merge_args(output.get(key, {}), import_output)
            if not script:
                script = import_script
            blueprints.update(import_blueprints)
        else:
            # Single parameter
            output[key] = Param(key, value, 'default', fn=str(fn))

    return (decls, output, script, blueprints)

def parse_script_code(
        fn: pathlib.Path, # current script/preset file name
        code: str,        # script inlined code
        preset_args: ArgTree,
        code_type: str,    # code type specifier, from 'code-type' YAML key
        code_cmd: str,     # code given in YAML, from 'cmd' YAML key
        script: str,      # file name of external code, from 'script' YAML key
        pre_script: str,  # file name of external pre-init code,
                          # from 'pre-init' YAML key
        line: int,        # line number where inlined code starts
        target: str,      # file name of actual script, from 'target' YAML key
        target_list: list, # list of available targets
        lookup_file: LookupFile) -> Tuple[str, str, str, str, int,
                                          DeclTree, ArgTree, Dict]:
    # There are three cases:
    #
    # 1. The current script points to another script via the 'targets' key.
    #    This means that it is a preset file and must not contain any code,
    #    hence the inlined code must be empty and there must be no separate
    #    code file. In this case declarations and arguments are also picked up
    #    from the referenced script.
    # 2. The current script contains code: inlined code, code given as a
    #    string in the YAML part, or code in an external file. The code type
    #    must then be set.
    # 3. The current script is a "pure" preset with only argument values.

    # Are we in case 2?
    if script or code or code_cmd:
        if not code_type:
            raise TargetParamError('Script code but no code type'
                                   f' specifier, in target "{fn}"')

        # Obtain code text
        if script:
            # Code is in another file
            if code or code_cmd:
                raise TargetParamError(f'Cannot have both inline code and code'
                                       f' file specifiers, in target "{fn}"')
            try:
                script_file = lookup_file(script)
            except ValueError:
                script_file = ""
            p = pathlib.Path(script_file)
            if not p.is_file():
                msg = f'Non-existent code file "{script}", in target "{fn}".'
                if not p.is_absolute():
                    msg += f" Did you mean %script%/{script}?"
                raise TargetParamError(msg)
            code = pathlib.Path(script_file).read_text(encoding='utf-8')
            line = 0
            script = script_file
        elif code_cmd:
            if code:
                raise TargetParamError(f'Cannot have inlined code and code'
                                       f' command specified, in target "{fn}"')
            script = str(fn)
            code = code_cmd
            line = 0
        else:
            # Code is inlined
            script = str(fn)

        if pre_script:
            try:
                pre_script_file = lookup_file(pre_script)
            except ValueError:
                pre_script_file = ""
            if not pathlib.Path(pre_script_file).is_file():
                raise TargetParamError(f'Non-existent code file "{pre_script}",'
                                       f' in target "{fn}"')
            pre_script = pre_script_file

        # Only presets can point to another script
        if target:
            raise TargetParamError(f'Cannot have both code and target'
                                   f' specifiers, in target "{fn}"')
        decls = InnerDecl('', fn, '', 1, '')
        args = {}
        blueprints = {}
    else:
        if pre_script:
            raise TargetParamError('Cannot have code in presets,'
                                   f' in target "{fn}"')

        # Are we in case 1?
        if target:
            from .targets import get_script_file
            script_file = get_script_file(target, target_list)
            if script_file is None:
                try:
                    script_file = lookup_file(target)
                except ValueError:
                    script_file = ""
            if not script_file:
                raise TargetParamError(
                    f'Referenced target "{target}" cannot be found'
                    f' in target "{fn}"')
            ret = parse_script(pathlib.Path(script_file), lookup_file,
                               target_list, preset_args)
            if ret and ret['code']:
                code = ret['code']['text']
                code_type = ret['code']['type']
                script = ret['code']['file']
                pre_script = ret['code']['pre-init']
                line = ret['code']['line']
                decls = ret['params']
                args = ret['args']
                blueprints = ret['blueprints']
            else:
                raise TargetParamError(f'No code found in target,'
                                       f' in target "{fn}"')
        else:
            return ("", "", "", "", None,
                    InnerDecl('', fn, '', 1, ''), {}, {})

    return (code, code_type, script, pre_script, line, decls, args, blueprints)


def merge_args(args: ArgTree, override: ArgTree) -> ArgTree:
    output = dict(args)
    for (k, v) in override.items():
        if k in args and isinstance(args[k], dict):
            assert isinstance(v, dict)
            output[k] = merge_args(args[k], v)
        else:
            output[k] = v
    return output

def parse_script_params(
        fn: pathlib.Path, data: Dict[str, str], input_args: ArgTree,
        lookup_file: LookupFile,
        ignore_blueprints: bool,
        targets: list) -> Tuple[DeclTree, ArgTree, str, str, Dict]:
    desc = data.get('description') or ""
    # Parse declaration tree, also obtain any arguments from imports
    (decls, args, script, blueprints) = parse_declarations(
        fn, data.get("params") or {}, input_args, lookup_file,
        ignore_blueprints, targets)
    # Parse argument tree, also obtain declarations from imports
    (preset_decls, preset_args,
     preset_script, preset_blueprints) = parse_arguments(
         fn, '', data.get("args") or {}, input_args, lookup_file,
         ignore_blueprints, targets)

    # Must not define a parameter more than once
    clashes = set(decls.keys()) & set(preset_decls.keys())
    if clashes:
        raise TargetParamError('Duplicate parameter definitions'
                               f' in target "{fn}": {clashes}')

    # No overrides since no clashes
    decls.update(preset_decls)
    # Arguments from 'args' section at top script overrides overrides 'args'
    # sections implicitly imported args in scripts imported from 'params'
    # sections.
    args = merge_args(args, preset_args)
    # Target script referenced in arguments take precedence
    if preset_script:
        script = preset_script
    # Target referenced in current script take precedence
    if 'target' in data:
        script = data['target']

    blueprints.update(preset_blueprints)
    return (decls, args, script, desc, blueprints)

# Convert command line parameters to an argument tre with Params objects
def parse_cmdline_args(cmdline_args: ArgTree) -> ArgTree:
    output = {}
    for (k, v) in cmdline_args.items():
        if isinstance(v, dict):
            output[k] = parse_cmdline_args(v)
        else:
            # Providing a file name is optional
            if isinstance(v, tuple):
                (val, fn) = v
            else:
                val = v
                fn = "<cmdline>"
            output[k] = Param(k, val, 'user', fn=fn)
    return output

def parse_script(fn: Union[pathlib.Path, str],
                 lookup: LookupFile,
                 targets: list,
                 cmdline_args: ArgTree = None,
                 ignore_blueprints: bool = False) -> Optional[Dict]:
    """Script parser entry point. Parses file or string <arg>fn</arg>
    and returns script meta-data, or <tt>None</tt> if it is not a new style
    script. Throws <tt>Exception</tt> on error.

    The <arg>lookup_file</arg> function is used on all file
    references (import/script/target)."""

    if cmdline_args is None:
        input_args = {}
    else:
        input_args = dict(cmdline_args)

    default_code_type = ''

    if isinstance(fn, str):
        # Used when parsing preset given as string on command line
        (data, code, line) = parse_yaml_string("<preset>", fn)
    else:
        (data, code, line) = parse_yaml_file(fn)

        # Promote Python code for new style targets.
        # Look at separate script code file if it exists.
        if data.get('script', ''):
            script_file = pathlib.Path(data.get('script', ''))
        else:
            script_file = fn
        if script_file.suffix in ['.py', '.yml']:
            default_code_type = 'py'
        elif script_file.suffix in ['.simics', '.include']:
            default_code_type = 'simics'

    if isinstance(fn, pathlib.Path):
        lookup_file = lookup_file_from_path(fn.absolute(), lookup)
    else:
        lookup_file = lookup

    # Parse declaration and argument tree from this script only
    # Also obtain highest level target script name
    (decls, args, script, desc, blueprints) = parse_script_params(
        fn, data, input_args, lookup_file, ignore_blueprints, targets)

    # Both args from preset and from command line should influence
    # parsing of referenced target
    code_args = merge_args(dump_arguments(args), input_args)

    # Obtain code from current script or referenced script
    # Also obtain any declaration and argument tree from referenced script
    (code, code_type, code_file, pre_init_file, line,
     target_decls, target_args, target_blueprints) = parse_script_code(
         fn, code, code_args, data.get('code-type', default_code_type),
         data.get('cmd', ''), data.get('script', ''),
         data.get('pre-init', ''),
         line, script, targets, lookup_file)

    # Clashes in parameter names are possible, e.g. if the target is a preset
    # importing another preset which references another target.
    # But the parameters are then always the same.
    clashes = set(decls.keys()) & set(target_decls.keys())
    if clashes:
        left = dump_declarations(decls, None)
        right = dump_declarations(target_decls, None)
        left_bad = {k: left[k] for k in clashes}
        right_bad = {k: right[k] for k in clashes}
        if left_bad != right_bad:
            raise TargetParamError(
                'Duplicate incompatible parameter definitions'
                f' in target "{fn}": {left_bad} != {right_bad}')

    # Blueprints may be listed directly at the top level, e.g. if they have
    # no parameters to import
    direct_blueprints = data.get('blueprints', {})

    blueprints.update(target_blueprints)
    blueprints.update(direct_blueprints)

    # No overrides since no clashes
    decls.update(target_decls)
    decls.fn = target_decls.fn

    # 'args' section from current script overrides any arguments obtained
    # in script referenced by 'target'
    args = merge_args(target_args, args)
    # Command line parameters have highest priority
    args = merge_args(args, parse_cmdline_args(input_args))

    code_data = {
        'text': code,
        'type': code_type,
        'file': code_file,
        'pre-init': pre_init_file,
        'line': line,
    } if code else None
    return {'code': code_data,
            'params': decls,
            'args': args,
            'desc': desc,
            'blueprints': blueprints}

def write_parameters(args: Dict, script: str, f: TextIO):
    """Export preset file into <arg>f</arg>, with given arguments
    <arg>args</arg> and target pointer <arg>script</arg>."""
    data = {'args': args}
    if script:
        data['target'] = script
    assert f is not None
    print("%YAML 1.2\n---\n", file=f)
    write_yaml(data, f)
    print("...\n", file=f)

def init():
    """Initialise script parameter functionality."""
    # Export YAML strings in a nice format
    yaml.add_representer(str, str_presenter)
