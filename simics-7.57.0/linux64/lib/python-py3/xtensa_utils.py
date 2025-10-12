# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import cli
import table
from simics import *

all_classes = cli.global_cmds.list_classes()
all_xtensa_classes = [
    SIM_get_class(cls) for cls in all_classes
    if (cls.startswith("xtensa_") and hasattr(SIM_get_class(cls), "config"))
]
all_xtensa_classes = sorted(all_xtensa_classes, key = lambda cls: cls.name)

all_config_keys = set()
for cls in all_xtensa_classes:
    all_config_keys.update(set(cls.config.keys()))

all_features = [x for x in all_config_keys
                if x.startswith("HAVE_")]

added_commands = [
    "list-xtensa-classes",
    "list-xtensa-configs",
    "list-xtensa-memories",
    "list-xtensa-memory-sizes",
    "list-xtensa-instruction-slots",
]

# Generic filtering used by list-xtensa-{classes,configs}
def filtered_xtensa_classes(classes, class_substr, with_features,
                            without_features):
    result = []
    for cls in all_xtensa_classes:
        if classes and cls not in classes:
            continue

        if class_substr and class_substr not in cls.name:
            continue

        if with_features and not all(
                [(f in cls.config and cls.config[f])
                 for f in with_features]):
            continue

        if without_features and any(
                [(f in cls.config and cls.config[f])
                 for f in without_features]):
            continue

        result.append(cls)
    return result

def list_xtensa_classes(substr, with_features, without_features, only_classes):
    data = []
    for cls in filtered_xtensa_classes(None, substr, with_features,
                                       without_features):
        if only_classes:
            data.append([cls.name])
        else:
            cls_features = [f[5:] for f in all_features
                            if f in cls.config and cls.config[f]]
            data.append([cls.name, ", ".join(cls_features)])

    if only_classes:
        props = [(Table_Key_Columns,
                  [[(Column_Key_Name, "Xtensa Class")]])]
    else:
        props = [(Table_Key_Columns,
                  [[(Column_Key_Name, "Xtensa Class")],
                   [(Column_Key_Name, "Features")]])]
    tbl = table.Table(props, data)
    msg = tbl.to_string(rows_printed=0) if data else ""
    return cli.command_verbose_return(msg, data)

def all_equal(elements):
    if len(elements) == 0:
        return True
    for e in elements:
        if e != elements[0]:
            return False
    return True

def list_xtensa_configs(classes, class_substr, config_substr,
                        with_features, without_features,
                        only_diffs):

    selected_classes = [SIM_get_class(cn) for cn in classes]
    xtensa_classes = filtered_xtensa_classes(
        selected_classes, class_substr, with_features, without_features)

    num_cores = len(xtensa_classes)
    if num_cores > 30:
        print(f"Trying to display {num_cores} Xtensa cores in a table")
        print("This might be too many to display nicely."
              " Reduce the set of Xtensa cores with the different filters to"
              " the command")

    config_keys = set()
    for cls in xtensa_classes:
        config_keys.update(set(cls.config.keys()))

    config_keys = sorted(config_keys)
    classnames = [cls.name[7:] for cls in xtensa_classes]

    cols =  [[(Column_Key_Name, "Config")]]
    cols +=  [[(Column_Key_Name, cn),
               (Column_Key_Alignment, "right")] for cn in classnames]

    props = [(Table_Key_Columns, cols)]
    data = []

    for k in config_keys:
        row = []
        if config_substr and not config_substr in k:
            continue
        for cls in xtensa_classes:
            if k in cls.config:
                if k.startswith("HAVE_"):
                    value = bool(cls.config[k])
                else:
                    value = cls.config[k]
                row.append(value)
            else:
                row.append("n/a")
        if only_diffs:
            if all_equal(row):
                continue

        data.append([k] + row)

    tbl = table.Table(props, data)
    msg = tbl.to_string(rows_printed=0, no_row_column=True) if data else ""
    return cli.command_verbose_return(msg, data)

def list_xtensa_memories(classes, class_substr):
    def show_mem(bank, attr):
        for i, (start, stop) in enumerate(attr):
            print(f"{bank}{i}: {start:08x} - {stop:08x}")

    for cls in all_xtensa_classes:
        if classes and cls.name not in classes:
            continue

        if class_substr and class_substr not in cls.name:
            continue

        print(f"\n{cls.name}")
        show_mem("\tDRAM", cls.dram)
        show_mem("\tDROM", cls.drom)
        show_mem("\tIRAM", cls.iram)
        show_mem("\tIROM", cls.irom)

def list_xtensa_memory_sizes(classes, class_substr, *table_args):
    def imem_size(attr):
        sz = 0
        for i, (start, stop) in enumerate(attr):
            sz += stop - start
        return sz

    cols =  [
        [(Column_Key_Name, "Class")],
        [(Column_Key_Name, "IMEM"),
         (Column_Key_Binary_Prefix, "B"),
         (Column_Key_Footer_Mean, True)],
        [(Column_Key_Name, "DMEM"),
         (Column_Key_Binary_Prefix, "B"),
         (Column_Key_Footer_Mean, True)],
        [(Column_Key_Name, "Total"),
         (Column_Key_Binary_Prefix, "B"),
         (Column_Key_Footer_Mean, True)]
    ]

    props = [(Table_Key_Columns, cols)]
    data = []
    for cls in all_xtensa_classes:

        if classes and cls.name not in classes:
            continue

        if class_substr and class_substr not in cls.name:
            continue

        imem = imem_size(cls.iram) + imem_size(cls.irom)
        dmem = imem_size(cls.dram) + imem_size(cls.drom)
        total = imem + dmem
        data.append([cls.name, imem, dmem, total])

    msg = table.get(props, data, *table_args)
    return cli.command_verbose_return(msg, data)


def list_xtensa_instruction_slots(instruction):
    def format_str(f):
        (format_name, slots) = f
        slot_str = ",".join(str(s) for s in slots)
        return f"{format_name}-{slot_str}"

    cols =  [[(Column_Key_Name, "Class")],
             [(Column_Key_Name, "Formats")]]
    props = [(Table_Key_Columns, cols)]
    data = []

    for cls in all_xtensa_classes:
        for (name, formats) in cls.encode_opcode_formats:
            if name != instruction:
                continue
            data.append([cls.name, "\n".join([format_str(f)
                                              for f in formats])])

    tbl = table.Table(props, data)
    msg = tbl.to_string(rows_printed=0) if data else ""
    return cli.command_verbose_return(msg, data)


cli.new_command(
    "list-xtensa-classes", list_xtensa_classes,
    args = [
        cli.arg(cli.str_t, "substr", "?"),
        cli.arg(cli.string_set_t(all_features), "with-features", "*"),
        cli.arg(cli.string_set_t(all_features), "without-features", "*"),
        cli.arg(cli.flag_t, "-only-classes"),
    ],
    short="list Xtensa classes",
    type = ["Processors"],
    doc = ("List all Xtensa processors in the available packages."
           " (Only native Simics models, not XTMP/XTSC models)."
           " The <arg>substr</arg> argument can be used to only print the Xtensa"
           " classes which includes the sub-string within the classname"
           "\n\n"
           " The <arg>with-features</arg> argument can be used to select Xtensa"
           " classes which have all specified features selected enabled."
           " This only includes configuration options starting with 'HAVE_',"
           " for example HAVE_WINDOWED HAVE_FP, will only show the Xtensa"
           " models which have both the window option and includes floating"
           " point instructions."
           "\n\n"
           " The <arg>without-features</arg> argument is similar but filters"
           " out any class which has any of the features specified."
           "\n\n"
           " By default, a list of classes and their features are listed "
           " the <tt>-only-classes</tt> only prints out the class names "
           " instead, producing more condensed output."
           )
)

cli.new_command(
    "list-xtensa-configs", list_xtensa_configs,
    args = [
        cli.arg(cli.string_set_t([cls.name for cls in all_xtensa_classes]),
            "classes", "*"),
        cli.arg(cli.str_t, "class-substr", "?"),
        cli.arg(cli.str_t, "config-substr", "?"),
        cli.arg(cli.string_set_t(all_features), "with-features", "*"),
        cli.arg(cli.string_set_t(all_features), "without-features", "*"),
        cli.arg(cli.flag_t, "-only-diffs"),
    ],
    type = ["Processors"],
    short="list detailed information Xtensa on all configurations",
    doc = ("Print configuration options for found Xtensa processors."
           " This can be used to compare how several Xtensa models have been"
           " configured. Without any options, a huge table will be presented"
           " with all configurations on all Xtensa models."
           " The <arg>classes</arg> argument specifies which Xtensa classes to"
           " compare."
           "\n\n"
           " The <arg>class-substr</arg> argument will select the classes to"
           " compare when the classname includes the specified sub-string."
           "\n\n"
           " The <arg>config-substr</arg> argument limits the available"
           " configuration options to be printed, by only print the options"
           " including the specified sub-string."
           "\n\n"
           " The <arg>with-features</arg> argument can be used to select Xtensa"
           " classes which have all specified features selected enabled."
           " This only includes configuration options starting with 'HAVE_',"
           " for example HAVE_WINDOWED HAVE_FP, will only show the Xtensa"
           " models which have both the window option and includes floating"
           " point instructions."
           "\n\n"
           " The <arg>without-features</arg> argument is similar but filters"
           " out any class which has any of the features specified."
           "\n\n"
           " Finally, the <tt>-only-diffs</tt> flag only print out the"
           " configuration options where there are any differences between"
           " the listed xtensa models.")
    )

cli.new_command(
    "list-xtensa-memories", list_xtensa_memories,
    args = [
        cli.arg(cli.string_set_t([cls.name for cls in all_xtensa_classes]),
                "classes", "*"),
        cli.arg(cli.str_t, "class-substr", "?"),
    ],
    short="list local memory configurations of an Xtensa class",
    doc = ("Print the local memory configuration for mapped"
           " DRAM, DROM, IRAM and IROM banks."
           "The <arg>classes</arg> argument selects which "
           " Xtensa classnames to list the internal memory regions from."
           " The <arg>class-substr</arg> can be used to select the classes"
           " including the specified sub-string."),
    )

table.new_table_command(
    "list-xtensa-memory-sizes", list_xtensa_memory_sizes,
    args = [
        cli.arg(cli.string_set_t([cls.name for cls in all_xtensa_classes]),
            "classes", "*"),
        cli.arg(cli.str_t, "class-substr", "?"),
    ],
    short="sizes of internal memories on all xtensa",
    doc = ("List the sizes of all IRAM, IROM, DRAM and DROM"
           " on all Xtensa classes."),
    sortable_columns = ["Class", "IMEM", "DMEM", "Total"]
)

cli.new_command(
    "list-xtensa-instruction-slots", list_xtensa_instruction_slots,
    args = [
        cli.arg(cli.str_t, "instruction")
    ],
    short="List instruction encoding of for all Xtensa classes",
    doc = ("""Iterate over all Xtensa classes and show which formats
    and slots that can be used for encoding the instruction.
    The <arg>instruction</arg> argument specifies the instruction to be listed.""")
)
