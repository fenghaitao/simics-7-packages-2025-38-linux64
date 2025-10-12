# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import logging
from .impl import BlueprintBuilder, BlueprintError
from .data import bp_name
from .params import preset_from_args

def expand(*args, params=None, logger=logging.getLogger(),
           **kwd) -> BlueprintBuilder:
    """Expand a blueprint and return the resulting Builder object,
       for inspection or instantiation. Either a single blueprint function is
       given, which is then expanded at the empty namespace (i.e. the object
       hierarchy root), or a top namespace name and blueprint function is given.

       Blueprint parameters can be provided using the 'params' argument, as a
       (nested) dict, name -> value."""
    builder = BlueprintBuilder(logger=logger)
    if params is not None:
        if len(args) != 2:
            raise BlueprintError("Expansion requires two arguments:"
                                 " <namespace> <blueprint>")
        (ns, fn) = args
        presets = preset_from_args(ns, bp_name(fn), params)
    else:
        presets = []
    # Add any presets explicitly provided
    presets += kwd.pop("presets", [])
    builder.expand(*args, presets=presets, **kwd)
    return builder

def instantiate(*args, prefix="", **kwd) -> BlueprintBuilder:
    """Expand blueprint and instantiate the result. The arguments are the same
       as for expand(), except that a prefix string can be specified, which is
       added to all object names, hence facilitating instantiating the blueprint
       system inside a given object hierarchy."""
    builder = expand(*args, **kwd)
    builder.instantiate(prefix=prefix)
    return builder
