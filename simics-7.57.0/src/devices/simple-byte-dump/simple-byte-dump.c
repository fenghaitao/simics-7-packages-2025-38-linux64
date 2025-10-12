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

#include <stdio.h>
#include <fcntl.h>
#include <ctype.h>

#include <simics/device-api.h>
#include <simics/util/os.h>

#include <simics/devs/io-memory.h>

typedef struct {
        conf_object_t obj;
	char *filename;
	int fd;
} byte_dump_device_t;

static conf_object_t *
alloc_object(void *data)
{
        byte_dump_device_t *bdd = MM_ZALLOC(1, byte_dump_device_t);
        return &bdd->obj;
}

static void *
init_object(conf_object_t *obj, void *data)
{
        byte_dump_device_t *bdd = (byte_dump_device_t *)obj;
	bdd->fd = -1;
        return bdd;
}

static exception_type_t
operation(conf_object_t *obj, generic_transaction_t *mop, map_info_t info)
{
        byte_dump_device_t *bdd = (byte_dump_device_t *)obj;
        int offset = (SIM_get_mem_op_physical_address(mop)
                      + info.start - info.base);

        if (SIM_mem_op_is_read(mop)) {
                if (SIM_get_mem_op_inquiry(mop))
                        return Sim_PE_Inquiry_Unhandled;

                SIM_LOG_SPEC_VIOLATION(1, &bdd->obj, 0,
                                       "only write accesses allowed");
                SIM_set_mem_op_value_le(mop, 0);
        } else {
		uint8 value = SIM_get_mem_op_value_le(mop);

                if (SIM_get_mem_op_size(mop) != 1)
                        SIM_LOG_SPEC_VIOLATION(1, &bdd->obj, 0,
                                               "only byte accesses allowed");
		SIM_LOG_INFO(2, &bdd->obj, 0,
			     "write to offset %d, value 0x%x: '%c'",
                             offset, value, isprint(value) ? value : ' ');

		if (bdd->fd >= 0) {
			ssize_t written = write(bdd->fd, &value, 1);
                        if (written == -1)
                                SIM_LOG_ERROR(&bdd->obj, 0, "Byte dump failed");
                }
        }
        return Sim_PE_No_Exception;
}

static set_error_t
set_filename(void *arg, conf_object_t *obj, attr_value_t *val,
             attr_value_t *idx)
{
        byte_dump_device_t *bdd = (byte_dump_device_t *)obj;
        int fd = -1;   // reset fd to <0 if input is Nil
        const char *fname =
                SIM_attr_is_string(*val) ? SIM_attr_string(*val) : NULL;
        if (fname) {
                fd = os_open(fname, O_CREAT | O_WRONLY | O_TRUNC | O_BINARY,
                             0666);
                
                if (fd < 0) {
                        SIM_attribute_error("Failed opening file");
                        return Sim_Set_Illegal_Value;
                }
        }

        if (bdd->filename) {
                close(bdd->fd);
                MM_FREE(bdd->filename);
        }

        bdd->fd = fd;
        bdd->filename = fname ? MM_STRDUP(SIM_attr_string(*val)) : NULL;

        return Sim_Set_Ok;
}

static attr_value_t
get_filename(void *arg, conf_object_t *obj, attr_value_t *idx)
{
        byte_dump_device_t *bdd = (byte_dump_device_t *)obj;
        return SIM_make_attr_string(bdd->filename);   // handles null
}

void
init_local()
{
        class_data_t funcs = {
                .alloc_object = alloc_object,
                .init_object = init_object,
                .class_desc = "dumps bytes from memory to file",
                .description =
                "A simple device that dumps all bytes written to a particular"
                " location in memory to a file specified by the"
                " \"filename\" attribute."
        };
        conf_class_t *class = SIM_register_class("simple-byte-dump", &funcs);

        static const io_memory_interface_t iom = { .operation = operation };
        SIM_register_interface(class, IO_MEMORY_INTERFACE, &iom);

        SIM_register_typed_attribute(
                class, "filename",
                get_filename, NULL, set_filename, NULL,
                Sim_Attr_Optional, "s|n", NULL,
                "Filename to write bytes to. If not set, or set to Nil,"
                " anything written is discarded.");
}
