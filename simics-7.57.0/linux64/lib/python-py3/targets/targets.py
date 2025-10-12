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


import itertools
import pathlib
from . import script_params
from typing import Dict, List, Tuple, Callable, Optional
import re
from pathlib import Path

# Extend lookup_file to handle local project as well
def proj_lookup_file(lookup_file, proj: Path, f: str, required: bool,
                     translate: bool) -> str:
    proj_path = proj / f
    if proj_path.is_file():
        return proj_path if translate else f
    else:
        path = lookup_file(f)
        if required and not path:
            raise ValueError(f"File lookup failed: '{f}'")
        return path if translate else f

script_re = re.compile(r"^%script%")
simics_re = re.compile(r"^%simics%/")

# Extend lookup_file to handle %script% and %simics%
# For use with script_params.parse_script
def get_lookup_wrapper(lookup_file, proj: Path, file_lookup: bool):
    def lookup_wrapper(f: str, **kwargs) -> str:
        cur_path = kwargs.get('cur_path', None)
        keep_ref = kwargs.get('keep_simics_ref', False)
        if script_re.match(f):
            if cur_path is None:
                raise ValueError("%script% used outside script")

            lookup = script_re.sub(cur_path.replace('\\', '\\\\'), f)
            # Always convert %script% marker, necessary to open the file.
            assert Path(lookup).is_absolute()
            found = proj_lookup_file(lookup_file, proj, lookup, file_lookup,
                                     True)
        elif simics_re.match(f):
            lookup = simics_re.sub("", f)
            if lookup:
                found = proj_lookup_file(lookup_file, proj, lookup, file_lookup,
                                         not keep_ref)
            else:
                if file_lookup:
                    raise ValueError(f"File lookup failed: '{f}'")
                else:
                    found = ""
            if found and keep_ref:
                found = f
        else:
            # Relative or absolute path, do not convert relative to absolute.
            found = proj_lookup_file(lookup_file, proj, f, file_lookup,
                                     False)
        # Return empty string instead of None
        return found if found else ""
    return lookup_wrapper

# Return target name for launch script file
def target_name(script_file: pathlib.Path) -> str:
    t = script_file
    while t.suffix:
        t = t.with_suffix('')
    return f"{t.parent.name}/{t.stem}"

# targets is modified in-place
def get_targets_from_path(targets: Dict[str, Dict],
                          pkg_path: str, pkg_name: str,
                          name: str) -> None:
    # Target naming convention
    targets_path = pkg_path / 'targets'
    scripts = itertools.chain(targets_path.glob(f'*/*.{name}.yml'),
                              targets_path.glob(f'*/*.{name}.simicsy'),
                              targets_path.glob(f'*/*.{name}.pyy'))
    for s in sorted(scripts, key=target_name):
        # Target name
        t = target_name(s)
        if t not in targets:
            targets[t] = {
                'script': s,
                'pkg': pkg_name,
            }

def get_targets_from_pkgs(pkgs: List[Tuple[str, str]],
                          name: str) -> Dict[str, Dict]:
    targets = {}
    for p in pkgs:
        get_targets_from_path(targets, pathlib.Path(p[1]), p[0], name)
    return targets

def get_preset_list(proj_path: str,
                    prio_pkgs: List[Tuple[str, str]],
                    pkgs: List[Tuple[str, str]],
                    lookup_file: Callable[[str], str]) -> Dict[str, Dict]:
    prio_presets = get_targets_from_pkgs(prio_pkgs, "preset")
    presets = get_targets_from_pkgs(pkgs, "preset")
    presets.update(prio_presets)

    if proj_path:
        # Project presets override packages
        proj_presets = {}
        get_targets_from_path(proj_presets, pathlib.Path(proj_path),
                              '<project>', "preset")
        presets.update(proj_presets)
    return dict(sorted(presets.items()))

def construct_target_args(presets, cmdline_args, lookup_file, target_list):
    args = {}

    # Take arguments from presets, later ones override earlier ones
    for entry in presets:
        (fn, ns) = entry
        data = script_params.parse_script(fn, lookup_file, target_list)
        # arg values are Param objects, but here we must have their values only
        vals = {k: v.value for (k, v) in script_params.flatten_params(
            data['args'], ns).items()}
        args.update({k: (v, str(fn)) for (k, v) in vals.items()})

    # Explicitly provided arguments override preset arguments
    args.update({k: (v, "<cmdline>")
                 for (k, v) in cmdline_args.items()})
    return args

def get_target_params(
        target_name: str, proj_path: Path, prio_pkgs: List[Tuple[str, str]],
        pkgs: List[Tuple[str, str]], input_presets: List[Tuple[str, str]],
        lookup_file: Callable[[str], str], cmdline_args: Dict,
        substr: str, advanced: Optional[int],
        only_changed: bool, include_outputs: bool,
        file_lookup: bool,
        include_refs: bool) -> Optional[Tuple[Dict, str, Dict, Dict]]:
    target_lookup_file = get_lookup_wrapper(lookup_file, proj_path, False)
    targets = get_target_list(proj_path, prio_pkgs, pkgs, target_lookup_file)
    preset_list = get_preset_list(proj_path, prio_pkgs, pkgs,
                                  target_lookup_file)

    # Lookup preset file names
    presets = []
    for (p, n) in input_presets:
        f = Path(p)
        if not f.is_file():
            f = get_script_file(p, preset_list)
            if not (f is not None and f.is_file()):
                return None
        presets.append([Path(f), n])

    # Construct target input arguments from presets and explicit args
    input_args = construct_target_args(
        presets,
        script_params.flatten_params(cmdline_args),
        target_lookup_file, targets)

    script = Path(target_name)
    if script.is_file():
        script = script.resolve()
    elif target_name in targets:
        script = targets[target_name]['script']
    else:
        script = None

    if script:
        data = script_params.parse_script(
            script, target_lookup_file, targets,
            script_params.unflatten_params(input_args))
        decls = data['params']
        args = data['args']
        errors = {}
        resolved = script_params.resolve_parameters(
            script, decls, args, errors,
            get_lookup_wrapper(lookup_file, proj_path, file_lookup), None)
        script_params.resolve_param_refs(script, resolved)
        script_params.check_param_cycles(resolved)
        tree = script_params.filter_parameters(
            decls, resolved, substr=substr, only_changed=only_changed,
            include_outputs=include_outputs, advanced=advanced,
            include_refs=include_refs)
        decls = script_params.filter_declarations(
            decls, substr=substr, include_outputs=include_outputs,
            advanced=advanced)
        return (decls, data['desc'], tree, args, errors)
    else:
        return None

def get_target_list(proj_path: str,
                    prio_pkgs: List[Tuple[str, str]],
                    pkgs: List[Tuple[str, str]],
                    lookup_file: Callable[[str], str]) -> Dict[str, Dict]:
    prio_targets = get_targets_from_pkgs(prio_pkgs, "target")
    targets = get_targets_from_pkgs(pkgs, "target")

    targets.update(prio_targets)

    if proj_path:
        # Project targets override packages
        proj_targets = {}
        proj_path = pathlib.Path(proj_path)
        get_targets_from_path(proj_targets, proj_path, '<project>', 'target')
        targets.update(proj_targets)

        # Include saved targets
        for f in proj_path.iterdir():
            script_file = f / 'target'
            if f.is_dir() and script_file.is_file():
                data = script_params.parse_script(
                    script_file, get_lookup_wrapper(lookup_file, proj_path,
                                                    False), targets)
                if data:
                    t = f.stem
                    targets[t] = {
                        'script': script_file,
                        'pkg': '<project>',
                    }

    return dict(sorted(targets.items()))

# Return script file for target
def get_script_file(target: str,
                    targets: Dict[str, Dict]) -> Optional[pathlib.Path]:
    if target in targets:
        return targets[target]['script']
    else:
        return None
