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

import simics
import importlib
import os.path
import re

def riscv_create_custom_cpu_class(base_class_name, class_name, **parameters):

    class CustomCpuException(Exception):
        pass

    class ParameterLimit:
        def __init__(self, limit_entry):
            self.name = limit_entry[0]
            # limit_entry[1] is description, used in list... command
            self.kind = limit_entry[2]
            # limit_entry[3] is default value, used in list... command
            self.params = limit_entry[4:]

    def log_error(msg):
        simics.SIM_log_error(simics.SIM_get_object("sim"), 0, msg)
        return None

    def fail(msg=None):
        if msg:
            msg = ': ' + msg
        return log_error(f'Failed creating custom class "{class_name}"{msg}')

    def validate_class_name(cn):
        if not isinstance(cn, str):
            raise CustomCpuException(f'Illegal class name type {cn}, expected string')

        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_\-]*$', cn):
            raise CustomCpuException(f'"{cn}" is not a valid class name')

        try:
            simics.SIM_get_class(cn)
        except simics.SimExc_General:
            pass
        else:
            raise CustomCpuException(f'Class "{cn}" already registered')

    def validate_parameters(parameters, limits):
        def param_error(p, v, dsc):
            raise CustomCpuException(f'Parameter error {p} = {v}, {dsc}')

        def misa_hex(misa_v, plimit):
            mask_max = plimit.params[1]
            if isinstance(misa_v, int):
                if misa_v & mask_max != misa_v:
                    param_error('misa', f'0x{misa_v:x}', f'expected within 0x{mask_max:x}')
                return misa_v
            # TBD: Handle 'RV{32|64}... str
            param_error('misa', misa_v, 'expected integer')

        def validate_extension_class(p, cls_name):
            try:
                cls = simics.SIM_get_class(cls_name)
            except simics.SimExc_General as e:
                param_error(p, cls_name, str(e))

            if simics.VT_get_class_kind(cls) != simics.Sim_Class_Kind_Extension:
                param_error(p, cls_name, "expected extension class")

        ld = {pl[0] : ParameterLimit(pl) for pl in limits }
        vp = []
        for (pn, v) in parameters.items():
            if not pn in ld:
                raise CustomCpuException(f'Unknown parameter {pn}={v}')
            pl = ld[pn]
            if pl.kind == 'string':
                if not isinstance(v, str):
                    param_error(pn, v, 'string')
                if pn == 'extension_class':
                    validate_extension_class(pn, v)
                vp += [[pn, v]]
            elif pl.kind == 'bool':
                if not isinstance(v, bool):
                    param_error(pn, v, 'True or False')
                vp += [[pn, v]]
            elif pl.kind == 'misa':
                vp += [[pn, misa_hex(v, pl)]]
            else:
                if not isinstance(v, int):
                    param_error(pn, v, 'integer')
                if pl.kind == 'range':
                    low = pl.params[0]
                    high = pl.params[1]
                    if not low <= v <= high:
                        param_error(pn, v, f'in the range {low} to {high}')
                elif pl.kind == 'set':
                    if v not in pl.params[0]:
                        param_error(pn, v, f'one of {" ".join(map(str,pl.params[0]))}')
                else:
                    param_error(pn, v, f'unexpected parameter kind: {pl.kind}')
                vp += [[pn, v]]
        return vp

    try:
        bcls = simics.SIM_get_class(base_class_name)
        if not hasattr(bcls, 'customization_module'):
            raise CustomCpuException(f'Not a valid base class: {base_class_name}')

        cm = importlib.import_module(bcls.customization_module)

        validate_class_name(class_name)

        parameter_limits = cm.internal_get_parameter_limits(base_class_name)
        validated_parameters = validate_parameters(parameters, parameter_limits)

    except CustomCpuException as e:
        return fail(str(e))

    cls = cm.internal_create_custom_cpu_class(base_class_name,
                                              class_name,
                                              validated_parameters)

    if cls:
        rc = importlib.import_module(bcls.riscv_commands_module)
        rc.setup_processor_ui(simics.SIM_get_class_name(cls))

        return cls

    return fail()
