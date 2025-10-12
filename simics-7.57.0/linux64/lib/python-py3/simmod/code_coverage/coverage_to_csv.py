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


import csv
import argparse
import pickle

class CSVReportException(Exception):
    pass

def get_source_coverage_from_info(mapping, src_files):
    covered = mapping.get("covered", {})
    addr_infos = mapping.get("info", [])
    for addr_info in addr_infos:
        file_id = addr_info.get("file_id")
        if file_id is None:
            continue
        lines = addr_info.get("executable_lines")
        if lines is None:
            continue
        src_file = mapping["file_table"].get(file_id)
        src_lines = src_files.setdefault(src_file, {})
        for line in lines:
            line_cov = src_lines.setdefault(line, False)
            if line_cov:
                # Already marked as covered
                continue

            if addr_info.get("address") in covered:
                src_lines[line] = True

def addr_in_ranges(addr_ranges):
    for addr_range in addr_ranges:
        for addr in range(addr_range[0], addr_range[1]):
            yield addr

def get_source_coverage_from_src_info(mapping, src_files):
    covered = mapping.get("covered", {})
    src_info = mapping["src_info"]
    for (file_id, src_file_data) in src_info.items():
        src_file = mapping["file_table"].get(file_id)
        src_lines = src_files.setdefault(src_file, {})
        for (line, addr_ranges) in src_file_data.items():
            line_cov = src_lines.setdefault(line, False)
            if line_cov:
                continue
            for addr in addr_in_ranges(addr_ranges):
                if addr in covered:
                    src_lines[line] = True
                    break

def get_source_coverage(report):
    src_files = {}
    mappings = report.get("mappings", [])
    for mapping in mappings:
        if 'info' in mapping:
            get_source_coverage_from_info(mapping, src_files)
        elif 'src_info' in mapping:
            get_source_coverage_from_src_info(mapping, src_files)

    sorted_src_files = [(x, src_files[x]) for x in sorted(src_files.keys())]
    return sorted_src_files

def summarize_src_coverage(src_coverage):
    summary = []
    for (src_file, lines) in src_coverage:
        covered = 0
        total = 0
        for line_is_covered in lines.values():
            total += 1
            if line_is_covered:
                covered += 1
        summary.append([src_file, total, covered])
    return summary

def output_csv(report, output):
    src_coverage = get_source_coverage(report)
    if not src_coverage:
        raise CSVReportException('No source coverage found')
    summary = summarize_src_coverage(src_coverage)
    try:
        with open(output, "w", newline='') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerows(summary)
    except OSError as e:
        raise CSVReportException(e)

def main():
    parser = argparse.ArgumentParser(
        description='Report code coverage in csv format')
    parser.add_argument('--output', required=True, type=str)
    parser.add_argument('--report', required=True, type=str)

    args = parser.parse_args()

    with open(args.report, "rb") as f:
        report = pickle.load(f)  # nosec

    try:
        output_csv(report, args.output)
    except CSVReportException as e:
        parser.exit(1, '%s\n' % e)

if __name__ == "__main__":
    main()
