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


from cli import (new_info_command, new_status_command, new_command,
                 arg, int_t, str_t, flag_t)
from ..ieee_802_15_4_link import ieee_802_15_4_common

class_name = 'sample_802_15_4_transceiver'

#
# ------------------------ info -----------------------
#

def get_info(obj):
    # USER-TODO: Return something useful here
    return []

new_info_command(class_name, get_info)

#
# ------------------------ status -----------------------
#

def get_status(obj):
    # USER-TODO: Return something useful here
    return ieee_802_15_4_common.get_status(obj)

new_status_command(class_name, get_status)

#
# ------------------------ set_rssi -----------------------
#

def set_rssi(obj, node_name, rssi_val):
    ieee_802_15_4_common.set_rssi(obj, node_name, rssi_val)

new_command('set-rssi', set_rssi,
            args=[arg(str_t, 'node_name',
                      expander=ieee_802_15_4_common.node_name_expander),
                  arg(int_t, 'rssi')],
            alias='sr',
            short='set RSSI value',
            cls=class_name,
            doc="""
            Set RSSI value given by <arg>rssi</arg>. The value will be
            associated with the messages that are sent from this node to the
            node with the specified <arg>node_name</arg>.""")

def rm_rssi(obj, node_name, clear_all):
    if clear_all:
        ieee_802_15_4_common.clear_all_rssi(obj)
    else:
        ieee_802_15_4_common.rm_rssi(obj, node_name)

new_command('rm-rssi', rm_rssi,
            args=[arg(str_t, 'node_name',
                      spec='?', default='',
                      expander=ieee_802_15_4_common.node_name_expander),
                  arg(flag_t, '-all')],
            alias='rr',
            short='remove RSSI value',
            cls=class_name,
            doc="""
            Remove the RSSI value matching <arg>node_name</arg>.
            If <tt>-all</tt> is given, delete all RSSI value.""")

def set_rssi_always_drop(obj, rssi_always_drop):
    ieee_802_15_4_common.set_rssi_always_drop(obj, rssi_always_drop)

new_command('set-rssi-always-drop', set_rssi_always_drop,
            args=[arg(int_t, 'rssi_always_drop')],
            alias='srad',
            short='set rssi-always-drop',
            cls=class_name,
            doc="""
            Set rssi-always-drop.
            Messages taking an RSSI value lower than
            <arg>rssi_always_drop</arg> will always be dropped by
            the receiving endpoint.""")

def set_rssi_random_drop(obj, rssi_random_drop):
    ieee_802_15_4_common.set_rssi_random_drop(obj, rssi_random_drop)

new_command('set-rssi-random-drop', set_rssi_random_drop,
            args=[arg(int_t, 'rssi_random_drop')],
            alias='srrd',
            short='set rssi-random-drop',
            cls=class_name,
            doc="""
            Set rssi-random-drop.
            Messages taking an RSSI value higher than
            <arg>rssi_random_drop</arg> will always be delivered.
            Messages that take an RSSI value between
            rssi_always_drop and rssi_random_drop are
            dropped at a percentage of
            rssi_random_drop_ratio.""")

def set_rssi_random_drop_ratio(obj, rssi_random_drop_ratio):
    ieee_802_15_4_common.set_rssi_random_drop_ratio(obj, rssi_random_drop_ratio)

new_command('set-rssi-random-drop-ratio', set_rssi_random_drop_ratio,
            args=[arg(int_t, 'rssi_random_drop_ratio')],
            alias='srrdr',
            short='set rssi-random-drop-ratio',
            cls=class_name,
            doc="""
            Set rssi-random-drop-ratio.
            Messages that take an RSSI value between
            rssi_always_drop and rssi_random_drop are
            dropped at a percentage of <arg>rssi_random_drop_ratio</arg>.""")

def set_contention_ratio(obj, contention_ratio):
    ieee_802_15_4_common.set_contention_ratio(obj, contention_ratio)

new_command('set-contention-ratio', set_contention_ratio,
            args=[arg(int_t, 'contention_ratio')],
            alias='scr',
            short='set contention-ratio',
            cls=class_name,
            doc="""
            Set <arg>contention_ratio</arg> to the given value.
            The higher the contention ratio,
            the lower the effective bandwidth offered.""")
