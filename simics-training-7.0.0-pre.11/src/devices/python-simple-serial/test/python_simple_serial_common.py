# © 2020 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# Unit test for the Python simple serial port
# Common code that sets up the required environment
#
#   serial device
#   memory map
#   ...
#

import stest
import pyobj
import dev_util
import conf
import simics


## Create objects
def create_python_simple_serial():
    py_dev = simics.pre_conf_object('pyart', 'python_simple_serial')
    phys_mem = simics.pre_conf_object('phys_mem', 'memory-space')
    phys_mem.attr.map = [ [0x0000, py_dev, 0, 0, 0x10] ]

    ## A clock
    clock = simics.pre_conf_object(
        'clock',
        'clock',
        freq_mhz=1000)
    py_dev.attr.queue = clock

    ## Add objects
    simics.SIM_add_configuration([clock, py_dev, phys_mem], None)

    ## Return objects in a list
    devobj = simics.SIM_get_object(py_dev.name)
    memobj = simics.SIM_get_object(phys_mem.name)
    clockobj = simics.SIM_get_object(clock.name)
    return [devobj, memobj, clockobj]
