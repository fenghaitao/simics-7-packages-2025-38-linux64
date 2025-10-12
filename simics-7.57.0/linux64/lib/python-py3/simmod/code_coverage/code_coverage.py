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

import json

import pyobj
import simics
import conf
import cli
import re

from . import coverage_data
from . import common
from . import html_report
from . import analyzer
from . import combine_reports
from . import filter_mappings
from . import coverage_to_lcov as lcov
from . import coverage_to_csv as to_csv

def default_cov_data():
    return {'version': 1,
            'features': {'access_count': False,
                         'branch_coverage': False}}

class code_coverage(pyobj.ConfObject):
    """Collect code coverage"""
    _class_kind = simics.Sim_Class_Kind_Pseudo
    _class_desc = "code coverage collector"

    def _initialize(self):
        super()._initialize()
        self.tcf = simics.SIM_get_debugger()
        self.query_iface = self.tcf.iface.debug_query
        self.notify_iface = self.tcf.iface.debug_notification
        self.context_query = None
        self.create_cid = None
        self.destruction_cid = None
        self.ctx_id = None
        self.tree_query = None
        self.cov_data = default_cov_data()
        self.curr_cov_data = {}
        self.executed_instructions = None
        self.branches = None
        self.cc_helper = simics.SIM_create_object(
            "code_coverage_helper", f"{self.obj.name}.helper", [])
        self.helper_iface = self.cc_helper.iface.code_coverage
        self.is_collecting = False

        self.cc_path_maps = []
        self.cached_tcf_path_maps = []
        self.activate_cid = None
        self.deactivate_cid = None
        self.module_update_cid = None
        self.data_label_patterns = [re.compile(r"^\.LC\d+")]
        self.known_cpu_classes = {}

    def _pre_delete(self):
        try:
            self.__cancel_callbacks()
        except common.CodeCoverageException() as e:
            simics.SIM_log_error(self.obj, 0, str(e))
        super()._pre_delete()

        # Removing helper should stop any active collection for it.
        simics.SIM_delete_object(self.cc_helper)

    def access_count(self):
        return self.cov_data['features'].get('access_count', False)

    def add_access_count(self):
        if self.access_count():
            return
        self.cov_data['features']['access_count'] = True


    def branch_coverage(self):
        return self.cov_data['features'].get('branch_coverage', False)

    def add_branch_cov(self):
        if self.branch_coverage():
            return
        self.cov_data['features']['branch_coverage'] = True

    def linear(self):
        return self.cov_data['features'].get('linear', False)

    def add_linear(self):
        self.cov_data['features']['linear'] = True

    def _info(self):
        info = [("Context query", self.context_query),
                ("Branch coverage", self.branch_coverage()),
                ("Access count", self.access_count())]
        if self.linear():
            info.append(("Linear addresses", True))
        return [("Coverage", info)]

    def _status(self):
        return [("Coverage", [("Collecting", self.is_collecting),
                              ("Context ID", self.ctx_id)])]

    def __report_error_no_exception(self, msg):
        errors = self.cov_data.setdefault("errors", [])
        errors.append([common.CC_Error_Other, str(msg)])

    def __report_error(self, msg):
        self.__report_error_no_exception(msg)
        raise common.CodeCoverageException(msg)

    class context_id(pyobj.Attribute):
        "Context ID for which code coverage is being performed"
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = "s|n"
        def getter(self):
            return self._up.ctx_id

    class is_collecting(pyobj.Attribute):
        "True if code coverage is collecting data"
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = "b"
        def getter(self):
            return self._up.is_collecting

    class helper(pyobj.Attribute):
        "Code coverage helper object"
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = "o"
        def getter(self):
            return self._up.cc_helper

    class data_label_patterns(pyobj.Attribute):
        """Patterns (as regular expressions) for functions that should be
        treated as data labels."""
        attrattr = simics.Sim_Attr_Pseudo | simics.Sim_Attr_Internal
        attrtype = "[s*]"
        def getter(self):
            return [x.pattern for x in self._up.data_label_patterns]

        def setter(self, value):
            patterns = []
            for pattern in value:
                try:
                    patterns.append(re.compile(pattern))
                except re.error as e:
                    simics.SIM_attribute_error(
                        'Illegal regexp for "%s": "%s"' % (pattern, e))
                    return simics.Sim_Set_Illegal_Value
            self._up.data_label_patterns = patterns

    def module_update_cb(self, data):
        try:
            self.sync()
        except common.CodeCoverageException as e:
            self.error(e)

    def context_created_cb(self, cbdata, tcf_obj, ctx_id, updated):
        self.log("Context '%s' created" % ctx_id)
        (old_contexts, query) = cbdata
        (err_code, new_contexts) = self.query_iface.matching_contexts(query)
        if err_code != simics.Debugger_No_Error:
            self.error("Failed to find matching contexts: %s" % new_contexts)
            return
        match_contexts = tuple(set(new_contexts) - set(old_contexts))
        if len(match_contexts) == 0:
            self.error("No new contexts found during context creation callback")
            return

        # Cancel creation breakpoint
        assert self.create_cid is not None
        self.tcf.iface.debug_notification.cancel(self.create_cid)
        self.create_cid = None

        # Start profiling
        (rc, unique_ctx_id) = common.get_unique_ctx(self.tcf, match_contexts)
        if not rc:
            self.error("Could not get unique context during creation of new"
                       " context: %s" % unique_ctx_id)
            return
        try:
            self.__start(unique_ctx_id, True)
        except common.CodeCoverageException as e:
            self.error(e)

    def wait_for_context(self, contexts, context_query, branch_cov,
                         access_count, linear):
        # Include children as notify_context_creation will only notify on
        # contexts that has state. The /** append will match both context query
        # or any children of that. It works fine to have /**/** at the end,
        # which works that same as one /**, so no need to check the original
        # context query for that. */
        query_with_children = "%s/**" % context_query
        self.log("Wait for context that matches '%s'" % query_with_children, 4)
        (err, cid) = self.tcf.iface.debug_notification.notify_context_creation(
            query_with_children, self.context_created_cb,
            (contexts, context_query))
        if err != simics.Debugger_No_Error:
            self.__report_error(cid)
        self.create_cid = cid
        if branch_cov:
            self.add_branch_cov()
        if access_count:
            self.add_access_count()
        if linear:
            self.add_linear()

    def log(self, msg, level = 4):
        simics.SIM_log_info(level, self.obj, 0, msg)

    def error(self, msg):
        # Cancel any callbacks on error if possible as coverage
        # collection is corrupted if it has started.
        try:
            self.__cancel_callbacks()
        except common.CodeCoverageException:
            pass
        simics.SIM_log_error(self.obj, 0, str(msg))

    def __activated(self, cb_data, obj, ctx_id, cpu):
        self.log("context '%s' activated on '%s'" % (ctx_id, cpu.name), 4)
        self.__start_collecting_instructions(cpu)

    def __deactivated(self, cb_data, obj, ctx_id, cpu):
        self.log("context '%s' deactivated on '%s'" % (ctx_id, cpu.name), 4)
        self.__stop_collecting_instructions(cpu)

    def __start_collecting_instructions(self, cpu):
        self.log("start collection on '%s', access_count: %s"
                 % (cpu.name, "enabled" if self.access_count()
                    else "disabled"), 4)
        self.helper_iface.start_collecting_instructions(
            cpu, self.branch_coverage(), self.access_count(), self.linear())
        self.__update_global_cpu_classes(cpu)

    def __stop_collecting_instructions(self, cpu):
        self.log("stop collection on '%s'" % cpu.name, 4)
        self.helper_iface.stop_collecting_instructions(cpu)

    def __active_cpus_for_context_id(self):
        if self.ctx_id is None:
            self.__report_error("active cpus called without any context id set")

        assert self.tree_query is not None
        (err, matching) = self.query_iface.matching_contexts(self.tree_query)
        if err != simics.Debugger_No_Error:
            self.__report_error("Failed to get contexts: %s" % matching)

        active_tracker_cpus = []
        matching_cpus = []

        for ctx_id in matching:
            (err, cpu) = self.query_iface.get_active_processor(ctx_id)
            if err == simics.Debugger_Context_Is_Not_Active:
                # Not active
                continue
            if err != simics.Debugger_No_Error:
                self.__report_error("Failed to get active cpu for '%s': %s"
                                    % (ctx_id, cpu))


            # Determine if the context is a tracker node or a cpu context
            (err, obj) = self.query_iface.object_for_context(ctx_id)
            if err == simics.Debugger_Missing_Object:
                # Tracker node context
                active_tracker_cpus.append(cpu)
            elif err != simics.Debugger_No_Error:
                self.__report_error("Failed to get object for '%s': %s"
                                    % (ctx_id, obj))
            else:
                if cpu != obj:
                    self.__report_error("Failed getting cpu object %s != %s"
                                        % (cpu.name, obj.name))
                matching_cpus.append(cpu)

        # If any tracker node matched return that otherwise any cpu context that
        # matched.
        return active_tracker_cpus or matching_cpus

    def __is_last_child_with_state(self, ctx_id):
        # This assumes that only one context with state is removed at
        # the same time.
        assert self.ctx_id is not None
        (err, matching) = self.query_iface.matching_contexts(self.tree_query)
        if err != simics.Debugger_No_Error:
            self.__report_error("Failed to matching contexts for '%s': %s"
                                % (self.tree_query, matching))

        matching_with_state = []
        for ctx in matching:
            (err, match) = self.query_iface.context_has_state(ctx)
            if (not err) and match:
                matching_with_state.append(ctx)

        if len(matching_with_state) == 1 and matching_with_state[0] == ctx_id:
            return True
        return False


    def __stop_if_last_child_destroyed(self, ctx_id):
        if not self.__is_last_child_with_state(ctx_id):
            return
        self.stop(True)
        self.log("Done collecting code coverage for '%s'" % self.ctx_name(), 1)

        self.ctx_id = None

    def __destroy_cb(self, data, obj, ctx_id):
        self.log("Context '%s' was destroyed" % ctx_id)
        try:
            self.__stop_if_last_child_destroyed(ctx_id)
        except common.CodeCoverageException as e:
            self.error(e)

    def __install_callbacks(self):
        assert self.tree_query is not None
        assert self.notify_iface
        # We can only listen to contexts with state, so we need to
        # check in the callback that all children have been removed
        # before stopping.
        (err, cid) = self.notify_iface.notify_context_destruction(
            self.tree_query, self.__destroy_cb, None)
        if err != simics.Debugger_No_Error:
            self.__report_error("Unable to listen to context destruction"
                                " notifications: %s" % cid)
        self.destruction_cid = cid

        (err, cid) = self.notify_iface.notify_activated(
            self.tree_query, self.__activated, None)
        if err != simics.Debugger_No_Error:
            self.__report_error(
                "Unable to listen to activation notifications: %s" % cid)
        self.activate_cid = cid

        (err, cid) = self.notify_iface.notify_deactivated(
            self.tree_query, self.__deactivated, None)
        if err != simics.Debugger_No_Error:
            self.__report_error(
                "Unable to listen to activation notifications: %s" % cid)
        self.deactivate_cid = cid

        internal_iface = self.tcf.iface.debug_internal
        (err, cid) = internal_iface.notify_map_changes(
            self.ctx_id, self.module_update_cb, None)
        if err != simics.Debugger_No_Error:
            self.__report_error("Unable to listen to module updates: %s" % cid)
        self.module_update_cid = cid

    def __cancel_callbacks(self):
        if self.module_update_cid is not None:
            internal_iface = self.tcf.iface.debug_internal
            (err, msg) = internal_iface.cancel_map_changes(
                self.ctx_id, self.module_update_cid)
            if err != simics.Debugger_No_Error:
                self.__report_error(
                    "Unable to stop listening to module updates: %s" % msg)
            self.module_update_cid = None

        assert self.notify_iface
        if self.activate_cid is not None:
            (err, msg) = self.notify_iface.cancel(self.activate_cid)
            if err != simics.Debugger_No_Error:
                self.__report_error(
                    "Unable to stop listening to activation callback: %s" % msg)
            self.activate_cid = None

        if self.deactivate_cid is not None:
            (err, msg) = self.notify_iface.cancel(self.deactivate_cid)
            if err != simics.Debugger_No_Error:
                self.__report_error(
                    "Unable to stop listening to deactivation callback: %s"
                    % msg)
            self.deactivate_cid = None

        if self.destruction_cid is not None:
            (err, msg) = self.notify_iface.cancel(self.destruction_cid)
            if err != simics.Debugger_No_Error:
                self.__report_error("Unable to stop listening to context"
                                    " destruction callbacks: %s" % msg)
            self.destruction_cid = None

    def __check_for_branch_coverage_support(self, cpus):
        if not self.branch_coverage():
            return

        cpus_that_supports_branch_coverage = []
        for cpu in cpus:
            if self.helper_iface.supports_branch_coverage(cpu):
                cpus_that_supports_branch_coverage.append(cpu)

        if len(cpus_that_supports_branch_coverage) == 0:
            # Error will be reported when exception is caught.
            raise common.CodeCoverageException(
                'No processors support branch coverage')

        if len(cpus_that_supports_branch_coverage) < len(cpus):
            self.log('Branch coverage is only supported on a subset of cpus', 1)
            cpus_missing_branch = list(
                set(cpus) - set(cpus_that_supports_branch_coverage))
            for cpu in cpus_missing_branch:
                self.__report_error_no_exception(
                    f'{cpu} does not support branch coverage')

    def __begin_collecting(self):
        self.log("Collecting coverage for context: %s" % self.ctx_id)
        active = self.__active_cpus_for_context_id()
        self.__check_for_branch_coverage_support(active)

        self.__install_callbacks()
        self.log("Active cpus for '%s': %s" % (self.ctx_id, active))
        for cpu in active:
            self.__start_collecting_instructions(cpu)

    def start(self, ctx_id, branch_cov, access_count, linear):
        if access_count:
            self.add_access_count()
        if branch_cov:
            self.add_branch_cov()
        if linear:
            self.add_linear()
        self.__start(ctx_id, False)

    def __start_without_exception_check(self, ctx_id):
        (err, query) = self.query_iface.query_for_context_tree(self.ctx_id)
        if err != simics.Debugger_No_Error:
            self.__report_error("Failed to get context tree: %s" % query)
        self.tree_query = query

        self.__update_memory_map_entries()
        self.__begin_collecting()
        self.is_collecting = True

    def __start(self, ctx_id, async_call):
        self.ctx_id = ctx_id
        if async_call:
            self.log("Starting coverage for '%s'%s"
                     % (self.ctx_name(),
                        " (with branch coverage)" if self.branch_coverage()
                        else ""), 1)
        try:
            self.__start_without_exception_check(ctx_id)
        except common.CodeCoverageException as e:
            # Clean up any installed callbacks, but raise the original
            # exception even if cancel raises an error.
            try:
                self.__cancel_callbacks()
            except common.CodeCoverageException:
                pass
            self.__report_error("Error while starting coverage: %s" % e)

    def ctx_name(self):
        assert self.ctx_id is not None
        (ret, name) = self.query_iface.context_name(self.ctx_id)
        if ret != simics.Debugger_No_Error:
            ctx_name = "id = %s" % self.ctx_id
        else:
            ctx_name =  name
        return ctx_name

    def __class_has_disassembly_iface(self, cpu_class):
        try:
            simics.SIM_get_class_interface(cpu_class, 'class_disassembly')
        except simics.SimExc_Lookup:
            return False
        except simics.SimExc_PythonTranslation:
            # Interface exists but cannot be translated to Python.
            pass
        return True

    def __update_known_cpu_classes(self, cpu_class):
        if cpu_class in self.known_cpu_classes:
            return
        self.known_cpu_classes[cpu_class] = self.__class_has_disassembly_iface(
            cpu_class)

    def __has_class_disassembly_iface(self, cpu_class):
        if cpu_class not in self.known_cpu_classes:
            self.__update_known_cpu_classes(cpu_class)
        return self.known_cpu_classes[cpu_class]

    def __update_global_cpu_classes(self, cpu):
        if not self.__has_class_disassembly_iface(cpu.classname):
            return
        cpu_classes = self.cov_data.setdefault('cpu_classes', [])
        if cpu.classname not in cpu_classes:
            cpu_classes.append(cpu.classname)

    def sync(self):
        if not self.is_collecting:
            # Only need to sync when data has been collected, not when
            # reports have been added.
            return
        self.log("Syncing coverage for '%s'" % self.ctx_id)
        self.__collect_executed_addresses()
        self.__build_mapping()
        self.executed_instructions = None
        self.branches = None
        self.__combine_cov_data(False)
        self.__update_memory_map_entries()

    def __combine_cov_data(self, ignore_addresses):
        self.curr_cov_data['features'] = self.cov_data['features']
        self.curr_cov_data['version'] = self.cov_data['version']
        combine_reports.combine_two(self.cov_data, self.curr_cov_data,
                                    ignore_addresses)
        self.curr_cov_data = {}

    def stop(self, async_call):
        if not self.is_collecting:
            msg = ("Trying to stop collecting data, but data is currently not"
                   " being collected")
            if async_call:
                self.__report_error(msg)
            else:
                raise common.CodeCoverageException(msg)

        self.__cancel_callbacks()
        for cpu in self.__active_cpus_for_context_id():
            self.__stop_collecting_instructions(cpu)
        self.sync()
        self.helper_iface.clean_up_after_collection()

        self.is_collecting = False
        self.cached_tcf_path_maps = self.__tcf_path_maps()

    def __collect_executed_addresses(self):
        self.executed_instructions = dict(
            self.helper_iface.get_collected_instructions())
        self.helper_iface.clear_collected_instructions()
        if self.branch_coverage():
            self.branches = dict(
                self.helper_iface.get_collected_branches())
            self.helper_iface.clear_collected_branches()

    def __update_memory_map_entries(self):
        setup_iface = self.tcf.iface.debug_setup
        (err, mmap_entries) = setup_iface.list_all_mappings(self.ctx_id)
        if err != simics.Debugger_No_Error:
            self.__report_error("Could not get mappings: %s" % mmap_entries)

        for mme in mmap_entries:
            if mme["size"] == 0:
                # TCF adds dummy mappings for OS Awareness node names,
                # they have size 0 and should be ignored.
                continue
            if mme["flags"] != 0 and mme["flags"] & 4 == 0:
                # Read/write/executable flags set, but the mapping is
                # set as not executable.
                continue
            coverage_data.add_mapping(self.curr_cov_data, mme["filename"],
                                      mme["address"], mme["size"],
                                      mme["file-offset"], mme["file-size"],
                                      mme.get("relocation", 0),
                                      mme["section-name"])

    def __build_mapping(self):
        for cpu_class in self.executed_instructions:
            self.__update_known_cpu_classes(cpu_class)
        coverage_data.add_executed_addresses(self.curr_cov_data,
                                             self.executed_instructions,
                                             self.access_count(),
                                             self.known_cpu_classes)
        if self.branch_coverage():
            coverage_data.add_branches(self.curr_cov_data, self.branches)

    def load(self, input_file):
        self.cov_data = coverage_data.from_raw_file(input_file)
        if not 'version' in self.cov_data:
            self.cov_data['version'] = 1
            self.cov_data['features'] = {}

    def add_report(self, input_file, ignore_addresses):
        a = analyzer.Analyzer(self.cov_data, self.log, self.data_label_patterns)
        a.read_report(input_file, ignore_addresses)
        self.cov_data = a.cov_data

    def __remove_errors_of_type(self, mapping, type_to_remove):
        common.remove_errors_of_type_from_mapping(mapping, type_to_remove)

    def __remove_disassembly_errors(self, mapping):
        for err_type in common.disassembly_error_types():
            self.__remove_errors_of_type(mapping, err_type)

    def __remove_address_info(self):
        for m in self.cov_data.get('mappings', []):
            if 'info' in m:
                m.pop('info')
                # 'info' will be referring to 'file_table', removing 'info'
                # makes 'file_table' invalid.
                m.pop('file_table', None)
                # Any source info has been removed so remove all errors related
                # to source info as well.
                self.__remove_errors_of_type(m, common.CC_Error_Source_Info)

            if 'removed_data' in m:
                # The removed data should be invalidated when info is removed as
                # this indicates what was not included in info.
                m.pop('removed_data')

            m.pop('disassembly_class', None)

            self.__remove_disassembly_errors(m)

    def __has_any_mappings(self):
        return len(self.cov_data.get('mappings', [])) > 0

    def __has_full_source_info(self):
        for m in self.cov_data.get('mappings', []):
            # Having both address info and file table for a mapping should mean
            # that source information has been added.
            if 'info' in m and 'file_table' in m:
                return True
        return False

    def __has_address_info(self):
        for m in self.cov_data.get('mappings', []):
            if 'info' in m:
                return True
        return False

    def __has_source_only_info(self):
        for m in self.cov_data.get('mappings', []):
            if 'src_info' in m:
                return True
        return False

    def __has_functions(self):
        for m in self.cov_data.get('mappings', []):
            if 'functions' in m or 'data_labels' in m:
                return True
        return False

    def __can_disassemble(self):
        a = analyzer.Analyzer(self.cov_data, self.log, self.data_label_patterns)
        return a.can_disassemble(self.path_maps())

    def disassemble(self, do_sync, by_function, remove_old):
        if do_sync:
            self.sync()
        if remove_old:
            self.__remove_address_info()

        # Always remove source only info. Only one 'info' format should be
        # present at once.
        self.__remove_source_only_info()

        a = analyzer.Analyzer(self.cov_data, self.log, self.data_label_patterns)
        return a.add_disassembly(self.cc_helper, self.path_maps(), by_function)

    def __remove_functions(self):
        for m in self.cov_data.get('mappings', []):
            for to_remove in ('functions', 'data_labels', 'exec_regions'):
                if to_remove in m:
                    m.pop(to_remove)
            self.__remove_errors_of_type(m, common.CC_Error_Functions)

    def add_functions(self, do_sync, remove_old, keep_data):
        if do_sync:
            self.sync()
        if remove_old:
            self.__remove_functions()
        if self.cov_data['features'].get('keep_data', False) != keep_data:
            # If keep_data state changes then old functions and info have to be
            # updated.
            self.__remove_functions()
            self.__remove_address_info()
            # Source only information can and will be kept.

        a = analyzer.Analyzer(self.cov_data, self.log, self.data_label_patterns)
        return a.add_functions(self.path_maps(), keep_data)

    def __remove_source_only_info(self):
        for m in self.cov_data.get('mappings', []):
            if 'src_info' not in m:
                continue
            m.pop('src_info')
            m.pop('file_table', None)
            self.__remove_errors_of_type(m, common.CC_Error_Source_Info)

    def __remove_source_info(self):
        for m in self.cov_data.get('mappings', []):
            info = m.get('info')
            if info is None:
                continue
            m.pop('file_table', None)
            for entry in info:
                if 'executable_lines' in entry:
                    entry.pop('executable_lines')
                if 'file_id' in entry:
                    entry.pop('file_id')

            self.__remove_errors_of_type(m, common.CC_Error_Source_Info)

    def add_source_info(self, do_sync, remove_old):
        if do_sync:
            self.sync()
        if remove_old:
            self.__remove_source_info()
        # Always remove any source only information. Only one format should
        # be present at once.
        self.__remove_source_only_info()

        if not self.__has_address_info():
            self.add_functions(False, False, False)
            self.disassemble(False, True, False)

        a = analyzer.Analyzer(self.cov_data, self.log, self.data_label_patterns)
        return a.add_source_info(self.cc_helper, self.path_maps())

    def add_source_only_info(self, do_sync, remove_old):
        if do_sync:
            self.sync()

        # Always remove source info of 'info' type if present. Only one format
        # should be present at once.
        if self.__has_address_info():
            self.__remove_address_info()

        if remove_old:
            self.__remove_source_only_info()
            self.__remove_functions()

        if not self.__has_functions():
            self.add_functions(False, False, False)

        a = analyzer.Analyzer(self.cov_data, self.log, self.data_label_patterns)
        return a.add_source_only_info(self.cc_helper, self.path_maps())

    def remove_analyzer_info(self):
        self.sync()
        self.__remove_functions()
        self.__remove_address_info()
        self.__remove_source_only_info()

    def __add_needed_analyzer_data(self, source_only_data, only_disassembly,
                                   keep_data):
        if not self.__has_any_mappings():
            # No analyzing can be done without mappings. Return early to avoid
            # trying and printing.
            return

        # If source only data is already present then use that format for any
        # additional source info.
        if source_only_data or self.__has_source_only_info():
            if only_disassembly:
                # only_disassembly should have been checked if source_only_data
                # is set.
                assert not source_only_data
                raise common.CodeCoverageException(
                    "Cannot output disassembly only as earlier data contains"
                    " 'src_info' format")
            self.add_source_only_info(False, False)
        # If only_disassembly is specified when __can_disassemble() is False
        # then disassembling will fail, but let it do so instead of having
        # another way of reporting error here.
        elif not only_disassembly and not self.__can_disassemble():
            # Don't remove any previously added source information as it could
            # have been added on a different host where disassembling was
            # possible. We still want to be able to output reports with that
            # source information on current host.
            if self.__has_full_source_info():
                return
            print('Disassembly not supported for binaries - source only'
                  ' output')
            self.add_source_only_info(False, False)
        else:
            self.add_functions(False, False, keep_data)
            self.disassemble(False, True, False)
            if not only_disassembly:
                self.add_source_info(False, False)

    def html_report(self, output, no_disassembly,
                    only_with_src, no_summary_table,
                    no_unknown_addrs, no_unknown_modules, only_disassembly,
                    include_opcode, keep_data, max_errors_per_mapping,
                    report_name, summary_per_file, show_line_functions,
                    no_module_line_cov, include_line, source_only_data,
                    source_files_base_path, tree_summary, no_function_coverage):
        self.sync()
        self.__add_needed_analyzer_data(source_only_data, only_disassembly,
                                        keep_data)
        self.check_for_errors()

        try:
            return html_report.output_html(
                output, self.cov_data, self.path_maps(),
                no_disassembly, only_with_src, no_summary_table,
                self.access_count(), no_unknown_addrs, no_unknown_modules,
                only_disassembly, include_opcode, max_errors_per_mapping,
                report_name, summary_per_file, show_line_functions,
                no_module_line_cov, include_line, source_files_base_path,
                tree_summary, no_function_coverage)
        except html_report.HTMLReportException as e:
            raise common.CodeCoverageException(
                "Failed to generate HTML report: %s" % e)

    def lcov_output(self, output, counter_option, keep_data, source_only_data):
        self.sync()
        self.__add_needed_analyzer_data(source_only_data, False, keep_data)
        self.check_for_errors()
        try:
            tracefiles = lcov.output_lcov(self.cov_data, output,
                                          self.path_maps(), counter_option)
        except lcov.LCOVReportException as e:
            raise common.CodeCoverageException(e)
        return tracefiles

    def csv_output(self, output):
        self.sync()
        self.__add_needed_analyzer_data(False, False, False)
        self.check_for_errors()
        try:
            to_csv.output_csv(self.cov_data, output)
        except to_csv.CSVReportException as e:
            raise common.CodeCoverageException(e)

    def __tcf_path_maps(self):
        (ret, val) = self.tcf.iface.debug_setup.path_map_entries_for_ctx(
            self.ctx_id)
        if ret == simics.Debugger_Unknown_Context:
            # If we have stopped and continued the context might have
            # been destroyed, but we will have removed destruction
            # callback.
            return self.cached_tcf_path_maps
        if ret != simics.Debugger_No_Error:
            self.__report_error("Failed to get tcf path maps: %s" % val)
        return [[v['source'], v['destination']] for v in val]

    def tcf_path_maps(self):
        if self.ctx_id is None:
            return self.cached_tcf_path_maps
        return self.__tcf_path_maps()

    def path_maps(self):
        return self.cc_path_maps + self.tcf_path_maps()

    def add_path_map(self, src, dst):
        self.cc_path_maps.append((src, dst))

    def clear_path_maps(self):
        self.cc_path_maps = []

    def list_path_maps(self):
        # Cannot contain tuples as it will be converted to a CLI value.
        return [[pm_from, pm_to] for (pm_from, pm_to) in self.cc_path_maps]

    def report(self):
        pass

    def filter_mappings(self, map_filters, file_filters, remove):
        if self.is_collecting:
            raise common.CodeCoverageException(
                "Collecting coverage must be stopped before filtering mappings")
        self.sync()
        return filter_mappings.filter_mappings(self.cov_data, map_filters,
                                               file_filters, remove)

    def remove_unknown_addresses(self):
        self.sync()
        return filter_mappings.remove_unknown_addresses(self.cov_data)

    def list_mappings(self, sort_by_file, remove_dirs):
        self.sync()
        mappings = self.cov_data.get("mappings", [])
        res = []
        for mapping in mappings:
            m = mapping["map"]
            sym_file = m["symbol_file"]
            if remove_dirs:
                sym_file = sym_file.rsplit("\\")[-1].rsplit("/")[-1]
            res.append([m["address"], m["address"] + m["size"] - 1, sym_file])
        if sort_by_file:
            res.sort(key=lambda x: x[2])
        else:
            res.sort(key=lambda x: x[0])
        return res

    def combine_mappings(self):
        if self.is_collecting:
            raise common.CodeCoverageException(
                "Collecting coverage must be stopped before filtering mappings")
        self.sync()

        mappings = self.cov_data.get("mappings")
        if not mappings:
            return 0

        return combine_reports.join_mappings_ignoring_addresses(
            mappings, self.cov_data["features"]["access_count"],
            self.cov_data["features"]["branch_coverage"])

    def save(self, output_file, overwrite):
        self.sync()
        self.check_for_errors()

        coverage_data.to_raw_file(output_file, overwrite, self.cov_data)

    def __add_disassembly_error_for_mapping(self, mapping, msg):
        errors = mapping.setdefault("errors", [])
        err = [common.CC_Error_Disassemble, msg]
        for existing_err in errors:
            if existing_err == err:
                return
        errors.append(err)

    def check_for_errors(self):
        for m in self.cov_data.get("mappings", []):
            info = m.get("info")
            if info is None:
                continue
            functions = m.get("functions", {})
            if functions:
                mapping_start = m["map"]["address"]
                mapping_end = mapping_start + m["map"]["size"] - 1
                function_addrs = set(common.function_start_addresses_in_range(
                    functions, mapping_start, mapping_end, False))
            else:
                function_addrs = None
            covered = set(m.get("covered", {}))
            for insn_info in info:
                addr = insn_info["address"]
                if function_addrs and addr in function_addrs:
                    function_addrs.remove(addr)
                if covered and addr in covered:
                    covered.remove(addr)
            if covered:
                for addr in sorted(covered):
                    self.__add_disassembly_error_for_mapping(
                        m, "Address 0x%x has been run but does not have any"
                        " disassembly" % addr)
            if function_addrs:
                for addr in sorted(function_addrs):
                    self.__add_disassembly_error_for_mapping(
                        m, "No instruction associated with function '%s' at"
                        " 0x%x"
                        % (functions[addr].get("name", "<unknown>"), addr))
