# © 2013 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import stest

def expect_objects_exist(objseq):
    all_objs = frozenset(o.name for o in SIM_object_iterator(None))
    non_existing = frozenset(o for o in objseq if not o in all_objs)
    stest.expect_equal(non_existing, frozenset(),
                       'objects should exist: ' + str(objseq))

def expect_objects_not_exist(objseq):
    all_objs = frozenset(o.name for o in SIM_object_iterator(None))
    existing = frozenset(o for o in objseq if o in all_objs)
    stest.expect_equal(existing, frozenset(),
                       'objects should not exist: ' + str(objseq))

initial_objects = list(SIM_object_iterator(None))

# Test simple case, just a cd and image created from file
run_command('new-cdrom-image file = simple-cd.craff name = cd0')
expect_objects_exist(('cd0', 'cd0_image0'))
run_command('cd0.delete')
expect_objects_not_exist(('cd0', 'cd0_image0'))

# Now test what happens if the image is in use, objects should not be deleted
run_command('new-cdrom-image file = simple-cd.craff name = cd0')
run_command('new-cdrom-image name = cd1')
conf.cd1.image = conf.cd0_image0
expect_objects_exist(('cd0', 'cd0_image0', 'cd1'))
run_command('cd0.delete')
expect_objects_exist(('cd0', 'cd0_image0', 'cd1'))
stest.expect_equal(conf.cd0.image, conf.cd0_image0)
run_command('cd1.delete')
stest.expect_equal(conf.cd0.image, conf.cd0_image0)
expect_objects_exist(('cd0', 'cd0_image0', 'cd1'))
SIM_delete_objects([conf.cd0, conf.cd1, conf.cd0_image0])

# If there is no image attached it should also work
run_command('new-cdrom-image file = simple-cd.craff name = cd0')
expect_objects_exist(('cd0', 'cd0_image0'))
conf.cd0.image = None
run_command('cd0.delete')
expect_objects_not_exist(('cd0',))
expect_objects_exist(('cd0_image0',))
SIM_delete_object(conf.cd0_image0)     # Clean up test objs

# It should not be possible to delete a CD in use (actually I guess
# this would fail anyway due to object references, but we can handle
# it nicely.
run_command('new-cdrom-image file = simple-cd.craff name = cd0')
expect_objects_exist(('cd0', 'cd0_image0'))
conf.cd0.iface.cdrom_media.insert()
stest.expect_exception(run_command, ['cd0.delete'], CliError)
expect_objects_exist(('cd0', 'cd0_image0'))
conf.cd0.iface.cdrom_media.eject()
run_command('cd0.delete')
expect_objects_not_exist(('cd0', 'cd0_image0'))

# Verify that we did not leave anything behind or remove something unintentional
all_objects = sorted(SIM_object_iterator(None))
initial_objects.sort()

stest.expect_equal(all_objects, initial_objects,
                   'The set of objects at the end of the test are different'
                   + ' from the set of objects at the start')
