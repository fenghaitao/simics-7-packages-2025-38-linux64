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
import re

def object_exists(name):
    try:
        simics.SIM_get_object(name)
        return True
    except simics.SimExc_General:
        return False

def uniq_name(base):
    cnt = 1
    name = base + '0'
    while object_exists(name):
        name = base + str(cnt)
        cnt += 1
    return name

def uniq_name_from_file(fnam):
    ''' Make up a name by taking the first alphanumerical part from
    the basename of the file, appending a number if required to make
    it unique.'''
    m = re.search(r'([a-zA-Z][a-zA-Z0-9_-]*)[^/\\]*$', fnam)
    if m:
        # strip bad characters from object name
        name = re.sub(r'[^a-zA-Z0-9_-]', '-', m.group(1))
        # replace hyphens with underscores
        name = name.replace('-', '_')
        return uniq_name(name)

    return None

def image_from_file(fnam, basename):
    img_name = uniq_name(basename + '_image')
    try:
        return simics.SIM_create_object('image', img_name,
                                 [['files', [[fnam, 'ro', 0, 0]]],
                                  ['size', simics.VT_logical_file_size(fnam)]])
    except Exception as e:
        raise cli.CliError("Failed creating object '%s': %s" % (img_name, e))

def create_cdrom(name, fnam):
    if not name and fnam:
        name = uniq_name_from_file(fnam)
    if not name:
        name = uniq_name('iso')
    try:
        return simics.SIM_create_object("cdrom_image", name)
    except Exception as e:
        raise cli.CliError("Failed creating object '%s': %s" % (name, e))


def new_cdrom_cmd(file_or_image, name):
    (typ, val, tag) = file_or_image
    if tag == 'file':
        cdrom = create_cdrom(name, val)
        image = image_from_file(val, cdrom.name)
    else:
        cdrom = create_cdrom(name, None)
        image = val

    try:
        cdrom.image = image
    except simics.SimExc_IllegalValue as e:
        raise cli.CliError('Failed to create cdrom-image %s: %s' % (cdrom.name, e))

    return cli.command_return(value = cdrom.name,
                          message = "CD-ROM '%s' created" % cdrom.name)

cli.new_command("new-cdrom-image", new_cdrom_cmd,
            [cli.arg((cli.filename_t(exist = 1, simpath = 1),
                  cli.obj_t('ISO image object', kind = 'image')),
                 ("file", "image"), "?",
                 (cli.obj_t, None, "image")),
             cli.arg(cli.str_t, "name", "?", "")],
            type = ["Disks", "Image"],
            short = "create new cdrom-image object",
            doc = """

Create a new cdrom-image object from an <arg>image</arg> or a <arg>file</arg>,
of which the contents must be a valid CD-ROM (ISO) image.

If a <arg>name</arg> is not given, the name will be derived from the given
file or image name, otherwise a unique default name will be used.

The created object can be inserted into a simulated CD-ROM device using the
<b>&lt;device&gt;.insert</b> command. To remove the CD-ROM medium, set the
<attr>image</attr> attribute to NIL.""")
