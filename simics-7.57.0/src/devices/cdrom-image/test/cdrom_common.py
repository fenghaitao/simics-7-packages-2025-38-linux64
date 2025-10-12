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


import simics
import conf

simple_cd_test_file = 'simple-cd.craff'

def pre_conf_cd_objs(image_file, cdname = 'cdrom', image_name = None):
    if not image_name:
        image_name = cdname + '_image'

    cdrom = simics.pre_conf_object(cdname, 'cdrom_image')
    image = simics.pre_conf_object(image_name, 'image')
    image.files = [[image_file, "ro", 0, 0]]
    image.size = simics.VT_logical_file_size(image_file)
    cdrom.image = image
    return [cdrom, image]

def uniq_name(base):
    obj_names = set(o.name for o in simics.SIM_object_iterator(None))
    n = 0
    name = '%s%d' % (base, n)
    while name in obj_names:
        name = '%s%d' % (base, n)
        n += 1

    return name

def create_simple(image_file):
    name = uniq_name('cdrom')
    simics.SIM_add_configuration(pre_conf_cd_objs(image_file, name), None)
    return getattr(conf, name)

def create_with_test_wrapper(image_file):
    objs = pre_conf_cd_objs(image_file)
    cd = objs[0]
    wrapper = simics.pre_conf_object('test_wrapper', 'test_cdrom_media_wrapper')
    wrapper.cdrom = cd
    objs.append(wrapper)
    simics.SIM_add_configuration(objs, None)
    return (conf.cdrom, conf.test_wrapper)

def image_from_file(path, name):
    return simics.SIM_create_object('image', name,
                             [['size', simics.VT_logical_file_size(path)],
                              ['files', [[path, 'ro', 0, 0]]]])
