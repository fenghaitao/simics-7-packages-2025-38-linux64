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

import builtins
import sys
import importlib.util as iutil
from pathlib import Path

def run_smbus_test(filename):
    sys.path.append(str((Path(filename).parent.parent / 'smbus').resolve()))
    actual_test = (Path(filename).parent.parent / 'smbus' / Path(filename).name)
    mname = Path(filename).stem.replace('-','_')
    mspec = iutil.spec_from_file_location(mname, actual_test.resolve())
    mod = iutil.module_from_spec(mspec)

    builtins.ich10_smbus_use_i2c_v2 = True
    mspec.loader.exec_module(mod)
