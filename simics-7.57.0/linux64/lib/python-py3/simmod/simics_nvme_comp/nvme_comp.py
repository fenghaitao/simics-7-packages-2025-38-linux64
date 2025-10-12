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
import simics
from comp import (PciBusUpConnector, SimpleConfigAttribute,
                  StandardConnectorComponent)


class simics_nvme_comp(StandardConnectorComponent):
    """A generic NVMe device over PCIe with support for multiple namespaces.
    Namespaces can be added with the add_namespace command, before
    instantiating the component."""
    _class_desc = "an NVMe IO Controller"
    _help_categories = ()
    nvme = None

    class disk_size(SimpleConfigAttribute(0, 'i', simics.Sim_Attr_Required)):
        """The size of the underlying storage for the NVMe drive. The combined
        size of the namespaces added with the add_namespace command must not
        exceed this value."""

    class bandwidth(SimpleConfigAttribute(0, 'i')):
        """The read/write speed of the NVMe disk, provided in MB/s. 0 means
        instant read/write:s, which is the default value"""

    class dynamic_size(SimpleConfigAttribute(False, 'b')):
        """If set to True, adding a namespace will increase the disk size
        if needed."""

    def add_namespace(self, obj, size: int, file: str):
        if self.instantiated.val:
            raise cli.CliError(f"Can not add new namespaces to {obj.name}."
                               " Component has already been instantiated.")
        ns_images = self.get_slot('namespaces.images')
        if len(ns_images) > 1024:
            raise cli.CliError(
                "Reached maximum number of supported namespaces")

        valid_path = False
        if file:
            real_path = simics.SIM_lookup_file(file)
            if real_path:
                valid_path = True
                if size == 0:
                    # Only use size from file if no disk size is set, allowing
                    # users to skip the end of the file or have a larger disk
                    # than the current file size.
                    size = simics.VT_logical_file_size(real_path)
                elif size < simics.VT_logical_file_size(real_path):
                    simics.SIM_log_info(
                        1, self.obj, 0,
                        "WARNING: explicitly specified disk size is smaller"
                        " than the size required by the disk image.")

        if (sum(self.nvme.namespace_sizes) + size) > self.disk_size.val:
            if self.dynamic_size.val:
                self.nvme.disk_size = sum(self.nvme.namespace_sizes) + size
                self.disk_size.val = self.nvme.disk_size
            else:
                raise cli.CliError("Trying to add a new namespace with a size that"
                                   " would result in the total size of all the"
                                   " added namespaces to exceed the disk size")

        image = self.add_pre_obj(None, 'image')
        ns_images.append(image)
        self.add_slot('namespaces.images', ns_images)
        if valid_path:
            image.files = [[file, 'ro', 0, 0, 0]]

        # We set the size of the image to the disk size to ensure that it will
        # never be too small. The actual size of the namespace will be tracked
        # in the namespace_sizes attribute of the nvme device model
        image.size = size
        self.nvme.namespace_sizes.append(size)
        self.nvme.attr.images.append(image)
        return cli.command_return(None,
                                  f"Added a new namespace to {obj.name} with"
                                  f" NID {len(ns_images)} with size {size}")

    def setup(self):
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()
        self.add_slots()

    def add_slots(self):
        self.add_slot('namespaces.images', [])

    def add_connectors(self):
        self.add_connector('pcie', PciBusUpConnector(0, 'nvme'))

    def add_objects(self):
        self.nvme = self.add_pre_obj('nvme', 'simics_nvme_controller')
        self.nvme.disk_size = self.disk_size.val
        self.nvme.bandwidth = self.bandwidth.val
        self.nvme.namespace_sizes = []
        self.nvme.attr.images = []
