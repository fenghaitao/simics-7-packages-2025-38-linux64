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


import argparse
import copy
import os.path
import pickle
import sys

def append_branches(src_branches, dst_branches, offset):
    for (addr, taken_not_taken) in src_branches.items():
        addr += offset
        taken = taken_not_taken["taken"]
        not_taken = taken_not_taken["not_taken"]
        tnt = dst_branches.setdefault(addr, {"taken": 0, "not_taken": 0})
        tnt["taken"] += taken
        tnt["not_taken"] += not_taken

def append_count(src_covered, dst_covered, access_count, offset):
    for (addr, count) in src_covered.items():
        addr += offset
        dst_covered[addr] = dst_covered.get(addr, 0) + count
        if not access_count and dst_covered[addr] > 1:
            dst_covered[addr] = 1

def get_mappings_offset(dst, src, ignore_addresses):
    if not ignore_addresses:
        return 0
    # Return the offset needed to add to src in order for it to become
    # the same as dst.
    return dst["map"]["address"] - src["map"]["address"]

def combine_cpu_classes(dst, src):
    src_classes = src.get('cpu_classes', [])
    if not src_classes and not 'cpu_classes' in dst:
        return
    dst_classes = dst.setdefault('cpu_classes', [])
    for cpu_class in src_classes:
        if cpu_class not in dst_classes:
            dst_classes.append(cpu_class)

def add_to_entry(dst, src, access_count, branch_coverage, ignore_addresses):
    # Info should be the same in all files that have the same symbol
    # file at the same address. If addresses are ignored and the
    # destination does not have any info then we cannot copy from
    # source as that will have incorrect offsets in the disassembly.
    if ('info' in src and 'info' not in dst) and not ignore_addresses:
        dst['info'] = copy.deepcopy(src['info'])
        dst['file_table'] = copy.deepcopy(src['file_table'])
        if 'disassembly_class' in src:
            dst['disassembly_class'] = src['disassembly_class']

    # Copy source info if neither src_info nor info field is present in
    # dst, but src_info exists in src.
    # The src_info field is expected to be identical for mappings with the same
    # symbol file.
    if 'src_info' in src and (('src_info' not in dst) and ('info' not in dst)):
        dst['src_info'] = copy.deepcopy(src['src_info'])
        dst['file_table'] = copy.deepcopy(src['file_table'])

    combine_cpu_classes(dst, src)

    offset = get_mappings_offset(dst, src, ignore_addresses)
    if 'covered' in src:
        append_count(src['covered'], dst.setdefault('covered', {}),
                     access_count, offset)
    if branch_coverage:
        src_branches = src.get("branches")
        if src_branches:
            dst_branches = dst.setdefault('branches', {})
            append_branches(src_branches, dst_branches, offset)
    else:
        # Remove any previous branch coverage data, both reports must have
        # branch coverage feature enabled in order for the combined report to
        # get correct branch coverage data.
        if 'branches' in dst:
            dst.pop('branches')

def mappings_are_equal(mapping1, mapping2, ignore_addresses):
    if not ignore_addresses:
        return mapping1 == mapping2
    m1 = mapping1.copy()
    m1.pop("address")
    m1.pop("relocation")
    m2 = mapping2.copy()
    m2.pop("address")
    m2.pop("relocation")
    return m1 == m2

def index_of_map(mappings, mapping):
    for (index, m) in enumerate(mappings):
        if mappings_are_equal(m['map'], mapping['map'], False):
            return index
    return None

def get_combinable_mapping_indexes(mappings):
    combinable = []
    handled = set()
    for (i, m1) in enumerate(mappings):
        if i in handled:
            continue
        curr_comb = [i]
        handled.add(i)
        for (j, m2) in enumerate(mappings):
            if j in handled:
                continue
            if mappings_are_equal(m1["map"], m2["map"], True):
                curr_comb.append(j)
                handled.add(j)
        combinable.append(curr_comb)
    return combinable

def join_mappings_ignoring_addresses(mappings, access_count, branch_coverage):
    indexes_to_delete = set()
    for comb in get_combinable_mapping_indexes(mappings):
        if len(comb) < 2:
            continue

        # Keep mapping with most covered instructions, if mappings have equal
        # amount of covered instructions then take first. Other criteria of
        # which mapping to keep could be added here.
        dest_i = comb[0]
        max_cov = 0
        for i in comb:
            curr_cov = len(mappings[i].get("covered", []))
            if curr_cov > max_cov:
                max_cov = curr_cov
                dest_i = i

        # Combine mappings into the destination index specified above
        comb.remove(dest_i)
        dest_map = mappings[dest_i]
        for src_i in comb:
            src_map = mappings[src_i]
            add_to_entry(dest_map, src_map, access_count, branch_coverage, True)
            indexes_to_delete.add(src_i)

    nr_to_remove = len(indexes_to_delete)
    indexes_to_delete = sorted(indexes_to_delete, reverse=True)
    for i in indexes_to_delete:
        mappings.pop(i)
    return nr_to_remove

def is_feature_enabled(report, feature):
    return report.get('features', {}).get(feature, False)

def combine_feature(report_dest, report_new, feature):
    enabled = (is_feature_enabled(report_new, feature)
               and is_feature_enabled(report_dest, feature))
    if not enabled:
        report_dest['features'][feature] = False

# The destination report will be updated
def combine_two(report_dest, report_new, ignore_addresses):
    for feature in ('access_count', 'branch_coverage'):
        combine_feature(report_dest, report_new, feature)
    access_count = is_feature_enabled(report_dest, 'access_count')
    branch_coverage = is_feature_enabled(report_dest, 'branch_coverage')

    # We don't do any specific handling of the keep_data feature, meaning that
    # the -no-data-labels flag has been given to a add-functions or html-report
    # command. We say that if any of the reports has been created with such a
    # flag then the new report has that feature set. We don't insert the
    # 'keep_data' feature in 'features' when the report has it disabled, that is
    # why it is handled separately from the combining above.
    if (is_feature_enabled(report_dest, 'keep_data')
        or is_feature_enabled(report_new, 'keep_data')):
        report_dest['features']['keep_data'] = True

    if 'unknown' in report_new:
        unknown_in_dest = report_dest.setdefault('unknown', {})
        new_unknown = report_new['unknown']
        append_count(new_unknown, unknown_in_dest, access_count, 0)

    if 'unknown_branches' in report_new:
        unknown_br_in_dest = report_dest.setdefault('unknown_branches', {})
        new_unknown_br = report_new['unknown_branches']
        append_branches(new_unknown_br, unknown_br_in_dest, 0)

    combine_cpu_classes(report_dest, report_new)

    for map_kind in ('mappings', 'unknown_mappings'):
        for mapping in report_new.get(map_kind, []):
            dest_mappings = report_dest.setdefault(map_kind, [])
            index = index_of_map(dest_mappings, mapping)
            if index is None:
                dest_mappings.append(mapping)
            else:
                add_to_entry(dest_mappings[index], mapping, access_count,
                             branch_coverage, False)

    if ignore_addresses:
        # Ignore addresses is used to combine the same module loaded at
        # different addresses. This is not possible for unknown mappings as we
        # can't tell if the modules are the same or not.
        join_mappings_ignoring_addresses(report_dest.get("mappings", []),
                                         access_count, branch_coverage)

def log_progress(text):
    sys.stdout.write('\r%s' % text)
    sys.stdout.flush()

def main():
    parser = argparse.ArgumentParser(
        description='Combine Simics code coverage reports')
    parser.add_argument('--reports', required=True, nargs="*", type=str,
                        help='list of reports to combine, separated by spaces')
    parser.add_argument('--output', required=True, type=str,
                        help='combined reports file')
    parser.add_argument('--ignore-addresses', action='store_true',
                        help='combine mappings with different'
                        ' addresses but all other properties being the same,'
                        ' using the address from the first report')

    args = parser.parse_args()
    if args.reports is None or len(args.reports) == 0:
        parser.error("Must specify at least one report")

    if len(args.reports) == 1 and not args.ignore_addresses:
        parser.error("Must specify at least two reports to combine or use the"
                     " --ignore-addresses option.")
    reports = []
    for (index, report) in enumerate(args.reports):
        if not os.path.exists(report):
            parser.error("File %s does not exist" % report)
        with open(report, "rb") as f:
            try:
                log_progress("Loading file %d / %d (%s)"
                             % (index + 1, len(args.reports), report))
                data = pickle.load(f)  # nosec
            except pickle.PickleError as e:
                parser.error("Could not read %s: %s" % (report, e))
            reports.append(data)
    print("")

    report1 = reports[0]
    if len(reports) == 1:
        assert args.ignore_addresses
        log_progress("Combining mapping data")
        join_mappings_ignoring_addresses(report1["mappings"],
                                         is_feature_enabled(report1,
                                                            'access_count'),
                                         is_feature_enabled(report1,
                                                            'branch_coverage'))
    else:
        for (index, report2) in enumerate(reports[1:]):
            log_progress("Combining report %d / %d" % (index + 2, len(reports)))
            combine_two(report1, report2, args.ignore_addresses)
    print("")

    try:
        out_file = open(args.output, "wb")
    except IOError as e:
        parser.error("Could not write output %s: %s" % (args.output, e))

    print("Saving raw report to %s" % args.output)
    pickle.dump(report1, out_file, pickle.HIGHEST_PROTOCOL)
    out_file.close()

if __name__ == "__main__":
    main()
