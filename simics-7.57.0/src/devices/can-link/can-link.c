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
#include <simics/devs/liblink.h>
#include "can-interface.h"

typedef struct {
        link_message_t common;
        can_frame_t    can_frame;
} can_link_message_t;

typedef struct {
    conf_object_t obj;
} can_endpoint_t;

typedef struct {
        conf_object_t obj;
} can_link_impl_t;

static link_message_t *
new_can_message(can_frame_t *can_frame)
{
        can_link_message_t *m = MM_MALLOC(1, can_link_message_t);
        ASSERT(m != NULL);

        SIMLINK_init_message(&m->common);
        m->can_frame.extended    = can_frame->extended;
        m->can_frame.identifier  = can_frame->identifier;
        m->can_frame.rtr         = can_frame->rtr;
        m->can_frame.data_length = can_frame->data_length;
        m->can_frame.crc         = can_frame->crc;

        memcpy(m->can_frame.data, can_frame->data, CAN_DATA_MAX_NUM);

        return &m->common;
}

static void
print_can_frame(conf_object_t *obj, can_frame_t *m)
{
        SIM_LOG_INFO(4, obj, 0,
                     "extended: %s, identifier: %d, rtr: %d,"
                     " data_length: %d,"
                     " data: %02x %02x %02x %02x %02x %02x %02x %02x,"
                     " crc: %d",
                     (m->extended) ? "True" : "False",
                     m->identifier,
                     ((m->rtr) ? 1 : 0),
                     m->data_length,
                     m->data[0], m->data[1], m->data[2], m->data[3],
                     m->data[4], m->data[5], m->data[6], m->data[7],
                     m->crc);
}

static attr_value_t
msg_to_attr(conf_object_t *link, const link_message_t *msg)
{
        can_link_message_t *m = (can_link_message_t *) msg;
        attr_value_t attr_frame;

        attr_frame = SIM_make_attr_list(5,
                       SIM_make_attr_uint64(m->can_frame.identifier),
                       SIM_make_attr_boolean(m->can_frame.extended),
                       SIM_make_attr_boolean(m->can_frame.rtr),
                       SIM_make_attr_data(m->can_frame.data_length,
                                          m->can_frame.data),
                       SIM_make_attr_uint64(m->can_frame.crc));

        return attr_frame;
}

static link_message_t *
msg_from_attr(conf_object_t *link, attr_value_t attr)
{
        attr_value_t attr_can_frame = attr;
        /* Restore Data/Remote Frame */
        can_frame_t can_frame;
        int item_pos = 0;
        
        can_frame.identifier =
              SIM_attr_integer(SIM_attr_list_item(attr_can_frame, item_pos++));
        can_frame.extended =
              SIM_attr_boolean(SIM_attr_list_item(attr_can_frame, item_pos++));
        can_frame.rtr =
              SIM_attr_boolean(SIM_attr_list_item(attr_can_frame, item_pos++));

        /* Restore data */
        attr_value_t attr_data;
        const uint8 *data_buf;
        attr_data = SIM_attr_list_item(attr_can_frame, item_pos++);
        data_buf  = SIM_attr_data(attr_data);
        can_frame.data_length = SIM_attr_data_size(attr_data);
        memcpy(can_frame.data, data_buf, can_frame.data_length);

        /* Restore CRC */
        can_frame.crc =
              SIM_attr_integer(SIM_attr_list_item(attr_can_frame, item_pos++));

        return new_can_message(&can_frame);
}

static void
free_msg(conf_object_t *link, link_message_t *msg)
{
        can_link_message_t *m = (can_link_message_t *) msg;
        MM_FREE(m);
}

static void
marshal(conf_object_t *link, const link_message_t *msg,
        void(*finish)(void *data, const frags_t *msg), void *finish_data)
{
        can_link_message_t * m = (can_link_message_t *) msg;
        frags_t buf;

        uint8 bytes[17];
        
        UNALIGNED_STORE_LE32(&bytes[0], m->can_frame.identifier);
        UNALIGNED_STORE_LE8(&bytes[4], m->can_frame.extended);
        UNALIGNED_STORE_LE8(&bytes[5], m->can_frame.rtr);
        UNALIGNED_STORE_LE8(&bytes[6], m->can_frame.data_length);
        memcpy(&bytes[7], m->can_frame.data, CAN_DATA_MAX_NUM);
        UNALIGNED_STORE_LE16(&bytes[15], m->can_frame.crc);
        frags_init_add(&buf, &bytes[0], 17);
        
        finish(finish_data, &buf);
}

static link_message_t *
unmarshal(conf_object_t *link, const frags_t *msg)
{
        can_frame_t can_frame;
        int32 data_pointer = 0;

        /* extract frame identifier */
        can_frame.identifier = frags_extract_le32(msg, data_pointer);
        data_pointer         = data_pointer + 4;

        /* extract frame extended flag */
        can_frame.extended = (bool) frags_extract_8(msg, data_pointer);
        data_pointer       = data_pointer + 1;

        /* extract frame rtr */
        can_frame.rtr = (bool) frags_extract_8(msg, data_pointer);
        data_pointer  = data_pointer + 1;

        /* extract frame data length */
        can_frame.data_length = frags_extract_8(msg, data_pointer);
        data_pointer          = data_pointer + 1;

        /* extract frame data */
        frags_extract_slice(msg,
                            can_frame.data,
                            data_pointer,
                            CAN_DATA_MAX_NUM);
        data_pointer += CAN_DATA_MAX_NUM;

        /* extract frame CRC */
        can_frame.crc = frags_extract_le16(msg, data_pointer);

        return new_can_message(&can_frame);
}

static can_device_interface_t *
get_can_device_interface(conf_object_t *endpoint)
{
        const char *port = SIMLINK_endpoint_port(endpoint);
        can_device_interface_t *iface  = NULL;
        iface = (can_device_interface_t *) SIM_c_get_port_interface(
                SIMLINK_endpoint_device(endpoint), "can_device", port);
        return iface;
}

static void
deliver(conf_object_t *endpoint, const link_message_t *msg)
{
        can_device_interface_t *iface = NULL;
        
        SIM_LOG_INFO(3, endpoint, 0, "receive message from link");

        can_link_message_t * m = (can_link_message_t *) msg;
        print_can_frame(endpoint, &m->can_frame);
        
        iface = get_can_device_interface(endpoint);
        if (iface != NULL) {
                iface->receive(SIMLINK_endpoint_device(endpoint),
                                                       &m->can_frame);
        } else {
                SIM_LOG_ERROR(endpoint, 0, "can_device interface is"
                                     " unimplemented in the attached device.");
        }
}

static void
update_config_value(conf_object_t *link, const char *key,
        const frags_t *value)
{
        /* do nothing */
}

static void
remove_config_value(conf_object_t *link, const char *key)
{
        /* do nothing */
}

static void
device_changed(conf_object_t *endpoint, conf_object_t *old_dev)
{
        SIM_LOG_INFO(3, endpoint, 0, "device changed");

        can_device_interface_t *iface = get_can_device_interface(endpoint);
        if (iface == NULL) {
                SIM_LOG_ERROR(endpoint, 0, "connected device need"
                        " to implement [can_device] interface");
        }
}

static void *
can_link_impl_init_object(conf_object_t *link, void *data)
{
        static const link_type_t link_methods = {
                      .msg_to_attr         = msg_to_attr,
                      .msg_from_attr       = msg_from_attr,
                      .free_msg            = free_msg,
                      .marshal             = marshal,
                      .unmarshal           = unmarshal,
                      .deliver             = deliver,
                      .update_config_value = update_config_value,
                      .remove_config_value = remove_config_value,
                      .device_changed      = device_changed };

        can_link_impl_t *can_link_impl = (can_link_impl_t*) link;
        SIMLINK_init(&(can_link_impl->obj), &link_methods);
        return &(can_link_impl->obj);
}

static conf_object_t *
can_link_impl_alloc_object(void *data)
{
        can_link_impl_t *can_link_impl = MM_ZALLOC(1, can_link_impl_t);
        return &can_link_impl->obj;
}

static void
can_link_impl_finalize_instance(conf_object_t *link)
{
        SIMLINK_finalize(link);
}

static void
can_link_impl_pre_delete_instance(conf_object_t *link)
{
        SIMLINK_pre_delete(link);
}

static int
can_link_impl_delete_instance(conf_object_t *link)
{
        MM_FREE(link);
        return 0;
}

static conf_object_t *
can_endpoint_alloc_object(void *data)
{
        can_endpoint_t *can_ep = MM_ZALLOC(1, can_endpoint_t);
        return &can_ep->obj;
}

static void *
can_endpoint_init_object(conf_object_t *endpoint, void *data)
{
        can_endpoint_t *can_ep = (can_endpoint_t *)endpoint;
        SIMLINK_endpoint_init(&can_ep->obj, false);
        return &can_ep->obj;
}

static void
can_endpoint_finalize_instance(conf_object_t *endpoint)
{
        SIMLINK_endpoint_finalize(endpoint);
}

static int
can_endpoint_delete_instance(conf_object_t *endpoint)
{
        MM_FREE(endpoint);
        return 0; /* this return value is ignored */
}

static can_status_t
send_can_frame(conf_object_t *endpoint, can_frame_t *frame)
{
        SIM_LOG_INFO(3, endpoint, 0, "receive request of sending frame");

        /* Distribute Data/Remote frame */
        SIMLINK_send_message(endpoint, LINK_BROADCAST_ID,
                             new_can_message(frame));
        return Can_Status_No_Error;
}

void init_local()
{
        /* The link library must always be initialised first. */
        SIMLINK_init_library();

        const class_data_t link_class_methods = {
                .alloc_object        = can_link_impl_alloc_object,
                .init_object         = can_link_impl_init_object,
                .finalize_instance   = can_link_impl_finalize_instance,
                .pre_delete_instance = can_link_impl_pre_delete_instance,
                .delete_instance     = can_link_impl_delete_instance,
                .class_desc          = "model of CAN link",
                .description         = "Distributed CAN link implementation" };
        conf_class_t *link_class
                = SIM_register_class("can_link_impl", &link_class_methods);
        SIMLINK_register_class(link_class);

        const class_data_t endpoint_class_methods = {
             .alloc_object        = can_endpoint_alloc_object,
             .init_object         = can_endpoint_init_object,
             .finalize_instance   = can_endpoint_finalize_instance,
             .pre_delete_instance = SIMLINK_endpoint_disconnect,
             .delete_instance     = can_endpoint_delete_instance,
             .class_desc          = "model of CAN endpoint",
             .description         = "Distributed CAN endpoint implementation" };
        conf_class_t *endpoint_class = SIM_register_class("can_endpoint",
                &endpoint_class_methods);
        SIMLINK_register_endpoint_class(endpoint_class, "[ibbdi]");

        static const can_link_interface_t can_link_if = {
                                                .send = send_can_frame };
        SIM_register_interface(endpoint_class, "can_link", &can_link_if);
}
