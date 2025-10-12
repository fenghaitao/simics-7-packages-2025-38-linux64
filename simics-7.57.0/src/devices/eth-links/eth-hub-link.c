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
#include <simics/devs/ethernet.h>
#include <simics/base/log.h>

#include "common.h"

static conf_class_t *ep_cls; /* the eth-hub link endpoint class */

typedef struct {
        common_link_t clink;
} hub_link_t;

typedef struct {
        common_link_endpoint_t cep;
} hub_ep_t;

typedef struct {
        link_message_t common;
        bytes_t frame;
        bool crc_correct;
} hub_link_message_t;

/* Create a new message, taking ownership of the given data. */
static link_message_t *
new_message(size_t len, const void *data, bool crc_correct)
{
        hub_link_message_t *msg = MM_MALLOC(1, hub_link_message_t);
        SIMLINK_init_message(&msg->common);
        msg->frame.len = len;
        msg->frame.data = data;
        msg->crc_correct = crc_correct;
        return &msg->common;
}

static void
free_message(conf_object_t *link, link_message_t *_msg)
{
        hub_link_message_t *msg = (hub_link_message_t *)_msg;
        MM_FREE((uint8 *)msg->frame.data);
        MM_FREE(msg);
}

static attr_value_t
hub_to_attr(conf_object_t *link, const link_message_t *msgdata)
{
        hub_link_message_t *msg = (hub_link_message_t *)msgdata;
        return SIM_make_attr_list(
                2,
                SIM_make_attr_data(msg->frame.len, msg->frame.data),
                SIM_make_attr_boolean(msg->crc_correct));
}

static link_message_t *
hub_from_attr(conf_object_t *link, attr_value_t attr)
{
        attr_value_t d = SIM_attr_list_item(attr, 0);
        attr_value_t crc_correct = SIM_attr_list_item(attr, 1);
        uint8 *frame = MM_MALLOC(SIM_attr_data_size(d), uint8);
        memcpy(frame, SIM_attr_data(d), SIM_attr_data_size(d));
        return new_message(SIM_attr_data_size(d), frame,
                           SIM_attr_boolean(crc_correct));
}

static void
hub_marshal(conf_object_t *link, const link_message_t *_msg,
              void (*finish)(void *data, const frags_t *msg), 
              void *finish_data)
{
        const hub_link_message_t *msg = (const hub_link_message_t *)_msg;
        uint32 crc_correct;
        STORE_BE32(&crc_correct, msg->crc_correct);

        frags_t buf;
        frags_init_add(&buf, &crc_correct, 4);
        frags_add(&buf, msg->frame.data, msg->frame.len);
        finish(finish_data, &buf);
}

static link_message_t *
hub_unmarshal(conf_object_t *link, const frags_t *msg)
{
        uint32 crc_correct = frags_extract_be32(msg, 0);
        return new_message(frags_len(msg) - 4, 
                           frags_extract_slice_alloc(msg, 4, 
                                                     frags_len(msg) - 4),
                           crc_correct);
}

/* <add id="hub_deliver"><insert-upto text="(buf)));"/></add> */
#define BUFFER_T(buf) (buffer_t){ .len = sizeof(buf), .data = buf }

static void
deliver_hub(conf_object_t *ep, const link_message_t *msgdata)
{
        uint8 buf[1000];
        SIM_LOG_INFO(3, ep, 0, "delivering to %s",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));

        hub_link_message_t *msg = (hub_link_message_t *)msgdata;
        frags_t frame;
        frags_init_add(&frame, msg->frame.data, msg->frame.len);
        deliver_frame(ep, &frame, msg->crc_correct);
}

static conf_object_t *
hub_link_alloc_object(void *data)
{
        hub_link_t *hlink = MM_ZALLOC(1, hub_link_t);
        return &hlink->clink.obj;
}

static void
hub_pre_delete_instance(conf_object_t *obj)
{
        hub_link_t *hlink = (hub_link_t *)obj;
        tear_down_network_breakpoints(&hlink->clink);
        common_pre_delete_instance(obj);
}

static void *
hub_link_init_object(conf_object_t *obj, void *data)
{
        static const link_type_t hub_link_type = {
                .free_msg = free_message,
                .msg_to_attr = hub_to_attr,
                .msg_from_attr = hub_from_attr,
                .marshal = hub_marshal,
                .unmarshal = hub_unmarshal,
                .deliver = deliver_hub,
                .device_changed = ep_device_changed
        };
        static const eth_funcs_t hub_eth_funcs = {
                .new_frame_message = new_message
        };

        hub_link_t *hlink = (hub_link_t *)obj;
        common_eth_link_init(&hlink->clink,
                             &hub_link_type, &hub_eth_funcs);
        hlink->clink.bpds = NULL;
        return hlink;
}

static conf_object_t *
hub_ep_alloc_object(void *data)
{
        hub_ep_t *hep = MM_ZALLOC(1, hub_ep_t);
        return &hep->cep.obj;
}

static void *
hub_ep_init_object(conf_object_t *obj, void *data)
{
        hub_ep_t *hep = (hub_ep_t *)obj;
        common_eth_ep_constructor(&hep->cep, false);
        return hep;
}

static void
hub_ep_pre_delete_instance(conf_object_t *obj)
{
        hub_ep_t *hep = (hub_ep_t *)obj;
        common_eth_ep_destructor(&hep->cep);
}

static int
hub_ep_delete_instance(conf_object_t *obj)
{
        MM_FREE(obj);
        return 0; /* this return value is ignored */
}

static int64
hub_bp_add(conf_object_t *obj, bytes_t src_mac, bytes_t dst_mac,
           int eth_type, break_net_cb_t cb, bool once, int64 bp_id)
{

        hub_link_t *hl = SIM_object_data(obj);
        return bp_add(obj, src_mac, dst_mac, eth_type, cb, &(hl->clink),
                      bp_id, once);
}

static
void hub_bp_remove(conf_object_t *obj, int64 bp_id)
{
        hub_link_t *hl = SIM_object_data(obj);
        bp_remove(obj, &(hl->clink), bp_id);
}

void
init_eth_hub_link()
{
        const class_data_t cls_funcs = {
                .alloc_object = hub_link_alloc_object,
                .init_object = hub_link_init_object,
                .finalize_instance = link_finalize_instance,
                .pre_delete_instance = hub_pre_delete_instance,
                .delete_instance = common_delete_instance,
                .class_desc = "model of broadcasting Ethernet link",
                .description = "Simple broadcasting Ethernet link"
        };
        conf_class_t *link_cls = SIM_register_class("eth-hub-link", &cls_funcs);
        SIMLINK_register_class(link_cls);
        register_ethernet_common_link_interfaces(link_cls, 0);

        const class_data_t ep_cls_funcs = {
                .alloc_object = hub_ep_alloc_object,
                .init_object = hub_ep_init_object,
                .finalize_instance = ep_finalize_instance,
                .pre_delete_instance = hub_ep_pre_delete_instance,
                .delete_instance = hub_ep_delete_instance,
                .class_desc = "an Ethernet hub link endpoint",
                .description = "Ethernet hub link endpoint"
        };
        ep_cls = SIM_register_class("eth-hub-link-endpoint", &ep_cls_funcs);
        SIMLINK_register_endpoint_class(ep_cls, "[db]");
        register_ethernet_common_ep_interfaces(ep_cls, broadcast_frame);

        static const network_breakpoint_interface_t break_net = {
                .add    = hub_bp_add,
                .remove = hub_bp_remove,
        };
        SIM_REGISTER_INTERFACE(link_cls, network_breakpoint, &break_net);
}
