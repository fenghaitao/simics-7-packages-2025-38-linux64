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

#include "i2c-link-v2.h"
#include <simics/device-api.h>

#include <simics/util/hashtab.h>
#include <simics/simulator/control.h>

typedef struct {
        conf_object_t obj;
        unsigned num_slaves; /* Number of slave endpoints */
} i2c_link_impl_t;

typedef struct {
        conf_object_t obj;

        const i2c_master_v2_interface_t *master_iface;
        const i2c_slave_v2_interface_t *slave_iface;

        /* Endpoint IDs of devices from which we are waiting for a start
           response. Start responses are a bit tricky, because a master needs
           to get responses from all slave devices before it knows the result
           (a noack can only be sent if all slave devices have responded with
           noack). This is handled as follows:

           - The start is broadcast to all endpoints, and in addition a message
             is sent to the posting master.

           - Each slave endpoint sends a response immediately. If no response
             is retrieved from the slave immediately, the endpoint will send a
             start_response_pending message immediately, and send the real
             response when it is ready.

           - When start_response_pending messages arrive to the master
             endpoint, the ID of the slave endpoints are stored in the
             pending_start_responses list.

           - When the real responses arrive from slaves, the corresponding
             entry is removed from pending_start_responses. When the list is
             empty, the master knows that it got a response from all slaves.
        */
        VECT(uint64) pending_start_responses;

        /* Endpoint IDs of devices which acknowledge general call address or
           10-bit address.

           General call address can be acknowledged by multiple slaves, slaves
           acknowledged will behave as slave-receiver and keep receiving the
           second and following bytes.

           10-bit addressing transaction begins with start write request
           containing 10-bit address pattern. Multiple slaves can acknowledge
           it. Following first start request, a write request with second byte
           of address is sent. No more than one ack will be received for this
           write request. If slave behaves as slave-receiver, then slave will
           receive the following bytes. If slave behaves as slave-transmitter,
           then a restart request with first byte of 10-bit address will be
           sent, and slave will transmit the following bytes.

           This is handled as follows:

           - General call or 10-bit address (first byte) is broadcast to all
             endpoints. If general call, attribute address_pattern will be set
             to 0. If 10-bit address, the request status will be saved in
             address_pattern, and a message is sent to the posting master.

           - Each slave endpoint sends a response. If a slave device requires
             data from a general call address or matches the first two bits of
             10-bit address, it will acknowledge the call. Otherwise, noack
             will be sent.

           - The endpoint can send a start_response_pending message if no
             response is retrieved from the slave immediately.

           - For each endpoint acknowledged, the ID is stored in the slave_list
             list.

           - For general call, the second and following bytes will keep sending
             out to slave devices according to the IDs listed in slave_list. A
             slave who cannot process one of these bytes ignore it by sending
             noack. But the following bytes will still send to it.

           - For 10-bit addressing, a write request with second byte of address
             will send out to slaves listed in slave_list. Slaves that respond
             with noack will be removed from slave_list. After handling all the
             write responses, no more than one slave in slave_list. If slave
             behaves as slave-transmitter, a restart read request with first
             address will send to slave in slave_list, otherwise, a write
             (data) request will send to slave in slave_list. The following
             steps will perform as normal transaction.

           - If the list is empty, or no slave is acknowledging, nothing will
             send out and a stop is needed for the master device.
        */
        VECT(uint64) slave_list;

        /* Keep track of how many responses we are still waiting from slave
           devices. It will set initially according to the number of slave
           endpoint IDs in slave_list list. Then when a response is received,
           the counter will decrement by 1. When counter is zero, meaning all
           slaves have responded and the ack/noack can be sent to master device.
        */
        uint8 slave_list_counter;

        /* General call acknowledge or 10-bit address acknowledge.
           It is the final ack/noack send to master device when all slaves
           in slave_list have responded. If any slave responded with ack,
           this general call acknowledge or 10-bit address acknowledge is set
           to ack. Otherwise, a noack will be sent to master device connected.
        */
        i2c_ack_t slave_list_ack;

        /* Save status for start request. If general call, it will be set to 0.
           If 10-bit address, it will save the first byte of 10-bit address.
           Otherwise, it will be -1.
        */
        int16 address_pattern;

        /* Endpoint ID connected with current active master */
        uint64 current_master;

        /* If a single slave device is connected, then this is its endpoint
           ID. Otherwise (i.e., when bus is idle, or when master waits for a
           start response), it is 0. Some special cases:
           - During General Call, it is 0
           - In 10-bit addressing, write mode, it is 0 until after the second
             address byte, after which it's the ID of the single slave device.
           - If the second address byte is followed by a repeated start in
             'read' mode, i.e., 10-bit read transaction is initiated, then the
             slave's endpoint ID is retained in current_slave. current_slave is
             otherwise 0 after a repeated start.
        */
        uint64 current_slave;

        /* Poor man's cell-local storage, used to detect whether a response is
           received synchronously.
        */
        bool waiting_for_synchronous_response;

        /* Current i2c link state */
        i2c_link_state_t state;

        /* Current number of i2c slave endpoints pending for start response.
           It is only valid in i2c master endpoints. Internal attribute.
           pending_slaves in master endpoint will be set to the number of
           slave endpoints according to num_slaves parameter of link when
           handling start request. The values will decrease each time a slave
           response was received. When the value reaches 0, the master knows
           it has got all slave responses.
        */
        unsigned pending_slaves;
} i2c_link_endpoint_t;

typedef struct {
        link_message_t common;
        uint64 src_epid;                     /* Sender's endpoint ID */
        i2c_link_action_type_t type;                  /* i2c command */
        uint64 status;    /* Either address, data or response status */
} i2c_link_message_t;

/* Link methods */

static inline i2c_link_message_t *
msg_to_lmsg(const link_message_t *msg)
{
        return (i2c_link_message_t *)msg;
}

static inline i2c_link_impl_t *
obj_to_ilink(conf_object_t *link)
{
        return (i2c_link_impl_t *)link;
}

static inline i2c_link_endpoint_t *
obj_to_ep(conf_object_t *ep)
{
        return (i2c_link_endpoint_t *)ep;
}

static inline conf_object_t *
ep_to_obj(i2c_link_endpoint_t *ep) { return &ep->obj; }

static link_message_t *
new_status_message(uint64 src_epid, i2c_link_action_type_t type, uint64 status)
{
        i2c_link_message_t *msg = MM_MALLOC(1, i2c_link_message_t);
        SIMLINK_init_message(&msg->common);
        msg->src_epid = src_epid;
        msg->type = type;
        msg->status = status;
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
        i2c_link_message_t *msg = msg_to_lmsg(msgdata);
        return SIM_make_attr_list(3,
                                  SIM_make_attr_uint64(msg->src_epid),
                                  SIM_make_attr_uint64(msg->type),
                                  SIM_make_attr_uint64(msg->status));
}

static link_message_t *
msg_from_attr(conf_object_t *link, attr_value_t attr)
{
        uint64 src_epid = SIM_attr_integer(SIM_attr_list_item(attr, 0));
        i2c_link_action_type_t type = SIM_attr_integer(
                SIM_attr_list_item(attr, 1));
        uint64 status = SIM_attr_integer(SIM_attr_list_item(attr, 2));
        return new_status_message(src_epid, type, status);
}

static void
marshal(conf_object_t *link, const link_message_t *_msg,
        void (*finish)(void *data, const frags_t *msg), void *finish_data)
{
        i2c_link_message_t *msg = msg_to_lmsg(_msg);
        uint8 data[8 + 1 + 8];
        frags_t buf;

        UNALIGNED_STORE_BE64(data, msg->src_epid);
        UNALIGNED_STORE_BE8(data + 8, msg->type);
        UNALIGNED_STORE_BE64(data + 9, msg->status);
        frags_init_add(&buf, data, 8 + 1 + 8);

        finish(finish_data, &buf);
}

static link_message_t *
unmarshal(conf_object_t *link, const frags_t *msg)
{
        size_t msg_len = frags_len(msg);

        ASSERT(msg_len == 8 + 1 + 8);
        uint64 src_epid = frags_extract_be64(msg, 0);
        i2c_link_action_type_t type = frags_extract_8(msg, 8);
        uint64 status = frags_extract_be64(msg, 9);
        return new_status_message(src_epid, type, status);
}

/* Return the name of the device on a given link and its endpoint id */
static const char *
ep_dev_name(conf_object_t *ep, uint64 id)
{
        conf_object_t *link = SIMLINK_endpoint_link(ep);
        ASSERT(link);
        conf_object_t *remote_ep = SIMLINK_find_endpoint_by_id(link, id);
        if (!remote_ep)
                return "<endpoint deleted>";
        conf_object_t *remote_obj = SIMLINK_endpoint_device(remote_ep);
        if (!remote_obj)
                return "<device disconnected>";

        return SIM_object_name(remote_obj);
}

static void
handle_remote_start_request(i2c_link_endpoint_t *ilep, i2c_link_message_t *msg,
                            conf_object_t *device)
{
        conf_object_t *ep = ep_to_obj(ilep);
        const uint64 current_epid = SIMLINK_endpoint_id(ep);
        uint64 epid_from = msg->src_epid;
        uint32 addr = msg->status;

        if (ilep->current_master == 0
            || ilep->current_master == epid_from) {
                /* First master during idle, or repeated start from currently
                   active master. The master that sent this start request will
                   be the active master */
                ilep->current_master = epid_from;
                if (current_epid == epid_from) {
                        ilep->state = (addr & 1) == 1
                                ? state_wait_rsp_start_r
                                : state_wait_rsp_start_w;

                        conf_object_t *link = SIMLINK_endpoint_link(ep);
                        i2c_link_impl_t *ilink = obj_to_ilink(link);
                        /* Init pending slave number to num_slaves */
                        ilep->pending_slaves = ilink->num_slaves;

                        /* If current ep also implements slave interface,
                           the total number of slaves waiting response should
                           decrease by 1. */
                        if (ilep->slave_iface) {
                                ASSERT(ilep->pending_slaves > 0);
                                ilep->pending_slaves -= 1;
                        }

                        /* If no slaves in current configuration, simply
                           send noack. */
                        if (ilep->pending_slaves == 0) {
                                SIM_LOG_INFO(
                                        2, ep, 0,
                                        "No slaves in current configuration,"
                                        " noacking start request");
                                ilep->state = state_wait_stop;
                                ilep->master_iface->acknowledge(
                                        device, I2C_noack);
                        }
                } else {
                        if (ilep->slave_iface) {
                                /* A master on some other endpoint becomes the
                                   active master, forward its start to
                                   this device */
                                ilep->state = (addr & 1) == 1
                                        ? state_wait_rsp_start_r
                                        : state_wait_rsp_start_w;
                                ilep->current_slave = 0;

                                SIM_LOG_INFO(
                                        4, ep, 0,
                                        "Forwarding request to device");
                                ilep->waiting_for_synchronous_response = true;
                                ilep->slave_iface->start(device, addr);

                                if (ilep->waiting_for_synchronous_response) {
                                        SIM_LOG_INFO(
                                                4, ep, 0,
                                                "Did not get synchronous"
                                                " start response, delaying"
                                                " response");
                                        SIMLINK_send_message(
                                                ep, ilep->current_master,
                                                new_status_message(
                                                        SIMLINK_endpoint_id(ep),
                                                        start_response_pending,
                                                        0));
                                }
                        } else if (ilep->state == state_wait_remote_start_rsp) {
                                /* A request from the local device just lost
                                   the arbitration. Normally this should be
                                   reported by responding with another start()
                                   call instead of acknowledge(), but if a
                                   master device was not written with
                                   multi-master in mind, it might not implement
                                   i2c_slave_v2. It is then an error that the
                                   master device is part of a multi-master
                                   configuration. */
                                SIM_LOG_ERROR(
                                        ep, 0,
                                        "Master device lost bus arbitration,"
                                        " but does not implement the "
                                        I2C_SLAVE_V2_INTERFACE
                                        " interface. The interface is required"
                                        " in multi-master configurations."
                                        " Responding with a faked NOACK.");
                                ilep->master_iface->acknowledge(
                                        device, I2C_noack);
                                /* Actually we should expect a stop
                                   and then ignore it */
                                ilep->state = state_idle;
                        }
                }
        }
}

static bool
is_10bit(int addr) {
        return (addr & 0xf8) == 0xf0;
}

static bool
is_hs(int addr) {
        return (addr & 0xf8) == 0x08;
}

static void
deliver(conf_object_t *ep, const link_message_t *msgdata)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(ep);
        const uint64 current_epid = SIMLINK_endpoint_id(ep);

        conf_object_t *device = SIMLINK_endpoint_device(ep);
        uint8 buf[1000];
        SIM_LOG_INFO(2, ep, 0, "Delivering to %s",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));

        i2c_link_message_t *msg = msg_to_lmsg(msgdata);
        uint64 epid_from = msg->src_epid;
        bool broadcast = ilep->address_pattern == 0
                || is_10bit(ilep->address_pattern);
        SIM_LOG_INFO(4, ep, 0,
                     "Got message from %s: type(%s), data(%lld)%s",
                     ep_dev_name(ep, epid_from), i2c_type_name(msg->type),
                     msg->status,
                     !ilep->address_pattern
                     ? " in general call mode" : "");

        uint32 msg_data = 0;
        switch (msg->type) {
        case start_request:
                /* Start request, broadcasted to all endpoints */
                handle_remote_start_request(ilep, msg, device);
                break;

        case start_response_pending:
                VADD(ilep->pending_start_responses, epid_from);
                break;

        case start_response: {
                bool restart_10bit_read = broadcast
                        && ilep->state == state_wait_rsp_start_r;
                if (msg->status == I2C_ack) {
                        if (broadcast && !restart_10bit_read) {
                                /* General call or 10-bit address: epid_from is
                                   one of the slaves to which the next write
                                   will be broadcast */
                                ASSERT(ilep->current_slave == 0);
                                VADD(ilep->slave_list, epid_from);
                                ilep->slave_list_ack = I2C_ack;
                        } else if (ilep->current_slave == 0) {
                                ilep->current_slave = epid_from;

                                if (ilep->state == state_wait_rsp_start_r)
                                        ilep->state = state_wait_req_r;
                                else if (ilep->state == state_wait_rsp_start_w)
                                        ilep->state = state_wait_req_w;
                                else
                                        SIM_LOG_ERROR(
                                                ep, 0, "Current slave is 0 but"
                                                " status is not wait-response"
                                                "-start for neither read nor"
                                                " write");

                                /* Acknowledge will be delayed until all
                                   slave devices have responded. */
                        } else if (!restart_10bit_read) {
                                SIM_LOG_ERROR(
                                        ep, 0, "Multiple slaves (%s and %s)"
                                        " acked a start() on the same"
                                        " address",
                                        ep_dev_name(ep, ilep->current_slave),
                                        ep_dev_name(ep, epid_from));
                        }
                }

                VREMOVE_FIRST_MATCH(ilep->pending_start_responses, epid_from);

                if (restart_10bit_read) {
                        /* response for 10-bit read restart */
                        ASSERT(ilep->pending_slaves == 1);
                        ilep->pending_slaves = 0;
                        if (msg->status == I2C_noack) {
                                ASSERT(ilep->current_slave == 0);
                                ilep->state = state_wait_stop;
                        } else {
                                ASSERT(ilep->current_slave != 0);
                                ilep->state = state_wait_req_r;
                        }
                        ilep->master_iface->acknowledge(device, msg->status);
                } else {
                        ilep->pending_slaves -= 1;
                        if (ilep->pending_slaves == 0) {
                                if (broadcast) {
                                        SIM_LOG_INFO(4, ep, 0,
                                                     "All slave devices have"
                                                     " acked %s request,"
                                                     " send ack(%d) to master"
                                                     " device",
                                                     ilep->address_pattern
                                                     ? "10-bit address"
                                                     : "general call",
                                                     ilep->slave_list_ack);

                                        ilep->state =
                                                ilep->slave_list_ack == I2C_ack
                                                ? state_wait_req_w
                                                : state_wait_stop;
                                        /* All slaves have responded general
                                           call or 10-bit address*/
                                        ilep->master_iface->acknowledge(
                                                device, ilep->slave_list_ack);
                                } else if (ilep->current_slave == 0) {
                                        if (!VEMPTY(
                                               ilep->pending_start_responses)) {
                                                SIM_LOG_ERROR(ep, 0,
                                                   "Inconsistent link state in"
                                                   " %s: had pending start"
                                                   " responses despite no"
                                                   " pending slaves",
                                                   SIM_object_name(ep));
                                                ASSERT_MSG(0,
                                                           "Inconsistent state"
                                                           " in link");
                                        }

                                        /* We just removed the last pending
                                           start response from the list, so
                                           it is time to respond with a noack
                                           to master */
                                        SIM_LOG_INFO(
                                                2, ep, 0,
                                                "NOACK received from all"
                                                " slave devices, noacking"
                                                " start request");
                                        ilep->state = state_wait_stop;
                                        ilep->master_iface->acknowledge(
                                                device, I2C_noack);
                                } else if (is_hs(ilep->address_pattern)) {
                                        /* Slaves are supposed to noack
                                           High-Speed mode */
                                        SIM_LOG_SPEC_VIOLATION(
                                                2, ep, 0,
                                                "ACK received after High-Speed"
                                                " mode address start request."
                                                " But send noack to master"
                                                " to continue simulation");
                                        ilep->address_pattern = -1;
                                        ilep->state = state_wait_stop;
                                        ilep->master_iface->acknowledge(
                                                device, I2C_noack);
                                } else {
                                        /* All slaves have responded
                                           the start call, return ack
                                           since current_slave ack. */
                                        ilep->master_iface->acknowledge(
                                                device, I2C_ack);
                                }
                        }
                }
                break;
        }

        case read_request:
                ASSERT(ilep->current_master == epid_from);
                ASSERT(ilep->current_slave == current_epid);

                ilep->state = state_wait_rsp_r;
                ilep->slave_iface->read(device);
                break;

        case read_response:
                msg_data = msg->status;
                ASSERT(ilep->current_master == current_epid);
                ASSERT(ilep->current_slave == epid_from);

                ilep->state = state_wait_req_r;
                ilep->master_iface->read_response(device, msg_data);
                break;

        case write_request:
                msg_data = msg->status;
                ASSERT(ilep->current_master == epid_from);
                ASSERT(ilep->current_slave == current_epid);

                ilep->state = state_wait_rsp_w;
                ilep->slave_iface->write(device, msg_data);
                break;

        case write_response:
                if (ilep->state == state_idle && ilep->current_master == 0)
                        return;

                ASSERT(ilep->current_master == current_epid);
                if (!broadcast) {
                        ASSERT(ilep->current_slave == epid_from);
                        ASSERT(ilep->slave_list_counter == 0);
                } else {
                        ASSERT(ilep->slave_list_counter > 0);
                        ilep->slave_list_counter--;
                        ilep->slave_list_ack &= msg->status;

                        /* Update slave list after request of second address */
                        if (ilep->state == state_wait_rsp_10bit_addr_w) {
                                if (msg->status == I2C_noack)
                                        VREMOVE_FIRST_MATCH(
                                                ilep->slave_list,
                                                epid_from);
                        }
                }

                if (ilep->slave_list_counter == 0) {
                        if (ilep->state == state_wait_rsp_10bit_addr_w) {
                                if (VLEN(ilep->slave_list) == 0) {
                                        SIM_LOG_INFO(
                                                2, ep, 0,
                                                "NOACK received from all"
                                                " devices, noacking second"
                                                " address request");
                                        ilep->state = state_wait_stop;
                                        ASSERT(ilep->slave_list_ack
                                               == I2C_noack);
                                } else if (VLEN(ilep->slave_list) == 1) {
                                        ilep->current_slave =
                                                VGET(ilep->slave_list, 0);
                                        ilep->state = state_wait_req_w;
                                        VCLEAR(ilep->slave_list);
                                } else {
                                        SIM_LOG_ERROR(
                                                ep, 0,
                                                "More than one ACK received"
                                                " when match second address");
                                        ilep->state = state_wait_stop;
                                        ilep->slave_list_ack = I2C_noack;
                                }
                        } else {
                                if (ilep->state != state_wait_stop) {
                                        ilep->state = state_wait_req_w;
                                }
                        }
                        ilep->master_iface->acknowledge(device,
                                                        broadcast
                                                        ? ilep->slave_list_ack
                                                        : msg->status);
                }
                break;

        case stop:
                ilep->current_master = 0;
                ilep->current_slave = 0;
                ilep->state = state_idle;

                /* It makes no sense to echo the stop back to the device that
                   sent it */
                if (ilep->slave_iface && epid_from != current_epid)
                        ilep->slave_iface->stop(device);
                break;
        }
}

static void
link_config_value_updated(conf_object_t *link, const char *key,
                          const frags_t *msg)
{
        i2c_link_impl_t *ilink = obj_to_ilink(link);
        ilink->num_slaves += 1;
        SIM_LOG_INFO(4, link, 0,
                     "Add one more slave, now in total %d slave endpoint(s)",
                     ilink->num_slaves);
}

static void
link_config_value_removed(conf_object_t *link, const char *key)
{
        i2c_link_impl_t *ilink = obj_to_ilink(link);
        ilink->num_slaves -= 1;
        SIM_LOG_INFO(4, link, 0,
                     "Remove one slave, now in total %d slave endpoint(s)",
                     ilink->num_slaves);
}

static void
i2c_link_ep_device_changed(conf_object_t *ep, conf_object_t *old_dev)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(ep);
        const char *port = SIMLINK_endpoint_port(ep);
        conf_object_t *dev = SIMLINK_endpoint_device(ep);

        const i2c_master_v2_interface_t *m =
                SIM_c_get_port_interface(dev, I2C_MASTER_V2_INTERFACE, port);
        const i2c_slave_v2_interface_t *s =
                SIM_c_get_port_interface(dev, I2C_SLAVE_V2_INTERFACE, port);
        if (m == NULL && s == NULL) {
                SIM_LOG_ERROR(ep, 0, "Device %s implements neither the "
                              I2C_MASTER_V2_INTERFACE " nor the "
                              I2C_SLAVE_V2_INTERFACE " interface",
                              SIM_object_name(dev));
        }

        ilep->master_iface = m;
        ilep->slave_iface = s;

        if (old_dev == NULL && s != NULL) {
                /* Empty values, just used as key */
                frags_t value;
                frags_init(&value);
                SIMLINK_config_update_value(SIMLINK_endpoint_link(ep), "",
                                            &value);
        }
}

/* Link class */
static conf_object_t *
link_alloc_object(conf_class_t *cls)
{
        i2c_link_impl_t *ilink = MM_ZALLOC(1, i2c_link_impl_t);
        return &ilink->obj;
}

static lang_void *
link_init_object(conf_object_t *obj)
{
        static const link_type_t i2c_link_type = {
                .free_msg = free_message,
                .msg_to_attr = msg_to_attr,
                .msg_from_attr = msg_from_attr,
                .marshal = marshal,
                .unmarshal = unmarshal,
                .deliver = deliver,
                .update_config_value = link_config_value_updated,
                .remove_config_value = link_config_value_removed,
                .device_changed = i2c_link_ep_device_changed
        };

        i2c_link_impl_t *ilink = obj_to_ilink(obj);
        SIMLINK_init(obj, &i2c_link_type);
        ilink->num_slaves = 0;
        return obj;
}

static void
i2c_link_finalize_instance(conf_object_t *obj)
{
        SIMLINK_finalize(obj);
}

static void
i2c_link_pre_delete_instance(conf_object_t *obj)
{
        SIMLINK_pre_delete(obj);
}

static void
i2c_link_delete_instance(conf_object_t *obj)
{
        i2c_link_impl_t *ilink = obj_to_ilink(obj);
        MM_FREE(ilink);
}

/* Endpoint class */
static conf_object_t *
ep_alloc_object(conf_class_t *cls)
{
        i2c_link_endpoint_t *ilep = MM_ZALLOC(1, i2c_link_endpoint_t);
        return ep_to_obj(ilep);
}

static lang_void *
ep_init_object(conf_object_t *obj)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        SIMLINK_endpoint_init(obj, false);
        VINIT(ilep->pending_start_responses);
        VINIT(ilep->slave_list);
        ilep->slave_list_counter = 0;
        ilep->slave_list_ack = I2C_noack;
        ilep->address_pattern = -1;
        return obj;
}

static void
i2c_link_ep_finalize_instance(conf_object_t *ep)
{
        SIMLINK_endpoint_finalize(ep);
}

static void
i2c_link_ep_pre_delete_instance(conf_object_t *ep)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(ep);

        if (ilep->slave_iface) {
                /* Empty values, just used as key */
                SIMLINK_config_remove_value(SIMLINK_endpoint_link(ep), "");
        }
        SIMLINK_endpoint_disconnect(ep);
}

static void
i2c_link_ep_delete_instance(conf_object_t *obj)
{
        MM_FREE(obj);
}


/* I2c_link interface methods */
static const char *
state_name(i2c_link_state_t state)
{
        switch (state) {
        case state_idle:
                return "idle";
        case state_wait_rsp_start_r:
                return "wait_rsp_start_r";
        case state_wait_rsp_start_w:
                return "wait_rsp_start_w";
        case state_wait_req_r:
                return "wait_req_r";
        case state_wait_req_w:
                return "wait_req_w";
        case state_wait_rsp_r:
                return "wait_rsp_r";
        case state_wait_rsp_w:
                return "wait_rsp_w";
        case state_wait_stop:
                return "wait_stop";
        case state_wait_remote_master:
                return "Wait for start/stop from remote master";
        case state_wait_remote_start_rsp:
                return "Wait for response from remote slave";
        case state_wait_rsp_10bit_addr_w:
                return "Wait for response from 10-bit second address";
        }
        return "invalid state";
}

static void
report_unsupported_address(conf_object_t *ep, uint32 addr)
{
        const char *operation_name = "i2c_slave_v2.start";
        if ((addr & 0xfe) == 0x02) {
                // CBUS address
                SIM_LOG_UNIMPLEMENTED(1, ep, 0,
                                      "%s: CBUS addressing not implemented"
                                      " - ignoring address pattern"
                                      " (address = 0x%x)",
                                      operation_name, addr);
        } else if (((addr & 0xfc) == 0x04) || ((addr & 0xf8) == 0xf8))
                SIM_LOG_UNIMPLEMENTED(1, ep, 0,
                                      "%s: attempt to connect to"
                                      " reserved slave address 0x%02x",
                                      operation_name, addr);
        else
                SIM_LOG_ERROR(ep, 0,
                              "%s: attempt to connect to reserved"
                              " slave address 0x%02x",
                              operation_name, addr);
}

static bool
is_unsupported_address(uint8 addr)
{
        /* General call address is supported */
        /* 10-bit address is supported */
        /* High-Speed master code addressing is supported */
        return (((addr & 0xf0) == 0 || (addr & 0xf0) == 0xf0)
                && addr != 0
                && (addr & 0xf8) != 0xf0
                && (addr & 0xf8) != 0x08);
}

static void
il_start(conf_object_t *ep, uint8 addr)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(ep);
        const uint64 current_epid = SIMLINK_endpoint_id(ep);
        uint8 buf[1000];
        SIM_LOG_INFO(4, ep, 0, "i2c_slave_v2.start(%s, 0x%x)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)), addr);

        if (ilep->master_iface == NULL) {
                SIM_LOG_ERROR(ep, 0, "device %s requesting I2C start"
                              " does not implement the "
                              I2C_MASTER_V2_INTERFACE " interface",
                              SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));
                return;
        }

        /* Confirm the state is OK, it could be idle when repeat start */
        if (ilep->state != state_idle
            && ilep->state != state_wait_stop
            && ilep->state != state_wait_req_w
            && ilep->state != state_wait_req_r
            && ilep->state != state_wait_remote_master) {
                SIM_LOG_ERROR(ep, 0, "Start: invalid state: %s",
                              state_name(ilep->state));
                return;
        }

        bool restart_10bit_read = false;
        if (is_10bit(ilep->address_pattern)
            && addr == (ilep->address_pattern | 1)
            && ilep->state == state_wait_req_w
            && VLEN(ilep->slave_list) == 0) {
                restart_10bit_read = true;
        }

        /* Clean relevant attributes for repeated start after general call
           or first start of 10-bit address */
        if (VLEN(ilep->slave_list)) {
                /* Reserve slave_list when restart 10-bit read*/
                if (!restart_10bit_read) {
                        ilep->slave_list_counter = 0;
                        VFREE(ilep->slave_list);
                }
        }
        ilep->address_pattern = -1;

        if (ilep->current_master == 0
            || ilep->current_master == current_epid) {
                if (is_unsupported_address(addr)) {
                        report_unsupported_address(ep, addr);
                }

                ilep->state = state_wait_remote_start_rsp;

                if (addr == 0) {
                        /* General call address. Set attribute address_pattern
                           to 0, indicating it is general call broadcasting. */
                        SIM_LOG_INFO(2, ep, 0, "General call broadcasting");

                        ilep->slave_list_ack = I2C_noack;
                        ilep->address_pattern = 0;
                } else if ((addr & 0xf9) == 0xf0) {
                        /* 10-bit address. It must be written when beginning a
                           transaction, because the second address will be
                           written on next request.
                           Set attribute addr_10bit to true, indicating it is
                           10-bit broadcasting. */
                        SIM_LOG_INFO(2, ep, 0, "10-bit broadcasting");

                        ilep->slave_list_ack = I2C_noack;
                        ilep->address_pattern = addr;
                } else if ((addr & 0xf9) == 0xf1 && !restart_10bit_read) {
                        SIM_LOG_ERROR(ep, 0,
                                      "10-bit transaction should"
                                      " start with write");
                        conf_object_t *dev = SIMLINK_endpoint_device(ep);
                        ilep->master_iface->acknowledge(dev, I2C_noack);
                        ilep->state = state_wait_stop;
                        return;
                } else if ((addr & 0xf8) == 0x08) {
                        /* High-Speed master code address */
                        SIM_LOG_INFO(2, ep, 0,
                                     "High-Speed master code address"
                                     " broadcasting");
                        ilep->slave_list_ack = I2C_noack;
                        ilep->address_pattern = addr;
                }

                /* 10-bit read restart. */
                if (restart_10bit_read) {
                        /* 10-bit restart read may only be acked by the already
                           addressed target, so we hide this from other devices
                           and use a simple unicast scheme */
                        ilep->slave_list_ack = I2C_noack;
                        ilep->address_pattern = addr;
                        ilep->pending_slaves = 1;
                        ASSERT(VEMPTY(ilep->slave_list));
                        VADD(ilep->slave_list, ilep->current_slave);
                        ilep->current_slave = 0;
                        ilep->state = state_wait_rsp_start_r;
                        SIMLINK_send_message(ep, VGET(ilep->slave_list, 0),
                                             new_status_message(current_epid,
                                                                start_request,
                                                                addr));
                } else {
                        /* Current slave will be decided when it acks the
                           request */
                        ilep->current_slave = 0;

                        /* All other START conditions are broadcast to all
                           endpoints */
                        SIMLINK_send_message(ep, SIMLINK_endpoint_id(ep),
                                             new_status_message(current_epid,
                                                                start_request,
                                                                addr));
                        SIMLINK_send_message(ep, LINK_BROADCAST_ID,
                                             new_status_message(current_epid,
                                                                start_request,
                                                                addr));
                }
        } else {
                conf_object_t *dev = SIMLINK_endpoint_device(ep);
                /* Link is busy and the master should have known it. */
                SIM_LOG_ERROR(
                        ep, 0,
                        "Got start request from master device %s,"
                        " but another master is active on the link."
                        " The device should implement the "
                        I2C_SLAVE_V2_INTERFACE " interface and monitor"
                        " start and stop requests to avoid collisions."
                        " Responding with a faked NOACK.",
                        SIM_object_name(dev));
                ilep->master_iface->acknowledge(dev, I2C_noack);
                /* Actually we should expect a stop and then ignore it */
                ilep->state = state_idle;
        }
}

static void
handle_write_response(i2c_link_endpoint_t *ilep, i2c_ack_t ack)
{
        unsigned char buf[1000];
        if (ilep->current_slave != SIMLINK_endpoint_id(ep_to_obj(ilep))) {
                SIM_LOG_ERROR(ep_to_obj(ilep), 0,
                              "Unexpected write_response call from %s",
                              SIMLINK_endpoint_dev_name(
                                      ep_to_obj(ilep), BUFFER_T(buf)));
                return;
        }

        ilep->state = state_wait_req_w;
        SIMLINK_send_message(ep_to_obj(ilep), ilep->current_master,
                             new_status_message(
                                     SIMLINK_endpoint_id(ep_to_obj(ilep)),
                                     write_response, ack));
}

static void
handle_start_response(i2c_link_endpoint_t *ilep, i2c_ack_t ack)
{
        ilep->waiting_for_synchronous_response = false;
        ilep->current_slave = ack == I2C_ack
                ? SIMLINK_endpoint_id(ep_to_obj(ilep)) : 0;
        ilep->state = state_wait_remote_master;
        SIMLINK_send_message(ep_to_obj(ilep), ilep->current_master,
                             new_status_message(
                                     SIMLINK_endpoint_id(ep_to_obj(ilep)),
                                     start_response, ack));
}

static void
il_acknowledge(conf_object_t *ep, i2c_ack_t ack)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(ep);
        SIM_LOG_INFO(4, ep, 0,
                     "i2c_master_v2.acknowledge(%d)", ack);

        /* Sanity check */
        if (ack != I2C_noack && ack != I2C_ack) {
                SIM_LOG_ERROR(ep, 0, "Acknowledge: invalid ack value: %d", ack);
                ack = I2C_noack;
        }

        if (ilep->state == state_wait_rsp_w)
                handle_write_response(ilep, ack);
        else if (ilep->state == state_wait_rsp_start_r
                 || ilep->state == state_wait_rsp_start_w)
                handle_start_response(ilep, ack);
        else
                SIM_LOG_ERROR(ep, 0, "Acknowledge: invalid state: %s",
                              state_name(ilep->state));
}

static void
il_read(conf_object_t *ep)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(ep);
        uint8 buf[1000];

        SIM_LOG_INFO(4, ep, 0, "i2c_slave_v2.read(%s)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));

        if (ilep->current_master != SIMLINK_endpoint_id(ep)) {
                SIM_LOG_ERROR(ep, 0, "Unexpected read call from %s",
                              SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));
                return;
        }

        if (ilep->state != state_wait_req_r)
                SIM_LOG_ERROR(ep, 0, "Read: invalid state: %s",
                              state_name(ilep->state));

        ilep->state = state_wait_rsp_r;
        if (ilep->current_slave != 0)
                SIMLINK_send_message(ep, ilep->current_slave,
                                     new_status_message(SIMLINK_endpoint_id(ep),
                                                        read_request,
                                                        0));
}

static void
il_read_response(conf_object_t *ep, uint8 value)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(ep);
        uint8 buf[1000];
        if (ilep->current_slave != SIMLINK_endpoint_id(ep)) {
                SIM_LOG_ERROR(ep, 0, "Unexpected read_response() call from %s",
                              SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));
                return;
        }

        SIM_LOG_INFO(4, ep, 0,
                     "i2c_slave_v2.read_response(%s, 0x%x)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)), value);

        if (ilep->state != state_wait_rsp_r) {
                SIM_LOG_ERROR(ep, 0, "Read_response: invalid state: %s",
                              state_name(ilep->state));
                return;
        }

        ilep->state = state_wait_req_r;
        SIMLINK_send_message(ep, ilep->current_master,
                             new_status_message(SIMLINK_endpoint_id(ep),
                                                read_response,
                                                value));
}

static void
il_write(conf_object_t *ep, uint8 value)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(ep);
        uint8 buf[1000];
        if (ilep->current_master != SIMLINK_endpoint_id(ep)) {
                SIM_LOG_ERROR(ep, 0, "Unexpected write call from %s",
                              SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));
                return;
        }

        SIM_LOG_INFO(4, ep, 0, "i2c_slave_v2.write(%s, 0x%x)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)), value);

        if (ilep->state != state_wait_req_w) {
                SIM_LOG_ERROR(ep, 0, "Write: invalid state: %s",
                              state_name(ilep->state));
                return;
        }

        ilep->state = state_wait_rsp_w;
        if (VLEN(ilep->slave_list)) {
                /* Initialize general call ack and general call counter for
                   write operation.

                   General call ack will be the acknowledge send to master
                   device when all slaves listed have responded. If any of
                   ack, an ack will be sent to master device for each write.

                   General call counter will be set before the first write
                   according to the number of slaves listed in slave_list. Each
                   time a slave responded, the value will decrement by 1. When
                   counter reach 0, it means all slaves have responded. Then it
                   will be refiled for further write. */
                ilep->slave_list_ack = I2C_noack;
                if (is_10bit(ilep->address_pattern))
                        ilep->state = state_wait_rsp_10bit_addr_w;
                ilep->slave_list_counter = VLEN(ilep->slave_list);

                /* General call, or second byte of 10-bit address */
                VFORI(ilep->slave_list, i) {
                        SIMLINK_send_message(
                                ep, VGET(ilep->slave_list, i),
                                new_status_message(SIMLINK_endpoint_id(ep),
                                                   write_request, value));
                }
        } else {
                /* Clear address pattern: This is done to enforce that a 10-bit
                   read transaction only can be initiated immediately after the
                   second byte of a 10-bit address. */
                ilep->address_pattern = -1;
                SIMLINK_send_message(ep, ilep->current_slave,
                                     new_status_message(SIMLINK_endpoint_id(ep),
                                                        write_request,
                                                        value));
        }
}

static void
il_stop(conf_object_t *ep)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(ep);
        uint8 buf[1000];
        SIM_LOG_INFO(4, ep, 0, "i2c_slave_v2.stop(%s)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));

        /* Check the state */
        if (ilep->state != state_wait_stop
            && ilep->state != state_wait_req_w
            && ilep->state != state_wait_req_r)
                SIM_LOG_ERROR(ep, 0, "Stop: invalid state: %s",
                              state_name(ilep->state));

        /* Clean relevant attributes for general call */
        if (VLEN(ilep->slave_list)) {
                ilep->slave_list_counter = 0;
                ilep->slave_list_ack = I2C_noack;
                VFREE(ilep->slave_list);
        }

        /* The stop is delayed locally as well. This is to make sure all
           endpoints have the same conception of who owns the bus; if the bus
           would be made available earlier locally, then this endpoint might
           accept a start request which another endpoint would refuse.
           TODO: add a test for this scenario. */
        SIMLINK_send_message(ep, SIMLINK_endpoint_id(ep),
                             new_status_message(
                                     SIMLINK_endpoint_id(ep), stop, 0));
        /* Broadcast it to all eps */
        SIMLINK_send_message(ep, LINK_BROADCAST_ID,
                             new_status_message(
                                     SIMLINK_endpoint_id(ep), stop, 0));
}

static attr_value_t
il_addresses(conf_object_t *obj)
{
        return SIM_make_attr_list(0);
}

static attr_value_t
get_ep_current_master(conf_object_t *obj)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        return SIM_make_attr_uint64(ilep->current_master);
}

static set_error_t
set_ep_current_master(conf_object_t *obj, attr_value_t *val)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        ilep->current_master = SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_ep_current_slave(conf_object_t *obj)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        return SIM_make_attr_uint64(ilep->current_slave);
}

static set_error_t
set_ep_current_slave(conf_object_t *obj, attr_value_t *val)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        ilep->current_slave = SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_ep_state(conf_object_t *obj)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        return SIM_make_attr_uint64(ilep->state);
}

static set_error_t
set_ep_state(conf_object_t *obj, attr_value_t *val)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        ilep->state = SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_pending_start_responses(conf_object_t *obj)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        attr_value_t l = SIM_alloc_attr_list(
                VLEN(ilep->pending_start_responses));
        VFORI(ilep->pending_start_responses, i) {
                SIM_attr_list_set_item(
                        &l, i, SIM_make_attr_uint64(
                                VGET(ilep->pending_start_responses, i)));
        }
        return l;
}

static set_error_t
set_pending_start_responses(conf_object_t *obj, attr_value_t *val)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        size_t len = SIM_attr_list_size(*val);
        VRESIZE(ilep->pending_start_responses, len);
        for (int i = 0; i < len; i++) {
                VSET(ilep->pending_start_responses, i,
                     SIM_attr_integer(SIM_attr_list_item(*val, i)));
        }

        return Sim_Set_Ok;
}

static attr_value_t
get_pending_slaves(conf_object_t *obj)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        return SIM_make_attr_uint64(ilep->pending_slaves);
}

static set_error_t
set_pending_slaves(conf_object_t *obj, attr_value_t *val)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        ilep->pending_slaves = SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_slave_list(conf_object_t *obj)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        attr_value_t l = SIM_alloc_attr_list(VLEN(ilep->slave_list));
        VFORI(ilep->slave_list, i) {
                SIM_attr_list_set_item(
                        &l, i, SIM_make_attr_uint64(
                                VGET(ilep->slave_list, i)));
        }
        return l;
}

static set_error_t
set_slave_list(conf_object_t *obj, attr_value_t *val)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        size_t len = SIM_attr_list_size(*val);
        VRESIZE(ilep->slave_list, len);
        for (int i = 0; i < len; i++) {
                VSET(ilep->slave_list, i,
                     SIM_attr_integer(SIM_attr_list_item(*val, i)));
        }

        return Sim_Set_Ok;
}

static attr_value_t
get_slave_list_counter(conf_object_t *obj)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        return SIM_make_attr_uint64(ilep->slave_list_counter);
}

static set_error_t
set_slave_list_counter(conf_object_t *obj, attr_value_t *val)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        ilep->slave_list_counter = SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

static attr_value_t
get_address_pattern(conf_object_t *obj)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        return SIM_make_attr_int64(ilep->address_pattern);
}

static set_error_t
set_address_pattern(conf_object_t *obj, attr_value_t *val)
{
        i2c_link_endpoint_t *ilep = obj_to_ep(obj);
        ilep->address_pattern = SIM_attr_integer(*val);
        return Sim_Set_Ok;
}

void
init_local()
{
        SIMLINK_init_library();

        const class_info_t link_cls_funcs = {
                .alloc = link_alloc_object,
                .init = link_init_object,
                .finalize = i2c_link_finalize_instance,
                .objects_finalized = NULL,
                .deinit = i2c_link_pre_delete_instance,
                .dealloc = i2c_link_delete_instance,
                .description = "model of I2C link v2",
                .short_desc = "I2C link v2",
                .kind = Sim_Class_Kind_Vanilla
        };
        conf_class_t *link_cls = SIM_create_class("i2c-link-impl",
                                                  &link_cls_funcs);
        SIMLINK_register_class(link_cls);

        const class_info_t ep_cls_funcs = {
                .alloc = ep_alloc_object,
                .init = ep_init_object,
                .finalize = i2c_link_ep_finalize_instance,
                .objects_finalized = NULL,
                .deinit = i2c_link_ep_pre_delete_instance,
                .dealloc = i2c_link_ep_delete_instance,
                .description = "Connects a link with a device",
                .short_desc = "connects a link with a device",
                .kind = Sim_Class_Kind_Vanilla
        };
        conf_class_t *ep_cls = SIM_create_class("i2c-link-endpoint",
                                                &ep_cls_funcs);
        SIMLINK_register_endpoint_class(ep_cls, "[iii]");

        SIM_register_attribute(
                ep_cls, "current_master",
                get_ep_current_master,
                set_ep_current_master,
                Sim_Attr_Optional, "i",
                "The endpoint id of current active master, initialized as 0");
        SIM_register_attribute(
                ep_cls, "current_slave",
                get_ep_current_slave,
                set_ep_current_slave,
                Sim_Attr_Optional, "i",
                "The endpoint id of current active slave, initialized as 0");
        SIM_register_attribute(
                ep_cls, "state",
                get_ep_state,
                set_ep_state,
                Sim_Attr_Optional, "i",
                "The current state of i2c link, initialized as idle(0)");
        SIM_register_attribute(
                ep_cls, "pending_start_responses",
                get_pending_start_responses,
                set_pending_start_responses,
                Sim_Attr_Optional, "[i*]",
                "IDs of endpoints from which we are awaiting a start response");
        SIM_register_attribute(
                ep_cls, "pending_slaves",
                get_pending_slaves,
                set_pending_slaves,
                Sim_Attr_Optional, "i",
                "The number of slaves we are awaiting a start response");
        SIM_register_attribute(
                ep_cls, "slave_list",
                get_slave_list,
                set_slave_list,
                Sim_Attr_Optional, "[i*]",
                "IDs of endpoints which acknowledge"
                " general call address or 10-bit address");
        SIM_register_attribute(
                ep_cls, "slave_list_counter",
                get_slave_list_counter,
                set_slave_list_counter,
                Sim_Attr_Optional, "i",
                "The number of slaves we are awaiting response"
                " for general call or 10-bit address");
        SIM_register_attribute(
                ep_cls, "address_pattern",
                get_address_pattern,
                set_address_pattern,
                Sim_Attr_Optional, "i",
                "Save address status for start request");

        static const i2c_slave_v2_interface_t s_ifc = {
                .start = il_start,
                .read = il_read,
                .write = il_write,
                .stop = il_stop,
                .addresses = il_addresses
        };
        SIM_REGISTER_INTERFACE(ep_cls, i2c_slave_v2, &s_ifc);
        static const i2c_master_v2_interface_t m_ifc = {
                .acknowledge = il_acknowledge,
                .read_response = il_read_response,
        };
        SIM_REGISTER_INTERFACE(ep_cls, i2c_master_v2, &m_ifc);
}
