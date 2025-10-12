# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# common functions for flash testing

from simics import *
from configuration import *
from flash_memory import *
from cli_impl import simenv

def make_flash_configuration(model, interleave, bus_width, name = "flash",
                             big_endian = 0):
    (flash_objects, flash_size) = flash_create_memory(name, model,
                                                      interleave, bus_width,
                                                      big_endian = big_endian)
    mem = pre_conf_object("mem" if name == "flash" else name + "_mem",
                          "memory-space")
    if hasattr(simenv, 'no_target'):
        target = None
    else:
        target = flash_objects[name + '_ram']
    mem.map = [[0x0, flash_objects[name], 0, 0, flash_size, target, 0, 0]]
    flash_objects['mem'] = mem
    SIM_add_configuration(flash_objects, None)

def make_data(value, size):
    data_value = ()
    for i in range(size):
        data_value = data_value + ((value >> (i*8)) & 0xFF,)
    return data_value

def make_list(value, size):
    list_value = []
    for i in range(size):
        list_value.append((value >> (i*8)) & 0xFF)
    return list_value

def extract_data(value):
    return sum(value[i] << (i * 8) for i in range(len(value)))

def setmem(address, value, size, inquiry_access=False):
    conf.mem.iface.memory_space.write(conf.mem, address,
                                      make_data(value, size), inquiry_access)

def set8(address, value):
    setmem(address, value, 1)

def set16(address, value):
    setmem(address, value, 2)

def set32(address, value):
    setmem(address, value, 4)

def set64(address, value):
    setmem(address, value, 8)

def fill(address, end, byte_value):
    while address < end:
        chunk = min(4096, end - address)
        conf.mem.iface.memory_space.write(conf.sim, address,
                                          (byte_value,)*chunk, True)
        address += chunk

def get(address, size, inquiry_access=False):
    return extract_data(conf.mem.iface.memory_space.read(
        conf.mem,address, size, inquiry_access))

def get8(address):
    return get(address, 1)

def get16(address):
    return get(address, 2)

def get32(address):
    return get(address, 4)

def get64(address):
    return get(address, 8)

class TestFailure(Exception):
    pass

def expect(string, a, b):
    if a != b:
        raise TestFailure("%s %s %s %s %s"%(string, "got", a, "and not", b))

def expect_hex(string, a, b):
    if a != b:
        raise TestFailure("%s %s %s"%(string, "got 0x%x"%a, "and not 0x%x"%b))
