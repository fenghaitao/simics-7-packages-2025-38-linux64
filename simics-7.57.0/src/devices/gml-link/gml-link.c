/*
  © 2015 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <stdlib.h>

#include <simics/module-host-config.h>
#include <simics/base/types.h>
#include <simics/base/conf-object.h>
#include <simics/devs/liblink.h>
#include <simics/util/hashtab.h>

#include "generic-message-interfaces.h"

/* THREAD_SAFE_GLOBAL: frame_delay_event init */
static event_class_t *frame_delay_event = NULL;

typedef VECT(uint64) gml_endpoint_list_t;

typedef struct {
        conf_object_t obj;
        /* destination address is key, gml_endpoint_list_t is value */
        ht_int_table_t receivers;
} gml_link_t;

typedef struct {
        conf_object_t obj;
} gml_link_endpoint_t;

typedef struct {
        link_message_t common;
        bytes_t payload;
} gml_link_message_t;

typedef struct {
        uint32 address;
        link_message_t *msg;
} event_data_t;

static link_message_t *
new_gml_message(const uint8 *data, size_t len)
{
        gml_link_message_t *m = MM_MALLOC(1, gml_link_message_t);
        SIMLINK_init_message(&m->common);
        uint8 *d = MM_MALLOC(len, uint8);
        memcpy(d, data, len);
        m->payload = (bytes_t){.data = d, .len = len};
        return &m->common;
}

static void
free_msg(conf_object_t *link, link_message_t *lm)
{
        gml_link_message_t *m = (gml_link_message_t *)lm;
        MM_FREE((uint8 *)m->payload.data);
        m->payload.data = NULL;
        MM_FREE(m);
}

static attr_value_t
msg_to_attr(conf_object_t *link, const link_message_t *lm)
{
        const gml_link_message_t *m = (const gml_link_message_t *)lm;
        return SIM_make_attr_data(m->payload.len, m->payload.data);
}

static link_message_t *
msg_from_attr(conf_object_t *link, attr_value_t attr)
{
        return new_gml_message(SIM_attr_data(attr), SIM_attr_data_size(attr));
}

static void
marshal(conf_object_t *link, const link_message_t *lm,
        void (*finish)(void *data, const frags_t *msg),
        void *finish_data)
{
        const gml_link_message_t *m = (const gml_link_message_t *)lm;
        frags_t buf;
        frags_init_add(&buf, m->payload.data, m->payload.len);
        finish(finish_data, &buf);
}

static link_message_t *
unmarshal(conf_object_t *link, const frags_t *data)
{
        size_t len = frags_len(data);
        uint8 bytes[len];
        frags_extract(data, bytes);
        return new_gml_message(bytes, len);
}

static const generic_message_device_interface_t *
get_gml_device_interface(conf_object_t *ep)
{
        conf_object_t *dev;
        const char *port;
        const generic_message_device_interface_t *iface;
        port = SIMLINK_endpoint_port(ep);
        dev = SIMLINK_endpoint_device(ep);
        iface = SIM_c_get_port_interface(dev,
                GENERIC_MESSAGE_DEVICE_INTERFACE, port);
        return iface;
}

static void
deliver(conf_object_t *ep, const link_message_t *lm)
{
        conf_object_t *dev;
        const generic_message_device_interface_t *iface;
        const gml_link_message_t *m = (const gml_link_message_t *)lm;
        dbuffer_t *frame;

        /* check if EP is connected to device */
        if (!SIMLINK_endpoint_is_device(ep))
                return;

        iface = get_gml_device_interface(ep);
        dev = SIMLINK_endpoint_device(ep);
        frame = new_dbuffer();
        dbuffer_append_data(frame, m->payload.data, m->payload.len);
        iface->receive_frame(dev, ep, frame);
        dbuffer_free(frame);
}

static void
link_config_value_updated(conf_object_t *link, const char *key,
                          const frags_t *msg)
{
        gml_link_t *gl = (gml_link_t *)link;
        uint64 ep_id = strtoull(key, NULL, 16);
        uint32 address;
        gml_endpoint_list_t *eps;

        address = frags_extract_be32(msg, 0);
        SIM_LOG_INFO(2, &gl->obj, 0, "add endpoint: ep%llx, address 0x%x",
                     ep_id, address);
        eps = (gml_endpoint_list_t *)ht_lookup_int(&gl->receivers, address);
        if (eps == NULL) {
                eps = MM_MALLOC(1, gml_endpoint_list_t);
                VINIT(*eps);
                ht_update_int(&gl->receivers, address, eps);
        }
        VADD(*eps, ep_id);
}

static void
link_config_value_removed(conf_object_t *link, const char *key)
{

        gml_link_t *gl = (gml_link_t *)link;
        uint64 ep_id = strtoull(key, NULL, 16);

        HT_FOREACH_INT(&gl->receivers, it) {
                gml_endpoint_list_t *eps;
                eps = (gml_endpoint_list_t *)ht_iter_int_value(it);
                VREMOVE_FIRST_MATCH(*eps, ep_id);
        }
}

static void
device_changed(conf_object_t *ep, conf_object_t *old_dev)
{
        const generic_message_device_interface_t *iface;
        SIM_LOG_INFO(2, ep, 0, "device changed");
        iface = get_gml_device_interface(ep);
        if (iface == NULL)
                SIM_LOG_ERROR(ep, 0, "Device does not implement %s interface",
                              GENERIC_MESSAGE_DEVICE_INTERFACE);
}

static conf_object_t *
gml_link_alloc_object(void *data)
{
        gml_link_t *gl = MM_ZALLOC(1, gml_link_t);
        return &gl->obj;
}

static void *
gml_link_init_object(conf_object_t *obj, void *data)
{
        gml_link_t *gl = (gml_link_t *)obj;

        static const link_type_t link_methods = {
                .msg_to_attr = msg_to_attr,
                .msg_from_attr = msg_from_attr,
                .free_msg = free_msg,
                .marshal = marshal,
                .unmarshal = unmarshal,
                .deliver = deliver,
                .update_config_value = link_config_value_updated,
                .remove_config_value = link_config_value_removed,
                .device_changed = device_changed
        };
        SIMLINK_init(&gl->obj, &link_methods);
        ht_init_int_table(&gl->receivers);
        return &gl->obj;
}

static void
gml_link_finalize_instance(conf_object_t *obj)
{
        SIMLINK_finalize(obj);
}

static void
gml_link_pre_delete_instance(conf_object_t *obj)
{
        SIMLINK_pre_delete(obj);
}

static int
gml_link_delete_instance(conf_object_t *obj)
{
        gml_link_t *gl = (gml_link_t *)obj;
        HT_FOREACH_INT(&gl->receivers, it)
                VFREE(*(gml_endpoint_list_t *)ht_iter_int_value(it));
        ht_delete_int_table(&gl->receivers, true);
        MM_FREE(obj);
        return 0;
}

static int
connect_device(conf_object_t *obj, conf_object_t *dev,
               int *new_connection, uint32 address)
{
        char ep_id[17];
        frags_t value;
        uint8 buf[4];

        snprintf(ep_id, sizeof(ep_id), "%llx", SIMLINK_endpoint_id(obj));
        STORE_BE32((uint32 *)buf, address);
        frags_init_add(&value, buf, sizeof(address));
        SIMLINK_config_update_value(SIMLINK_endpoint_link(obj), ep_id, &value);

        return SIMLINK_endpoint_id(obj);
}

static void
disconnect_device(conf_object_t *obj, conf_object_t *dev)
{
        char ep_id[17];
        snprintf(ep_id, sizeof(ep_id), "%llx", SIMLINK_endpoint_id(obj));
        SIMLINK_config_remove_value(SIMLINK_endpoint_link(obj), ep_id);
}

static void
send_frame_to_link(conf_object_t *obj, event_data_t *edata)
{
        gml_endpoint_list_t *eps;
        uint32 address = edata->address;
        link_message_t *msg = edata->msg;
        gml_link_t *gl = (gml_link_t *)SIMLINK_endpoint_link(obj);

        eps = (gml_endpoint_list_t *)ht_lookup_int(&gl->receivers, address);

        if (eps == NULL) {
                SIM_LOG_INFO(2, obj, 0,
                             "cannot find endpoint(s) with address 0x%x",
                             address);
        } else {
                /* Remove self from list */
                gml_endpoint_list_t filter_eps = VNULL;
                VCOPY(filter_eps, *eps);
                VREMOVE_FIRST_MATCH(filter_eps, SIMLINK_endpoint_id(obj));

                if (VLEN(filter_eps) == 0) {
                        SIM_LOG_INFO(4, obj, 0,
                                     "this endpoint is only one with address"
                                     " 0x%x", address);
                } else {
                        SIM_LOG_INFO(4, obj, 0,
                                     "sending message to eps with address 0x%x",
                                     address);
                        SIMLINK_send_message_multi(
                                obj, VLEN(filter_eps), VVEC(filter_eps), msg);
                }
                VFREE(filter_eps);
        }
        MM_FREE(edata);
}

static void
send_frame(conf_object_t *obj, int id, uint32 address,
           dbuffer_t *frame, nano_secs_t delay)
{
        event_data_t *edata = MM_MALLOC(1, event_data_t);
        uint8 buf[dbuffer_len(frame)];
        edata->address = address;
        memcpy(buf, dbuffer_read_all(frame), dbuffer_len(frame));
        edata->msg = new_gml_message(buf, dbuffer_len(frame));
        if (delay) {
                double time = delay / 1E9;
                SIM_LOG_INFO(4, obj, 0,
                             "frame to address 0x%x delayed by %f ns",
                             address, time);
                SIM_event_post_time(
                        SIM_object_clock(SIMLINK_endpoint_device(obj)),
                        frame_delay_event, obj,
                        time, edata);
        } else
                send_frame_to_link(obj, edata);
}

static void
delay_callback(conf_object_t *obj, lang_void *data)
{
        send_frame_to_link(obj, (event_data_t *)data);
}

static void
delay_destroy(conf_object_t *obj, lang_void *data)
{
        event_data_t *edata = (event_data_t *)data;
        free_msg(SIMLINK_endpoint_link(obj), edata->msg);
        MM_FREE(edata);
}

static attr_value_t
delay_get_value(conf_object_t *obj, lang_void *data)
{
        event_data_t *edata = (event_data_t *)data;
        return SIM_make_attr_list(
                2,
                SIM_make_attr_uint64(edata->address),
                msg_to_attr(NULL, edata->msg));
}

static lang_void *
delay_set_value(conf_object_t *obj, attr_value_t value)
{
        event_data_t *edata = MM_MALLOC(1, event_data_t);
        edata->address = SIM_attr_integer(SIM_attr_list_item(value, 0));
        edata->msg = msg_from_attr(NULL, SIM_attr_list_item(value, 1));
        return edata;
}

static conf_object_t *
gml_link_endpoint_alloc_object(void *data)
{
        gml_link_endpoint_t *ep =
                MM_ZALLOC(1, gml_link_endpoint_t);
        return &ep->obj;
}

static void *
gml_link_endpoint_init_object(conf_object_t *obj, void *data)
{
        gml_link_endpoint_t *ep =
                (gml_link_endpoint_t *)obj;
        SIMLINK_endpoint_init(&ep->obj, false);
        return ep;
}

static void
gml_link_endpoint_finalize_instance(conf_object_t *ep)
{
        SIMLINK_endpoint_finalize(ep);
}

static int
gml_link_endpoint_delete_instance(conf_object_t *ep)
{
        MM_FREE(ep);
        return 0;
}

void
init_local()
{
        SIMLINK_init_library();

        const class_data_t cl_methods = {
                .alloc_object = gml_link_alloc_object,
                .init_object = gml_link_init_object,
                .finalize_instance = gml_link_finalize_instance,
                .pre_delete_instance = gml_link_pre_delete_instance,
                .delete_instance = gml_link_delete_instance,
                .class_desc = "general message link",
                .description = "A link that broadcasts byte strings."
        };
        conf_class_t *cl = SIM_register_class("gml_link_impl",
                                              &cl_methods);
        SIMLINK_register_class(cl);

        const class_data_t epcl_methods = {
                .alloc_object = gml_link_endpoint_alloc_object,
                .init_object = gml_link_endpoint_init_object,
                .finalize_instance = gml_link_endpoint_finalize_instance,
                .pre_delete_instance = SIMLINK_endpoint_disconnect,
                .delete_instance = gml_link_endpoint_delete_instance,
                .class_desc = "endpoint for a general message link",
                .description = "Endpoint for gml_link objects."
        };
        conf_class_t *epcl = SIM_register_class("gml_link_endpoint",
                                                &epcl_methods);

        frame_delay_event = SIM_register_event(
                "frame delay",
                epcl,
                Sim_EC_No_Flags,
                delay_callback,
                delay_destroy,
                delay_get_value,
                delay_set_value,
                NULL);

        static const generic_message_link_interface_t gml_if = {
                .connect_device = connect_device,
                .disconnect_device = disconnect_device,
                .send_frame = send_frame
        };
        SIM_register_interface(epcl, GENERIC_MESSAGE_LINK_INTERFACE, &gml_if);

        SIMLINK_register_endpoint_class(epcl, "d");
}
