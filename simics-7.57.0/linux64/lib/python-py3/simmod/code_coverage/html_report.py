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
import pickle

import contextlib
import os
import io
import json
import bisect

def cc_information_text():
    return """
<h3>Information:</h3>
<dl>
<dt>Unknown addresses</dt>
<dd><em>Unknown addresses</em> corresponds to executed instructions in a
memory area where there was no known memory mapping.</dd>

<dt>Path maps</dt>
 <dd>If the software was not built on the computer doing the code coverage
analysis you may have to add <em>path maps</em> in order for the system to
locate source files and binaries.</dd>

<dt>Function coverage</dt>
<dd>A function is considered to have run as many times as the instruction, that
is located at the same address as the function, has run. If coverage is
collected without access count, the times a function has been hit will be one
time regardless of how many times it has run.</dd>

<dt>Disassembly without source mapping</dt>
<dd>Disassembly of instructions that do not have any source will be put under a
section named <em>Disassembly without any source mapping</em> instead of under a
section for the corresponding source file. That section will be excluded if the
<tt>-only-addresses-with-source</tt> flag is used when creating the report.</dd>

<dt>Function padding</dt>
<dd>A function named <em>&lt;function padding&gt;</em> can be present in the
disassembly summary. This will contain all instructions that are considered as
padding; instructions beyond the function length or instructions that lack
source map for a function that otherwise has source map. The coverage for such
instructions are gathered under <em>&lt;function padding&gt;</em>. The actual
instructions will be shown in the report as part of the function for which the
instructions are padding for, after a separator.</dd>

<dt>Removed data</dt>
<dd>Code coverage will try to remove parts of the executable section that is
placed under a label that is known to be data. This label is expected to end
once there is a new function for an address. The <tt>-no-data-labels</tt> can be
used, when creating a report, to keep all symbols as functions instead of trying
to filter out known data labels. All address ranges and their corresponding
symbols will be displayed under the <em>Removed data</em> page if any parts of
the section has been removed.</dd>

</dl>
"""

def cc_limitations_text(fmt_html):
    return """
%s
<dl>
<dt>Disassembly</dt>
<dd>
Disassembly is done per executable section, starting at the first address
of each function and taking instruction by instruction until the next function
or end of section. If function information is not available then disassembly
will be done from the beginning of the section to the end of the section
instead. The latter behavior can be forced by using the
<tt>-whole-section</tt> flag with the <em>disassemble</em> command.  Data in
the executable section may corrupt the disassembly, especially for variable
length instruction platforms, as this data is also treated as instructions and
disassembled. Disassembly will be performed on data from the original
executable file, so any code that is modified in memory (compressed code as an
example) will not be reflected in the report. Code that is not part of any
executable section, will not be included in the report.
</dd>

<dt>Sections</dt>
<dd>
When disassembling an executable section, it is assumed that the executable
section has the same architecture for the entire mapping, this is taken from
the binary. Code that mixes different processor modes, 16, 32 and 64 bit for
example, may therefore end up with incorrect disassembly.
</dd>

<dt>PDB format</dt>
<dd>
PDB symbol information is only supported on Microsoft* Windows*.
</dd>

<dt>Quality</dt>
<dd>
This code coverage implementation is purely based on available debug
information and does not require modifications to the binary. This means that
the executable source lines and executed source lines information depends
highly on the quality of debug information. Usually this improves by decreasing
optimization level. Due to inlining of functions and various optimizations the
source coverage may be hard to interpret.
</dd>

<dt>Architectures</dt>
<dd>
For disassembly, only classes that implement the
<iface>class_disassembly</iface> interface plus x86 and ARM families are
supported. Other architectures where the processor model supports
instrumentation, source only coverage can be output.

When disassembling without the <iface>class_disassembly</iface> interface, some
instructions that were added in recent architectures might not be disassembled
correctly in the disassembly report.
</dd>
<dt>Reverse Execution</dt>
<dd>
The code coverage implementation does not support reverse execution.
</dd>
<dt>VMP</dt>
<dd>
VMP will not be engaged while code coverage is collecting data.
</dd>

<dt>Branch coverage</dt> <dd>
<dd>
This is only for disassembly output, source level branch coverage is not
supported.

It's only supported by a subset of processor models. An error message will be
displayed when attempted to use with an unsupported architecture.
</dd>

<dt>ARM branch coverage</dt>
<dd>
For branch coverage on ARM only <tt>B&lt;cond&gt;</tt>, <tt>CBZ</tt>,
<tt>CBNZ</tt>, <tt>TBZ</tt> and <tt>TBNZ</tt> instructions are handled. Any
other conditional instructions, including <tt>BL</tt>, <tt>BX</tt> and similar
are not included in branch coverage. Neither are Thumb instructions made
conditional by an IT-block handled by branch coverage.
</dd>
<dt>x86 16-bit real mode</dt>
<dd>
Instructions in 16-bit real mode will be disassembled as 32-bit
instructions. This is because the ELF header or sections do not have any
information about 16-bit mode. This can result in that both disassembly and
source coverage for 16-bit real mode code gets incorrect.
</dd>
</dl>
""" % ("<h3>Limitations:</h3>" if fmt_html else "",)

class HTMLReportException(Exception):
    pass

def looks_like_windows_path(file_name):
    if file_name.find(':\\') >= 0:
        return True
    if file_name.find('\\') >= 0 and file_name.find('/') < 0:
        return True
    return False

def start_of_path_matches(file_name, src_path, ignore_case):
    if ignore_case:
        file_name = file_name.lower()
        src_path = src_path.lower()
    return file_name.startswith(src_path)

def path_map(tcf, file_name, path_maps):
    ignore_case = looks_like_windows_path(file_name)
    # If file exist return it.
    # If file is found when applying pathmap, return the updated file name.
    # Otherwise, return the input file name.
    for (src, dst) in path_maps:
        while src.endswith("/") or src.endswith("\\"):
            src = src[:-1]
        while dst.endswith("/") or dst.endswith("\\"):
            dst = dst[:-1]
        if start_of_path_matches(file_name, src, ignore_case):
            new_name = dst + file_name[len(src):]
            new_name_norm = os.path.normpath(new_name)
            # We want to keep any initial './' or '.\' in the report, normpath
            # will remove such from the path. But always use the host system
            # separator type so that we do not get './' on Windows.
            if (len(new_name) >= 2
                and (new_name[0] == '.' and new_name[1] in ('/', '\\'))):
                new_name = '.' + os.path.sep + new_name_norm
            else:
                new_name = new_name_norm
            if os.path.exists(new_name):
                return new_name
            new_name = new_name.replace("\\", "/")
            if os.path.exists(new_name):
                return new_name
    return file_name

@contextlib.contextmanager
def open_or_raise_ccerror(filename, mode = 'r', custom_err_msg = None):
    try:
        f = open(filename, mode)
    except IOError as e:
        err_msg = custom_err_msg if custom_err_msg else str(e)
        raise HTMLReportException(err_msg)
    else:
        try:
            yield f
        finally:
            f.close()

class Mangler:
    def __init__(self):
        self.__map = {}
        self.__used = set()
        self.file_length = 16
        self.counter = -1
    def mangle(self, filename):
        mangled = self.__map.get(filename)
        if not mangled:
            s = ''
            # Don't allow first char to be a dot (the "." char).
            replacing_initial_dots = True
            # Only use the last 'file_length' characters as too long names may
            # hit path limit on Windows
            for c in filename[-self.file_length:]:
                if c == "." and replacing_initial_dots:
                    s += "_"
                    continue
                replacing_initial_dots = False

                if c in ('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
                         '0123456789-_.'):
                    s += c
                else:
                    s += '_'
            mangled = s
            while mangled in self.__used:
                self.counter += 1
                mangled = "%s%d" % (s, self.counter)
            self.__used.add(mangled)
            self.__map[filename] = mangled
        return mangled

def js_sort_code():
    return """
function removeTags(str) {
  return str.replace(/<[^>]*>/g, "");
}

function intCommonSort(intColumn, a, b, use_hex) {
  var toFewCellsA = a.cells.length < intColumn + 1;
  var toFewCellsB = b.cells.length < intColumn + 1;
  if (toFewCellsA && toFewCellsB)
    return 0;
  if (toFewCellsA)
    return 1;
  if (toFewCellsB)
    return -1;

  var addrCellA = a.cells[intColumn];
  var addrCellB = b.cells[intColumn];

  var addrStrA = addrCellA.innerHTML;
  var addrStrB = addrCellB.innerHTML;

  var bits = 10;
  if (use_hex)
    bits = 16;
  var addrA = parseInt(addrStrA, bits);
  var addrB = parseInt(addrStrB, bits);

  if (isNaN(addrA) && isNaN(addrB))
    return 0;
  if (isNaN(addrA))
    return 1;
  if (isNaN(addrB))
    return -1;
  return addrA - addrB;
}

function addrSort(addressColumn, a, b) {
    return intCommonSort(addressColumn, a, b, true);
}

function intSort(intColumn, a, b) {
    // Use b, a order to get highest number at top the first sort.
    return intCommonSort(intColumn, b, a, false);
}

function nameSort(nameColumn, a, b) {
  var toFewCellsA = a.cells.length < nameColumn + 1;
  var toFewCellsB = b.cells.length < nameColumn + 1;
  if (toFewCellsA && toFewCellsB)
    return 0;
  if (toFewCellsA)
    return 1;
  if (toFewCellsB)
    return -1;

  var nameCellA = a.cells[nameColumn];
  var nameCellB = b.cells[nameColumn];

  var nameStrA = removeTags(nameCellA.innerHTML);
  var nameStrB = removeTags(nameCellB.innerHTML);

  return (nameStrA < nameStrB) ? -1 : (nameStrA > nameStrB) ? 1 : 0;
}

function covSort(coverageColumn, a, b) {
  var toFewCellsA = a.cells.length < coverageColumn + 1;
  var toFewCellsB = b.cells.length < coverageColumn + 1;
  if (toFewCellsA && toFewCellsB)
     return 0;
  if (toFewCellsA)
    return 1;
  if (toFewCellsB)
    return -1;

  var covCellA = a.cells[coverageColumn];
  var covCellB = b.cells[coverageColumn];

  var covStrA = removeTags(covCellA.innerHTML);
  var covStrB = removeTags(covCellB.innerHTML);
  var aArr = covStrA.split("/");
  var bArr = covStrB.split("/");
  if (aArr.length != 2) {
    // Can happen for error reports.
    if (bArr.length != 2)
      return 0;
    return -1;
  }
  if (bArr.length != 2) {
    // Can happen for error reports.
    return 1;
  }

  var covA = parseInt(aArr[0]);
  var totalA = parseInt(aArr[1]);
  var covB = parseInt(bArr[0]);
  var totalB = parseInt(bArr[1]);
  var notCoverageElemA = isNaN(covA) || isNaN(totalA);
  var notCoverageElemB = isNaN(covB) || isNaN(totalB);
  if (notCoverageElemA && notCoverageElemB)
    return 0;
  if (notCoverageElemA)
    return 1;
  if (notCoverageElemB)
    return -1;

  var percentA = totalA == 0 ? 100.0 : 100.0 * covA / totalA;
  var percentB = totalB == 0 ? 100.0 : 100.0 * covB / totalB;

  if (percentA < percentB)
    return -1
  if (percentA > percentB)
    return 1

  return totalA - totalB;
}

function errorSort(errorColumn, a, b) {
  var toFewCellsA = a.cells.length < errorColumn + 1;
  var toFewCellsB = b.cells.length < errorColumn + 1;
  if (toFewCellsA && toFewCellsB)
     return 0;
  if (toFewCellsA)
    return 1;
  if (toFewCellsB)
    return -1;

  var errorStrA = removeTags(a.cells[errorColumn].innerHTML);
  var errorStrB = removeTags(b.cells[errorColumn].innerHTML);
  if (errorStrA == errorStrB)
    return 0;
  return errorStrA > errorStrB ? 1 : -1;
}

function inverseSortDir() {
  if (sortDir == "descending") {
    sortDir = "ascending";
  } else {
    sortDir = "descending";
  }
}

function buttonHasArrow(button) {
  var arrowClasses = ["ascending", "descending", "not_sorted"];
  for (var i = 0; i < arrowClasses.length; i++) {
    if (button.classList.contains(arrowClasses[i]))
      return true;
  }
  return false;
}

function showSorting(header, column) {
  for (var i = 0; i < header.cells.length; i++) {
    buttons = header.cells[i].getElementsByTagName("button");
    if (buttons.length < 1)
      continue;
    button = buttons[0];
    if (!buttonHasArrow(button))
      continue;
    button.classList.remove("ascending", "descending", "not_sorted")
    if (i == column) {
      button.classList.add(sortDir);
    } else {
      button.classList.add("not_sorted");
    }
  }
}

function sortRows(rows, column) {
  var usedSort;
  if (sortDir == "ascending") {
    // Reversed order from what is in sort functions.
    usedSort = function(a, b) { return sortFun(column, b, a); };
  } else {
    usedSort = function(a, b) { return sortFun(column, a, b); };
  }
  rows.sort(usedSort);
}

var compareFunctions = {"address": addrSort, "name": nameSort,
                        "coverage": covSort, "error": errorSort,
                        "int": intSort};
function sortSummaryTable(newType, column, sort_two, id_str) {
  table = document.getElementById("summary_table" + id_str);
  var htmlRows = table.rows;
  var rows = [];
  var header = htmlRows[0];
  for (var i = 1; i < htmlRows.length; i++) {
    rows.push(htmlRows[i]);
  }
  sortFun = compareFunctions[newType];

  if (sort_two) {
    sortRows(rows, column + 1)
  }
  sortRows(rows, column)

  showSorting(header, column);
  rows.unshift(header);
  summaryTable = '';
  for (var i = 0; i < rows.length; i++)
    summaryTable += '<tr>' + rows[i].innerHTML + '</tr>';
  table.innerHTML = summaryTable;
}

function sortSummaryCommon(newType, column, sort_two, id_str = '') {
  if (sortType == newType) {
    inverseSortDir();
  } else {
    sortType = newType;
    sortDir = "descending";
  }
  sortSummaryTable(newType, column, sort_two, id_str);
}

function sortSummaryTableByAddr(addressCol) {
  sortSummaryCommon("address", addressCol, false);
}

function sortSummaryTableIdxByAddr(idx, addressCol) {
  sortSummaryCommon("address", addressCol, false, String(idx));
}

function sortSummaryTableByInt(intCol) {
  sortSummaryCommon("int", intCol, false);
}

function sortSummaryTableIdxByInt(idx, intCol) {
  sortSummaryCommon("int", intCol, false, String(idx));
}

function sortSummaryTableByName(nameCol) {
  sortSummaryCommon("name", nameCol, false);
}

function sortSummaryTableIdxByName(idx, nameCol) {
  sortSummaryCommon("name", nameCol, false, String(idx));
}

function sortSummaryTableByName2(nameCol) {
  sortSummaryCommon("name", nameCol, true);
}

function sortSummaryTableByCov(covCol) {
  sortSummaryCommon("coverage", covCol, false);
}

function sortSummaryTableByError(errorCol) {
  sortSummaryCommon("error", errorCol, false);
}

function hideOrUnhide(extra_id='') {
    var divToHide = document.getElementById("hideableDiv" + extra_id);
    var hideButton = document.getElementById("hideButton" + extra_id);
    hideButton.classList.remove("div_shown", "div_hidden");
    if (divToHide.style.display === "block" || divToHide.style.display === "") {
        divToHide.style.display = "none";
        hideButton.classList.add("div_hidden");
    } else {
        divToHide.style.display = "block";
        hideButton.classList.add("div_shown");
    }
}

function hideOrUnhideAll(do_hide) {
    const elems = document.querySelectorAll("*");
    let base_id = "hideableDiv"
    for (let i = 0; i < elems.length; i++) {
        let elem = elems[i];
        if (elem.id.startsWith(base_id)) {
            let is_hidden = elem.style.display == "none";
            if ((is_hidden && !do_hide) || (!is_hidden && do_hide)) {
                let extra_id = elem.id.substring(base_id.length);
                hideOrUnhide(extra_id);
            }
        }
    }
}

var sortDir = "undefined";
var sortType = "undefined";
"""

def js_mark_source_line_code():
    return """

function mark_source_line() {
    document.querySelectorAll('.lineno').forEach(
        function(line) { line.classList.remove('highlight_line'); });

     var hash = window.location.hash;
     if (!hash) {
         return;
     }
     var line = document.querySelector(hash);
     if (!line) {
         return;
     }
     line.classList.add('highlight_line')
}

window.addEventListener('load', mark_source_line);
window.addEventListener('hashchange', mark_source_line);
"""

def js_summary_code():
    return """
function get_expand_box(expanded, id) {
  id = "'" + id + "'";
  var box = '<button class="expand_box"'
  box += ' onClick="expand_or_collapse(' + id + ')">';
  if (expanded) {
    box += '-';
  } else {
    box += '+';
  }
  box += '</button>';
  return box;
}

function format_filename(fn, level, id, link, expanded, has_children,
                         full_path) {
  var td = '<td class="filename"';
  td += ' style="text-indent:'+ ((level - 1) * 20) + 'px"';
  td += ' id="' + id + '"';
  td += '>';
  if (has_children) {
    expand_box = get_expand_box(expanded, id) + '&nbsp';
  } else {
    expand_box = '';
  }
  if (link) {
    fn = '<a href="' + link + '">' + fn + '</a>';
  }
  if (full_path) {
    fn = ('<span class="path_tooltip">' + fn
          + '<span class="path_tooltip_text">' + full_path + '</span></span>')
  }
  return td + expand_box + fn + '</td>';
}

function format_lines(covered, total) {
  var elem = '<td class="count">'
  if (total == 0) {
    elem = '- / -';
  } else {
    elem += covered + ' / ' + total;
  }
  elem += '</td>';
  return elem;
}

function format_percentage(covered, total) {
  var elem = '<td class="percentage">';
  if (total == 0) {
    elem += 'N/A';
  } else {
    let pct = 100.0 * covered / total;
    elem += pct.toFixed(1) + '%';
  }
  elem += '</td>';
  return elem;
}

function format_row(elem, full_path) {
  var row = '<tr>';
  if ('link' in elem) {
    link = elem.link;
  } else {
    link = null;
  }
  row += format_filename(elem.dirname, elem.level, elem.id, link,
                         elem.expanded, elem.children.length > 0,
                         full_path);
  row += format_lines(elem.accumulated_covered, elem.accumulated_total);
  row += format_percentage(elem.accumulated_covered, elem.accumulated_total);
  row += '</tr>';
  return row;
}

function get_sort_dir_common(top_elem, name) {
  if (('sort_elem' in top_elem) && (top_elem.sort_elem == name)) {
    return top_elem.sort_dir;
  }
  return 'not_sorted';
}

function get_dir_sort(top_elem) {
  return get_sort_dir_common(top_elem, "dir")
}

function get_line_sort(top_elem) {
  return get_sort_dir_common(top_elem, "line")
}

function get_pct_sort(top_elem) {
  return get_sort_dir_common(top_elem, "pct")
}

function format_header(top_elem) {
  var line_sort = get_line_sort(top_elem);
  var pct_sort = get_pct_sort(top_elem);
  var dir_sort = get_dir_sort(top_elem);
  return ('<tr><th><button class="' + dir_sort + '"'
          + ' onClick="sort_by_dir()">Directory</button></th>'
          + '<th><button class="' + line_sort + '" onClick="sort_by_line()">'
          + 'Lines</button></th><th>'
          + '<button class="' + pct_sort + '" onClick="sort_by_pct()">'
          + 'Percentage</button></th></tr>');
}

function get_separator(path) {
  if (path.search('/') == -1) {
    return '\\\\';
  }
  return '/';
}

function make_html_table(elem, parent_path) {
  var output = '';
  var full_path = '';
  if (elem.level == 0) {
    output += format_header(elem);
  } else {
    if (elem.level == 1) {
      full_path = elem.dirname;
    } else {
      full_path = parent_path + get_separator(parent_path) + elem.dirname;
    }
    output += format_row(elem, full_path);
  }
  if (elem.expanded) {
    for (var i = 0; i < elem.children.length; i++) {
      output += make_html_table(elem.children[i], full_path);
    }
  }
  return output;
}

function update_summary_table_with_data(data) {
  var table_id = "summary_table";
  rows = make_html_table(data, "");
  document.getElementById(table_id).innerHTML = rows;
  check_coverage_data();
  if (coverage_data.org_widths == undefined) {
    set_org_widths(table_id);
  }
  update_summary_table_width(table_id);
}

function find_elem(start_elem, id) {
  if (id == start_elem.id) {
    return start_elem;
  }
  for (var i = 0; i < start_elem.children.length; i++) {
    var elem = find_elem(start_elem.children[i], id);
    if (elem) {
      return elem;
    }
  }
  return null;
}

function toggle_expanded(table, id) {
  elem = find_elem(table, id);
  if (!elem) {
    return;
  }
  elem.expanded = !elem.expanded;
}

function sort_children_by_dir(elem, ascending) {
  for (var i = 0; i < elem.children.length; i++) {
    sort_children_by_dir(elem.children[i], ascending);
  }
  if (ascending) {
    elem.children.sort(function(a, b) {
      return b.dirname.localeCompare(a.dirname);
    });
  } else {
    elem.children.sort(function(a, b) {
      return a.dirname.localeCompare(b.dirname);
    });
  }
}

function nr_sorter(a, b) {
  if (a > b) {
      return -1;
  }
  if (b > a) {
      return 1;
  }
  return 0;
}

function sort_children_by_line(elem, ascending) {
  for (var i = 0; i < elem.children.length; i++) {
    sort_children_by_line(elem.children[i], ascending);
  }
  elem.children
  if (ascending) {
    elem.children.sort(function(a, b) {
      return nr_sorter(a.accumulated_total, b.accumulated_total);
    });
  } else {
    elem.children.sort(function(a, b) {
      return nr_sorter(b.accumulated_total, a.accumulated_total);
    });
  }
}

function get_pct(elem) {
  if (elem.accumulated_total == 0)
    return 100.1;  // 100 should be max.
  return 100.0 * elem.accumulated_covered / elem.accumulated_total;
}

function sort_children_by_pct(elem, ascending) {
  for (var i = 0; i < elem.children.length; i++) {
    sort_children_by_pct(elem.children[i], ascending);
  }
  if (ascending) {
    elem.children.sort(function(a, b) {
      return nr_sorter(get_pct(a), get_pct(b));
    });
  } else {
    elem.children.sort(function(a, b) {
      return nr_sorter(get_pct(b), get_pct(a));
    });
  }
}

function handle_sort_dir_common(top_elem, sort_type) {
  if (top_elem == undefined) {
    alert('no code coverage data found');
  }
  sort_dir = get_sort_dir_common(top_elem, sort_type);
  if (sort_dir == "descending") {
    sort_dir = "ascending";
  } else {
    sort_dir = "descending";
  }
  top_elem.sort_elem = sort_type;
  top_elem.sort_dir = sort_dir;
}

function sort_by_dir() {
  top_elem = coverage_data;
  handle_sort_dir_common(top_elem, "dir")
  sort_children_by_dir(top_elem, top_elem.sort_dir == "ascending");
  update_summary_table();
}

function sort_by_line() {
  top_elem = coverage_data;
  handle_sort_dir_common(top_elem, "line")
  sort_children_by_line(top_elem, top_elem.sort_dir == "ascending");
  update_summary_table();
}

function sort_by_pct() {
  top_elem = coverage_data;
  handle_sort_dir_common(top_elem, "pct")
  sort_children_by_pct(top_elem, top_elem.sort_dir == "ascending");
  update_summary_table();
}

function expand_or_collapse(id) {
  check_coverage_data();
  toggle_expanded(coverage_data, id);
  update_summary_table();
}

function expand_or_collapse_all(elem, expand) {
  for (var i = 0; i < elem.children.length; i++) {
    expand_or_collapse_all(elem.children[i], expand);
  }
  if (elem.level > 0) {
    elem.expanded = expand;
  }
}

function summary_expand_all() {
  check_coverage_data();
  expand_or_collapse_all(coverage_data, true);
  update_summary_table();
}

function summary_collapse_all() {
  check_coverage_data();
  expand_or_collapse_all(coverage_data, false);
  update_summary_table();
}

function set_org_widths(table_id) {
  var table = document.getElementById(table_id);
  var table_tr = table.querySelectorAll('tr')[0];
  if (table_tr == undefined) {
    return;
  }
  var columns = table_tr.querySelectorAll('th');
  var widths = [];
  for (var i = 0; i < columns.length; i++) {
    var col = columns[i];
    var style = window.getComputedStyle(col);
    widths.push(style.width);
  }
  check_coverage_data();
  coverage_data.org_widths = widths;
}

function update_summary_table_width(table_id) {
  check_coverage_data();
  if (coverage_data.org_widths == undefined) {
    return;
  }
  var table = document.getElementById(table_id);
  var table_tr = table.querySelectorAll('tr')[0];
  if (table_tr == undefined) {
    return;
  }
  var columns = table_tr.querySelectorAll('th');
  if (coverage_data.org_widths.length != columns.length) {
    return;
  }
  for (var i = 0; i < columns.length; i++) {
    var col = columns[i];
    col.style.width = coverage_data.org_widths[i];
  }
}

function check_coverage_data() {
  if (coverage_data == undefined) {
    alert('no code coverage data found');
  }
}

function update_summary_table() {
  check_coverage_data();
  update_summary_table_with_data(coverage_data);
}
"""

def java_scripts_file_name():
    return "scripts.js"

def coverage_data_file_name():
    return "coverage_data.js"

def sort_script_include_html(up):
    if up:
        up_str = "../"
    else:
        up_str = ""
    return ('<script src="%s%s" type="text/javascript"></script>\n'
            % (up_str, java_scripts_file_name()))

def coverage_json_data_include():
    return (f'<script src="{coverage_data_file_name()}"'
            ' type="text/javascript"></script>\n')

def disassembly_index(config):
    return 'index.html' if config.only_disassembly else 'disassembly.html'

def css_file():
    return "coverage.css"

def css_data():
    return """
body { margin: 0; float: left; min-width: 100%; }
.head { background: #0071c5;
        color: #fff;
        padding: 1ex 0 1ex 3em;
        border-bottom: solid 1px gray;
        font-weight: bold; }
.head a:link { color: #fff; }
.head a:visited { color: #fff; }
.head a:hover { color: #dee; }
.head a:active { color: #dff; }
.files { #border-top: 1px solid gray;
         #border-bottom: 1px solid gray;
         padding: 0 0 2ex 3em;
         border-collapse: collapse
         padding: 1ex }
div.src_func { max-height: 8em; overflow: auto;}
td.src_func { border: 1px solid black; }
.src_func span { padding-right: 1.5em; padding-left: .5em;}
td.dot_sep { border-top: 1px dotted black; vertical-align: text-top; }
.filename { font-family: sans-serif }
.filepath { font-family: sans-serif; padding-bottom: .5em; }
.error_report { font-family: sans-serif;
                color: DarkRed; font-weight: bold;}
.error_string { font-family: sans-serif; }
.function { font-family: sans-serif }
.ascending::after { content: " \\21E7"; }
.descending::after { content: " \\21E9"; }
.not_sorted::after { content: " \\21F3"; }
.page { padding: 0 0 2ex 3em; }
.disassembly table { padding: 0; margin: 0; border: 0px;
                     border-collapse: collapse; width: auto;
                     font-family: monospace; }
.disassembly td { white-space: nowrap; text-align: right;}
.disassembly td:last-child { width: 100%;
                             text-align: left;}
.disassembly th { white-space: nowrap; text-align: left;}
.explanation p { margin-bottom: 1em; }
.explanation h4 { margin-bottom: .5em; }
.explanation { max-width: 65ch; font-size: 85%; }
.explanation dl { margin-left: 1em; }
.explanation dt { font-weight: bold; }
.explanation dd { margin: .3em 0 1em 2em; }

table.source { empty-cells: show;
               border-collapse: collapse; }
.source td:last-child { width: 100%; }
.lineno { text-align: right; padding-right: .5em;
          font: small sans-serif;
          border-right: 1px solid gray; color: #888 }
.lineno.highlight_line {
    background-color: yellow;
    text-color: black;
    font-weight: bold;
}
.uninteresting { background-color: #f0f4f8 }
.code { font-family: monospace; padding: .25em; }
.covered { background-color: #afa }
.covered_taken { background-color: #8df }
.covered_not_taken { background-color: #ff8 }
.covered_both { background-color: #0d3 }
.uncovered { background-color: #faa }
.covered_error { background-color: #c00 }
.cov_not_included { border:1px dashed red;
                    font: x-small sans-serif;
                    background-color: #ddd; }
.cov_included { border:1px dashed green;
                    font: x-small sans-serif;
                    background-color: #dfd; }
.warning { background-color: #faa }
h4.symbol { padding-bottom: 0.5ex;
            margin-bottom: 0;
            border-bottom: 1px solid gray }
.sourcelink { font-size: 11pt;
              padding-left: 2em;}
.no_sourcelink { font-size: 11pt;
                 font-weight: normal;
                 font-style: italic;
                 padding-left: 2em;}
.summary tr:nth-child(even) { background: #eee; }
.summary th { font-weight: bold; cursor:pointer;
              white-space: nowrap; }
.summary td { vertical-align:top; }
.count { white-space: nowrap; }
.percentage { text-align:center; white-space: nowrap; }
.summary button { background-color: transparent; background-repeat: no-repeat;
                  color: inherit; font-weight: inherit; text-align: inherit;
                  font-size: inherit; font-family: inherit;
                  border: none; padding: 0; cursor: pointer; }
.summary { font-size: 14px;
           text-align: left;}
.address { font-family: monospace,monospace;}
th { padding-right: 2em; }
td { padding-right: 2em; }
p { margin: 2px; }
.functions h4 { font-size: 13pt;
                padding-bottom: 0.5ex;
                margin-bottom: 0; }
.functions table { padding-left: 20px;
                   margin-bottom: 1ex; }
.functions { border-bottom: 1px solid gray; }
.functions .summary a { color: darkblue; font-weight: bold;
                        text-decoration: none; margin-left:.3em;}

td.func_hit { background-color:  rgba(160, 240, 160, 0.4); }
td.func_not_hit { background-color: rgba(240, 160, 160, 0.4); }

.source_avail { font-size: x-small; }
ul { margin-top: .3em; font-size: small; }
.src_to_mappings table { margin-left: 1em; }
.src_to_mappings { margin: .5em 0 1em .2em; }
button.hide_button { background-color: #e7e7e7; color: inherit;
                     font-weight: inherit; text-align: inherit;
                     font-size: inherit; font-family: monospace;
                     border-radius: 4px; border: 1px solid grey;
                     padding: 0; cursor: pointer; padding: 0 1px 0 1px; }
.hide_button_div { float: left; margin-right: .5em; }
.div_hidden::after { content: " +"; }
.div_shown::after { content: " -"; }
.hide_wrapper { overflow: hidden; margin: .5em 0 1em 0; }
.hideable_div { overflow: hidden; }
button.expand_box { background-color: darkgrey; color: inherit;
                    font-weight: inherit; text-align: inherit;
                    font-size: inherit; font-family: monospace;
                    border-radius: 4px; border: 0px;
                    padding: 0; cursor: pointer; padding: 0 1px 0 1px; }
button.expand_all { background-color: lightgrey; color: inherit;
                    font-weight: inherit; text-align: inherit;
                    font-size: inherit; font-family: monospace;
                    border-radius: 4px; border: 1px solid black;
                    cursor: pointer; padding: 2px 4px 2px 4px; }

/* Tooltip handling, to show full path when hovering over a directory. */
.path_tooltip { position: relative; }
.path_tooltip .path_tooltip_text { display: none; background-color: black;
                                   color: white; text-align: center;
                                   padding: 2px; text-indent: 0px;
                                   border: 4px; border-color: black;
                                   border-radius: 5px; border-style: solid;
                                   position: absolute; top: -5px;
                                   left: calc(100% + 12px);
                                   z-index: 10; opacity: .75; }
/* Add an arrow pointing left. */
.path_tooltip_text::after {
    content: " "; border-width: 10px; border-style: solid;
    border-color: transparent black transparent transparent;
    position: absolute; top: 0px; right: 100%; }
.path_tooltip:hover .path_tooltip_text { display: block; }
"""

def output_css_file(config):
    filename_css = os.path.join(config.output_dir, css_file())
    with open_or_raise_ccerror(filename_css, 'w') as o:
        o.write(css_data())

def output_scripts_file(config):
    filename_scripts = os.path.join(config.output_dir, java_scripts_file_name())
    with open_or_raise_ccerror(filename_scripts, 'w') as o:
        o.write(js_sort_code())
        if config.tree_summary:
            o.write(js_summary_code())
        if not config.only_disassembly:
            o.write(js_mark_source_line_code())

def output_header_separator(o):
    o.write(' | ')

def output_unknown_addrs_header(o, up, config, no_link):
    if config.nr_unknown_addrs is None:
        return
    output_header_separator(o)
    if config.nr_unknown_addrs == 1:
        unknown_addrs_str = "1 unknown address"
    else:
        unknown_addrs_str = "%d unknown addresses" % config.nr_unknown_addrs
    if no_link:
        o.write(unknown_addrs_str)
    else:
        o.write('<a href="%sunknown_addrs.html">%s</a>' % (
            up, unknown_addrs_str))

def output_unknown_mappings_header(o, up, config, no_link):
    if config.nr_unknown_mappings is None:
        return
    output_header_separator(o)
    if config.nr_unknown_mappings == 1:
        unknown_mappings_str = "1 unknown mapping"
    else:
        unknown_mappings_str = ("%d unknown mappings"
                                % config.nr_unknown_mappings)
    if no_link:
        o.write(unknown_mappings_str)
    else:
        o.write('<a href="%sunknown_mappings.html">%s</a>' % (
            up, unknown_mappings_str))

def output_removed_data_header(o, up, config, no_link):
    if not config.contains_removed_data:
        return
    output_header_separator(o)
    removed_data_str = "Removed data"
    if no_link:
        o.write(removed_data_str)
    else:
        o.write('<a href="%sremoved_data.html">%s</a>' % (up, removed_data_str))

def output_explanation_header(o, up, config, no_link):
    output_header_separator(o)
    explanation_str = "Explanation"
    if no_link:
        o.write(explanation_str)
    else:
        o.write('<a href="%sexplanation.html">%s</a>' % (up, explanation_str))

def get_nr_errors(config):
    i = 0
    for (_, _, map_errors) in config.errors:
        i += len(map_errors)
    return i

def output_error_header(o, up, config, no_link):
    output_header_separator(o)
    nr_errors = get_nr_errors(config)
    if nr_errors == 1:
        error_str = "1 error"
    else:
        error_str = "%d errors" % nr_errors
    if config.errors and not no_link:
        o.write('<a href="%serrors.html">%s</a>' % (up, error_str))
    else:
        o.write(error_str)

def output_src_header(o, up, no_link):
    src_str = 'Source Files'
    if no_link:
        o.write(src_str)
    else:
        o.write('<a href="%sindex.html">%s</a>' % (up, src_str))

def output_da_header(o, up, config, no_link):
    if not config.only_disassembly:
        output_header_separator(o)

    da_str = 'Disassembly'
    if no_link:
        o.write(da_str)
    else:
        disassembly_index_path = "%s%s" % (up, disassembly_index(config))
        o.write('<a href="%s">%s</a>' % (disassembly_index_path, da_str))


def output_functions_header(o, up, no_link):
    func_str = 'Functions'
    output_header_separator(o)
    if no_link:
        o.write(func_str)
    else:
        o.write(f'<a href="{up}functions.html">{func_str}</a>')

def is_top_page(page):
    return page in ('source', 'disasm-index', 'errors', 'unknown-addrs',
                    'unknown-mappings',  'removed-data', 'explanation',
                    'functions')

def output_html_head(o, page, subdir, config):
    if subdir:
        up = "../"
    else:
        up = ""
    o.write('<!DOCTYPE html>\n')
    o.write('<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en"'
            ' lang="en">\n')
    o.write('<head>\n')
    o.write('<link rel="stylesheet" type="text/css" href="%s%s">'
            % (up, css_file()))
    title = config.report_name
    if not is_top_page(page):
        title += " - %s" % page
    o.write('<title>%s</title>\n' % title)
    o.write('</head>\n')
    o.write('<body>\n')
    o.write('<div class="head">\n')
    o.write('<h1>%s</h1>\n' % config.report_name)

    if not config.only_disassembly:
        output_src_header(o, up, page == 'source')
    if config.include_disassembly:
        output_da_header(o, up, config, page == 'disasm-index')
    if not config.no_function_coverage:
        output_functions_header(o, up, page == 'functions')

    if not is_top_page(page):
        output_header_separator(o)
        o.write(f'<span class="filename">{page}</span>')
    output_error_header(o, up, config, page == 'errors')
    output_unknown_addrs_header(o, up, config, page == 'unknown-addrs')
    output_unknown_mappings_header(o, up, config, page == 'unknown-mappings')
    output_removed_data_header(o, up, config, page == 'removed-data')
    output_explanation_header(o, up, config, page == 'explanation')
    o.write('\n</div>\n')

def percentage_str(covered, total):
    if total == 0:
        return "N/A"
    return "%.1f %%" % (covered / total * 100,)

def coverage_str(covered, total):
    covered_str = "-" if covered == 0 and total == 0 else str(covered)
    total_str = "-" if total == 0 else str(total)
    return "%s / %s" % (covered_str, total_str)

def html_escape(s, replace_space):
    escaped_str = s.rstrip().expandtabs().replace('&', '&amp;')
    escaped_str = escaped_str.replace('<', '&lt;').replace('>', '&gt;')
    if replace_space:
        escaped_str = escaped_str.replace(' ', '&nbsp;')
    return escaped_str

def output_src_to_mapping(config, o, coverage):
    maps = coverage['maps']
    if not maps:
        return
    o.write('<div class="hide_wrapper">\n')
    o.write('<div class="hide_button_div">\n'
            '<button class="hide_button div_shown" onClick="hideOrUnhide()"'
            ' id="hideButton"></button>\n</div>\n')
    o.write('<div id="hideableDiv" class="hideable_div">\n'
            'Source file included in the following mappings:\n')
    o.write('<table class="summary" id="summary_table">\n')
    o.write('<tr><th><button class="not_sorted"'
            ' onClick="sortSummaryTableByAddr(0)">Address</button></th>'
            '<th><button class="not_sorted"'
            ' onClick="sortSummaryTableByName%s(1)">Symbol file</button></th>'
            % ("2" if config.contains_sections else "",))
    if config.contains_sections:
        o.write('<th>Section</th>')
    o.write('</tr>')
    for (map_addr, map_data) in sorted(maps.items()):
        o.write('<tr><td class="address">0x%08x</td>'
                '<td class="filename">' % map_addr)
        if config.include_disassembly:
            html_base_name = html_file_name_from_map(map_data)
            href_start = '<a href="../disass/%s">' % (
                disassembly_page_file(config, html_base_name, 0),)
            o.write(href_start)
        o.write(base_name(map_data['symbol_file'], map_data['address']))
        if config.include_disassembly:
            o.write('</a>')
        o.write('</td>')
        if config.contains_sections:
            o.write('\n<td>')
            section = map_data.get('section')
            if section:
                if config.include_disassembly:
                    o.write(href_start)
                o.write(section)
                if config.include_disassembly:
                    o.write('</a>')
            o.write('</td>')
        o.write('</tr>\n')
    o.write('</table>\n</div>\n</div>\n')

class open_source:
    def __init__(self, path):
        # We do not have control over source so ignore any decoding related
        # errors.
        self._file = open(path, "r", errors='replace')

    def __enter__(self):
        return self._file.__enter__()

    def __exit__(self, e_type, e_val, e_tb):
        return self._file.__exit__(e_type, e_val, e_tb)

def line_func_name(base_name, addr):
    if base_name is None:
        base_name = "<unknown>"
    return "%s@0x%x" % (base_name, addr)

# Returns true if source file could be read and output was generated
def output_html_file(config, filename_out, source_file, org_src_file, coverage):
    covered_lines = coverage['covered']
    executable_lines = coverage['all_executable_lines']

    src_lines = []
    try:
        with open_source(source_file) as src_file:
            for (line_num, l) in enumerate(src_file, 1):
                l = html_escape(l, True)

                if line_num in covered_lines:
                    cls = "covered"
                elif line_num in executable_lines:
                    cls = "uncovered"
                else:
                    cls = "uninteresting"

                if config.show_line_functions:
                    if cls == 'uninteresting':
                        func_str = ""
                    else:
                        line_functions = executable_lines[line_num]
                        func_strs = []
                        # Sort by executed, functions should already be in
                        # address order so that will be second sort order.
                        line_items = sorted([[addr, name, run] for
                                             (addr, (name, run))
                                             in line_functions.items()],
                                            key=lambda x: 0 if x[2] else 1)
                        for (func_addr, name, executed) in line_items:
                            func_name = line_func_name(name, func_addr)
                            func_strs.append(
                                '<span class="%scovered">%s</span>' % (
                                    "" if executed else "un",
                                    html_escape(func_name, False)))
                        func_str = (
                            '<td class="src_func"><div class="src_func">'
                            '%s</div></td>' % ("<br/>".join(func_strs),))
                    line_str = ('<tr>'
                                '<td id="l%d" class="lineno dot_sep">%d</td>'
                                '<td class="code dot_sep %s">%s</td>%s</tr>\n'
                                % (line_num, line_num, cls, l, func_str))
                else:
                    line_str = ('<tr><td id="l%d" class="lineno">%d</td>'
                                '<td class="code %s">%s</td></tr>\n'
                                % (line_num, line_num, cls, l))
                src_lines.append(line_str)
    except IOError:
        return False

    with open_or_raise_ccerror(filename_out, 'w') as o:
        output_html_head(o, base_name(source_file, None), True, config)

        o.write('<div class="page">\n')
        o.write('<p class="filepath">Source file: <i>%s</i></p>\n'
                % source_file)
        if source_file != org_src_file:
            o.write('<p class="filepath">Compiled source path: <i>%s</i>'
                    '</p>\n' % org_src_file)

        o.write('<p>Covered <b>%d</b> of a possible <b>%d</b> lines (%s).'
                '</p>\n'
                % (len(covered_lines), len(executable_lines),
                   percentage_str(len(covered_lines), len(executable_lines))))

        output_src_to_mapping(config, o, coverage)

        o.write('<table class="source">\n')
        for line in src_lines:
            o.write(line)
        o.write('</table>\n')
        o.write('</div>\n')
        o.write(sort_script_include_html(True))
        o.write('</body>\n')
        o.write('</html>\n')
    return True

def get_functions_list(functions_dict):
    functions_list = [[a, a + d.get('size', 1), d.get('name')]
                      for (a, d) in functions_dict.items()]
    functions_list.sort()
    # Functions that are said to have zero size will be treated like they end
    # where the next function starts.
    for (i, f) in enumerate(functions_list):
        if f[1] == 0 and i != len(functions_list) - 1:
            f[1] = functions_list[i + 1]
    return functions_list

def function_coverage_summary(nr_covered, nr_total):
    if nr_total is None:
        return ''
    return (f'<p>Covered <b>{nr_covered}</b> of a possible'
            f' <b>{nr_total}</b> functions'
            f' ({percentage_str(nr_covered, nr_total)})</p>\n')


def is_covered_range(covered, ranges):
    for addr_range in ranges:
        for addr in range(addr_range[0], addr_range[1] + 1):
            if addr in covered:
                return True
    return False

def mapping_coverage_for_src_only(files_to_coverage, mapping, functions_dict,
                                  map_addr):
    src_info = mapping['src_info']
    for (file_id, line_data) in src_info.items():
        covered = files_to_coverage.setdefault(
                mapping['file_table'][file_id],
                {'covered': {}, 'all_executable_lines': {}, 'maps': {}})
        maps = covered['maps']
        if map_addr not in maps:
            maps[map_addr] = mapping["map"]

        for (line, addrs) in line_data.items():
            covered['all_executable_lines'][line] = {}
            if is_covered_range(mapping.get('covered', {}), addrs):
                covered['covered'][line] = True

    # TODO: config.show_line_functions


def source_file_coverage(config):
    report = config.report
    files_to_coverage = {}
    for mapping in report.get('mappings', []):
        functions_dict = mapping.get('functions', {})
        functions_list = get_functions_list(functions_dict)
        map_addr = mapping["map"]["address"]
        if 'src_info' in mapping:
            # Mapping contains only source info, no disassembly.
            mapping_coverage_for_src_only(files_to_coverage, mapping,
                                          functions_dict, map_addr)
            continue

        curr_func = [0, 0, None, -1] # [start, end, name, index]
        info_list = mapping.get('info', [])
        for entry in info_list:
            file_id = entry.get('file_id')
            if file_id is None:
                continue
            covered = files_to_coverage.setdefault(
                mapping['file_table'][file_id],
                {'covered': {}, 'all_executable_lines': {}, 'maps': {}})
            maps = covered['maps']
            if map_addr not in maps:
                maps[map_addr] = mapping["map"]
            addr = entry.get('address')
            lines = entry['executable_lines']
            if addr in mapping.get('covered', {}):
                covered['covered'].update(lines)
                addr_is_run = True
            else:
                addr_is_run = False

            if config.show_line_functions:
                # Addresses come in order and functions are sorted in address
                # order. When an address is beyond the end of a function, check
                # if it matches the next function or is at an address that does
                # not belong to any function.
                while addr >= curr_func[1]:
                    idx = curr_func[3]
                    # out of scope for this function.
                    if idx + 1 >= len(functions_list):  # last entry
                        # unknown until the end of the 64 bit address space.
                        curr_func = [curr_func[1], (1 << 64) - 1,
                                     None, len(functions_list)]
                    elif addr < functions_list[idx + 1][0]:
                        # Outside previous function but not yet in next.
                        curr_func = [curr_func[1], functions_list[idx + 1][0],
                                     None, idx]
                    else:
                        new_func = functions_list[idx + 1]
                        curr_func = [new_func[0], new_func[1], new_func[2],
                                     idx + 1]

                if curr_func[2] is None and not addr_is_run:
                    # Don't include unknown functions if they have not been run.
                    continue

                for line in lines:
                    funcs = covered['all_executable_lines'].setdefault(line, {})
                    line_data = funcs.get(curr_func[0])
                    if line_data is None:
                        if curr_func[3] < 0:
                            # Address is prior to the first known function.
                            continue
                        line_data = [curr_func[2], addr_is_run]
                        funcs[curr_func[0]] = line_data
                    elif addr_is_run and not line_data[1]:
                        line_data[1] = True
            else:
                for line in lines:
                    covered['all_executable_lines'][line] = True
    return files_to_coverage

def output_list_of_src_files(list_of_src_data, full_dir_name, summary_output):
    dir_covered = 0
    dir_total = 0
    for (pm_file, src_link, file_covered, file_total) in list_of_src_data:
        summary_output.append('<tr><td class="filename">')

        if full_dir_name:
            assert pm_file.startswith(full_dir_name)
            pm_file_no_path = pm_file[len(full_dir_name):].lstrip("/\\")
        else:
            pm_file_no_path = pm_file
        if src_link:
            summary_output.append('<a href="%s">%s</a>' % (
                src_link[4:], pm_file_no_path))
        else:
            summary_output.append(pm_file_no_path)
        summary_output.append('</td>')
        summary_output.append('<td class="count">%s</td>'
                              % coverage_str(file_covered, file_total))
        summary_output.append('<td class="percentage">%s</td></tr>\n'
                              % percentage_str(file_covered, file_total))
        dir_covered += file_covered
        dir_total += file_total
    return (dir_covered, dir_total)

def output_src_dir(config, full_dir_name, dir_name, html_file_name,
                   list_of_src_data):
    html_file_path = os.path.join(config.output_dir, 'src', html_file_name)
    summary_output = []
    (dir_covered, dir_total) = output_list_of_src_files(
        list_of_src_data, full_dir_name, summary_output)
    with open_or_raise_ccerror(html_file_path, 'w') as o:
        output_html_head(o, dir_name, True, config)
        o.write('<div class="page">\n')
        if dir_total == 0:
            o.write('<p class="error_report">No source coverage in %s.\n'
                    % full_dir_name)
        else:
            o.write('<p>Covered <b>%d</b> of a possible <b>%d</b> lines (%s) in'
                    ' <span class="filename">%s</span></p>\n'
                    % (dir_covered, dir_total,
                       percentage_str(dir_covered, dir_total), full_dir_name))
            o.write('<table class="summary" id="summary_table">\n')
            o.write('<tr><th><button class="not_sorted"'
                    ' onClick="sortSummaryTableByName(0)">Source file'
                    '</button></th><th><button class="not_sorted"'
                    ' onClick="sortSummaryTableByCov(1)">Lines</button></th>'
                    '<th><button onClick="sortSummaryTableByCov(1)">Percentage'
                    '</button></th></tr>\n')
            for output in summary_output:
                o.write(output)
            o.write('</table>\n')
            o.write('</div>\n')
            o.write(sort_script_include_html(True))
        o.write('</body>\n')
        o.write('</html>\n')

def get_separator(path):
    first_fwd = path.find('/')
    first_back = path.find('\\')
    if first_fwd < 0:
        if first_back < 0:
            return None
    else:
        if first_back < 0 or first_fwd < first_back:
            return '/'
    return '\\'

def get_highest_scored_common_path(score, num_files, separator):
    best_score = 0
    best_path = None
    for (path, value) in score.items():
        (count, subpath, contains_files) = value
        if count > best_score and not contains_files:
            best_score = count
            best_path = path

    if (best_score > 0.7 * num_files):
        return best_path + separator + get_highest_scored_common_path(
            score[best_path][1], num_files, separator)
    else:
        return ''

def get_common_path(config, file_paths):
    if config.source_files_base_path is not None:
        return config.source_files_base_path
    # score is used to find a possible common path.
    score = {}
    common_path = ""
    if len(file_paths) > 1:
        separator = None
        for (path, src_data) in file_paths.items():
            if not path:
                continue
            if not separator:
                if len(src_data) >= 1:
                    # Use pm_file as the directory path does not have to contain
                    # any separators, while path/file will contain one for that
                    # case.
                    separator = get_separator(src_data[0][0])
                if not separator:
                    continue
            path_elements = path.split(separator)
            entry = score
            # Exclude directories that contain source files as we do not want
            # source files on the main summary page and do not want to show a .
            # directory under base.
            for (i, elem) in enumerate(path_elements):
                v = entry.setdefault(elem, [0, {}, False])
                v[0] += 1
                entry = v[1]
                if i == len(path_elements) - 1:
                    # Last entry, contains files.
                    v[2] = True

        if separator:
            common_path = get_highest_scored_common_path(score, len(file_paths),
                                                         separator)

            # If the base path has depth one then show the full paths of all
            # directories.
            if separator not in common_path.strip(separator):
                common_path = ""
    return common_path

def move_children_to_list(elem):
    child_list = []
    for (child_name, child_data) in elem.get('children', {}).items():
        move_children_to_list(child_data)
        child_data['dirname'] = child_name
        child_list.append(child_data)
    elem['children'] = child_list

row_id_nr = 0
def unique_row_id_str():
    global row_id_nr
    id_str = 'l' + str(row_id_nr)
    row_id_nr += 1
    return id_str

def add_metadata(elem, level):
    elem['id'] = unique_row_id_str()
    elem['expanded'] = True
    elem['level'] = level
    for child in elem.get('children', {}).values():
        add_metadata(child, level + 1)

def combine_dirs_in_summary(summary, separator):
    if len(summary) == 0:
        return

    for (base_path, value) in summary.items():
        children = value.get('children', {})
        if len(children) == 1:
            del summary[base_path]
            child_name = list(children)[0]
            base_path = base_path + separator + child_name
            value = children[child_name]
            summary[base_path] = value
            combine_dirs_in_summary(summary, separator)
            return
        combine_dirs_in_summary(children, separator)

def set_direct_covered(summary, direct_covered, direct_total):
    assert 'direct_covered' not in summary
    summary['direct_covered'] = direct_covered
    assert 'direct_total' not in summary
    summary['direct_total'] = direct_total

def get_dir_summary_data(config, file_paths):
    dir_summary = {}
    separator = None
    for (full_dir_name, list_of_src_data) in file_paths.items():
        if separator is None:
            separator = get_separator(full_dir_name)
        direct_covered = 0
        direct_total = 0
        for (_, _, file_covered, file_total) in list_of_src_data:
            direct_covered += file_covered
            direct_total += file_total

        dir_parts = full_dir_name.split(separator)
        initial_slash = dir_parts and dir_parts[0] == ''
        if initial_slash:
            dir_parts = dir_parts[1:]
            add_slash = True
        else:
            add_slash = False
        parent = dir_summary.setdefault('children', {})

        for (i, dir_part) in enumerate(dir_parts, 1):
            if add_slash:
                dir_part = separator + dir_part
                add_slash = False
            elem = parent.setdefault(dir_part, {})
            elem['accumulated_covered'] = elem.get(
                'accumulated_covered', 0) + direct_covered
            elem['accumulated_total'] = elem.get(
                'accumulated_total', 0) + direct_total
            if i == len(dir_parts):  # last item
                set_direct_covered(elem, direct_covered,
                                   direct_total)
                assert 'full_dir_name' not in elem
                elem['full_dir_name'] = full_dir_name
                html_file_name = config.mangler.mangle(full_dir_name) + '.html'
                output_src_dir(config, full_dir_name, dir_part, html_file_name,
                               list_of_src_data)
                elem['link'] = f'src/{html_file_name}'
            else:
                parent = elem.setdefault('children', {})
    if separator:
        combine_dirs_in_summary(dir_summary.get('children', {}), separator)
    add_metadata(dir_summary, 0)
    move_children_to_list(dir_summary)
    return dir_summary

def get_tree_summary(config, file_coverage, src_links):
    all_files_covered = 0
    all_files_total = 0
    file_paths = {}  # path -> list of (src_file, covered, total)
    for (src_file, coverage) in sorted(file_coverage.items()):
        (pm_file, src_link) = src_links.get(src_file, (src_file, None))
        separator = get_separator(pm_file)
        if separator:
            directory = pm_file.rsplit(separator, 1)[0]
        else:
            directory = ""

        covered = len(coverage['covered'])
        total = len(coverage['all_executable_lines'])
        all_files_covered += covered
        all_files_total += total

        src_data = (pm_file, src_link, covered, total)
        file_paths.setdefault(directory, []).append(src_data)

    dir_summaries = get_dir_summary_data(config, file_paths)

    cov_data_file = os.path.join(config.output_dir,
                                 coverage_data_file_name())
    with open_or_raise_ccerror(cov_data_file, 'w') as cov_data_out:
        cov_data_out.write("coverage_data = ")
        # The json type is directly readable as a javascript object.
        json.dump(dir_summaries, cov_data_out)
        cov_data_out.write("\n")
    return (all_files_covered, all_files_total)

def summary_per_dir(config, file_coverage, src_links):
    all_files_covered = 0
    all_files_total = 0
    file_paths = {}  # path -> list of (src_file, covered, total)
    for (src_file, coverage) in sorted(file_coverage.items()):
        (pm_file, src_link) = src_links.get(src_file, (src_file, None))
        separator = get_separator(pm_file)
        if separator:
            directory = pm_file.rsplit(separator, 1)[0]
        else:
            directory = ""

        covered = len(coverage['covered'])
        total = len(coverage['all_executable_lines'])
        all_files_covered += covered
        all_files_total += total

        src_data = (pm_file, src_link, covered, total)
        file_paths.setdefault(directory, []).append(src_data)

    common_path = get_common_path(config, file_paths)
    summary_output = []
    for (full_dir_name, list_of_src_data) in file_paths.items():
        if full_dir_name.startswith(common_path):
            dir_name = full_dir_name[len(common_path):]
        else:
            dir_name = full_dir_name
        if dir_name:
            html_file_name = config.mangler.mangle(dir_name) + '.html'
            output_src_dir(config, full_dir_name, dir_name, html_file_name,
                           list_of_src_data)
            summary_output.append('<tr><td class="filename">')

            summary_output.append('<a href="src/%s">%s</a>' % (html_file_name,
                                                               dir_name))
            summary_output.append('</td>')

            dir_covered = 0
            dir_total = 0
            for (_, _, file_covered, file_total) in list_of_src_data:
                dir_covered += file_covered
                dir_total += file_total
            summary_output.append('<td class="count">%s</td>'
                                  % coverage_str(dir_covered, dir_total))
            summary_output.append('<td class="percentage">%s</td></tr>\n'
                                  % percentage_str(dir_covered, dir_total))
        else:
            # Output source files directly on index page if they do not have any
            # directory.
            output_list_of_src_files(list_of_src_data, "", summary_output)
    return (summary_output, all_files_covered, all_files_total, common_path)

def summary_per_file(config, file_coverage, src_links):
    all_files_covered = 0
    all_files_total = 0
    summary_output = []
    for (src_file, coverage) in sorted(file_coverage.items()):
        summary_output.append('<tr><td class="filename">')

        (pm_file, src_link) = src_links.get(src_file, (src_file, None))
        if src_link:
            summary_output.append('<a href="%s">%s</a>' % (src_link, pm_file))
        else:
            summary_output.append(src_file)
        summary_output.append('</td>')
        covered = len(coverage['covered'])
        total = len(coverage['all_executable_lines'])
        summary_output.append('<td class="count">%s</td>'
                              % coverage_str(covered, total))
        summary_output.append('<td class="percentage">%s</td></tr>\n'
                              % percentage_str(covered, total))
        all_files_covered += covered
        all_files_total += total

    return (summary_output, all_files_covered, all_files_total)

def no_symbols_page():
    o = io.StringIO("")
    o.write('<p class="error_report">No source coverage available.'
            ' Maybe symbol files are lacking debug information?</p>\n')
    return o

def tree_summary_page(all_files_covered, all_files_total, functions_run,
                      functions_total):
    if all_files_total == 0:
        return no_symbols_page()

    o = io.StringIO("")
    o.write('<p>Covered <b>%d</b> of a possible <b>%d</b> lines (%s).'
            '</p>\n'
            % (all_files_covered, all_files_total,
               percentage_str(all_files_covered, all_files_total)))
    if functions_total is not None:
        o.write(function_coverage_summary(functions_run, functions_total))
    o.write('<p>Summary per directory with coverage of sub-directories'
            ' included.</p>')
    o.write('<button class="expand_all"'
            ' onClick=summary_collapse_all()>Collapse all'
            '</button>&nbsp;'
            '<button class="expand_all" onClick=summary_expand_all()>'
            'Expand all</button>')
    o.write('<table class="summary" id="summary_table">\n')
    # The text below will be shown before javascript overwrites the summary
    # table.
    o.write('<tr><td>Loading summary...</td></tr>\n')
    o.write('<tr><td>Note that this page requires javascript.</td></tr>\n')
    o.write('</table>\n')
    o.write('</div>\n')
    o.write(sort_script_include_html(False))
    o.write(coverage_json_data_include())
    o.write('<script>window.onload = update_summary_table</script>\n')
    return o

def standard_index_page(output_header, summary_output, all_files_covered,
                        all_files_total, functions_run, functions_total,
                        common_path):
    if all_files_total == 0:
        return no_symbols_page()

    o = io.StringIO("")
    o.write('<p>Covered <b>%d</b> of a possible <b>%d</b> lines (%s).'
            '</p>\n'
            % (all_files_covered, all_files_total,
               percentage_str(all_files_covered, all_files_total)))
    o.write(function_coverage_summary(functions_run, functions_total))

    if common_path:
        o.write('<p>Base path: %s</p>\n' % common_path)

    o.write('<table class="summary" id="summary_table">\n')
    o.write('<tr><th><button class="not_sorted"'
            ' onClick="sortSummaryTableByName(0)">%s'
            '</button></th><th><button class="not_sorted"'
            ' onClick="sortSummaryTableByCov(1)">Lines</button></th>'
            '<th><button onClick="sortSummaryTableByCov(1)">Percentage'
            '</button></th></tr>\n' % output_header)
    for output in summary_output:
        o.write(output)
    o.write('</table>\n')
    o.write('</div>\n')
    o.write(sort_script_include_html(False))
    return o

def get_function_coverage(config):
    if config.no_function_coverage:
        return (None, None)

    cov = 0
    tot = 0
    report = config.report
    for mapping in report.get('mappings', []):
        functions = mapping.get('functions', {})
        covered = mapping.get('covered', {})
        tot += len(functions)
        for addr in functions:
            if addr in covered:
                cov += 1
    return (cov, tot)

def output_html_index(config, file_coverage, src_links):
    filename_index = os.path.join(config.output_dir, 'index.html')
    (functions_run, functions_total) = get_function_coverage(config)

    if config.summary_per_file:
        (summary_output, all_files_covered, all_files_total) = summary_per_file(
            config, file_coverage, src_links)
        page_contents = standard_index_page(
            "Source file", summary_output, all_files_covered, all_files_total,
            functions_run, functions_total, None)
    elif config.tree_summary:
        (all_files_covered, all_files_total) = get_tree_summary(
            config, file_coverage, src_links)
        page_contents = tree_summary_page(all_files_covered, all_files_total,
                                          functions_run, functions_total)
    else:
        (summary_output, all_files_covered, all_files_total,
         common_path) = summary_per_dir(config, file_coverage, src_links)
        page_contents = standard_index_page(
            "Directory", summary_output, all_files_covered,
            all_files_total, functions_run, functions_total, common_path)

    with open_or_raise_ccerror(filename_index, 'w') as o:
        output_html_head(o, 'source', False, config)
        o.write('<div class="page">\n')
        o.write(page_contents.getvalue())
        o.write('</body>\n')
        o.write('</html>\n')

def info_key(a):
    return a['address']

def strip_sym(sym_name):
    return sym_name.replace("<", "").replace(">", "")

def symbol_id(sym_name, sym_addr):
    return "%s@0x%x" % (strip_sym(sym_name), sym_addr)

class DisassemblySummary:
    def __init__(self, name, addr, size, link_id, has_src, page):
        self.name = name or "<unknown>"
        self.addr = addr
        # End is exclusive.
        self.end = None if (addr is None or not size) else addr + size
        self.covered = 0
        self.uncovered = 0
        # lines_* have format {file_id: {line #1, line #2,},}
        self.lines_exec = {}
        self.lines_total = {}
        self.link_id = link_id
        self.has_src = has_src
        self.page = page  # -1 means last page

    def inc_covered(self, addr):
        if self.addr is None or (addr >= self.addr and (self.end is None
                                                        or addr < self.end)):
            self.covered += 1

    def inc_uncovered(self, addr):
        if self.addr is None or (addr >= self.addr and (self.end is None
                                                        or addr < self.end)):
            self.uncovered +=1

    def inc_lines(self, file_id, line_nr, covered):
        self.lines_total.setdefault(file_id, {})[line_nr] = True
        if covered:
            self.lines_exec.setdefault(file_id, {})[line_nr] = True

    @property
    def total(self):
        return self.covered + self.uncovered

    @property
    def sorting_addr(self):
        return 1 << 64 if self.addr is None else self.addr

    def calc_lines(self, lines_dict):
        num_covered = 0
        for lines in lines_dict.values():
            num_covered += len(lines)
        return num_covered

    @property
    def covered_lines(self):
        return self.calc_lines(self.lines_exec)

    @property
    def total_lines(self):
        return self.calc_lines(self.lines_total)

def disassembly_sum_key(a):
    return a.sorting_addr

def disassembly_page_file(config, html_base_name, page_nr):
    if page_nr == 0:
        html_file_name = html_base_name
    else:
        html_file_name = "%s-%d" % (html_base_name, page_nr)
    return "%s.html" % html_file_name

def generate_disasm_coverage_summary(config, html_base_name, summary, one_page):
    sum_str = [
        ('<div class="hide_wrapper">\n'
         '<div class="hide_button_div">\n'
         '<button class="hide_button div_shown" onClick="hideOrUnhide()"'
         ' id="hideButton"></button>\n</div>\n'
         '<div id="hideableDiv">\n<table class="summary" id="summary_table">\n'
         '<tr><th><button class="not_sorted"'
         ' onClick="sortSummaryTableByAddr(0)">Address</button></th>'
         '<th><button class="not_sorted" onClick="sortSummaryTableByName(1)">'
         'Function</button></th>'
         '<th><button class="not_sorted" onClick="sortSummaryTableByCov(2)">'
         'Instructions</button></th>'
         '<th><button onClick="sortSummaryTableByCov(2)">Percentage</button>'
         '</th>')]
    col = 4
    if config.module_line_cov:
        sum_str += [
            '<th>'
            '<button class="not_sorted" onClick="sortSummaryTableByCov(%d)">'
            'Source Lines</button></th>'
            '<th><button onClick="sortSummaryTableByCov(%d)">Lines %%</button>'
            '</th>' % (col, col)]
        col += 2
    elif config.include_addresses_without_src:
        sum_str += ['<th><button class="not_sorted"'
                    ' onClick="sortSummaryTableByName(%d)">Source</button>'
                    '</th>' % col]
    sum_str += ['</tr>\n']
    for disasm_sum in summary:
        name = html_escape(disasm_sum.name, False)
        sum_str.append('<tr>')
        if disasm_sum.addr is None:
            sum_str.append('<td></td><td class="function">')
            if disasm_sum.link_id:
                sum_str.append('<a href="%s#%s">' % (
                    "" if one_page else
                    disassembly_page_file(config, html_base_name,
                                          disasm_sum.page),
                    disasm_sum.link_id))
            sum_str.append(name)
            if disasm_sum.link_id:
                sum_str.append("</a>")
        else:
            sum_str.append('<td class="address">0x%08x</td>' % disasm_sum.addr)
            sum_str.append('<td class="function"><a href="%s#%s">%s</a></td>'
                           % ("" if one_page
                              else disassembly_page_file(config, html_base_name,
                                                         disasm_sum.page),
                              symbol_id(disasm_sum.name, disasm_sum.addr),
                              name))
        sum_str.append('<td class="count">%s</td>\n'
                       % coverage_str(disasm_sum.covered, disasm_sum.total))
        sum_str.append('<td class="percentage">%s</td>'
                       % percentage_str(disasm_sum.covered, disasm_sum.total))

        if config.module_line_cov:
            sum_str.append('<td class="count">%s</td>\n'
                           % coverage_str(disasm_sum.covered_lines,
                                          disasm_sum.total_lines))
            sum_str.append('<td class="percentage">%s</td>'
                           % percentage_str(disasm_sum.covered_lines,
                                            disasm_sum.total_lines))

        elif config.include_addresses_without_src:
            sum_str.append('<td class="source_avail">%s</td>'
                           % ("&#x2713;" if disasm_sum.has_src else "",))
        sum_str.append('</tr>\n')
    sum_str.append('</table>\n</div>\n</div>\n')
    return sum_str

def source_link_no_source():
    return (None, None, 0)

def get_source_link_for_file_id_and_line(config, mapping, file_id, line):
    filename = mapping.get("file_table", {}).get(file_id)
    if not filename:
        return source_link_no_source()
    src_file = config.mangler.mangle(filename)
    src_html_file = f"src/{src_file}.html"
    if os.path.exists(os.path.join(config.output_dir, src_html_file)):
        src_location = f'{src_html_file}#l{line}'
    else:
        src_location = None
    return (src_location, filename, line)

def get_source_link(config, mapping, entry):
    if config.only_disassembly:
        return source_link_no_source()

    file_id = entry.get("file_id")
    if not file_id:
        return source_link_no_source()

    if len(entry.get('executable_lines', [])) == 0:
        return source_link_no_source()
    line = sorted(entry['executable_lines'])[0]
    return get_source_link_for_file_id_and_line(config, mapping, file_id, line)

def source_link_to_html(src_link_data):
    (src_location, filename, line_nr) = src_link_data
    line_str = f'{filename}:{line_nr}' if filename else None
    if src_location and filename:
        return (f'<a class="sourcelink" href="../{src_location}">'
                f'{line_str}</a>')
    elif line_str:
        return f'<span class="no_sourcelink">{line_str}</span>'
    return ""

def fn_data_key(mapping, addr):
    return (mappings_key(mapping), addr)

def get_fn_data_for_addr(config, mapping, addr):
    return config.functions_cache.get(fn_data_key(mapping, addr), {})

def get_source_link_for_addr(config, mapping, addr):
    fn_data = get_fn_data_for_addr(config, mapping, addr)
    return fn_data.get('src_link', (None, None, None))

def get_disassembly_link_for_addr(config, mapping, addr):
    fn_data = get_fn_data_for_addr(config, mapping, addr)
    da_data = fn_data.get('da_link')
    if not da_data:
        return None
    assert len(da_data) == 2
    (page, sym_id) = da_data
    if getattr(config, "single_disassembly_page", True):
        page = 0
    html_base_name = html_file_name_from_map(mapping['map'])
    page_file = disassembly_page_file(config, html_base_name, page)
    return f'disass/{page_file}#{sym_id}'

def get_first_entry_with_address(entries):
    first_addr_entry = None
    for entry in entries:
        if entry == unknown_src_separator or entry == known_src_separator:
            continue
        first_addr_entry = entry
        assert entry.get("address") is not None
        break
    return first_addr_entry

def output_disassembly_table(config, table_name, source_link, entries, covered,
                             branches, mapping, page):
    out_strings = []
    first_addr_entry = get_first_entry_with_address(entries) or {}
    first_addr = first_addr_entry.get("address")
    first_file_id = first_addr_entry.get("file_id")
    if table_name:
        if first_addr is None:
            id_str = ''
        else:
            sym_id = symbol_id(table_name, first_addr)
            id_str = f' id="{sym_id}"'

            fn_data = config.functions_cache.setdefault(
                fn_data_key(mapping, first_addr), {})
            fn_data['da_link'] = (page, sym_id)
        out_strings.append('<h4 class="symbol"%s>%s' % (
            id_str, html_escape(table_name, False)))
        if source_link:
            out_strings.append(source_link)
        out_strings.append('</h4>\n')
    elif first_addr is not None:
        out_strings.append('<div id="%s"></div>\n' % symbol_id("<unknown>",
                                                               first_addr))

    out_strings.append('<table class="disassembly">\n<tr>')
    if config.include_count:
        out_strings.append('<th>count</th>')
    out_strings.append('<th>address</th><th>mnemonic</th>')
    if config.include_opcode:
        out_strings.append('<th>opcode</th>')
    if config.include_line:
        out_strings.append('<th>line</th>')
    out_strings.append('</tr>\n')
    for entry in entries:
        if entry is unknown_src_separator:
            # separator after function size
            out_strings.append('<tr class="cov_not_included">'
                               '<td colspan="100%">Instructions below are'
                               ' excluded from function coverage</td></tr>\n')
            continue
        if entry is known_src_separator:
            # separator after function size
            out_strings.append('<tr class="cov_included">'
                               '<td colspan="100%">Instructions below are'
                               ' included in function coverage</td></tr>\n')
            continue
        addr = entry['address']
        non_exec = entry.get("non_exec", False)
        if covered and addr in covered:
            coverage = "covered"
            if non_exec:
                coverage = "covered_error"
            if branches:
                taken_not_taken = branches.get(addr)
                if taken_not_taken:
                    taken = taken_not_taken["taken"] > 0
                    not_taken = taken_not_taken["not_taken"] > 0
                    if taken and not_taken:
                        coverage = "covered_both"
                    elif taken:
                        coverage = "covered_taken"
                    elif not_taken:
                        coverage = "covered_not_taken"
        elif non_exec:
            coverage = "uninteresting"
        else:
            coverage = "uncovered"
        if config.include_count:
            count_str = "<td>%u</td>" % covered.get(addr, 0)
        else:
            count_str = ""
        if config.include_opcode:
            code_format = entry.get('format')
            if code_format in ("arm", "aarch64"):
                format_type = '08x'
            elif code_format == "thumb":
                format_type = '04x'
            else:
                format_type = '02x'
            opcode_str = ('<td>%s</td>'
                          % " ".join([format(x, format_type)
                                      for x in entry.get('op', [])]))
        else:
            opcode_str = ''

        if config.include_line:
            line_str = ', '.join([str(l) for l in entry.get('executable_lines',
                                                           {})])
            curr_file_id = entry.get('file_id')
            if first_file_id is None:
                other_file_str = '<no file>:'
            elif curr_file_id == first_file_id:
                other_file_str = ''
            else:
                file_name = None
                if curr_file_id:
                    file_name = mapping['file_table'].get(curr_file_id)
                if file_name:
                    other_file_str = file_name.replace('\\', '/').split('/')[-1]
                else:
                    other_file_str = ' <unknown file>'
                other_file_str = other_file_str + ":"

            line_str = '<td>%s%s</td>' % (other_file_str, line_str)
        else:
            line_str = ''
        out_strings.append('<tr class="%s">%s<td>0x%08x:</td><td>%s</td>'
                           '%s%s</tr>\n'
                           % (coverage, count_str, addr,
                              html_escape(entry['mnemonic'], False),
                              opcode_str, line_str))
    out_strings.append('</table>\n')
    return out_strings

class UnknownSourceSeparator:
    pass

unknown_src_separator = UnknownSourceSeparator()

class KnownSourceSeparator:
    pass

known_src_separator = KnownSourceSeparator()

def start_of_new_function(config, mapping, entry, functions, page):
    addr = entry["address"]
    func_data = functions[addr]
    entries = []
    func_name = func_data["name"]
    func_size = func_data["size"]
    has_src = entry.get("file_id") is not None
    func_sum = DisassemblySummary(func_name, addr, func_size, None, has_src,
                                  page)
    src_link_data = get_source_link(config, mapping, entry)
    src_link_html = source_link_to_html(src_link_data)
    if not config.no_function_coverage:
        fn_data = config.functions_cache.setdefault(
            fn_data_key(mapping, addr), {})
        assert 'src_link' not in fn_data
        fn_data['src_link'] = src_link_data
    return (func_name, None if func_size == 0 else addr + func_size - 1,
            src_link_html, entries, func_sum, page)

def disassembly_for_entries(config, mapping, entries, functions,
                            branches, covered, out_strings, summary,
                            outside_range_sum):
    if not entries:
        return
    sorted_entries = sorted(entries, key=info_key)

    # list of (func_name, func_end, source_link, func_entries, func_summary)
    functions_data = []
    is_padding = False
    first_entry = sorted_entries[0]
    initial_addr = first_entry["address"]
    has_src = first_entry.get("file_id") is not None
    curr_page = len(out_strings)  # Current last page, page starts at 1
    unknown_sum = DisassemblySummary("<unknown>", initial_addr, None, None,
                                     has_src, curr_page)
    unknown_function_data = [None, None, None, [], unknown_sum, 0]
    entries_per_page = 50000
    entries_on_curr_page = 0
    for entry in sorted_entries:
        addr = entry["address"]
        if functions and addr in functions:
            functions_data.append(start_of_new_function(config, mapping, entry,
                                                        functions, curr_page))
            is_padding = False
            if entries_on_curr_page > entries_per_page:
                curr_page += 1
                entries_on_curr_page = 0
                out_strings.append(list())

        if functions_data:
            curr_data = functions_data[-1]
        else:
            curr_data = unknown_function_data

        non_exec = entry.get("non_exec", False)
        if curr_data[0] is None and non_exec:
            # Exclude removed data outside of functions.
            continue
        (_, func_end, _, out_entries, func_sum, _) = curr_data
        if ((func_end is not None and addr > func_end)
            or (func_sum.has_src and entry.get("file_id") is None
                and not non_exec)):
            if non_exec:
                # Exclude removed data from padding.
                continue

            if not is_padding:
                is_padding = True
                out_entries.append(unknown_src_separator)
            if addr in covered:
                outside_range_sum.inc_covered(addr)
            else:
                outside_range_sum.inc_uncovered(addr)
        else:
            if is_padding:
                is_padding = False
                out_entries.append(known_src_separator)
            addr_covered = addr in covered
            if config.module_line_cov:
                file_id = entry.get('file_id')
                if file_id:
                    for line_nr in entry.get('executable_lines', {}):
                        func_sum.inc_lines(file_id, line_nr, addr_covered)
            if addr_covered:
                func_sum.inc_covered(addr)
            elif not non_exec:
                func_sum.inc_uncovered(addr)
        entries_on_curr_page += 1
        out_entries.append(entry)

    (_, _, _, unknown_function_entries, _, _) = unknown_function_data
    if unknown_function_entries:
        if functions_data:
            # Other function before in this section, the <unknown>
            # name should be shown.
            unknown_function_data[0] = "<unknown>"
        functions_data.append(tuple(unknown_function_data))
    for (func_name, _, source_link, func_entries, func_sum,
         page) in functions_data:
        summary.append(func_sum)
        assert len(out_strings) >= page
        out_strings[page - 1] += output_disassembly_table(
            config, func_name, source_link, func_entries, covered, branches,
            mapping, page)

def output_disasm_page_references(config, o, html_base_name, last_page,
                                  curr_page):
    o.write('Disassembly pages:<br>\n')
    if curr_page == 0:
        o.write('summary, ')
    else:
        o.write('<a href="%s">summary</a>, '
                % disassembly_page_file(config, html_base_name, 0))
    for i in range(1, last_page + 1):
        if i == curr_page:
            o.write('%d' % i)
        else:
            o.write('<a href="%s">%d</a>'
                    % (disassembly_page_file(config, html_base_name, i), i))
        if i != last_page:
            o.write(', ')
    o.write('\n')

def get_number_of_lines(lines):
    # lines has the format {file_id: {line,},}
    num_lines = 0
    for lines_for_file in lines.values():
        num_lines += len(lines_for_file)
    return num_lines

def info_with_removed_data(org_info, removed_data):
    info = org_info.copy()
    # Currently only little endian is handled. This could be determined from
    # the binary, but haven't had the need for that.
    is_little_endian = True
    # Must be sorted from largest to smallest.
    size_types = ((8, "quad"), (4, "word"), (2, "short"), (1, "byte"))

    for (rem_addr, rem_data) in removed_data.items():
        size = rem_data.get("size", 0)
        if not size:
            continue

        # Only remove pure data, not data been removed for unhandled mode or
        # similar.
        if rem_data.get("reason", "data") != "data":
            continue

        data = rem_data.get("data", [])
        data = list(data) + ([None] * (size - len(data)))
        entries = []
        remaining_size = size
        while remaining_size:
            for (sz, t) in size_types:
                if remaining_size >= sz:
                    used_size = sz
                    size_type = t
                    break

            start_i = size - remaining_size
            end_i = size - remaining_size + used_size  # exclusive

            d = ["??" if data[i] is None else f"{data[i]:02x}"
                 for i in range(start_i, end_i, 1)]
            if is_little_endian:
                d.reverse()
            d_out = "".join(d)

            entries.append({'address': rem_addr + start_i,
                            'mnemonic': f'.{size_type} {d_out}',
                            'non_exec': True,
                            'op': data[start_i:end_i]})

            remaining_size -= used_size

        i = bisect.bisect(info, rem_addr, key=lambda x: x.get('address', 0))
        info = info[:i] + entries + info[i:]
    return info

def output_one_disassembly(config, html_base_name, mapping):
    assert "info" in mapping
    symbol_file = mapping['map']['symbol_file']
    section = mapping['map'].get('section')
    page_name_base = base_name(symbol_file, mapping['map']['address'])
    if section:
        page_name_base = page_name_base + ":" + section
    outside_range_sum = DisassemblySummary("<function padding>", None,
                                           None, None, False, -1)
    covered = mapping.get('covered', {})

    functions = mapping.get('functions', {})
    branches  = mapping.get('branches')
    removed_data = mapping.get('removed_data', {})

    summary = []
    out_strings = [[]]  # output per page
    with_src = []
    without_src =[]

    executed_lines = {}
    all_lines = {}

    # Addresses without source that follow a function with source will be
    # put as padding to that function, so they are put in the with_src even
    # though the source for those addresses are unknown. Initial unknown
    # addresses and addresses following a function without source will be
    # placed in the without_src list.
    check_if_unknown = True
    info = mapping.get('info', [])
    if removed_data:
        info = info_with_removed_data(info, removed_data)
    for entry in info:
        add_with_src = False
        if config.include_addresses_without_src:
            if entry["address"] in functions:
                check_if_unknown = True
            if check_if_unknown:
                if not entry.get('file_id'):  # No source == unknown
                    if not entry.get('non_exec'):
                        without_src.append(entry)
                else:
                    check_if_unknown = False
                    add_with_src = True
            else:
                add_with_src = True
        else:
            # For the case where addresses without source are not included
            # in the report only fill the with_src list and do not care
            # about padding as that should not be included.
            if entry.get('file_id'):
                add_with_src = True

        if add_with_src:
            with_src.append(entry)
            if config.module_line_cov:
                for line_nr in entry.get('executable_lines', {}):
                    file_id = entry.get('file_id')
                    if covered.get(entry['address']):
                        executed_lines.setdefault(file_id, {})[line_nr] = True
                    all_lines.setdefault(file_id, {})[line_nr] = True
    disassembly_for_entries(config, mapping, with_src, functions, branches,
                            covered, out_strings, summary,
                            outside_range_sum)
    if config.include_addresses_without_src:
        total_with_source = 0
        covered_with_source = 0
        for s in summary:
            total_with_source += s.total
            covered_with_source += s.covered

        if without_src:
            out_strings[-1].append('<h3 id="no_src_map">Disassembly without any'
                                   ' source mapping</h3>')
            disassembly_for_entries(config, mapping, without_src,
                                    functions, branches, covered,
                                    out_strings, summary, outside_range_sum)

        if outside_range_sum.total > 0:
            summary.append(outside_range_sum)

    sum_total = 0
    sum_covered = 0
    for s in summary:
        sum_total += s.total
        sum_covered += s.covered

    covered_lines = get_number_of_lines(executed_lines)
    total_lines = get_number_of_lines(all_lines)

    one_page = len(out_strings) == 1
    config.single_disassembly_page = one_page
    output_file = os.path.join(config.output_dir, "disass",
                               disassembly_page_file(config, html_base_name, 0))
    with open_or_raise_ccerror(output_file, 'w') as o:
        output_html_head(o, page_name_base, True, config)
        if config.include_summary_table:
            o.write(sort_script_include_html(True))
        o.write('<div class="page">\n')
        o.write('<p class="filepath">Symbol file: <i>%s</i></p>\n'
                % symbol_file)
        if section:
            o.write('<p class="filepath">Section: <i>%s</i></p>\n' % section)
        o.write('<p>All instructions: Covered <b>%d</b> of a possible <b>%d</b>'
                ' instructions (%s).</p>\n'
                % (sum_covered, sum_total,
                   percentage_str(sum_covered, sum_total)))

        if config.include_addresses_without_src:
            o.write('<p>Instructions with source: Covered <b>%d</b> of a'
                    ' possible <b>%d</b> instructions (%s).</p>\n'
                    % (covered_with_source, total_with_source,
                       percentage_str(covered_with_source, total_with_source)))

        file_or_section = "section" if section else "symbol file"
        if config.module_line_cov:
            o.write('<p>Source line coverage for %s: Covered <b>%d</b>'
                    ' of <b>%d</b> lines (%s).</p>\n'
                    % (file_or_section, covered_lines, total_lines,
                       percentage_str(covered_lines, total_lines)))

        if not config.no_function_coverage:
            total_func = len(functions)
            covered_func = 0
            for addr in functions:
                if addr in covered:
                    covered_func += 1

            o.write(f'<p>Function coverage for {file_or_section}: Covered'
                    f' <b>{covered_func}</b> of <b>{total_func}</b> functions'
                    f' ({percentage_str(covered_func, total_func)}).</p>\n')

        if not one_page:
            output_disasm_page_references(config, o, html_base_name,
                                          len(out_strings), 0)

        if config.include_summary_table:
            summary.sort(key=disassembly_sum_key)
            for out_str in generate_disasm_coverage_summary(
                    config, html_base_name, summary, one_page):
                o.write(out_str)

        if one_page:
            o.write('<div class="disassembly">\n')
            for out_string in out_strings[0]:
                o.write(out_string)

            o.write('</div>\n')
        o.write('</div>\n')
        o.write('</body>\n')
        o.write('</html>\n')
    if one_page:
        return (sum_covered, sum_total, covered_lines, total_lines)

    for (i, page_out) in enumerate(out_strings, 1):
        output_file = os.path.join(config.output_dir, "disass",
                                   disassembly_page_file(config,
                                                         html_base_name, i))
        page_name = "%s:%d" % (page_name_base, i)
        with open_or_raise_ccerror(output_file, 'w') as o:
            output_html_head(o, page_name, True, config)
            o.write('<div class="page">\n')
            output_disasm_page_references(config, o, html_base_name,
                                          len(out_strings), i)
            o.write('<div class="disassembly">\n')
            for out_string in page_out:
                o.write(out_string)

            o.write('</div>\n')
            o.write('</div>\n')
            o.write('</body>\n')
            o.write('</html>\n')
    return (sum_covered, sum_total, covered_lines, total_lines)

def base_name(name, addr):
    if name is None:
        return "unknown%s" % ("" if addr is None else "-0x%x" % addr)
    sep_index_back = name.rfind('/')
    sep_index_forward = name.rfind('\\')
    if sep_index_back > sep_index_forward:
        return name[sep_index_back + 1:]
    elif sep_index_forward > -1:
        return name[sep_index_forward + 1:]
    else:
        return name

def html_file_name_from_map(map_info):
    name = base_name(map_info['symbol_file'], None)
    return "%s-%x-%d" % (name, map_info['address'], map_info['size'])

def html_link_to_map_disassembly_page(config, mapping, custom_name=None):
    symbol_file_base_name = base_name(mapping['map']['symbol_file'],
                                      mapping['map']['address'])
    html_base_name = html_file_name_from_map(mapping['map'])
    symbol_file_href = "disass/%s" % disassembly_page_file(
        config, html_base_name, 0)
    output_name = symbol_file_base_name if custom_name is None else custom_name
    return f'<a href="{symbol_file_href}">{output_name}</a>'

def mappings_key(a):
    return (a['map']['address'], a['map']['symbol_file'], a['map']['size'])

def output_removed_data(config):
    if not config.contains_removed_data:
        return
    removed_data_file = os.path.join(config.output_dir, 'removed_data.html')
    with open_or_raise_ccerror(removed_data_file, 'w') as o:
        output_html_head(o, 'removed-data', False, config)
        o.write('<div class="page">\n')
        o.write('<table class="summary" id="summary_table">\n<tr>\n')
        col = 0
        o.write('<th><button class="not_sorted"'
                ' onClick="sortSummaryTableByName%s(%d)">'
                'Symbol file' '</button></th>\n'
                % ("2" if config.contains_sections else "", col))
        col += 1
        if config.contains_sections:
            o.write('<th>Section</th>\n')
            col += 1

        o.write('<th><button class="not_sorted"'
                ' onClick="sortSummaryTableByAddr(%d)">'
                'Start address' '</button></th>\n' % col)
        col += 1
        o.write('<th><button class="not_sorted"'
                ' onClick="sortSummaryTableByAddr(%d)">'
                'End address' '</button></th>\n' % col)
        col += 1
        o.write('<th><button class="not_sorted"'
                ' onClick="sortSummaryTableByName(%d)">'
                'Symbol' '</button></th>\n</tr>\n' % col)
        for m in config.report.get('mappings', []):
            sym_file_link = html_link_to_map_disassembly_page(config, m)
            removed_data = m.get('removed_data', {})
            for removed_addr in sorted(removed_data):
                o.write('<tr>\n<td class="filename">%s</td>\n' % sym_file_link)
                if config.contains_sections:
                    o.write('<td>%s</td>' % m['map'].get('section', ''))
                o.write('<td class="address">0x%08x</td>\n' % removed_addr)
                o.write('<td class="address">0x%08x</td>\n' % (
                    removed_addr + removed_data[removed_addr]["size"] - 1,))
                label = m.get('data_labels', {}).get(removed_addr, {})
                o.write('<td class="function">%s</td>\n</tr>\n' % (
                    html_escape(label.get('name', '<unknown>'), False),))

        o.write('</table>\n')
        o.write('</div>\n')
        o.write(sort_script_include_html(False))
        o.write('</body>\n')
        o.write('</html>\n')

def output_unknown_addrs(config):
    if config.nr_unknown_addrs is None:
        return
    unknown_addrs_file = os.path.join(config.output_dir, 'unknown_addrs.html')
    with open_or_raise_ccerror(unknown_addrs_file, 'w') as o:
        output_html_head(o, 'unknown-addrs', False, config)
        o.write('<div class="page">\n')
        o.write('<table class="summary" id="summary_table">\n')
        o.write('<tr><th><button class="not_sorted"'
                ' onClick="sortSummaryTableByAddr(0)">'
                'Addresses without valid memory maps when executed'
                '</button></th></tr>\n')
        for unknown_addr in sorted(config.report.get('unknown', {}).keys()):
            o.write('<tr><td class="address">0x%08x</td></tr>\n' % unknown_addr)

        o.write('</table>\n')
        o.write('</div>\n')
        o.write(sort_script_include_html(False))
        o.write('</body>\n')
        o.write('</html>\n')

def output_unknown_mappings(config):
    if config.nr_unknown_mappings is None:
        return
    unknown_mappings_file = os.path.join(config.output_dir,
                                        'unknown_mappings.html')
    with open_or_raise_ccerror(unknown_mappings_file, 'w') as o:
        output_html_head(o, 'unknown-mappings', False, config)
        o.write('<div class="page">\n')
        o.write('<table class="summary" id="summary_table">\n')
        o.write('<tr><th><button class="not_sorted"'
                ' onClick="sortSummaryTableByAddr(0)">'
                'Addresses'
                '</button></th><th><button class="not_sorted"'
                ' onClick="sortSummaryTableByAddr(1)">'
                'Size'
                '</button></th>'
                '<th><button class="not_sorted"'
                ' onClick="sortSummaryTableByAddr(2)">'
                'Number of addresses with executed instruction'
                '</button></th></tr>\n')
        for unknown_mapping in sorted(config.report.get('unknown_mappings',
                                                        []),
                                      key=lambda m: m["map"]["address"]):
            o.write('<tr><td class="address">0x%08x</td>'
                    '<td class="size">%d</td>'
                    '<td class="size">%d</td></tr>\n'
                    % (unknown_mapping["map"]["address"],
                       unknown_mapping["map"]["size"],
                       len(unknown_mapping.get("covered", []))))

        o.write('</table>\n')
        o.write('</div>\n')
        o.write(sort_script_include_html(False))
        o.write('</body>\n')
        o.write('</html>\n')

def output_functions_one_mapping(config, mapping, index, output):
    functions = mapping.get("functions", {})
    covered = mapping.get("covered", {})

    table_output = []
    nr_total = len(functions)
    nr_covered = 0
    have_da_output = config.include_disassembly
    have_src_output = not config.only_disassembly
    for (addr, func_data) in functions.items():
        hit_times = covered.get(addr, 0)
        if hit_times > 0:
            nr_covered += 1
        hit_cls = "func_" + ("hit" if hit_times > 0 else "not_hit")
        table_output += [
            '<tr>\n',
            f'  <td class="address {hit_cls}">0x{addr:08x}</td>\n',
            f'  <td class="name {hit_cls}">{func_data["name"]}</td>\n',
            f'  <td class="{hit_cls}">{hit_times}</td>\n']
        if have_src_output:
            (src_loc, filename, line_nr) = get_source_link_for_addr(
                config, mapping, addr)
            if filename:
                text = f'{base_name(filename, None)}:{line_nr}'
            elif src_loc:
                text = 'source'
            else:
                text = ''

            if src_loc:
                link = f'<a href="{src_loc}">{text}</a>'
            else:
                link = text
            table_output.append(
                f'  <td class="{hit_cls}">{link}</td>\n')
        if have_da_output:
            da_link = get_disassembly_link_for_addr(
                config, mapping, addr)
            if da_link:
                link_target = f'<a href="{da_link}">disassembly</a>'
            else:
                link_target = ''
            table_output.append(
                f'  <td class="{hit_cls}">{link_target}</td>\n')
        table_output.append('</tr>\n')

    output.append('<div class="functions">\n')
    if nr_total:
        file_cov_out = (f'<b>{nr_covered}</b> of <b>{nr_total}</b>'
                        f' ({percentage_str(nr_covered, nr_total)}) covered')
        m_map = mapping["map"]
        m_addr = m_map["address"]
        m_section = m_map.get('section')
        section_part = f' {m_section}' if m_section else ''
        custom_link = (f'{base_name(m_map["symbol_file"], m_addr)}'
                       f'{section_part} @0x{m_addr:x}')
        if config.include_disassembly:
            link = html_link_to_map_disassembly_page(config, mapping,
                                                     custom_link)
        else:
            link = f'<b>{custom_link}</b>'
        output.append(f'<h4>Functions in {link} - {file_cov_out}:</h4>')
        output.append(
            '<div class="hide_wrapper">\n'
            '<div class="hide_button_div">\n'
            '<button class="hide_button div_shown"'
            f' onClick="hideOrUnhide(\'{index}\')"'
            f' id="hideButton{index}"></button>\n'
            '</div>\n'
            f'<div id="hideableDiv{index}">\n')
        output.append(f'<table class="summary" id="summary_table{index}">\n')
        output.append(
            '<tr>\n'
            '<th><button class="not_sorted"'
            f' onClick="sortSummaryTableIdxByAddr({index}, 0)">Address'
            '</button></th>\n'
            '<th><button class="not_sorted"'
            f' onClick="sortSummaryTableIdxByName({index}, 1)">Function'
            '</button></th>\n'
            '<th><button class="not_sorted"'
            f' onClick="sortSummaryTableIdxByInt({index}, 2)">Hit'
            '</button></th>\n')
        if have_src_output:
            output.append('<th>Source</th>\n')
        if have_da_output:
            output.append('<th>Disassembly</th>\n')
        output.append('</tr>\n')

        output += table_output
        output.append('</table>\n')
        output.append('</div>\n</div>\n')
    else:
        output.append('<h4>No functions in'
                      f' {html_link_to_map_disassembly_page(config, mapping)}'
                      f'</h4>')
    output.append('</div>\n')

    return [nr_covered, len(functions)]

def populate_functions_cache_src_link_info(config, mapping):
    functions = mapping.get('functions', {})
    for entry in mapping['info']:
        addr = entry['address']
        if not addr in functions:
            continue
        fn_data = config.functions_cache.setdefault(
            fn_data_key(mapping, addr), {})
        src_link_data = get_source_link(config, mapping, entry)
        assert 'src_link' not in fn_data
        fn_data['src_link'] = src_link_data

def populate_functions_cache_src_link_src_only(config, mapping):
    src_info = mapping['src_info']
    functions = mapping.get('functions', {})
    for (file_id, line_data) in src_info.items():
        for (line, addr_ranges) in line_data.items():
            for (start, end) in addr_ranges:
                for addr in range(start, end + 1):
                    if addr in functions:
                        fn_data = config.functions_cache.setdefault(
                            fn_data_key(mapping, addr), {})
                        src_link_data = get_source_link_for_file_id_and_line(
                            config, mapping, file_id, line)
                        assert 'src_link' not in fn_data
                        fn_data['src_link'] = src_link_data

def populate_functions_cache_src_link(config):
    for mapping in config.report.get('mappings', {}):
        if 'info' in mapping:
            populate_functions_cache_src_link_info(config, mapping)
        elif 'src_info' in mapping:
            populate_functions_cache_src_link_src_only(config, mapping)

def output_functions(config):
    # functions_cache will be populated when adding disassembly. When
    # disassembly is not included in the report it need to be populated here.
    if not config.functions_cache:
        populate_functions_cache_src_link(config)

    functions_path = os.path.join(config.output_dir, "functions.html")

    output = []
    # Amount covered and total
    covered = [0, 0]
    i = 0
    for mapping in sorted(config.report.get('mappings', []), key=mappings_key):
        mapping_cov = output_functions_one_mapping(config, mapping, i, output)
        covered = list(map(int.__add__, covered, mapping_cov))
        i += 1

    with open_or_raise_ccerror(functions_path, 'w') as o:
        output_html_head(o, 'functions', False, config)
        o.write('<div class="page">\n')
        o.write(function_coverage_summary(covered[0], covered[1]))
        if i > 1:
            o.write(
                '<p style="margin-top: 1em;">\n'
                '<button class="expand_all"'
                ' onClick=hideOrUnhideAll(true)>Hide all</button>&nbsp;'
                '<button class="expand_all" onClick=hideOrUnhideAll(false)>'
                'Show all</button>\n'
                '</p>')

        for out in output:
            o.write(out)
        o.write('</div>\n')
        o.write(sort_script_include_html(False))
        o.write('</body>\n')
        o.write('</html>\n')

def output_disassembly_index(config):
    disassembly_index_path = os.path.join(config.output_dir,
                                          disassembly_index(config))
    output = ['<table class="summary" id="summary_table">\n']
    output.append(
        '<tr><th><button class="not_sorted"'
        ' onClick="sortSummaryTableByAddr(0)">Address</button></th>'
        '<th><button class="not_sorted"'
        ' onClick="sortSummaryTableByName%s(1)">Symbol file</button></th>'
        % ("2" if config.contains_sections else "",))
    if config.contains_sections:
        output.append('<th>Section</th>')
        col = 3
    else:
        col = 2
    output.append(
        '<th><button class="not_sorted"'
        ' onClick="sortSummaryTableByCov(%d)">Instructions</button></th>'
        '<th><button onClick="sortSummaryTableByCov(%d)">Percentage'
        '</button></th>' % (col, col))
    col += 2
    if config.module_line_cov:
        output.append(
            '<th><button class="not_sorted"'
            ' onClick="sortSummaryTableByCov(%d)">Source Lines</button></th>'
            '<th><button onClick="sortSummaryTableByCov(%d)">Lines %%'
            '</button></th>' % (col, col))
        col += 2

    output.append(
        '<th><button class="not_sorted error_column"'
        ' onClick="sortSummaryTableByName(%d)">Errors</button></th>'
        '</tr>\n' % col)
    any_error = False
    all_mappings_total = 0
    all_mappings_covered = 0
    for mapping in sorted(config.report.get('mappings', []),
                          key=mappings_key):
        html_base_name = html_file_name_from_map(mapping['map'])

        addr = mapping['map']['address']
        output.append('<tr><td class="address">0x%08x</td>' % addr)
        mapping_errors = mapping.get('errors', [])
        symbol_file_base_name = base_name(mapping['map']['symbol_file'],
                                          mapping['map']['address'])
        local_error = None
        if "info" in mapping:
            (covered, total, covered_lines,
             total_lines) = output_one_disassembly(config, html_base_name,
                                                   mapping)
            all_mappings_total += total
            all_mappings_covered += covered
            output.append('<td class="filename">')
            output.append(html_link_to_map_disassembly_page(config, mapping))
            output.append('</td>')
        else:
            output.append('<td class="error_report">%s</td>'
                          % symbol_file_base_name)
            local_error = "No disassembly info"
            covered = 0
            total = 0
            covered_lines = 0
            total_lines = 0
        if config.contains_sections:
            section = mapping['map'].get('section')
            if section:
                if "info" in mapping:
                    symbol_file_href = html_link_to_map_disassembly_page(
                        config, mapping, section)
                    output.append(f'<td>{symbol_file_href}</td>')
                else:
                    output.append('<td class="error_report">%s</td>'
                                  % (section))
            else:
                output.append('<td></td>')
        output.append('<td class="count">%s</td>'
                      % coverage_str(covered, total))
        output.append('<td class="percentage">%s</td>'
                      % percentage_str(covered, total))
        if config.module_line_cov:
            output.append('<td class="count">%s</td>'
                          % coverage_str(covered_lines, total_lines))
            output.append('<td class="percentage">%s</td>'
                          % percentage_str(covered_lines, total_lines))

        error_data = []
        if local_error:
            error_data.append(local_error)

        if mapping_errors:
            nr_errors = len(mapping_errors)
            error_data.append('<a href="errors.html#%s">%d %serror%s</a>'
                              % (symbol_id(symbol_file_base_name, addr),
                                 nr_errors, 'other ' if local_error else '',
                                 's' if nr_errors != 1 else ''))
        if error_data:
            any_error = True
            output.append('<td class="error_report">%s</td>'
                          % "<br>".join(error_data))
        else:
            output.append('<td class="error_column"></td>')

        output.append('</tr>\n')
    output.append('</table>\n')
    with open_or_raise_ccerror(disassembly_index_path, 'w') as o:
        output_html_head(o, 'disasm-index', False, config)
        o.write('<div class="page">\n')
        o.write('<p>Covered <b>%d</b> of a possible <b>%d</b> instructions'
                ' (%s).</p>\n'
                % (all_mappings_covered, all_mappings_total,
                   percentage_str(all_mappings_covered, all_mappings_total)))
        for out in output:
            o.write(out)
        o.write('</div>\n')
        if not any_error:
            # Hide error column if no errors are present
            o.write('<style>.error_column { visibility:collapse; }</style>\n')
        o.write(sort_script_include_html(False))
        o.write('</body>\n')
        o.write('</html>\n')

def get_errors(report):
    errors = [[None, None, [e]] for e in report.get('errors', [])]
    for mapping in report.get('mappings', []):
        map_errors = mapping.get("errors")
        if map_errors is None:
            continue
        errors.append([mapping["map"]["address"], mapping["map"]["symbol_file"],
                       map_errors])
    return errors

def output_error_report(config):
    if len(config.errors) == 0:
        return
    error_file = os.path.join(config.output_dir, 'errors.html')
    with open_or_raise_ccerror(error_file, 'w') as o:
        output_html_head(o, 'errors', False, config)
        o.write('<div class="page">\n')
        o.write('<table class="summary" id="summary_table">\n')
        o.write('<tr><th><button class="not_sorted"'
                ' onClick="sortSummaryTableByAddr(0)">Address</button></th>'
                '<th><button class="not_sorted"'
                ' onClick="sortSummaryTableByName(1)">Symbol File</button></th>'
                '<th><button class="not_sorted"'
                ' onClick="sortSummaryTableByError(2)">Errors</button></th>'
                '</tr>\n')
        for (addr, sym_file, map_errors) in config.errors:
            id_str = ("" if addr is None
                      else ' id="%s"' % symbol_id(base_name(sym_file, addr),
                                                  addr))
            addr_str  = "" if addr is None else "0x%08x" % addr
            sym_str = "" if sym_file is None else sym_file
            o.write('<tr%s><td class="address">%s</td>'
                    '<td class="filename">%s</td>'
                    % (id_str, addr_str, sym_str))
            nr_errors = len(map_errors)
            if ((addr or sym_file)  # Exclude global errors
                and config.max_errors_per_mapping >= 0
                and nr_errors > config.max_errors_per_mapping):
                map_errors = map_errors[:config.max_errors_per_mapping]
                extra_errors = nr_errors - config.max_errors_per_mapping
                if config.max_errors_per_mapping == 0:
                    extra_str = "%d errors" % extra_errors
                else:
                    extra_str = "%d additional error%s" % (
                        extra_errors, "" if extra_errors == 1 else "s")
                map_errors.append([None, extra_str])

            o.write('<td class="error_string">%s</td></tr>\n'
                    % '<br>'.join(['"%s"' % m[1] for m in map_errors]))
        o.write('</table>\n')
        o.write('</div>\n')
        o.write(sort_script_include_html(False))
        o.write('</body>\n')
        o.write('</html>\n')

def explanation_text(fmt_html):
    return (cc_information_text() + cc_limitations_text(fmt_html))

def output_explanation_page(config):
    explanation_file = os.path.join(config.output_dir, 'explanation.html')
    with open_or_raise_ccerror(explanation_file, 'w') as o:
        output_html_head(o, 'explanation', False, config)
        o.write('<section class="page explanation">\n')
        o.write('<h3>Color explanations:</h3>\n')
        o.write('<table>\n'
                '<tr><td class="covered">covered</td>'
                '<td class="uncovered">uncovered</td></tr>\n')
        o.write('<tr><td class="covered_taken">branch taken</td>'
                '<td class="covered_not_taken">branch not taken</td>'
                '<td class="covered_both">branch both taken and not'
                '</td></tr>\n')
        o.write('<tr><td class="covered_error">error on this line</td/></tr>\n')
        o.write('</table>\n')
        o.write(explanation_text(True))
        o.write('</section>\n')
        o.write('</body>\n')
        o.write('</html>\n')

class ReportConfig:
    def __init__(self, output_dir, report, path_maps, no_disassembly,
                 only_with_src, no_summary_table, include_count,
                 no_unknown_addrs, no_unknown_mappings, only_disassembly,
                 include_opcode, max_errors_per_mapping, report_name,
                 summary_per_file, show_line_functions, no_module_line_cov,
                 include_line, source_files_base_path, tree_summary,
                 no_function_coverage):
        self.output_dir = output_dir
        self.report = report
        self.path_maps = path_maps
        self.include_addresses_without_src = not only_with_src
        self.module_line_cov = not no_module_line_cov
        # Uses same option av module line coverage, but prepared to be able to
        # have a separate config option for line coverage of functions.
        self.function_line_cov = self.module_line_cov
        self.include_summary_table = not no_summary_table
        self.include_count = include_count
        self.include_opcode = include_opcode
        self.include_line = include_line
        self.tree_summary = tree_summary
        contains_removed_data = False
        contains_sections = False
        src_only_info = False
        for m in report.get('mappings', []):
            if not contains_removed_data and 'removed_data' in m:
                contains_removed_data = True

            if not contains_sections and m["map"].get('section'):
                contains_sections = True

            if 'src_info' in m:
                src_only_info = True

        if src_only_info:
            # Disassembly cannot be generated for raw reports with 'src_info'
            # data.
            no_disassembly = True
            # When using 'src_info' reports make sure there are no conflicting
            # options provided.
            bad_options = ((only_disassembly, "only disassembly"),
                           (include_opcode, "include opcode"),
                           (include_line, "include line"),
                           (no_summary_table, "no summary table"),
                           # Support for show_line_functions could potentially
                           # be added for src_only info if functions were
                           # added. Currently this is not supported.
                           (show_line_functions, "show line functions"),)
            for (bad_option, option_str) in bad_options:
                if bad_option:
                    raise HTMLReportException(
                        "Cannot use %s option with report that has 'src_info'"
                        " data." % (option_str))

        self.include_disassembly = not no_disassembly
        self.contains_sections = contains_sections
        self.contains_removed_data = contains_removed_data
        self.nr_unknown_addrs = (None if no_unknown_addrs
                                 else len(report.get('unknown', {})))
        self.nr_unknown_mappings = (None if no_unknown_mappings
                                    else len(report.get('unknown_mappings',
                                                        [])))
        self.only_disassembly = only_disassembly
        self.mangler = Mangler()
        self.max_errors_per_mapping = max_errors_per_mapping
        self.errors = get_errors(report)
        self.report_name = report_name if report_name else "Coverage analysis"
        self.summary_per_file = summary_per_file
        self.show_line_functions = show_line_functions
        self.source_files_base_path = source_files_base_path
        self.no_function_coverage = no_function_coverage
        self.functions_cache = {}


def make_html_report(config):
    if os.path.exists(config.output_dir):
        raise HTMLReportException(
            'Target output directory %s already exists' % config.output_dir)

    # Create directory for source file reports:
    try:
        if not config.only_disassembly:
            os.makedirs(os.path.join(config.output_dir, 'src'))
        if config.include_disassembly:
            os.makedirs(os.path.join(config.output_dir, 'disass'))
    except OSError as e:
        raise HTMLReportException(
            'Could not create directory in %s: %s' % (config.output_dir, e))

    if not config.only_disassembly:
        file_coverage = source_file_coverage(config)

        src_links = {}
        for (source_file, coverage) in sorted(file_coverage.items()):
            pm_file = path_map(None, source_file, config.path_maps)
            did_output = False
            if os.path.exists(pm_file):
                file_name = config.mangler.mangle(source_file) + '.html'
                abs_file_name = os.path.join(config.output_dir, 'src',
                                             file_name)
                did_output = output_html_file(config, abs_file_name, pm_file,
                                              source_file, coverage)
                src_link = 'src/' + file_name
            if not did_output:
                src_link = None

            src_links[source_file] = (pm_file, src_link)

        output_html_index(config, file_coverage, src_links)

    if config.include_disassembly:
        output_disassembly_index(config)
    if not config.no_function_coverage:
        output_functions(config)
    output_unknown_addrs(config)
    output_unknown_mappings(config)
    output_error_report(config)
    output_removed_data(config)
    output_explanation_page(config)
    output_css_file(config)
    output_scripts_file(config)
    return get_nr_errors(config)

def output_html(output_dir, report, path_maps, no_disassembly,
                no_unmapped_addresses, no_summary_table, include_count,
                no_unknown_addrs, no_unknown_mappings, only_disassembly,
                include_opcode, max_errors_per_mapping, report_name,
                summary_per_file, show_line_functions, no_module_line_cov,
                include_line, source_files_base_path, tree_summary,
                no_function_coverage):

    config = ReportConfig(output_dir, report, path_maps, no_disassembly,
                          no_unmapped_addresses, no_summary_table,
                          include_count, no_unknown_addrs, no_unknown_mappings,
                          only_disassembly, include_opcode,
                          max_errors_per_mapping, report_name, summary_per_file,
                          show_line_functions, no_module_line_cov, include_line,
                          source_files_base_path, tree_summary,
                          no_function_coverage)
    return make_html_report(config)

def main():
    parser = argparse.ArgumentParser(description='Path map example')
    parser.add_argument('--output', required=True, type=str,
                        help='output directory for the HTML coverage report')
    parser.add_argument('--report', required=True, type=str,
                        help='the raw code coverage report from which to'
                        ' generate the HTML coverage report')
    parser.add_argument('--report-name', type=str,
                        help='the name of the report, this will be displayed as'
                        ' title and header in the HTML pages')
    parser.add_argument('--path-maps', nargs="*", type=str,
                        help='a list of path mapping pairs (from, to) to apply'
                        ' in order to locate files')
    parser.add_argument('--no-disassembly', action='store_true',
                        help='exclude disassembly from the coverage report')
    parser.add_argument('--no-unmapped-addresses', action='store_true',
                        help='exclude unmapped addresses, that is the part of a'
                        ' mapping but no know source mapping, from the coverage'
                        ' report')
    parser.add_argument('--no-summary-table', action='store_true',
                        help='exclude the summary table from the disassembly'
                        ' coverage report')
    parser.add_argument('--include-count', action='store_true',
                        help='include execution count in the coverage report,'
                        ' the raw file must have been generated with this'
                        ' feature for this to be supported')
    parser.add_argument('--no-unknown-addresses', action='store_true',
                        help='exclude instructions that were executed outside'
                        ' any known memory mapping')
    parser.add_argument('--no-unknown-mappings', action='store_true',
                        help='exclude mappings that were found but are unknown')
    parser.add_argument('--no-module-line-coverage', action='store_true',
                        help="don't show source line coverage per symbol file")
    parser.add_argument('--only-disassembly', action='store_true',
                        help='only include disassembly in the coverage report')
    parser.add_argument('--no-function-coverage', action='store_true',
                        help="don't show function coverage report")
    parser.add_argument('--include-opcode', action='store_true',
                        help='include instruction op code for disassembly')
    parser.add_argument('--include-line', action='store_true',
                        help='include line numbers in disassembly report')
    parser.add_argument('--summary-per-file', action='store_true',
                        help='Include every source file on the main page'
                        ' instead of directories')
    parser.add_argument('--tree-summary', action='store_true',
                        help='display directory tree summary, that includes'
                        ' coverage of sub directories')
    parser.add_argument('--show-line-functions', action='store_true',
                        help='Show which functions include a line, useful for'
                        ' understanding reports with inlined code')
    parser.add_argument('--max-errors-per-mapping', type=int, default=8,
                        help='limit the maximum number of errors to show per'
                        ' mapping to this amount, or a negative value to always'
                        ' show all errors, defaults to 8')
    parser.add_argument('--source-files-base-path', type=str, default=None,
                        help='Override base path of source files on summary'
                        ' page')

    args = parser.parse_args()
    pm = []
    if args.path_maps is not None:
        if len(args.path_maps) % 2:
            parser.error("Must have matching number of path map entries")
        for i in range(0, len(args.path_maps), 2):
            pm.append([args.path_maps[i], args.path_maps[i + 1]])

    try:
        with open(args.report, "rb") as f:
            report = pickle.load(f)  # nosec
    except IOError as e:
        parser.error(str(e))

    if args.no_disassembly and args.only_disassembly:
        parser.error("Cannot specify both --no-disassembly and"
                     " --only-disassembly")

    config = ReportConfig(args.output, report, pm, args.no_disassembly,
                          args.no_unmapped_addresses, args.no_summary_table,
                          args.include_count, args.no_unknown_addresses,
                          args.no_unknown_mappings, args.only_disassembly,
                          args.include_opcode, args.max_errors_per_mapping,
                          args.report_name, args.summary_per_file,
                          args.show_line_functions,
                          args.no_module_line_coverage, args.include_line,
                          args.source_files_base_path, args.tree_summary,
                          args.no_function_coverage)

    try:
        nr_errors = make_html_report(config)
    except HTMLReportException as e:
        parser.exit(1, "%s\n" % e)

    if nr_errors > 0:
        parser.exit(2, "Report contains %d errors\n" % nr_errors)

if __name__ == "__main__":
    main()
