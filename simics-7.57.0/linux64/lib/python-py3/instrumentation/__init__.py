# © 2016 Intel Corporation
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

# Only export a few functions that should be used externally
from .cmd_factory import (
    # Exported tool interface
    make_tool_commands,
    get_registered_tool_classes)

from .connections import (
    # Should only be used by instrumentation-preview. Not documented.
    # Exported until these commands are moved to Simics-base.
    delete_connection,
    get_all_connections,
    get_named_connections,
    name_expander
)

from .groups import (
    # Should only be used by instrumentation-preview. Not documented.
    # Exported until these commands are moved to Simics-base.
    get_groups,
    set_group,
    remove_group,
    group_expander,
)

from .filter import (
    # Should only be used by instrumentation-preview. Not documented.
    # Exported until these commands are moved to Simics-base.
    get_filter_disabled_reasons,

    # Exported filter interface
    get_filter_source,
    delete_filter
)

# force help() to list all contents
__all__ = sorted(k for k in locals() if not k.startswith('_'))
