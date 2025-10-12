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


# This file is used by the pattern-matcher and all defined patterns
import cli

__all__ = ['add',
           'hypersim_patterns',
           'register_std_info_command',
           'register_std_status_command']

# used by cli.doc
__simicsapi_doc_id__ = 'hypersim_api'

# Global list of patterns that are available
hypersim_patterns = []

@cli.doc('register a hypersim-pattern')
def add(name, arch,
        target_list = None,
        own_info_cmd = False,
        own_status_cmd = False):
    '''The simics_start.py script for all pattern modules should call
    this function to register its pattern classes. The patterns will
    be automatically installed on the processor types it supports.

    Function arguments:
    <dl>
    <dt><param>name</param></dt> <dd>class name</dd>
    <dt><param>arch</param></dt>
        <dd>architecture it supports (cpu->architecture ppc32, ppc64)</dd>
    <dt><param>target_list</param></dt>
        <dd>optional list of classnames that are supported.
            If target_list is omitted or None, the pattern will be used by all
            CPUs of <param>arch</param> architecture.</dd>
    <dt><param>own_info_cmd</param></dt>
        <dd>Legacy parameter, must always be overridden to True</dd>
    <dt><param>own_status_cmd</param></dt>
        <dd>Legacy parameter, must always be overridden to True</dd>
    </dl>
    '''
    if own_info_cmd is not True or own_status_cmd is not True:
        # This deprecation is discussed in bug 19625
        raise Exception("It is deprecated to pass other values than True in the"
                        " own_info_cmd and own_status_cmd parameters to"
                        " hypersim_patterns.add(). Omitting the parameters is"
                        " also deprecated."
                        " Register info/status commands in module_load.py."
                        " Call hypersim_patterns.register_std_info_command()"
                        " and hypersim_patterns.register_std_status_command()"
                        " there to get the default implementations.")
    hypersim_patterns.append([name, arch, target_list])

def default_info_cmd(obj):
    return [(None,
             [("Pattern matcher", obj.pattern_matcher)])]

# All state for a pattern is normally within the hypersim-pattern matcher
def default_status_cmd(obj):
    return [(None,
             [("Status", "See the hypersim-status -v command")])]

@cli.doc('register standard info command')
def register_std_info_command(cls):
    '''Register a basic info command implementation for the hypersim
    pattern class named <param>cls</param>'''
    cli.new_info_command(cls, default_info_cmd)

@cli.doc('register standard status command')
def register_std_status_command(cls):
    '''Register a basic status command implementation for the hypersim
    pattern class named <param>cls</param>'''
    cli.new_status_command(cls, default_status_cmd)
