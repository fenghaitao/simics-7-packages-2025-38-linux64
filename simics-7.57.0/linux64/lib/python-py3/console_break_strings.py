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


from cli import (
    CliError,
    check_script_branch_command,
    command_verbose_return,
    get_completions,
    )
from script_branch import (
    sb_wait_for_hap_internal,
)
from simics import (
    Column_Key_Name,
    Table_Key_Columns,
    conf_object_t,
    )
import table

def break_cmd(console, string, once, regexp):
    if regexp:
        return console.iface.break_strings_v2.add_regexp(string, None, None)
    elif once:
        return console.iface.break_strings_v2.add_single(string, None, None)
    else:
        return console.iface.break_strings_v2.add(string, None, None)

def unbreak_cmd(console, str_id):
    blist = [bp_id for (_, active, _, bp_id, _, _) in console.break_strings
             if active]
    if str_id in blist:
        console.iface.break_strings_v2.remove(str_id)
    else:
        raise CliError(f"No such breakpoint: {str_id}")

def active_bp_ids(console):
    # Construct IDs of active breakpoints.
    return map(lambda e: str(e[3]),
               filter(lambda e: e[1], console.break_strings))

# Must match hap name in C code.
break_hap_name = "Console_Break_String"

def wait_then_write_cmd(console, slow_flag, regexp, emacs, wait_str, write_str,
                        input_fn):
    check_script_branch_command("wait-then-write")
    # First wait for the string output.
    if regexp:
        break_id = console.iface.break_strings_v2.add_regexp(wait_str,
                                                             None, None)
    else:
        break_id = console.iface.break_strings_v2.add(wait_str, None, None)
    try:
        sb_wait_for_hap_internal(
            f'bp.console_string.wait-then-write console = {console.name}',
            break_hap_name, console, break_id, wait_str)

        # Now enter the input string.
        input_fn(console, write_str, emacs)
    finally:
        if isinstance(console, conf_object_t):
            # unregister, unless SB interrupted because object was deleted.
            console.iface.break_strings_v2.remove(break_id)

def break_arg_doc(cmd):
    return """
Example of waiting for a typical shell prompt on console object $con:
<pre>
<b>bp.console_string.¤cmd¤ $con "~ $"</b>
</pre>
""".replace("¤cmd¤", cmd)

def regexp_arg_doc(cmd):
    return """
If <tt>-regexp</tt> is specified, the breakpoint string will be
interpreted as a regular expression (regexp). The regexp syntax
follows the common Perl style, as interpreted by the Hyperscan library
<url>https://hyperscan.io</url>.

Note that the string is a Simics CLI string, and thus \\ has to be
escaped as \\\\ when writing the regexp.

Examples:
<ul>
<li>Wait for 3 digits:
<pre>
<b>$con.¤cmd¤ -regexp "\\\\d{3}"</b>
</pre>
</li>
<li>Wait for a '4' somewhere between square brackets (note that in regular expressions, [] have special meanings, so must be escaped):
<pre>
<b>$con.¤cmd¤ -regexp "\\\\[.*4.*\\\\]"</b>
</pre>
</li>
<li>Wait for a 3 characters or 6 curly braces:
<pre>
<b>$con.¤cmd¤ -regexp "\\\\w{3}|[{}]{6}"</b>
</pre>
</li>
</ul>

For more information about regular expression syntax, see
<url>https://perldoc.perl.org/re.html</url>.
""".replace("¤cmd¤", cmd)
