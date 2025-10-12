/*
  © 2010 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <simics/device-api.h>
#include <simics/devs/io-memory.h>
#include <simics/devs/serial-device.h>

typedef struct {
        conf_object_t obj;

        conf_object_t *tty_con;
        const serial_device_interface_t *tty_int;

        QUEUE(uint8) in_buffer;
        QUEUE(uint8) out_buffer;
} tty_device_t;

static int
tty_write(conf_object_t *obj, int value)
{
        tty_device_t *tty = (tty_device_t *)obj;
        QADD(tty->in_buffer, value);
        return 1;
}

static void
tty_receive_ready(conf_object_t *obj)
{
        tty_device_t *tty = (tty_device_t *)obj;

        if (!tty->tty_con)
                return;

        while (!QEMPTY(tty->out_buffer)) {
                if (tty->tty_int->write(tty->tty_con, QGET(tty->out_buffer, 0)))
                        (void)QREMOVE(tty->out_buffer);
                else
                        return; /* wait for destination to accept more */
        }
}

static exception_type_t
tty_operation(conf_object_t *obj, generic_transaction_t * mem_op,
              map_info_t info)
{
        if (SIM_get_mem_op_inquiry(mem_op))
                return Sim_PE_Inquiry_Unhandled;

        tty_device_t *tty = (tty_device_t *)obj;
        int offset = SIM_get_mem_op_physical_address(mem_op) - info.base;
        uint32 value;

        if (offset == 0) {
                if (SIM_mem_op_is_write(mem_op)) {
                        value = SIM_get_mem_op_value_be(mem_op);

                        SIM_LOG_INFO(4, &tty->obj, 0,
                                     "wrote char 0x%x", value);

                        /* handle 'return' specially, add carriage return */
                        if (value == (uint32)'\n') {
                                QADD(tty->out_buffer, '\n');
                                QADD(tty->out_buffer, '\r');
                        } else {
                                QADD(tty->out_buffer, value);
                        }
                        tty_receive_ready(obj);
                } else {
                        if (QEMPTY(tty->in_buffer))
                                value = TTY_NO_CHAR;
                        else
                                value = QREMOVE(tty->in_buffer);

                        SIM_set_mem_op_value_be(mem_op, value);
                }
        } else {
                SIM_LOG_SPEC_VIOLATION(1, &tty->obj, 0,
                                       "unknown offset 0x%x",
                                       offset);
                if (SIM_mem_op_is_read(mem_op))
                        SIM_set_mem_op_value_be(mem_op, 0);
        }
        return Sim_PE_No_Exception;
}

static conf_object_t *
tty_alloc_object(void *obj)
{
        tty_device_t *tty = (tty_device_t *)MM_ZALLOC(1, tty_device_t);
        return &tty->obj;
}

static void *
tty_init_object(conf_object_t *obj, void *data)
{
        tty_device_t *tty = (tty_device_t *)obj;
        QINIT(tty->in_buffer);
        QINIT(tty->out_buffer);
        return tty;
}

static int
tty_delete_object(conf_object_t *obj)
{
        tty_device_t *tty = (tty_device_t *)obj;
        QFREE(tty->in_buffer);
        QFREE(tty->out_buffer);
        MM_FREE(tty);
        return 1;
}

static set_error_t
set_console(conf_object_t *obj, attr_value_t *val)
{
        tty_device_t *tty = (tty_device_t *)obj;
        if (SIM_attr_is_nil(*val)) {
                tty->tty_con = NULL;
        } else {
                const serial_device_interface_t *con_int;
                con_int = SIM_get_interface(SIM_attr_object(*val),
                                            SERIAL_DEVICE_INTERFACE);
                if (!con_int)
                        return Sim_Set_Interface_Not_Found;

                tty->tty_con = SIM_attr_object(*val);
                tty->tty_int = con_int;
        }
        return Sim_Set_Ok;
}

static attr_value_t
get_console(conf_object_t *obj)
{
        tty_device_t *tty = (tty_device_t *)obj;
        return SIM_make_attr_object(tty->tty_con);
}

static set_error_t
set_in_buffer(conf_object_t *obj, attr_value_t *val)
{
        tty_device_t *tty = (tty_device_t *)obj;

        QCLEAR(tty->in_buffer);

        for (int i = 0; i < SIM_attr_list_size(*val); i++)
                QADD(tty->in_buffer,
                     SIM_attr_integer(SIM_attr_list_item(*val, i)));

        return Sim_Set_Ok;
}

static attr_value_t
get_in_buffer(conf_object_t *obj)
{
        tty_device_t *tty = (tty_device_t *)obj;
        int len;
        len = QLEN(tty->in_buffer);
        attr_value_t ret = SIM_alloc_attr_list(len);
        for (int i = 0; i < len; i++)
                SIM_attr_list_set_item(
                        &ret, i,
                        SIM_make_attr_uint64(QGET(tty->in_buffer, i)));

        return ret;
}

static set_error_t
set_out_buffer(conf_object_t *obj, attr_value_t *val)
{
        tty_device_t *tty = (tty_device_t *)obj;

        QCLEAR(tty->out_buffer);

        for (int i = 0; i < SIM_attr_list_size(*val); i++)
                QADD(tty->out_buffer,
                     SIM_attr_integer(SIM_attr_list_item(*val, i)));

        return Sim_Set_Ok;
}

static attr_value_t
get_out_buffer(conf_object_t *obj)
{
        tty_device_t *tty = (tty_device_t *)obj;
        int len;
        len = QLEN(tty->out_buffer);
        attr_value_t ret = SIM_alloc_attr_list(len);
        for (int i = 0; i < len; i++)
                SIM_attr_list_set_item(
                        &ret, i,
                        SIM_make_attr_uint64(QGET(tty->out_buffer, i)));

        return ret;
}

void
init_local()
{
        conf_class_t *tty_class = SIM_register_class(
                "simple-tty",
                &(const class_data_t){
                        .alloc_object    = tty_alloc_object,
                        .init_object     = tty_init_object,
                        .delete_instance = tty_delete_object,
                        .class_desc      = "simple tty",
                        .description     = "A simple serial device."});

        static const serial_device_interface_t tty_interface = {
                .write         = tty_write,
                .receive_ready = tty_receive_ready,
        };
        SIM_REGISTER_INTERFACE(tty_class, serial_device, &tty_interface);

        static const io_memory_interface_t io_interface = {
                .operation = tty_operation
        };
        SIM_REGISTER_INTERFACE(tty_class, io_memory, &io_interface);

        SIM_register_attribute(tty_class, "console",
                               get_console,
                               set_console,
                               Sim_Attr_Optional,
                               "o|n",
                               "Name of a console object that implements the '"
                               SERIAL_DEVICE_INTERFACE "' interface. This"
                               " object is used for character input and"
                               " output.");

        SIM_register_attribute(tty_class, "input_buffer",
                               get_in_buffer,
                               set_in_buffer,
                               Sim_Attr_Optional,
                               "[i*]",
                               "The input buffer.");

        SIM_register_attribute(tty_class, "output_buffer",
                               get_out_buffer,
                               set_out_buffer,
                               Sim_Attr_Optional,
                               "[i*]",
                               "The output buffer.");
}
