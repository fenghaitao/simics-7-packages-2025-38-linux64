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


#::doc info_status {{
# Library for checking if classes has info and status commands.
# }}

import cli
import simics

__all__ = ('report_info_status_errors', 'check_for_info_status')

def get_classes_in_modules(modules):
    res = []
    for m in simics.SIM_get_all_modules():
        name = m[0]
        classes = m[7]
        if name in modules:
            res.extend(classes)
    return set(res)

def print_indented_list(heading, lst):
    if lst == []: return
    print(heading)
    for e in lst:
        print("    %s" % e)

#:: doc info_status.report_info_status_errors {{
# Prints its input lists and quits Simics with an error.
#
# First each provided list is printed in a human readable manner and then the
# function quits Simics with the result 1, which will be detected by the test
# system as a test failure.
#
# Arguments:
# <div class="dl">
#
# - <span class="term">missing\_info</span>
#     a list of classes which do not have `info` commands
# - <span class="term">missing\_status</span>
#     a list of classes which do not have `status` commands
# - <span class="term">unexpected\_info</span>
#     a list of classes which have `info` commands, but which
#     were on the info command passlist
# - <span class="term">unexpected\_status</span>
#     a list of classes which have `status` commands, but which
#     were on the status command passlist
# </div>
# }}
def report_info_status_errors(missing_info, missing_status, unexpected_info,
                             unexpected_status):
    print_indented_list("Classes with missing info commands:", missing_info)
    print_indented_list("Classes with missing status commands:",
                        missing_status)
    print_indented_list("Classes which unexpectedly has info commands:",
                        unexpected_info)
    print_indented_list("Classes which unexpectedly has status commands:",
                        unexpected_status)
    simics.SIM_quit(1)

#:: doc info_status.check_for_info_status {{
# Check that the classes in a list of modules have info and status commands.
#
# Classes are Simics configuration classes, not python classes. The function
# checks all the classes in the named modules to see if they have `info` and
# `status` commands. If any such command is missing it will be detected as an
# error, but you can provide passlists. If a class is passlisted and still has
# the command it will be detected as an error. If any errors are detected the
# function calls a function to report this. By default the
# `report_info_status_error` is called, but you can override this with the
# `report_errors` argument.
#
# The modules named in modules will be loaded into Simics as a side effect of
# running this test.
#
# Arguments:
# <div class="dl">
#
# - <span class="term">modules</span>
#     the modules whose classes to test
# - <span class="term">info\_passlist</span>
#     the list of classes which should not have info commands
# - <span class="term">status\_passlist</span>
#     the list of classes which should not have status commands
# - <span class="term">report\_errors</span>
#     the function to call to report errors
# </div>
# }}
def check_for_info_status(modules, info_passlist=[], status_passlist=[],
                          report_errors=report_info_status_errors):
    for module in modules:
        simics.SIM_load_module(module)

    missing_info = []
    missing_status = []
    unexpected_info = []
    unexpected_status = []
    def check(classname, present, passlist, missing, unexpected):
        if classname in passlist:
            if present:
                unexpected.append(classname)
        else:
            if not present:
                missing.append(classname)

    all_commands = cli.simics_commands()
    for cls in get_classes_in_modules(modules):
        has_info = False
        has_status = False
        for cmd in all_commands:
            namespace = cmd.cls or cmd.iface
            if namespace == cls or namespace in simics.VT_get_interfaces(cls):
                has_info = has_info or cmd.name.endswith(".info")
                has_status = has_status or cmd.name.endswith(".status")
        print(cls, has_info, has_status)
        check(cls, has_info, info_passlist, missing_info, unexpected_info)
        check(cls, has_status, status_passlist, missing_status,
              unexpected_status)

    if missing_info or missing_status or unexpected_info or unexpected_status:
        report_errors(missing_info, missing_status, unexpected_info,
                      unexpected_status)
