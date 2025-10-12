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

from . import nvme_comp

nvme_comp.simics_nvme_comp.register()

args_add_namespace = [
    cli.arg(cli.uint64_t, "size", "?", default=0),
    cli.arg(cli.str_t, "file", "?", default=None),
]

doc_add_namespace = """Add a namespace to the NVMe drive. This command can only
be used before instantiating the component. Therefore using
create-simics-nvme-comp is preferred to new-simics-nvme-comp (the latter
instantiates the component automatically after it is created). Either a
<arg>file</arg>, containing for example a file system can be provided, and/or a
<arg>size</arg> of the namespace. If no size if provided, the size of the
namespace will be the size of the provided file. If the size is smaller than
the file, an error will be returned. If no file is provided, the namespace will
be empty with the size provided"""

doc_add_namespace_short = "add a namespace to the NVMe drive"


def add_namespace(obj, size: int, file: str):
    obj.object_data.add_namespace(obj, size, file)


cli.new_command("add_namespace", add_namespace, args_add_namespace,
                cls="simics_nvme_comp", doc=doc_add_namespace,
                short=doc_add_namespace_short)
