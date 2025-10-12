/*
  © 2017 Intel Corporation

  This software and the related documents are Intel copyrighted materials, and
  your use of them is governed by the express license under which they were
  provided to you ("License"). Unless the License provides otherwise, you may
  not use, modify, copy, publish, distribute, disclose or transmit this software
  or the related documents without Intel's prior written permission.

  This software and the related documents are provided as is, with no express or
  implied warranties, other than those that are expressly stated in the License.
*/

#include <simics/device-api.h>
#include <simics/util/hashtab.h>
#include <simics/devs/liblink.h>
#include <simics/devs/i3c.h>

#define INVALID_ADDRESS 0xffff

typedef struct {
        conf_object_t obj;
        int num_devs;
} i3c_cable_impl_t;

typedef struct {
        conf_object_t obj;
        const i3c_slave_interface_t *if_slave;
        const i3c_master_interface_t *if_master;
        const i3c_daa_snoop_interface_t *if_snoop;
} i3c_cable_endpoint_t;

typedef enum {
        I3C_Msg_Start = 0,
        I3C_Msg_IBI_Request,
        I3C_Msg_IBI_Start,
        I3C_Msg_IBI_Address,
        I3C_Msg_IBI_Acknowledge,
        I3C_Msg_Acknowledge,
        I3C_Msg_Stop,
        I3C_Msg_Read,
        I3C_Msg_Daa_Read,
        I3C_Msg_Write,
        I3C_Msg_Sdr_Write,
        I3C_Msg_Read_Response,
        I3C_Msg_Daa_Response,
        I3C_Msg_Daa_Address,
} i3c_cable_message_type_t;

typedef struct {
        link_message_t common;
        i3c_cable_message_type_t type;
        uint8 value;
        union {
                bool more;
                uint64 daa_data;
                i3c_ack_t ack;
        } u;
        uint32 length;
        uint8* payload;
} i3c_cable_message_t;

#define BUFFER_T(buf) (buffer_t){ .len = sizeof(buf), .data = buf }
#define CABLE_LOG(ep, ...)                                      \
do {                                                            \
        i3c_cable_impl_t *cable =                               \
                (i3c_cable_impl_t*) SIMLINK_endpoint_link(ep);  \
        uint8 buf[1000];                                        \
        buffer_t buffer = {                                     \
                .len = 1000,                                    \
                .data = buf                                     \
        };                                                      \
        SIM_LOG_INFO(3, &cable->obj, 0, __VA_ARGS__,            \
                     SIMLINK_endpoint_dev_name(ep, buffer));    \
} while (false)

static i3c_cable_message_t *
new_cable_message(i3c_cable_message_type_t type,
                 uint8 value, uint32 length, const uint8 *data)
{
        i3c_cable_message_t *msg = MM_ZALLOC(1, i3c_cable_message_t);
        SIMLINK_init_message(&msg->common);
        msg->type = type;
        msg->value = value;
        if (length > 0) {
                msg->length = length;
                msg->payload = MM_ZALLOC(length, uint8);
                memcpy(msg->payload, data, length);
        }
        return msg;
}

static void
free_cable_message(conf_object_t *link, link_message_t *lmsg)
{
        i3c_cable_message_t *msg = (i3c_cable_message_t *)lmsg;
        if (msg->length > 0) {
                MM_FREE(msg->payload);
                msg->payload = NULL;
        }
        MM_FREE(lmsg);
}

static link_message_t *
attr_to_msg(conf_object_t *link, attr_value_t attr)
{
        i3c_cable_message_type_t type =
                SIM_attr_integer(SIM_attr_list_item(attr, 0));
        uint8 value = SIM_attr_integer(SIM_attr_list_item(attr, 1));
        uint64 d64 = SIM_attr_integer(SIM_attr_list_item(attr, 2));
        attr_value_t data = SIM_attr_list_item(attr, 3);
        uint32 length = SIM_attr_data_size(data);
        i3c_cable_message_t *msg =
                new_cable_message(type, value, length, SIM_attr_data(data));
        msg->u.daa_data = d64;
        return &msg->common;
}

static attr_value_t
msg_to_attr(conf_object_t *link, const link_message_t *lmsg)
{
        i3c_cable_message_t *msg = (i3c_cable_message_t *)lmsg;
        return SIM_make_attr_list(
                        4,
                        SIM_make_attr_int64(msg->type),
                        SIM_make_attr_int64(msg->value),
                        SIM_make_attr_int64(msg->u.daa_data),
                        SIM_make_attr_data(msg->length, msg->payload));
}

static void
marshal(conf_object_t *link, const link_message_t *lmsg,
        void (*finish)(void *data, const frags_t *msg), void *finish_data)
{
        const i3c_cable_message_t *msg = (i3c_cable_message_t *)lmsg;
        frags_t frame;
        uint32 len = msg->length + 14;
        uint8 *buffer = MM_ZALLOC(len, uint8);

        buffer[0] = msg->type;
        buffer[1] = msg->value;
        UNALIGNED_STORE_LE64(&buffer[2], msg->u.daa_data);
        UNALIGNED_STORE_LE32(&buffer[10], msg->length);
        if (msg->length > 0)
                memcpy(&buffer[14], msg->payload, msg->length);
        frags_init_add(&frame, buffer, len);
        finish(finish_data, &frame);
}

static link_message_t *
unmarshal(conf_object_t *link, const frags_t *frame)
{
        i3c_cable_message_type_t type = frags_extract_8(frame, 0);
        uint8 value = frags_extract_8(frame, 1);
        uint64 d64 = frags_extract_le64(frame, 2);
        uint32 length = frags_extract_le32(frame, 10);
        uint8 *buffer = NULL;
        if (length > 0) {
                buffer = MM_ZALLOC(length, uint8);
                frags_extract_slice(frame, buffer, 14, length);
        }
        i3c_cable_message_t *msg =
                new_cable_message(type, value, length, buffer);
        msg->u.daa_data = d64;
        if (buffer)
                MM_FREE(buffer);
        return &msg->common;
}

static void
deliver(conf_object_t *ep_obj, const link_message_t *lmsg)
{
        i3c_cable_message_t *msg = (i3c_cable_message_t *) lmsg;
        i3c_cable_endpoint_t *ep = (i3c_cable_endpoint_t *) ep_obj;
        CABLE_LOG(ep_obj, "delivering i3c message (type %d) to %s", msg->type);
        conf_object_t *dev = SIMLINK_endpoint_device(ep_obj);
        bytes_t payload;
        switch (msg->type) {
        case I3C_Msg_Start:
                ep->if_slave->start(dev, msg->value);
                break;
        case I3C_Msg_IBI_Acknowledge:
                ep->if_slave->ibi_acknowledge(dev, msg->u.ack);
                break;
        case I3C_Msg_IBI_Start:
                ep->if_slave->ibi_start(dev);
                break;
        case I3C_Msg_Stop:
                ep->if_slave->stop(dev);
                break;
        case I3C_Msg_Read:
                ep->if_slave->read(dev);
                break;
        case I3C_Msg_Daa_Read:
                ep->if_slave->daa_read(dev);
                break;
        case I3C_Msg_Write:
                ep->if_slave->write(dev, msg->value);
                break;
        case I3C_Msg_Sdr_Write:
                payload.len = msg->length;
                payload.data = msg->payload;
                ep->if_slave->sdr_write(dev, payload);
                break;
        case I3C_Msg_Acknowledge:
                ep->if_master->acknowledge(dev, msg->u.ack);
                break;
        case I3C_Msg_IBI_Address:
                ep->if_master->ibi_address(dev, msg->value);
                break;
        case I3C_Msg_IBI_Request:
                ep->if_master->ibi_request(dev);
                break;
        case I3C_Msg_Read_Response:
                ep->if_master->read_response(dev, msg->value, msg->u.more);
                break;
        case I3C_Msg_Daa_Response:
                ep->if_master->daa_response(dev, msg->u.daa_data >> 16,
                                            (msg->u.daa_data >> 8) & 0xff,
                                            msg->u.daa_data & 0xff);
                break;
        case I3C_Msg_Daa_Address:
                if (ep->if_snoop) {
                        ep->if_snoop->assigned_address(
                                        dev,
                                        msg->u.daa_data >> 16,
                                        (msg->u.daa_data >> 8) & 0xff,
                                        msg->u.daa_data & 0xff,
                                        msg->value);
                }
                break;
        default:
                ASSERT(0);
        }
}

static void
endpoint_device_changed(conf_object_t *obj, conf_object_t *old_dev)
{
        i3c_cable_endpoint_t *ep = (i3c_cable_endpoint_t *)obj;
        conf_object_t *dev = SIMLINK_endpoint_device(obj);
        const char *port = SIMLINK_endpoint_port(obj);
        const i3c_slave_interface_t *slave =
                SIM_C_GET_PORT_INTERFACE(dev, i3c_slave, port);
        const i3c_master_interface_t *master =
                SIM_C_GET_PORT_INTERFACE(dev, i3c_master, port);
        const i3c_daa_snoop_interface_t *snoop =
                SIM_C_GET_PORT_INTERFACE(dev, i3c_daa_snoop, port);
        if (slave == NULL && master == NULL) {
                uint8 buf[1000];
                SIM_LOG_ERROR(&ep->obj, 0,
                              "The device '%s' should at least implement "
                              "one of interfaces i3c_master and i3c_slave",
                              SIMLINK_endpoint_dev_name(obj, BUFFER_T(buf)));
                return;
        }

        ep->if_slave = slave;
        ep->if_master = master;
        ep->if_snoop = snoop;
}

static conf_object_t *
cable_alloc_object(void *arg)
{
        i3c_cable_impl_t *cable = MM_ZALLOC(1, i3c_cable_impl_t);
        return &cable->obj;
}

static void
link_config_value_updated(conf_object_t *obj, const char *key,
                          const frags_t *msg)
{
        i3c_cable_impl_t *link = (i3c_cable_impl_t *)obj;
        link->num_devs += 1;
        SIM_LOG_INFO(4, &link->obj, 0,
                     "add one more device, now in total %d endpoint(s)",
                     link->num_devs);
}

static void
link_config_value_removed(conf_object_t *obj, const char *key)
{
        i3c_cable_impl_t *link = (i3c_cable_impl_t *)obj;
        link->num_devs -= 1;
        SIM_LOG_INFO(4, &link->obj, 0,
                     "Remove one device, now in total %d endpoint(s)",
                     link->num_devs);
}

static void *
cable_init_object(conf_object_t *obj, void *arg)
{
        static const link_type_t cable_type = {
                .free_msg = free_cable_message,
                .msg_to_attr = msg_to_attr,
                .msg_from_attr = attr_to_msg,
                .marshal = marshal,
                .unmarshal = unmarshal,
                .deliver = deliver,
                .update_config_value = link_config_value_updated,
                .remove_config_value = link_config_value_removed,
                .device_changed = endpoint_device_changed
        };

        i3c_cable_impl_t *cable = (i3c_cable_impl_t *)obj;
        cable->num_devs = 0;
        SIMLINK_init(&cable->obj, &cable_type);
        return &cable->obj;
}

static void
cable_finalize_instance(conf_object_t *obj)
{
        SIMLINK_finalize(obj);
}

static void
cable_pre_delete_instance(conf_object_t *obj)
{
        SIMLINK_pre_delete(obj);
}

static int
cable_delete_instance(conf_object_t *obj)
{
        i3c_cable_impl_t *cable = (i3c_cable_impl_t *)obj;
        MM_FREE(cable);
        return 0;
}

static conf_object_t *
ep_alloc_object(void *arg)
{
        i3c_cable_endpoint_t *ilep = MM_ZALLOC(1, i3c_cable_endpoint_t);
        return &ilep->obj;
}

static void *
ep_init_object(conf_object_t *obj, void *arg)
{
        i3c_cable_endpoint_t *ep = (i3c_cable_endpoint_t *)obj;
        SIMLINK_endpoint_init(&ep->obj, false);
        return &ep->obj;
}

static void
cable_ep_finalize_instance(conf_object_t *ep)
{
        SIMLINK_endpoint_finalize(ep);
}

static void
cable_ep_pre_delete_instance(conf_object_t *ep)
{
        SIMLINK_endpoint_disconnect(ep);
}

static int
cable_ep_delete_instance(conf_object_t *obj)
{
        MM_FREE(obj);
        return 0;
}

static void
i3c_send_message(conf_object_t *obj, i3c_cable_message_t *msg)
{
        SIMLINK_send_message(obj, LINK_BROADCAST_ID, &msg->common);
}

static void
i3c_master_acknowledge(conf_object_t *obj, i3c_ack_t ack)
{
        CABLE_LOG(obj, "i3c acknowledge (%d) from %s", ack);
        i3c_cable_message_t *msg =
                new_cable_message(I3C_Msg_Acknowledge, 0, 0, NULL);
        msg->u.ack = ack;
        i3c_send_message(obj, msg);
}

static void
i3c_master_ibi_request(conf_object_t *obj)
{
        CABLE_LOG(obj, "IBI request from from %s");
        i3c_cable_impl_t *link = (i3c_cable_impl_t*)SIMLINK_endpoint_link(obj);
        if (link->num_devs == 1)
                return;
        i3c_send_message(obj,
                         new_cable_message(I3C_Msg_IBI_Request, 0, 0, NULL));
}

static void
i3c_master_ibi_address(conf_object_t *obj, uint8 address)
{
        CABLE_LOG(obj, "IBI address (0x%x) from from %s", address);
        i3c_send_message(obj, new_cable_message(I3C_Msg_IBI_Address,
                                                address, 0, NULL));
}

static void
i3c_master_read_response(conf_object_t *obj, uint8 data, bool more)
{
        CABLE_LOG(obj, "read response from %s");
        i3c_cable_message_t *msg =
                new_cable_message(I3C_Msg_Read_Response, data, 0, NULL);
        msg->u.more = more;
        i3c_send_message(obj, msg);
}

static void
i3c_master_daa_response(conf_object_t *obj, uint64 id, uint8 bcr, uint8 dcr)
{
        CABLE_LOG(obj, "daa response from %s");
        i3c_cable_message_t *msg =
                new_cable_message(I3C_Msg_Daa_Response, 0, 0, NULL);
        msg->u.daa_data = (id << 16) | (bcr << 8) | dcr;
        i3c_send_message(obj, msg);
}

static void
i3c_slave_stop(conf_object_t *obj)
{
        CABLE_LOG(obj, "i3c stop from %s");
        i3c_send_message(obj, new_cable_message(I3C_Msg_Stop, 0, 0, NULL));
}

static void
i3c_slave_start(conf_object_t *obj, uint8 address)
{
        CABLE_LOG(obj,"start (0x%x) from %s", address);
        i3c_cable_impl_t *link = (i3c_cable_impl_t*)SIMLINK_endpoint_link(obj);
        if (link->num_devs == 1) {
                i3c_cable_endpoint_t *ep = (i3c_cable_endpoint_t *)obj;
                ep->if_master->acknowledge(SIMLINK_endpoint_device(obj),
                                           I3C_noack);
                return;
        }
        i3c_send_message(obj, new_cable_message(I3C_Msg_Start,
                                                address, 0, NULL));
}
static void
i3c_slave_read(conf_object_t *obj)
{
        CABLE_LOG(obj,"read request from %s");
        i3c_send_message(obj, new_cable_message(I3C_Msg_Read, 0, 0, NULL));
}

static void
i3c_slave_daa_read(conf_object_t *obj)
{
        CABLE_LOG(obj, "daa read request from %s");
        i3c_send_message(obj, new_cable_message(I3C_Msg_Daa_Read, 0, 0, NULL));
}

static void
i3c_slave_write(conf_object_t *obj, uint8 value)
{
        CABLE_LOG(obj, "write request (0x%x) from %s", value);
        i3c_send_message(obj, new_cable_message(I3C_Msg_Write, value, 0, NULL));
}

static void
i3c_slave_sdr_write(conf_object_t *obj, bytes_t data)
{
        CABLE_LOG(obj, "sdr write request from %s");
        i3c_cable_message_t *msg =
                new_cable_message(I3C_Msg_Sdr_Write, 0, data.len, data.data);
        i3c_send_message(obj, msg);
}

static void
i3c_slave_ibi_acknowledge(conf_object_t *obj, i3c_ack_t ack) {
        CABLE_LOG(obj, "IBI acknowledge (%d) from %s", ack);
        i3c_cable_message_t *msg =
                new_cable_message(I3C_Msg_IBI_Acknowledge, 0, 0, NULL);
        msg->u.ack = ack;
        i3c_send_message(obj, msg);
}

static void
i3c_slave_ibi_start(conf_object_t *obj)
{
        CABLE_LOG(obj, "IBI start from %s");
        i3c_send_message(obj,
                         new_cable_message(I3C_Msg_IBI_Start, 0, 0, NULL));
}

static void
i3c_daa_snoop_assigned_address(conf_object_t *obj, uint64 id,
                                   uint8 bcr, uint8 dcr, uint8 address)
{
        CABLE_LOG(obj, "daa broadcast from from %s");
        i3c_cable_impl_t *link = (i3c_cable_impl_t*)SIMLINK_endpoint_link(obj);
        if (link->num_devs == 1)
                return;

        i3c_cable_message_t *msg =
                new_cable_message(I3C_Msg_Daa_Address, address, 0, NULL);
        msg->u.daa_data = (id << 16) | (bcr << 8) | dcr;
        i3c_send_message(obj, msg);
}

void
init_i3c_cable()
{
        const class_data_t cable_cls_funcs = {
                .alloc_object = cable_alloc_object,
                .init_object = cable_init_object,
                .finalize_instance = cable_finalize_instance,
                .pre_delete_instance = cable_pre_delete_instance,
                .delete_instance = cable_delete_instance,
                .class_desc = "model of I3C cable link",
                .description = "I3C cable link"
        };
        conf_class_t *link_cls = SIM_register_class("i3c_cable_impl",
                                                    &cable_cls_funcs);
        SIMLINK_register_class(link_cls);

        const class_data_t ep_cls_funcs = {
                .alloc_object = ep_alloc_object,
                .init_object = ep_init_object,
                .finalize_instance = cable_ep_finalize_instance,
                .pre_delete_instance = cable_ep_pre_delete_instance,
                .delete_instance = cable_ep_delete_instance,
                .class_desc = "model of I3C cable link endpoint",
                .description = "I3C cable link endpoint"
        };
        conf_class_t *ep_cls = SIM_register_class("i3c_cable_endpoint",
                                                  &ep_cls_funcs);
        SIMLINK_register_endpoint_class(ep_cls, "[iiid]");

        static const i3c_master_interface_t i3c_master = {
                .acknowledge = i3c_master_acknowledge,
                .daa_response = i3c_master_daa_response,
                .read_response = i3c_master_read_response,
                .ibi_request = i3c_master_ibi_request,
                .ibi_address = i3c_master_ibi_address,
        };
        SIM_register_interface(ep_cls, I3C_MASTER_INTERFACE, &i3c_master);

        static const i3c_slave_interface_t i3c_slave = {
                .start = i3c_slave_start,
                .read = i3c_slave_read,
                .daa_read = i3c_slave_daa_read,
                .write  = i3c_slave_write,
                .sdr_write = i3c_slave_sdr_write,
                .stop = i3c_slave_stop,
                .ibi_start = i3c_slave_ibi_start,
                .ibi_acknowledge = i3c_slave_ibi_acknowledge,
        };
        SIM_register_interface(ep_cls, I3C_SLAVE_INTERFACE, &i3c_slave);

        static i3c_daa_snoop_interface_t i3c_daa_snoop = {
                .assigned_address = i3c_daa_snoop_assigned_address
        };
        SIM_register_interface(ep_cls, I3C_DAA_SNOOP_INTERFACE,
                               &i3c_daa_snoop);
}

#undef BUFFER_T
#undef CABLE_LOG
