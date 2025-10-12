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


import simics
import stest
import info_status

images = [simics.pre_conf_object(None, 'image', size=1024)]
nvme = simics.pre_conf_object('nvme', 'simics_nvme_controller', images=images,
                              namespace_sizes=[1024], disk_size=4096)
simics.SIM_add_configuration([nvme, images[0]], None)

# Verify that info/status commands have been registered for nvme device
info_status.check_for_info_status(['simics-nvme-controller'])

# Currently just check that the commands return nicely
for cmd in ['info', 'status']:
    try:
        simics.SIM_run_command(nvme.name + '.' + cmd)
    except simics.SimExc_General as e:
        stest.fail(cmd + ' command failed: ' + str(e))
