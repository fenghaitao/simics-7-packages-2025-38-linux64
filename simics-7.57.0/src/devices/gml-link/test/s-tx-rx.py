# © 2015 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import os
import stest
from dev_comp import gml_dev_comp

to_test = []
objs = [x for x in SIM_object_iterator_for_class("test_generic_message_device")
        if x.name.endswith('dev')]
for o in objs:
    to_test += [o.name + ".recv", o.name + ".send"]

for f in to_test:
    file_path = os.path.join(os.environ['SANDBOX'], f)
    run = open(file_path, "r").readlines()
    ref = open(f + "_ref", "r").readlines()

    # do not test last two entries multi-threading will make some cells run longer
    for run_l in run[:-2]:
        if not run_l in ref:
            stest.fail("file %s, line: --%s-- missing in reference" % (f, run_l))

    # do not test last two entries multi-threading will make some cells run longer
    for ref_l in ref[:-2]:
        if not ref_l in run:
            stest.fail("file %s, line: --%s-- missing in test run" % (f, ref_l))
