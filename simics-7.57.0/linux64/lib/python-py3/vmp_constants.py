# © 2025 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

# Process VMP headers for constants

from pathlib import Path
import re
from typing import Callable, Optional, Iterable
import simicsutils


def get_vmxmon_root() -> Path:
    return Path(simicsutils.internal.simics_base()) / "vmxmon"


def match_define(line) -> Optional[re.Match]:
    return re.match(r"#define\s+(\w+)\s+(\d+)", line)


def pair_from_match(m: Optional[re.Match]) -> tuple[int, str]:
    return (int(m.group(2)), m.group(1)) if m else None


def is_interesting(ignored: set[str]) -> Callable[tuple[int, str], bool]:
    def apply(x: tuple[int, str]) -> bool:
        return x and (x[1] not in ignored)
    return apply


# Markers for ranges of codes should be skipped because they do not represent
# usable symbols
ignored_vmret_symbols = {'VMRET_INST_EXIT_RANGE_START',
                         'VMRET_INST_EXIT_RANGE_END', 'VMRET_COUNT'}
ignored_vmexit_symbols = {'VMEXIT_COUNT'}
ignored_perfctr_symbols = {'PERFCTR_COUNT'}


def build_mapping(lines: Iterable[str], predicate: Callable) -> dict[int, str]:
    regex_matches = (match_define(line) for line in lines)
    matches = (pair_from_match(match) for match in regex_matches)
    pairs_without_ignored = filter(predicate, matches)

    return dict(pairs_without_ignored)


def vmp_return_codes() -> dict[int, str]:
    root = get_vmxmon_root()

    vmp_exit_codes_h = root / "module/include/vmp-exit-codes.h"
    with open(vmp_exit_codes_h, encoding="utf-8") as f:
        result = build_mapping(f, is_interesting(ignored_vmret_symbols))
    return result


def vm_exit_codes() -> dict[int, str]:
    root = get_vmxmon_root()

    vm_exit_codes_h = root / "module/common/vm-exit-codes.h"
    with open(vm_exit_codes_h, encoding="utf-8") as f:
        result = build_mapping(f, is_interesting(ignored_vmexit_symbols))
    return result


def perfctr_codes(hardcoded_mapping: dict[int, str]) -> dict[int, str]:
    root = get_vmxmon_root()

    vm_exit_codes_h = root / "module/common/perfctr.h"
    with open(vm_exit_codes_h, encoding="utf-8") as f:
        generated_mapping = build_mapping(
            f, is_interesting(ignored_perfctr_symbols))

    result = dict((code, hardcoded_mapping[code]) if code in hardcoded_mapping
                  else (code, symbol)
                  for code, symbol in generated_mapping.items())
    return result
