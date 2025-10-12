# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


def name_to_module(func, filename):
    def strip_end(s, e):
        if s.endswith(e):
            return s[:len(s) - len(e)]
        else:
            return s

    interpreter_funcs = ["_service_routines", "_ep_", "_dec_", "_disassemble_", "_translate_", "_interpret"]
    jit_compiler_funcs = ["turbo_opcode_type", "op_writes_reg", "get_constant", "turbo_host_opt", "turbo_regalloc", "turbo_opt_scan_mark", "remove_unused_regs", "compile_block", "turbo_opt_optimize", "turbo_opt_template_to_block", "turbo_opt_scan", "turbo_opt_block_to_template", "turbo_alloc_turbo_block_t", "turbo_opt_allocate_target_registers", "use_def_analysis", "turbo_create_hostop", "mark_reachable_instrs", "collect_live_dead_ranges", "rewrite_insert_fills_spills", "_Z12operand_sizeP12turbo_hostopi", "turbo_opt_create_op", "turbo_opt_copy_propagate", "turbo_md_asm", "turbo_opt_create_reg", "opcode_type", "turbo_opt_scan_mark_reg_def_imm", "make_interference_graph", "v9_turbo_decoder", "turbo_opt_create_params", "check_insert_virt_bp", "rewrite_reg", "accum_removed_block", "turbot_v9_on_x86", "turbo_opt_block_to_template_mark", "_Z17rex_prefix_lengthP14turbot_block_tP12turbo_hostopi", "turbo_get_template", "turbot_host_x86", "create_turbot_register", "turbo_umod32", "op_push_branches", "mark_reachable_instrs_dfs", "liveness_analysis", "turbo_opt_scan_mark_reg_def_reg", "_Z18encode_instructionP9processorP13turbo_compileP14turbot_bloc", "turbo_opt_scan_mark_reg_use", "turbo_trace_instruction", "_Z17encode_rex_prefixPPhP14turbot_block_tP12turbo_hostopii", "find_extra_spill_area_offsets_dfs", "turbo_opt_inline_immediates", "turbo_opt_remove_jumps", "turbo_opt_scan_mark_reg_def_unknown", "turbo_opt_op_is_fallthrough", "allocate_add_alloc_reg", "turbo_regalloc_fp", "is_parameter_constant"]
    softfloat_funcs = ["addFloat128Sigs",
                       "addFloat32Sigs",
                       "addFloat32xSigs",
                       "addFloat64Sigs",
                       "addFloatx80Sigs",
                       "estimateDiv128To64",
                       "estimateSqrt32",
                       "exp2_co",
                       "float128ToCommonNaN",
                       "float128_add",
                       "float128_div",
                       "float128_eq",
                       "float128_eq_signaling",
                       "float128_exp",
                       "float128_is_nan",
                       "float128_is_signaling_nan",
                       "float128_kind",
                       "float128_le",
                       "float128_le_quiet",
                       "float128_lt",
                       "float128_lt_quiet",
                       "float128_mul",
                       "float128_rem",
                       "float128_round_to_int",
                       "float128_sign",
                       "float128_sqrt",
                       "float128_sub",
                       "float128_to_float32",
                       "float128_to_float64",
                       "float128_to_floatx80",
                       "float128_to_int64",
                       "float32ToCommonNaN",
                       "float32_add",
                       "float32_cmp_quiet",
                       "float32_div",
                       "float32_eq",
                       "float32_eq_signaling",
                       "float32_exp",
                       "float32_frac",
                       "float32_gt",
                       "float32_is_nan",
                       "float32_is_signaling_nan",
                       "float32_kind",
                       "float32_le",
                       "float32_le_quiet",
                       "float32_lt",
                       "float32_lt_quiet",
                       "float32_mul",
                       "float32_mul_add",
                       "float32_mul_sub",
                       "float32_rem",
                       "float32_round_to_int",
                       "float32_sign",
                       "float32_sqrt",
                       "float32_sub",
                       "float32_to_float128",
                       "float32_to_float64",
                       "float32_to_floatx80",
                       "float32_to_int32",
                       "float32_to_int32_round_to_zero",
                       "float32_to_int64",
                       "float32_to_int64_round_to_zero",
                       "float32x_add",
                       "float32x_eq",
                       "float32x_gt",
                       "float32x_mul",
                       "float32x_mul_add",
                       "float32x_mul_sub",
                       "float32x_sub",
                       "float32x_to_float64",
                       "float64ToCommonNaN",
                       "float64_add",
                       "float64_cmp_quiet",
                       "float64_cmp_zero",
                       "float64_div",
                       "float64_eq",
                       "float64_eq_signaling",
                       "float64_exp",
                       "float64_exp2",
                       "float64_frac",
                       "float64_is_nan",
                       "float64_is_signaling_nan",
                       "float64_kind",
                       "float64_le",
                       "float64_le_quiet",
                       "float64_log2",
                       "float64_lt",
                       "float64_lt_quiet",
                       "float64_mul",
                       "float64_mul_add",
                       "float64_mul_sub",
                       "float64_rem",
                       "float64_round_to_int",
                       "float64_sign",
                       "float64_sqrt",
                       "float64_sub",
                       "float64_to_float128",
                       "float64_to_float32",
                       "float64_to_float32x",
                       "float64_to_floatx80",
                       "float64_to_int32",
                       "float64_to_int32_round_to_zero",
                       "float64_to_int64",
                       "float64_to_int64_round_to_zero",
                       "float_detect_tininess",
                       "float_exact_overflow",
                       "float_exact_underflow",
                       "float_raise",
                       "float_signed_indefinite",
                       "float_to_int_signed_indefinite",
                       "floatx80ToCommonNaN",
                       "floatx80_add",
                       "floatx80_div",
                       "floatx80_eq",
                       "floatx80_eq_signaling",
                       "floatx80_is_nan",
                       "floatx80_is_signaling_nan",
                       "floatx80_le",
                       "floatx80_le_quiet",
                       "floatx80_lt",
                       "floatx80_lt_quiet",
                       "floatx80_mul",
                       "floatx80_rem",
                       "floatx80_round_to_int",
                       "floatx80_sqrt",
                       "floatx80_sub",
                       "floatx80_to_float128",
                       "floatx80_to_float32",
                       "floatx80_to_float64",
                       "floatx80_to_int32",
                       "floatx80_to_int32_round_to_zero",
                       "floatx80_to_int64",
                       "floatx80_to_int64_round_to_zero",
                       "init_softfloat_state",
                       "int32_to_float128",
                       "int32_to_float32",
                       "int32_to_float64",
                       "int32_to_floatx80",
                       "int64_to_float128",
                       "int64_to_float32",
                       "int64_to_float64",
                       "int64_to_floatx80",
                       "log2_co",
                       "mulAddFloat32Sigs",
                       "mulAddFloat32xSigs",
                       "mulAddFloat64Sigs",
                       "mulSubFloat32Sigs",
                       "mulSubFloat32xSigs",
                       "mulSubFloat64Sigs",
                       "normalizeFloat128Subnormal",
                       "normalizeFloat32Subnormal",
                       "normalizeFloat64Subnormal",
                       "normalizeFloatx80Subnormal",
                       "normalizeRoundAndNegAndPackFloat32",
                       "normalizeRoundAndNegAndPackFloat32_infp",
                       "normalizeRoundAndNegAndPackFloat64",
                       "normalizeRoundAndNegAndPackFloat64_infp",
                       "normalizeRoundAndPackFloat128",
                       "normalizeRoundAndPackFloatx80",
                       "propagateFloat128NaN",
                       "propagateFloat32NaN",
                       "propagateFloat64NaN",
                       "propagateFloatx80NaN",
                       "propagateTriFloat32NaN",
                       "propagateTriFloat64NaN",
                       "roundAndNegAndPackFloat32",
                       "roundAndNegAndPackFloat32x",
                       "roundAndNegAndPackFloat64",
                       "roundAndPackFloat128",
                       "roundAndPackFloatx80",
                       "roundAndPackInt32",
                       "roundAndPackInt64",
                       "sqrtEvenAdjustments.25428",
                       "sqrtOddAdjustments.25427",
                       "subFloat128Sigs",
                       "subFloat32Sigs",
                       "subFloat32xSigs",
                       "subFloat64Sigs",
                       "subFloatx80Sigs",
                       "uint64_to_floatx80"]
    helper_funcs = ["turbo_chain",
                    "turbo_chain_x86",
                    "turbo_chain_x86_not_found",
                    "turbo_pistc_lookup_and_jump",
                    "turbo_pistc_lookup_and_jump_hit",
                    "turbo_pistc_lookup_and_jump_miss",
                    "turbo_pistc_lookup_and_jump_not_turbo",
                    "turbo_stc_miss_ldd",
                    "turbo_stc_miss_std",
                    "turbo_raise_exception",
                    "turbo_stc_miss_load_int16_be",
                    "turbo_stc_miss_load_int16_le",
                    "turbo_stc_miss_load_int32_be",
                    "turbo_stc_miss_load_int32_le",
                    "turbo_stc_miss_load_int8",
                    "turbo_stc_miss_load_uint128",
                    "turbo_stc_miss_load_uint16_be",
                    "turbo_stc_miss_load_uint16_le",
                    "turbo_stc_miss_load_uint32_be",
                    "turbo_stc_miss_load_uint32_le",
                    "turbo_stc_miss_load_uint64_be",
                    "turbo_stc_miss_load_uint64_le",
                    "turbo_stc_miss_load_uint8",
                    "turbo_stc_miss_store_uint128",
                    "turbo_stc_miss_store_uint16_be",
                    "turbo_stc_miss_store_uint16_le",
                    "turbo_stc_miss_store_uint32_be",
                    "turbo_stc_miss_store_uint32_le",
                    "turbo_stc_miss_store_uint64_be",
                    "turbo_stc_miss_store_uint64_le",
                    "turbo_stc_miss_store_uint8",
                    "cmp_set_flags_common",
                    "turbo_lookup_ipc",
                    "turbo_raise_exception_c",
                    "turbo_sdiv64",
                    "turbo_smod32",
                    "turbo_smod64",
                    "turbo_stc_miss_r",
                    "turbo_stc_miss_w",
                    "turbo_stc_miss_w_128",
                    "turbo_try_chain",
                    "turbo_udiv64",
                    "turbo_umod32",
                    "turbo_umod64",
                    "turbo_complete_memop",
                    "turbo_sync_pc",
                    "turbo_recover_lazy_pc",
                    "turbo_lookup_miss_case",
                    "get_turbo_machine_data",
                    "turbo_dealloc_local_miss_case",
                    "turbo_register_precondition_hap",
                    "turbo_set_condition",
                    "turbo_jmpl_aligned_helper"
                    ]

    prefix = None
    if filename.endswith("-turbo"):
        if filename.startswith("sparc-u"):
            prefix = "v9"
        elif filename.startswith("ppc"):
            prefix = "ppc"
        elif filename.startswith("x86"):
            prefix = "p2"
        else:
            prefix = "unknown"
        filename = strip_end(filename, "-turbo")

    if not prefix:
        return (filename, None, True)

    for f in interpreter_funcs:
        if func.startswith(prefix + f):
            return (filename, "interpreter", True)
        elif func.startswith(prefix + "_turbo" + f):
            return (filename, "JIT compiler", True)
    if func in jit_compiler_funcs:
        return (filename, "JIT compiler", True)
    if func.startswith("handle_"):
        return (filename, "JIT compiler", True)
    if func in softfloat_funcs:
        return (filename, "FP emulation", True)
    if func in helper_funcs:
        return (filename, "JIT helpers", True)
    if func.startswith("turbo_" + prefix + "_"):
        return (filename, "JIT helpers", True)

    return (filename, None, False)
