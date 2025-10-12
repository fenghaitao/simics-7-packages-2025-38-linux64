# © 2021 Intel Corporation
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
from typing import (
    Literal,
    NamedTuple,
)
from blueprints import Builder, ConfObject, State, Default, Namespace
from .state import SATAConnectionState

class FileEntry(NamedTuple):
    path: str
    mode: Literal["ro", "rw"]
    start: int = 0
    size: int = 0
    offset: int = 0

class DiskImage(State):
    path = ""
    "Image path"
    size = 0
    "Optional image size. The size is obtained from the image file by default."
    files: list[FileEntry] = []
    """List with file entries (an alternative to path, if multiple files
    need to be specified."""
    obj = ConfObject()
    "The image object."
    resulting_size = 0
    "The image size. Set to the calculated size."

def disk_image(bp: Builder, name: Namespace, **kwds):
    "Blueprint representing an image object with handling for setting the"
    " files attribute using the DiskImage state."
    di = bp.read_state(name, DiskImage)
    for (k, v) in kwds.items():
        setattr(di, k, v)

    def lookup_image_size():
        import simics
        real_path = simics.SIM_lookup_file(di.path)
        if not real_path:
            bp.error(f"missing disk image '{di.path}'")
            return 0
        return simics.VT_logical_file_size(real_path)

    size = di.size if di.size else (lookup_image_size() if di.path else 0)
    if di.path:
        di.files.append(FileEntry(di.path, "ro"))
    di.obj = bp.obj(name, "image", size = size, files = di.files)
    di.resulting_size = size


def ide_disk_common(bp: Builder, name: Namespace, di: DiskImage):
    size = di.resulting_size
    disk_sectors = size // 512
    disk_cylinders = min(size // (16 * 63 * 52), 16383)

    bp.obj(name, "ide-disk",
        image = di.obj,
        disk_sectors = disk_sectors,
        disk_cylinders = disk_cylinders,
        disk_heads = 16,
        disk_sectors_per_track = 63,
    )

def ide_disk(bp: Builder, name: Namespace):
    bp.expose_state(name, DiskImage)
    bp.expand(name, "", ide_disk_common)

def sata_disk(bp: Builder, name: Namespace, sata: SATAConnectionState):
    bp.expose_state(name, DiskImage)
    bp.expand(name, "hd", ide_disk_common)
    sata.device = bp.obj(name, "sata", master = name.hd, hba = sata.controller)
    sata.device_connector = bp.obj(name.connector, "sata-device-connector",
          device=name,
          aname="hba",
          remote=sata.controller_connector
    )

# SATA disk *with* image
def generic_sata_disk(bp: Builder, name: Namespace, path = None):
    "SATA disk with a disk image"
    bp.expand(name, "", sata_disk)
    bp.expand(name, "image", disk_image, path = path)
