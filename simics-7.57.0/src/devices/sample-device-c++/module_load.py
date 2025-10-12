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


import cli

#
# ------------------------ info -----------------------
#

def get_empty_info(obj):
    return []

def get_sample_info(obj):
    return [(None,
             [("Ports", [p for p in obj.port.sample]),
              ("Banks", [b for b in obj.bank.b])])]

def get_sample_bank_info(obj):
    return [(None,
             [("Banks", [b for b in obj.bank.b])])]

cli.new_info_command('sample_device_cxx_attribute_class_attribute', get_empty_info)
cli.new_info_command('sample_device_cxx_attribute_class_member_method', get_empty_info)
cli.new_info_command('sample_device_cxx_attribute_class_member_variable',
                     get_empty_info)
cli.new_info_command('sample_device_cxx_attribute_custom_method', get_empty_info)
cli.new_info_command('sample_device_cxx_attribute_global_method', get_empty_info)
cli.new_info_command('sample_device_cxx_attribute_nested_stl_container', get_empty_info)
cli.new_info_command('sample_device_cxx_attribute_pseudo', get_empty_info)
cli.new_info_command('sample_device_cxx_attribute_specialized_converter',
                     get_empty_info)
cli.new_info_command('sample_device_cxx_bank_by_code', get_sample_bank_info)
cli.new_info_command('sample_device_cxx_bank_by_data', get_sample_bank_info)
cli.new_info_command('sample_device_cxx_class_with_init_class', get_empty_info)
cli.new_info_command('sample_device_cxx_class_without_init_class', get_empty_info)
cli.new_info_command('sample_device_cxx_class_without_init_local', get_empty_info)
cli.new_info_command('sample_device_cxx_connect', get_empty_info)
cli.new_info_command('sample_device_cxx_connect_to_descendant', get_empty_info)
cli.new_info_command('sample_device_cxx_connect_map_target', get_empty_info)
cli.new_info_command('sample_device_cxx_event', get_empty_info)
cli.new_info_command('sample_device_cxx_interface', get_empty_info)
cli.new_info_command('sample_device_cxx_interface_c', get_empty_info)
cli.new_info_command('sample_device_cxx_interface_with_custom_info', get_empty_info)
cli.new_info_command('sample_device_cxx_logging', get_empty_info)
cli.new_info_command('sample_device_cxx_port_use_confobject', get_empty_info)
cli.new_info_command('sample_device_cxx_port_use_confobject.sample', get_empty_info)
cli.new_info_command('sample_device_cxx_port_use_port', get_empty_info)
cli.new_info_command('sample_device_cxx_port_use_port.sample', get_empty_info)
cli.new_info_command('sample_device_cxx_user_interface', get_empty_info)
cli.new_info_command('sample_device_cxx_after', get_empty_info)
cli.new_info_command('sample_device_cxx_after_bank', get_empty_info)


#
# ------------------------ status -----------------------
#

def get_empty_status(obj):
    return []

def get_sample_attribute_status(obj):
    return [(None,
             [("a_int", obj.attr.a_int),
              ("a_bool_array", obj.attr.a_bool_array),
              ("names", obj.attr.names),
              ("blob", obj.attr.blob),
              ("a_const_float", obj.attr.a_const_float),
              ("signal_target", obj.attr.signal_target),
              ("target_mem_space", obj.attr.target_mem_space)])]

def get_sample_bank_status(obj):
    return [(None,
             [("b0.r0", hex(obj.bank.b[0].r[0])),
              ("b0.r1", hex(obj.bank.b[0].r[1])),
              ("b1.r0", hex(obj.bank.b[1].r[0])),
              ("b1.r1", hex(obj.bank.b[1].r[1]))])]

def get_sample_interface_status(obj):
    return [(None,
            [("signal_raised", obj.attr.signal_raised)])]

def get_sample_logging_status(obj):
    return [(None,
             [("Log groups", obj.log_groups)])]

def get_sample_port_status(obj):
    return [(None,
             [("state", obj.attr.state)])]

def get_sample_user_interface_status(obj):
    return [(None,
             [("simple_method_cnt", obj.attr.simple_method_cnt)])]

cli.new_status_command('sample_device_cxx_attribute_class_attribute',
                       get_empty_status)
cli.new_status_command('sample_device_cxx_attribute_class_member_method',
                       get_empty_status)
cli.new_status_command('sample_device_cxx_attribute_class_member_variable',
                       get_empty_status)
cli.new_status_command('sample_device_cxx_attribute_custom_method', get_empty_status)
cli.new_status_command('sample_device_cxx_attribute_global_method', get_empty_status)
cli.new_status_command('sample_device_cxx_attribute_nested_stl_container', get_empty_status)
cli.new_status_command('sample_device_cxx_attribute_pseudo', get_empty_status)
cli.new_status_command('sample_device_cxx_attribute_specialized_converter',
                       get_empty_status)
cli.new_status_command('sample_device_cxx_bank_by_code', get_sample_bank_status)
cli.new_status_command('sample_device_cxx_bank_by_data', get_sample_bank_status)
cli.new_status_command('sample_device_cxx_class_with_init_class', get_empty_status)
cli.new_status_command('sample_device_cxx_class_without_init_class', get_empty_status)
cli.new_status_command('sample_device_cxx_class_without_init_local', get_empty_status)
cli.new_status_command('sample_device_cxx_connect', get_empty_status)
cli.new_status_command('sample_device_cxx_connect_to_descendant', get_empty_status)
cli.new_status_command('sample_device_cxx_connect_map_target', get_empty_status)
cli.new_status_command('sample_device_cxx_event', get_empty_status)
cli.new_status_command('sample_device_cxx_interface', get_sample_interface_status)
cli.new_status_command('sample_device_cxx_interface_c', get_sample_interface_status)
cli.new_status_command('sample_device_cxx_interface_with_custom_info',
                       get_sample_interface_status)
cli.new_status_command('sample_device_cxx_logging', get_sample_logging_status)
cli.new_status_command('sample_device_cxx_port_use_confobject', get_empty_status)
cli.new_status_command('sample_device_cxx_port_use_confobject.sample', get_empty_status)
cli.new_status_command('sample_device_cxx_port_use_port', get_empty_status)
cli.new_status_command('sample_device_cxx_port_use_port.sample', get_empty_status)
cli.new_status_command('sample_device_cxx_user_interface', get_sample_user_interface_status)
cli.new_status_command('sample_device_cxx_after', get_empty_status)
cli.new_status_command('sample_device_cxx_after_bank', get_empty_status)
