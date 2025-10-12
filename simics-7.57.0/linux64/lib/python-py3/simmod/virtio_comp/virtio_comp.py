# © 2022 Intel Corporation
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
import stat

import simics
from comp import (EthernetLinkDownConnector, PciBusUpConnector,
                  SimpleConfigAttribute, StandardConnectorComponent)
from simmod.std_comp.std_comp import disk_components


class virtio_pcie_blk_comp(disk_components):
    """PCIe Virtio Block Device."""
    _class_desc = "a PCIe Block device"
    _help_categories = ()

    def setup(self):
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_connectors(self):
        self.add_connector('pcie', PciBusUpConnector(0, 'virtio_blk'))

    def add_objects(self):
        virtio_blk = self.add_pre_obj('virtio_blk', 'virtio_pcie_blk')
        virtio_blk.attr.image = self.create_disk_image('virtio_blk.image')


class virtio_pcie_net_comp(StandardConnectorComponent):
    """PCIe Virtio Net Device."""
    _class_desc = "a PCIe Network device"
    _help_categories = ()

    class mac_address(SimpleConfigAttribute("00:00:00:00:00:00", 's')):
        """MAC Address for the Virtio Net Device"""

    def setup(self):
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_connectors(self):
        self.add_connector(
            'eth', EthernetLinkDownConnector('virtio_net.port.eth'))
        self.add_connector('pcie', PciBusUpConnector(0, 'virtio_net'))

    def add_objects(self):
        virtio_net = self.add_pre_obj('virtio_net', 'virtio_pcie_net')
        virtio_net.mac_address = self.mac_address.val


### Virtio MMIO disk
class virtio_mmio_blk_comp(disk_components):
    """"virtio_mmio_blk" component setups a disk using the virtio mmio block device"""
    _class_desc = "a virtio mmio block device"
    _do_not_init = object()
    _help_categories = ("Virtio", "Disks")

    class basename(StandardConnectorComponent.basename):
        val = 'virtio_mmio_disk'

    class component_icon(disk_components.component_icon):
        pass

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()

    def add_objects(self):
        image = self.create_disk_image('disk_image')
        virtio_block = self.add_pre_obj('virtio_disk', 'virtio_mmio_blk')
        virtio_block.image = image


class virtio_pcie_fs_comp(StandardConnectorComponent):
    """PCIe Virtio File System Device. This component should be used with the
    configuration attribute <attr>share</attr> set to either a directory or a
    Unix domain socket file. If the former case, the virtioFS daemon will be
    started automatically by Simics. In the latter case, the user has to start
    the daemon manually. This can be beneficial in cases where one would want
    to run the daemon under fakeroot or root."""
    _class_desc = "a PCIe fs device"
    _help_categories = ()

    class tag_name(SimpleConfigAttribute('simics', 's')):
        """The tag name to be used when mounting the device on the guest,
        default is simics"""

    class share(SimpleConfigAttribute('', 's', simics.Sim_Attr_Required)):
        """Either a directory to share with the target, or a unix domain socket
        file."""

    class daemon_log_file(SimpleConfigAttribute('', 's')):
        """If set, the FUSE daemon will enable DEBUG logs and log to the
        provided path, default is unset"""

    class always_cache(SimpleConfigAttribute(False, 'b',
                                             simics.Sim_Attr_Internal |
                                             simics.Sim_Attr_Optional)):
        """Enable full caching for FUSE, which increases the performance of the
        virtioFS mount point on the guest. WARNING! Only set to true if no
        modifications will be done in the shared directory by the host until
        the simics process has been terminated. Doing so might result in data
        loss. Default is FALSE"""

    def setup(self):
        s = os.stat(self.share.val)
        if not stat.S_ISSOCK(s.st_mode) and not stat.S_ISDIR(s.st_mode):
            raise ValueError(
                "The 'share' configuration attribute must be set to either a"
                " directory or a unix domain socket file")
        if not self.instantiated.val:
            self.add_objects()
        self.add_connectors()

    def add_connectors(self):
        self.add_connector(
            'upstream_target', PciBusUpConnector(0, 'virtio_fs'))

    def add_objects(self):
        virtio_fs_dev = self.add_pre_obj(
            'virtio_fs', 'virtio_pcie_fs', tag_name=self.tag_name.val)

        virtiofs_fuse_dev = self.add_pre_obj('fuse', 'virtiofs_fuse')

        virtiofs_fuse_dev.always_cache = self.always_cache.val
        virtiofs_fuse_dev.share = self.share.val
        if self.daemon_log_file.val != '':
            virtiofs_fuse_dev.daemon_log_file = self.daemon_log_file.val

        virtio_fs_dev.chan = virtiofs_fuse_dev
