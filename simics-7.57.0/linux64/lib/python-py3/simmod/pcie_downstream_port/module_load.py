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


import cli
from simics import SIM_port_object_parent, SIM_object_descendant, conf_object_t
from sim_commands import map_cmd

classes = ["pcie-downstream-port", "pcie-downstream-port-legacy"]


def pkey(obj, pdev):
    if isinstance(pdev, conf_object_t):
        return ((obj.sec_bus_num, -1, -1), pdev)
    if len(pdev) == 2:
        return (((pdev[0] >> 8) or obj.sec_bus_num,
                 (pdev[0] & 0xff) >> 3, pdev[0] & 7), pdev[1])
    return ((obj.sec_bus_num, pdev[0], pdev[1]), pdev[2])


def pinfo(obj, bdf, dev):
    (b, d, f) = bdf
    attrs = ()
    if hasattr(dev.iface, 'pci_device'):
        attrs += ("legacy",)
    if None not in bdf and ((d << 3) | f) in obj.disabled:
        attrs += ("disabled",)
    if attrs:
        name = f'{dev.name} ({", ".join(attrs)})'
    else:
        name = dev.name

    if -1 in bdf:
        devid = f"{b:02x}:xx.x"
    else:
        devid = f"{b:02x}:{d:02x}.{f}"

    return (devid, name)


def address_ranges(map_list):
    if not map_list:
        return []
    regions = sorted(
        (base, size, dev) for (base, dev, _, _, size, *_) in map_list)
    bl = max(r[0] + r[1] for r in regions).bit_length() if regions else 0
    prec = (bl + 3) // 4

    def rgn(base, size, dev):
        start = cli.number_str(base, radix=16, precision=prec)
        end = cli.number_str(base + size - 1, radix=16, precision=prec)
        name = f"{dev[0].name}:{dev[1]}" if isinstance(dev, list) else dev.name
        return (f"{start} - {end}", name)

    return [rgn(*r) for r in regions]


def get_info(obj):
    upstream = ("Upstream target", obj.upstream_target)
    transparent = ("Transparent target", obj.transparent_target)
    bus_number = ("Bus number", hex(obj.sec_bus_num))
    top_info = (None, [transparent if obj.transparent_enabled else upstream,
                       bus_number])
    devices = list(obj.devices) + list(getattr(obj, 'pci_devices', []))
    devs = sorted(pkey(obj, d) for d in devices)
    devs_info = ("Connected devices", [pinfo(obj, *d) for d in devs])
    info = [top_info, devs_info]
    return info


def get_status(obj):
    upstream = ("Upstream target", obj.upstream_target)
    transparent = ("Transparent target", obj.transparent_target)
    bus_number = ("Bus number", hex(obj.sec_bus_num))
    top_status = (None, [transparent if obj.transparent_enabled else upstream,
                         bus_number])
    functions = sorted(pkey(obj, f) for f in obj.functions)
    funcs_status = ("Mapped functions", [pinfo(obj, *f) for f in functions])

    mem_status = ("Memory ranges", address_ranges(obj.mem_space.map))
    io_status = ("I/O ranges", address_ranges(obj.io_space.map))

    # filter out cfg map entries that correspond to functions, which
    # we've already included above
    cfg_map = ((base, *tail) for (base, *tail) in obj.cfg_space.map
               if not (base >> 16) in [bdf for (bdf, *_) in obj.functions])
    cfg_status = ("Config ranges", address_ranges(cfg_map))

    status = (top_status, funcs_status, mem_status, io_status, cfg_status)
    return [s for s in status if s[1]]


for cls in classes:
    cli.new_info_command(cls, get_info)
    cli.new_status_command(cls, get_status)


# As a convenience to the user, give the translating ports a 'map'
# command which simply redirects to the map of the corresponding
# memory space.
def port_map_cmd(obj):
    parent = SIM_port_object_parent(obj)
    name = obj.name.split('.')[-1]
    space = SIM_object_descendant(parent, f'{name}_space')
    return map_cmd(space)


for p in ['mem', 'io', 'cfg', 'msg']:
    for cls in classes:
        cli.new_command(
            'map', port_map_cmd,
            type = ["Memory"],
            short="print memory map",
            see_also=['<memory-space>.map'],
            doc="Prints the memory map of the port's memory space object.",
            cls=f'{cls}.{p}')
