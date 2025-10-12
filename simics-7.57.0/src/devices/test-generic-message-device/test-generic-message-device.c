/*
  test-generic-message-device.c - sample code of generic message device for
  testing purpose.

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

#include <simics/device-api.h>
#include <simics/util/genrand.h>

#define DEVICE_NAME "test_generic_message_device"

#include "generic-message-interfaces.h"

typedef struct {
        uint64 min;
        uint64 max;
} value_int_t;

/* THREAD_SAFE_GLOBAL: send_message_event_class init */
static event_class_t *send_message_event_class;

static uint64
randomize_value_int(rand_state_t *rs, value_int_t *vi)
{
        return (genrand_uint64(rs) % (vi->max - vi->min + 1)) + vi->min;
}

typedef struct generic_message_sample_device {
        conf_object_t obj;

        uint32 address;

        value_int_t dest_address;
        value_int_t value;                   /* uint8 values */
        value_int_t length;                  /* bytes */
        value_int_t delay;                   /* steps */
        value_int_t frame_delay;             /* ns */

        int save_logs;
        FILE *sendlog;
        FILE *recvlog;

        rand_state_t *rstate;

        conf_object_t *link;
        const generic_message_link_interface_t *link_ifc;
        int id;
} generic_message_sample_device_t;

/* generic message device interface */
static void
sample_receive_frame(conf_object_t *obj, conf_object_t *link, dbuffer_t *frame)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;
        const uint8 *contents = dbuffer_read_all(frame);

        if (dbuffer_len(frame) < 5) {
                SIM_LOG_ERROR(
                        &sample->obj, 0,
                        "received a frame that contains less than 5 bytes");
                return;
        }

        /* read the source address */
        uint32 src_address = *((uint32 *)contents);

        /* check that this is a correct frame */
        for (int i = 4; i < dbuffer_len(frame); i++) {
                if (contents[i] != contents[4]) {
                        SIM_LOG_ERROR(&sample->obj, 0,
                                      "incorrect frame at offset %d", i);
                        return;
                }
        }

        SIM_LOG_INFO(4, &sample->obj, 0, "receive: src 0x%x -> dst 0x%x,"
                     " size %d, contents 0x%x",
                     src_address, sample->address,
                     (uint32)dbuffer_len(frame),
                     (uint32)contents[4]);
        if (sample->save_logs) {
                fprintf(sample->recvlog, 
                        "%lld: src 0x%x -> dst 0x%x, size %d, contents 0x%x\n",
                        SIM_cycle_count(&sample->obj),
                        src_address, sample->address,
                        (uint32)dbuffer_len(frame),
                        (uint32)contents[4]);
                fflush(sample->recvlog);
        }
}

/* address */
static set_error_t
set_address(void *arg, conf_object_t *obj, attr_value_t *val,
            attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;
        sample->address = SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_address(void *arg, conf_object_t *obj, attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;
        return SIM_make_attr_uint64(sample->address);
}

static void
attr_to_value_int(attr_value_t *attr, value_int_t *val)
{
        val->min = SIM_attr_integer(SIM_attr_list_item(*attr, 0));
        val->max = SIM_attr_integer(SIM_attr_list_item(*attr, 1));
}

static attr_value_t
value_int_to_attr(value_int_t *val)
{
        return SIM_make_attr_list(
                2,
                SIM_make_attr_uint64(val->min),
                SIM_make_attr_uint64(val->max));
}

/* dest_address */
static set_error_t
set_dest_address(void *arg, conf_object_t *obj, attr_value_t *val,
                 attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;
        attr_to_value_int(val, &(sample->dest_address));
        return Sim_Set_Ok;
}

static attr_value_t
get_dest_address(void *arg, conf_object_t *obj, attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;
        return value_int_to_attr(&(sample->dest_address));
}

/* value */
static set_error_t
set_value(void *arg, conf_object_t *obj, attr_value_t *val, attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;
        attr_to_value_int(val, &(sample->value));
        return Sim_Set_Ok;
}

static attr_value_t
get_value(void *arg, conf_object_t *obj, attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;
        return value_int_to_attr(&(sample->value));
}

/* delay */
static set_error_t
set_delay(void *arg, conf_object_t *obj, attr_value_t *val, attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;
        attr_to_value_int(val, &(sample->delay));
        return Sim_Set_Ok;
}

static attr_value_t
get_delay(void *arg, conf_object_t *obj, attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;
        return value_int_to_attr(&(sample->delay));
}

/* frame_delay */
static set_error_t
set_frame_delay(void *arg, conf_object_t *obj, attr_value_t *val,
                attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;
        attr_to_value_int(val, &(sample->frame_delay));
        return Sim_Set_Ok;
}

static attr_value_t
get_frame_delay(void *arg, conf_object_t *obj, attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;
        return value_int_to_attr(&(sample->frame_delay));
}

/* length */
static set_error_t
set_length(void *arg, conf_object_t *obj, attr_value_t *val, attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;
        sample->length.min = SIM_attr_integer(SIM_attr_list_item(*val, 0));
        sample->length.max = SIM_attr_integer(SIM_attr_list_item(*val, 1));
        return Sim_Set_Ok;
}

static attr_value_t
get_length(void *arg, conf_object_t *obj, attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;
        return value_int_to_attr(&(sample->length));
}

/* save_logs */
static set_error_t
set_save_logs(void *arg, conf_object_t *obj, attr_value_t *val,
              attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;

        if (!sample->save_logs && SIM_attr_integer(*val)) {
                int len = strlen(SIM_object_name(obj));
                char filename[len + 6];

                sprintf(filename, "%s.send", SIM_object_name(obj));
                sample->sendlog = fopen(filename, "w+");
        
                sprintf(filename, "%s.recv", SIM_object_name(obj));
                sample->recvlog = fopen(filename, "w+");
        } else if (sample->save_logs && !SIM_attr_integer(*val)) {
                fclose(sample->sendlog);
                fclose(sample->recvlog);
        }

        sample->save_logs = !!SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_save_logs(void *arg, conf_object_t *obj, attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;
        return SIM_make_attr_uint64(sample->save_logs);
}

/* link */
static int
connect_link(generic_message_sample_device_t *sample)
{
        if (sample->link) {
                if (!SIM_object_is_configured(sample->link))
                        SIM_require_object(sample->link);

                int dummy;
                sample->id = sample->link_ifc->connect_device(sample->link,
                                                              &sample->obj,
                                                              &dummy,
                                                              sample->address);
                SIM_event_post_cycle(&sample->obj,
                                     send_message_event_class,
                                     &sample->obj,
                                     0,
                                     NULL);
        }

        return sample->id;
}

static void
disconnect_link(generic_message_sample_device_t *sample)
{
        if (sample->link) {
                sample->link_ifc->disconnect_device(sample->link, &sample->obj);
                SIM_event_cancel_time(&sample->obj, send_message_event_class,
                                      &sample->obj, NULL, NULL);
        }
}

static set_error_t
set_link(void *arg, conf_object_t *obj, attr_value_t *val, attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;

        if (SIM_attr_is_nil(*val)) {
                if (sample->link)
                        disconnect_link(sample);
                sample->link = NULL;
                return Sim_Set_Ok;
        }

        if (sample->link == SIM_attr_object(*val))
                return Sim_Set_Ok;

        sample->link_ifc = SIM_c_get_interface(SIM_attr_object(*val),
                                               GENERIC_MESSAGE_LINK_INTERFACE);
        if (!sample->link_ifc) {
                SIM_LOG_ERROR(&sample->obj, 0, 
                              "the %s object is not a generic message link",
                              SIM_object_name(SIM_attr_object(*val)));
                return Sim_Set_Illegal_Value;
        }

        sample->link = SIM_attr_object(*val);
        if (SIM_object_is_configured(&sample->obj))
                connect_link(sample);

        return Sim_Set_Ok;
}

static attr_value_t
get_link(void *arg, conf_object_t *obj, attr_value_t *idx)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;
        return SIM_make_attr_object(sample->link);
}

/* send frame event */
static void 
send_message_event(conf_object_t *obj, lang_void *dummy) 
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;

        dbuffer_t *frame = new_dbuffer();
        uint32 *src_address = (uint32 *)dbuffer_append(frame, 4);
        *src_address = sample->address;
        uint8 value = randomize_value_int(sample->rstate, &sample->value);
        dbuffer_append_value(
                frame,
                value,
                randomize_value_int(sample->rstate, &sample->length));
        uint32 dst_address = randomize_value_int(sample->rstate, 
                                                 &sample->dest_address);
        uint64 delay = randomize_value_int(sample->rstate,
                                           &sample->frame_delay);

        sample->link_ifc->send_frame(sample->link,
                                     sample->id,
                                     dst_address,
                                     frame,
                                     delay);

        SIM_LOG_INFO(4, &sample->obj, 0, "send: src 0x%x -> dst 0x%x, size %d,"
                     " contents 0x%x", sample->address, dst_address,
                     (uint32)dbuffer_len(frame),
                     (uint32)value);
        if (sample->save_logs) {
                fprintf(sample->sendlog, 
                        "%lld: src 0x%x -> dst 0x%x, size %d, contents 0x%x\n",
                        SIM_cycle_count(&sample->obj),
                        sample->address, dst_address,
                        (uint32)dbuffer_len(frame),
                        (uint32)value);
                fflush(sample->sendlog);
        }

        /* we don't need the frame anymore */
        dbuffer_free(frame);

        SIM_event_post_cycle(obj,
                             send_message_event_class,
                             obj,
                             randomize_value_int(sample->rstate, 
                                                 &sample->delay),
                             NULL);
}

/* new/finalize/init/fini */
static conf_object_t *
sample_alloc_object(void *data)
{
        generic_message_sample_device_t *sample = 
                MM_ZALLOC(1, generic_message_sample_device_t);
        return &sample->obj;
}

static void *
sample_init_object(conf_object_t *obj, void *data)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;

        sample->address = 0xFFFFFFFF;
        sample->dest_address.min = 0;
        sample->dest_address.max = 0;
        sample->id = -1;
        
        return sample;
}

static void
sample_finalize_instance(conf_object_t *obj)
{
        generic_message_sample_device_t *sample = 
                (generic_message_sample_device_t *)obj;

        connect_link(sample);
        sample->rstate = genrand_init(sample->address);
}

#if defined(__cplusplus)
extern "C" {
#endif

/*
 * init_local() is called once when the device module is loaded into Simics.
 */
void
init_local()
{
        /*
         * Register the sample device class. The 'sample_alloc_object'
         * and 'sample_init_object' functions serve as a constructor, 
         * and is called every time a new instance is created.
         */
        class_data_t cd = {
                .alloc_object = sample_alloc_object,
                .init_object = sample_init_object,
                .finalize_instance = sample_finalize_instance,
                .class_desc = "obsolete - sample generic message link",
                .description = "obsolete generic-message-link sample device"
        };
        conf_class_t *sample_class = SIM_register_class(DEVICE_NAME, &cd);

        send_message_event_class = 
                SIM_register_event("g-link-sample-device-send-message", 
                                   sample_class, 0, 
                                   send_message_event, NULL, NULL, NULL, NULL);

        static const generic_message_device_interface_t gmd_ifc = {
                .receive_frame = sample_receive_frame
        };
        SIM_register_interface(sample_class, GENERIC_MESSAGE_DEVICE_INTERFACE,
                               &gmd_ifc);

        SIM_register_typed_attribute(
                sample_class, "address",
                get_address, NULL,
                set_address, NULL,
                Sim_Attr_Required,
                "i", NULL,
                "Address of the device itself on the link.");

        SIM_register_typed_attribute(
                sample_class, "dest_address",
                get_dest_address, NULL,
                set_dest_address, NULL,
                Sim_Attr_Optional,
                "[ii]", NULL,
                "Destination address for the messages (default is [0,0]).");
        
        SIM_register_typed_attribute(
                sample_class, "value",
                get_value, NULL,
                set_value, NULL,
                Sim_Attr_Optional,
                "[ii]", NULL,
                "Value to send in messages (default is [0,0]).");

        SIM_register_typed_attribute(
                sample_class, "length",
                get_length, NULL,
                set_length, NULL,
                Sim_Attr_Optional,
                "[ii]", NULL,
                "Length of the message to send (default is [1,100] bytes).");

        SIM_register_typed_attribute(
                sample_class, "delay",
                get_delay, NULL,
                set_delay, NULL,
                Sim_Attr_Optional,
                "[ii]", NULL,
                "Delay between each message in cycles (default is [1,100]).");

        SIM_register_typed_attribute(
                sample_class, "frame_delay",
                get_frame_delay, NULL,
                set_frame_delay, NULL,
                Sim_Attr_Optional,
                "[ii]", NULL,
                "Delay to send messages in ns (default is [0,0] ns).");

        SIM_register_typed_attribute(
                sample_class, "save_logs",
                get_save_logs, NULL,
                set_save_logs, NULL,
                Sim_Attr_Pseudo,
                "i", NULL,
                "Activate/Deactivate log saving for send/received frames");

        SIM_register_typed_attribute(
                sample_class, "link",
                get_link, NULL,
                set_link, NULL,
                Sim_Attr_Optional,
                "o|n", NULL,
                "Link to connect to.");
}

#if defined(__cplusplus)
}
#endif
