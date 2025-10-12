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

static conf_class_t *ep_cls; /* the eth-cable link endpoint class */

typedef struct {
        common_link_t clink;
} cable_link_t;

typedef struct {
        common_link_endpoint_t cep;
        const ethernet_cable_interface_t *cable;
} cable_ep_t;

typedef enum { Cable_Frame, Cable_Status } cable_link_msg_type_t;

typedef struct {
        link_message_t common;
        cable_link_msg_type_t msgtype;
        union {
                struct {
                        bytes_t frame;
                        bool crc_correct;
                } f;
                bool link_up;
        } u;
} cable_link_message_t;

/* Create a new frame message, taking ownership of the given data. */
static link_message_t *
new_frame_message(size_t len, const void *data, bool crc_correct)
{
        cable_link_message_t *msg = MM_MALLOC(1, cable_link_message_t);
        SIMLINK_init_message(&msg->common);
        msg->msgtype = Cable_Frame;
        msg->u.f.frame.len = len;
        msg->u.f.frame.data = data;
        msg->u.f.crc_correct = crc_correct;
        return &msg->common;
}

static cable_link_message_t *
new_status_message(bool link_up)
{
        cable_link_message_t *msg = MM_MALLOC(1, cable_link_message_t);
        SIMLINK_init_message(&msg->common);
        msg->msgtype = Cable_Status;
        msg->u.link_up = link_up;
        return msg;
}

static void
free_message(conf_object_t *link, link_message_t *_msg)
{
        cable_link_message_t *msg = (cable_link_message_t *)_msg;
        if (msg->msgtype == Cable_Frame)
                MM_FREE((uint8 *)msg->u.f.frame.data);
        MM_FREE(msg);
}

static attr_value_t
cable_to_attr(conf_object_t *link, const link_message_t *msgdata)
{
        cable_link_message_t *msg = (cable_link_message_t *)msgdata;
        switch (msg->msgtype) {
        case Cable_Frame:
                return SIM_make_attr_list(
                        3, 
                        SIM_make_attr_string("frame"),
                        SIM_make_attr_data(msg->u.f.frame.len,
                                           msg->u.f.frame.data),
                        SIM_make_attr_boolean(msg->u.f.crc_correct));
        case Cable_Status:
                return SIM_make_attr_list(
                        2, 
                        SIM_make_attr_string("status"),
                        SIM_make_attr_boolean(msg->u.link_up));
        }
        ASSERT(0);
}

static link_message_t *
cable_from_attr(conf_object_t *link, attr_value_t attr)
{
        const char *type = SIM_attr_string(SIM_attr_list_item(attr, 0));
        if (strcmp(type, "frame") == 0) {
                attr_value_t d = SIM_attr_list_item(attr, 1);
                attr_value_t crc_correct = SIM_attr_list_item(attr, 2);
                uint8 *frame = MM_MALLOC(SIM_attr_data_size(d), uint8);
                memcpy(frame, SIM_attr_data(d), SIM_attr_data_size(d));
                return new_frame_message(SIM_attr_data_size(d), frame,
                                         SIM_attr_boolean(crc_correct));
        } else if (strcmp(type, "status") == 0) {
                return &new_status_message(
                        SIM_attr_boolean(SIM_attr_list_item(attr, 1)))->common;
        } else {
                ASSERT(0);
        }
}

static void
cable_marshal(conf_object_t *link, const link_message_t *_msg,
              void (*finish)(void *data, const frags_t *msg), 
              void *finish_data)
{
        const cable_link_message_t *msg = (const cable_link_message_t *)_msg;
        uint32 msgtype;
        uint32 status;
        uint32 crc_correct;

        STORE_BE32(&msgtype, msg->msgtype);
        frags_t buf;
        frags_init_add(&buf, &msgtype, 4);

        if (msg->msgtype == Cable_Status) {
                STORE_BE32(&status, msg->u.link_up);
                frags_add(&buf, &status, 4);
        } else {
                STORE_BE32(&crc_correct, msg->u.f.crc_correct);
                frags_add(&buf, &crc_correct, 4);
                frags_add(&buf, msg->u.f.frame.data, msg->u.f.frame.len);
        }

        finish(finish_data, &buf);
}

static link_message_t *
cable_unmarshal(conf_object_t *link, const frags_t *msg)
{
        size_t msg_len = frags_len(msg);

        ASSERT(msg_len >= 4);
        cable_link_msg_type_t msgtype = frags_extract_be32(msg, 0);

        if (msgtype == Cable_Frame) {
                bool crc_correct = frags_extract_be32(msg, 4);
                size_t frame_len = msg_len - 8;
                uint8 *frame_data = frags_extract_slice_alloc(msg, 8, 
                                                              frame_len);
                return new_frame_message(frame_len, frame_data, crc_correct);
        } else {
                ASSERT(msg_len == 8);
                return &new_status_message(frags_extract_be32(msg, 4))->common;
        }
}

#define BUFFER_T(buf) (buffer_t){ .len = sizeof(buf), .data = buf }

static void
deliver_cable(conf_object_t *ep, const link_message_t *msgdata)
{
        cable_ep_t *cbep = (cable_ep_t *)ep;
        uint8 buf[1000];
        SIM_LOG_INFO(3, &cbep->cep.obj, 0, "delivering to %s",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));

        cable_link_message_t *msg = (cable_link_message_t *)msgdata;
        switch (msg->msgtype) {
        case Cable_Frame: {
                frags_t frame;
                frags_init_add(&frame, msg->u.f.frame.data, msg->u.f.frame.len);
                deliver_frame(ep, &frame, msg->u.f.crc_correct);
                break;
        }
        case Cable_Status:
                if (SIMLINK_endpoint_is_device(ep)) {
                        if (cbep->cable) {
                                cbep->cable->link_status(
                                        SIMLINK_endpoint_device(ep),
                                        msg->u.link_up);
                        } else {
                                SIM_LOG_INFO(
                                        2, &cbep->cep.obj, 0,
                                        "status message dropped;"
                                        " %s doesn't implement %s",
                                        SIMLINK_endpoint_dev_name(
                                                ep, BUFFER_T(buf)),
                                        ETHERNET_CABLE_INTERFACE);
                        }
                } else {
                        /* Do nothing. */
                }
                break;
        }
}

static void
cable_ep_device_changed(conf_object_t *ep, conf_object_t *old_dev)
{
        ep_device_changed(ep, old_dev);
        cable_ep_t *cbep = (cable_ep_t *)ep;
        const ethernet_cable_interface_t *cable_iface =
                SIM_c_get_port_interface(
                        SIMLINK_endpoint_device(ep),
                        ETHERNET_CABLE_INTERFACE, 
                        SIMLINK_endpoint_port(ep));
        /* cable_iface will be NULL here if the device doesn't support
           the cable interface */
        cbep->cable = cable_iface;
}

static conf_object_t *
cable_link_alloc_object(void *data)
{
        cable_link_t *cblink = MM_ZALLOC(1, cable_link_t);
        return &cblink->clink.obj;
}

static void *
cable_link_init_object(conf_object_t *obj, void *data)
{
        static const link_type_t cable_link_type = {
                .free_msg = free_message,
                .msg_to_attr = cable_to_attr,
                .msg_from_attr = cable_from_attr,
                .marshal = cable_marshal,
                .unmarshal = cable_unmarshal,
                .deliver = deliver_cable,
                .device_changed = cable_ep_device_changed
        };
        static const eth_funcs_t cable_eth_funcs = {
                .new_frame_message = new_frame_message
        };

        cable_link_t *cblink = (cable_link_t *)obj;
        common_eth_link_init(&cblink->clink,
                             &cable_link_type, &cable_eth_funcs);
        cblink->clink.bpds = NULL;
        return cblink;
}

static void
cable_pre_delete_instance(conf_object_t *obj)
{
        cable_link_t *cblink = (cable_link_t *)obj;
        tear_down_network_breakpoints(&cblink->clink);
        common_pre_delete_instance(obj);
}

static conf_object_t *
cable_ep_alloc_object(void *data)
{
        cable_ep_t *cbep = MM_ZALLOC(1, cable_ep_t);
        return &cbep->cep.obj;
}

static void *
cable_ep_init_object(conf_object_t *obj, void *data)
{
        cable_ep_t *cbep = (cable_ep_t *)obj;
        common_eth_ep_constructor(&cbep->cep, false);
        return cbep;
}

static void
cable_ep_finalize_instance(conf_object_t *ep)
{
        ep_finalize_instance(ep);
}

static void
cable_ep_pre_delete_instance(conf_object_t *obj)
{
        cable_ep_t *cbep = (cable_ep_t *)obj;
        common_eth_ep_destructor(&cbep->cep);
}

static int
cable_ep_delete_instance(conf_object_t *obj)
{
        MM_FREE(obj);
        return 0; /* this return value is ignored */
}

static void
set_status(conf_object_t *ep, bool link_up)
{
        cable_ep_t *cbep = (cable_ep_t *)ep;
        SIM_LOG_INFO(3, &cbep->cep.obj, 0, "set_status: %s",
                     link_up ? "link up" : "link down");
        cable_link_message_t *msg = new_status_message(link_up);
        SIMLINK_send_message(ep, LINK_BROADCAST_ID, &msg->common);
}

static int64
cable_bp_add(conf_object_t *obj, bytes_t src_mac, bytes_t dst_mac,
             int eth_type, break_net_cb_t cb, bool once, int64 bp_id)
{
        cable_link_t *cl = SIM_object_data(obj);
        return bp_add(obj, src_mac, dst_mac, eth_type, cb, &(cl->clink), bp_id,
                      once);
}

static void
cable_bp_remove(conf_object_t *obj, int64 bp_id)
{
        cable_link_t *cl = SIM_object_data(obj);
        bp_remove(obj, &(cl->clink), bp_id);
}

void
init_eth_cable_link()
{
        const class_data_t link_cls_funcs = {
                .alloc_object = cable_link_alloc_object,
                .init_object = cable_link_init_object,
                .finalize_instance = link_finalize_instance,
                .pre_delete_instance = cable_pre_delete_instance,
                .delete_instance = common_delete_instance,
                .class_desc = "model of Ethernet cable link",
                .description = "Ethernet cable link"
        };
        conf_class_t *link_cls = SIM_register_class("eth-cable-link",
                                                    &link_cls_funcs);
        SIMLINK_register_class(link_cls);
        register_ethernet_common_link_interfaces(link_cls, 0);

        const class_data_t ep_cls_funcs = {
                .alloc_object = cable_ep_alloc_object,
                .init_object = cable_ep_init_object,
                .finalize_instance = cable_ep_finalize_instance,
                .pre_delete_instance = cable_ep_pre_delete_instance,
                .delete_instance = cable_ep_delete_instance,
                .class_desc = "an Ethernet cable link endpoint",
                .description = "Ethernet cable link endpoint"
        };
        ep_cls = SIM_register_class("eth-cable-link-endpoint", &ep_cls_funcs);
        SIMLINK_register_endpoint_class(ep_cls, "[sdb]|[sb]");
        register_ethernet_common_ep_interfaces(ep_cls, broadcast_frame);
        static const ethernet_cable_interface_t eth_cable_iface =
                { .link_status = set_status };
        SIM_register_interface(ep_cls, ETHERNET_CABLE_INTERFACE,
                               &eth_cable_iface);
        static const network_breakpoint_interface_t break_net = {
                .add    = cable_bp_add,
                .remove = cable_bp_remove,
        };
        SIM_REGISTER_INTERFACE(link_cls, network_breakpoint, &break_net);
}
