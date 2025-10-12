# © 2019 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# The format of the LCOV tracefile is documented in the man page of geninfo,
# see "man geninfo" or  https://linux.die.net/man/1/geninfo for example.


import argparse
import os.path
import pickle

class LCOVReportException(Exception):
    pass

class CounterOptions:
    # 1 for both functions and lines
    All_1 = 0
    # 1 for lines but count of first instruction for function.
    Lines_1 = 1
    # Count for line is the instruction that has run most in that line. For
    # function this is the count of the first instruction.
    Most_Run = 2
    # Count of first instruction of both line and function.
    First_Insn = 3

def get_unique_map_id(data, known_ids):
    symbol_file_name = data["map"].get("symbol_file", "unknown")
    # Replace backward slashes with forward slashes on hosts with forward slash
    # separators. On Windows os.path methods handles both forward and backward
    # slashes as separators so no need to replace slashes there.
    if os.path.sep == '/':
        symbol_file_name = symbol_file_name.replace('\\', '/')
    map_id = os.path.basename(symbol_file_name + "_%x" % data["map"]["address"])
    if map_id in known_ids:
        # Find a unique id.
        i = 1
        org_map_id = map_id
        while map_id in known_ids:
            map_id = org_map_id + "_%d" % i
            i += 1

    return map_id

def get_source_coverage_from_info(mapping, counter_option):
    src_data = {}
    functions = mapping.get("functions", {})
    covered = mapping.get("covered", {})
    addr_infos = mapping["info"]
    for addr_info in addr_infos:
        file_id = addr_info.get("file_id")
        if file_id is None:
            continue
        lines = addr_info.get("executable_lines")
        if lines is None:
            continue
        addr = addr_info["address"]
        src_file = mapping["file_table"].get(file_id)
        curr_data = src_data.setdefault(src_file, {})
        src_lines = curr_data.setdefault("lines", {})
        src_funcs = curr_data.setdefault("functions", {})
        for line in lines:
            line_cov = src_lines.setdefault(line, None)
            addr_cov = covered.get(addr, 0)
            if counter_option == CounterOptions.First_Insn:
                if line_cov is not None:
                    # Line already handled.
                    continue
                src_lines[line] = addr_cov
            elif counter_option in [CounterOptions.All_1,
                                    CounterOptions.Lines_1]:
                if line_cov:
                    continue
                src_lines[line] = 1 if addr_cov else 0
            else:
                assert counter_option == CounterOptions.Most_Run
                if line_cov is None or addr_cov > line_cov:
                    src_lines[line] = addr_cov

        if addr in functions and len(lines) > 0:
            fn_coverage = covered.get(addr, 0)
            if counter_option == CounterOptions.All_1 and fn_coverage > 1:
                fn_coverage = 1
            f_data = {"name": functions[addr]["name"],
                      "line": list(lines.keys())[0],
                      "coverage": fn_coverage}
            src_funcs[addr] = f_data
    return src_data

def addr_in_ranges(addr_ranges):
    for addr_range in addr_ranges:
        for addr in range(addr_range[0], addr_range[1]):
            yield addr

def get_source_coverage_from_src_info(mapping, counter_option):
    src_data = {}
    src_info = mapping['src_info']
    covered = mapping.get('covered', {})
    functions = mapping.get("functions", {})
    for (file_id, src_file_data) in src_info.items():
        src_file = mapping["file_table"].get(file_id)
        curr_data = src_data.setdefault(src_file, {})
        src_lines = curr_data.setdefault("lines", {})
        src_funcs = curr_data.setdefault("functions", {})
        for (line, addr_ranges) in src_file_data.items():
            if len(addr_ranges) == 0:
                continue
            src_lines.setdefault(line, 0)
            if counter_option == CounterOptions.First_Insn:
                src_lines[line] = covered.get(addr_ranges[0][0], 0)
            elif counter_option in [CounterOptions.All_1,
                                    CounterOptions.Lines_1]:
                for addr_range in addr_ranges:
                    if src_lines.get(line, 0) > 0:  # Found in loop
                        break
                    for addr in addr_range:
                        if addr in covered:
                            src_lines[line] = 1
                            break
            else:
                assert counter_option == CounterOptions.Most_Run
                line_cov = 0
                for addr in addr_in_ranges(addr_ranges):
                    line_cov = max(line_cov, covered.get(addr, 0))

            for addr in addr_in_ranges(addr_ranges):
                if addr in functions:
                    fn_coverage = covered.get(addr, 0)
                    if (counter_option == CounterOptions.All_1
                        and fn_coverage > 1):
                        fn_coverage = 1
                    f_data = {"name": functions[addr]["name"],
                              "line": line, "coverage": fn_coverage}
                    src_funcs[addr] = f_data

    return src_data

def get_source_coverage(report, counter_option):
    mappings = report.get("mappings", [])
    res = {}
    for mapping in mappings:
        map_id = get_unique_map_id(mapping, res)
        if 'info' in mapping:
            src_data = get_source_coverage_from_info(mapping, counter_option)
        elif 'src_info' in mapping:
            src_data = get_source_coverage_from_src_info(mapping,
                                                         counter_option)
        else:
            continue
        res[map_id] = src_data
    return res

def write_functions_data(f, src_data):
    fns_data = src_data.get("functions", {})
    total_fun = 0
    total_fun_covered = 0
    for da in (False, True):   # First write all FN then all FNDA
        for fn_data in fns_data.values():
            if da:
                total_fun += 1
                coverage = fn_data["coverage"]
                f.write("FNDA:%d,%s\n" % (coverage, fn_data["name"]))
                if coverage > 0:
                    total_fun_covered += 1
            else:
                f.write("FN:%d,%s\n" % (fn_data["line"], fn_data["name"]))
    f.write("FNF:%d\nFNH:%d\n" % (total_fun, total_fun_covered))

def write_line_data(f, src_data):
    total_lines = 0
    covered_lines = 0
    lines_data = src_data.get("lines", {})
    for (line, coverage) in lines_data.items():
        f.write("DA:%d,%d\n" % (line, coverage))
        total_lines += 1
        if coverage > 0:
            covered_lines += 1
    f.write("LH:%d\nLF:%d\n" % (covered_lines, total_lines))

def path_mapped_src_file(org_src_file, path_maps):
    # If file is found when applying pathmap, return the updated file name.
    # Otherwise, return the input file name.
    for (src, dst) in path_maps:
        while src.endswith("/") or src.endswith("\\"):
            src = src[:-1]
        while dst.endswith("/") or dst.endswith("\\"):
            dst = dst[:-1]
        if org_src_file.startswith(src):
            new_src_file = org_src_file.replace(src, dst, 1)
            if os.path.exists(new_src_file):
                return os.path.abspath(new_src_file)
            # Try replacing slashes with path separator for the OS.
            new_src_file = new_src_file.replace("\\", os.path.sep).replace(
                "/", os.path.sep)
            if os.path.exists(new_src_file):
                return os.path.abspath(new_src_file)
    return org_src_file

def write_lcov_data(f, data, path_maps):
    for (src_file, src_data) in data.items():
        f.write("TN:\n")  # No test name
        f.write("SF:%s\n" % path_mapped_src_file(src_file, path_maps))
        write_functions_data(f, src_data)
        write_line_data(f, src_data)
        f.write("end_of_record\n")

def option_str_to_value(option_str):
    options = {"one": CounterOptions.Lines_1,
               "all_one": CounterOptions.All_1,
               "most": CounterOptions.Most_Run,
               "first": CounterOptions.First_Insn}
    option = options.get(option_str)
    if option is None:
        raise LCOVReportException("Bad counter option %s" % option_str)
    return option

def output_lcov(report, output_dir, path_maps, counter_option_str):
    if os.path.exists(output_dir):
        raise LCOVReportException(
            'Target output directory "%s" already exists' % output_dir)

    counter_option = option_str_to_value(counter_option_str)
    src_coverage = get_source_coverage(report, counter_option)
    if not src_coverage:
        return 0

    try:
        os.makedirs(output_dir)
    except OSError as e:
        raise LCOVReportException(e)

    outputted_files = []
    for (map_id, data) in src_coverage.items():
        filename = os.path.join(output_dir, map_id)
        try:
            with open(filename, "w") as f:
                write_lcov_data(f, data, path_maps)
        except OSError as e:
            raise LCOVReportException(e)
        outputted_files.append(filename)

    return outputted_files

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
Report code coverage in lcov tracefile format.

The output will be one LCOV formatted tracefile for each mapping in the report,
outputted to the specified output directory. The naming of the tracefiles will
be the name of the mapping's symbol file plus a suffix with an underscore and
the address of the mapping in hex, for example "program_400000".""",
        epilog="""
As the binaries are not instrumented the number of times a line has been
executed might not always be accurate. The user has the option to specify how
the counting of how many times a line has been executed should be done, using
the --counter-option argument. It has the following options:
"all_one": Always one, for both functions and lines.
"one": One for lines. For functions the number of times the first instruction
       has been executed (default).
"most": Times run for the instruction that has executed most times for the
        line.
"first": Times the first instruction of the line has executed.

In order for any of these options to display more than one executed line or
function the code coverage report must have been collected with the
-access-count option.
""")

    parser.add_argument('--output', required=True, type=str,
                        help="the lcov tracefile to output")
    parser.add_argument('--report', required=True, type=str,
                        help="the raw code coverage report from which to"
                        " create a tracefile from")
    parser.add_argument('--path-maps', required=False, nargs="+",
                        help="a list of path mapping pairs (from, to) to apply"
                        " to source files to update path from compiled path to"
                        " location on disk")
    parser.add_argument('--counter-option', type=str, default="one",
                        choices=["one", "all_one", "most", "first"],
                        help="options for displaying number of times a line has"
                        " executed, see details below")

    args = parser.parse_args()
    path_maps = []
    if args.path_maps:
        if len(args.path_maps) % 2:
            parser.error("Must have matching number of path map entries")
        for i in range(0, len(args.path_maps), 2):
            path_maps.append([args.path_maps[i], args.path_maps[i + 1]])

    with open(args.report, "rb") as f:
        report = pickle.load(f)  # nosec

    try:
        outputted_files = output_lcov(report, args.output, path_maps,
                                      args.counter_option)
    except LCOVReportException as e:
        parser.exit(1, "%s\n" % e)

    if outputted_files == 0:
        parser.exit(1, "No source information found in report\n")

if __name__ == "__main__":
    main()
