# © 2018 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from .table_enums import *  # Table constants
from .common import (TableException,)

from . import common_table
from . import column
from . import border
from . import extra_header
from . import cell
from . import prop

import cli
from cli_impl import (get_current_cmdinfo)
import simics
import conf
from simicsutils.internal import py3_cmp

import csv
from functools import cmp_to_key


# TODO/Ideas:
# * property for truncating (instead of wrapping) too long column items?
# * handle <b>foo</b> in strings and other markups
# * allow print-table to continue with next "part" (repeat)


class Table(common_table.CommonTable):
    __slots__ = (
        # Properties
        'p_default_sort_column',
        'p_columns',

        # Other
        'footer_rows',          # List of footer rows
        'table_data',           # Initial data for table
        'show_all_columns',
        'num_rows',             # Body rows
        'start_row',            # Start printing on this row
        'rows_printed',         # Body rows to be printed
        'ignore_column_widths', # Ignore Column_Width property
    )
    def __init__(self, key_value_def, data,
                 show_all_columns=False):
        super().__init__()

        # Table properties
        self.p_default_sort_column = self.map_prop(
            Table_Key_Default_Sort_Column,
            prop.StrProp(Table_Key_Default_Sort_Column))
        self.p_columns = self.map_prop(Table_Key_Columns,
                                       column.ColumnsProp(self))

        # Other
        self.footer_rows = []
        self.table_data = data
        self.show_all_columns = show_all_columns
        self.num_rows = None
        self.rows_printed = None

        # Simply ignore some key-value definition since it has not
        # meaning here. Allows us to reuse properties from StreamTable
         # properties in Table.
        ignore_keys = [Table_Key_Stream_Header_Repeat]

        prop.check_key_value(key_value_def)

        self.num_rows = len(data) if data else 0
        if self.num_rows:
            num_cols = len(data[0])
        else:
            num_cols = 0

        # Assign properties
        for i, (key, value) in enumerate(key_value_def):
            if not self.assign_properties(key, value):
                if key not in ignore_keys:
                    raise TableException(
                        f"unknown table key: {prop.property_name(key)}")

        if not self.p_columns.get():
            # No user-defined columns, create unnamed automatically
            for i in range(num_cols):
                kv = [(Column_Key_Name, "")]
                c = column.Column(kv)
                self.columns.append(c)

        for r in range(self.num_rows):
            if len(self.table_data[r]) != len(self.columns):
                raise TableException(
                    "row %d contains %d columns, but %d is expected" % (
                        r, len(self.table_data[r]), len(self.columns)))

        # Error checks
        if not isinstance(data, list):
            raise TableException("data not a list: %s" % data)

        # Push out the column data to the actual columns and set
        # default values based data
        if self.table_data:
            for i, c in enumerate(self.columns):
                c_data = [r[i] for r in self.table_data]
                c.set_data(c_data)

                # Pick ascending/descending sorting based on row[0]'s data
                if c.p_sort_descending.get() == None and self.num_rows:
                    if isinstance(c.column_data[0], (str, simics.conf_object_t)):
                        c.p_sort_descending.set(False)
                    else:
                        c.p_sort_descending.set(True)

        if self.p_default_sort_column.get():
            for i, c in enumerate(self.columns):
                if c.canonical_name() == self.p_default_sort_column.get():
                    break
            else:
                raise TableException(
                    "Table_Key_Default_Sort_Column: invalid column:"
                    f"{self.p_default_sort_column.get()}")

        self.finalize()

    def _produce_table(self, headings, table, footers, force_max_width=None):
        '''generates the resulting formatted table as multi-line string'''

        def sort_col():
            for i, c in enumerate(self.columns):
                if c._used_for_sorting:
                    return i
            return -1   # unsorted

        def initial_widths(table_cells):
            # If Column_Key_Width is set, use it initially
            used_widths = max_widths(table_cells)
            if self.ignore_column_widths:
                return used_widths
            return [(c.p_width.get() or w)
                    for (c, w) in zip(self.columns, used_widths)]

        def max_widths(t):
            # Returns list with the maximum lengths of the elements in
            # each column
            return [max(t[row][col].max_len()
                        for row in range(len(t)))
                    for col in range(len(t[0]))]

        def blank_row(row):
            return all([c.max_len() == 0 for c in row])

        def blank_rows(rows):
            return all([blank_row(r) for r in rows])

        def narrow_down_column(table, col, mx):
            for r in table:
                cell_obj = r[col]
                w = cell_obj.max_len()
                if w > mx:
                    cell_obj.narrow_width(mx, force_max_width=False)

        def widest_column(table):
            # Returns the column id and the size of the widest column
            # in the table.
            widths = max_widths(table)
            col = -1
            mx = -1
            for i, w in enumerate(widths):
                if w >= mx:
                    col = i
                    mx = w
            return (col, mx)

        def should_narrow():
            if force_max_width:  # For testability
                return True
            if (get_current_cmdinfo() and cli.interactive_command()):
                return True
            return False

        def narrow_down_table(t, max_width):
            cols = len(t[0])
            extra_width = max(draw_style_head.extra_width(cols),
                                draw_style_body.extra_width(cols))
            min_width = cols * 3 + extra_width
            if max_width < min_width:
                raise cli.CliError(
                    "Cannot fit table in %d characters, too narrow."
                    " Make your terminal window wider." % (max_width))
            while True:
                widths = max_widths(t)
                raw_width = sum(widths)
                total_width = raw_width + extra_width
                if total_width <= max_width:
                    return      # Horray! Table now fits!
                (c, mx) = widest_column(t)
                if mx > max_width:
                    # If a column is very wide, make it as wide as
                    # the terminal directly
                    narrow_down_column(t, c, max_width - 2)
                else:
                    # Shrink the widest column with 2 characters
                    narrow_down_column(t, c, mx - 2)

        def fit_text_in_cells(rows, widths):
            for row in rows:
                for c, w in zip(row, widths):
                    c.narrow_width(w, force_max_width=True)


        def header_section(rows, widths, draw_style):
            if blank_rows(rows):
                # Skip the header
                return draw_style.start_row_light(widths)

            # Mark heading which is used for the sorting. Not implemented!
            _ = sort_col()
            s = self._produce_headers(draw_style, widths)
            return s

        def table_section(rows, widths, draw_style):
            return self._data_rows(draw_style, rows, widths)

        def footer_section(rows, widths, draw_style):
            if not rows:
                return draw_style.end_row_light(widths)
            s = draw_style.row_separator_heavy_light_light(widths, widths)
            s += self._data_rows(draw_style, rows, widths)
            s += draw_style.end_row_light(widths)
            return s

        if 'header_only' in self.border_style:
            draw_style_head = border.border_style[self.border_style]
            draw_style_body = border.border_style['borderless']
        else:
            draw_style_head = border.border_style[self.border_style]
            draw_style_body = draw_style_head

        # Calculate max widths in each column and narrow down the columns
        # to fit into the terminal width.
        table_cells = headings + table + footers
        widths = initial_widths(table_cells)

        raw_width = sum(widths)
        extra_width = len(widths) + 1 # space/border separators
        table_width =  raw_width + extra_width

        max_w = force_max_width if force_max_width else cli.terminal_width()
        if table_width > max_w and should_narrow():
            narrow_down_table(table_cells, max_w)
            widths = max_widths(table_cells)

        # Set the current width of the columns after possible resizing
        for c, w in zip(self.columns, widths):
            c.set_auto_width(w)

        # Make sure each column really fits in new width (or width property)
        fit_text_in_cells(table_cells, widths)

        self.finalize_extra_headers()

        # Generate the string for the table
        s = header_section(headings, widths, draw_style_head)
        s += table_section(table, widths, draw_style_body)
        s += footer_section(footers, widths, draw_style_body)
        return s[:-1]                       # Remove last new-line

    def rows(self):
        'Number of rows in table'
        # All columns should have the same number of rows
        return self.columns[0].rows()

    def _get_data(self):
        tbl = []
        for r in range(self.num_rows):
            row = []
            for c in self.columns:
                row.append(c.get_row_data(r))
            tbl.append(row)
        return tbl

    def _set_data(self, data):
        for r in range(len(data)):
            row = data[r]
            for i, c in enumerate(self.columns):
                cell_obj = row[i]
                c.set_row_data(r, cell_obj)

    def _calc_sums(self):
        for c in self.columns:
            c.calc_sum()
            c.calc_shown_sum(self.start_row, self.rows_printed)
            c.calc_mean()
            c.calc_shown_mean(self.start_row, self.rows_printed)

    def _sort(self, sort_col = None, reverse = None):
        '''sort the raw table on a certain column.'''
        # TODO: Allow secondary key for sorting, and third...
        if sort_col == None:
            # Use default sort column, if any
            if not self.p_default_sort_column.get():
                return   # Don't sort
            # Get hold of default sort-key to use, if any
            sort_col = self.p_default_sort_column.get()

        sort_idx = -1
        for i, c in enumerate(self.columns):
            if sort_col == c.canonical_name():
                sort_idx = i
                c._used_for_sorting = True
            else:
                c._used_for_sorting = False

        if sort_idx == -1:
            raise TableException("Invalid sort-column specified: %s" %
                                 (sort_col,))

        if reverse == None:
            # Use descending sort according to the column
            col = self.columns[sort_idx]
            reverse = col.p_sort_descending.get()
            if reverse is None:
                reverse = False

        # Retrieve the data from the columns
        tbl_data = self._get_data()

        # Sort it
        tbl_data.sort(key = cmp_to_key(lambda x, y:
                                       py3_cmp(x[sort_idx], y[sort_idx])),
                      reverse = reverse)
        # Put the sorted data back in the columns
        self._set_data(tbl_data)


    def _hide_columns(self):
        for c in self.columns[:]:
            if c.hide():
                self.columns.remove(c)

    def _add_percent_column(self, col, col_num):
        # Add default properties, if not specified
        kv = col.p_percent_col.get()
        keys = [k for (k, _) in kv]
        name = col.canonical_name()
        align = col.p_alignment.get()
        # Set default properties, unless already set.
        if not Column_Key_Name in keys:
            kv.append([Column_Key_Name, "%s%%" % name])
        if align and not Column_Key_Alignment in keys:
            kv.append([Column_Key_Alignment, align])
        if not Column_Key_Float_Percent in keys:
            kv.append([Column_Key_Float_Percent, True])
        if not Column_Key_Description in keys:
            kv.append(
                [Column_Key_Description,
                 "Percent of the %s column out of total." % (name)])
        if not Column_Key_Footer_Sum in keys:
            kv.append([Column_Key_Footer_Sum, True])

        new = column.Column(kv, generated=True)
        self.columns.insert(col_num + 1, new)

        total = col.sum
        data = []
        for r in range(self.num_rows):
            cell_obj = col.get_row_data(r)
            if not isinstance(cell_obj, str) and total:
                data.append(float(cell_obj) / total)
            else:
                data.append(0.0)
        new.set_data(data)
        new.calc_sum()
        new.calc_shown_sum(self.start_row, self.rows_printed)

    def _add_accumulated_percent_column(self, col, col_num):
        # Add default properties, if not specified
        kv = col.p_acc_percent_col.get()
        keys = [k for k, v in kv]
        name = col.canonical_name()
        align = col.p_alignment.get()
        if not Column_Key_Name in keys:
            kv.append([Column_Key_Name, "Accumulated\n%s%%" % (name)])
        if align and not Column_Key_Alignment in keys:
            kv.append([Column_Key_Alignment, align])
        if not Column_Key_Float_Percent in keys:
            kv.append([Column_Key_Float_Percent, True])
        if not Column_Key_Description in keys:
            kv.append([Column_Key_Description,
                       "Accumulated percent of the %s column" % (name)])

        new = column.Column(kv, generated=True)
        self.columns.insert(col_num + 1, new)

        total = col.sum
        data = []
        acc = 0
        for r in range(self.num_rows):
            cell_obj = col.get_row_data(r)
            if not isinstance(cell_obj, str):
                acc += cell_obj
            if total:
                data.append(float(acc) / total)
            else:
                data.append(0.0)
        new.set_data(data)
        new.calc_sum()
        new.calc_shown_sum(self.start_row, self.rows_printed)

    def _add_calculated_columns(self):
        '''Add additional columns that is calculated from the raw data.'''

        def column_should_be_created(c):
            return c._used_for_sorting or self.show_all_columns

        for i, c in enumerate(self.columns):
            # Add accumulated first, the percent column will insert before
            if (c.p_acc_percent_col.get() != None
                and column_should_be_created(c)):
                self._add_accumulated_percent_column(c, i)

            if (c.p_percent_col.get() != None
                and column_should_be_created(c)):
                self._add_percent_column(c, i)

    def _add_row_column(self):
        # Create an additional column to far left, for the footer headings.
        kv = [(Column_Key_Name, "Row #"),
              (Column_Key_Int_Radix, 10),
              (Column_Key_Description, "Presented row number.")]
        new = column.Column(kv)
        rows = self.columns[0].rows()
        d = list(range(1, rows + 1))
        new.set_data(d)
        self.columns.insert(0, new)

    def _row_column_exists(self):
        return self.columns[0].p_name.get() == "Row #"

    def _add_blank_column(self):
        # Create empty column
        kv = [(Column_Key_Name, ""), (Column_Key_Description, "")]
        new = column.Column(kv)
        rows = self.columns[0].rows()
        new.set_data([""] * rows)
        self.columns.insert(0, new)

    def _add_row_footer(self, cols):
        # Display how many rows that was actually shown, if the table
        # was reduced.
        if self.num_rows == self.rows_printed:
            return []           # Entire table shown

        footer = ["# %d/%d" % (self.rows_printed, self.num_rows)]
        footer.extend([""] * len(cols))
        return [footer]

    def _add_sum_footers(self, cols):
        summable = [c.p_footer_sum.get() for c in cols]
        if not any(summable):
            return []
        if self.num_rows == self.rows_printed:
            footer = ["Sum"]
            for c in cols:
                footer.append(c.sum if c.p_footer_sum.get() else "")
            return [footer]

        shown_footer = ["Sum shown"]
        sum_footer = ["Sum (all)"]
        for c in cols:
            s = c.sum if c.p_footer_sum.get() else ""
            ss = c.shown_sum if c.p_footer_sum.get() else ""
            sum_footer.append(s)
            shown_footer.append(ss)
        return [sum_footer, shown_footer]

    def _add_mean_footers(self, cols):
        means = [c.p_footer_mean.get() for c in cols]
        if not any(means):
            return []
        if self.num_rows == self.rows_printed:
            footer = ["Mean"]
            for c in cols:
                footer.append(c.mean if c.p_footer_mean.get() else "")
            return [footer]
        shown_footer = ["Mean shown"]
        mean_footer = ["Mean (all)"]
        for c in cols:
            s = c.mean if c.p_footer_mean.get() else ""
            ss = c.shown_mean if c.p_footer_mean.get() else ""
            mean_footer.append(s)
            shown_footer.append(ss)
        return [mean_footer, shown_footer]

    def _add_footers(self):
        # Give the footer functions the columns it should look at.
        cols = self.columns[1:] if self._row_column_exists() else self.columns

        # Each footer function will return an additional leftmost column,
        # with the name of the footer.
        f = []
        f.extend(self._add_row_footer(cols))
        f.extend(self._add_sum_footers(cols))
        f.extend(self._add_mean_footers(cols))

        # The footer 'headings' are printed in the "Row #" column,
        # otherwise we create a new empty column.
        if f and not self._row_column_exists():
            self._add_blank_column()

        self.footer_rows = f


    def _data_to_cells(self):
        table = self._get_data()
        start = self.start_row -1
        stop = start + self.rows_printed
        table = table[start:stop] # Shrink the table
        return self._cellify(table)

    def _footer_to_cells(self):
        return self._cellify(self.footer_rows)

    def _table_info(self):
        name = self.p_name.get()
        desc = self.p_desc.get()
        name = name if name != None else ""
        desc = desc if desc != None else ""
        ret = str(name) + '\n' + str(desc) + '\n\n'
        return ret

    def _column_descriptions(self):
        data = []
        # Extra headers
        for row in self.headers:
            for (name, desc) in row.descriptions():
                data.append((name, desc))

        for c in self.columns:
            name = c.canonical_name()
            desc = c.p_desc.get()
            name = name if name != None else ""
            desc = desc if desc != None else ""
            if name != "" or desc != "":
                data.append((name, desc))

        struct = [
            [Table_Key_Columns, [
                [(Column_Key_Name, "Column"),
                 (Column_Key_Alignment, "left")],
                [(Column_Key_Name, "Description"),
                 (Column_Key_Alignment, "left")]
            ]]
        ]
        tbl = Table(struct, data)
        s = '\n\n' + tbl.to_string(border_style = "borderless",
                                   no_row_column=True)
        return s

    def to_string(self, sort_col=None, reverse=None, rows_printed=40,
                  float_decimals=None, border_style=None,
                  force_max_width=None, verbose=False, no_row_column=False,
                  no_footers=False, start_row=1,
                  ignore_column_widths=False):
        if not rows_printed:    # Print rest of table
            rows_printed = self.num_rows - (start_row - 1)

        self.rows_printed = min(rows_printed, self.num_rows - (start_row - 1))
        self.float_decimals = float_decimals
        self.ignore_column_widths = ignore_column_widths
        if border_style:
            self.border_style  = border_style
        else:
            self.border_style = conf.prefs.cli_table_border_style

        if (not force_max_width) and (conf.prefs.cli_table_maximum_width > 0):
            force_max_width = conf.prefs.cli_table_maximum_width

        self._sort(sort_col, reverse)
        if not self.show_all_columns:
            self._hide_columns()

        if not self.columns:
            return "" # No table left to print!

        self.start_row = start_row
        self._calc_sums()
        self._add_calculated_columns()
        if not no_row_column:
            self._add_row_column()
        if not no_footers:
            self._add_footers()

        heading_cells = self._header_to_cells()
        self.header_cells = heading_cells

        data_cells = self._data_to_cells()
        footer_cells = self._footer_to_cells()

        main_table = self._produce_table(
            heading_cells, data_cells, footer_cells, force_max_width)

        info = self._table_info() if verbose else ""
        desc = self._column_descriptions() if verbose else ""
        return info + main_table + desc

    def csv_export(self, filename):

        def csv_headers():
            # Join the extra-header elements which spans a column
            # creating longer column headers for csv matrix.
            csv_headings = []
            for c in self.columns:
                extra_names = []
                for row in self.headers:
                    for e in row.elements:
                        if not c in e.col_spans:
                            continue

                        # Header element overlaps with our column
                        name = e.p_name.get()
                        if name:
                            name = name.replace("\n", " ") # Replace any new-lines
                            extra_names.append(name)
                name = ":".join(extra_names + [c.canonical_name()])
                csv_headings.append(name)
            return [csv_headings] # return headings as one row

        self.finalize_extra_headers()
        headings = csv_headers()
        self._sort()
        table = self._get_data()
        csv_file = open(filename, "w", encoding='utf-8', newline='')
        with csv_file:
            w = csv.writer(csv_file)
            for row in headings + table:
                w.writerow(row)

    def sortable_columns(self):
        return [c.canonical_name()
                for c in self.columns
                if not c.generated]
