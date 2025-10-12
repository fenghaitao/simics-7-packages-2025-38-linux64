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
import os.path
import fnmatch
import sys

is_python2 = sys.version_info[0] == 2

if is_python2:
    import cPickle as pickle
else:
    import pickle

def file_matches_pattern(filename, pattern):
    filename = filename.replace("\\", "/")
    pattern = pattern.replace("\\", "/")

    absolute_path = pattern.startswith("/")
    if not absolute_path and "/" in filename:
        if not pattern.startswith("*"):
            pattern = "*/" + pattern

    if fnmatch.fnmatch(filename, pattern):
        return True
    return False

def find_entries_to_remove(to_remove_per_map, remove):
    if not to_remove_per_map:
        return []
    if remove:
        combined = set()
        for to_remove in to_remove_per_map:
            combined |= set(to_remove)
        return sorted(combined)

    # Must be in all mappings in order to remove
    if len(to_remove_per_map) == 1:
        return to_remove_per_map[0]

    to_remove = []
    for i in to_remove_per_map[0]:
        in_all = True
        for mapping in to_remove_per_map[1:]:
            if i not in mapping:
                in_all = False
        if in_all:
            to_remove.append(i)
    return to_remove

def get_addr_range(possible_addr_range):
    assert isinstance(possible_addr_range, str)
    ranges = possible_addr_range.split("-")
    if len(ranges) != 2:
        return None

    addr_range = []
    for addr_str in ranges:
        try:
            addr = int(addr_str, 0)
        except ValueError:
            return None
        addr_range.append(addr)
    return addr_range

def filter_maps(mappings, map_filters, remove):
    assert map_filters
    assert mappings
    removed_files = 0
    to_remove_per_map = []
    for map_filter in map_filters:
        to_remove_for_map = []
        is_addr = not isinstance(map_filter, str)
        addr_range = None
        if not is_addr:
            addr_range = get_addr_range(map_filter)
        for (i, mapping) in enumerate(mappings):
            curr_map = mapping["map"]
            found = False
            if is_addr:
                if curr_map.get("address") == map_filter:
                    found = True
            elif addr_range is not None:
                curr_addr = curr_map.get("address")
                if addr_range[0] <= curr_addr <= addr_range[1]:
                    found = True
            else:
                filename = curr_map.get("symbol_file")
                if not filename:
                    continue
                if file_matches_pattern(filename, map_filter):
                    found = True
            if (remove and found) or (not remove and not found):
                to_remove_for_map.append(i)
        to_remove_per_map.append(to_remove_for_map)

    to_remove = find_entries_to_remove(to_remove_per_map, remove)

    # Remove in reverse order so that the indexes in to_remove are
    # the same as they were when collected.
    to_remove.reverse()
    for i in to_remove:
        old_mapping = mappings.pop(i)
        removed_files += len(old_mapping.get('file_table', {}))
    return (len(to_remove), removed_files)

def filter_files(mappings, file_filters, remove):
    assert file_filters
    assert mappings
    nr_removed = 0
    maps_to_remove = []
    for (i, mapping) in enumerate(mappings):
        matching_file_ids = set()
        file_table = mapping.get('file_table', {})
        for file_filter in file_filters:
            for file_id in file_table:
                if file_matches_pattern(file_table[file_id], file_filter):
                    matching_file_ids.add(file_id)
        for file_id in list(file_table.keys()):
            if remove and file_id in matching_file_ids:
                nr_removed += 1
                file_table.pop(file_id)
                continue
            if not remove and file_id not in matching_file_ids:
                nr_removed += 1
                file_table.pop(file_id)

        if len(file_table) == 0:
            # There could potentially be cases where there still exist info or
            # other data in the mapping even though all associated files are
            # removed. We have chosen to remove the whole mapping in those
            # cases, this could change to be optional if there is a use case.
            maps_to_remove.append(i)
        else:
            infos = mapping.get('info', [])
            filtered_info = []
            removed_addrs = []
            for info in infos:
                if 'file_id' in info:
                    if info['file_id'] not in file_table:
                        removed_addrs.append(info['address'])
                        continue
                elif not remove:
                    # Remove entries not associated with any file if only
                    # certain files are being kept.
                    removed_addrs.append(info['address'])
                    continue
                filtered_info.append(info)
            # If nothing was removed then no need to updated info.
            if removed_addrs:
                mapping['info'] = filtered_info
            for addr in removed_addrs:
                # Remove address from various places.
                for data_structure in ('functions', 'covered', 'branches',
                                       'data_labels', 'removed_data'):
                    mapping.get(data_structure, {}).pop(addr, None)

    maps_removed = 0
    for i in reversed(maps_to_remove):
        maps_removed += 1
        mappings.pop(i)

    return (maps_removed, nr_removed)

def filter_mappings(report, map_filters, file_filters, remove):
    assert map_filters or file_filters
    mappings = report.get("mappings")
    if not mappings:
        return (0, 0)
    maps_removed = 0
    files_removed = 0
    if map_filters:
        (maps_removed, files_removed) = filter_maps(
            mappings, map_filters, remove)
    if not mappings:
        return (maps_removed, files_removed)
    if file_filters:
        (nr_maps_removed, files_removed) = filter_files(
            mappings, file_filters, remove)
        maps_removed += nr_maps_removed
    return (maps_removed, files_removed)

def int_strings_to_ints(input_filters):
    if input_filters is None:
        return None
    output_filters = []
    for map_filter in input_filters:
        if isinstance(map_filter, str):
            try:
                map_filter = int(map_filter, 0)
            except ValueError:
                pass
        output_filters.append(map_filter)
    return output_filters

def remove_unknown_addresses(report):
    if not 'unknown' in report:
        return 0
    unknown_addrs_removed = len(report['unknown'])
    del report['unknown']
    return unknown_addrs_removed

def main():
    parser = argparse.ArgumentParser(
        description='Filter out mappings from code coverage report.'
        ' Filter matching the given filter will be kept unless the --remove'
        ' flag is given')
    parser.add_argument('--report', required=True, type=str,
                        help='the raw code coverage report to filter out'
                        ' mappings from')
    parser.add_argument('--filters', required=False, nargs="*", type=str,
                        help='list of filters, separated by spaces')
    parser.add_argument('--files', required=False, nargs="*", type=str,
                        help='list of files, separated by spaces, to keep or'
                        ' remove from available mappings')
    parser.add_argument('--replace', action='store_true',
                        help='replace the input file with the filtered data')
    parser.add_argument('--output', type=str,
                        help='new report file with filtered data, use'
                        ' --replace to replace the input file instead of'
                        ' creating a new file')
    parser.add_argument('--overwrite', action='store_true',
                        help='overwrite existing output file if it exists, not'
                        ' needed when --replace is used')
    parser.add_argument('--remove', action='store_true',
                        help='remove mappings matching filter instead of'
                        ' keeping them')
    parser.add_argument('--remove-unknown-addrs', action='store_true',
                        help='remove unknown addresses from report')

    args = parser.parse_args()

    if not args.replace and not args.output:
        parser.error("Either --output or --replace must be provided")

    if args.replace and args.output:
        parser.error("Only one of --output and --replace can be provided")

    if not os.path.exists(args.report):
        parser.error("File %s does not exist" % args.report)

    if not (args.filters or args.files or args.remove_unknown_addrs):
        parser.error("At least one of --filters, --files or"
                     " --remove-unknown-addrs must be provided")

    if args.replace:
        outfile = args.report
    else:
        outfile = args.output
        if not args.overwrite and os.path.exists(outfile):
            parser.error("File already exists: %s" % outfile)

    with open(args.report, "rb") as f:
        try:
            print("Reading report: %s" % args.report)
            report = pickle.load(f)  # nosec
        except pickle.PickleError as e:
            parser.error("Could not read %s: %s" % (args.report, e))

    if args.filters or args.files:
        (nr_removed, nr_files_removed) = filter_mappings(
            report, int_strings_to_ints(args.filters), args.files, args.remove)
    if args.remove_unknown_addrs:
        unknown_addrs_removed = remove_unknown_addresses(report)
    try:
        f = open(outfile, "wb")
    except IOError as e:
        parser.error("Could not write output %s: %s" % (outfile, e))

    print("Saving report: %s" % outfile)
    pickle.dump(report, f, pickle.HIGHEST_PROTOCOL)
    f.close()

    if args.filters or args.files:
        print("Removed %d mappings" % nr_removed)
        print("Removed %d files from mappings" % nr_files_removed)
    if args.remove_unknown_addrs:
        print("Removed %d unknown addresses" % unknown_addrs_removed)

if __name__ == "__main__":
    main()
