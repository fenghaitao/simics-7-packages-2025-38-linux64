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

from .documentation import doc

class CliException(Exception):
    def value(self):
        if self.args:
            (val,) = self.args
            return val
        else:
            return '[Exception without args]'

class CliError(
        CliException,
        metaclass=doc('error in CLI command',
                      module = 'cli',
                      synopsis = 'CliError(args)')):
    """This exception can be raised whenever a command can
    not complete successfully."""
class CliTabComplete(CliException): pass
class CliSyntaxError(CliException): pass
class CliTypeError(CliException): pass
class CliValueError(CliException): pass
class CliParseError(CliException): pass
class CliBreakError(CliException):
    "Used by break-loop command"
class CliContinueError(CliException):
    "Used by continue-loop command"
class CliParseErrorInDocText(CliException): pass
class CliErrorInPolyToSpec(CliException): pass
class CliArgumentError(CliException): pass
class CliArgNameError(CliArgumentError): pass
class CliOutOfArgs(CliArgumentError): pass
class CliAmbiguousCommand(CliException): pass
class CliQuietError(CliException):
    def __init__(self, *args, is_script_branch_interrupt=False):
        super().__init__(*args)
        self.is_script_branch_interrupt = is_script_branch_interrupt
class CliCmdDefError(CliException):
    "A bad CLI command definition"
