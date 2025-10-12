# © 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import simics
import conf
from pathlib import Path
from simicsutils.host import so_suffix

def create_sample_device_with_external_lib(name = None):
    '''Create a new sample_device_with_external_lib object'''
    mod_src_base = Path(__file__).resolve().parent.parent
    ext_lib_loc = (mod_src_base / 'technically' / 'arbitrary' / 'path' /
                   'on' / 'disk' / 'lib')
    if ext_lib_loc.is_dir():
        ext_lib_file = ext_lib_loc / f'libexternal_lib{so_suffix()}'
        if ext_lib_file.is_file():
            #delete original lib to ensure we pick it up from sys/lib
            simics.SIM_log_info(1, conf.sim, 0, 'External lib found. Deleting.')
            ext_lib_file.unlink()
        else:
            simics.SIM_log_info(
                1, conf.sim, 0,
                'External lib not found. Should only be in sys/lib then.')
    else:
        simics.SIM_log_info(1, conf.sim, 0,
                            'Path to external lib could not be found.')

    sample_device_with_external_lib = simics.pre_conf_object(
        name, 'sample_device_with_external_lib')
    simics.SIM_add_configuration([sample_device_with_external_lib], None)
    return simics.SIM_get_object(sample_device_with_external_lib.name)
