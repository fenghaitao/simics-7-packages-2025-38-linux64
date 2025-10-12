# © 2014 Intel Corporation
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
import component_utils

default_mac = "0:0:0:0:0:0"
default_ip = "127.0.0.1"

default_arguments = {
    'bios':                     "bios.bin",
    'boot_flash':               "flash.image",
    'boot_flash_image':         "flash.image",
    'boot_flash_megs':          64,
    'boot_rom':                 "rom.image",
    'cpu_cores':                1,
    'cpu_num':                  1,
    'dst_ip':                   default_ip,
    'endian':                   "be",
    'gateway_ip':               default_ip,
    'integer_attribute':        1,
    'ip':                       default_ip,
    'loop_id':                  0,
    'loop_id0':                 0,
    'loop_id1':                 0,
    'mac':                      default_mac,
    'mac_address':              default_mac,
    'mac_address0':             default_mac,
    'mac_address1':             default_mac,
    'mac_address2':             default_mac,
    'mac_address3':             default_mac,
    'mac_addr':                 default_mac,
    'mac_addr0':                default_mac,
    'mac_addr1':                default_mac,
    'mac_addr2':                default_mac,
    'mac_addr3':                default_mac,
    'mac_addr4':                default_mac,
    'memory_megs':              64,
    'netmask':                  "255.255.0.0",
    'num_cores':                1,
    'num_cpus':                 1,
    'prom_size':                1024,
    'rom_megs':                 16,
    'rtc_time':                 "2008-01-01 00:00:00 UTC",
    'scsi_id':                  1,
    'subclock_freq_multiplier': 1,
    'system_freq_multiplier':   1,
    'telnet_port':              1025,
    'SWMODE':                   0,
    'cpu_class':                "x86-nehalem",
}

f_or_i_arguments = {
    'cpu_frequency':            168,
    'system_frequency':         100,
    'timebase_frequency':       100,
}

class CompInfoAttribute(Exception):
    pass

class CompInfoCreate(Exception):
    pass

#
# return icon
#
#
def get_comp_info(cls):
    info = {}

    cdata = simics.SIM_get_class(cls)
    cdesc, ckind, cifaces, cattrs, cmodule, cports = simics.VT_get_class_info(cls)
    config_attrs = dict(simics.SIM_get_class_attribute(cdata, 'config_attributes'))

    # the SystemC wrapper is a component in order to expose its SC objects in
    # a hierarchical namespace, but it does not provide any connectors and thus
    # can safely be excluded from get_comp_info()
    if 'sc_simcontext' in cifaces:
        info['connectors'] = {}
        return info

    args = []
    for attr in cattrs:
        (attr_n, attr_a, attr_d, attr_t) = [x for x in cdata.attributes
                                            if x[0] == attr][0]
        if attr in config_attrs and config_attrs[attr]:
            args.append([attr, config_attrs[attr][0]])
        elif not ((attr_a & simics.Sim_Attr_Flag_Mask) == simics.Sim_Attr_Required):
            continue
        elif any(a[0] == attr for a in args):
            pass
        elif attr in default_arguments:
            args.append([attr, default_arguments[attr]])
        elif attr in f_or_i_arguments:
            val = f_or_i_arguments[attr]
            if attr_t == 'f':
                args.append([attr, float(val)])
            elif attr_t == 'i':
                args.append([attr, int(val)])
            else:
                args.append([attr, val])
        else:
            raise CompInfoAttribute(("error finding default value for the %r"
                                     " attribute in class %r") % (
                    attr, cls))
    try:
        compobj = simics.SIM_create_object(cls, '', args)
    except Exception as msg:
        raise CompInfoCreate("failed creating component"
                             " SIM_create_object(%r, '', %r): %s" % (
                cls, args, msg))

    # find the subclasses iterating over the slots
    csubclasses = set()
    for o in compobj.iface.component.get_slot_objects():
        if (isinstance(o, simics.pre_conf_object)
            or isinstance(o, simics.conf_object_t)):
            csubclasses.add(o.classname)
    info['subclasses'] = list(sorted(csubclasses))

    # find connectors
    info['connectors'] = {}
    for cnt in component_utils.get_connectors(compobj):
        cinfo = {}
        cinfo['type'] = cnt.iface.connector.type()
        cinfo['hotpluggable'] = cnt.iface.connector.hotpluggable()
        cinfo['required'] = cnt.iface.connector.required()
        cinfo['multi'] = cnt.iface.connector.multi()
        cinfo['direction'] = component_utils.convert_direction(
            cnt.iface.connector.direction())
        info['connectors'][cnt.connector_name] = cinfo

    try:
        simics.SIM_delete_object(compobj)
    except Exception as msg:
        raise CompInfoCreate("error when removing component %s: %s" % (cls, msg))
    return info
