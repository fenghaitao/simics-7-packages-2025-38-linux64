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

'This module contains code to load some documentation for the Simics API.'

# Let's introduce two data files:
# - api-help-text.json: documentation text for python api entities
# - api-help.json: prototypes for C api entities (from gulp)

import simicsutils.internal
import simicsutils.host
import pathlib
import json

try:
    from simmod.dml_api_info import dml_api_info
    try:
        _supported_dml_apis = dml_api_info.supported_dml_apis
    except AttributeError:
        # may happen during build
        pass
    # TODO: This should just be loaded as data
    from api_help_py import api_help_py
except ImportError:
    # may happen during build
    api_help_py = {}

def find_datafile():
    host = simicsutils.host.host_type()
    base = simicsutils.internal.simics_base()
    return pathlib.Path(base) / host / "api-help.json"

def load_data(datafile):
    with open(datafile) as f:
        return json.load(f)

_api_help = load_data(find_datafile())

_topics = set(api_help_py.keys())
_topics.update(_api_help.keys())
def topics():
    """Returns a set with the API help topics."""

    return _topics

def api_help(topic):
    """Returns API information about 'topic' as a tuple:
        ( defined_in_file,
          include_file,
          ( ( apis, help, typestr ), ... ) )
    or tuple(markup, plaintext) for Python API objects.

    'apis' is a sorted tuple of the APIs that the help string
    'help' applies to.

    'help' can be None, indicating that 'topic' is not supported in
    the listed APIs.

    'typestr' is "f" for functions,
    "[sue]:<typename>:<field>;<field>;..." for structs, unions and
    enums.

    The (apis, ...) tuples are sorted by the 'apis' tuples.

    Returns None if there is no such topic."""
    return _api_help.get(topic, None) or api_help_py.get(topic, None)

def api_dml_available(api):
    """Returns True if the API 'api' is available from DML.
    Will raise an exception for unknown APIs."""
    return api in _supported_dml_apis

def api_cxx_available(api):
    """Returns True if the API 'api' is available from C++"""
    # The listed interfaces do not have a C++ header. See detail reason
    # from gen_cc_interface.py
    _unsupported_cxx_apis = [
        'bank_after_read_interface_t',
        'bank_before_read_interface_t',
        'bank_after_write_interface_t',
        'bank_before_write_interface_t',
        'internal_cached_instruction_interface_t',
        'nios_interface_t',
        'mips_interface_t',
        'kbd_console_interface_t',
        ]
    return api not in _unsupported_cxx_apis
