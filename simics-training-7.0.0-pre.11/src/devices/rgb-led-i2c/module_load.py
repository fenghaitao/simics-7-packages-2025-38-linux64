# © 2018 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


##
## module-load.py for the RGB LED on I2C
##
## Define custom info and status commands for the device
## 
import cli
import simics 

def info(obj):
    return [(None,
             [("I2C Device Address", obj.address),
              ("I2C Link", obj.i2c_link),
              ("System panel LED", obj.panel_led_out)])]

def status(obj):
    return [("Current color registers",
             [("red", obj.bank.i2cregs.red),
              ("green", obj.bank.i2cregs.green),
              ("blue", obj.bank.i2cregs.blue)]),
            ("LED output",
             [("Current value", obj.current_color_value_driven)])]

cli.new_info_command("rgb_led_i2c", info)
cli.new_status_command("rgb_led_i2c", status)

##
## Custom command - set rgb color from the Simics CLI 
## 
def set_color(obj,r,g,b):
    ## Try to set color codes, expect the device attribute to
    ## reject bad values.  No point in doing extra error checking here. 
    try:
        obj.bank.i2cregs.red = r
        obj.bank.i2cregs.green = g
        obj.bank.i2cregs.blue = b
        obj.drive_value = True
        return cli.command_return(
            f"Pixel value #{r:02x}{g:02x}{b:02x} driven to LED",
            [r,g,b])
    except:
        raise cli.CliError("Failed to set LED color")

# Actual definition of the command 
cli.new_command(
    "set-color", set_color,
    cls="rgb_led_i2c",
    args=[cli.arg(cli.int_t, "red"),
          cli.arg(cli.int_t, "green"),
          cli.arg(cli.int_t, "blue")],
    short="set the color of the LED",
    doc=("<tt>set-color</tt> sets the color of the LED controller and drives"
         " the color to the system panel. <arg>red</arg>, <arg>green</arg>,"
         " and <arg>blue</arg> specify the value for each component of"
         " an RGB color specification. The values for the arguments should be"
         " between 0 and 255, but at the moment the model really only cares"
         " about 0 and non-zero. This can change in the future."))
