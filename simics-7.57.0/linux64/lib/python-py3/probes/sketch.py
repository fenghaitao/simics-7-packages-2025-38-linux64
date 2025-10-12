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

import cli
from simics import *
from configuration import OBJECT

# We use a 'blue-print' of the objects that should be created later,
# all in one go.
class ObjSketch:
    __slots__ = ('cls', 'name', 'attrs')
    def __init__(self, cls, name, attrs):
        self.cls = cls
        self.name = name
        self.attrs = attrs

def new(cls, name, attrs=[]):
    'return a list of one or zero elements of ObjSketch.'
    n = name.replace("-", "_")  # Object names may not contain hyphens
    if cli.object_exists(n):
        return []
    return [ ObjSketch(cls, n, attrs) ]

def create_configuration_objects(new_sketches):
    objs = {}
    for sketch in new_sketches:
        path = ""
        for part in sketch.name.split(".")[:-1]:
            path += part
            # Create a name-space object if the path is unknown
            if path not in objs and not cli.object_exists(path):
                objs[path] = ("pseudo_namespace", [])
            path += "."

        if not cli.object_exists(sketch.name):
            objs[sketch.name] = (sketch.cls, sketch.attrs)

    new_objects = []
    for (name, (cls, attrs)) in objs.items():
        new_objects.append(OBJECT(name, cls, **dict(attrs)))

    if new_objects:
        SIM_set_configuration(new_objects)
