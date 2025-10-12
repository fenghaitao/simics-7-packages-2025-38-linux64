# © 2017 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import os

import cli
import simics

from . import common

def create_object(name, cls, uniqify):
    """Create an object named by adding an index to the given name."""
    if uniqify:
        name = cli.get_available_object_name(name + '_')
    try:
        return simics.SIM_create_object(cls, name, [])
    except simics.SimExc_General as e:
        raise cli.CliError(e)

def mangle_string(s):
    # Remove anything that isn't a-z or A-Z
    out = ""
    for c in s:
        if (c >= 'a' and c <= 'z') or (c >= 'A' and c <= 'Z'):
            out += c
    return out

def create_cc_object(name, context_query, suffix=None):
    if name:
        obj_name = name
    elif context_query:
        obj_name = 'coverage'
        query_suffix = mangle_string(context_query)
        if query_suffix:
            obj_name += query_suffix
    elif suffix:
        obj_name = f'coverage_{suffix}'
    else:
        assert False

    coverage_conf_obj = create_object(obj_name, 'code_coverage', not name)
    return coverage_conf_obj

def load_coverage(input_file, name):
    coverage_conf_obj = create_cc_object(name, None, suffix='reporter')
    try:
        coverage_conf_obj.object_data.load(input_file)
    except common.CodeCoverageException as e:
        raise cli.CliError("Error loading coverage: %s" % e)

    return cli.command_return(
        value = coverage_conf_obj,
        message = ('%s has been loaded with a coverage report using %s'
                   % (coverage_conf_obj.name, input_file)))

def simics_query_reformat(query):
    if not query:
        return None
    return '\''.join([elem.replace('\'', '\"') for elem in query.split('\\\'')])

def is_x86_cpu(cpu):
    return getattr(getattr(cpu, "iface", object), "x86", None) is not None

def any_x86_cpu():
    for cpu in simics.SIM_get_all_processors():
        if is_x86_cpu(cpu):
            return True
    return False

def coverage(cq, name, flag_next_or_running, branch_cov, access_count,
             linear):
    if flag_next_or_running:
        (_, _, flag_next_or_running) = flag_next_or_running

    context_query = simics_query_reformat(cq)
    if not context_query:
        raise cli.CliError('Context query is empty!')

    tcf = simics.SIM_get_debugger()
    query_iface = tcf.iface.debug_query
    (err_code, contexts) = query_iface.matching_contexts(context_query)
    if err_code != simics.Debugger_No_Error:
        raise cli.CliError("Error collecting coverage: %s" % contexts)

    if flag_next_or_running == '-running' and not contexts:
        raise cli.CliError("Error: No matching contexts")

    if linear and not any_x86_cpu():
        raise cli.CliError("The -linear flag requires an x86 processor to be"
                           " present")

    if flag_next_or_running == "-next" or not contexts:
        coverage_conf_obj = create_cc_object(name, context_query)
        try:
            coverage_conf_obj.object_data.wait_for_context(
                contexts, context_query, branch_cov, access_count, linear)
        except common.CodeCoverageException as e:
            raise cli.CliError("Error while trying to wait for context: %s" % e)
        return cli.command_return(
            value = coverage_conf_obj,
            message = ('%s will collect coverage for %s when it starts'
                       % (coverage_conf_obj.name, context_query)))

    (rc, res) = common.get_unique_ctx(tcf, contexts)
    if not rc:
        raise cli.CliError(res)

    coverage_conf_obj = create_cc_object(name, context_query)
    ctx_id = res
    try:
        coverage_conf_obj.object_data.start(ctx_id, branch_cov, access_count,
                                            linear)
    except common.CodeCoverageException as e:
        raise cli.CliError(e)

    return cli.command_return(
        value = coverage_conf_obj,
        message = ('%s is collecting coverage for %s'
                   % (coverage_conf_obj.name, context_query)))


def stop(obj):
    try:
        obj.object_data.stop(False)
    except common.CodeCoverageException as e:
        raise cli.CliError("Error stopping coverage: %s" % e)

def save(obj, output, overwrite):
    print("Saving output to: %s" % output)
    try:
        obj.object_data.save(output, overwrite)
    except common.CodeCoverageException as e:
        raise cli.CliError("Error saving report: %s" % e)

def load(obj, input_file):
    print("Loading input from: %s" % input_file)
    try:
        obj.object_data.load(input_file)
    except common.CodeCoverageException as e:
        raise cli.CliError("Error loading coverage: %s" % e)

def add_report(obj, input_file, ignore_addresses):
    print("Adding report from input file: %s" % input_file)
    try:
        obj.object_data.add_report(input_file, ignore_addresses)
    except common.CodeCoverageException as e:
        raise cli.CliError("Error adding report: %s" % e)

def disassemble(obj, whole_section, remove_old):
    try:
        (ok, err_str) = obj.object_data.disassemble(True, not whole_section,
                                                    remove_old)
    except common.CodeCoverageException as e:
        raise cli.CliError("Error disassembling: %s" % e)
    if not ok:
        return cli.command_return(err_str)

def add_functions(obj, remove_old, keep_data):
    try:
        (ok, err_str) = obj.object_data.add_functions(True, remove_old,
                                                      keep_data)
    except common.CodeCoverageException as e:
        raise cli.CliError("Error adding functions: %s" % e)
    if not ok:
        return cli.command_return(err_str)

def add_source_info(obj, remove_old):
    try:
        (ok, err_str) = obj.object_data.add_source_info(True, remove_old)
    except common.CodeCoverageException as e:
        raise cli.CliError(e)
    if not ok:
        return cli.command_return(err_str)

def add_source_only_info(obj, remove_old):
    try:
        (ok, err_str) = obj.object_data.add_source_only_info(True, remove_old)
    except common.CodeCoverageException as e:
        raise cli.CliError(e)
    if not ok:
        return cli.command_return(err_str)

def remove_analyzer_info(obj):
    try:
        obj.object_data.remove_analyzer_info()
    except common.CodeCoverageException as e:
        raise cli.CliError(e)

def html_report(obj, output, report_name, no_disassembly, no_unmapped_addresses,
                no_unknown_modules, no_summary_table, no_module_line_cov,
                only_with_src, no_function_coverage, only_disassembly,
                include_opcode, include_line, keep_data, max_errors_per_mapping,
                summary_per_file, tree_summary, show_line_functions,
                source_only_data, source_files_base_path):
    print("Saving HTML report to: %s" % output)
    if no_disassembly and only_disassembly:
        raise cli.CliError("Only one of -no-disassembly and -only-disassembly"
                           " can be specified")
    if source_only_data:
        if only_disassembly:
            raise cli.CliError('-only-disassembly cannot be used with'
                               ' -source-only-data')
        if only_with_src:
            raise cli.CliError('-only-addresses-with-source cannot be used with'
                               ' -source-only-data')
    try:
        nr_errors = obj.object_data.html_report(
            output, no_disassembly, only_with_src, no_summary_table,
            no_unmapped_addresses, no_unknown_modules, only_disassembly,
            include_opcode, keep_data, max_errors_per_mapping, report_name,
            summary_per_file, show_line_functions, no_module_line_cov,
            include_line, source_only_data, source_files_base_path,
            tree_summary, no_function_coverage)
    except common.CodeCoverageException as e:
        raise cli.CliError("Error adding source info: %s" % e)
    if nr_errors > 0:
        return cli.command_return(
            message = "Report contains %d errors" % nr_errors)

def lcov_output(obj, output, counter_option, keep_data, source_only_data):
    if counter_option not in lcov_counter_option_types:
        raise cli.CliError("Invalid counter option '%s'" % counter_option)
    try:
        tracefiles = obj.object_data.lcov_output(output, counter_option,
                                                 keep_data, source_only_data)
    except common.CodeCoverageException as e:
        raise cli.CliError("Error outputting LCOV tracefiles: %s" % e)

    if tracefiles == 0:
        raise cli.CliError('No tracesfiles output, failed to add source info?')

    return cli.command_return(
        value = tracefiles,
        message = "Outputted %d tracefile%s" % (
            len(tracefiles), "" if len(tracefiles) == 1 else "s"))

def csv_output(obj, output):
    try:
        obj.object_data.csv_output(output)
    except common.CodeCoverageException as e:
        raise cli.CliError(f'Error outputting CSV report: {e}')
    cli.command_return(message = 'CSV report successfully output')

def add_path_map(obj, src, dst):
    try:
        obj.object_data.add_path_map(src, dst)
    except common.CodeCoverageException as e:
        raise cli.CliError("Error adding path map: %s" % e)

def clear_path_maps(obj):
    try:
        obj.object_data.clear_path_maps()
    except common.CodeCoverageException as e:
        raise cli.CliError("Error clearing path maps: %s" % e)

def list_path_maps(obj):
    try:
        maps = obj.object_data.list_path_maps()
    except common.CodeCoverageException as e:
        raise cli.CliError("Error listing path maps: %s" % e)
    return cli.command_return(
        value = maps,
        message = '\n'.join('%s -> %s' % (pm_from, pm_to)
                            for (pm_from, pm_to) in maps))

def filter_mappings(obj, map_filters, file_filters, remove):
    if not map_filters and not file_filters:
        raise cli.CliError("At least one filter must be specified")
    if not isinstance(map_filters, list):
        map_filters = [map_filters]
    for m in map_filters:
        if not isinstance(m, (str, int)):
            raise cli.CliError("Bad filter: '%s' is not a string or integer"
                               % m)
    if not isinstance(file_filters, list):
        file_filters = [file_filters]
    for f in file_filters:
        if not isinstance(f, str):
            raise cli.CliError("Bad file filter: '%s' is not a string" % f)
    try:
        (maps_removed, files_removed) = obj.object_data.filter_mappings(
            map_filters, file_filters, remove)
    except common.CodeCoverageException as e:
        raise cli.CliError("Error filtering mappings: %s" % e)
    return cli.command_return(value = [maps_removed, files_removed],
                              message = ("removed %d mappings and %d files"
                                         % (maps_removed, files_removed)))

def remove_unknown_addresses(obj):
    try:
        nr_removed = obj.object_data.remove_unknown_addresses()
    except common.CodeCoverageException as e:
        raise cli.CliError(f'Error removing unknown addresses: {e}')
    return cli.command_return(value=nr_removed,
                              message=f'removed {nr_removed} unknown addresses')

def list_mappings(obj, sort_by_file, keep_directories):
    try:
        mappings = obj.object_data.list_mappings(sort_by_file,
                                                 not keep_directories)
    except common.CodeCoverageException as e:
        raise cli.CliError("Error listing mappings: %s" % e)

    addr_len = (8 if not mappings or max([x[1] for x in mappings]) < 1 << 32
                else 16)
    return cli.command_return(
        value = mappings,
        message = "\n".join("0x%0*x-0x%0*x: %s"
                            % (addr_len, s_addr, addr_len, e_addr, f)
                            for (s_addr, e_addr, f) in mappings))

def combine_mappings(obj):
    try:
        nr_removed = obj.object_data.combine_mappings()
    except common.CodeCoverageException as e:
        raise cli.CliError("Error combining mappings: %s" % e)
    return cli.command_return(
        value = nr_removed,
        message = "%d mappings were removed" % nr_removed)

def add_collect_command():
    cli.new_command(
        'collect-coverage', coverage,
        [cli.arg(cli.str_t, 'context-query'),
         cli.arg(cli.str_t, "name", "?", None),
         cli.arg((cli.flag_t, cli.flag_t), ('-next', '-running'), '?'),
         cli.arg(cli.flag_t, "-branch-coverage"),
         cli.arg(cli.flag_t, "-access-count"), cli.arg(cli.flag_t, "-linear")],
        short = 'collect a coverage profile',
        see_also = [],
        doc = """
Start collecting code coverage for the context matching the context query given
by the <arg>context-query</arg> argument.

If the <tt>-running</tt> flag is given, code coverage will be started on an
already existing context.

If the <tt>-next</tt> flag is given, code coverage will be started on the next
created context that matches the context query.

If the <tt>-branch-coverage</tt> flag is given, then instruction level branch
coverage will be collected and stored in the report. Using this option can
affect simulation performance. Note that this option is only for disassembly
output, source level branch coverage is not supported.

If the <tt>-access-count</tt> flag is given, the times each instruction has
been accessed will be stored in the report. Otherwise the count will always
be set to 1. Using this option will affect simulation performance.

If the <tt>-linear</tt> flag is given, addresses on x86 processors will be
collected as linear addresses instead of logical.

The name of the code coverage object can be specified by the <arg>name</arg>
argument. If no name is provided a random name is selected.

""")

def add_load_coverage_command():
    cli.new_command(
        'load-coverage', load_coverage,
        [cli.arg(cli.filename_t(), 'input'),
         cli.arg(cli.str_t, "name", "?", None)],
        short = 'load coverage from file',
        see_also = ["<code_coverage>.save",
                    "<code_coverage>.add-report"],
        doc = """

Load the code coverage data file specified by the <arg>input</arg> argument and
create a new code coverage object. The name of the code coverage object can be
set by specifying the <arg>name</arg> argument, if no name is given a random
one will be used.

""")

def add_save_command(code_coverage):
    cli.new_command(
        'save', save,
        [cli.arg(cli.filename_t(), 'output'),
         cli.arg(cli.flag_t, '-overwrite')],
        cls=code_coverage.code_coverage.__name__,
        short = 'save collected code coverage',
        see_also = ["load-coverage",
                    "<code_coverage>.add-report"],
        doc = """

Save the current code coverage state into a raw file given by the
<arg>output</arg> argument. If the <tt>-overwrite</tt> flag was given, any
existing file will be overwritten.

""")

def add_report_command(code_coverage):
    cli.new_command(
        'add-report', add_report,
        [cli.arg(cli.filename_t(), 'input'),
         cli.arg(cli.flag_t, "-ignore-addresses")],
        cls=code_coverage.code_coverage.__name__,
        short = 'add report to already existing coverage',
        see_also = ["<code_coverage>.combine-mappings"],
        doc = """

Load a raw code coverage report specified by the <arg>input</arg> argument and
merge it into the current code coverage state.

If the <tt>-ignore-addresses</tt> flag is given, memory maps will be combined
if the only difference are their loaded addresses (and relocation). Since
disassembly will differ for the two mappings (jump addresses etc), the
disassembly information will only be kept for the existing mapping.

""")

def add_disass_command(code_coverage):
    cli.new_command(
        'disassemble', disassemble,
        [cli.arg(cli.flag_t, '-whole-section'),
         cli.arg(cli.flag_t, '-remove-old')],
        cls=code_coverage.code_coverage.__name__,
        short = 'create disassembly for all mappings',
        see_also = ["<code_coverage>.add-functions"],
        doc = """

Build disassembly information for all mappings that has been found by the code
coverage system.

If <tt>-whole-section</tt> flag is used each section will be disassembled from
start to end. Otherwise, if functions data is added and available,
disassembling will start from the start address of each function.
Disassembling from the start of each function has the advantage that if there
is data in the executable section then such data in the end of a function will
not affect the function after.

The <tt>-remove-old</tt> flag will remove any disassembly previously
added. This will also remove any source info that was previously added as that
depends on addresses added when disassembling.

""")

def add_functions_command(code_coverage):
    cli.new_command(
        'add-functions', add_functions,
        [cli.arg(cli.flag_t, '-remove-old'),
         cli.arg(cli.flag_t, '-no-data-labels')],
        cls=code_coverage.code_coverage.__name__,
        short = 'create functions map',
        see_also = ["<code_coverage>.disassemble"],
        doc = """

Adds function information to the internal data structures.

The <tt>-remove-old</tt> flag will remove any existing function information
before adding new. Without this flag function information will only be added
if it has previously not been added.

The <tt>-no-data-labels</tt> flag will tell the command to <b>not</b> try to
handle certain function names as data labels and instead keep them as
functions. This will lead to that these labels as included in the disassembly
report as functions, even though they are most likely data. Without this options
data ranges following such labels will be excluded from the report. Altering
this flag implies removing old data.
""")

def add_source_info_command(code_coverage):
    cli.new_command(
        'add-source-info', add_source_info,
        [cli.arg(cli.flag_t, '-remove-old')],
        cls=code_coverage.code_coverage.__name__,
        short = 'include source info',
        see_also = ["<code_coverage>.disassemble",
                    "<code_coverage>.add-functions",
                    "<code_coverage>.add-source-only-info",
                    "<code_coverage>.remove-analyzer-info"],
        doc = """

Builds source line information to the internal data structures.

This command will also perform what the
<cmd class="code_coverage">add-functions</cmd> and
<cmd class="code_coverage">disassemble</cmd> commands do, with default options,
unless those commands have been run prior to this command.

The <tt>-remove-old</tt> flag will remove any existing source info data before
adding new. Without this flag source info data will only be added if it has
previously not been added.

Any source only information (see <cmd
class="code_coverage">add-source-only-info</cmd>) will be removed regardless of
the <tt>-remove-old</tt> flag. Only one type of analyzer information can be
present at once.

""")

def add_source_only_info_command(code_coverage):
    cli.new_command(
        'add-source-only-info', add_source_only_info,
        [cli.arg(cli.flag_t, '-remove-old')],
        cls=code_coverage.code_coverage.__name__,
        short = 'include source info',
        see_also = ["<code_coverage>.add-source-info",
                    "<code_coverage>.remove-analyzer-info"],
        doc = """

Adds source info without need for disassembly and functions.

The <tt>-remove-old</tt> flag will remove any existing source info data before
adding new. Without this flag source info data will only be added if it has
previously not been added.

Data under the 'info' field in the raw report will always be removed when this
command is run. This includes data collected from added with <cmd
class="code_coverage">add-source-info</cmd> and <cmd
class="code_coverage">disassemble</cmd> commands. Only one type of analyzer
information can be present at once.

""")

def add_remove_analyzer_info_command(code_coverage):
    cli.new_command(
        'remove-analyzer-info', remove_analyzer_info,
        [],
        cls=code_coverage.code_coverage.__name__,
        short = 'remove source info',
        see_also = ["<code_coverage>.add-source-info",
                    "<code_coverage>.add-source-only-info",
                    "<code_coverage>.add-functions",
                    "<code_coverage>.disassemble"],
        doc = """

Remove analyzer information from the report, including source information, file
table, functions and disassembly information. The data left in the report after
this command will be the same data that was initially collected.

""")

def add_stop_command(code_coverage):
    cli.new_command(
        'stop', stop,
        [],
        cls=code_coverage.code_coverage.__name__,
        short = 'stop recording coverage',
        see_also = ["<code_coverage>.add-source-info",
                    "<code_coverage>.disassemble",
                    "<code_coverage>.add-functions",
                    "<code_coverage>.html-report"],
        doc = """

Will stop code coverage collection, existing data will be kept in order to
support report generation.

""")

def add_html_report_command(code_coverage):
    cli.new_command(
        'html-report', html_report,
        [cli.arg(cli.filename_t(), 'output'),
         cli.arg(cli.str_t, 'report-name', '?', None),
         cli.arg(cli.flag_t, '-no-disassembly'),
         cli.arg(cli.flag_t, '-no-unmapped-addresses'),
         cli.arg(cli.flag_t, '-no-unknown-modules'),
         cli.arg(cli.flag_t, '-no-summary-table'),
         cli.arg(cli.flag_t, '-no-module-line-coverage'),
         cli.arg(cli.flag_t, '-only-addresses-with-source'),
         cli.arg(cli.flag_t, '-no-function-coverage'),
         cli.arg(cli.flag_t, '-only-disassembly'),
         cli.arg(cli.flag_t, '-include-opcode'),
         cli.arg(cli.flag_t, '-include-line'),
         cli.arg(cli.flag_t, '-no-data-labels'),
         cli.arg(cli.int_t, 'max-errors-per-mapping', '?', 8),
         cli.arg(cli.flag_t, '-summary-per-file'),
         cli.arg(cli.flag_t, '-tree-summary'),
         cli.arg(cli.flag_t, '-show-line-functions'),
         cli.arg(cli.flag_t, '-source-only-data'),
         cli.arg(cli.str_t, 'source-files-base-path', '?', None)],
        cls = code_coverage.code_coverage.__name__,
        short = "write html report",
        see_also = [],
        doc = """

Create an HTML code coverage report, with the root directory specified by the
<arg>output</arg> argument.

The <arg>report-name</arg> argument can be used to give the report a name, this
will be displayed as the title and header in the HTML pages.

If the <tt>-no-disassembly</tt> flag is set, no disassembly will be included in
the HTML report.

If the <tt>-no-unmapped-addresses</tt> flag is set, addresses that has been
run, but was not mapped into a known memory map of any symbol file will be
ignored. This can typically be addresses that are part of interrupt routines,
padding instructions between functions, or addresses for which there where no
mapping found, although there should have been.

If the <tt>-no-unknown-modules</tt> flag is set, modules that has no debug
information mapping of any kind associated with them, will not show up in the
report.

If the <tt>-no-summary-table</tt> flag is set, the function coverage summary
for the disassembly report will be disabled.

If the <tt>-no-module-line-coverage</tt> flag is set, source line coverage
per symbol file and function will be excluded from disassembly reports.

If the <tt>-no-function-coverage</tt> flag is set, the function coverage report
page is excluded.

If the <tt>-only-addresses-with-source</tt> flag is set, instructions that are
not associated with any source line will be excluded from the disassembly
report.

If the <tt>-only-disassembly</tt> flag is set, no source code coverage
will be reported, only the disassembly coverage.

If the <tt>-include-opcode</tt> flag is set opcode will be shown in
the disassembly coverage report.

If the <tt>-include-line</tt> flag is set line numbers will be shown in
the disassembly coverage report.

The <tt>-summary-per-file</tt> flag specifies that the source coverage page
should include every file on that page, otherwise the main page will group
coverage per directory.

The <tt>-tree-summary</tt> flag specifies that the summary page should be
presented in such a way that covered lines and percentage include coverage for
all sub-directories as well.

The <tt>-show-line-functions</tt> flag can be used to output which functions
make use of each line, in the source file reports. This can be useful to gain a
better understanding of why source lines are covered or not when there are
optimizations and inlined code involved.

The <tt>-no-data-labels</tt> flag will tell the command to <b>not</b> try to
handle certain function names as data labels and instead keep them as
functions. This will lead to that these labels as included in the disassembly
report as functions, even though they are most likely data. Without this options
data ranges following such labels will be excluded from the report. Altering
this flag implies removing old data.

The <tt>-source-only-data</tt> flag will force the source code data to be
collected in the way the <cmd class="code_coverage">add-source-only-info</cmd>
command does it, regardless of architecture. This implies the
<tt>-no-disassembly</tt> flag. Previously added source and disassembly
information of other format will be removed from the raw report data.

The <arg>source-files-base-path</arg> option can be used to override the default
base path on the source files summary page. Setting this to "" will result in
full paths being displayed for all paths.

The <arg>max-errors-per-mapping</arg> argument can be used to specify a
maximum number of errors to show per mapping. If this is set to a negative
value an unlimited amout of errors will be shown.

If the data collection done by the <cmd
class="code_coverage">add-functions</cmd>, and <cmd
class="code_coverage">disassemble</cmd>, <cmd
class="code_coverage">add-source-info</cmd> commands has not been performed,
this will be done before saving the report.

""")

lcov_counter_option_types = ("one", "all_one", "most", "first")

def lcov_counter_option_exp(string):
    return cli.get_completions(string, lcov_counter_option_types)

def add_lcov_report_command(code_coverage):
    cli.new_command(
        'lcov-output', lcov_output,
        [cli.arg(cli.filename_t(), 'output'),
         cli.arg(cli.str_t, 'counter-option', '?', "one",
                 expander=lcov_counter_option_exp),
         cli.arg(cli.flag_t, '-no-data-labels'),
         cli.arg(cli.flag_t, '-source-only-data')],
        cls = code_coverage.code_coverage.__name__,
        short = "output report to LCOV tracefile format",
        see_also = ["<code_coverage>.html-report",
                    "<code_coverage>.save"],
        doc = """
Report code coverage in lcov tracefile format.

The <arg>output</arg> is a directory with one LCOV formatted tracefile for each
mapping in the report. The naming of the tracefiles will be the name of the
mapping's symbol file plus a suffix with an underscore and the address of the
mapping in hex, for example "program_400000".

As the binaries are not instrumented the number of times a line has been
executed might not always be accurate. The user has the option to specify how
the counting of how many times a line has been executed should be done, using
the <arg>counter-option</arg> argument. It has the following options:

"all_one": Always one, for both functions and lines.
"one": One for lines. For functions the number of times the first instruction
       has been executed (default).
"most": Times run for the instruction that has executed most times for the
        line.
"first": Times the first instruction of the line has executed.

In order for any of these options to display more than one executed line or
function the code coverage report must have been collected with the access
count option enabled.

For description of <tt>-no-data-labels</tt> and <tt>-source-only-data</tt> see
help for <cmd class="code_coverage">html-report</cmd>.

If the data collection done by the <cmd
class="code_coverage">add-functions</cmd>, and <cmd
class="code_coverage">disassemble</cmd>, <cmd
class="code_coverage">add-source-info</cmd> commands has not been performed,
this will be done before saving the report.

The command will return a list of files that were outputted, with absolute
path.""")

def add_csv_report_command(code_coverage):
    cli.new_command(
        'csv-output', csv_output,
        [cli.arg(cli.filename_t(), 'output'),],
        cls = code_coverage.code_coverage.__name__,
        short = 'output report in CSV format',
        see_also = ['<code_coverage>.html-report',
                    '<code_coverage>.save',
                    '<code_coverage>.add-source-info'],
        doc = """
Report code coverage in a comma separated values (CSV) format.

The lines in the <arg>output</arg> file has the following format:
source file,total line,covered lines

If source info has not been added to the report, it will be added before
outputting. See help for the <cmd class="code_coverage">add-source-info</cmd>
command for more information.

""")

def add_path_map_command(code_coverage):
    cli.new_command(
        'add-path-map', add_path_map,
        [cli.arg(cli.str_t, 'from'),
         cli.arg(cli.filename_t(dirs=True), 'to')],
        cls = code_coverage.code_coverage.__name__,
        short = "add path map",
        see_also = ["<code_coverage>.clear-path-maps",
                    "<code_coverage>.list-path-maps"],
        doc = """

Add a path map that will be used when locating binaries and source files while
building the code coverage data and report. The path map will be used by
replacing the beginning of a file path matching the string given by the
<arg>from</arg> argument with the string in the <arg>to</arg> argument.

""")

def add_clear_path_maps_command(code_coverage):
    cli.new_command(
        'clear-path-maps', clear_path_maps, [],
        cls = code_coverage.code_coverage.__name__,
        short = "clear all added path maps",
        see_also = ["<code_coverage>.add-path-map",
                    "<code_coverage>.list-path-maps"],
        doc = """

Remove all path maps that has been added with the <cmd
class="code_coverage">add-path-map</cmd> command.

""")

def add_list_path_maps_command(code_coverage):
    cli.new_command(
        'list-path-maps', list_path_maps, [],
        cls = code_coverage.code_coverage.__name__,
        short = "list added path maps",
        see_also = ["<code_coverage>.add-path-map",
                    "<code_coverage>.clear-path-maps"],
        doc = """

List path maps that has been added with the <cmd
class="code_coverage">add-path-map</cmd> command.

The returned value is a list with two elements per entry:<br/>
<tt>[[from path, to path,]*]</tt>

""")

def add_filter_mappings_command(code_coverage):
    cli.new_command(
        'filter-mappings', filter_mappings,
        [cli.arg(cli.poly_t('filter', cli.list_t, cli.str_t, cli.uint_t),
                 'filter', '?', []),
         cli.arg(cli.poly_t('files', cli.list_t, cli.str_t), 'files', '?', []),
         cli.arg(cli.flag_t, '-remove')],
        cls = code_coverage.code_coverage.__name__,
        short = "filter out mappings or source files using a pattern",
        see_also = ["<code_coverage>.stop",
                    "<code_coverage>.add-source-info"],
        doc = """

By default, removes all mappings that do <b>not</b> match the pattern in
<arg>filter</arg> or source files that do <b>not</b> match
<arg>files</arg>. This command requires that code coverage collection is not
running.

If the <tt>-remove</tt> flag is used then mappings and source files that do
match <arg>filter</arg> and <arg>files</arg> will be removed instead.

The <arg>filter</arg>can be given in the following formats:
<ul>
<li>As the start address of the mapping: 0x44000</li>
<li>As an address range (written as a string): "0x44000-0x44fff". The last
address is included in the range. A mapping will match if the start address of
the mapping is in the range.</li>
<li>As a filename wildcard pattern (using *, ? or [seq]) for the symbol file of
the mapping: "mymodule-*.so" or "somedir/*dxe*.efi"</li>
<li>As a list where each element contains any of the previous formats:
[0x44000, "0x50000-0x55000", "dxe*.efi"]</li>
</ul>
The <arg>files</arg> filters on source files matching this argument and can be
given either as a string containing a filename wildcard pattern or as a list of
such patterns. Note that source info (see <cmd
class="code_coverage">add-source-info</cmd>) must have been added prior to
filtering on source files, otherwise source file information will not have been
added.

""")

def add_remove_unknown_addresses_command(code_coverage):
    cli.new_command(
        'remove-unknown-addresses', remove_unknown_addresses, [],
        cls = code_coverage.code_coverage.__name__,
        short = "remove unknown addresses",
        doc = "Removes any unknown addresses from the report.")

def add_list_mappings_command(code_coverage):
    cli.new_command(
        'list-mappings', list_mappings,
        [cli.arg(cli.flag_t, '-sort-by-file'),
         cli.arg(cli.flag_t, '-full-path')],
        cls = code_coverage.code_coverage.__name__,
        short = "list mappings",
        doc = """
Lists all mappings collected for the code coverage object on the format:<br/>
<tt>&lt;start address&gt;-&lt;end address&gt;: &lt;symbol file&gt;</tt>

The returned value is a list with three elements per entry:<br/>
<tt>[[start address, end address, symbol file]*]</tt>

The end address is included in the mapping.

The <tt>-sort-by-file</tt> flag can be used to sort the output by symbol file,
otherwise the list will be sorted by start address.

The <tt>-full-path</tt> flag specifies that the full path with directories
should be included in the output, otherwise just the file name will be
included.
""")

def add_combine_mappings_command(code_coverage):
    cli.new_command(
        'combine-mappings', combine_mappings,
        [],
        cls = code_coverage.code_coverage.__name__,
        see_also = ["<code_coverage>.add-report"],
        short = "combine matching mappings that have different addresses",
        doc = """

Combine mappings in the report that have the same symbol file, but are located
at different addresses.

When combining two or more mappings the combined mapping will get the
addresses of the mapping that has most covered instructions. If two or more
mappings have the same amount of covered instructions the first mapping (from
the 'mappings' list in the raw format) will be used for addresses of the
combined mapping.

""")

def add_commands():
    from . import code_coverage
    add_save_command(code_coverage)
    add_disass_command(code_coverage)
    add_functions_command(code_coverage)
    add_source_info_command(code_coverage)
    add_source_only_info_command(code_coverage)
    add_remove_analyzer_info_command(code_coverage)
    add_stop_command(code_coverage)
    add_html_report_command(code_coverage)
    add_lcov_report_command(code_coverage)
    add_csv_report_command(code_coverage)
    add_report_command(code_coverage)
    add_path_map_command(code_coverage)
    add_clear_path_maps_command(code_coverage)
    add_list_path_maps_command(code_coverage)
    add_filter_mappings_command(code_coverage)
    add_remove_unknown_addresses_command(code_coverage)
    add_list_mappings_command(code_coverage)
    add_combine_mappings_command(code_coverage)

def add_global_commands():
    add_collect_command()
    add_load_coverage_command()
