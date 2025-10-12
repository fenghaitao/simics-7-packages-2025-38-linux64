# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

from pathlib import Path
import common as setup
import testparams as tp
add_testfun("setup-project", setup.run,
            args=[Path(tp.sandbox_project()), Path(tp.simics_base_path()),
                  Path(tp.simics_repo_root())])
add_subtests("s-*.py", scratch_project=True)

add_dependency("setup-project", "s-info-status")
add_dependency("setup-project", "s-sample-device-with-external-lib")

# tests need to run sequentially as they both attempt to delete the library
# from its build location to ensure it is picked up only from its
# runtime location
add_dependency("s-info-status", "s-sample-device-with-external-lib")
