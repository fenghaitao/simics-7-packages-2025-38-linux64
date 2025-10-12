# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


'''The conf module contains all Simics configuration objects. As
objects are created or deleted, they are added to or removed from this
module.

The special member 'classes' is a namespace for all registered Simics
configuration classes.'''


from conf_impl import classes

# force help() to list all contents
__all__ = sorted(k for k in locals() if not k.startswith('_'))
