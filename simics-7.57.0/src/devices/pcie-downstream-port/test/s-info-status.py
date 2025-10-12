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


from pcie_downstream_port_common import legacy_rc
import cli
import random
import re
import simics
import stest

random.seed("Lungs")
(rc, _) = legacy_rc()
mem = simics.SIM_create_object('set-memory', 'smem')
spaces = {simics.PCIE_Type_IO: rc.dp.io_space,
          simics.PCIE_Type_Mem: rc.dp.mem_space}


class transparent:
    cls = simics.confclass('transparent-pcie')

    @cls.iface.pcie_device.connected
    def connected(self, *args):
        pass


# disable one legacy device and one new device
rc.dp.pci_devices[1][3] = 0
d, f, *_ = rc.dp.devices[1]
rc.dp.iface.pcie_map.disable_function(d << 3 | f)

# add one virtual device
rc.dp.iface.pcie_map.add_function(mem, random.randrange(0xff))

# add one transparent device
rc.dp.devices += [
    simics.SIM_create_object('transparent-pcie', 'transparent')]


def check_eps(output, eps):
    b = rc.dp.sec_bus_num
    for nfo in eps:
        if isinstance(nfo, simics.conf_object_t):
            exp = f'{b:02x}:xx.x : {nfo.name}'  # transparent device
        else:
            if len(nfo) == 2:
                (df, dev) = nfo
                d = df >> 3
                f = df & 7
            else:
                (d, f, dev, *_) = nfo
            exp = f'{b:02x}:{d:02x}.{f} : {dev.name}'
        legacy = hasattr(dev.iface, 'pci_device')
        disabled = (d << 3 | f) in rc.dp.disabled
        if legacy and disabled:
            exp += ' (legacy, disabled)'
        elif legacy:
            exp += ' (legacy)'
        elif disabled:
            exp += ' (disabled)'
        stest.expect_true(exp in output, exp)


val, output = cli.quiet_run_command(f'{rc.dp.name}.info')
print(output)
check_eps(output, rc.dp.pci_devices)
check_eps(output, rc.dp.devices)

map_infos = []
for kind in (simics.PCIE_Type_IO, simics.PCIE_Type_Mem, simics.PCIE_Type_Cfg):
    for _ in range(3):
        nfo = simics.map_info_t(
            base=1 << random.randrange(64), length=1 << random.randrange(64))
        rc.dp.iface.pcie_map.add_map(mem, nfo, kind)
        map_infos.append((nfo, mem))


# manually add a map that uses legacy dev:port notation
class legacy:
    cls = simics.confclass('legacy')
    cls.ports.foo.transaction()


ldev = simics.SIM_create_object('legacy', 'ldev')
lnfo = simics.map_info_t(base=0x123000, length=0x1000)
rc.dp.mem_space.iface.map_demap.map_simple(ldev, "foo", lnfo)
map_infos.append((lnfo, ldev))

val, output = cli.quiet_run_command(f'{rc.dp.name}.status')
print(output)
for nfo, dev in map_infos:
    exp = rf'0x0*{nfo.base:x} - 0x0*{nfo.base + nfo.length - 1:x} : {dev.name}'
    stest.expect_true(re.search(exp, output))
check_eps(output, rc.dp.functions)
