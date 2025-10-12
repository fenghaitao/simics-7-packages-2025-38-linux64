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

#include <string.h>

#include <simics/module-host-config.h>
#include <simics/device-api.h>
#include <simics/util/hashtab.h>

#include <simics/devs/liblink.h>
#include <simics/devs/signal.h>

static conf_class_t *ep_cls; /* the signal link endpoint class */

typedef struct {
        conf_object_t obj;
        ht_int_table_t receivers; /* IDs of all receiving endpoints */
} signal_link_t;

typedef struct {
        conf_object_t obj;
        bool is_sender;
} signal_link_endpoint_t;

typedef enum {
        Signal_Raise, Signal_Lower
} signal_link_msg_type_t;

typedef struct {
        link_message_t common;
        signal_link_msg_type_t msgtype;
} signal_link_message_t;

static signal_link_message_t *
new_signal_message(signal_link_msg_type_t msgtype)
{
        signal_link_message_t *msg = MM_MALLOC(1, signal_link_message_t);
        SIMLINK_init_message(&msg->common);
        msg->msgtype = msgtype;
        return msg;
}

static void
free_signal_message(conf_object_t *link, link_message_t *msg)
{
        MM_FREE(msg);
}

static attr_value_t
signal_to_attr(conf_object_t *link, const link_message_t *msgdata)
{
        const signal_link_message_t *msg
                = (const signal_link_message_t *)msgdata;
        return SIM_make_attr_list(
                1, SIM_make_attr_string(msg->msgtype == Signal_Raise
                                        ? "raise" : "lower"));
}

static link_message_t *
signal_from_attr(conf_object_t *link, attr_value_t attr)
{
        const char *type = SIM_attr_string(SIM_attr_list_item(attr, 0));
        if (strcmp(type, "raise") == 0)
                return &new_signal_message(Signal_Raise)->common;
        else
                return &new_signal_message(Signal_Lower)->common;
}

#define BUFFER_T(buf) (buffer_t){ .len = sizeof(buf), .data = buf }

static void
deliver_signal(conf_object_t *ep, const link_message_t *msg)
{
        signal_link_t *slink = (signal_link_t *)SIMLINK_endpoint_link(ep);
        conf_object_t *dev = SIMLINK_endpoint_device(ep);
        const char *port = SIMLINK_endpoint_port(ep);
        uint8 buf[1000];
        SIM_LOG_INFO(3, &slink->obj, 0, "delivering to %s",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));

        /* FIXME: cache */
        const signal_interface_t *iface =
                SIM_c_get_port_interface(dev, SIGNAL_INTERFACE, port);
        if (!iface) {
                SIM_LOG_ERROR(&slink->obj, 0,
                              "%s doesn't implement the "
                              SIGNAL_INTERFACE " interface",
                              SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));
                return;
        }

        signal_link_message_t *sigmsg = (signal_link_message_t *)msg;
        switch (sigmsg->msgtype) {
        case Signal_Raise:
                iface->signal_raise(dev);
                break;
        case Signal_Lower:
                iface->signal_lower(dev);
                break;
        default:
                ASSERT(0);
        }
}

static void
link_config_value_updated(conf_object_t *link, const char *key, const frags_t *msg)
{
        signal_link_t *slink = (signal_link_t *)link;
        uint64 ep_id = strtoull(key, NULL, 16);

        SIM_LOG_INFO(4, &slink->obj, 0, "Add receiver endpoint: ep%llx", ep_id);
        ht_update_int(&slink->receivers, ep_id, NULL);
}

static void
link_config_value_removed(conf_object_t *link, const char *key)
{
        signal_link_t *slink = (signal_link_t *)link;
        uint64 ep_id = strtoull(key, NULL, 16);

        SIM_LOG_INFO(4, &slink->obj, 0, "Remove receiver endpoint: ep%llx", ep_id);
        ht_remove_int(&slink->receivers, ep_id);
}

static void
marshal_signal(conf_object_t *link, const link_message_t *_msg,
               void (*finish)(void *data, const frags_t *msg),
               void *finish_data)
{
        const signal_link_message_t *msg = (const signal_link_message_t *)_msg;
        uint8 msg_data = msg->msgtype;
        frags_t data;
        frags_init_add(&data, &msg_data, 1);
        finish(finish_data, &data);
}

static link_message_t *
unmarshal_signal(conf_object_t *link, const frags_t *data)
{
        size_t len = frags_len(data);
        ASSERT(len >= 1);
        signal_link_message_t *msg = new_signal_message(
                frags_extract_8(data, 0));
        return &msg->common;
}

static void
signal_link_ep_device_changed(conf_object_t *ep, conf_object_t *old_dev)
{
        signal_link_endpoint_t *slep = (signal_link_endpoint_t *)ep;
        if (old_dev == NULL && !slep->is_sender) {
                /* Announce the presence of a new receiver to all the
                   endpoints. */
                char ep_id[17];
                snprintf(ep_id, sizeof(ep_id), "%llx",
                         SIMLINK_endpoint_id(ep));
                frags_t value;
                frags_init(&value); /* empty value, just to put the
                                       key in the database */
                SIMLINK_config_update_value(
                        SIMLINK_endpoint_link(ep), ep_id, &value);
        }
}

static const link_type_t signal_link_type = {
        .msg_to_attr = signal_to_attr,
        .msg_from_attr = signal_from_attr,
        .free_msg = free_signal_message,
        .marshal = marshal_signal,
        .unmarshal = unmarshal_signal,
        .deliver = deliver_signal,
        .update_config_value = link_config_value_updated,
        .remove_config_value = link_config_value_removed,
        .device_changed = signal_link_ep_device_changed
};

static conf_object_t *
signal_link_alloc_object(void *data)
{
        signal_link_t *slink = MM_ZALLOC(1, signal_link_t);
        return &slink->obj;
}

static void *
signal_link_init_object(conf_object_t *obj, void *data)
{
        signal_link_t *slink = (signal_link_t *)obj;
        SIMLINK_init(&slink->obj, &signal_link_type);
        ht_init_int_table(&slink->receivers);
        return slink;
}

static void
signal_link_finalize_instance(conf_object_t *obj)
{
        SIMLINK_finalize(obj);
}

static void
signal_link_pre_delete_instance(conf_object_t *obj)
{
        SIMLINK_pre_delete(obj);
}

static int
signal_link_delete_instance(conf_object_t *obj)
{
        signal_link_t *slink = (signal_link_t *)obj;
        ht_delete_int_table(&slink->receivers, false);
        return 0;
}

static conf_object_t *
signal_link_ep_alloc_object(void *data)
{
        signal_link_endpoint_t *slep = MM_ZALLOC(1, signal_link_endpoint_t);
        return &slep->obj;
}

static void *
signal_link_ep_init_object(conf_object_t *obj, void *data)
{
        signal_link_endpoint_t *slep = (signal_link_endpoint_t *)obj;
        SIMLINK_endpoint_init(&slep->obj, false);
        return slep;
}

static void
signal_link_ep_finalize_instance(conf_object_t *ep)
{
        SIMLINK_endpoint_finalize(ep);
}

static void
signal_link_ep_pre_delete_instance(conf_object_t *ep)
{
        signal_link_endpoint_t *slep = (signal_link_endpoint_t *)ep;
        if (!slep->is_sender) {
                /* Announce the removal of a receiver to all the endpoints. */
                char ep_id[17];
                snprintf(ep_id, sizeof(ep_id), "%llx",
                         SIMLINK_endpoint_id(ep));
                SIMLINK_config_remove_value(SIMLINK_endpoint_link(ep), ep_id);
        }
        SIMLINK_endpoint_disconnect(ep);
}

static int
signal_link_ep_delete_instance(conf_object_t *obj)
{
        MM_FREE(obj);
        return 0; /* this return value is ignored */
}

/* <add id="sig_send_message"><insert-upto text="}"/></add> */
static void
send_message(signal_link_endpoint_t *slep, link_message_t *msg)
{
        signal_link_t *slink = 
                (signal_link_t *)SIMLINK_endpoint_link(&slep->obj);
        int num_dsts = ht_num_entries_int(&slink->receivers);
        uint64 dst_ids[num_dsts];
        memset(dst_ids, 0, num_dsts * sizeof(uint64));
        int i = 0;
        HT_FOREACH_INT(&slink->receivers, it)
                dst_ids[i++] = ht_iter_int_key(it);
        SIMLINK_send_message_multi(&slep->obj, num_dsts, dst_ids, msg);
}

#define CHECK_SENDER(slep)                                               \
        ASSERT(slep);                                                    \
        if (!slep->is_sender) {                                          \
                SIM_LOG_ERROR(&slep->obj, 0, "receiver trying to send"); \
                return;                                                  \
        }

static void
raise(conf_object_t *obj)
{
        signal_link_endpoint_t *slep = (signal_link_endpoint_t *)obj;
        CHECK_SENDER(slep);
        SIM_LOG_INFO(3, &slep->obj, 0, "raise");
        signal_link_message_t *msg = new_signal_message(Signal_Raise);
        send_message(slep, &msg->common);
}

static void
lower(conf_object_t *obj)
{
        signal_link_endpoint_t *slep = (signal_link_endpoint_t *)obj;
        CHECK_SENDER(slep);
        SIM_LOG_INFO(3, &slep->obj, 0, "lower");
        signal_link_message_t *msg = new_signal_message(Signal_Lower);
        send_message(slep, &msg->common);
}

static attr_value_t
get_ep_type(void *user_data, conf_object_t *obj, attr_value_t *idx)
{
        signal_link_endpoint_t *slep = (signal_link_endpoint_t *)obj;
        if (slep->is_sender)
                return SIM_make_attr_string("sender");
        else
                return SIM_make_attr_string("receiver");
}

static set_error_t
set_ep_type(void *user_data, conf_object_t *obj,
            attr_value_t *val, attr_value_t *idx)
{
        if (SIM_object_is_configured(obj))
                return Sim_Set_Not_Writable;
        signal_link_endpoint_t *slep = (signal_link_endpoint_t *)obj;
        const char *type = SIM_attr_string(*val);
        if (strcmp(type, "sender") == 0) {
                slep->is_sender = true;
                return Sim_Set_Ok;
        } else if (strcmp(type, "receiver") == 0) {
                slep->is_sender = false;
                return Sim_Set_Ok;
        } else {
                return Sim_Set_Illegal_Value;
        }
}

void
init_local()
{
        SIMLINK_init_library();

        const class_data_t link_cls_funcs = {
                .alloc_object = signal_link_alloc_object,
                .init_object = signal_link_init_object,
                .finalize_instance = signal_link_finalize_instance,
                .pre_delete_instance = signal_link_pre_delete_instance,
                .delete_instance = signal_link_delete_instance,
                .class_desc = "model of link for simple signals",
                .description = "A link that propagates simple signals."
        };
        conf_class_t *link_cls = SIM_register_class("signal_link_impl",
                                                    &link_cls_funcs);
        SIMLINK_register_class(link_cls);

        const class_data_t ep_cls_funcs = {
                .alloc_object = signal_link_ep_alloc_object,
                .init_object = signal_link_ep_init_object,
                .finalize_instance = signal_link_ep_finalize_instance,
                .pre_delete_instance = signal_link_ep_pre_delete_instance,
                .delete_instance = signal_link_ep_delete_instance,
                .class_desc = "signal link endpoint",
                .description = "Signal link endpoint"
        };
        ep_cls = SIM_register_class("signal_link_endpoint", &ep_cls_funcs);
        SIMLINK_register_endpoint_class(ep_cls, "[s]|[si]");
        SIM_register_typed_attribute(
                ep_cls, "type", get_ep_type, NULL, set_ep_type, NULL,
                Sim_Attr_Required, "s", NULL,
                "Endpoint type (\"sender\" or \"receiver\").");
        static const signal_interface_t sl_iface = {
                .signal_raise = raise,
                .signal_lower = lower,
        };
        SIM_register_interface(ep_cls, SIGNAL_INTERFACE, &sl_iface);
}
