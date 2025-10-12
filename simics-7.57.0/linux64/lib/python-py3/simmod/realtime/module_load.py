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
class_name = 'realtime'

def get_info(rt):
    return [(None,
             [('Realtime clock frequency', '%d Hz' % rt.rtc_freq)])]
cli.new_info_command(class_name, get_info)

def get_status(rt):
    return [(None,
             [('Enabled', ['No', 'Yes'][rt.enabled]),
              ('Clock', rt.clock_object.name),
              ('Speed', '%.3f' % rt.speed),
              ('Check interval', '%d ms' % rt.check_interval),
              ('Drift compensation speed', '%.3f' % rt.drift_compensate),
              ('Compensate for OS sleep inaccuracy',
               '%d us' % rt.max_oversleep)])]
cli.new_status_command(class_name, get_status)

def enable_cmd(rt, speed, check_interval, drift_comp):
    if speed != None:
        rt.speed = speed/100.0
    if check_interval != None:
        rt.check_interval = check_interval
    if drift_comp != None:
        rt.drift_compensate = drift_comp
    rt.enabled = True
cli.new_command('enable', enable_cmd,
            [cli.arg(cli.float_t, 'speed', '?', None),
             cli.arg(cli.range_t(1, 0xffffffff, "positive integer"),
                 'check-interval', '?', None),
             cli.arg(cli.float_t, 'drift-compensate', '?', None)],
            cls = class_name,
            type = ['Execution', 'Performance'],
            short = 'enable real-time behavior',
            see_also = ['enable-real-time-mode',
                        '<realtime>.disable'],
            doc = """
When enabled, a <obj>realtime</obj> object will periodically check the
simulation speed and wait for a while if it is too high.

<arg>speed</arg> specifies how fast simulated time is allowed to run, in
percent of real time; default is 100.

<arg>check-interval</arg> specifies how often the check should take place, in
milliseconds of simulated time; default is 1000. Higher values give better
performance; lower values reduce the maximum difference between real and
simulated time. Setting this to less than <cmd>set-time-quantum</cmd> has no
effect.

Upon deviation, <arg>drift-compensate</arg> regulates how much may be
adjusted. If set to (for example) 0.25, simulation speed may be increased or
decreased by up to 25% if necessary to make up for any accumulated drift with
respect to real time. If set to zero (the default), the simulation speed may
not be changed at all from its set value.
""")

def disable_cmd(rt):
    rt.enabled = False
cli.new_command('disable', disable_cmd, [],
            cls = class_name,
            type = ['Execution', 'Performance'],
            short = 'disable real-time behavior',
            doc = 'Disable real-time behavior.',
            see_also = ['<realtime>.enable'])
