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


# Hard-error, the json file is incorrect.
class GraphSpecException(Exception):
    pass

# Container for probes, with annotations and possibly the
# expanded wildcard object
class ExpandedDataProbe:
    def __init__(self, probe_name, annotation_probes, wildcard_obj):
        self.probe_name = probe_name
        self.annotation_probes = annotation_probes
        self.wildcard_obj = wildcard_obj

    def __repr__(self):
        return (f"Norm: (probe_name:{self.probe_name},"
                f"annotation_probes:{self.annotation_probes},"
                f"wildcard_obj:{self.wildcard_obj})")


# Documentation elements for a graph property
class PropDoc:
    def __init__(self, name, type, default, valid_values, desc):
        self.name = name
        self.type = type
        self.default = default
        self.valid_values = valid_values
        self.desc = desc
