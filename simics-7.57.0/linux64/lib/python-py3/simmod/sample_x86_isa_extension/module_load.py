# © 2016 Intel Corporation
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
import simics

class_name = 'sample-x86-isa-extension'

def create_isa_extension_cmd(processor, connect_all):
    def connect_processor(processor):
        object_name = (processor.component.name
                       + '.isa_extension_' + processor.component_slot)
        try:
            simics.SIM_get_object(object_name)
            return
        except simics.SimExc_General:
            pass
        isa_obj = simics.SIM_create_object(class_name, object_name)
        isa_obj.iface.instrumentation_tool.connect(processor, None)
        return isa_obj

    if connect_all:
        cpus = [p for p in simics.SIM_get_all_processors() if hasattr(p.iface, 'x86')]
        isa_objs = []
        for c in cpus:
            isa_objs.append(connect_processor(c))
        return isa_objs
    elif processor:
        return connect_processor(processor)

cli.new_command("new-sample-x86-isa-extension", create_isa_extension_cmd,
            [cli.arg(cli.obj_t('processor', 'x86'), 'processor', '?'),
             cli.arg(cli.flag_t, '-connect-all')],
            short = "create a new sample ISA extension for x86",
            doc = """Create a new sample ISA extension object which can be
connected to x86 processors.

The <arg>processor</arg> parameter specifies which processor should be
connected to the new ISA extension object.

<tt>-connect-all</tt> flag can be used to create and connect an ISA extension
object to all x86 processors in the simulated system.""")

def get_info(obj):
    # USER-TODO: Return something useful here
    return []

cli.new_info_command(class_name, get_info)

def get_status(obj):
    # USER-TODO: Return something useful here
    return []

cli.new_status_command(class_name, get_status)
