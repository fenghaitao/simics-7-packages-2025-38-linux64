# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import subprocess
import re
import cli
import errno

def try_start_program(args, **kwords):
    try:
        return subprocess.Popen(args, **kwords)
    except OSError as e:
        raise cli.CliError(f'OSError: {e}')

def run(flatten_lines, thread_group):

    p = try_start_program(
        ["flamegraph.pl",
         "--title", "Flame Graph (vtune-measurement)",
         "--subtitle", f"Thread-group: {thread_group}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE)
    (out, err) = p.communicate(flatten_lines)
    return out


# Convert the top-down VTune lines into the format flamegraphs expects
# See test_flatten for details
def flatten_stack(lines, discard_module, modules_only):

    class Stack:
        def __init__(self, parent, stack_depth, module, function, samples):
            self.parent = parent    # Stack() object
            self.stack_depth = stack_depth
            self.module = module
            self.function = function
            self.samples = samples
            self.children = []      # List of Stack() objects

        def __repr__(self):
            if modules_only:
                return self.module
            if discard_module:
                return self.function
            return f"{self.function}[{self.module}]"

    flamegraph_lines = []

    # Recursively traverse the stack add flamegraphs lines on the
    # stack entries with samples reported on them.
    def emit_flamegraph_output(entry, prev_ids):
        identifier = repr(entry)
        stack = prev_ids + [identifier]

        if entry.samples: # Save entire stack for function with samples
            s = ";".join(stack) + (" " + str(entry.samples))
            flamegraph_lines.append(s)

        for child in entry.children:
            emit_flamegraph_output(child, stack)

    stack_re = re.compile(r'^(\s*)(.*?),([0-9]*\.?[0-9]+?),(.*)$')
    parent = None
    top = None
    for l in lines:
        mo = stack_re.match(l)
        if not mo:
            raise cli.CliError(f"Parse error: {l}")

        stack_depth = len(mo.group(1))  # stack-depth: number of spaces
        function = mo.group(2)
        samples = int(float(mo.group(3)) * 1000) # seconds -> "samples"
        module = mo.group(4)

        new = Stack(parent, stack_depth, module, function, samples)
        if not parent:  # top-level
            top = new
            parent = new
        else:
            # If we found a lower stack_depth, scan backwards to find the parent
            while stack_depth <= parent.stack_depth:
                parent = parent.parent

            # Ignore intra-module calls which costs nothing
            if not modules_only or (
                    new.module != parent.module or new.samples != 0):
                parent.children.append(new)
                parent = new

    emit_flamegraph_output(top, [])
    return flamegraph_lines


def test_flatten():
    def check_expected(out, expected):
        assert len(out) == len(expected)
        for r in range(len(out)):
            if out[r] != expected[r]:
                print(f"{r}: '{out[r]}' != '{expected[r]}' (expected)")
                assert False

    lines = [
        "main,10.0,a.out",
        " a0,0.0,a.out",
        "  b0,1.0,libc.so",
        "   b1,12.0,libc.so",
        " a1,7.0,a.out",
        "  b0,1,libc.so",
    ]
    # Both function and module
    out = flatten_stack(lines, False, False)

    expected = ["main[a.out] 10000",
                "main[a.out];a0[a.out];b0[libc.so] 1000",
                "main[a.out];a0[a.out];b0[libc.so];b1[libc.so] 12000",
                "main[a.out];a1[a.out] 7000",
                "main[a.out];a1[a.out];b0[libc.so] 1000"]
    check_expected(out, expected)

    # Discard module
    out = flatten_stack(lines, True, False)

    expected = ["main 10000",
                "main;a0;b0 1000",
                "main;a0;b0;b1 12000",
                "main;a1 7000",
                "main;a1;b0 1000"]
    check_expected(out, expected)

    # Only modules (and remove intra-module calls)
    out = flatten_stack(lines, False, True)
    expected = ["a.out 10000",
                "a.out;libc.so 1000",
                "a.out;libc.so;libc.so 12000",
                "a.out;a.out 7000",
                "a.out;a.out;libc.so 1000"]
    check_expected(out, expected)

test_flatten()
