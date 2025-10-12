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

# This is a wrapper to the old cli_impl.py file, which now resides
# inside the cli package under 'impl'

# We will only get the symbols from this file, which does not start with underscores
# Hence we need to explicitly load some symbols that are used.
from cli.impl import *
from cli.impl import (
    _DummyCommandHandler,
    __simics_import_module_commands,
)
from cli.documentation import _simics_doc_items

from cli.tokenizer import *
from cli.tee import *
from cli.number_utils import *
