/*
 intel.c

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include "flash-memory.h"

static bool
unit_is_write_protected(flash_memory_t *flash, unit_data_t *unit)
{
        return unit->dyb == 0 || unit->ppb == 0 || flash->wp;
}

static void
intel_chip_erase(flash_memory_t *flash, unsigned chip_index)
{
        int64 total_size = get_total_chip_size(flash);

        if (total_size < 0) {
                SIM_LOG_ERROR(to_obj(flash), FS_Log_Erase, "Intel chip erase: "
                              "no size has been set on the chip");
                return;
        }

        SIM_LOG_INFO(3, to_obj(flash), FS_Log_Erase,
                     "Intel chip erase: erasing all (size: 0x%llx)",
                     total_size);

        if (opt_trigger_allowed(flash)) {
                /* optimizing */
                if (!opt_op_done(flash)) {
                        memory_set(flash,
                                   0,
                                   total_size << flash->interleave_bits,
                                   0xFF);
                        mark_opt_op_done(flash);
                }
        } else {
                /* not optimizing, doing it the slow way */
                memory_set_straddle(
                        flash,
                                                        /* start offset */
                        chip_index * flash->chip_width_in_bytes,
                        total_size,                     /* total size */
                        0xFF,                           /* value */
                        flash->chip_width_in_bytes,     /* size of each
                                                           write */
                        flash_interleave(flash));       /* straddle,
                                                           in size unit */
        }
}

static void
intel_block_erase(flash_memory_t *flash, unsigned chip_index,
                  uint64 offset_in_flash)
{
        uint64 offset_in_chip = get_offset_in_chip(flash, offset_in_flash);
        int unit_index = get_unit_in_chip(flash, offset_in_chip, false);

        if (unit_index == -1) {
                SIM_LOG_SPEC_VIOLATION(
                        1, to_obj(flash), FS_Log_Erase,
                        "offset in chip 0x%llx (address 0x%llx) is not valid",
                                     offset_in_chip, offset_in_flash);
                return;
        }

        /* Align the address to the start of the sector */
        offset_in_flash &=
                ~(((uint64)1 << (flash->unit_bits[unit_index]
                                 + flash->interleave_bits))
                  - 1);
        offset_in_chip &= ~(uint64)(flash_unit_size(flash, unit_index) - 1);

        SIM_LOG_INFO(3, to_obj(flash), FS_Log_Erase,
                     "erasing block %d in chip %d (0x%llx, size 0x%x)",
                     unit_index, chip_index,
                     offset_in_chip, flash_unit_size(flash, unit_index));

        if (opt_trigger_allowed(flash)) {
                /* optimized method */
                if (!opt_op_done(flash)) {
                        memory_set(flash, offset_in_flash,
                                   1 << (flash->unit_bits[unit_index]
                                         + flash->interleave_bits),
                                   0xFF);
                        mark_opt_op_done(flash);
                }
        }
        else {
                /* no optimizing, do it the slow way */
                memory_set_straddle(
                        flash,
                        /* start offset */
                        (offset_in_flash
                         + chip_index * flash->chip_width_in_bytes),
                        flash_unit_size(flash, unit_index), /* total size */
                        0xFF,                         /* value */
                        flash->chip_width_in_bytes,   /* size of each write */
                        flash_interleave(flash));     /* straddle, in size
                                                         unit */
        }
}

static void
intel_word_program(flash_memory_t *flash, unsigned chip_index,
                   uint64 offset_in_flash, uint64 chip_value)
{
        uint64 offset_in_chip = get_offset_in_chip(flash, offset_in_flash);
        int unit_index = get_unit_in_chip(flash, offset_in_chip, false);
        unit_data_t *unit;
        chip_t *chip;

        if (unit_index == -1) {
                SIM_LOG_ERROR(to_obj(flash), 0,
                          "Intel program: offset in chip 0x%llx is out of range",
                          offset_in_chip);
                return;
        }

        chip = &flash->chip[chip_index];
        unit = &chip->unit_data[unit_index];

        if (unit_is_write_protected(flash, unit)) {
                SIM_LOG_INFO(3, to_obj(flash), 0,
                                       "Intel program: chip %d sector %d is "
                                       "write protected.",
                                       chip_index, unit_index);
                return;
        }

        if (opt_write_allowed(flash)) {
                if (!opt_op_done(flash)) {
                        /* write all the value at once */
                        memory_write(flash, offset_in_flash,
                                     flash->bus_width_in_bytes,
                                     get_bus_value(flash,
                                                   flash->opt_op.full_value));
                        mark_opt_op_done(flash);
                }
        }
        else {
                /* write only the bytes we should take care of */
                memory_write(flash,
                             offset_in_flash
                             + chip_index * flash->chip_width_in_bytes,
                             flash->chip_width_in_bytes,
                             endian_converted(flash, chip_value));
        }
}

static void
intel_lock_command_simple(flash_memory_t *flash, unsigned chip_index,
                          uint64 offset_in_flash,
                          intel_cmd_lock_operation_t lock_cmd)
{
        switch (lock_cmd) {
        case Intel_Cmd_Block_Lock: {
                /* find relevant block */
                uint64 offset_in_chip =
                        get_offset_in_chip(flash, offset_in_flash);
                int unit_index = get_unit_in_chip(flash, offset_in_chip,
                                                  false);
                if (unit_index == -1) {
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), FS_Log_Lock,
                                "received a lock command for a non-existing "
                                "block (offset in chip 0x%llx)",
                                offset_in_chip);
                        return;
                }
                unit_data_t *unit =
                        &flash->chip[chip_index].unit_data[unit_index];
                unit->lock_status = 0x1; break;
        }
        case Intel_Cmd_Block_Unlock: {
                int i;

                /* unlock all units */
                for (i=0; i<flash->num_units; i++)
                        flash->chip[chip_index].unit_data[i].lock_status = 0x0;
                break;
        }
        case Intel_Cmd_Block_Lock_Down:
        case Intel_Cmd_Hardware_WP_Up:
        case Intel_Cmd_Hardware_WP_Down:
                SIM_LOG_ERROR(to_obj(flash), FS_Log_Lock,
                              "wrong command send to intel simple lock "
                              "mechanism");
        }
}

static void
intel_lock_command_advanced(flash_memory_t *flash, unsigned chip_index,
                            uint64 offset_in_flash,
                            intel_cmd_lock_operation_t lock_cmd)
{
        /* find relevant unit */
        uint64 offset_in_chip = get_offset_in_chip(flash, offset_in_flash);
        int unit_index = get_unit_in_chip(flash, offset_in_chip, false);
        if (unit_index == -1) {
                SIM_LOG_SPEC_VIOLATION(
                        1, to_obj(flash), FS_Log_Lock,
                        "received a lock command for a non-existing block "
                        "(offset in chip 0x%llx)", offset_in_chip);
                return;
        }

        unit_data_t *unit = &flash->chip[chip_index].unit_data[unit_index];

        switch (unit->lock_status | (flash->wp << 2)) {
        case 0x00:              /* 000 unlocked - wp */
        case 0x04:              /* 100 unlocked + wp */
                switch (lock_cmd) {
                case Intel_Cmd_Block_Lock:
                        unit->lock_status = 0x01; break; /* 001/101 */
                case Intel_Cmd_Block_Lock_Down:
                        unit->lock_status = 0x03; break; /* 011/111 */
                default:
                        ;
                }
                break;

        case 0x01:              /* 001 locked - wp */
        case 0x05:              /* 101 locked + wp */
                switch (lock_cmd) {
                case Intel_Cmd_Block_Unlock:
                        unit->lock_status = 0x00; break; /* 000/100 */
                case Intel_Cmd_Block_Lock_Down:
                        unit->lock_status = 0x03; break; /* 011/111 */
                default:
                        ;
                }
                break;

        case 0x06:              /* 110 unlocked */
                switch (lock_cmd) {
                case Intel_Cmd_Block_Lock:
                        unit->lock_status = 0x03; break; /* 111 */
                case Intel_Cmd_Hardware_WP_Down:
                        unit->hardware_lock = 1;
                        unit->lock_status = 0x03; break; /* 011 + hwlock */
                        break;
                default:
                        ;
                }
                break;

        case 0x03:              /* 011 locked-down - wp */
                if (unit->hardware_lock) {
                        switch (lock_cmd) {
                        case Intel_Cmd_Block_Lock_Down:
                                unit->hardware_lock = 0; /* 011 - hwlock */
                                break;
                        case Intel_Cmd_Hardware_WP_Up:
                                unit->hardware_lock = 0;
                                unit->lock_status = 0x2; /* 110 - hwlock */
                                break;
                        default:
                                ;
                        }
                }
                break;

        case 0x07:              /* 111 locked-down + wp */
                switch (lock_cmd) {
                case Intel_Cmd_Block_Unlock:
                        unit->lock_status = 0x2; break; /* 110 */
                default:
                          ;
                }
                break;

        case 0x02:              /* 010 non-accessible state */
                SIM_LOG_ERROR(to_obj(flash), FS_Log_Lock,
                              "Intel lock status is 010b, "
                              "which should be impossible");
                break;
        }
}

int
intel_read_operation(flash_memory_t *flash, unsigned chip_index,
                     uint64 offset_in_flash, uint64 *chip_value)
{
        chip_t *chip = &flash->chip[chip_index];
        *chip_value = 0;

        switch (chip->mode) {

        case FS_read_array:
                /* handle the case where not all chips are in read-array
                   mode */
                if (!flash->opt_op.same_state) {
                        *chip_value |= memory_read(
                                flash,
                                offset_in_flash
                                + chip_index * flash->chip_width_in_bytes,
                                flash->chip_width_in_bytes);
                        return 1;
                } else {
                        return 0;
                }

        case FS_cfi_query:
                return cfi_query_read(flash, chip_index, offset_in_flash,
                                      chip_value);

        case FS_intel_read_identifier_codes: {

                uint64 cmd_addr =
                        get_cmd_offset(
                                flash,
                                get_offset_in_chip(flash, offset_in_flash))
                        & 0xFF;

                if (cmd_addr == 0) {
                        /* Manufacturer code, block independent */
                        *chip_value = flash->manufacturer_id;
                }
                else if (cmd_addr == 1) {
                        /* Device code - always one byte on intel */
                        *chip_value = flash->device_id[0];
                }
                else if (cmd_addr == 2) {
                        *chip_value = generic_read_lock_status(
                                flash, chip_index, offset_in_flash);
                }
                else {
                        SIM_LOG_UNIMPLEMENTED(1, to_obj(flash), 0,
                                              "Intel identifier codes at "
                                              "0x%llx are unimplemented",
                                              cmd_addr);
                        *chip_value = 0;
                }
        }
                return 1;
        case FS_intel_read_status:
                *chip_value = 0x80;
                return 1;

        case FS_intel_block_erase:
                if (flash->strict_cmd_set) {
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "read operation in Intel block erase mode");
                        update_state(flash, chip_index, FS_unknown);
                } else {
                        SIM_LOG_SPEC_VIOLATION(
                                2, to_obj(flash), 0,
                                "read operation in Intel block erase mode - "
                                "ignored");
                }
                return 1;

        case FS_intel_word_program:
                if (flash->strict_cmd_set) {
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "read operation in Intel word program mode");
                        update_state(flash, chip_index, FS_unknown);
                } else {
                        SIM_LOG_SPEC_VIOLATION(
                                2, to_obj(flash), 0,
                                "read operation in Intel word program mode - "
                                "ignored");
                }
                return 1;

        case FS_write_buffer_size:
        case FS_write_buffer_gather:
        case FS_write_buffer_confirm:
                *chip_value = 0x80;
                return 1;

        case FS_intel_lock_setup:
        case FS_intel_lock_command_error:
        case FS_intel_lock_command_done:
                *chip_value = 0x80;
                return 1;

        case FS_unknown:
        case FS_unimplemented:
        case FS_write_buffer_in_progress:
                return 0;

        case FS_chip_erase_in_progress:
                update_state(flash, chip_index, FS_intel_read_status);
                *chip_value = 0x00;
                return 1;

        case FS_amd_unlock1:
        case FS_amd_unlock2:
        case FS_amd_autoselect:
        case FS_amd_erase3:
        case FS_amd_erase4:
        case FS_amd_erase5:
        case FS_amd_erase_in_progress:
        case FS_amd_program:
        case FS_amd_program_pending:
        case FS_amd_unlock_bypass:
        case FS_amd_unlock_bypass_program:
        case FS_amd_unlock_bypass_reset:
        case FS_amd_lock_register_command_set:
        case FS_amd_lock_register_bits:
        case FS_amd_lock_register_exit:
        case FS_amd_non_volatile_command_set:
        case FS_amd_non_volatile_program:
        case FS_amd_non_volatile_erase:
        case FS_amd_non_volatile_exit:
        case FS_amd_ppb_lock_command_set:
        case FS_amd_ppb_lock_program:
        case FS_amd_ppb_lock_exit:
        case FS_amd_volatile_command_set:
        case FS_amd_volatile_write:
        case FS_amd_volatile_exit:
        case FS_amd_unlock_bypass_erase:
        case FS_amd_unlock_bypass_command1:
        case FS_amd_unlock_bypass_command2:
        case FS_bypass_write_buffer_size:
        case FS_bypass_write_buffer_gather:
        case FS_bypass_write_buffer_confirm:
        case FS_bypass_write_buffer_in_progress:
        case FS_bypass_chip_erase_in_progress:
        case FS_bypass_erase_in_progress:
                /* An intel chip can't be in one of the AMD states */
                ASSERT(0);
        case FS_max:
                ASSERT(0);
        }
        return 0;
}

int
intel_write_operation(flash_memory_t *flash, unsigned chip_index,
                      uint64 offset_in_flash, uint64 chip_value)
{
        chip_t *chip = &flash->chip[chip_index];
        uint8 cmd_data = chip_value & 0xFF; /* upper bytes are ignored in
                                               command mode */

        switch (chip->mode) {

        case FS_read_array:
        case FS_intel_read_status:
        case FS_intel_read_identifier_codes:
        case FS_cfi_query:
        case FS_intel_lock_command_error:
        case FS_intel_lock_command_done:
                switch (cmd_data) {

                        /* return to read-array mode */
                case 0xFF:      /* read-array mode */
                case 0xF0:
                case 0xD0:      /* block erase/program resume */
                case 0xB0:      /* block erase/program suspend */
                case 0x50:      /* clear status register */
                case 0x2F:      /* lock down confirm */
                case 0x01:      /* lock confirm */
                case 0x00:      /* undocumented see bug 5374 */
                        update_state(flash, chip_index, FS_read_array);
                        break;

                case 0xE8:      /* write buffer setup */
                        if (flash->intel.write_buffer) {
                                generic_write_buffer_setup(
                                        flash, chip_index, offset_in_flash,
                                        cmd_data);
                                update_state(flash, chip_index,
                                             FS_write_buffer_size);
                        }
                        break;
                case 0xC0:      /* prot. prog. setup */
                        if (flash->intel.protection_program) {
                                SIM_LOG_UNIMPLEMENTED(1, to_obj(flash), 0,
                                                      "Intel protection "
                                                      "program setup is "
                                                      "unimplemented");
                                update_state(flash, chip_index,
                                             FS_unimplemented);
                        } else if (flash->intel.program_verify) {
                                update_state(flash, chip_index,
                                             FS_read_array);
                        }
                        break;
                case 0xB8:      /* configuration */
                        if (flash->intel.configuration) {
                                SIM_LOG_UNIMPLEMENTED(1, to_obj(flash), 0,
                                                      "Intel block "
                                                      "configuration command "
                                                      "is unimplemented");
                                update_state(flash, chip_index,
                                             FS_unimplemented);
                        }
                        break;
                case 0x98:      /* CFI query */
                        update_state(flash, chip_index, FS_cfi_query);
                        break;
                case 0x90:      /* read config */
                        update_state(flash, chip_index,
                                     FS_intel_read_identifier_codes);
                        break;
                case 0x70:      /* read status */
                        update_state(flash, chip_index,
                                     FS_intel_read_status);
                        break;
                case 0x60:      /* lock setup */
                        if (flash->intel.lock)
                                update_state(flash, chip_index,
                                             FS_intel_lock_setup);
                        break;
                case 0x40:      /* program setup */
                case 0x10:
                        update_state(flash, chip_index,
                                     FS_intel_word_program);
                        break;
                case 0x20:      /* erase setup */
                        update_state(flash, chip_index,
                                     FS_intel_block_erase);
                        break;
                }
                return 1;

        case FS_intel_lock_setup:
                switch (cmd_data) {
                        /* fail to cmd-lock error mode */
                case 0xFF:
                case 0xF0:      /* read-array mode */
                case 0xE8:      /* write buffer */
                case 0xB8:      /* configuration */
                case 0xB0:      /* block erase/program suspend */
                case 0x98:      /* CFI query */
                case 0x90:      /* read config */
                case 0x70:      /* read status */
                case 0x60:      /* lock setup */
                case 0x50:      /* clear status register */
                case 0x40:      /* program setup */
                case 0x10:
                case 0x20:      /* erase setup */
                        update_state(flash, chip_index,
                                     FS_intel_lock_command_error);
                        break;

                case 0xD0:      /* block erase/program resume */
                        if (flash->intel.lock == 2)
                                intel_lock_command_advanced(
                                        flash, chip_index, offset_in_flash,
                                        Intel_Cmd_Block_Unlock);
                        else
                                intel_lock_command_simple(
                                        flash, chip_index, offset_in_flash,
                                        Intel_Cmd_Block_Unlock);
                        update_state(flash, chip_index,
                                     FS_intel_lock_command_done);
                        break;

                case 0x2F:      /* lock down confirm */
                        if (flash->intel.lock == 2) {
                                intel_lock_command_advanced(
                                        flash, chip_index, offset_in_flash,
                                        Intel_Cmd_Block_Lock_Down);
                                update_state(
                                        flash, chip_index,
                                        FS_intel_lock_command_done);
                        } else {
                                update_state(
                                        flash, chip_index,
                                        FS_intel_lock_command_error);
                        }
                        break;

                case 0x01:      /* lock confirm */
                        if (flash->intel.lock == 2)
                                intel_lock_command_advanced(
                                        flash, chip_index, offset_in_flash,
                                        Intel_Cmd_Block_Lock);
                        else
                                intel_lock_command_simple(
                                        flash, chip_index, offset_in_flash,
                                        Intel_Cmd_Block_Lock);
                        update_state(flash, chip_index,
                                     FS_intel_lock_command_done);
                        break;
                }
                return 1;

        case FS_intel_block_erase:
                if (cmd_data == 0xd0) {
                        intel_block_erase(flash, chip_index, offset_in_flash);
                        update_state(flash, chip_index,
                                     FS_intel_read_status);
                } else if ((cmd_data == 0x20) && flash->intel.chip_erase) {
                        intel_chip_erase(flash, chip_index);
                        update_state(flash, chip_index,
                                     FS_chip_erase_in_progress);
                } else {
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "unexpected value 0x%x written in Intel block "
                                "erase mode", cmd_data);
                        update_state(flash, chip_index, FS_unknown);
                }
                return 1;

        case FS_intel_word_program:
                intel_word_program(flash, chip_index, offset_in_flash,
                                   chip_value);
                update_state(flash, chip_index, FS_intel_read_status);
                return 1;

        case FS_write_buffer_size: {
                int success = generic_write_buffer_size(
                        flash, chip_index, offset_in_flash, chip_value);
                update_state(flash, chip_index, success
                             ? FS_write_buffer_gather : FS_read_array);
                return 1;
        }
        case FS_write_buffer_gather: {
                int result = generic_write_buffer_gather(
                        flash, chip_index, offset_in_flash, chip_value);
                if (result == 2) {
                        update_state(flash, chip_index,
                                     FS_write_buffer_confirm);
                        return 1;
                }
                return result;
        }

        case FS_write_buffer_confirm:
                if (cmd_data != 0xD0)
                        return 1;
                generic_write_buffer_confirm(flash, chip_index,
                                             offset_in_flash, chip_value);
                update_state(flash, chip_index, FS_intel_read_status);
                return 1;

        case FS_unknown:
        case FS_unimplemented:
        case FS_write_buffer_in_progress:
        case FS_chip_erase_in_progress:
                return 1;

        case FS_amd_unlock1:
        case FS_amd_unlock2:
        case FS_amd_autoselect:
        case FS_amd_erase3:
        case FS_amd_erase4:
        case FS_amd_erase5:
        case FS_amd_erase_in_progress:
        case FS_amd_program:
        case FS_amd_program_pending:
        case FS_amd_unlock_bypass:
        case FS_amd_unlock_bypass_program:
        case FS_amd_unlock_bypass_reset:
        case FS_amd_lock_register_command_set:
        case FS_amd_lock_register_bits:
        case FS_amd_lock_register_exit:
        case FS_amd_non_volatile_command_set:
        case FS_amd_non_volatile_program:
        case FS_amd_non_volatile_erase:
        case FS_amd_non_volatile_exit:
        case FS_amd_ppb_lock_command_set:
        case FS_amd_ppb_lock_program:
        case FS_amd_ppb_lock_exit:
        case FS_amd_volatile_command_set:
        case FS_amd_volatile_write:
        case FS_amd_volatile_exit:
        case FS_amd_unlock_bypass_erase:
        case FS_amd_unlock_bypass_command1:
        case FS_amd_unlock_bypass_command2:
        case FS_bypass_write_buffer_size:
        case FS_bypass_write_buffer_gather:
        case FS_bypass_write_buffer_confirm:
        case FS_bypass_write_buffer_in_progress:
        case FS_bypass_chip_erase_in_progress:
        case FS_bypass_erase_in_progress:
                /* An intel chip can't be in one of the AMD states */
                ASSERT(0);
        case FS_max:
                ASSERT(0);
        }

        return 1;
}

void intel_finalize(flash_memory_t *flash)
{
}
