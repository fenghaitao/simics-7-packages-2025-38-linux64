/*
 ser-link.c

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

#include <simics/module-host-config.h>
#include <simics/device-api.h>

#include <simics/devs/liblink.h>
#include <simics/devs/serial-device.h>

#include <simics/util/hashtab.h>

typedef struct {
        conf_object_t obj;

        /* The set of connected endpoints. The link is unusable if there aren't
           exactly two endpoints. (The hash table maps endpoint IDs to
           NULL.) */
        ht_int_table_t endpoints;

        /* The number of characters an endpoint is allowed to have outstanding
           delivery notifications for. Must be at least one, otherwise the link
           wouldn't be able to ack sent characters. */
        unsigned buffer_size;
} ser_link_impl_t;

typedef QUEUE(uint8) uint8_queue_t;

typedef struct {
        conf_object_t obj;
        const serial_device_interface_t *serial_ifc;

        /* Is the device currently waiting for a go-ahead when we become able
           to accept new characters? */
        bool device_is_waiting;

        /* The number of characters we've sent but not yet gotten delivery
           notifications for. */
        unsigned sent_characters;

        /* Characters that we've received but not yet delivered to the
           device. */
        uint8_queue_t receive_buffer;
} ser_link_endpoint_t;

typedef struct {
        link_message_t common;
        enum { MSG_Char, MSG_Delivered } msgtype;
        uint8 c; /* only for MSG_Char */
} ser_link_message_t;

static link_message_t *
new_char_message(uint8 c)
{
        ser_link_message_t *msg = MM_MALLOC(1, ser_link_message_t);
        SIMLINK_init_message(&msg->common);
        msg->msgtype = MSG_Char;
        msg->c = c;
        return &msg->common;
}

static link_message_t *
new_delivered_message()
{
        ser_link_message_t *msg = MM_MALLOC(1, ser_link_message_t);
        SIMLINK_init_message(&msg->common);
        msg->msgtype = MSG_Delivered;
        return &msg->common;
}

static void
free_message(conf_object_t *link, link_message_t *msg)
{
        MM_FREE(msg);
}

static attr_value_t
msg_to_attr(conf_object_t *link, const link_message_t *msgdata)
{
        const ser_link_message_t *msg
                = (const ser_link_message_t *)msgdata;
        switch (msg->msgtype) {
        case MSG_Char:
                return SIM_make_attr_list(2, SIM_make_attr_string("char"),
                                          SIM_make_attr_uint64(msg->c));
        case MSG_Delivered:
                return SIM_make_attr_list(1, SIM_make_attr_string("delivered"));
        }
        ASSERT(false);
}

static link_message_t *
msg_from_attr(conf_object_t *link, attr_value_t attr)
{
        const char *type = SIM_attr_string(SIM_attr_list_item(attr, 0));
        if (strcmp(type, "char") == 0) {
                uint8 c = SIM_attr_integer(SIM_attr_list_item(attr, 1));
                return new_char_message(c);
        } else if (strcmp(type, "delivered") == 0) {
                return new_delivered_message();
        } else {
                return NULL;
        }
}

/* Deliver as many characters from the receive buffer as the connected device
   will accept. */
static void
deliver_from_buffer(ser_link_endpoint_t *slep)
{
        conf_object_t *dev = SIMLINK_endpoint_device(&slep->obj);
        while (!QEMPTY(slep->receive_buffer)) {
                uint8 c = QPEEK(slep->receive_buffer);
                switch (slep->serial_ifc->write(dev, c)) {
                case 0:
                        /* Rejected. We'll try again later. */
                        return;
                case 1:
                        /* Accepted. Remove the char from our buffer and send a
                           delivery notification. */
                        QDROP(slep->receive_buffer, 1);
                        SIMLINK_send_message(&slep->obj, LINK_BROADCAST_ID,
                                             new_delivered_message());
                        break;
                default:
                        ASSERT(false);
                }
        }
}

/* <add id="sl_dlv"><insert-upto text="case MSG_Char:"/></add> */
static void
deliver(conf_object_t *ep, const link_message_t *msgd)
{
        ser_link_endpoint_t *slep = (ser_link_endpoint_t *)ep;
        ser_link_impl_t *slink = (ser_link_impl_t *)SIMLINK_endpoint_link(ep);
        ser_link_message_t *msg = (ser_link_message_t *)msgd;
        switch (msg->msgtype) {
        case MSG_Char:
                QADD(slep->receive_buffer, msg->c);
                if (QLEN(slep->receive_buffer) == 1) {
                        /* The queue was empty, so we're not currently blocked
                           and can try to deliver the character immediately. */
                        deliver_from_buffer(slep);
                }
                return;
        case MSG_Delivered:
                ASSERT(slep->sent_characters > 0);
                slep->sent_characters--;
                if (slep->device_is_waiting
                    && slep->sent_characters < slink->buffer_size) {
                        slep->device_is_waiting = false;
                        slep->serial_ifc->receive_ready(
                                SIMLINK_endpoint_device(ep));
                }
                return;
        }
        ASSERT(false);
}

/* <add id="sl_cfg_up"><insert-until text="// sl_cfg_up_end"/></add> */
static void
link_config_value_updated(conf_object_t *link, const char *key, 
                          const frags_t *msg)
{
        ser_link_impl_t *slink = (ser_link_impl_t *)link;
        if (strncmp(key, "ep", 2) == 0) {
                uint64 ep_id = strtoull(key + 2, NULL, 16);
                SIM_LOG_INFO(4, &slink->obj, 0,
                             "Add endpoint: 0x%llx", ep_id);
                ht_update_int(&slink->endpoints, ep_id, NULL);
        } else if (strcmp(key, "buffer_size") == 0) {
                slink->buffer_size = frags_extract_be32(msg, 0);
        } else {
                ASSERT(false);
        }
}
// sl_cfg_up_end <- jdocu insert-until marker

/* <add id="sl_cfg_rm"><insert-until text="// sl_cfg_rm_end"/></add> */
static void
link_config_value_removed(conf_object_t *link, const char *key)
{
        ser_link_impl_t *slink = (ser_link_impl_t *)link;
        if (strncmp(key, "ep", 2) == 0) {
                uint64 ep_id = strtoull(key + 2, NULL, 16);
                SIM_LOG_INFO(4, &slink->obj, 0,
                             "Remove endpoint: 0x%llx", ep_id);
                ht_remove_int(&slink->endpoints, ep_id);
        } else {
                ASSERT(false);
        }
}
// sl_cfg_rm_end <- jdocu insert-until marker

static void
marshal(conf_object_t *link, const link_message_t *_msg,
        void (*finish)(void *data, const frags_t *msg), void *finish_data)
{
        const ser_link_message_t *msg = (const ser_link_message_t *)_msg;
        uint8 msg_data[2] = { msg->msgtype, msg->c };
        frags_t data;
        frags_init_add(&data, &msg_data, sizeof(msg_data));
        finish(finish_data, &data);
}

static link_message_t *
unmarshal(conf_object_t *link, const frags_t *data)
{
        ASSERT(frags_len(data) == 2);
        switch (frags_extract_8(data, 0)) {
        case MSG_Char: return new_char_message(frags_extract_8(data, 1));
        case MSG_Delivered: return new_delivered_message();
        }
        ASSERT(false);
}

/* <add id="sl_dev_changed"><insert-until text="// sl_dev_changed_end"/>
   </add> */
static void
ser_link_ep_device_changed(conf_object_t *ep, conf_object_t *old_dev)
{
        ser_link_endpoint_t *slep = (ser_link_endpoint_t *)ep;
        slep->serial_ifc = SIM_c_get_port_interface(
                SIMLINK_endpoint_device(ep), SERIAL_DEVICE_INTERFACE,
                SIMLINK_endpoint_port(ep));
 
        if (!old_dev) {
                char ep_id[19];
                snprintf(ep_id, sizeof(ep_id), "ep%llx", 
                         SIMLINK_endpoint_id(ep));
                frags_t value;
                frags_init(&value);
                SIMLINK_config_update_value(SIMLINK_endpoint_link(ep), 
                                            ep_id, &value);
        }
}
// sl_dev_changed_end <- jdocu insert-until marker

/* <add id="sl_init_object"><insert-until text="// sl_init_object_end"/>
   </add> */
static const link_type_t ser_link_type = {
        .msg_to_attr = msg_to_attr,
        .msg_from_attr = msg_from_attr,
        .free_msg = free_message,
        .marshal = marshal,
        .unmarshal = unmarshal,
        .deliver = deliver,
        .update_config_value = link_config_value_updated,
        .remove_config_value = link_config_value_removed,
        .device_changed = ser_link_ep_device_changed
};

static conf_object_t *
ser_link_alloc_object(void *arg)
{
        ser_link_impl_t *slink = MM_ZALLOC(1, ser_link_impl_t);
        return &slink->obj;
}

static void *
ser_link_init_object(conf_object_t *obj, void *arg)
{
        ser_link_impl_t *slink = (ser_link_impl_t *)obj;
        SIMLINK_init(&slink->obj, &ser_link_type);
        slink->buffer_size = 10; /* a reasonable default value? */
        return obj;
}
// sl_init_object_end <- jdocu insert-until marker

static void
ser_link_finalize_instance(conf_object_t *obj)
{
        SIMLINK_finalize(obj);
}

/* <add id="sl_link_pre_delete"><insert-upto text="}"/></add> */
static void
ser_link_pre_delete_instance(conf_object_t *obj)
{
        SIMLINK_pre_delete(obj);
}

static int
ser_link_delete_instance(conf_object_t *obj)
{
        ser_link_impl_t *slink = (ser_link_impl_t *)obj;
        ht_delete_int_table(&slink->endpoints, false);
        MM_FREE(slink);
        return 0; /* this return value is ignored */
}

static conf_object_t *
ser_link_ep_alloc_object(void *arg)
{
        ser_link_endpoint_t *slep = MM_ZALLOC(1, ser_link_endpoint_t);
        return &slep->obj;
}

static void *
ser_link_ep_init_object(conf_object_t *obj, void *arg)
{
        ser_link_endpoint_t *slep = (ser_link_endpoint_t *)obj;
        SIMLINK_endpoint_init(&slep->obj, false);
        slep->device_is_waiting = false;
        slep->sent_characters = 0;
        QINIT(slep->receive_buffer);
        return obj;
}

/* <add id="sl_ep_finalize"><insert-upto text="}"/></add> */
static void
ser_link_ep_finalize_instance(conf_object_t *ep)
{
        SIMLINK_endpoint_finalize(ep);
}

/* <add id="sl_remove_config"><insert-upto text="}"/></add> */
static void
ser_link_ep_pre_delete_instance(conf_object_t *ep)
{
        char ep_id[19];
        snprintf(ep_id, sizeof(ep_id), "ep%llx", SIMLINK_endpoint_id(ep));
        SIMLINK_config_remove_value(SIMLINK_endpoint_link(ep), ep_id);
        SIMLINK_endpoint_disconnect(ep);
}

static int
ser_link_ep_delete_instance(conf_object_t *obj)
{
        MM_FREE(obj);
        return 0; /* this return value is ignored */
}

/* The device writes a character to the link. */
static int
sd_write(conf_object_t *ep, int val)
{
        ser_link_endpoint_t *slep = (ser_link_endpoint_t *)ep;
        ser_link_impl_t *slink = (ser_link_impl_t *)SIMLINK_endpoint_link(ep);
        if (slep->sent_characters >= slink->buffer_size) {
                slep->device_is_waiting = true;
                return 0; /* our send buffer is full, try again later */
        }
        int num_endpoints = ht_num_entries_int(&slink->endpoints);
        if (num_endpoints != 2) {
                bool plural = num_endpoints == 1;
                SIM_LOG_ERROR(&slep->obj, 0, "sending when there %s %d"
                              " connected endpoint%s (there should be"
                              " exactly 2)", plural ? "are" : "is",
                              num_endpoints, plural ? "s" : "");
                return 1; /* we accepted the character (but dropped it) */
        }
        if (val < 0 || val > 0xff) {
                SIM_LOG_ERROR(&slep->obj, 0, "trying to send out-of-range"
                              " character 0x%x", val);
                return 1; /* we accepted the character (but dropped it) */
        }
        slep->sent_characters++;
        SIMLINK_send_message(ep, LINK_BROADCAST_ID, new_char_message(val));
        return 1; /* we accepted the character */
}

/* We have previously tried to deliver a character to the device and gotten
   told to try again later; the device is now telling us that it's time to try
   again. */
static void
sd_receive_ready(conf_object_t *obj)
{
        ser_link_endpoint_t *slep = (ser_link_endpoint_t *)obj;
        deliver_from_buffer(slep);
}

static attr_value_t
get_link_buffer_size(void *user_data, conf_object_t *obj, attr_value_t *idx)
{
        ser_link_impl_t *slink = (ser_link_impl_t *)obj;
        return SIM_make_attr_uint64(slink->buffer_size);
}

static set_error_t
set_link_buffer_size(void *user_data, conf_object_t *obj,
                     attr_value_t *val, attr_value_t *idx)
{
        ser_link_impl_t *slink = (ser_link_impl_t *)obj;
        int new_size = SIM_attr_integer(*val);
        if (new_size < 1)
                return Sim_Set_Illegal_Value;
        if (slink->buffer_size != new_size) {
                uint32 size;
                STORE_BE32(&size, new_size);
                frags_t value;
                frags_init_add(&value, &size, sizeof(size));
                SIMLINK_config_update_value(obj, "buffer_size", &value);
                slink->buffer_size = new_size;
        }
        return Sim_Set_Ok;
}

static attr_value_t
get_ep_device_is_waiting(void *user_data, conf_object_t *obj, attr_value_t *idx)
{
        ser_link_endpoint_t *slep = (ser_link_endpoint_t *)obj;
        return SIM_make_attr_boolean(slep->device_is_waiting);
}

static set_error_t
set_ep_device_is_waiting(void *user_data, conf_object_t *obj,
                     attr_value_t *val, attr_value_t *idx)
{
        ser_link_endpoint_t *slep = (ser_link_endpoint_t *)obj;
        slep->device_is_waiting = SIM_attr_boolean(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_ep_sent_characters(void *user_data, conf_object_t *obj, attr_value_t *idx)
{
        ser_link_endpoint_t *slep = (ser_link_endpoint_t *)obj;
        return SIM_make_attr_uint64(slep->sent_characters);
}

static set_error_t
set_ep_sent_characters(void *user_data, conf_object_t *obj,
                       attr_value_t *val, attr_value_t *idx)
{
        ser_link_endpoint_t *slep = (ser_link_endpoint_t *)obj;
        slep->sent_characters = SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_ep_receive_buffer(void *user_data, conf_object_t *obj, attr_value_t *idx)
{
        ser_link_endpoint_t *slep = (ser_link_endpoint_t *)obj;
        attr_value_t lst = SIM_alloc_attr_list(QLEN(slep->receive_buffer));
        for (int i = 0; i < QLEN(slep->receive_buffer); i++)
                SIM_attr_list_set_item(
                        &lst, i, SIM_make_attr_uint64(
                                QGET(slep->receive_buffer, i)));
        return lst;
}

static set_error_t
set_ep_receive_buffer(void *user_data, conf_object_t *obj,
                      attr_value_t *val, attr_value_t *idx)
{
        ser_link_endpoint_t *slep = (ser_link_endpoint_t *)obj;
        uint8_queue_t q = QNULL;
        for (int i = 0; i < SIM_attr_list_size(*val); i++) {
                int64 c = SIM_attr_integer(SIM_attr_list_item(*val, i));
                if (c < 0 || c > 0xff)
                        return Sim_Set_Illegal_Value;
                QADD(q, c);
        }
        QFREE(slep->receive_buffer);
        slep->receive_buffer = q;
        return Sim_Set_Ok;
}

/* <add id="sl_init"><insert-until text="// sl_init_end"/></add> */
void
init_local()
{
        SIMLINK_init_library();

        const class_data_t link_cls_funcs = {
                .alloc_object = ser_link_alloc_object,
                .init_object = ser_link_init_object,
                .finalize_instance = ser_link_finalize_instance,
                .pre_delete_instance = ser_link_pre_delete_instance,
                .delete_instance = ser_link_delete_instance,
                .class_desc = "model of serial link",
                .description = "Serial link"
        };
        conf_class_t *link_cls = SIM_register_class("ser-link-impl",
                                                    &link_cls_funcs);
        SIMLINK_register_class(link_cls);
        SIM_register_typed_attribute(
                link_cls, "buffer_size", get_link_buffer_size, NULL,
                set_link_buffer_size, NULL, Sim_Attr_Optional, "i", NULL,
                "The number of characters that the link may buffer. Must"
                " be at least one.");

        const class_data_t ep_cls_funcs = {
                .alloc_object = ser_link_ep_alloc_object,
                .init_object = ser_link_ep_init_object,
                .finalize_instance = ser_link_ep_finalize_instance,
                .pre_delete_instance = ser_link_ep_pre_delete_instance,
                .delete_instance = ser_link_ep_delete_instance,
                .class_desc =  "serial link endpoint",
                .description = "Serial link endpoint"
        };
        conf_class_t *ep_cls = SIM_register_class("ser-link-endpoint",
                                                  &ep_cls_funcs);
        SIMLINK_register_endpoint_class(ep_cls, "[s]|[si]");
        // sl_init_end <- jdocu insert-until marker

        SIM_register_typed_attribute(
                ep_cls, "device_is_waiting", get_ep_device_is_waiting, NULL,
                set_ep_device_is_waiting, NULL, Sim_Attr_Optional, "b", NULL,
                "Is the device waiting for us to notify it when we can"
                " accept another character?");
        SIM_register_typed_attribute(
                ep_cls, "sent_characters", get_ep_sent_characters, NULL,
                set_ep_sent_characters, NULL, Sim_Attr_Optional, "i", NULL,
                "The number of characters that we have sent over the link"
                " but not yet received delivery notifications for.");
        SIM_register_typed_attribute(
                ep_cls, "receive_buffer", get_ep_receive_buffer, NULL,
                set_ep_receive_buffer, NULL, Sim_Attr_Optional, "[i*]", NULL,
                "The characters that we are about to deliver to the"
                " connected device.");
        static const serial_device_interface_t sd_ifc = {
                .write = sd_write,
                .receive_ready = sd_receive_ready,
        };
        SIM_register_interface(ep_cls, SERIAL_DEVICE_INTERFACE, &sd_ifc);
}
