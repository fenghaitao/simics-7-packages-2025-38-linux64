# © 2024 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import simics
import cli
import re
import table
import commands
import textwrap
from map_commands import (
    atom_args,
    probe_address,
    simple_atom_list,
    hits_to_table,
    include_atoms_doc,
)
from mem_commands import (
    obj_set_cmd_convert_value,
    MAX_SIZE_GET_SET_CMDS,
    format_obj_get_cmd_ret_val,
)

def find_downstream_ports():
    d = cli.quiet_run_command('list-objects class = "pcie-downstream-port"')[0]
    d += cli.quiet_run_command('list-objects class = "pcie-downstream-port-legacy"')[0]
    # cxl ports are not released
    try:
        simics.SIM_get_class("cxl-downstream-port")
        simics.SIM_get_class("cxl-hdm-port")
    except simics.SimExc_General:
        pass
    else:
        d += cli.quiet_run_command('list-objects class = "cxl-downstream-port"')[0]
        d += cli.quiet_run_command('list-objects class = "cxl-hdm-port"')[0]
    return d
def find_legacy_pcie_buses():
    # This is to prevent loading the pcie-bus module by the next command
    # Since the pcie-bus modules is deprecated it will print out a warning
    # that this command really should not generate.
    v = cli.quiet_run_command('list-classes -l module = pcie-bus')[0]
    if len(v) == 0:
        return []
    d = cli.quiet_run_command('list-objects class = "pcie-bus"')[0]
    return d


def find_top_level_pcie_objects(namespace, dps, legacy_dps, allow_0_functions=False):
    """
    Identifies and returns the top-level PCIe objects in a given namespace. This
    function analyzes a set of PCIe downstream ports (`pcie-downstream-port` and
    `pcie-downstream-port-legacy`) and legacy `pcie-bus`s ports (legacy_dps) to
    determine which objects are at the top level of the PCIe hierarchy.

    For every upstream target attribute in each downstream port (stored in
    upstream_targets), it checks if the upstream object appears in any of the
    downstream port's devices attribute. If it does not, it is considered a
    top-level PCIe object.

    Args:
        namespace (str): The namespace to filter the PCIe objects. If None or an
                         empty string, all namespaces are considered.
        dps (list): A list of pcie-downstream-port(-legacy) object names to
                    analyze.
        legacy_dps (list): A list of legacy pcie-bus object names to analyze.
        allow_0_functions (bool, optional): If True, allows root objects with
                                            zero functions to be included in the
                                            results. Defaults to False.
    Returns:
        list: A list of tuples, where each tuple contains:
              - The upstream target object.
              - The downstream port object associated with the upstream target.
    """

    upstream_targets = []
    downstream_targets = []
    for dp in dps:
        dp_obj = simics.SIM_get_object(dp)

        if dp_obj.upstream_target is not None:
            upstream_targets.append((dp_obj.upstream_target, dp_obj))

        devs = dp_obj.devices
        for d in devs:
            if not isinstance(d, list):
                downstream_targets.append(d)
            else:
                if d[-1] == dp_obj.upstream_target:
                    continue
                downstream_targets.append(d[-1])
        for df, func in dp_obj.functions:
            d, legacy = find_function_parent_dev(func)
            if d is not None and d not in devs:
                if d == dp_obj.upstream_target:
                    continue
                downstream_targets.append(d)

    for dp in legacy_dps:
        dp_obj = simics.SIM_get_object(dp)
        if dp_obj.upstream_target is not None:
            upstream_targets.append((attr_object(dp_obj.upstream_target), dp_obj))
        # Legacy pcie forwards the transaction downstream if upstream target not present
        # Has to accept that scenario as a valid subsystem
        elif dp_obj.memory_space is not None:
            upstream_targets.append((attr_object(dp_obj.memory_space), dp_obj))
        devs = dp_obj.pci_devices
        for d in devs:
            if attr_object(d[2]) == attr_object(dp_obj.upstream_target):
                continue
            downstream_targets.append(d[2])

    roots = []
    for upt, dp in upstream_targets:
        functions = len(dp.functions) if dp.classname != "pcie-bus" else len(dp.pci_devices)
        if upt not in downstream_targets and ((functions > 0) or allow_0_functions):
            if (namespace is None or namespace == ""
                or simics.SIM_object_name(upt).startswith(f"{namespace}.")
                or simics.SIM_object_name(upt) == namespace):
                roots.append((upt, dp))

    return roots

def attr_object(attr):
    if attr is None:
        return None
    elif isinstance(attr, simics.conf_object_t):
        return attr
    elif len(attr) == 2 and isinstance(attr[0], simics.conf_object_t) and isinstance(attr[1], str):
        p = getattr(attr[0], "port", None)
        if p is None:
            raise Exception("Unknown attribute object", attr)
        p = getattr(p, attr[1], None)
        if p is None:
            raise Exception("Unknown attribute object", attr)

        return simics.SIM_get_object(f"{simics.SIM_object_name(attr[0])}.port.{attr[1]}")
    else:
        raise Exception("Unknown attribute object", attr)

def find_function_parent_dev(function):
    p = function
    while p is not None:
        try:
            if simics.SIM_get_interface(p, "pcie_device") is not None:
                return p, False
        except simics.SimExc_Lookup:
            try:
                if simics.SIM_get_interface(p, "pci_device") is not None:
                    return p, True
            except simics.SimExc_Lookup:
                pass
        p = simics.SIM_object_parent(p)
    return None, None


def list_pcie_hierarchies_cmd(namespace, skip_info, include_bus, indicate_legacy_pcie):
    dps = None
    legacy_dps = None

    def get_topology_next_depth(dev, depth, downstream_list):
        nonlocal dps
        for d in (dps + legacy_dps):
            d_obj = simics.SIM_get_object(d)
            # Handle transparent target
            if dev.classname == "pcie-downstream-port.downstream":
                t_dobj = simics.SIM_object_parent(simics.SIM_object_parent(dev))
                if d_obj == t_dobj:
                    downstream_list.append(get_topology(d_obj, depth + 1))
            elif d_obj.upstream_target == dev:
                downstream_list.append(get_topology(d_obj, depth + 1))

    def dev_attr_to_dev(dev_attr):
        if isinstance(dev_attr, simics.conf_object_t):
            return dev_attr
        if len(dev_attr) == 2:
            return dev_attr[1]
        return dev_attr[2]


    def get_topology(dp, depth):
        max_depth = 15
        if depth > max_depth:
            raise cli.CliError(f"Aborting command, PCIe depth exceeded {max_depth}")


        dev_info = []
        pcie_lvl = (simics.SIM_object_name(dp), dev_info)
        devices = list(getattr(dp, 'devices', [])) + list(getattr(dp, 'pci_devices', []))
        for dev_attr in devices:
            dev = dev_attr_to_dev(dev_attr)
            name = simics.SIM_object_name(dev)
            downstream = []
            dev_info.append((name, downstream))
            if dev == dp.upstream_target:
                continue
            get_topology_next_depth(dev, depth,  downstream)

        if dp.classname != "pcie-bus":
            for df, f_dev in dp.functions:
                dev, _ = find_function_parent_dev(f_dev)
                name = simics.SIM_object_name(dev)
                downstream = []

                found = False
                for (n, _) in dev_info:
                    if name == n:
                        found = True
                if not found:
                    dev_info.append((name, downstream))
                    get_topology_next_depth(dev, depth,  downstream)

        return pcie_lvl


    def get_register_value(bank, offset, size):
        cmd = f'get-device-offset bank = {simics.SIM_object_name(bank)} offset = {offset} size = {size}'
        v = cli.quiet_run_command(cmd)[0]
        return v

    def find_capability(bank, id):
        cap_ptr = get_register_value(bank, 0x34, 1)
        while cap_ptr != 0:
            val = get_register_value(bank, cap_ptr, 4)
            cur_id = val & 0xff
            next_cap_ptr = (val >> 8) & 0xff
            if cur_id == id:
                return cap_ptr

            cap_ptr = next_cap_ptr
        return None

    def dp_type_to_str(dp_type):
        if dp_type is None:
            return None
        elif dp_type == 0:
            return "Endpoint"
        elif dp_type == 0b1:
            return "Legacy Endpoint"
        elif dp_type == 0b1001:
            return "RCiEP"
        elif dp_type == 0b1010:
            return "Root complex Event collector"
        elif dp_type == 0b0100:
            return "Root port of Root Complex"
        elif dp_type == 0b0101:
            return "Switch Upstream port"
        elif dp_type == 0b0110:
            return "Switch Downstream port"
        elif dp_type == 0b0111:
            return "PCIe to PCI/PCI-X Bridge"
        elif dp_type == 0b1000:
            return "PCI/PCI-X to PCIe Bridge"

    def get_dp_type(bank):
        cap_ptr = find_capability(bank, 0x10)
        if cap_ptr is not None:
            v = get_register_value(bank, cap_ptr + 0x2, 1)
            return v >> 4
        return None

    def get_dp_type_str(bank):
        t = get_dp_type(bank)
        if t is not None: # PCIe
            return dp_type_to_str(t)
        else:
            header_type = get_register_value(bank, 0xE, 1)
            layout = header_type & 0x7f
            if layout == 0:
                return "PCI Endpoint"
            elif layout == 1:
                return "PCI to PCI Bridge"

        return None



    def topology_to_table(table_data, info, depth):
        def shift_str(s, depth):
            return f"{s:>{len(s) + depth * 4}}"
        dp_name, dev_info = info
        dp_obj = simics.SIM_get_object(dp_name)
        sec_bus_num = dp_obj.sec_bus_num if dp_obj.classname != "pcie-bus" else dp_obj.bus_number
        disabled_funcs = []
        if dp_obj.classname != "pcie-bus":
            functions = dp_obj.functions
            disabled_funcs = dp_obj.disabled
        else:
            functions = []
            for m in dp_obj.conf_space.map:
                # When mapped bus number is same as pcie-bus.bus_number
                # it means the mapping is a function.
                # Otherwise it is a mapping to a second downstream pcie-bus
                if (m[0] >> 20) != dp_obj.bus_number:
                    continue
                if isinstance(m[1], list):
                    print("Downstream port", dp_name, "Skipping function",
                          m[1], "Port object not permitted")
                    continue
                functions.append([(m[0] >> 12) & 0xff, m[1]])
            # Print disabled devices as well with no functions mapped
            for d, f, o, en in dp_obj.pci_devices:
                if en == 0:
                    if isinstance(o, list):
                        print("Downstream port", dp_name, "Skipping device",
                              o, "Port object not permitted")
                        continue
                    item_info = [shift_str(f"{sec_bus_num:02x}:{d:02x}.{f}", depth),
                             dp_name,
                             simics.SIM_object_name(o),
                             "Disabled",
                             textwrap.shorten(o.class_desc, width=40, placeholder="...") if o.class_desc is not None else "",
                             "",
                             "Legacy",]
                    table_data += [item_info]

        for f_num, func in sorted(functions, key=lambda x: x[0]):
            pcie_dev, legacy = find_function_parent_dev(func)
            if pcie_dev is None:
                print("Downstream port", dp_name,
                      "Skipping function",
                      simics.SIM_object_name(func),
                      "cannot find its pcie device")
                continue
            if legacy:
                try:
                    try:
                        simics.SIM_get_interface(func, "register_view")
                        bank = func
                    except simics.SimExc_Lookup:
                        bank = pcie_dev.bank.pci_config
                except AttributeError:
                    bank = None
            else:
                bank = func
            dev_name = simics.SIM_object_name(pcie_dev)

            dev_id = None
            id_bit_shift = 16 if dp_obj.classname != "pcie-bus" else 12
            cfg_space_map = (
                dp_obj.cfg_space.map
                if dp_obj.classname != "pcie-bus"
                else dp_obj.conf_space.map
            )
            for m in cfg_space_map:
                if m[1] == func:
                    dev_id = (m[0] >> id_bit_shift)
                    if dp_obj.classname != "pcie-bus":
                        dev_id += (sec_bus_num << 8)
                    break
            disabled = False
            if dev_id is None:
                if f_num in disabled_funcs:
                    disabled = True
                    dev_id = (sec_bus_num << 8) | f_num
                else:
                    print(f"Cannot find device id for {func}. Will show incorrect BDF.")
                    dev_id = 0

            bdf = f"{dev_id >> 8:02x}:{(dev_id >> 3) & 0b11111:02x}.{dev_id & 0b111}"

            dp_type = get_dp_type_str(bank) if bank is not None else None
            bdf_str = shift_str(bdf, depth)
            bdf_str += " (disabled)" if disabled else ""

            item_info = [bdf_str,
                    dp_name,
                    dev_name,
                    simics.SIM_object_name(func),
                    textwrap.shorten(pcie_dev.class_desc, width=40, placeholder="...") if pcie_dev.class_desc is not None else "",
                    dp_type if dp_type is not None else "",
                    "Legacy" if legacy else "New",]
            table_data += [item_info]
            for dn, ds_info in dev_info:
                if dn == dev_name:
                    for d in ds_info:
                        topology_to_table(table_data, d, depth + 1)
        # Handle transparent downstream ports separately
        # Transparent downstream port are added under devices
        # but does not show up in the functions attribute.
        if dp_obj.classname != "pcie-bus":
            for dev in dp_obj.devices:
                if isinstance(dev, list):
                    continue
                # Transparent downstream port
                dev_name = simics.SIM_object_name(dev)
                for dn, ds_info in dev_info:
                    if dn == dev_name:
                        for d in ds_info:
                            topology_to_table(table_data, d, depth)

    dps = find_downstream_ports()
    legacy_dps = find_legacy_pcie_buses()
    roots = find_top_level_pcie_objects(namespace, dps, legacy_dps)

    msg = ""
    tables = []
    header = ["BDF", "Bus", "Device", "Function", "Info", "Device/Port Type", "PCIe library"]
    if not indicate_legacy_pcie:
        header.pop(6)
    if skip_info:
        header.pop(4)
    if not include_bus:
        header.pop(1)
    for i, (upt, dp) in enumerate(roots):
        info = get_topology(dp, 1)

        if dp.classname == "pcie-bus":
            bridge = simics.SIM_object_name(upt)
            if dp.bridge is not None and dp.upstream_target != attr_object(dp.bridge):
                bridge += ", " + simics.SIM_object_name(attr_object(dp.bridge))
        else:
            bridge = simics.SIM_object_name(upt)
        props = [(table.Table_Key_Columns,
                  [[(table.Column_Key_Name, n)] for n in header]),
                    (table.Table_Key_Extra_Headers, [
                    (table.Extra_Header_Key_Row, [ #  row 1
                        [(table.Extra_Header_Key_Name, f"PCIe Subsystem #{i}")],
                    ]),
                    (table.Extra_Header_Key_Row, [ #  row 1
                        [(table.Extra_Header_Key_Name, f"Host CPU/Memory Bridge: {bridge}")],
                    ]),
                  ])
                ]
        table_data = []
        depth = 0
        topology_to_table(table_data, info, depth)
        if not indicate_legacy_pcie:
            for t in table_data:
                t.pop(6)
        if skip_info:
            for t in table_data:
                t.pop(4)
        if not include_bus:
            for t in table_data:
                t.pop(1)
        t = table.Table(props, table_data)
        msg += t.to_string(rows_printed=0, no_row_column=True)
        msg += "\n"
        tables.append(table_data)

    return cli.command_verbose_return(msg, tables)

cli.new_command("list-pcie-hierarchies", list_pcie_hierarchies_cmd,
                args = [cli.arg(cli.str_t, "namespace", "?", "",
                                expander = commands.cn_expander),
                        cli.arg(cli.flag_t, "-skip-info", "?", False),
                        cli.arg(cli.flag_t, "-include-bus", "?", False),
                        cli.arg(cli.flag_t, "-indicate-legacy-pcie", "?", False),],
                type=["Inspection"],
                alias="pcie-list-hierarchies",
                short="list PCIe hierarchies in the system",
                doc="""
Tries to find all PCIe subsystems and traverses the
hierarchies from root port down to all endpoints and prints out
the hierarchy in a table format.

The command supports the new Simics PCIe library and the legacy Simics PCIe library.
The command also tries to traverse hybrid PCIe systems where a root port is implemented
with the new Simics PCIe library but endpoints and switches underneath could be based on the
legacy Simics PCIe library.

The new Simics PCIe library utilizes the
classes <class>pcie-downstream-port</class> and
<class>pcie-downstream-port-legacy</class> to build up the PCIe topology.
The legacy Simics PCIe library utilizes the
classes <class>pcie-bus</class> and <class>pci-bus</class> to build up the PCIe topology.
The command finds all instantiated objects of these classes, and tries to construct
the hierarchy based on how these class instances are connected to one another.

The <tt>-include-bus</tt> flag adds an addition column in the table,
listing which bus object the <tt>device</tt> and <tt>function</tt> are underneath.

The <tt>-skip-info</tt> flag can be used to hide the <tt>info</tt>
column in the table that contains the class description of the device.

The <tt>-indicate-legacy-pcie</tt> flag can be used to show if the
PCIe device is modeled based on the new or legacy Simics PCIe interfaces.

The <arg>namespace</arg> argument can be used to only traverse PCIe hierarchies
where the host bridge is part of the namespace.
""")

def is_big_endian(little_endian, big_endian):
    if little_endian and big_endian:
        raise cli.CliError("Cannot use both -l and -b.")
    elif (not little_endian and not big_endian):
        return False
    return big_endian

def setup_pcie_dma(obj, simple_atoms):
    upstream_target = obj.iface.pcie_function_info.get_upstream_target()
    if upstream_target is None:
        raise cli.CliError("No upstream target found for this PCIe function")

    atoms = {}
    if simple_atoms:
        names = simple_atom_list()
        atoms = {names[i]: v for (i, v) in enumerate(simple_atoms) if v is not None}

    atoms["pcie_requester_id"] = obj.iface.pcie_function_info.get_device_id()
    atoms["pcie_type"] = simics.PCIE_Type_Mem
    atoms["initiator"] = obj
    return atoms


def common_pcie_read_write_doc():
    return f"""
The <tt>-inquiry</tt> flag is used to mark the issued transaction as an inquiry,
which result in the DMA setting the memory without any side-effects. By default,
the transaction is not using the inquiry flag.

The <tt>-l</tt> and <tt>-b</tt> flags are used to select little-endian or
big-endian byte order, respectively used to determine how the bytes in memory
should be interpreted as a value. If neither is given, then little endian is
used.

{include_atoms_doc}
"""

value_note = (
    "If <arg>value</arg> is larger than the specified size, an error is given. "
)
truncate_note = "Unless <tt>-t</tt> is specified, the value will be truncated to <arg>size</arg> bytes. "
fit_note = "If <tt>-fit</tt> is specified, the value will be fitted to the least number of bytes that can hold the value (<arg>size</arg> must not be smaller than then the least number of bytes needed). "

def pcie_dma_read_write_doc(is_write):
    return f"""
PCIe DMA {"write" if is_write else "read"} from a PCIe function. The DMA will be
of <arg>size</arg> bytes to <arg>address</arg>{" with <arg>value</arg>" if
is_write else ""}. The default <arg>size</arg> is 4 bytes, but it can be
anywhere between 1 and {MAX_SIZE_GET_SET_CMDS} inclusive. {(value_note +
truncate_note + fit_note) if is_write else ""}This command will issue a
transaction with the payload and flags set, <tt>pcie_requester_id</tt> atom set
to the device id of the PCIe function, the <tt>pcie_type</tt> atom set to
<tt>PCIE_Type_Mem</tt> and the <tt>initiator</tt> atom set to the function
object. It will issue the transaction to the upstream target of the PCIe device
the function belongs to.

{common_pcie_read_write_doc()}

Note! The <tt>data</tt>, <tt>flags</tt>, <tt>pcie_requester_id</tt>,
<tt>pcie_type</tt> and <tt>initiator</tt> atoms will be ignored if they are set
using the <tt>-add-atoms</tt> as those are added by this command.
"""

def get_size(size, value, fit, truncate):
    if fit and truncate:
        raise cli.CliError("Cannot use both -t and -fit")
    if fit:
        size_fit = (value.bit_length() + 7) // 8
        if size_fit > size:
            raise cli.CliError(
                f"Value {value} does not fit in {size} bytes, use -t to truncate or increase size"
            )
        size = size_fit
    return size

def pcie_dma_write_cmd(
    obj,
    addr,
    value,
    size,
    little_endian,
    big_endian,
    truncate,
    fit,
    inquiry,
    add_atoms,
    *simple_atoms,
):
    big_endian = is_big_endian(little_endian, big_endian)
    size = get_size(size, value, fit, truncate)

    t_args = setup_pcie_dma(obj, simple_atoms)
    t_args["inquiry"] = inquiry
    t_args["write"] = True
    t_args["data"] = bytes(
        obj_set_cmd_convert_value(value, size, big_endian, validate_value=not truncate)
    )
    t_args["data"] = bytes(
        obj_set_cmd_convert_value(value, size, big_endian, validate_value=not truncate)
    )
    t = simics.transaction_t(**t_args)
    mt = simics.SIM_new_map_target(
        obj.iface.pcie_function_info.get_upstream_target(), None, None
    )
    exc = simics.SIM_issue_transaction(mt, t, addr)
    simics.SIM_free_map_target(mt)
    if exc != simics.Sim_PE_No_Exception:
        print(f"Issue transaction resulted in following return code: {exc}")

cli.new_command(
    "pcie-dma-write",
    pcie_dma_write_cmd,
    args=[
        cli.arg(cli.uint64_t, "address"),
        cli.arg(cli.poly_t("value", cli.int_t, cli.list_t), "value"),
        cli.arg(
            cli.range_t(1, MAX_SIZE_GET_SET_CMDS, f"1..{MAX_SIZE_GET_SET_CMDS}"),
            "size",
            "?",
            4,
        ),
        cli.arg(cli.flag_t, "-l"),
        cli.arg(cli.flag_t, "-b"),
        cli.arg(cli.flag_t, "-t"),
        cli.arg(cli.flag_t, "-fit"),
        cli.arg(cli.flag_t, "-inquiry"),
        cli.arg(cli.flag_t, "-add-atoms"),
    ],
    dynamic_args=("-add-atoms", atom_args),
    type=["Memory", "Inspection"],
    see_also=["<pcie_function_info>.pcie-dma-read"],
    iface="pcie_function_info",
    short="memory PCIe (DMA) Write",
    doc=pcie_dma_read_write_doc(True),
)

def pcie_dma_read_cmd(
    obj, addr, size, little_endian, big_endian, inquiry, add_atoms, *simple_atoms
):
    big_endian = is_big_endian(little_endian, big_endian)

    t_args = setup_pcie_dma(obj, simple_atoms)
    t_args["inquiry"] = inquiry
    t_args["size"] = size
    t = simics.transaction_t(**t_args)
    mt = simics.SIM_new_map_target(
        obj.iface.pcie_function_info.get_upstream_target(), None, None
    )
    exc = simics.SIM_issue_transaction(mt, t, addr)
    simics.SIM_free_map_target(mt)
    if exc != simics.Sim_PE_No_Exception:
        print(f"Issue transaction resulted in following return code: {exc}")
        return
    val = int.from_bytes(t.data, "big" if big_endian else "little")
    return format_obj_get_cmd_ret_val(val, big_endian)

cli.new_command(
    "pcie-dma-read",
    pcie_dma_read_cmd,
    args=[
        cli.arg(cli.uint64_t, "address"),
        cli.arg(
            cli.range_t(1, MAX_SIZE_GET_SET_CMDS, f"1..{MAX_SIZE_GET_SET_CMDS}"),
            "size",
            "?",
            4,
        ),
        cli.arg(cli.flag_t, "-l"),
        cli.arg(cli.flag_t, "-b"),
        cli.arg(cli.flag_t, "-inquiry"),
        cli.arg(cli.flag_t, "-add-atoms"),
    ],
    dynamic_args=("-add-atoms", atom_args),
    type=["Memory", "Inspection"],
    see_also=["<pcie_function_info>.pcie-dma-write"],
    iface="pcie_function_info",
    short="memory PCIe DMA Read",
    doc=pcie_dma_read_write_doc(False),
)

def get_top_hierarchy_object(hierarchy, include_legacy_dps=True):
    dps = find_downstream_ports()
    if include_legacy_dps:
        legacy_dps = find_legacy_pcie_buses()
    else:
        legacy_dps = []
    roots = find_top_level_pcie_objects("", dps, legacy_dps, True)

    if len(roots) == 0:
        raise cli.CliError("No PCIe hierarchies found")

    if hierarchy == "":
        if len(roots) > 1:
            raise cli.CliError(
                "Multiple PCIe hierarchies found, please specify one using the hierarchy argument"
            )
        else:
            return roots[0][1]
    else:
        for r in roots:
            if simics.SIM_object_name(r[1]) == hierarchy:
                return r[1]
        raise cli.CliError(
            f"Cannot find PCIe hierarchy {hierarchy}, please specify one that exists using the hierarchy argument"
        )

def calc_address(top_obj, bus, device, function, offset):
    if top_obj.classname == "pcie-bus":
        return (bus << 20) | (device << 15) | (function << 12) | offset
    else:
        return (bus << 24) | (device << 19) | (function << 16) | offset

def setup_pcie_config(simple_atoms):
    atoms = {}
    if simple_atoms:
        names = simple_atom_list()
        atoms = {names[i]: v for (i, v) in enumerate(simple_atoms) if v is not None}

    atoms["pcie_type"] = simics.PCIE_Type_Cfg
    return atoms

def _hierarchy_top_expander(prefix, include_legacy_dps=True):
    dps = find_downstream_ports()
    if include_legacy_dps:
        legacy_dps = find_legacy_pcie_buses()
    else:
        legacy_dps = []
    roots = find_top_level_pcie_objects("", dps, legacy_dps, True)
    return [
        simics.SIM_object_name(r[1])
        for r in roots
        if simics.SIM_object_name(r[1]).startswith(prefix)
    ]

def hierarchy_top_expander_non_legacy(prefix):
    return _hierarchy_top_expander(prefix, False)

def hierarchy_top_expander_include_legacy(prefix):
    return _hierarchy_top_expander(prefix, True)

def bdf_sanity_check(device, function, offset, ari):
    if ari:
        if device != 0:
            raise cli.CliError("Device number must be 0 when using ARI")
    else:
        if device > 31:
            raise cli.CliError("Device number must not be larger than 31")
        if function > 7:
            raise cli.CliError("Function number must not be larger than 7")
    if offset > 4095:
        raise cli.CliError("Offset must not be larger than 4095")

def pcie_config_read_write_doc(is_write):
    return f"""
PCIe Configuration space {"write" if is_write else "read"}. The config {"write"
if is_write else "read"} will be of <arg>size</arg> bytes to
<arg>bus</arg>:<arg>device</arg>:<arg>function</arg> (B:D:F){" with "
"<arg>value</arg>" if is_write else ""} at <arg>offset</arg>. The default
<arg>size</arg> is 4 bytes, but it can be anywhere between 1 and
{MAX_SIZE_GET_SET_CMDS} inclusive. {(value_note + truncate_note + fit_note) if
is_write else ""}The <tt>-ari</tt> flag can be used to indicate an ARI BDF. When
this flag is used, <arg>device</arg> must be set to 0. This command will issue a
transaction with the payload and flags set, the <tt>pcie_type</tt> atom set to
<tt>PCIE_Type_Cfg</tt>. It will issue the transaction to the
<arg>hierarchy</arg> object. If there is only one top-level PCIe hierarchy in
the system, the <arg>hierarchy</arg> argument can be omitted. The command will
automatically find the top-level PCIe hierarchy object.

{common_pcie_read_write_doc()}

Note! The <tt>data</tt>, <tt>flags</tt>, <tt>pcie_type</tt> and atoms will be
ignored if they are set using the <tt>-add-atoms</tt> as those are added by this
command.
"""

def pcie_config_write_cmd(
    hierarchy,
    bus,
    device,
    function,
    offset,
    value,
    size,
    ari,
    little_endian,
    big_endian,
    truncate,
    fit,
    inquiry,
    add_atoms,
    *simple_atoms,
):
    top_obj = get_top_hierarchy_object(hierarchy)
    bdf_sanity_check(device, function, offset, ari)
    addr = calc_address(top_obj, bus, device, function, offset)
    big_endian = is_big_endian(little_endian, big_endian)
    size = get_size(size, value, fit, truncate)

    mt = simics.SIM_new_map_target(
        simics.SIM_object_descendant(top_obj, "port.downstream"), None, None
    )

    t_args = setup_pcie_config(simple_atoms)
    t_args["inquiry"] = inquiry
    t_args["write"] = True
    data = bytes(
        obj_set_cmd_convert_value(value, size, big_endian, validate_value=not truncate)
    )
    t_args["data"] = data
    t = simics.transaction_t(**t_args)
    exc = simics.SIM_issue_transaction(mt, t, addr)
    simics.SIM_free_map_target(mt)
    if exc != simics.Sim_PE_No_Exception:
        print(f"Issue transaction resulted in following return code: {exc}")
    else:
        _, written_target = pcie_probe_bdf(
            hierarchy, bus, device, function, offset, *simple_atoms
        )
        print(
            f"Wrote '{value}' ({size} bytes) to {written_target.name} starting at offset {hex(addr)}"
        )


cli.new_command(
    "pcie-config-write",
    pcie_config_write_cmd,
    args=[
        cli.arg(
            cli.str_t,
            "hierarchy",
            "?",
            "",
            expander=hierarchy_top_expander_include_legacy,
        ),
        cli.arg(cli.uint8_t, "bus"),
        cli.arg(cli.uint8_t, "device"),
        cli.arg(cli.uint16_t, "function"),
        cli.arg(cli.uint16_t, "offset"),
        cli.arg(cli.poly_t("value", cli.int_t, cli.list_t), "value"),
        cli.arg(
            cli.range_t(1, MAX_SIZE_GET_SET_CMDS, f"1..{MAX_SIZE_GET_SET_CMDS}"),
            "size",
            "?",
            4,
        ),
        cli.arg(cli.flag_t, "-ari"),
        cli.arg(cli.flag_t, "-l"),
        cli.arg(cli.flag_t, "-b"),
        cli.arg(cli.flag_t, "-t"),
        cli.arg(cli.flag_t, "-fit"),
        cli.arg(cli.flag_t, "-inquiry"),
        cli.arg(cli.flag_t, "-add-atoms"),
    ],
    dynamic_args=("-add-atoms", atom_args),
    type=["Memory", "Inspection"],
    see_also=["pcie-config-read", "pcie-probe-bdf"],
    short="configuration Write PCIe",
    doc=pcie_config_read_write_doc(True),
)

def pcie_config_read_cmd(
    hierarchy,
    bus,
    device,
    function,
    offset,
    size,
    ari,
    little_endian,
    big_endian,
    inquiry,
    add_atoms,
    *simple_atoms,
):
    top_obj = get_top_hierarchy_object(hierarchy)
    addr = calc_address(top_obj, bus, device, function, offset)
    big_endian = is_big_endian(little_endian, big_endian)
    bdf_sanity_check(device, function, offset, ari)

    mt = simics.SIM_new_map_target(
        simics.SIM_object_descendant(top_obj, "port.downstream"), None, None
    )

    t_args = setup_pcie_config(simple_atoms)
    t_args["inquiry"] = inquiry
    t_args["size"] = size
    t = simics.transaction_t(**t_args)
    exc = simics.SIM_issue_transaction(mt, t, addr)
    simics.SIM_free_map_target(mt)
    if exc != simics.Sim_PE_No_Exception:
        print(f"Issue transaction resulted in following return code: {exc}")
        return
    else:
        _, read_target = pcie_probe_bdf(
            hierarchy, bus, device, function, offset, *simple_atoms
        )
        print(
            f"Read {size} bytes from {read_target.name} starting at offset {hex(addr)}:"
        )
    val = int.from_bytes(t.data, "big" if big_endian else "little")
    return format_obj_get_cmd_ret_val(val, big_endian)

cli.new_command(
    "pcie-config-read",
    pcie_config_read_cmd,
    args=[
        cli.arg(
            cli.str_t,
            "hierarchy",
            "?",
            "",
            expander=hierarchy_top_expander_include_legacy,
        ),
        cli.arg(cli.uint8_t, "bus"),
        cli.arg(cli.uint8_t, "device"),
        cli.arg(cli.uint8_t, "function"),
        cli.arg(cli.uint16_t, "offset"),
        cli.arg(
            cli.range_t(1, MAX_SIZE_GET_SET_CMDS, f"1..{MAX_SIZE_GET_SET_CMDS}"),
            "size",
            "?",
            4,
        ),
        cli.arg(cli.flag_t, "-ari"),
        cli.arg(cli.flag_t, "-l"),
        cli.arg(cli.flag_t, "-b"),
        cli.arg(cli.flag_t, "-inquiry"),
        cli.arg(cli.flag_t, "-add-atoms"),
    ],
    dynamic_args=("-add-atoms", atom_args),
    type=["Memory", "Inspection"],
    see_also=["pcie-config-write", "pcie-probe-bdf"],
    short="configuration Read PCIe",
    doc=pcie_config_read_write_doc(False),
)

def validate_probed_target(target):
    ifaces = dir(target.iface)
    if "pcie_function_info" in ifaces or "pcie_device" in ifaces or "pci_device" in ifaces:
        return True
    return False

def pcie_probe_bdf(
    hierarchy, bus, device, function, offset, *simple_atoms
):
    top_obj = get_top_hierarchy_object(hierarchy, False)
    addr = calc_address(top_obj, bus, device, function, offset)
    addr_spec = ("p", addr)

    atoms = {}
    if simple_atoms:
        names = simple_atom_list()
        atoms = {names[i]: v for (i, v) in enumerate(simple_atoms) if v is not None}
    atoms["pcie_type"] = simics.PCIE_Type_Cfg
    atoms["inquiry"] = True

    mt = simics.SIM_new_map_target(
        simics.SIM_object_descendant(top_obj, "port.downstream"), None, None
    )
    hits = probe_address(mt, addr, inquiry=True, atoms=atoms)
    simics.SIM_free_map_target(mt)

    return hits_to_table(addr_spec, addr, hits)

def pcie_probe_bdf_cmd(
    hierarchy, bus, device, function, offset, ari, add_atoms, *simple_atoms
):
    bdf_sanity_check(device, function, offset, ari)
    (msg, val) = pcie_probe_bdf(hierarchy, bus, device, function, offset, *simple_atoms)
    if offset == 0 and "Destination: " in msg:
        msg = msg.split("Destination: ")[0]
    if val is None:
        return cli.command_return(
            f"Nothing found at the provided BDF (Bus, Device and Function){'+ offset' if offset != 0 else ''}{', together with provided atoms' if add_atoms else ''}.",
            None,
        )
    if not validate_probed_target(val):
        msg += f"""
Note! The probed target {val} may not be a PCIe function"""
    return cli.command_return(msg.rstrip(), val)


cli.new_command(
    "pcie-config-probe",
    pcie_probe_bdf_cmd,
    args=[
        cli.arg(
            cli.str_t, "hierarchy", "?", "", expander=hierarchy_top_expander_non_legacy
        ),
        cli.arg(cli.uint8_t, "bus"),
        cli.arg(cli.uint8_t, "device"),
        cli.arg(cli.uint8_t, "function"),
        cli.arg(cli.uint16_t, "offset", "?", default=0),
        cli.arg(cli.flag_t, "-ari"),
        cli.arg(cli.flag_t, "-add-atoms"),
    ],
    dynamic_args=("-add-atoms", atom_args),
    type=["Memory", "Inspection"],
    see_also=["pcie-config-read", "pcie-config-write"],
    alias="pcie-probe-bdf",
    short="probe PCIe hierarchy with a BDF",
    doc=f"""
Probe the PCIe Configuration space using
<arg>bus</arg>:<arg>device</arg>:<arg>function</arg> (B:D:F) values. The
<tt>-ari</tt> flag can be used to indicate an ARI BDF. When this flag is used,
<arg>device</arg> must be set to 0. Optionally, an <arg>offset</arg> can be
included, which will then reveal the register in a function's configuration bank
that is hit. If there is only one top-level PCIe hierarchy in the system, the
<arg>hierarchy</arg> argument can be omitted. The command will automatically
find the top-level PCIe hierarchy object.

{include_atoms_doc}

Note! The <tt>pcie_type</tt> atom will be ignored if it is set using
<tt>-add-atoms</tt> as that atom is added by this command.
""",
)
