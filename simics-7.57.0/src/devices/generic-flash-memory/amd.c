/*
 amd.c

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
unit_is_write_protected(flash_memory_t *flash, chip_t *chip, unit_data_t *unit)
{
        return unit->dyb == 0 || unit->ppb == 0 || flash->wp;
}

static void
amd_sector_erase(flash_memory_t *flash, unsigned chip_index,
                 uint64 offset_in_flash)
{
        uint64 offset_in_chip = get_offset_in_chip(flash, offset_in_flash);
        int unit_index = get_unit_in_chip(flash, offset_in_chip, false);
        unit_data_t *unit;
        chip_t *chip;

        if (unit_index == -1) {
                SIM_LOG_ERROR(to_obj(flash), FS_Log_Erase, "AMD sector erase: "
                              "offset in chip 0x%llx is not valid",
                              offset_in_chip);
                return;
        }

        chip = &flash->chip[chip_index];
        unit = &chip->unit_data[unit_index];

        /* Align the address to the start of the sector */
        offset_in_flash &=
                ~(((uint64)1 << (flash->unit_bits[unit_index]
                                 + flash->interleave_bits))
                  - 1);
        offset_in_chip &= ~(uint64)(flash_unit_size(flash, unit_index) - 1);

        SIM_LOG_INFO(3, to_obj(flash), FS_Log_Erase,
                     "AMD sector erase: erasing sector %d "
                     "(offset in chip: 0x%llx, ending at: 0x%llx, "
                     "size: 0x%x)",
                     unit_index, offset_in_chip,
                     offset_in_chip + flash_unit_size(flash, unit_index),
                     flash_unit_size(flash, unit_index));

        if (opt_trigger_allowed(flash)) {
                /* optimizing */
                if (!opt_op_done(flash)) {
                        memory_set(flash,
                                   offset_in_flash,
                                   1 << (flash->unit_bits[unit_index]
                                         + flash->interleave_bits),
                                   0xFF);
                        mark_opt_op_done(flash);
                }
        }
        else {
                /* not optimizing, doing it the slow way */
                memory_set_straddle(
                        flash,
                        (offset_in_flash + chip_index
                         * flash->chip_width_in_bytes), /* start offset */
                        flash_unit_size(flash, unit_index), /* total size */
                        0xFF,                           /* value */
                        flash->chip_width_in_bytes,     /* size of each
                                                           write */
                        flash_interleave(flash));       /* straddle,
                                                           in size unit */
        }

        /* During the embedded erase algorithm, data# polling produces
           a 0 on dq7. If dq3 is 1, the internally controlled erase
           cycle has begun. */
        unit->status = 0x08;
}

static void
amd_chip_erase(flash_memory_t *flash, unsigned chip_index)
{
        int64 total_size = get_total_chip_size(flash);

        if (total_size < 0) {
                SIM_LOG_ERROR(to_obj(flash), FS_Log_Erase, "AMD chip erase: "
                              "no size has been set on the chip");
                return;
        }

        SIM_LOG_INFO(3, to_obj(flash), FS_Log_Erase,
                     "AMD chip erase: erasing all (size: 0x%llx)", total_size);

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

        for (int i = 0; i < flash->num_units; i++) {
                /* During the embedded erase algorithm, data# polling produces
                   a 0 on dq7. If dq3 is 1, the internally controlled erase
                   cycle has begun. */
                flash->chip[chip_index].unit_data[i].status = 0x08;
        }
}

static void
amd_ppb_program(flash_memory_t *flash, unsigned chip_index,
                uint64 offset_in_flash)
{
        uint64 offset_in_chip = get_offset_in_chip(flash, offset_in_flash);
        int unit_index = get_unit_in_chip(flash, offset_in_chip, false);

        if (unit_index == -1) {
                SIM_LOG_ERROR(to_obj(flash), FS_Log_Erase, "AMD ppb program: "
                              "offset in chip 0x%llx is not valid",
                              offset_in_chip);
                return;
        }
        if (flash->chip[chip_index].amd.ppb_lock_bit == 0) {
                SIM_LOG_INFO(1, to_obj(flash), 0,
                             "non-volatile program of sector %d could not be "
                             "performed since the PPB lock bit is 0.",
                             unit_index);
                return;
        }
        SIM_LOG_INFO(2, to_obj(flash), 0, "non-volatile program of sector %d",
                     unit_index);
        flash->chip[chip_index].unit_data[unit_index].ppb = 0;
}

static void
amd_ppb_erase(flash_memory_t *flash, unsigned chip_index)
{
        if (flash->chip[chip_index].amd.ppb_lock_bit == 0) {
                SIM_LOG_INFO(1, to_obj(flash), 0,
                             "non-volatile PPB erase on chip %d could not be "
                             "performed since the PPB lock bit is 0.",
                             chip_index);
                return;
        }
        for (int i = 0; i < flash->num_units; i++)
                flash->chip[chip_index].unit_data[i].ppb = 1;
        SIM_LOG_INFO(2, to_obj(flash), 0, "non-volatile PPB erase chip %d",
                     chip_index);
}

static void
amd_dyb_write(flash_memory_t *flash, unsigned chip_index,
              uint64 offset_in_flash, int value)
{
        uint64 offset_in_chip = get_offset_in_chip(flash, offset_in_flash);
        int unit_index = get_unit_in_chip(flash, offset_in_chip, false);

        if (unit_index == -1) {
                SIM_LOG_ERROR(to_obj(flash), FS_Log_Erase, "AMD dyb write: "
                              "offset in chip 0x%llx is not valid",
                              offset_in_chip);
                return;
        }
        SIM_LOG_INFO(2, to_obj(flash), 0, "Setting volatile program "
                     "protection bit (DYB) of sector %d to %d",
                     unit_index, value);
        flash->chip[chip_index].unit_data[unit_index].dyb = value;
}

static void
amd_program(flash_memory_t *flash, unsigned chip_index,
            uint64 offset_in_flash, uint64 chip_value)
{
        uint64 offset_in_chip = get_offset_in_chip(flash, offset_in_flash);
        int unit_index = get_unit_in_chip(flash, offset_in_chip, false);
        unit_data_t *unit;
        chip_t *chip;

        if (unit_index == -1) {
                SIM_LOG_ERROR(to_obj(flash), 0,
                          "AMD program: offset in chip 0x%llx is out of range",
                          offset_in_chip);
                return;
        }

        chip = &flash->chip[chip_index];
        unit = &chip->unit_data[unit_index];

        if (unit_is_write_protected(flash, chip, unit)) {
                SIM_LOG_SPEC_VIOLATION(1, to_obj(flash), 0,
                                       "AMD program: chip %d sector %d is "
                                       "write protected.",
                                       chip_index, unit_index);
                return;
        }

        if (opt_write_allowed(flash)) {
                if (!opt_op_done(flash)) {
                        /* Write all the value at once. Note that full_value is
                           kept in the original cpu endianness, so the cpu will
                           see what it programmed */
                        memory_write(flash, offset_in_flash,
                                     flash->bus_width_in_bytes,
                                     get_bus_value(flash,
                                                   flash->opt_op.full_value));
                        mark_opt_op_done(flash);
                }
        }
        else {
                /* Write only the bytes we should take care of. Note that we
                   byte-swap back the value to write it in the original cpu
                   endianness */
                memory_write(flash,
                             offset_in_flash
                             + chip_index * flash->chip_width_in_bytes,
                             flash->chip_width_in_bytes,
                             endian_converted(flash, chip_value));
        }

        unit->status = ~chip_value & 0x80;
}

int
amd_read_operation(flash_memory_t *flash, unsigned chip_index,
                   uint64 offset_in_flash, uint64 *chip_value)
{
        uint64 offset_in_chip = get_offset_in_chip(flash, offset_in_flash);
        int unit_index = get_unit_in_chip(flash, offset_in_chip, false);
        chip_t *chip = &flash->chip[chip_index];
        unit_data_t *unit = &chip->unit_data[unit_index];

        *chip_value = 0;

        switch (chip->mode) {

        case FS_read_array:
        case FS_amd_unlock_bypass:
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

        case FS_amd_unlock1:
        case FS_amd_unlock2:
        case FS_amd_unlock_bypass_command1:
        case FS_amd_unlock_bypass_command2:
                if (flash->strict_cmd_set) {
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "read operation during AMD unlock sequence");
                        update_state(flash, chip_index, FS_unknown);
                } else {
                        SIM_LOG_SPEC_VIOLATION(
                                4, to_obj(flash), 0,
                                "read operation during AMD unlock sequence - "
                                "ignored");
                }
                return 1;

        case FS_amd_unlock_bypass_reset:
                if (flash->strict_cmd_set) {
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "read operation during AMD unlock bypass "
                                "reset sequence");
                        update_state(flash, chip_index, FS_unknown);
                } else {
                        SIM_LOG_SPEC_VIOLATION(
                                4, to_obj(flash), 0,
                                "read operation during AMD unlock bypass "
                                "reset sequence - ignored");
                }
                return 1;

        case FS_amd_autoselect: {
                /* only the lowest 8 address bits are used to select the
                   data, hence the & 0xFF */
                uint32 as_addr = get_cmd_offset(flash, offset_in_chip) & 0xFF;

                switch (as_addr) {
                case 0x00: /* manufacturer id */
                        *chip_value = flash->manufacturer_id;
                        return 1;
                case 0x02: /* sector protect verification */
                        *chip_value = generic_read_lock_status(
                                flash, chip_index, offset_in_flash);
                        return 1;
                case 0x01:                   /* device id, cycle 1 */
                case 0x0E:                   /* device id, cycle 2 */
                case 0x0F:                   /* device id, cycle 3 */
                {
                        unsigned index = (as_addr == 0x1)
                                ? 0 : as_addr - 0xD; /* 0, 1, or 2 */
                        if (flash->device_id_len > index)
                                *chip_value = flash->device_id[index];
                        else
                                SIM_LOG_SPEC_VIOLATION(
                                        2, to_obj(flash), 0,
                                        "Flash device ID should be at least "
                                        "%d bytes long to read ID byte %d at "
                                        "offset 0x%x in autoselect mode",
                                        index + 1, index, as_addr);
                        return 1;
                }
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                2, to_obj(flash), 0,
                                "reading unknown offset 0x%x in "
                                "AMD autoselect mode",
                                as_addr);
                        return 1;
                }
                break;
        }
        case FS_amd_erase3:
        case FS_amd_erase4:
        case FS_amd_erase5:
                if (flash->strict_cmd_set) {
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "read operation during AMD erase sequence");
                        update_state(flash, chip_index, FS_unknown);
                } else {
                        SIM_LOG_SPEC_VIOLATION(
                                4, to_obj(flash), 0,
                                "read operation during AMD erase sequence - "
                                "ignored");
                }
                return 1;

        case FS_amd_erase_in_progress:
        case FS_bypass_chip_erase_in_progress:
        case FS_bypass_erase_in_progress:
                /* Flip DQ6 and DQ2 */
                SIM_LOG_INFO(3, to_obj(flash), FS_Log_Erase,
                            "flipping DQ6 and DQ2 during erase old=%x, new=%x",
                            unit->status, unit->status ^ 0x44);
                unit->status ^= 0x44;
                *chip_value = unit->status;
                return 1;

        case FS_write_buffer_in_progress:
        case FS_bypass_write_buffer_in_progress:
                /* Flip DQ6 */
                SIM_LOG_INFO(3, to_obj(flash), FS_Log_Write_Buffer,
                             "flipping DQ6 during write buffer old=%x, new=%x",
                             unit->status, unit->status ^ 0x40);
                unit->status ^= 0x40;
                *chip_value = unit->status;
                return 1;

        case FS_amd_program:
        case FS_write_buffer_size:
        case FS_write_buffer_gather:
                *chip_value = unit->status;
                return 1;

        case FS_amd_lock_register_command_set:
                SIM_LOG_INFO(4, to_obj(flash), 0, "reading lock bits 0x%x",
                             chip->amd.lock_register);
                *chip_value = chip->amd.lock_register;
                return 1;

        case FS_amd_non_volatile_command_set:
                *chip_value = unit->ppb;
                SIM_LOG_INFO(2, to_obj(flash), 0, "reading 0x%llx from "
                             "non-volatile PPB bits for sector %d",
                             *chip_value, unit_index);
                return 1;

        case FS_amd_volatile_command_set:
                *chip_value = unit->dyb;
                SIM_LOG_INFO(2, to_obj(flash), 0, "reading 0x%llx from "
                             "volatile DYB bits for sector %d",
                             *chip_value, unit_index);
                return 1;

        case FS_amd_ppb_lock_command_set:
                SIM_LOG_INFO(2, to_obj(flash), 0, "reading PPB lock bit: %d",
                             chip->amd.ppb_lock_bit);
                *chip_value = chip->amd.ppb_lock_bit;
                return 1;

        case FS_unknown:
        case FS_unimplemented:
        case FS_write_buffer_confirm:
        case FS_chip_erase_in_progress:
        case FS_amd_program_pending:
        case FS_amd_unlock_bypass_program:
        case FS_amd_lock_register_bits:
        case FS_amd_lock_register_exit:
        case FS_amd_non_volatile_program:
        case FS_amd_non_volatile_erase:
        case FS_amd_non_volatile_exit:
        case FS_amd_ppb_lock_program:
        case FS_amd_ppb_lock_exit:
        case FS_amd_volatile_write:
        case FS_amd_volatile_exit:
        case FS_bypass_write_buffer_size:
        case FS_bypass_write_buffer_gather:
        case FS_bypass_write_buffer_confirm:
        case FS_amd_unlock_bypass_erase:
                return 0;

        case FS_intel_read_identifier_codes:
        case FS_intel_read_status:
        case FS_intel_block_erase:
        case FS_intel_word_program:
        case FS_intel_lock_setup:
        case FS_intel_lock_command_error:
        case FS_intel_lock_command_done:
                /* Intel states shouldn't occur in AMD flash chips */
                ASSERT(0);
        case FS_max:
                ASSERT(0);
        }

        return 0;
}

static int ptr_eq(void *a, void *b)
{
        return a == b;
}

static void
cancel_busy_event(flash_memory_t *flash, unsigned chip_index)
{
        SIM_event_cancel_time(SIM_object_clock(to_obj(flash)),
                              event_operation_done,
                              to_obj(flash),
                              ptr_eq, (void*)(uintptr_t)chip_index);
}

static void
complete_busy_event(flash_memory_t *flash, unsigned chip_index)
{
        time_delayed_operation_done(to_obj(flash),
                                    (void*)(uintptr_t)chip_index);
}

static void
handle_amd_erase_subcommand(flash_memory_t *flash, unsigned chip_index,
                            uint64 offset_in_flash, int cmd_code,
                            uint64 chip_value,
                            fm_operation_t erase_progress,
                            fm_operation_t chip_erase_progress,
                            fm_operation_t read_array_mode) {
        switch (cmd_code) {
        case 0x30: /* sector erase */
                /* Do the erase directly */
                amd_sector_erase(flash, chip_index, offset_in_flash);

                if (flash->time_model[erase_progress]) {
                        /* ..but report it as finished after a while */
                        post_busy_event(flash, chip_index,
                                        flash->time_model[erase_progress]);
                        update_state(flash, chip_index, erase_progress);
                } else {
                        update_state(flash, chip_index, read_array_mode);
                }
                break;

        case 0x10: /* chip erase */
                /* Do the erase directly */
                amd_chip_erase(flash, chip_index);

                if (flash->time_model[chip_erase_progress]) {
                        /* ..but report it as finished after a while */
                        post_busy_event(flash, chip_index,
                                        flash->time_model[chip_erase_progress]);
                        update_state(flash, chip_index, chip_erase_progress);
                } else {
                        update_state(flash, chip_index, read_array_mode);
                }
                break;

        default:
                SIM_LOG_SPEC_VIOLATION(
                        1, to_obj(flash), 0,
                        "illegal value (0x%llx) written in erase mode",
                        chip_value);
                update_state(flash, chip_index, FS_unknown);
                break;
        }
}

int
amd_write_operation(flash_memory_t *flash, unsigned chip_index,
                    uint64 offset_in_flash, uint64 chip_value)
{
        chip_t *chip = &flash->chip[chip_index];

        /* offset and value for command cycles */
        uint64 offset_in_chip = get_offset_in_chip(flash, offset_in_flash);

        /* Only A10-A0 are counted when decoding the command address, hence the
           & 0x7FF */
        uint64 cmd_addr = get_cmd_offset(flash, offset_in_chip) & 0x7FF;
        unsigned cmd_code = chip_value & 0xff;

        /* function specific macro */
#define IF_ADDR(target_addr, code)                                       \
if (cmd_addr == (target_addr) || flash->amd.ignore_cmd_address) {        \
        code;                                                            \
}                                                                        \
else {                                                                   \
        SIM_LOG_SPEC_VIOLATION(                                          \
                2, to_obj(flash), 0,                                   \
                "AMD command with data 0x%llx but invalid address "      \
                "0x%llx in %s mode. You may try to set the "             \
                "\"amd_ignore_cmd_address\" flag.",                      \
                chip_value, cmd_addr,                                    \
                state_desc[chip->mode]);                                 \
}


        switch (chip->mode) {

        case FS_read_array:
                switch (cmd_code) {
                case 0xFF: /* nothing, but seems to be reset */
                case 0xF0: /* reset */
                        break;
                case 0xAA: /* command setup */
                        IF_ADDR(0x555,
                                update_state(flash, chip_index,
                                             FS_amd_unlock1));
                        break;

                case 0xA0: /* unlock bypass program */
                        SIM_LOG_SPEC_VIOLATION(1, to_obj(flash), 0,
                                               "AMD unlock bypass program "
                                               "while in read-array mode");
                        update_state(flash, chip_index, FS_unknown);
                        break;
                case 0x98:
                        IF_ADDR(0x55,
                                update_state(flash, chip_index,
                                             FS_cfi_query));
                        break;
                case 0x90: /* unlock bypass reset */
                        SIM_LOG_SPEC_VIOLATION(1, to_obj(flash), 0,
                                               "AMD unlock bypass reset while "
                                               "in read-array mode");
                        update_state(flash, chip_index, FS_unknown);
                        break;
                case 0xB0: /* erase suspended */
                        SIM_LOG_SPEC_VIOLATION(1, to_obj(flash), 0,
                                               "AMD erase suspend while "
                                               "in read-array mode");
                        update_state(flash, chip_index, FS_unknown);
                        break;
                case 0x30: /* erase resumed, is now a NOP (bug 21451) */
                        break;
                case 0x00:
                        /* do not warn, it's probably a padded operation */
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "AMD command with unknown "
                                "data 0x%llx in read-array-mode", chip_value);
                        break;
                }
                break;

        case FS_cfi_query:
                switch (cmd_code) {
                case 0xff:
                case 0xf0:
                case 0x00:     /* undocumented see bug 5374 */
                        update_state(flash, chip_index, FS_read_array);
                        break;
                default:
                        break;
                }
                break;

        case FS_amd_unlock1:
                switch (cmd_code) {
                case 0x55:
                        IF_ADDR(0x2AA,
                                update_state(flash, chip_index,
                                             FS_amd_unlock2));
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "AMD first command cycle with unknown "
                                "data 0x%llx", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_unlock2:
                switch (cmd_code) {
                case 0xA0:
                        IF_ADDR(0x555,
                                update_state(flash, chip_index,
                                             FS_amd_program_pending));
                        break;
                case 0x90:
                        IF_ADDR(0x555,
                                update_state(flash, chip_index,
                                             FS_amd_autoselect));
                        break;
                case 0x80:
                        IF_ADDR(0x555,
                                update_state(flash, chip_index,
                                             FS_amd_erase3));
                        break;
                case 0x25:
                        generic_write_buffer_setup(
                                flash, chip_index, offset_in_flash,
                                chip_value);
                        update_state(flash, chip_index,
                                     FS_write_buffer_size);
                        break;
                case 0x20:
                        IF_ADDR(0x555,
                                update_state(flash, chip_index,
                                             FS_amd_unlock_bypass));
                        break;
                case 0x40:
                        /* The S29GLxxxN flash have a lock register. */
                        IF_ADDR(0x555,
                                update_state(flash, chip_index,
                                             FS_amd_lock_register_command_set));
                        break;
                case 0x50:
                        IF_ADDR(0x555,
                                update_state(flash, chip_index,
                                             FS_amd_ppb_lock_command_set));
                        break;
                case 0xc0:
                        IF_ADDR(0x555,
                                update_state(flash, chip_index,
                                             FS_amd_non_volatile_command_set));
                        break;
                case 0xe0:
                        IF_ADDR(0x555,
                                update_state(flash, chip_index,
                                             FS_amd_volatile_command_set));
                        break;
                case 0xf0:
                        SIM_LOG_INFO(2, to_obj(flash), 0,
                                     "Write-to-Buffer-Abort Reset");
                        update_state(flash, chip_index, FS_read_array);
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "AMD third command cycle with unknown "
                                "data 0x%llx", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_unlock_bypass:
                switch (cmd_code) {
                case 0x25:
                        generic_write_buffer_setup(flash, chip_index,
                                                   offset_in_flash,
                                                   chip_value);
                        update_state(flash, chip_index,
                                     FS_bypass_write_buffer_size);
                        break;
                case 0x80:
                        update_state(flash, chip_index,
                                     FS_amd_unlock_bypass_erase);
                        break;
                case 0xA0:
                        update_state(flash, chip_index,
                                     FS_amd_unlock_bypass_program);
                        break;
                case 0x90:
                        update_state(flash, chip_index,
                                     FS_amd_unlock_bypass_reset);
                        break;
                /* See bug 20011 why read/reset is allowed in unlock bypass
                   mode */
                case 0xf0:
                        /* Nothing happens, device stays in unlock bypass mode */
                        break;
                case 0xaa:
                        update_state(flash, chip_index,
                                     FS_amd_unlock_bypass_command1);
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal data (0x%llx) written while in AMD "
                                "unlock bypass mode", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_unlock_bypass_command1:
                switch (cmd_code) {
                case 0x55:
                        update_state(flash, chip_index,
                                     FS_amd_unlock_bypass_command2);
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal data (0x%llx) written while in AMD "
                                "unlock bypass mode command 1", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_unlock_bypass_command2:
                switch (cmd_code) {
                case 0xf0:
                        update_state(flash, chip_index,
                                     FS_amd_unlock_bypass);
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal data (0x%llx) written while in AMD "
                                "unlock bypass mode command 2", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_unlock_bypass_program:

                amd_program(flash, chip_index, offset_in_flash, chip_value);
                update_state(flash, chip_index, FS_amd_unlock_bypass);
                break;

        case FS_amd_unlock_bypass_reset:
                if (cmd_code == 0x00) {
                        update_state(flash, chip_index, FS_read_array);
                } else {
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal data (0x%llx) in AMD unlock bypass "
                                "reset sequence", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                }
                break;

        case FS_amd_autoselect:
                switch (cmd_code) {
                case 0xFF:
                case 0xF0:
                        update_state(flash, chip_index, FS_read_array);
                        break;
                case 0x98:
                        IF_ADDR(0x55,
                                update_state(flash, chip_index,
                                             FS_cfi_query));
                        break;
                default:
                        if (flash->strict_cmd_set) {
                                SIM_LOG_SPEC_VIOLATION(
                                        1, to_obj(flash), 0,
                                        "writing 0x%llx at 0x%llx in AMD "
                                        "autoselect mode",
                                        chip_value, cmd_addr);
                                update_state(flash, chip_index,
                                             FS_unknown);
                        } else {
                                SIM_LOG_SPEC_VIOLATION(
                                        4, to_obj(flash), 0,
                                        "writing 0x%llx at 0x%llx in AMD "
                                        "autoselect mode - ignored",
                                        chip_value, offset_in_flash);
                        }
                }
                break;

        case FS_amd_erase3:
                switch (cmd_code) {
                case 0xAA:
                        IF_ADDR(0x555,
                                update_state(flash, chip_index,
                                             FS_amd_erase4));
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal value (0x%llx) written as fourth "
                                "cycle in AMD erase sequence", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_erase4:
                switch (cmd_code) {
                case 0x55:
                        IF_ADDR(0x2AA,
                                update_state(flash, chip_index,
                                             FS_amd_erase5));
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal value (0x%llx) written as fifth "
                                "cycle in AMD erase sequence", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_erase5:
                handle_amd_erase_subcommand(
                        flash, chip_index, offset_in_flash, cmd_code,
                        chip_value, FS_amd_erase_in_progress,
                        FS_chip_erase_in_progress, FS_read_array);
                break;

        case FS_amd_unlock_bypass_erase:
                handle_amd_erase_subcommand(
                        flash, chip_index, offset_in_flash, cmd_code,
                        chip_value, FS_bypass_erase_in_progress,
                        FS_bypass_chip_erase_in_progress,
                        FS_amd_unlock_bypass);
                break;

        case FS_amd_erase_in_progress:
        case FS_write_buffer_in_progress:
        case FS_bypass_write_buffer_in_progress:
        case FS_bypass_chip_erase_in_progress:
        case FS_bypass_erase_in_progress:
                cancel_busy_event(flash, chip_index);
                int chip_mode = chip->mode;  /* reset by complete_busy_event */
                if (cmd_code != 0x30) {
                        /* all commands must complete the busy event, or the
                           busy signal will stay raised */
                        complete_busy_event(flash, chip_index);
                }

                switch (cmd_code) {
                case 0xff:                   /* reset */
                case 0xf0:                   /* reset */
                case 0xb0:                   /* erase suspend (bug 21451) */
                        break;
                case 0x30:
                        if (chip_mode == FS_amd_erase_in_progress) {
                                /* repeated sector erase */
                                amd_sector_erase(flash, chip_index,
                                                 offset_in_flash);

                                /* move event forward */
                                /* TODO: make sure busy signal is not
                                 * raised twice */
                                post_busy_event(flash, chip_index,
                                   flash->time_model[FS_amd_erase_in_progress]);
                                break;
                        }
                        /* fall-through */
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal value (0x%llx) written to chip %d"
                                " in '%s' mode",
                                chip_value, chip_index, state_desc[chip_mode]);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_program_pending:
                amd_program(flash, chip_index, offset_in_flash, chip_value);
                update_state(flash, chip_index, FS_read_array);
                break;

        case FS_write_buffer_size: {
                int success = generic_write_buffer_size(
                        flash, chip_index, offset_in_flash, chip_value);
                update_state(flash, chip_index, success
                             ? FS_write_buffer_gather : FS_read_array);
                break;
        }
        case FS_bypass_write_buffer_size: {
                int success = generic_write_buffer_size(
                        flash, chip_index, offset_in_flash, chip_value);
                update_state(flash, chip_index,
                             success ? FS_bypass_write_buffer_gather
                             : FS_read_array);
                break;
        }
        case FS_write_buffer_gather: {
                int result = generic_write_buffer_gather(
                        flash, chip_index, offset_in_flash, chip_value);
                if (result == 2) {
                        update_state(flash, chip_index,
                                     FS_write_buffer_confirm);
                        break;
                }
                return result;
        }
        case FS_bypass_write_buffer_gather: {
                int result = generic_write_buffer_gather(
                        flash, chip_index, offset_in_flash, chip_value);
                if (result == 2) {
                        update_state(flash, chip_index,
                                     FS_bypass_write_buffer_confirm);
                        break;
                }
                return result;
        }
        case FS_write_buffer_confirm:
                if (cmd_code != 0x29)
                        break;
                generic_write_buffer_confirm(flash, chip_index,
                                             offset_in_flash, chip_value);
                if (flash->time_model[FS_write_buffer_in_progress]) {
                        post_busy_event(
                                flash, chip_index, flash->
                                time_model[FS_write_buffer_in_progress]);
                        update_state(flash, chip_index,
                                     FS_write_buffer_in_progress);
                } else {
                        update_state(flash, chip_index, FS_read_array);
                }
                break;

        case FS_bypass_write_buffer_confirm:
                if (cmd_code != 0x29)
                        break;
                generic_write_buffer_confirm(flash, chip_index,
                                             offset_in_flash, chip_value);
                if (flash->time_model[FS_bypass_write_buffer_in_progress]) {
                        post_busy_event(
                                flash, chip_index, flash->
                                time_model[FS_bypass_write_buffer_in_progress]);
                        update_state(flash, chip_index,
                                     FS_bypass_write_buffer_in_progress);
                } else {
                        update_state(flash, chip_index,
                                     FS_amd_unlock_bypass);
                }
                break;

        case FS_amd_lock_register_command_set:
                switch (cmd_code) {
                case 0xa0:
                        update_state(flash, chip_index,
                                     FS_amd_lock_register_bits);
                        break;
                case 0x90:
                        update_state(flash, chip_index,
                                     FS_amd_lock_register_exit);
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal value (0x%llx) written in lock "
                                "register command set", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_lock_register_bits:
                chip->amd.lock_register &= chip_value;
                SIM_LOG_INFO(2, to_obj(flash), 0,
                             "value 0x%llx written to lock register, lock "
                             "bits now 0x%x",
                             chip_value, chip->amd.lock_register);
                update_state(flash, chip_index,
                             FS_amd_lock_register_command_set);
                break;

        case FS_amd_lock_register_exit:
                switch (cmd_code) {
                case 0x00:
                        update_state(flash, chip_index,
                                     FS_read_array);
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal value (0x%llx) written in lock "
                                "register command set exit", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_ppb_lock_command_set:
                switch (cmd_code) {
                case 0xa0:
                        update_state(flash, chip_index,
                                     FS_amd_ppb_lock_program);
                        break;
                case 0x90:
                        update_state(flash, chip_index,
                                     FS_amd_ppb_lock_exit);
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal value (0x%llx) written in PPB "
                                "lock command set", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;
        case FS_amd_ppb_lock_program:
                switch (cmd_code) {
                case 0x00:
                        chip->amd.ppb_lock_bit = 0;
                        SIM_LOG_INFO(2, to_obj(flash), 0,
                                     "PPB lock bit set to 0");
                        update_state(flash, chip_index,
                                     FS_amd_ppb_lock_command_set);
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal value (0x%llx) written in PPB "
                                "lock program", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;
        case FS_amd_ppb_lock_exit:
                switch (cmd_code) {
                case 0x00:
                        update_state(flash, chip_index,
                                     FS_read_array);
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal value (0x%llx) written in PPB "
                                "lock command set exit", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_non_volatile_command_set:
                switch (cmd_code) {
                case 0xa0:
                        update_state(flash, chip_index,
                                     FS_amd_non_volatile_program);
                        break;
                case 0x80:
                        update_state(flash, chip_index,
                                     FS_amd_non_volatile_erase);
                        break;
                case 0x90:
                        update_state(flash, chip_index,
                                     FS_amd_non_volatile_exit);
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal value (0x%llx) written in "
                                "non-volatile command set", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_non_volatile_program:
                switch (cmd_code) {
                case 0x00:
                        amd_ppb_program(flash, chip_index, offset_in_flash);
                        update_state(flash, chip_index,
                                     FS_amd_non_volatile_command_set);
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal value (0x%llx) written in "
                                "non-volatile program", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_non_volatile_erase:
                if (cmd_code == 0x30 && cmd_addr == 0x00) {
                        amd_ppb_erase(flash, chip_index);
                        update_state(flash, chip_index,
                                     FS_amd_non_volatile_command_set);
                } else {
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal value (0x%llx) written in "
                                "non-volatile erase", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                }
                break;

        case FS_amd_non_volatile_exit:
                switch (cmd_code) {
                case 0x00:
                        update_state(flash, chip_index,
                                     FS_read_array);
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal value (0x%llx) written in "
                                "non-volatile command set exit", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_volatile_command_set:
                switch (cmd_code) {
                case 0xa0:
                        update_state(flash, chip_index,
                                     FS_amd_volatile_write);
                        break;
                case 0x90:
                        update_state(flash, chip_index,
                                     FS_amd_volatile_exit);
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal value (0x%llx) written in "
                                "volatile sector protection "
                                "command set", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_volatile_write:
                switch (cmd_code) {
                case 0x00:
                case 0x01:
                        amd_dyb_write(flash, chip_index, offset_in_flash,
                                      cmd_code);
                        update_state(flash, chip_index,
                                     FS_amd_volatile_command_set);
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal value (0x%llx) written in "
                                "volatile DYB bit program", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_amd_volatile_exit:
                switch (cmd_code) {
                case 0x00:
                        update_state(flash, chip_index,
                                            FS_read_array);
                        break;
                default:
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "illegal value (0x%llx) written in "
                                "volatile sector protection "
                                "command set exit", chip_value);
                        update_state(flash, chip_index, FS_unknown);
                        break;
                }
                break;

        case FS_unknown:
        case FS_unimplemented:
                /* allow reset to bring us back to read-array mode */
                switch (cmd_code) {
                case 0xff:
                case 0xf0:
                        update_state(flash, chip_index,
                                     FS_read_array);
                        break;
                default:
                        break;
                }
                break;
        case FS_chip_erase_in_progress:
        case FS_amd_program:
                break;
        case FS_intel_read_identifier_codes:
        case FS_intel_read_status:
        case FS_intel_block_erase:
        case FS_intel_word_program:
        case FS_intel_lock_setup:
        case FS_intel_lock_command_error:
        case FS_intel_lock_command_done:
                /* Intel states shouldn't occur in AMD flash chips */
                ASSERT(0);
        case FS_max:
                ASSERT(0);
        }
        return 1;
}

void amd_finalize(flash_memory_t *flash)
{
}
