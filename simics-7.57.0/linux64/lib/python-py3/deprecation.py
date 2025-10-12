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
import conf
import simics

SIM_MAJOR_VERSION_DIFF = 1000
sim_deprecated_warnings = set()

# When adding a deprecation also update
# src/docs/app-notes/simics-migration-guide/deprecation-table.docu
# if required.
def DEPRECATED(depr_build_id, warn_msg, reference):
    '''Issue a deprecation warning depending on the current deprecation settings.

The depr_build_id should be the build id where the deprecation takes
place, for example to deprecate something in Simics 6 one would
specify a build id of 6000. Such a deprecation would often be
added in Simics 5, or in Simics 6 prior to its release.
This would cause a deprecation warning to be emitted in 5 if
the -wdeprecated flag (deprecation level 2) is given to Simics. In 6 and 7,
the message would be emitted by default (deprecation level
1), but it can be suppressed with the -no-wdeprecated flag
(deprecation level 0). The feature would be removed in 8.

warn_msg should provide a warning of what was deprecated and reference
should explain what to use instead.'''
    if warn_msg in sim_deprecated_warnings:
        return
    assert depr_build_id % SIM_MAJOR_VERSION_DIFF == 0
    sim_deprecated_warnings.add(warn_msg)
    if conf.sim.deprecation_level == 0:
        return
    elif conf.sim.deprecation_level == 1:
        if depr_build_id > conf.sim.version:
            return
    else:
        assert conf.sim.deprecation_level == 2
    simics.VT_deprecate(depr_build_id, warn_msg, reference)
    if conf.sim.deprecations_as_errors and conf.sim.deprecation_stack_trace:
        cli.simics_print_stack()
