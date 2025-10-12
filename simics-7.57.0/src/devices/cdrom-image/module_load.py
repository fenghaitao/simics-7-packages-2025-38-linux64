# © 2012 Intel Corporation
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
import os

def get_image_port(obj):
    img = obj.image
    port = None
    if img and not isinstance(img, simics.conf_object_t):
        (img, port) = img
    return (img, port)

def del_cdrom_image_cmd(obj):
    if obj.in_use:
        raise cli.CliError(
            'CD-ROM %s is in use, eject it before you delete it.'
            % obj.name)

    (img, _) = get_image_port(obj)

    name = obj.name
    objs = [obj] + ([img] if img else [])
    try:
        simics.SIM_delete_objects(objs)
        print("CD-ROM object '%s' (and any image) deleted." % name)
    except simics.SimExc_General as msg:
        print("Failed deleting file CD-ROM object '%s': %s" % (name, msg))
        return

def get_info(obj):
    (img, port) = get_image_port(obj)
    if not img:
        return [(None, [('Image', 'No image')])]

    if port:
        img_name = '%s:%s' % (img.name, port)
    else:
        img_name = img.name

    info = []
    if len(img.files) == 1:
        info = [('Image file', os.path.basename(img.files[0][0]))]

    cap = obj.capacity
    info += [('Image', img_name),
             ('Capacity', '%d (%d bytes)' % (cap, 2048*cap))]

    return [(None, info)]

def get_status(obj):
    return [(None,
             [('In use', obj.in_use)])]

cli.new_info_command("cdrom_image", get_info)
cli.new_status_command("cdrom_image", get_status)

cli.new_command("delete", del_cdrom_image_cmd,
            args  = [],
            type = ["Disks", "Image"],
            cls = "cdrom_image",
            short = "delete an unused cdrom-image object",
            doc = """
Delete an unused cdrom-image object. This will also delete any
image assigned to the <attr>image</attr> attribute of the
cdrom-image. The deletion will fail if the object or its image is
referenced from other objects.
""")
