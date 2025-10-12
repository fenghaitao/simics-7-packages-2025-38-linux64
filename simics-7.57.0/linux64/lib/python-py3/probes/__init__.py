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


"""Simics probes framework

The probes Python package allows convenient methods for accessing
all probes which has been registered in Simics.

When probes are enabled with the enable-probes command the probe
framework will create Python ProbeProxy objects for all existing
probes in the system. Any additional created objects with probes will
also automatically get ProbeProxy objects.
"""

from .probe_enums import *     # Probe constants from interfaces

from . import templates
from . import commands
from . import prop
from . import probes
from . import pre_registered
from . import global_probes
from . import cell_probes
from . import extended_objects

from .probe_proxy import ProbeProxy

from .probes import (
    get_probes,
    get_probe_by_object,
    get_all_probes,
    get_all_probe_kinds,
    register_probe_delete_cb,
    unregister_probe_delete_cb,
    register_probe,
    is_singleton,
    CellFormatter)

from .probe_cache import cached_probe_read  # Decorator class

# Define __all__ listing all names of identifiers you get with 'from table import *'
# Also, having __all__ defined, makes help(table) produce lots of more info.
__all__ = sorted(k for k in locals() if not k.startswith('_'))
