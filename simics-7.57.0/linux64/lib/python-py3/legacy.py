# © 2023 Intel Corporation
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
sim_legacy_warnings = set()

# When adding a legacy also update
# src/docs/app-notes/simics-migration-guide/deprecation-table.docu
# if required.
def LEGACY(legacy_build_id, warn_msg, reference):
    '''Issue a legacy warning.

The 'legacy_build_id' should be the build id where the legacy change should take
place, for example to make something legacy in Simics 6, one would specify a
build id of 6000. Such a legacy change would often be added in Simics 5, or in
Simics 6 prior to its release. The 'warn_msg' argument should provide a warning
of what was set to legacy and reference should explain what to use instead.'''

    if warn_msg in sim_legacy_warnings:
        return
    if legacy_build_id > conf.sim.version:
        return
    assert legacy_build_id % SIM_MAJOR_VERSION_DIFF == 0
    sim_legacy_warnings.add(warn_msg)
    cli.pr(f"--- {warn_msg}.\n")
    cli.pr(f"    {reference}\n")
