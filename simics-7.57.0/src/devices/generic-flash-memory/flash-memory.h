/*
 flash-memory.h

  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#ifndef FLASH_MEMORY_H
#define FLASH_MEMORY_H

#include <simics/device-api.h>

#include <simics/model-iface/image.h>
#include <simics/base/map-target.h>

#include <simics/devs/ram.h>
#include <simics/devs/signal.h>
#if defined(__cplusplus)
extern "C" {
#endif

enum {
        FS_Log_Read           = 0x01, /* read operations on flash */
        FS_Log_Write          = 0x02, /* write operations on flash */
        FS_Log_Command        = 0x04, /* commands received */
        FS_Log_Lock           = 0x08, /* lock commands */
        FS_Log_Erase          = 0x10, /* erase commands */
        FS_Log_State          = 0x20, /* state changes */
        FS_Log_Write_Buffer   = 0x40, /* write buffer commands */
        FS_Log_CFI            = 0x80, /* CFI operations */
        FS_Log_Other          = 0x100, /* misc. */
        FS_Log_Max            = 9
};


/*
   IMPORTANT:

   The name string of each state is used for checkpointing purposes. If you
   change one, keep the old one as an alias so that older checkpoints will
   still load properly.
 */
#define FOR_ALL_FLASH_STATE(op)                                               \
    op(0, FS_unknown,                       "Unknown"),                       \
    op(0, FS_unimplemented,                 "Unimplemented"),                 \
    op(0, FS_read_array,                    "Read-Array"),                    \
    op(0, FS_cfi_query,                     "CFI Query"),                     \
                                                                              \
    op(0, FS_write_buffer_size,             "Write Buffer Size"),             \
    op(0, FS_write_buffer_gather,           "Write Buffer Gather"),           \
    op(0, FS_write_buffer_confirm,          "Write Buffer Confirm"),          \
    op(1, FS_write_buffer_in_progress,      "Write Buffer In Progress"),      \
    op(1, FS_chip_erase_in_progress,        "Chip Erase In Progress"),        \
                                                                              \
    op(0, FS_amd_unlock1,                   "AMD Command Cycle 1"),           \
    op(0, FS_amd_unlock2,                   "AMD Command Cycle 2"),           \
    op(0, FS_amd_autoselect,                "AMD Autoselect"),                \
    op(0, FS_amd_erase3,                    "AMD Erase Cycle 3"),             \
    op(0, FS_amd_erase4,                    "AMD Erase Cycle 4"),             \
    op(0, FS_amd_erase5,                    "AMD Erase Cycle 5"),             \
    op(1, FS_amd_erase_in_progress,         "AMD Erase In Progress"),         \
    op(0, FS_amd_program,                   "AMD Program"),                   \
    op(0, FS_amd_program_pending,           "AMD Program Pending"),           \
    op(0, FS_amd_unlock_bypass,             "AMD Unlock Bypass"),             \
    op(0, FS_amd_unlock_bypass_program,     "AMD Unlock Bypass Program"),     \
    op(0, FS_amd_unlock_bypass_reset,       "AMD Unlock Bypass Reset"),       \
    op(0, FS_amd_unlock_bypass_erase,       "AMD Unlock Bypass Erase"),       \
    op(0, FS_amd_unlock_bypass_command1,    "AMD Unlock Bypass Command Cycle 1"), \
    op(0, FS_amd_unlock_bypass_command2,    "AMD Unlock Bypass Command Cycle 2"), \
                                                                                \
    op(0, FS_bypass_write_buffer_size,      "AMD Unlock Bypass Write Buffer Size"),               \
    op(0, FS_bypass_write_buffer_gather,    "AMD Unlock Bypass Write Buffer Gather"),             \
    op(0, FS_bypass_write_buffer_confirm,   "AMD Unlock Bypass Write Buffer Confirm"),            \
    op(1, FS_bypass_write_buffer_in_progress, "AMD Unlock Bypass Write Buffer In Progress"),      \
    op(1, FS_bypass_chip_erase_in_progress, "AMD Unlock Bypass Chip Erase In Progress"),          \
    op(1, FS_bypass_erase_in_progress,      "AMD Unlock Bypass Sector Erase In Progress"),          \
                                                                              \
    op(0, FS_amd_lock_register_command_set, "AMD Lock Register Command Set"), \
    op(0, FS_amd_lock_register_bits,        "AMD Lock Register Bits"),        \
    op(0, FS_amd_lock_register_exit,        "AMD Lock Register Command Set Exit"),\
    op(0, FS_amd_non_volatile_command_set,  "AMD Non-Volatile Command Set"),  \
    op(0, FS_amd_non_volatile_program,      "AMD Non-Volatile Program PPB"),  \
    op(0, FS_amd_non_volatile_erase,        "AMD Non-Volatile Erase PPB"),    \
    op(0, FS_amd_non_volatile_exit,         "AMD Non-Volatile Command Exit"), \
    op(0, FS_amd_ppb_lock_command_set,      "AMD PPB Lock Command Set"),      \
    op(0, FS_amd_ppb_lock_program,          "AMD PPB Lock Program"),          \
    op(0, FS_amd_ppb_lock_exit,             "AMD PPB Lock Command Set Exit"), \
    op(0, FS_amd_volatile_command_set,      "AMD Volatile Sector Protection Command Set"),    \
    op(0, FS_amd_volatile_write,            "AMD Volatile Sector Protection Program DYB"),    \
    op(0, FS_amd_volatile_exit,             "AMD Volatile Sector Protection Command Exit"),   \
                                                                              \
    op(0, FS_intel_read_identifier_codes,   "Intel Read-Config"),             \
    op(0, FS_intel_read_status,             "Intel Read-Status"),             \
    op(0, FS_intel_block_erase,             "Intel Block Erase"),             \
    op(0, FS_intel_word_program,            "Intel Program Word"),            \
    op(0, FS_intel_lock_setup,              "Intel Lock Setup"),              \
    op(0, FS_intel_lock_command_error,      "Intel Lock Command Error"),      \
    op(0, FS_intel_lock_command_done,       "Intel Lock Command Done")

#define GET_FIRST_ELEMENT(a,b,c) a
#define GET_SECOND_ELEMENT(a,b,c) b
#define GET_THIRD_ELEMENT(a,b,c) c

typedef enum {
        FOR_ALL_FLASH_STATE(GET_SECOND_ELEMENT),
        FS_max
} fm_operation_t;

extern const char *const state_desc[];
extern event_class_t *event_operation_done;

typedef enum {
        Intel_Cmd_Block_Lock,
        Intel_Cmd_Block_Unlock,
        Intel_Cmd_Block_Lock_Down,
        Intel_Cmd_Hardware_WP_Up,
        Intel_Cmd_Hardware_WP_Down
} intel_cmd_lock_operation_t;

typedef struct {
        /* byte status to return for status inquiry */
        uint8 status;
        uint8 lock_status;                   /* generic lock system */
        bool hardware_lock;                 /* intel advanced lock */
        bool ppb;                           /* amd Persistent Protection Bit */
        bool dyb;                           /* amd Dynamic Protection Bit */
} unit_data_t;

typedef struct {
        /* current mode in state machine */
        fm_operation_t mode;

        /* buffer used for write-buffer commands */
        uint8 *write_buffer;
        int    write_buffer_len;

        /* start address for write buffer  */
        uint64 start_address;

        /* current count for write buffer */
        uint32 current_count;

        unit_data_t *unit_data;

        struct {
                /* Connection for busy pin */
                conf_object_t *obj;
                const char* pin;
                const signal_interface_t *iface;
        } busy;

        struct {
                uint32 lock_register;
                bool ppb_lock_bit;
        } amd;
} chip_t;

typedef struct flash_memory {

        conf_object_t obj;

        /* cfi support */
        uint8 *  cfi_query_struct;
        unsigned cfi_query_size;

        /* generic information */
        unsigned command_set;   /* set from cfi struct */
        uint32 *device_id;      /* device id */
        unsigned device_id_len; /* how many integers in device id */

        uint32 manufacturer_id;

        unsigned wb_max_len_in_bytes; /* maximum length for write buffer (in
                                         bytes!) */
        /* device layout */
        unsigned interleave_bits; /* log2(interleave factor) i.e., num_chips */

        unsigned bus_width_in_bits;
        unsigned bus_width_in_bytes; /* computed */

        unsigned chip_width_in_bits;  /* computed */
        unsigned chip_width_in_bytes; /* computed */

        uint64 chip_mask;        /* computed */

        unsigned max_chip_width_in_bits;
        unsigned max_chip_width_in_bytes; /* computed */

        /* chip layout */
        bool uniform_units;      /* computed */
        unsigned num_units;          /* computed */
        unsigned *unit_bits;    /* array[num_units] of log2(unit size) */

        chip_t *chip;           /* chip information */

        /* command-set settings */
        bool strict_cmd_set;

        struct {
                bool ignore_cmd_address;
        } amd;

        /* intel specific parameters */
        struct {
                bool write_buffer;
                bool chip_erase;
                bool protection_program;
                bool program_verify;
                bool configuration;
                int lock;
        } intel;

        /* storage ram support */
        conf_object_t            *storage_ram;
        const ram_interface_t    *storage_ram_interface;
        conf_object_t            *storage_image;
        const image_interface_t  *storage_image_interface;
        map_target_t             *storage_ram_map_target;
        map_target_t             *io_map_target;

        /* generic flash parameters */
        bool big_endian;     /* make the flash behave as a big-endian device */

        /* translator has provided a direct RAM mapping */
        bool has_translated_to_ram;

        /* optimization state */
        struct {
                bool same_state;   /* set to true before operation if all the
                                      chips are in the same state */
                bool bus_size;     /* set to true if the transaction is
                                      matching the flash bus size */
                bool bus_aligned;  /* set to true if the transaction is aligned
                                      with the flash bus */
                bool same_value;   /* set to true before write if all the chips
                                      will receive the same value */
                uint8 *full_value; /* value written to the whole flash
                                      system */
                bool done;         /* set to true by the first chip doing
                                      a fully optimized operation */
        } opt_op;

        /* lock system */
        int wp;                 /* write protection pin */

        double time_model[FS_max];
} flash_memory_t;

static inline flash_memory_t *
from_obj(conf_object_t *obj)
{
        return (flash_memory_t *)obj;
}

static inline conf_object_t *
to_obj(flash_memory_t *flash)
{
        return &flash->obj;
}

FORCE_INLINE unsigned
flash_interleave(flash_memory_t *flash)
{
        return 1 << flash->interleave_bits;
}

FORCE_INLINE unsigned
flash_unit_size(flash_memory_t *flash, unsigned index)
{
        return 1 << flash->unit_bits[index];
}

FORCE_INLINE uint64
get_offset_in_chip(flash_memory_t *flash,
                                       uint64 offset_in_flash)
{
        return offset_in_flash >> flash->interleave_bits;
}

/* return whether the optimized operation was already performed (and therefore
   can be skipped now) */
FORCE_INLINE bool
opt_op_done(flash_memory_t *flash)
{
        return flash->opt_op.done;
}

/* return whether a trigger operation can be optimized. A trigger operation
   requires both the chip states and the value written to the chips to be
   identical for all chips (write-buffer, for example) */
FORCE_INLINE bool
opt_trigger_allowed(flash_memory_t *flash)
{
        return flash->opt_op.bus_size && flash->opt_op.bus_aligned
                && flash->opt_op.same_state && flash->opt_op.same_value;
}

/* return whether a write operation can be optimized. A write operation
   requires the chip state to be identical, but the value written may differ
   per chip */
FORCE_INLINE bool
opt_write_allowed(flash_memory_t *flash)
{
        return flash->opt_op.bus_size && flash->opt_op.bus_aligned
                && flash->opt_op.same_state;
}

FORCE_INLINE void
mark_opt_op_done(flash_memory_t *flash)
{
        flash->opt_op.done = true;
}

/*
  Compute a command address. According to AMD documentation (the way it works
  is similar for Intel flashes), a flash is connected the following way:

  * 8-bit flash on 8-bit bus:

  Bus        Flash
  0 -------- A0
  1 -------- A1
  ...

  Command addresses are 0x555 and 0x2AA

  * 16-bit flash on 16-bit bus (the lsb is ignored since we are addressing
    words)

  Bus        Flash
  0
  1 -------- A0
  ...

  Command addresses are 0x555 and 0x2AA. To produce them on A0-An, the software
  has to access 0x555 * 2 = 0xAAA and 0x2AA *2 = 0x554

  * 16-bit flash on 8-bit bus (the lsb is used on DQ15 to select the correct
    byte)

  Bus        Flash
  0 -------- DQ15 (byte select)
  1 -------- A0
  ......

  Command addresses are 0xAAA and 0x555, which will produce 0x555 and 0x2AA on
  A0-An, just as in the previous case.

  * Note that the reasoning is similar for CFI offsets (0x10 -> 0x20, ...)

  * The conclusion is that the command address is dependent on the maximum chip
    width only, so it can be computed with the following formula:
*/
FORCE_INLINE uint64 get_cmd_offset(flash_memory_t *flash,
                                   uint64 offset_in_chip)
{
        return offset_in_chip / flash->max_chip_width_in_bytes;
}

uint64 byte_swap(uint64 value, unsigned swap_size);

FORCE_INLINE uint64
endian_converted(flash_memory_t *flash, uint64 chip_value)
{
        return (flash->big_endian)
                ? byte_swap(chip_value, flash->chip_width_in_bytes)
                : chip_value;
}

int generic_read_lock_status(flash_memory_t *flash, unsigned chip_index,
                             uint64 offset_in_flash);
void generic_write_buffer_setup(flash_memory_t *flash, unsigned chip_index,
                                uint64 offset_in_flash, uint64 value);
int generic_write_buffer_size(flash_memory_t *flash, unsigned chip_index,
                              uint64 offset_in_flash, uint64 value);
int generic_write_buffer_gather(flash_memory_t *flash, unsigned chip_index,
                                uint64 offset_in_flash, uint64 chip_value);
void generic_write_buffer_confirm(flash_memory_t *flash, unsigned chip_index,
                                  uint64 offset_in_flash, uint64 value);

int cfi_query_read  (flash_memory_t *flash, unsigned chip_index, uint64 offset,
                     uint64 *chip_value);

int intel_read_lock_status(flash_memory_t *flash, unsigned chip_index,
                           uint64 chip_offset);
int intel_read_operation(flash_memory_t *flash, unsigned chip_index,
                         uint64 offset, uint64 *chip_value);
int intel_write_operation(flash_memory_t *flash, unsigned chip_index,
                          uint64 offset, uint64 chip_value);

int amd_read_operation  (flash_memory_t *flash, unsigned chip_index,
                         uint64 offset, uint64 *chip_value);
int amd_write_operation  (flash_memory_t *flash, unsigned chip_index,
                          uint64 offset, uint64 chip_value);

void update_state(flash_memory_t *flash, unsigned chip_index,
                  fm_operation_t state);
int get_unit_in_chip(flash_memory_t *flash, uint64 offset_in_chip, bool exact);
int64 get_total_chip_size(flash_memory_t *flash);

uint64 memory_read(flash_memory_t *flash, uint64 offset, unsigned len);
void memory_write(flash_memory_t *flash, uint64 offset, unsigned len,
                  uint64 value);
void memory_write_buf(flash_memory_t *flash, uint64 address, uint64 len,
                      uint8 *buf);
void memory_write_buf_straddle(flash_memory_t *flash, uint64 offset,
                               uint64 size, uint8 *buf, unsigned width,
                               unsigned straddle);
void memory_set(flash_memory_t *flash, uint64 offset, uint64 size,
                uint8 value);
void memory_set_straddle(flash_memory_t *flash, uint64 offset, uint64 size,
                         uint8 value, unsigned width, unsigned straddle);
uint64 get_bus_value(flash_memory_t *flash, uint8 *value);

void time_delayed_operation_done(conf_object_t *obj, void *data);
void post_busy_event(flash_memory_t *flash, unsigned chip_index, double delay);

void intel_finalize(flash_memory_t *flash);
void amd_finalize(flash_memory_t *flash);

#if defined(__cplusplus)
}
#endif
#endif /* FLASH_MEMORY_H */
