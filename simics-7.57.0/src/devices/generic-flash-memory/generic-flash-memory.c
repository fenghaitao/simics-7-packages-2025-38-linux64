/*
  Related Documentation:

  [1] VIN 32: "Flash Memory in Simics"
  [2] JEDEC Standard No. 68
  [3] All flash documentation from Intel/AMD/...

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <string.h>
#include <ctype.h>

#include <simics/device-api.h>
#include <simics/util/bitcount.h>
#include <simics/base/map-target.h>
#include <simics/devs/translator.h>
#include <simics/devs/memory-space.h>
#include <simics/devs/io-memory.h>

// TODO: This violated the Device API
#include <simics/simulator/conf-object.h>

#define DEVICE_NAME "generic-flash-memory"

#include "flash-memory.h"

static const char *const fm_log_groups[] = {
        "Read",
        "Write",
        "Command",
        "Lock",
        "Erase",
        "State",
        "Write Buffer",
        "CFI",
        "Other",
        NULL
};
STATIC_ASSERT(ALEN(fm_log_groups) == FS_Log_Max + 1);

/* Does a timemodel exists for certain type */
static const int supports_time_model[] = {
        FOR_ALL_FLASH_STATE(GET_FIRST_ELEMENT)
};
STATIC_ASSERT(ALEN(supports_time_model) == FS_max);

static int total_timing_model_states_supported;

const char *const state_desc[] = {
        FOR_ALL_FLASH_STATE(GET_THIRD_ELEMENT)
};
STATIC_ASSERT(ALEN(state_desc) == FS_max);

event_class_t *event_operation_done;

uint64
byte_swap(uint64 value, unsigned swap_size)
{
        switch (swap_size) {
        case 1: return value;
        case 2: return SWAB16(value);
        case 4: return SWAB32(value);
        case 8: return SWAB64(value);
        default:
                ASSERT(0);
        }
}

static bool
intel_cmd_set(flash_memory_t *f)
{
        return f->command_set == 1 || f->command_set == 3;
}

static bool
amd_cmd_set(flash_memory_t *f)
{
        return f->command_set == 2 || f->command_set == 4;
}

static uint64
extract_value(uint8 *value, unsigned width, unsigned offset)
{
        switch (width) {
        case 1: return value[offset];
        case 2: return UNALIGNED_LOAD_LE16(&value[offset]);
        case 4: return UNALIGNED_LOAD_LE32(&value[offset]);
        case 8: return UNALIGNED_LOAD_LE64(&value[offset]);
        default:
                ASSERT(0);
        }
}

static uint64
get_chip_value(flash_memory_t *flash, uint8 *value, unsigned offset)
{
        return extract_value(value, flash->chip_width_in_bytes, offset);
}

uint64
get_bus_value(flash_memory_t *flash, uint8 *value)
{
        return extract_value(value, flash->bus_width_in_bytes, 0);
}

static void
set_value(uint8 *value, unsigned width, unsigned offset,
          uint64 partial_value)
{
        switch (width) {
        case 1: value[offset] = partial_value; break;
        case 2: UNALIGNED_STORE_LE16(&value[offset], partial_value); break;
        case 4: UNALIGNED_STORE_LE32(&value[offset], partial_value); break;
        case 8: UNALIGNED_STORE_LE64(&value[offset], partial_value); break;
        default:
                ASSERT(0);
        }
}

static void
set_chip_value(flash_memory_t *flash, uint8 *value, unsigned offset,
               uint64 partial_value)
{
        set_value(value, flash->chip_width_in_bytes, offset, partial_value);
}

/* update the state of a chip if necessary */
void
update_state(flash_memory_t *flash, unsigned chip_index, fm_operation_t state)
{
        chip_t *chip = &flash->chip[chip_index];

        if (state != chip->mode)
                SIM_LOG_INFO(3, to_obj(flash), FS_Log_State,
                             "chip %d: new state: %s (%d)",
                             chip_index, state_desc[state], (int)state);
        chip->mode = state;

        /* flush translations to RAM */
        if (flash->has_translated_to_ram && state != FS_read_array) {
                SIM_translation_changed(to_obj(flash));
                flash->has_translated_to_ram = false;
        }
}

/* find a unit index by its offset in the chip */
int
get_unit_in_chip(flash_memory_t *flash, uint64 offset_in_chip, bool exact)
{
        if (!flash->unit_bits) {
                return -1;
        } else if (flash->uniform_units) {
                int n = offset_in_chip >> flash->unit_bits[0];
                if (n < flash->num_units)
                        return n;
        } else {
                int i = 0;
                int64 ofs = offset_in_chip;
                while (ofs >= 0 && i < flash->num_units) {
                        if ((exact && ofs == 0)
                            || (!exact && ofs < flash_unit_size(flash, i)))
                                return i;
                        ofs -= flash_unit_size(flash, i);
                        i++;
                }
        }

        return -1;
}

/* return the relative offset in the current unit */
static int64
get_offset_in_unit(flash_memory_t *flash, int64 offset_in_chip)
{
        if (!flash->unit_bits) {
                return -1;
        } else if (flash->uniform_units) {
                return offset_in_chip & (flash_unit_size(flash, 0) - 1);
        } else {
                int i = 0;
                while (offset_in_chip >= 0 && i < flash->num_units) {
                        if (offset_in_chip < flash_unit_size(flash, i))
                                return offset_in_chip;
                        else
                                offset_in_chip -= flash_unit_size(flash, i);
                        i++;
                }
        }

        return -1;
}

/* return the total size of one chip */
int64
get_total_chip_size(flash_memory_t *flash)
{
        if (!flash->unit_bits)
                return -1;
        if (flash->uniform_units)
                return (uint64) flash->num_units << flash->unit_bits[0];
        uint64 sum = 0;
        for (int i = 0; i < flash->num_units; i++)
                sum += flash_unit_size(flash, i);
        return sum;
}

static void
reset(flash_memory_t *flash)
{
        SIM_LOG_INFO(3, to_obj(flash), 0, "reset");

        for (int i = 0; i < flash_interleave(flash); i++) {
                flash->chip[i].mode = FS_read_array;
                flash->chip[i].write_buffer = NULL;
                flash->chip[i].write_buffer_len = 0;
                flash->chip[i].start_address = 0;
                flash->chip[i].current_count = 0;
                for (int j = 0; j < flash->num_units; j++) {
                        /* a reset also affects DYB bits on AMD chips */
                        flash->chip[i].unit_data[j].dyb = 1;
                }
        }
}

static void
perform_transaction(map_target_t *mt, transaction_t *t, uint64 addr)
{
        exception_type_t ex = SIM_issue_transaction(mt, t, addr);
        SIM_transaction_wait(t, ex);
}

static void
perform_write(bytes_t *data, conf_object_t *obj, map_target_t *mt, uint64 addr)
{
        atom_t list[] = {
                ATOM_completion(NULL),
                ATOM_flags(Sim_Transaction_Write),
                ATOM_size(data->len),
                ATOM_data((uint8_t *)data->data),
                ATOM_initiator(obj),
                ATOM_LIST_END,
        };

        transaction_t t = { list };
        perform_transaction(mt, &t, addr);
}

static void
perform_read(buffer_t *buf, conf_object_t *obj, map_target_t *mt, uint64 addr)
{
        atom_t list[] = {
                ATOM_completion(NULL),
                ATOM_flags(0),
                ATOM_size(buf->len),
                ATOM_data(buf->data),
                ATOM_initiator(obj),
                ATOM_LIST_END,
        };

        transaction_t t = { list };
        perform_transaction(mt, &t, addr);
}

/* read an aligned 8, 16, 32 or 64 bits value from memory */
uint64
memory_read(flash_memory_t *flash, uint64 offset, unsigned len)
{
        uint64 scratch_data;
        buffer_t buf = { (uint8 *)&scratch_data, len };
        perform_read(&buf, to_obj(flash), flash->storage_ram_map_target,
                     offset);
        return scratch_data;
}

/* write an aligned 8, 16, 32 or 64 bits value to memory */
void
memory_write(flash_memory_t *flash, uint64 offset,
             unsigned len, uint64 value)
{
        bytes_t data = { (uint8 *)&value, len };
        perform_write(&data, to_obj(flash), flash->storage_ram_map_target,
                      offset);
}

/* write a buffer of any size to memory */
void
memory_write_buf(flash_memory_t *flash,
                 uint64 address, uint64 len,
                 uint8 *buf)
{
        bytes_t data = { buf, len };
        perform_write(&data, to_obj(flash), flash->storage_ram_map_target,
                      address);
}

/* write a buffer straddled in memory depending on interleave */
void
memory_write_buf_straddle(flash_memory_t *flash, uint64 offset, uint64 size,
                          uint8 *buf, unsigned width, unsigned straddle)
{
        for (uint64 i = 0; i < size; i += width)
                memory_write_buf(flash, offset + i * straddle, width, buf + i);
}

/* set a specific part of memory to the same byte value */
void
memory_set(flash_memory_t *flash, uint64 offset, uint64 size, uint8 value)
{
#define SET_BLOCK_SIZE 4096
        uint8 buffer[SET_BLOCK_SIZE];
        memset(buffer, value, MIN(size, SET_BLOCK_SIZE));

        while (size) {
                int n = MIN(size, SET_BLOCK_SIZE);
                memory_write_buf(flash, offset, n, buffer);
                size -= n;
                offset += n;
        }
}

/* set a specific part of memory to the same byte value */
void
memory_set_straddle(flash_memory_t *flash, uint64 offset, uint64 size,
                    uint8 value, unsigned width, unsigned straddle)
{
        uint64 scratch_value;
        memset(&scratch_value, value, sizeof(scratch_value));
        for (uint64 i = 0; i < size; i += width)
                memory_write(flash, offset + i * straddle, width,
                             scratch_value);
}

/* validate that the flash setup is consistent */
static bool
valid_setup(flash_memory_t *flash)
{
        /* validate cfi query structure, if any */
        if (flash->cfi_query_struct == NULL) {
                if (flash->command_set == 0) {
                        SIM_LOG_ERROR(to_obj(flash), 0,
                                      "No CFI structure and no command set. "
                                      "You must define at least a command-set "
                                      "for a non-CFI compatible device.");
                        return false;
                }
        }
        else {
                if (flash->cfi_query_size < 0x31) {
                        SIM_LOG_ERROR(to_obj(flash), 0,
                                      "query structure too small");
                        return false;
                }

                if (memcmp(&flash->cfi_query_struct[0x10], "QRY", 3) != 0) {
                        SIM_LOG_SPEC_VIOLATION(
                                1, to_obj(flash), 0,
                                "query structure must start with \"QRY\"");
                        return false;
                }

                if (flash->cfi_query_struct[0x27] == 0) {
                        SIM_LOG_ERROR(to_obj(flash), 0,
                                      "device size (query structure offset "
                                      "0x27) is zero");
                        return false;
                }
        }

        /* validate chip organization */
        if (flash->interleave_bits > 3) {
                SIM_LOG_ERROR(to_obj(flash), 0,
                              "interleave should be 1, 2, 4, or 8");
                return false;
        }

        if (   flash->bus_width_in_bits != 8
            && flash->bus_width_in_bits != 16
            && flash->bus_width_in_bits != 32
            && flash->bus_width_in_bits != 64) {
                SIM_LOG_ERROR(to_obj(flash), 0,
                              "bus width should be 8, 16, 32, or 64 bits");
                return false;
        }

        if (flash->chip_width_in_bits << flash->interleave_bits
            != flash->bus_width_in_bits) {
                SIM_LOG_ERROR(to_obj(flash), 0, "chip width %d doesn't match "
                              "bus width and interleave",
                              flash->chip_width_in_bits);
                return false;
        }

        if (flash->chip_width_in_bits > flash->max_chip_width_in_bits) {
                SIM_LOG_ERROR(to_obj(flash), 0,
                              "chip width cannot exceed maximum device width");
                return false;
        }

        if (flash->command_set < 1 || flash->command_set > 4) {
                SIM_LOG_ERROR(to_obj(flash), 0,
                              "Defined command-set is not valid: %u. "
                              "You should set it via cfi_query if your "
                              "flash is CFI compatible, or directly via the "
                              "command_set attribute if not.",
                              flash->command_set);
                return false;
        }

        /* validate partition */
        if (flash->unit_bits) {
                if (flash->num_units <= 0) {
                        SIM_LOG_ERROR(to_obj(flash), 0,
                                  "flash must have at least one block/sector");
                        return false;
                }

                if (flash->cfi_query_struct) {
                        int size = 0;
                        for (int i = 0; i < flash->num_units; i++)
                                size += flash_unit_size(flash, i);

                        if (size != (1 << flash->cfi_query_struct[0x27])) {
                                SIM_LOG_ERROR(to_obj(flash), 0,
                                              "the sum of blocks/sectors "
                                              "(0x%x) doesn't match device "
                                              "size (%d bits)", size,
                                              flash->cfi_query_struct[0x27]);
                                return false;
                        }
                }
        }

        return true;
}

int
generic_read_lock_status(flash_memory_t *flash, unsigned chip_index,
                         uint64 offset_in_flash)
{
        /* Block lock status */
        uint64 offset_in_chip = get_offset_in_chip(flash, offset_in_flash);
        int unit_index = get_unit_in_chip(flash, offset_in_chip, false);

        if (unit_index == -1) {
                SIM_LOG_SPEC_VIOLATION(
                        1, to_obj(flash), FS_Log_Lock,
                        "received a lock status read for a non-existing block "
                        "(offset in chip 0x%llx)", offset_in_chip);
                return 0;
        }

        return flash->chip[chip_index].unit_data[unit_index].lock_status;
}

/* generic write_buffer */
void
generic_write_buffer_setup(flash_memory_t *flash, unsigned chip_index,
                           uint64 offset_in_flash, uint64 value)
{
        chip_t *chip = &flash->chip[chip_index];

        chip->start_address = offset_in_flash;
        SIM_LOG_INFO(4, to_obj(flash), FS_Log_Write_Buffer,
                     "write-to-buffer: command started for block 0x%llx",
                     offset_in_flash);
}

/* returns 1 if successful, 0 if unsuccessful, does not update chip state */
int
generic_write_buffer_size(flash_memory_t *flash, unsigned chip_index,
                          uint64 offset_in_flash, uint64 value)
{
        chip_t *chip = &flash->chip[chip_index];
        unsigned wb_max_len_in_words =
                flash->wb_max_len_in_bytes / flash->chip_width_in_bytes;

        if (offset_in_flash != chip->start_address) {
                SIM_LOG_SPEC_VIOLATION(
                        2, to_obj(flash), FS_Log_Write_Buffer,
                        "write-to-buffer: address mismatch in second command "
                        "cycle (0x%llx instead of 0x%llx)",
                        offset_in_flash, chip->start_address);
                chip->start_address = offset_in_flash;
        }

        if (value >= wb_max_len_in_words) {
                SIM_LOG_SPEC_VIOLATION(
                        2, to_obj(flash), FS_Log_Write_Buffer,
                        "write-to-buffer: invalid count %lld", value);
                return 0;
        }

        SIM_LOG_INFO(4, to_obj(flash), FS_Log_Write_Buffer,
                     "write-to-buffer: using buffer of %lld words", value + 1);

        chip->current_count = 0;
        chip->write_buffer_len = (value + 1) * flash->chip_width_in_bytes;
        chip->write_buffer = MM_ZALLOC(chip->write_buffer_len, uint8);
        return 1;
}

/* Returns 1 if buffer not filled, 2 if buffer filled,
   0 if unsuccessful. Does not update chip state. */
int
generic_write_buffer_gather(flash_memory_t *flash, unsigned chip_index,
                          uint64 offset_in_flash, uint64 chip_value)
{
        chip_t *chip = &flash->chip[chip_index];
        uint64 buffer_offset;
        /* byte-swap back chip_value so we write straight to memory what the
           processor told us to write */
        uint64 chip_value_nc = endian_converted(flash, chip_value);

        /* check for start address */
        if (chip->current_count == 0) {
                chip->start_address = offset_in_flash;
                SIM_LOG_INFO(4, to_obj(flash), FS_Log_Write_Buffer,
                             "write-to-buffer: start address 0x%llx",
                             offset_in_flash);
        }

        /* check address range */
        buffer_offset = (offset_in_flash - chip->start_address)
                        >> flash->interleave_bits;
        if (offset_in_flash < chip->start_address ||
            buffer_offset > (chip->write_buffer_len - 1)) {
                SIM_LOG_SPEC_VIOLATION(
                        1, to_obj(flash), FS_Log_Write_Buffer,
                        "write-to-buffer: address 0x%llx outside buffer",
                        offset_in_flash);
                return 0;
        }

        for (int i = 0; i < flash->chip_width_in_bytes; i++)
                chip->write_buffer[buffer_offset + i] =
                        chip_value_nc >> (i * 8);

        chip->current_count += flash->chip_width_in_bytes;

        if (chip->current_count == chip->write_buffer_len) {
                SIM_LOG_INFO(4, to_obj(flash), FS_Log_Write_Buffer,
                             "write-to-buffer: %d bytes written",
                             chip->write_buffer_len);
                return 2;
        }
        else
                return 1;
}

void
generic_write_buffer_confirm(flash_memory_t *flash, unsigned chip_index,
                             uint64 offset_in_flash, uint64 value)
{
        chip_t *chip = &flash->chip[chip_index];

        SIM_LOG_INFO(4, to_obj(flash), FS_Log_Write_Buffer,
                     "write-to-buffer: confirmed");

        if(flash->wp == 1) {
                SIM_LOG_INFO(
                        2, to_obj(flash), FS_Log_Write_Buffer,
                        "write-to-buffer: WP pin blocking write");
                return;
        }

        memory_write_buf_straddle(flash,
                                  chip->start_address
                                  + chip_index * flash->chip_width_in_bytes,
                                  chip->write_buffer_len,
                                  chip->write_buffer,
                                  flash->chip_width_in_bytes,
                                  flash_interleave(flash));
        MM_FREE(chip->write_buffer);

        chip->write_buffer = NULL;
        chip->write_buffer_len = 0;
        chip->start_address = 0;
        chip->current_count = 0;
}

int
cfi_query_read(flash_memory_t *flash, unsigned chip_index,
               uint64 offset_in_flash, uint64 *chip_value)
{
        uint8  query_data = 0;
        uint64 offset_in_chip = get_offset_in_chip(flash, offset_in_flash);

        /* compute the relative offset in the current unit. Since for example
           lock status information is present at the same offset for each unit,
           a unit is considered as the biggest amount of data addressable
           through a CFI query. Taking the relative offset makes the access
           limited to a unit size. */
        uint64 offset_in_unit = get_offset_in_unit(flash, offset_in_chip);

        /* compute the real offset in the CFI table */
        uint64 query_offset = get_cmd_offset(flash, offset_in_unit);

        *chip_value = 0;

        /* handle block lock first */
        if (query_offset == 0x2) {
                query_data = generic_read_lock_status(flash, chip_index,
                                                      offset_in_flash);
        }
        else {
                if (flash->cfi_query_struct == NULL) {
                        SIM_LOG_ERROR(to_obj(flash), 0,
                                      "no query structure available");
                        return 0;
                }

                if (query_offset >= flash->cfi_query_size) {
                        SIM_LOG_SPEC_VIOLATION(
                                2, to_obj(flash), FS_Log_CFI,
                                "query read at unsupported cfi offset "
                                "(0x%llx), memory offset = 0x%llx",
                                query_offset, offset_in_flash);
                        return 0;
                }

                query_data = flash->cfi_query_struct[query_offset];
        }

        SIM_LOG_INFO(4, to_obj(flash), FS_Log_CFI,
                     "chip %u: reading query data 0x%x at index 0x%llx, "
                     "memory offset 0x%llx",
                     chip_index, (int)query_data, query_offset,
                     offset_in_flash);

        *chip_value = query_data;
        return 1;
}

/* return true if all chips are in the same state */
static bool
same_chip_state(flash_memory_t *flash)
{
        fm_operation_t state = flash->chip[0].mode;

        for (int i = 1; i < flash_interleave(flash); i++)
                if (flash->chip[i].mode != state)
                        return false;
        return true;
}

/* return true if the values written to the chips are all the same */
static bool
same_chip_values(flash_memory_t *flash, uint8 *value, unsigned size)
{
        unsigned width = flash->chip_width_in_bytes;
        uint64 chip_value = get_chip_value(flash, value, 0);

        for (unsigned offset = width; offset < size; offset += width)
                if (get_chip_value(flash, value, offset) != chip_value)
                        return false;
        return true;
}

static bool do_aligned_op(flash_memory_t *flash,
                          generic_transaction_t *memop,
                          uint64 address);

/* pad an operation so that it addresses entire chips, and try again */
static bool
pad_and_translate(flash_memory_t *flash,
                  generic_transaction_t *memop,
                  uint64 address)
{
        SIM_LOG_INFO(4, to_obj(flash), 0,
                     "padding operation (address offset = 0x%llx,"
                     " size = %d, but chip_width = %d)",
                     address, SIM_get_mem_op_size(memop),
                     flash->chip_width_in_bytes);

        unsigned width = flash->chip_width_in_bytes;
        physical_address_t aligned_start = address
                & ~((uint64) width - 1);
        physical_address_t end = address + SIM_get_mem_op_size(memop);
        physical_address_t aligned_end =
                (end & ~((uint64) width - 1));
        aligned_end = (end == aligned_end) ? end : aligned_end + width;

        uint8 scratch[aligned_end - aligned_start];
        memset(scratch, 0, sizeof(scratch));

        /* perform a padded access */
        generic_transaction_t new_memop = *memop;
        new_memop.size = aligned_end - aligned_start;
        SIM_set_mem_op_virtual_address(&new_memop, 0);
        new_memop.real_address = scratch;
        SIM_set_mem_op_initiator(&new_memop, Sim_Initiator_Other, NULL);

        if (SIM_mem_op_is_write(memop))
                SIM_c_get_mem_op_value_buf(
                        memop,
                        scratch + (address - aligned_start));

        bool io = do_aligned_op(flash, &new_memop, aligned_start);

        /* check if an operation was done */
        if (io && SIM_mem_op_is_read(memop))
                SIM_c_set_mem_op_value_buf(
                        memop,
                        scratch + (address - aligned_start));
        return io;
}

/* log an access represented by 'value', which may have an unusual size */
static void
log_array_access(unsigned level, conf_object_t *obj, unsigned log_group,
                 uint64 address, uint8 *value, unsigned size)
{
        strbuf_t str = sb_newf(log_group == FS_Log_Write
                               ? "writing to address   0x%016llx: "
                               : "reading from address 0x%016llx: ",
                               address);
        if (size == 1 || size == 2 || size == 4 || size == 8) {
                uint64 gvalue = extract_value(value, size, 0);
                sb_addfmt(&str, "0x%llx", gvalue);
        } else {
                for (unsigned i=0; i<size; i++)
                        sb_addfmt(&str, "0x%x ", (unsigned)value[i]);
        }
        SIM_LOG_INFO(level, obj, log_group, "%s", sb_str(&str));
        sb_free(&str);
}

/* align address to the flash's bus size and return the new value */
static uint64
bus_aligned(flash_memory_t *flash, uint64 address)
{
        return address & ~((uint64) (flash->bus_width_in_bytes - 1));
}

/* handle a flash write operation */
static bool
do_write_op(flash_memory_t *flash, generic_transaction_t *memop,
            uint64 address, unsigned start_chip)
{
        unsigned size = SIM_get_mem_op_size(memop);
        uint8 value[size];
        memset(value, 0, size);
        SIM_c_get_mem_op_value_buf(memop, value);

        if (SIM_log_level(to_obj(flash)) >= 3) {
                log_array_access(3, to_obj(flash), FS_Log_Write,
                                 address, value, size);
        }

        /* fill in optimization variables */
        flash->opt_op.same_state = same_chip_state(flash);
        flash->opt_op.bus_size = size == flash->bus_width_in_bytes;
        flash->opt_op.bus_aligned = bus_aligned(flash, address) == address;
        flash->opt_op.same_value = same_chip_values(flash, value, size);
        flash->opt_op.full_value = value;
        flash->opt_op.done = false;

        /*
           loop over each chip addressed by the memory transaction, and perform
           the write operation
        */

        /* true when a chip reports an operation was done, which means the
           transaction should not go to memory */
        bool operation_done = false;
        /* address of the current chip being written to */
        uint64 addr = address;
        /* address reported to the chip (aligned on flash bus) */
        uint64 report_addr = bus_aligned(flash, addr);
        /* current chip index in the flash */
        unsigned chip_index = start_chip;
        while (addr < address + size) {
                uint64 chip_value = endian_converted(
                        flash, get_chip_value(flash, value, addr - address));

                /* intel */
                if (intel_cmd_set(flash) &&
                    intel_write_operation(flash, chip_index,
                                          report_addr, chip_value))
                        operation_done = true;

                /* amd */
                else if (amd_cmd_set(flash) &&
                         amd_write_operation(flash, chip_index,
                                             report_addr, chip_value))
                        operation_done = true;

                addr += flash->chip_width_in_bytes;
                report_addr = bus_aligned(flash, addr);
                chip_index = (chip_index + 1) & (flash_interleave(flash) - 1);
        }

        return operation_done;
}

/* handle a flash read operation */
static bool
do_read_op(flash_memory_t *flash, generic_transaction_t *memop,
           uint64 address, unsigned start_chip)
{
        unsigned size = SIM_get_mem_op_size(memop);
        uint8 value[size];
        memset(value, 0, size);

        /* fill in optimization variables */
        flash->opt_op.same_state = same_chip_state(flash);
        flash->opt_op.bus_size = size == flash->bus_width_in_bytes;
        flash->opt_op.bus_aligned = bus_aligned(flash, address) == address;
        flash->opt_op.same_value = false;
        flash->opt_op.full_value = NULL;
        flash->opt_op.done = false;

        /*
           loop over each chip addressed by the memory transaction, and perform
           the write operation
        */

        /* true when a chip reports an operation was done, which means the
           transaction should not go to memory */
        bool operation_done = false;
        /* address of the current chip being read from */
        uint64 addr = address;
        /* address reported to the chip (aligned on flash bus) */
        uint64 report_addr = bus_aligned(flash, addr);
        /* current chip index in the flash */
        unsigned chip_index = start_chip;
        while (addr < address + size) {
                uint64 chip_value = 0;

                /* intel */
                if (intel_cmd_set(flash) &&
                    intel_read_operation(flash, chip_index,
                                         report_addr, &chip_value))
                        operation_done = true;

                /* amd */
                else if (amd_cmd_set(flash) &&
                         amd_read_operation(flash, chip_index,
                                            report_addr, &chip_value))
                        operation_done = true;

                if (operation_done)
                        set_chip_value(flash, value, addr - address,
                                       endian_converted(flash, chip_value));

                addr += flash->chip_width_in_bytes;
                report_addr = bus_aligned(flash, addr);
                chip_index = (chip_index + 1) & (flash_interleave(flash) - 1);
        }

        if (operation_done) {
                if (SIM_log_level(to_obj(flash)) >= 3)
                        log_array_access(3, to_obj(flash), FS_Log_Read,
                                         address, value, size);
                SIM_c_set_mem_op_value_buf(memop, value);
        } else {
                SIM_LOG_INFO(4, to_obj(flash), FS_Log_Read,
                             "reading from address 0x%016llx (from memory)",
                             address);
        }

        return operation_done;
}

static void
memory_operate(flash_memory_t *flash, uint64 address,
               generic_transaction_t *memop)
{
        if (SIM_mem_op_is_write(memop)) {
                uint8 char_buf[SIM_get_mem_op_size(memop)];
                SIM_c_get_mem_op_value_buf(memop, char_buf);
                bytes_t data = { char_buf, SIM_get_mem_op_size(memop) };
                perform_write(&data, to_obj(flash),
                              flash->storage_ram_map_target, address);
        } else {
                uint8 char_buf[SIM_get_mem_op_size(memop)];
                buffer_t buf = { char_buf, SIM_get_mem_op_size(memop) };
                perform_read(&buf, to_obj(flash),
                             flash->storage_ram_map_target, address);
                SIM_c_set_mem_op_value_buf(memop, char_buf);
        }
}

static exception_type_t
nfm_operation(conf_object_t *obj, generic_transaction_t *memop,
              map_info_t map_info)
{
        flash_memory_t *flash = from_obj(obj);

        /* byte address in the memory space represented
           by the flash-memories */
        uint64 address = SIM_get_mem_op_physical_address(memop)
                + map_info.start - map_info.base;

        if (SIM_get_mem_op_inquiry(memop)) {
                /* Behavior for inquiry is that we access the image
                   directly. Tests and possibly other things depend on this. */
                memory_operate(flash, address, memop);
                return Sim_PE_No_Exception;
        }

        /* if the operation is not aligned on a chip boundary, pad it and
           try again */
        if ((address & (flash->chip_width_in_bytes - 1))
            || (SIM_get_mem_op_size(memop)
                & (flash->chip_width_in_bytes - 1))) {
                bool io = pad_and_translate(flash, memop, address);
                if (!io)
                        memory_operate(flash, address, memop);
                return Sim_PE_No_Exception;
        }

        bool io = do_aligned_op(flash, memop, address);
        if (!io)
                memory_operate(flash, address, memop);
        return Sim_PE_No_Exception;
}

static exception_type_t
port_nfm_operation(conf_object_t *obj, generic_transaction_t *memop,
                   map_info_t map_info)
{
        return nfm_operation(SIM_port_object_parent(obj), memop, map_info);
}

static translation_t
nfm_translate(conf_object_t *obj, physical_address_t addr,
              access_t rwx, const map_target_t *default_tgt)
{
        flash_memory_t *flash = from_obj(obj);

        /* Special case of memory-map command. */
        access_t all = (Sim_Access_Read | Sim_Access_Write
                        | Sim_Access_Execute);
        if ((rwx & all) == all) {
                if (default_tgt)
                        return (translation_t){ .target = default_tgt, };
                else
                        return (translation_t){
                                .target = flash->io_map_target };
        }

        /* fail translation of more than one type */
        if (rwx != Sim_Access_Read &&
            rwx != Sim_Access_Write &&
            rwx != Sim_Access_Execute)
                return (translation_t){ NULL };

        /* writes always should always go to the I/O bank */
        if (rwx & Sim_Access_Write)
                return (translation_t){ .target = flash->io_map_target };

        /* translate directly to RAM if all chips are read-array mode */
        bool same_state = same_chip_state(flash);
        if (same_state && flash->chip[0].mode == FS_read_array) {
                flash->has_translated_to_ram = true;
                if (default_tgt)
                        return (translation_t){ .target = default_tgt, };
                else
                        return (translation_t){
                                .target = flash->storage_ram_map_target, };
        }

        /* translate to I/O. We flag this as a dynamic translation
           since we want to change this to direct RAM access
           without having to flush stuff */
        return (translation_t){
                .target = flash->io_map_target,
                .flags = Sim_Translation_Dynamic,
        };
}

static bool
do_aligned_op(flash_memory_t *flash, generic_transaction_t *memop,
              uint64 address)
{
        /* address is aligned on a chip boundary, so this is an exact
           operation */
        unsigned start_chip = (address & (flash->bus_width_in_bytes - 1))
                / flash->chip_width_in_bytes;

        /* do the access */
        if (SIM_mem_op_is_write(memop))
                return do_write_op(flash, memop, address, start_chip);
        else
                return do_read_op(flash, memop, address, start_chip);
}

/*** attributes ***/

static set_error_t
set_command_set(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        if (SIM_attr_integer(*val) < 1 || SIM_attr_integer(*val) > 4)
                return Sim_Set_Illegal_Value;
        else
                flash->command_set = SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_command_set(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_uint64(flash->command_set);
}

/* cfi support */

static set_error_t
set_cfi_query_struct(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);

        if (SIM_attr_is_nil(*val)) {
                MM_FREE(flash->cfi_query_struct);
                flash->cfi_query_struct = NULL;
                flash->cfi_query_size = 0;
        }
        else if (SIM_attr_is_data(*val)) {
                MM_FREE(flash->cfi_query_struct);
                flash->cfi_query_struct =
                        MM_ZALLOC(SIM_attr_data_size(*val), uint8);
                memcpy(flash->cfi_query_struct,
                       SIM_attr_data(*val),
                       SIM_attr_data_size(*val));
                flash->cfi_query_size = SIM_attr_data_size(*val);
        }
        else {
                for (int i = 0; i < SIM_attr_list_size(*val); i++) {
                        if (SIM_attr_integer(SIM_attr_list_item(*val, i)) < 0
                            || SIM_attr_integer(
                                    SIM_attr_list_item(*val, i)) > 255)
                                return Sim_Set_Illegal_Value;
                }

                MM_FREE(flash->cfi_query_struct);
                flash->cfi_query_struct =
                        MM_ZALLOC(SIM_attr_list_size(*val), uint8);
                flash->cfi_query_size = SIM_attr_list_size(*val);

                for (int i = 0; i < SIM_attr_list_size(*val); i++)
                        flash->cfi_query_struct[i] =
                                SIM_attr_integer(SIM_attr_list_item(*val, i));
        }

        if (flash->cfi_query_size > 0x14) {
                attr_value_t cmdset;
                cmdset = SIM_make_attr_uint64(
                        (flash->cfi_query_struct[0x14] << 8)
                        | flash->cfi_query_struct[0x13]);
                return set_command_set(&flash->obj, &cmdset);
        }
        else
                return Sim_Set_Ok;
}

static attr_value_t
get_cfi_query_struct(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);

        if (flash->cfi_query_struct)
                return SIM_make_attr_data(flash->cfi_query_size,
                                          flash->cfi_query_struct);
        else
                return SIM_make_attr_nil();
}

/* generic information */

static set_error_t
set_device_id(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *fm = from_obj(obj);

        MM_FREE(fm->device_id);
        if (SIM_attr_is_integer(*val)) {
                fm->device_id_len = 1;
                fm->device_id = MM_ZALLOC(fm->device_id_len, uint32);
                fm->device_id[0] = SIM_attr_integer(*val);
        } else {
                fm->device_id_len = SIM_attr_list_size(*val);
                fm->device_id = MM_ZALLOC(fm->device_id_len, uint32);
                for (int i = 0; i < fm->device_id_len; i++)
                        fm->device_id[i] =
                                SIM_attr_integer(SIM_attr_list_item(*val, i));
        }

        return Sim_Set_Ok;
}

static attr_value_t
get_device_id(conf_object_t *obj)
{
        flash_memory_t *fm = from_obj(obj);

        if (fm->device_id_len == 1)
                return SIM_make_attr_uint64(fm->device_id[0]);
        else {
                attr_value_t ret = SIM_alloc_attr_list(fm->device_id_len);
                for (int i = 0; i < fm->device_id_len; i++)
                        SIM_attr_list_set_item(
                                &ret, i,
                                SIM_make_attr_uint64(fm->device_id[i]));
                return ret;
        }
}

static set_error_t
set_manufacturer_id(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *fm = from_obj(obj);
        fm->manufacturer_id = SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_manufacturer_id(conf_object_t *obj)
{
        flash_memory_t *fm = from_obj(obj);
        return SIM_make_attr_uint64(fm->manufacturer_id);
}


/* device layout */

static set_error_t
set_interleave(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        unsigned bits = LOG2(SIM_attr_integer(*val));
        if (bits > 3 || 1 << bits != SIM_attr_integer(*val))
                return Sim_Set_Illegal_Value;

        if (flash->chip) {
                if (flash->interleave_bits == bits)
                        return Sim_Set_Ok;
                else {
                        SIM_LOG_ERROR(to_obj(flash), 0,
                                      "not allowed to change interleave "
                                      "when running");
                        return Sim_Set_Illegal_Value;
                }
        }

        flash->interleave_bits = bits;

        flash->chip = MM_ZALLOC(1 << bits, chip_t);
        for (int i = 0; i < (1 << bits); i++) {
                flash->chip[i].mode = FS_read_array;
                flash->chip[i].amd.lock_register = 0xffff;
                flash->chip[i].amd.ppb_lock_bit = 1;
        }

        return Sim_Set_Ok;
}

static attr_value_t
get_interleave(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_uint64(flash_interleave(flash));
}

static set_error_t
set_bus_width(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);

        int64 value = SIM_attr_integer(*val);
        if (value != 8 && value != 16 && value != 32 && value != 64)
                return Sim_Set_Illegal_Value;

        if ((value >> flash->interleave_bits) < 8) {
                SIM_LOG_ERROR(to_obj(flash), 0,
                              "Incompatible values for bus_width "
                              "and interleave");
                return Sim_Set_Illegal_Value;
        }

        flash->bus_width_in_bits = value;
        flash->bus_width_in_bytes = value / 8;

        flash->chip_width_in_bits =
                flash->bus_width_in_bits >> flash->interleave_bits;
        flash->chip_width_in_bytes = flash->chip_width_in_bits / 8;
        flash->chip_mask = (1 << flash->chip_width_in_bits) - 1;

        return Sim_Set_Ok;
}

static attr_value_t
get_bus_width(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_uint64(flash->bus_width_in_bits);
}

static set_error_t
set_max_chip_width(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);

        int64 value = SIM_attr_integer(*val);
        if (value != 8 && value != 16 && value != 32 && value != 64)
                return Sim_Set_Illegal_Value;

        flash->max_chip_width_in_bits = value;
        flash->max_chip_width_in_bytes = value / 8;

        return Sim_Set_Ok;
}

static attr_value_t
get_max_chip_width(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_uint64(flash->max_chip_width_in_bits);
}

static set_error_t
set_write_buffer_size(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        flash->wb_max_len_in_bytes = SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_write_buffer_size(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_uint64(flash->wb_max_len_in_bytes);
}

static attr_value_t
get_wp_flag(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_boolean((bool)flash->wp);
}

static set_error_t
set_wp_flag(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        flash->wp = (int)SIM_attr_boolean(*val);
        return Sim_Set_Ok;
}

static void
wp_disable(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        SIM_LOG_INFO(3, to_obj(flash), 0,
                     "The hardware write protect was disabled");

        flash->wp = 0;
}

static void
wp_enable(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        SIM_LOG_INFO(3, to_obj(flash), 0,
                     "The hardware write protect was enabled");

        flash->wp = 1;
}

static void
port_wp_enable(conf_object_t *obj)
{
        wp_enable(SIM_port_object_parent(obj));
}

static void
port_wp_disable(conf_object_t *obj)
{
        wp_disable(SIM_port_object_parent(obj));
}

/* chip layout */

static set_error_t
set_unit_size(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        flash->num_units = SIM_attr_list_size(*val);
        MM_FREE(flash->unit_bits);
        flash->unit_bits = MM_ZALLOC(flash->num_units, unsigned);

        int size = SIM_attr_integer(SIM_attr_list_item(*val, 0));
        for (int i = 0; i < flash->num_units; i++)
                if (!SIM_attr_is_integer(SIM_attr_list_item(*val, i)))
                        return Sim_Set_Illegal_Value;
                else {
                        unsigned usize =
                                SIM_attr_integer(SIM_attr_list_item(*val, i));
                        unsigned bits = LOG2(usize);
                        if (usize != 1 << bits)
                                return Sim_Set_Illegal_Value;
                        flash->unit_bits[i] = bits;
                        if (size != usize)
                                size = -1;
                }

        flash->uniform_units = size != -1;

        /* allocate unit_data information */
        for (int i = 0; i < flash_interleave(flash); i++) {
                MM_FREE(flash->chip[i].unit_data);
                flash->chip[i].unit_data =
                        MM_ZALLOC(flash->num_units, unit_data_t);
                /* set default values of unit_data */
                for (int j = 0; j < flash->num_units; j++) {
                        unit_data_t *unit = &flash->chip[i].unit_data[j];
                        unit->dyb = 1;
                        unit->ppb = 1;
                }
        }

        return Sim_Set_Ok;
}

static attr_value_t
get_unit_size(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t attr = SIM_alloc_attr_list(flash->num_units);
        for (int i = 0; i < flash->num_units; i++)
                SIM_attr_list_set_item(
                        &attr, i,
                        SIM_make_attr_uint64(flash_unit_size(flash, i)));
        return attr;
}

/* timing - obsolete */

static set_error_t
set_ignore_timing(conf_object_t *obj, attr_value_t *val)
{
        return Sim_Set_Ok;
}

static attr_value_t
get_ignore_timing(conf_object_t *obj)
{
        return SIM_make_attr_uint64(1);
}

static set_error_t
set_unit_erase_time(conf_object_t *obj, attr_value_t *val)
{
        return Sim_Set_Ok;
}

static attr_value_t
get_unit_erase_time(conf_object_t *obj)
{
        return SIM_make_attr_floating(0.0);
}


/* command-set settings */

static set_error_t
set_amd_ignore_cmd_address(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        flash->amd.ignore_cmd_address = !!SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_amd_ignore_cmd_address(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_uint64(flash->amd.ignore_cmd_address);
}

static set_error_t
set_strict_cmd_set(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        flash->strict_cmd_set = !!SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_strict_cmd_set(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_uint64(flash->strict_cmd_set);
}


/* storage-ram */

static set_error_t
set_storage_ram(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        conf_object_t *ram;
        const ram_interface_t *iface;

        ram = SIM_attr_object(*val);
        iface = SIM_C_GET_INTERFACE(ram, ram);
        if (!iface)
                return Sim_Set_Illegal_Value;

        if (flash->storage_ram_map_target)
                SIM_free_map_target(flash->storage_ram_map_target);

        flash->storage_ram = ram;
        flash->storage_ram_interface = iface;
        flash->storage_ram_map_target = SIM_new_map_target(flash->storage_ram,
                                                           NULL, NULL);
        return Sim_Set_Ok;
}

static attr_value_t
get_storage_ram(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_object(flash->storage_ram);
}


/* generic flash parameters */

static set_error_t
set_accept_smaller_reads(conf_object_t *obj, attr_value_t *val)
{
        return Sim_Set_Ok;
}

static attr_value_t
get_accept_smaller_reads(conf_object_t *obj)
{
        return SIM_make_attr_uint64(1);
}

static set_error_t
set_accept_smaller_writes(conf_object_t *obj, attr_value_t *val)
{
        return Sim_Set_Ok;
}

static attr_value_t
get_accept_smaller_writes(conf_object_t *obj)
{
        return SIM_make_attr_uint64(1);
}

static set_error_t
set_big_endian(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        flash->big_endian = !!SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_big_endian(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_uint64(flash->big_endian);
}

/* intel command set configuration */

static set_error_t
set_intel_chip_erase(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        flash->intel.chip_erase = SIM_attr_boolean(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_intel_chip_erase(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_boolean(flash->intel.chip_erase);
}

static set_error_t
set_intel_program_verify(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        flash->intel.program_verify = SIM_attr_boolean(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_intel_program_verify(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_boolean(flash->intel.program_verify);
}

static set_error_t
set_intel_write_buffer(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        flash->intel.write_buffer = !!SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_intel_write_buffer(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_uint64(flash->intel.write_buffer);
}

static set_error_t
set_intel_protection_program(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        flash->intel.protection_program = !!SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_intel_protection_program(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_uint64(flash->intel.protection_program);
}

static set_error_t
set_intel_configuration(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        flash->intel.configuration = !!SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_intel_configuration(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_uint64(flash->intel.configuration);
}

static set_error_t
set_intel_lock(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);

        int64 value = SIM_attr_integer(*val);
        if (value < 0 || value > 2)
                return Sim_Set_Illegal_Value;

        if (value == 2) {
                /* set all blocks to 01 locked, default value */
                for (int i = 0; i < flash_interleave(flash); i++)
                        for (int j = 0; j < flash->num_units; j++)
                                flash->chip[i].unit_data[j].lock_status = 0x1;
        }

        flash->intel.lock = value;
        return Sim_Set_Ok;
}

static attr_value_t
get_intel_lock(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        return SIM_make_attr_uint64(flash->intel.lock);
}

/* lock status */
static set_error_t
set_lock_status(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t inner_list;

        if (SIM_attr_list_size(*val) != flash_interleave(flash))
                return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++)
                if (SIM_attr_list_size(SIM_attr_list_item(*val, i))
                    != flash->num_units)
                        return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++) {
                inner_list = SIM_attr_list_item(*val, i);
                for (int j = 0; j < flash->num_units; j++)
                        flash->chip[i].unit_data[j].lock_status =
                                SIM_attr_integer(
                                        SIM_attr_list_item(inner_list, j));
        }

        return Sim_Set_Ok;
}

static attr_value_t
get_lock_status(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t inl, ret;

        ret = SIM_alloc_attr_list(flash_interleave(flash));

        for (int i = 0; i < flash_interleave(flash); i++) {
                inl = SIM_alloc_attr_list(flash->num_units);
                SIM_attr_list_set_item(&ret, i, inl);

                for (int j = 0; j < flash->num_units; j++)
                        SIM_attr_list_set_item(
                                &inl, j, SIM_make_attr_uint64(
                                        flash->
                                        chip[i].unit_data[j].lock_status));
        }

        return ret;
}

/* hardware lock status */
static set_error_t
set_hardware_lock_status(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);

        if (SIM_attr_list_size(*val) != flash_interleave(flash))
                return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++)
                if (SIM_attr_list_size(SIM_attr_list_item(*val, i))
                    != flash->num_units)
                        return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++) {
                attr_value_t inner_list = SIM_attr_list_item(*val, i);
                for (int j = 0; j < flash->num_units; j++)
                        flash->chip[i].unit_data[j].hardware_lock =
                                SIM_attr_integer(
                                        SIM_attr_list_item(inner_list, j));
        }

        return Sim_Set_Ok;
}

static attr_value_t
get_hardware_lock_status(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t ret = SIM_alloc_attr_list(flash_interleave(flash));

        for (int i = 0; i < flash_interleave(flash); i++) {
                attr_value_t inl =  SIM_alloc_attr_list(flash->num_units);
                SIM_attr_list_set_item(&ret, i, inl);

                for (int j = 0; j < flash->num_units; j++)
                        SIM_attr_list_set_item(
                                &inl, j, SIM_make_attr_uint64(
                                        flash->
                                        chip[i].unit_data[j].hardware_lock));
        }

        return ret;
}

/* unit status */
static set_error_t
set_unit_status(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t inner_list;

        if (SIM_attr_list_size(*val) != flash_interleave(flash))
                return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++)
                if (SIM_attr_list_size(SIM_attr_list_item(*val, i))
                    != flash->num_units)
                        return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++) {
                inner_list = SIM_attr_list_item(*val, i);
                for (int j = 0; j < flash->num_units; j++)
                        flash->chip[i].unit_data[j].status =
                                SIM_attr_integer(
                                        SIM_attr_list_item(inner_list, j));
        }

        return Sim_Set_Ok;
}

static attr_value_t
get_unit_status(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t ret = SIM_alloc_attr_list(flash_interleave(flash));

        for (int i = 0; i < flash_interleave(flash); i++) {
                attr_value_t inner_list
                        = SIM_alloc_attr_list(flash->num_units);
                SIM_attr_list_set_item(&ret, i, inner_list);

                for (int j = 0; j < flash->num_units; j++)
                        SIM_attr_list_set_item(
                                &inner_list, j,
                                SIM_make_attr_uint64(
                                        flash->chip[i].unit_data[j].status));
        }

        return ret;
}

/* ppb bits */
static set_error_t
set_unit_ppb_bits(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t inner_list;

        if (SIM_attr_list_size(*val) != flash_interleave(flash))
                return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++)
                if (SIM_attr_list_size(SIM_attr_list_item(*val, i))
                    != flash->num_units)
                        return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++) {
                inner_list = SIM_attr_list_item(*val, i);
                for (int j = 0; j < flash->num_units; j++)
                        flash->chip[i].unit_data[j].ppb =
                                SIM_attr_integer(
                                        SIM_attr_list_item(inner_list, j));
        }

        return Sim_Set_Ok;
}

static attr_value_t
get_unit_ppb_bits(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t ret = SIM_alloc_attr_list(flash_interleave(flash));

        for (int i = 0; i < flash_interleave(flash); i++) {
                attr_value_t inner_list
                        = SIM_alloc_attr_list(flash->num_units);
                SIM_attr_list_set_item(&ret, i, inner_list);

                for (int j = 0; j < flash->num_units; j++)
                        SIM_attr_list_set_item(
                                &inner_list, j,
                                SIM_make_attr_uint64(
                                        flash->chip[i].unit_data[j].ppb));
        }

        return ret;
}

/* dyb bits */
static set_error_t
set_unit_dyb_bits(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t inner_list;

        if (SIM_attr_list_size(*val) != flash_interleave(flash))
                return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++)
                if (SIM_attr_list_size(SIM_attr_list_item(*val, i))
                    != flash->num_units)
                        return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++) {
                inner_list = SIM_attr_list_item(*val, i);
                for (int j = 0; j < flash->num_units; j++)
                        flash->chip[i].unit_data[j].dyb =
                                SIM_attr_integer(
                                        SIM_attr_list_item(inner_list, j));
        }

        return Sim_Set_Ok;
}

static attr_value_t
get_unit_dyb_bits(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t ret = SIM_alloc_attr_list(flash_interleave(flash));

        for (int i = 0; i < flash_interleave(flash); i++) {
                attr_value_t inner_list
                        = SIM_alloc_attr_list(flash->num_units);
                SIM_attr_list_set_item(&ret, i, inner_list);

                for (int j = 0; j < flash->num_units; j++)
                        SIM_attr_list_set_item(
                                &inner_list, j,
                                SIM_make_attr_uint64(
                                        flash->chip[i].unit_data[j].dyb));
        }

        return ret;
}

/* chip mode */
static attr_value_t
get_chip_mode(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t ret = SIM_alloc_attr_list(flash_interleave(flash));

        for (int i = 0; i < flash_interleave(flash); i++)
                SIM_attr_list_set_item(
                        &ret, i,
                        SIM_make_attr_string(state_desc[flash->chip[i].mode]));
        return ret;
}

static fm_operation_t
find_mode_by_name(const char *s)
{
        for (int i = 0; i < FS_max; i++) {
                if (strcmp(state_desc[i], s) == 0)
                        return i;
        }

        return FS_unknown;
}

static set_error_t
set_chip_mode(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);

        if (SIM_attr_list_size(*val) != flash_interleave(flash))
                return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++)
                flash->chip[i].mode = find_mode_by_name(
                        SIM_attr_string(SIM_attr_list_item(*val, i)));

        return Sim_Set_Ok;
}


/* chip write buffer */
static attr_value_t
get_chip_write_buffer(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t ret = SIM_alloc_attr_list(flash_interleave(flash));

        for (int i = 0; i < flash_interleave(flash); i++) {
                attr_value_t value;
                if (flash->chip[i].write_buffer)
                        value = SIM_make_attr_data(
                                flash->chip[i].write_buffer_len,
                                flash->chip[i].write_buffer);
                else
                        value = SIM_make_attr_nil();
                SIM_attr_list_set_item(&ret, i, value);
        }

        return ret;
}

static set_error_t
set_chip_write_buffer(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);

        if (SIM_attr_list_size(*val) != flash_interleave(flash))
                return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++) {
                attr_value_t wb = SIM_attr_list_item(*val, i);
                MM_FREE(flash->chip[i].write_buffer);
                flash->chip[i].write_buffer = NULL;
                if (SIM_attr_is_data(wb)) {
                        flash->chip[i].write_buffer =
                                MM_MALLOC(SIM_attr_data_size(wb), uint8);
                        memcpy(flash->chip[i].write_buffer,
                               SIM_attr_data(wb),
                               SIM_attr_data_size(wb));
                        flash->chip[i].write_buffer_len
                                = SIM_attr_data_size(wb);
                }
        }

        return Sim_Set_Ok;
}

/* chip_write_buffer_start_address */
static attr_value_t
get_chip_write_buffer_start_address(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t ret = SIM_alloc_attr_list(flash_interleave(flash));

        for (int i = 0; i < flash_interleave(flash); i++)
                SIM_attr_list_set_item(&ret, i, SIM_make_attr_uint64(
                                               flash->chip[i].start_address));
        return ret;
}

static set_error_t
set_chip_write_buffer_start_address(conf_object_t *obj,  attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);

        if (SIM_attr_list_size(*val) != flash_interleave(flash))
                return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++)
                flash->chip[i].start_address =
                        SIM_attr_integer(SIM_attr_list_item(*val, i));

        return Sim_Set_Ok;
}

/* chip_write_buffer_current_count */
static attr_value_t
get_chip_write_buffer_current_count(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t ret = SIM_alloc_attr_list(flash_interleave(flash));

        for (int i = 0; i < flash_interleave(flash); i++)
                SIM_attr_list_set_item(&ret, i, SIM_make_attr_uint64(
                                               flash->chip[i].current_count));
        return ret;
}

static set_error_t
set_chip_write_buffer_current_count(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);

        if (SIM_attr_list_size(*val) != flash_interleave(flash))
                return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++)
                flash->chip[i].current_count =
                        SIM_attr_integer(SIM_attr_list_item(*val, i));

        return Sim_Set_Ok;
}

/* amd lock register */
static attr_value_t
get_amd_lock_register(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t ret = SIM_alloc_attr_list(flash_interleave(flash));

        for (int i = 0; i < flash_interleave(flash); i++)
                SIM_attr_list_set_item(
                        &ret, i, SIM_make_attr_uint64(
                                flash->chip[i].amd.lock_register));
        return ret;
}

static set_error_t
set_amd_lock_register(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);

        if (SIM_attr_list_size(*val) != flash_interleave(flash))
                return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++)
                flash->chip[i].amd.lock_register =
                        SIM_attr_integer(SIM_attr_list_item(*val, i));

        return Sim_Set_Ok;
}

/* amd PPB lock bit */
static attr_value_t
get_amd_ppb_lock_bit(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        attr_value_t ret = SIM_alloc_attr_list(flash_interleave(flash));

        for (int i = 0; i < flash_interleave(flash); i++)
                SIM_attr_list_set_item(
                        &ret, i, SIM_make_attr_uint64(
                                flash->chip[i].amd.ppb_lock_bit));
        return ret;
}

static set_error_t
set_amd_ppb_lock_bit(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);

        if (SIM_attr_list_size(*val) != flash_interleave(flash))
                return Sim_Set_Illegal_Value;

        for (int i = 0; i < flash_interleave(flash); i++)
                flash->chip[i].amd.ppb_lock_bit =
                        SIM_attr_integer(SIM_attr_list_item(*val, i));

        return Sim_Set_Ok;
}

/* timing_model */
static attr_value_t
get_timing_model(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);

        attr_value_t ret = SIM_alloc_attr_dict(
                total_timing_model_states_supported);
        int j = 0;
        for (int i = 0; i < FS_max; i++) {
                if (supports_time_model[i]) {
                        SIM_attr_dict_set_item(
                                &ret, j,
                                SIM_make_attr_string(state_desc[i]),
                                SIM_make_attr_floating(flash->time_model[i]));
                        j++;
                }
        }
        return ret;
}

static set_error_t
set_timing_model(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);

        /* Check types */
        for (int i = 0; i < SIM_attr_dict_size(*val); i++) {
                /* Key */
                if (!SIM_attr_is_string(SIM_attr_dict_key(*val, i)))
                        return Sim_Set_Illegal_Type;

                /* Value */
                if (!SIM_attr_is_floating(SIM_attr_dict_value(*val, i)))
                        return Sim_Set_Illegal_Type;
        }

        /* Commit */
        for (int i = 0; i < SIM_attr_dict_size(*val); i++) {
                const char *key = SIM_attr_string(SIM_attr_dict_key(*val, i));
                double value = SIM_attr_floating(SIM_attr_dict_value(*val, i));
                fm_operation_t state = find_mode_by_name(key);

                if (state == FS_unknown)
                        return Sim_Set_Illegal_Value;

                if (!supports_time_model[state])
                        return Sim_Set_Illegal_Value;

                flash->time_model[state] = value;
        }
        return Sim_Set_Ok;
}

/* other attributes */
static set_error_t
set_reset(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);

        if (SIM_attr_integer(*val))
                reset(flash);

        return Sim_Set_Ok;
}

static set_error_t
set_busy_targets(conf_object_t *obj, attr_value_t *val)
{
        flash_memory_t *flash = from_obj(obj);

        if (SIM_attr_list_size(*val) != flash_interleave(flash))
                return Sim_Set_Illegal_Value;

        for (int i = 0; i < SIM_attr_list_size(*val); i++) {
                attr_value_t item = SIM_attr_list_item(*val, i);
                conf_object_t *dst;
                const char *pin;
                const signal_interface_t *iface;

                if (SIM_attr_is_nil(item)) {
                        dst = NULL;
                        pin = NULL;
                        iface = NULL;
                } else if (SIM_attr_is_list(item)) {
                        dst = SIM_attr_object(SIM_attr_list_item(item, 0));
                        pin = SIM_attr_string(SIM_attr_list_item(item, 1));
                        iface = SIM_C_GET_PORT_INTERFACE(dst, signal, pin);
                        if (!iface)
                                return Sim_Set_Interface_Not_Found;
                } else {
                        dst = SIM_attr_object(item);
                        pin = NULL;
                        iface = SIM_C_GET_INTERFACE(dst, signal);
                        if (!iface)
                                return Sim_Set_Interface_Not_Found;
                }
                flash->chip[i].busy.obj = dst;
                flash->chip[i].busy.pin = pin ? MM_STRDUP(pin) : NULL;
                flash->chip[i].busy.iface = iface;
        }

        return Sim_Set_Ok;
}

static attr_value_t
get_busy_targets(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);

        attr_value_t ret = SIM_alloc_attr_list(flash_interleave(flash));

        for (int i = 0; i < flash_interleave(flash); i++) {
                chip_t *chip = &flash->chip[i];
                attr_value_t a;
                if (chip->busy.pin) {
                        a = SIM_make_attr_list(2,
                               SIM_make_attr_object(chip->busy.obj),
                               SIM_make_attr_string(chip->busy.pin));
                } else {
                        a = SIM_make_attr_object(chip->busy.obj);
                }
                SIM_attr_list_set_item(&ret, i, a);
        }

        return ret;
}

/*
   Generic event function to take a chip out of a function which must take
   some time to execute. Causes the chip to go back to read-array mode,
   and lower the busy signal.
*/
void
time_delayed_operation_done(conf_object_t *obj, void *data)
{
        flash_memory_t *flash = from_obj(obj);
        unsigned chip_index = (uintptr_t)data;

        update_state(flash, chip_index, FS_read_array);
        if (flash->chip[chip_index].busy.obj) {
                flash->chip[chip_index].busy.iface->signal_lower(
                        flash->chip[chip_index].busy.obj);
        }
}

void
post_busy_event(flash_memory_t *flash, unsigned chip_index, double delay)
{
        SIM_event_post_time(SIM_object_clock(to_obj(flash)),
                            event_operation_done,
                            to_obj(flash),
                            delay,
                            (void*)(uintptr_t)chip_index);

        if (flash->chip[chip_index].busy.obj) {
                flash->chip[chip_index].busy.iface->signal_raise(
                        flash->chip[chip_index].busy.obj);
        }
}

static attr_value_t
event_get_operation_done(conf_object_t *obj, lang_void *data)
{
        return SIM_make_attr_uint64((int64)(uintptr_t)data);
}

static lang_void *
event_set_operation_done(conf_object_t *obj, attr_value_t value)
{
        return (void *)(uintptr_t)SIM_attr_integer(value);
}

static char *
event_describe_operation_done(conf_object_t *obj, lang_void *data)
{
        strbuf_t s = sb_newf("operation done - %d", (int)(intptr_t)data);
        return sb_detach(&s);
}

static void
reset_raised(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        SIM_LOG_INFO(3, to_obj(flash), 0, "RESET raised");
        reset(flash);
}

static void
reset_lowered(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        SIM_LOG_INFO(3, to_obj(flash), 0, "RESET lowered");
}

static void
port_reset_raised(conf_object_t *obj)
{
        reset_raised(SIM_port_object_parent(obj));
}

static void
port_reset_lowered(conf_object_t *obj)
{
        reset_lowered(SIM_port_object_parent(obj));
}

static void
wr_enabled_true(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        SIM_LOG_INFO(3, to_obj(flash), 0,
                     "The lowest sector was Write enabled");
        /* Either the highest or lowest sector is unlocked (device specific) */
        unit_data_t *unit = &flash->chip[0].unit_data[0];
        unit->ppb = 1;
}

static void
wr_enabled_false(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);
        SIM_LOG_INFO(3, to_obj(flash), 0,
                     "The lowest sector was Write protected");
        /* Either the highest or lowest sector is locked (device specific) */
        unit_data_t *unit = &flash->chip[0].unit_data[0];
        unit->ppb = 0;
}

static void
port_wr_enabled_true(conf_object_t *obj)
{
        wr_enabled_true(SIM_port_object_parent(obj));
}

static void
port_wr_enabled_false(conf_object_t *obj)
{
        wr_enabled_false(SIM_port_object_parent(obj));
}

/* class support */

static conf_object_t *
fm_alloc_object(conf_class_t *cls)
{
        flash_memory_t *flash = MM_ZALLOC(1, flash_memory_t);
        return to_obj(flash);
}

static void *
fm_init_object(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);

        flash->bus_width_in_bits = 32;
        flash->bus_width_in_bytes = 4;
        flash->interleave_bits = 0;

        /* default for Intel Strataflash® */
        flash->wb_max_len_in_bytes = 32;

        flash->device_id_len = 1;
        flash->device_id = MM_ZALLOC(flash->device_id_len, uint32);

        flash->io_map_target = SIM_new_map_target(obj, "io", NULL);

        flash->wp = 0;

        return flash;
}

static void
fm_finalize_instance(conf_object_t *obj)
{
        flash_memory_t *flash = from_obj(obj);

        attr_value_t attr = SIM_get_attribute(flash->storage_ram, "image");
        if (!SIM_attr_is_object(attr)) {
                SIM_LOG_ERROR(to_obj(flash), 0,
                              "no image object found in RAM object");
                return;
        }
        conf_object_t *image = SIM_attr_object(attr);
        const image_interface_t *iface = SIM_C_GET_INTERFACE(image, image);
        if (!iface) {
                SIM_LOG_ERROR(to_obj(flash), 0,
                              "no image interface found in image object");
                return;
        }

        flash->storage_image = image;
        flash->storage_image_interface = iface;
        /* flash memory is persistent */
        flash->storage_image_interface->set_persistent(flash->storage_image);

        if (!valid_setup(flash)) {
                SIM_LOG_ERROR(to_obj(flash), 0,
                              "the setup doesn't seem to be correct");
                return;
        }

        if (intel_cmd_set(flash))
                intel_finalize(flash);
        else if (amd_cmd_set(flash))
                amd_finalize(flash);
        else
                SIM_LOG_UNIMPLEMENTED(1, to_obj(flash), 0,
                                      "unimplemented command set");
}

void
init_local()
{
        static const class_info_t info = {
                .alloc = fm_alloc_object,
                .init = fm_init_object,
                .finalize = fm_finalize_instance,
                .short_desc = "model of generic flash memory",
                .description =
                "The generic-flash-memory class simulates different types of"
                " flash-memory depending on which attributes are set.\n"
                " Refer to"
                " [simics]/src/extensions/apps-python/flash_memory.py for a"
                " complete description of the features implemented and"
                " the flash chips that are pre-configured.\n\n"
                "<dl><dt>Limitations</dt>"
                "<dd><ul>"
                "  <li>Many vendor-specific commands are not implemented.</li>"
                "  <li>Erase suspend will complete the erase, and resume"
                "      will then simply be ignored.</li>"
                "</ul></dd></dl>"
        };

        conf_class_t *class = SIM_create_class(DEVICE_NAME, &info);

        /* register an alias for the former 'new-flash-memory' name */
        SIM_register_class_alias("new-flash-memory", DEVICE_NAME);
        SIM_log_register_groups(class, fm_log_groups);

        /* register the translator_interface_t */
        static const translator_interface_t ti = {
                .translate = nfm_translate
        };
        SIM_REGISTER_INTERFACE(class, translator, &ti);

        conf_class_t *io_mem = SIM_register_simple_port(class, "port.io",
                                                        NULL);
        static const io_memory_interface_t port_ioi = {
                .operation = port_nfm_operation
        };
        SIM_REGISTER_INTERFACE(io_mem, io_memory, &port_ioi);

        static const io_memory_interface_t ioi = {
                .operation = nfm_operation
        };
        SIM_REGISTER_PORT_INTERFACE(class, io_memory, &ioi, "io", NULL);

        event_operation_done = SIM_register_event("operation done",
                                                  class,
                                                  Sim_EC_No_Flags,
                                                  time_delayed_operation_done,
                                                  NULL,
                                                  event_get_operation_done,
                                                  event_set_operation_done,
                                                  event_describe_operation_done);

        /* Reset signal */
        conf_class_t *reset = SIM_register_simple_port(class, "port.Reset",
                                                       "Reset the flash");
        static const signal_interface_t port_reset_iface = {
                .signal_raise = port_reset_raised,
                .signal_lower = port_reset_lowered
        };
        SIM_REGISTER_INTERFACE(reset, signal, &port_reset_iface);

        static const signal_interface_t reset_iface = {
                .signal_raise = reset_raised,
                .signal_lower = reset_lowered
        };
        SIM_REGISTER_PORT_INTERFACE(class, signal, &reset_iface,
                                    "Reset", "Resets the flash");

        conf_class_t *wren = SIM_register_simple_port(class, "port.wren",
                                                      "Enable/Disable Write to"
                                                      " flash sector");
        static const signal_interface_t port_wren_iface = {
                .signal_raise = port_wr_enabled_false,
                .signal_lower = port_wr_enabled_true
        };
        SIM_REGISTER_INTERFACE(wren, signal, &port_wren_iface);

        static const signal_interface_t wren_iface =
                { .signal_raise = wr_enabled_false,
                  .signal_lower = wr_enabled_true };
        SIM_REGISTER_PORT_INTERFACE(class, signal, &wren_iface, "wren",
                                    "Enable/Disable Write to flash sector");

        /* Write protect signal */
        conf_class_t *wp = SIM_register_simple_port(class, "port.wp",
                                                      "Hardware signal,"
                                                      " Enable/Disable Write");
        static const signal_interface_t port_wp_iface = {
                .signal_raise = port_wp_enable,
                .signal_lower = port_wp_disable
        };
        SIM_REGISTER_INTERFACE(wp, signal, &port_wp_iface);

        static const signal_interface_t wp_iface =
                { .signal_raise = wp_enable,
                  .signal_lower = wp_disable};
        SIM_REGISTER_PORT_INTERFACE(class, signal, &wp_iface, "wp",
                                    "Hardware signal, Enable/Disable Write");

        SIM_register_attribute(
                class, "wp",
                get_wp_flag,
                set_wp_flag,
                Sim_Attr_Optional | Sim_Attr_Internal,
                "b",
                "Hardware write protection.");

        /* cfi support */
        SIM_register_attribute(
                class, "command_set",
                get_command_set,
                set_command_set,
                Sim_Attr_Optional,
                "i",
                "If no CFI structure is provided, this attribute should be "
                "set to indicate the command-set to use. "
                "Default is 0 (invalid command-set).");

        SIM_register_attribute(
                class, "cfi_query",
                get_cfi_query_struct,
                set_cfi_query_struct,
                Sim_Attr_Optional,
                "n|d|[i+]",
                "CFI query structure (if the device is CFI compatible). "
                "Default is none (device is not CFI compatible).");

        /* generic information */
        SIM_register_attribute(
                class, "device_id",
                get_device_id,
                set_device_id,
                Sim_Attr_Optional,
                "i|[i+]",
                "Device ID/code as used in Intel identifier codes "
                "and AMD autoselect mode. Default is 0.");

        SIM_register_attribute(
                class, "manufacturer_id",
                get_manufacturer_id,
                set_manufacturer_id,
                Sim_Attr_Optional,
                "i",
                "Manufacturer ID/code as used in Intel identifier codes "
                "and AMD autoselect mode. Default is 0.");

        SIM_register_attribute(
                class, "write_buffer_size",
                get_write_buffer_size,
                set_write_buffer_size,
                Sim_Attr_Optional,
                "i",
                "Write buffer size *in bytes* for write buffer commands. "
                "Default is 32 (standard value for Intel Strataflash®).");

        /* device layout */
        SIM_register_attribute(
                class, "interleave",
                get_interleave,
                set_interleave,
                Sim_Attr_Required,
                "i",
                "Interleave (number of parallel flash memory chips).");

        SIM_register_attribute(
                class, "bus_width",
                get_bus_width,
                set_bus_width,
                Sim_Attr_Required,
                "i",
                "Total width (in bits) of the data path connected to the "
                "flash device.");

        SIM_register_attribute(
                class, "max_chip_width",
                get_max_chip_width,
                set_max_chip_width,
                Sim_Attr_Optional,
                "i",
                "Maximum data width (for example, specified as 16 "
                "for a x8/x16 capable device).");

        /* chip layout */
        SIM_register_attribute(
                class, "unit_size",
                get_unit_size,
                set_unit_size,
                Sim_Attr_Required,
                "[i+]",
                "A list of block/sector sizes.");

        /* timing */
        SIM_register_attribute(
                class, "ignore_timing",
                get_ignore_timing,
                set_ignore_timing,
                Sim_Attr_Optional,
                "i",
                "Obsolete attribute since timing is not modeled. "
                "Kept for backward compatibility only.");

        SIM_register_attribute(
                class, "unit_erase_time",
                get_unit_erase_time,
                set_unit_erase_time,
                Sim_Attr_Optional,
                "f",
                "Obsolete attribute since timing is not modeled. "
                "Kept for backward compatibility only.");

        /* command-set settings */
        SIM_register_attribute(
                class, "strict_cmd_set",
                get_strict_cmd_set,
                set_strict_cmd_set,
                Sim_Attr_Optional,
                "i",
                "If set to 1, warnings that the command-set is misused "
                "become errors. Default is 0.");

        /* storage ram */
        SIM_register_attribute(
                class, "storage_ram",
                get_storage_ram,
                set_storage_ram,
                Sim_Attr_Required,
                "o",
                "RAM object providing the backing store area.");

        /* generic flash parameters */
        SIM_register_attribute(
                class, "accept_smaller_reads",
                get_accept_smaller_reads,
                set_accept_smaller_reads,
                Sim_Attr_Pseudo,
                "i",
                "Obsolete, do not use.");

        SIM_register_attribute(
                class, "accept_smaller_writes",
                get_accept_smaller_writes,
                set_accept_smaller_writes,
                Sim_Attr_Pseudo,
                "i",
                "Obsolete, do not use.");

        SIM_register_attribute(
                class, "big_endian",
                get_big_endian,
                set_big_endian,
                Sim_Attr_Optional,
                "i",
                "If 1, the flash device will behave as a big endian device. "
                "If 0, it will behave as a little endian device. "
                "Default is 0.");


        /* intel command-set configuration */
        SIM_register_attribute(
                class, "intel_chip_erase",
                get_intel_chip_erase,
                set_intel_chip_erase,
                Sim_Attr_Optional,
                "b",
                "If TRUE, the flash device supports Intel chip erase command"
                " operations. If FALSE, Intel chip erase command is flagged as"
                " error. Default is FALSE.");

        SIM_register_attribute(
                class, "intel_program_verify",
                get_intel_program_verify,
                set_intel_program_verify,
                Sim_Attr_Optional,
                "b",
                "If TRUE, the flash device supports Intel program verify"
                " command operations. If FALSE, Intel program verify command"
                " is flagged as error. Default is FALSE.");

        SIM_register_attribute(
                class, "intel_write_buffer",
                get_intel_write_buffer,
                set_intel_write_buffer,
                Sim_Attr_Optional,
                "i",
                "If 1, the flash device supports Intel write buffer "
                "operations. If 0, Intel write buffer operations are ignored."
                " Default is 0.");

        SIM_register_attribute(
                class, "intel_protection_program",
                get_intel_protection_program,
                set_intel_protection_program,
                Sim_Attr_Optional,
                "i",
                "If 1, the flash device supports Intel protection program "
                "operations. "
                "If 0, Intel protection program operations are ignored. "
                "Default is 0.");

        SIM_register_attribute(
                class, "intel_configuration",
                get_intel_configuration,
                set_intel_configuration,
                Sim_Attr_Optional ,
                "i",
                "If 1, the flash device supports Intel configuration "
                "operations. If 0, Intel configuration operations are "
                "ignored. Default is 0.");

        SIM_register_attribute(
                class, "intel_lock",
                get_intel_lock,
                set_intel_lock,
                Sim_Attr_Optional,
                "i",
                "If 2, the flash device supports advanced "
                "lock/unlock/lock down operations. "
                "If 1, the flash device supports simple "
                "lock/unlock all operations. "
                "If 0, lock operations are ignored. Default is 0.");

        /* AMD command-set configuration */
        SIM_register_attribute(
                class, "amd_ignore_cmd_address",
                get_amd_ignore_cmd_address,
                set_amd_ignore_cmd_address,
                Sim_Attr_Optional,
                "i",
                "If 1, the address will be ignored when parsing AMD commands. "
                "Default is 0.");

        /* Unit states */
        SIM_register_attribute(
                class, "lock_status",
                get_lock_status,
                set_lock_status,
                Sim_Attr_Optional,
                "[[i*]*]",
                "Lock status for all units.");

        SIM_register_attribute(
                class, "hardware_lock_status",
                get_hardware_lock_status,
                set_hardware_lock_status,
                Sim_Attr_Optional,
                "[[i*]*]",
                "Hardware lock status for all units (for Intel advanced lock "
                "system).");

        SIM_register_attribute(
                class, "unit_status",
                get_unit_status,
                set_unit_status,
                Sim_Attr_Optional,
                "[[i*]*]",
                "Status for all units.");

        SIM_register_attribute(
                class, "ppb_bits",
                get_unit_ppb_bits,
                set_unit_ppb_bits,
                Sim_Attr_Optional | Sim_Attr_Persistent,
                "[[i*]*]",
                "AMD non-volatile PPB section bits.");

        SIM_register_attribute(
                class, "dyb_bits",
                get_unit_dyb_bits,
                set_unit_dyb_bits,
                Sim_Attr_Optional,
                "[[i*]*]",
                "AMD volatile (dynamic) section protection bits.");

        /* Chip states */
        SIM_register_attribute(
                class, "chip_mode",
                get_chip_mode,
                set_chip_mode,
                Sim_Attr_Optional,
                "[s*]",
                "Current state for all chips.");

        SIM_register_attribute(
                class, "chip_write_buffer",
                get_chip_write_buffer,
                set_chip_write_buffer,
                Sim_Attr_Optional,
                "[d|n*]",
                "Current write buffer for all chips.");

        SIM_register_attribute(
                class, "chip_write_buffer_start_address",
                get_chip_write_buffer_start_address,
                set_chip_write_buffer_start_address,
                Sim_Attr_Optional,
                "[i*]",
                "Current write buffer start address for all chips.");

        SIM_register_attribute(
                class, "chip_write_buffer_current_count",
                get_chip_write_buffer_current_count,
                set_chip_write_buffer_current_count,
                Sim_Attr_Optional,
                "[i*]",
                "Current write buffer count for all chips.");

        SIM_register_attribute(
                class, "amd_lock_register",
                get_amd_lock_register,
                set_amd_lock_register,
                Sim_Attr_Optional | Sim_Attr_Persistent,
                "[i*]",
                "AMD lock register contents.");

        SIM_register_attribute(
                class, "amd_ppb_lock_bit",
                get_amd_ppb_lock_bit,
                set_amd_ppb_lock_bit,
                Sim_Attr_Optional | Sim_Attr_Persistent,
                "[i*]",
                "AMD PPB lock bit");

        SIM_register_attribute(
                class, "timing_model",
                get_timing_model,
                set_timing_model,
                Sim_Attr_Optional | Sim_Attr_Internal,
                "D",
                "Associates a flash state/operation with a time. "
                "The flash will remain in this state the given time allowing "
                "a more strict time model to be simulated. Sometimes flash "
                "drivers requires that an operation takes some time to "
                "complete for the software to work correctly.");

        /* Other attributes */
        SIM_register_attribute(
                class, "reset",
                NULL,
                set_reset,
                Sim_Attr_Pseudo,
                "i",
                "Set to 1 in order to reset the device.");

        /* Outgoing pins */
        SIM_register_attribute(
                class, "busy_signal_targets",
                get_busy_targets,
                set_busy_targets,
                Sim_Attr_Optional,
                "[n|o|[os]*]",
                "(dst_object, dst_signal)* The destination device and signal "
                "name to connect the busy signal of the chips to. The "
                "destinations "
                "should implement the <iface>" SIGNAL_INTERFACE "</iface> "
                "interface. Without a timing model, the device will "
                "never raise the busy signal.");

        total_timing_model_states_supported = 0;
        for (int i = 0; i < FS_max; i++) {
                if (supports_time_model[i])
                        total_timing_model_states_supported++;
        }
}
