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


import cli

from instrumentation import make_tool_commands

def pre_connect(obj, provider, *args):
    if not provider and any(args):
        raise cli.CliError("Argument specified with nothing connected")
    (offset, size, value, inject) = args

    entire_bank = offset == 0 and size == 0
    range_desc = "bank" if entire_bank else "range %02x:%02x" % (
        offset, offset + size - 1)
    return ([['offset', offset],
             ['size', size],
             ['value', value],
             ['inject', inject]],
            ("%s access misses in %s (value: %02x)") % (
                'Injecting' if inject else 'Forgiving', range_desc, value))

intmax = 0xFFFFFFFFFFFFFFFF
args = [
    cli.arg(cli.range_t(0, intmax, 'address'), 'offset'),
    cli.arg(cli.range_t(0, intmax, 'size'), 'size'),
    cli.arg(cli.uint64_t, 'value', '?', 0),
    cli.arg(cli.flag_t, '-inject', '?', False)]

doc = \
    """Each new connection to the patch tool may be configured by
       providing the instrumentation start address
       (<arg>offset</arg>), the instrumentation range
       (<arg>size</arg>), and the value to be read in place of a
       otherwise mapped register values (<arg>value</arg>).

       Providing an offset and a size of 0 will instrument the entire
       bank.  Access misses may also be injected using the
       <tt>-inject</tt> flag, which is disabled by default"""

make_tool_commands('bank_patch_tool',
                   object_prefix = 'patch_tool',
                   provider_requirements = 'bank_instrumentation_subscribe',
                   provider_names = ('bank', 'banks'),
                   connect_extra_args = (args, pre_connect, doc),
                   new_cmd_doc = """Creates a new bank patch tool object which
                                    can be connected to register banks.""")
