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
import simics
import conf
import table

#
# -------------------- list-telemetry-classes -------------
#

class TelemetryBase:

    def __init__(self, obj):
        self.obj = obj

    def iface(self):
        return self.obj.iface.telemetry

    def class_name(self, cid):
        return self.iface().get_telemetry_class_name(cid)


class TelemetryClass(TelemetryBase):

    def __init__(self, obj, class_id):
        super().__init__(obj)
        self.cid = class_id

    def class_id(self):
        return self.cid

    def telemetries(self):
        tids = []
        tid = 0
        while self.iface().get_telemetry_name(self.cid, tid):
            tids.append(tid)
            tid += 1
        return tids


class TelemetryClasses(TelemetryBase):

    def __init__(self, obj):
        super().__init__(obj)

    def all_classes(self, name_prefix=None):
        cids = []
        cid = 0
        name = self.iface().get_telemetry_class_name(cid)
        while name:
            if not name_prefix or name.startswith(name_prefix):
                cids.append(cid)
            cid += 1
            name = self.iface().get_telemetry_class_name(cid)
        return cids

    def class_names(self, name_prefix=None):
        return [self.class_name(cid) for cid in self.all_classes(name_prefix)]


class TelemetryClassesList:

    def __init__(self, providers, class_name_prefix):
        self.providers = providers
        self.class_name_prefix = class_name_prefix
        self.rows = []

    def _create_table(self):
        props = [
            (table.Table_Key_Columns, [
                [(table.Column_Key_Name, "Provider")],
                [(table.Column_Key_Name, "Telemetry Class")],
                [(table.Column_Key_Name, "Telemetry Description")],
            ])
        ]
        if len(self.rows):
            tbl = table.Table(props, self.rows)
            return tbl.to_string(rows_printed=0, no_row_column=True)
        return ""

    def _fill_rows(self):
        for obj in self.providers:
            if simics.SIM_c_get_interface(obj, "telemetry"):
                tcs = TelemetryClasses(obj)
                for cid in tcs.all_classes(self.class_name_prefix):
                    tcname = tcs.class_name(cid)
                    tcdescr = tcs.iface().get_telemetry_class_description(cid)
                    self.rows.append([obj.name, tcname, tcdescr])
            else:
                print("Object does not provide telemetry-interface: %s" %
                      (obj.name))

    def get_table_and_rows(self):
        self._fill_rows()
        return (self._create_table(), self.rows)


class TelemetryClassListDetails(TelemetryClass):

    def __init__(self, obj, cid):
        super().__init__(obj, cid)
        self.rows = []
        self.cli_rows = []

    def _create_table(self):
        ti = self.iface()
        cid = self.class_id()
        cname = self.class_name(cid)
        cdescr = ti.get_telemetry_class_description(cid)
        cols = [
            [(table.Column_Key_Name, "Telemetry")],
            [(table.Column_Key_Name, "Current value"),
             (table.Column_Key_Int_Radix, 10),
             (table.Column_Key_Int_Grouping, True)],
            [(table.Column_Key_Name, "Type")],
            [(table.Column_Key_Name, "Description")],
        ]
        extra_headers = [
            (table.Extra_Header_Key_Row, [  # row 1
                [(table.Extra_Header_Key_Name,
                  "Object: %s\nClass: %s\nDescription: %s" % (self.obj.name,
                                                              cname, cdescr))]
            ])
        ]
        props = [
            (table.Table_Key_Columns, cols),
            (table.Table_Key_Extra_Headers, extra_headers)
        ]
        if len(self.rows):
            tbl = table.Table(props, self.rows)
            return tbl.to_string(rows_printed=0, no_row_column=True)
        return ""

    def _get_value_type(self, value):
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return "string"
        return "-"

    def _add_telemetries(self):
        ti = self.iface()
        cid = self.class_id()
        cname = self.class_name(cid)
        for tid in self.telemetries():
            name = ti.get_telemetry_name(cid, tid)
            value = ti.get_value(cid, tid)
            vtype = self._get_value_type(value)
            descr = ti.get_telemetry_description(cid, tid)
            self.rows.append((name, value, vtype, descr))
            cli_row = [self.obj.name, cname, name, value, vtype, descr]
            self.cli_rows.append(cli_row)
        return len(self.rows)

    def get_table_and_rows(self):
        if self._add_telemetries():
            return (self._create_table(), self.cli_rows)
        else:
            return ("", [])


class TelemetryClassesListDetails:

    def __init__(self, providers, class_name_prefix):
        self.providers = providers
        self.class_name_prefix = class_name_prefix

    def get_table_and_rows(self):
        msg = ""
        rows = []
        for obj in self.providers:
            if simics.SIM_c_get_interface(obj, "telemetry"):
                tcs = TelemetryClasses(obj)
                for cid in tcs.all_classes(self.class_name_prefix):
                    tcld = TelemetryClassListDetails(obj, cid)
                    one_msg, one_rows = tcld.get_table_and_rows()
                    if len(one_msg):
                        msg += one_msg + "\n"
                        rows += one_rows
            else:
                print("Object does not provide telemetry-interface: %s" %
                      (obj.name))
        return (msg, rows)


def get_telemetry_cpus():
    return [cpu for cpu in simics.SIM_get_all_processors()
            if simics.SIM_c_get_interface(cpu, "telemetry")]


def get_telemetry_classes(obj_prefix):
    def get_valid_object(obj_name):
        if obj_name:
            try:
                obj = simics.VT_get_object_by_name(obj_name)
                if obj and simics.SIM_c_get_interface(obj, "telemetry"):
                    return obj
            except simics.SimExc_Generic:
                pass
        return None

    def get_all_classes(obj):
        return {cname for cname in TelemetryClasses(obj).class_names()}

    classes = set()
    obj = get_valid_object(obj_prefix)
    if obj:
        classes = get_all_classes(obj)
    elif not obj_prefix:
        for obj in get_telemetry_cpus():
            classes.update(get_all_classes(obj))
    return list(classes)


def list_telemetry_classes_cmd(provider, tclass, all):
    if not all and tclass and provider:
        all_classes = get_telemetry_classes(provider)
        all = tclass in all_classes

    if provider:
        try:
            obj = simics.SIM_get_object(provider)
        except simics.SimExc_General as e:
            raise cli.CliError(str(e))
        if not simics.SIM_c_get_interface(obj, "telemetry"):
            raise cli.CliError(f'{provider} is not a valid telemetry object')
        providers = [obj]
    else:
        providers = get_telemetry_cpus()

    if all:
        tl = TelemetryClassesListDetails(providers, tclass)
    else:
        tl = TelemetryClassesList(providers, tclass)
    msg, rows = tl.get_table_and_rows()
    return cli.command_verbose_return(msg, rows)


def telemetry_cpu_expander(prefix, namespace, args):

    def includes_tclass(obj, prefix):
        return len(TelemetryClasses(obj).class_names(prefix))

    tclass_prefix = args[1]
    candidates = [obj.name for obj in get_telemetry_cpus()
                  if includes_tclass(obj, tclass_prefix)]
    return cli.get_completions(prefix, candidates)


def telemetry_class_expander(prefix, namespace, args):
    provider_prefix = args[0]
    candidates = get_telemetry_classes(provider_prefix)
    return cli.get_completions(prefix, candidates)


def register_list_telemetry_classes_command():
    cli.new_command("list-telemetry-classes",
                    list_telemetry_classes_cmd,
                    [cli.arg(cli.str_t, "provider", "?",
                             default=None,
                             expander=telemetry_cpu_expander),
                     cli.arg(cli.str_t, "class_name", "?",
                             default=None,
                             expander=telemetry_class_expander),
                     cli.arg(cli.flag_t, "-all", "?",
                             default=False)],
                    short="list telemetry classes",
                    doc=("""List telemetry classes of provided
 by cpu objects.
If <arg>provider</arg> object is specified telemetry classes provided by that
 object is listed. In this case <arg>provider</arg> does not have to be a cpu
 object.

The <arg>class_name</arg> filters out provided classes where the class name
 does not starts with <arg>class_name</arg>.

With the <tt>-all</tt> flag all telemetries in the telemetry class is listed.
If both <arg>provider</arg> and <arg>class_name</arg> is supplied and
 <arg>class_name</arg> matches the name of a telemetry class that is provided
 by <arg>provider</arg> then all telemetries of that class is listed."""))

register_list_telemetry_classes_command()
