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


from .table_enums import *  # Table constatants
from . import table
from cli import (doc, CliError)
from . import cmd

# Exported
@doc('get hold of column names from a property list',
     module = 'table',
     see_also = 'table.show')
def column_names(prop_list):
    """Help function to retrieve the column names embedded in
    the list of table properties."""
    names = []
    for (k, v) in prop_list:
        if k != Table_Key_Columns:
            continue
        for c in v:  # Each column
            for (key, value) in c:
                if key == Column_Key_Name:
                    names.append(value)
    return [s.replace('\n', ' ') for s in names]

# Exported!
@doc('format and print the table',
     module = 'table',
     see_also = 'table.new_table_command, table.get')
def show(properties, data, *table_args):
    """This function should be used from a command function registered
    through the <fun>table.new_table_command()</fun> function to
    print out the table according to the user arguments.
    The <arg>properties</arg> argument is a list of key/value pairs
    setting table properties for the table.
    The <arg>data</arg> argument contains the two-dimensional data
    to be printed where the inner list contains the columns and the
    outer list the rows of the table.
    See the <iface>table</iface> interface for more information.

    The <arg>*table_args</arg> argument represents the standard table
    arguments, received last in the <fun>table.new_table_command()</fun>
    callback function.
    """
    print(get(properties, data, *table_args))

@doc('fetch the formatted table',
     module = 'table',
     see_also = 'table.new_table_command, table.get')
def get(properties, data, *table_args):
    """Similar to the <fun>table.show</fun> but this function returns the
    table as a multi-line string."""

    # Unpack the table-arguments and get a dict back: { cli-arg-name: value }
    d = cmd.unpack_arguments(table_args)

    float_decimals = d["float-decimals"]
    if float_decimals != None and (
            float_decimals < 0 or float_decimals > 20):
        raise CliError("Invalid number of float_decimals")

    sort_order = d["sort-order"]
    if sort_order == "descending":
        descending = True
    elif sort_order == "ascending":
        descending = False
    else:
        descending = None       # Pick what the column thinks is best

    tbl = table.Table(properties, data, d["-show-all-columns"])
    sort_col = d["sort-on-column"]
    if sort_col != None and sort_col not in tbl.sortable_columns():
        raise CliError("Invalid sort column")

    return tbl.to_string(
        sort_col=d["sort-on-column"],
        reverse=descending,
        rows_printed=d["max"],
        force_max_width=d["max-table-width"],
        float_decimals=float_decimals,
        border_style=d["border-style"],
        verbose=d["-verbose"],
        no_row_column=d["-no-row-column"],
        no_footers=d["-no-footers"],
        ignore_column_widths=d["-ignore-column-widths"],
    )
