# © 2013 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from cli import (
    arg,
    new_command,
    new_info_command,
    new_status_command,
    uint16_t,
)
import sim_commands
import pci_common
import vga_common

vga_name = "accel_vga_v2"

VBE_INDEX = 0
VBE_ENABLE = 1
VBE_BANK = 2
VBE_XRES = 3
VBE_YRES = 4
VBE_BPP = 5
VBE_ID = 6
VBE_VIRT_XRES = 7
VBE_VIRT_YRES = 8
VBE_X_OFFSET = 9
VBE_Y_OFFSET = 10

def accel_vga_display_res(obj, x, y):
    if x == None or y == None:
        print("Maximum display resolution: %d x %d" % (
            obj.display_max_xres,
            obj.display_max_yres))
    else:
        obj.display_max_xres = x
        obj.display_max_yres = y

new_command("display-resolution", accel_vga_display_res,
            [arg(uint16_t, "x", '?', None),
             arg(uint16_t, "y", '?', None)],
            short = "display resolution",
            cls = "accel_vga_v2",
            doc = """
Set the maximum resolution (<arg>x</arg>, <arg>y</arg>) of the display
connected to the device. When used without any arguments, the current setting
is shown.""")

def accel_vga_get_info(obj):
    return (vga_common.get_info(obj.vga_engine) +
            [("Display",
              [("Max horizontal resolution", obj.display_max_xres),
               ("Max vertical resolution", obj.display_max_yres)])])

def accel_vga_get_status(obj):
    vbe_regs = obj.bank.vbe_regs
    enabled = (vbe_regs.vbe_enable & 1)
    if enabled:
        return [(None,
                  [("VBE enabled",             enabled),
                   ("Linear Frame Buffer", ((vbe_regs.vbe_enable >> 6) & 1)),
                   ("X Resolution",        vbe_regs.vbe_xres),
                   ("Y Resolution",        vbe_regs.vbe_yres),
                   ("Bits Per Pixel",      vbe_regs.vbe_bpp),
                   ("Virtual X Resolution", vbe_regs.vbe_virt_xres),
                   ("Virtual Y Resolution", vbe_regs.vbe_virt_yres),
                   ("X Offset", vbe_regs.vbe_x_offset),
                   ("Y Offset", vbe_regs.vbe_y_offset)])]
    else:
        return ([(None,
                  [("VBE enabled", enabled)])] +
                vga_common.get_status(obj.vga_engine))

new_info_command(vga_name, accel_vga_get_info)
new_status_command(vga_name, accel_vga_get_status)
vga_common.new_vga_commands(vga_name, info=False)
