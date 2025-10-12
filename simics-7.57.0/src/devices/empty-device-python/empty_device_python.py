# © 2010 Intel Corporation

# empty_device_python.py - sample code for a Simics device

# Use this file as a skeleton for your own device implementation in Python.

# Tie code to specific API, simplifying upgrade to new major version
import simics_7_api as simics
import cli

class empty_device_python:
    # Instance constructor
    def __init__(self, obj):
        # Keep track of the associated configuration object
        self.obj = obj

        # Initialize instance variables
        self.value = 0

def init(obj):
    return empty_device_python(obj)

def finalize(obj):
    pass

# operation() is called whenever a memory access (read/write)
# is performed to an address mapped by the empty-device-python object.

def operation(obj, mop, info):
    # offset in the memory mapping (unused here)
    # offset = SIM_get_mem_op_physical_address(mop) + info.start - info.base

    # find instance data
    inst = obj.object_data

    if simics.SIM_mem_op_is_read(mop):
        simics.SIM_set_mem_op_value_le(mop, inst.value)
    else:
        inst.value = simics.SIM_get_mem_op_value_le(mop)
    return simics.Sim_PE_No_Exception

# Attribute get/set functions

def get_value(obj):
    return obj.object_data.value

def set_value(obj, val):
    obj.object_data.value = val
    return simics.Sim_Set_Ok

# info command prints static information
def get_info(obj):
    return []

# status command prints dynamic information
def get_status(obj):
    return [("Registers",
             [("Value", obj.value)])]

# Initialization code run when module is loaded
def register_class(class_name):
    class_data = simics.class_info_t(
        init = init,
        finalize = finalize,
        short_desc = "a Python device template",
        description = """\
This device does nothing useful, but can be used as a starting point
when writing Simics devices in Python.
""")
    py_class = simics.SIM_create_class(class_name, class_data)

    simics.SIM_register_attribute(py_class, "value",
                                  get_value,
                                  set_value,
                                  simics.Sim_Attr_Optional,
                                  "i",
                                  "The <i>value</i> register.")

    io_iface = simics.io_memory_interface_t(operation = operation)
    simics.SIM_register_interface(py_class, simics.IO_MEMORY_INTERFACE,
                                  io_iface)

    cli.new_info_command(class_name, get_info)
    cli.new_status_command(class_name, get_status)
