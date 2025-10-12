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

#include <simics/devs/liblink.h>
#include <simics/devs/i3c.h>
#include <stddef.h>
/* Define broadcast address 0x7e as a macro. */
#define BROADCAST 0x7e

#define MAX_BUF_SIZE 0x400

typedef struct {
        conf_object_t obj;
        uint8 num_devs;     /* Number of device endpoints,
                               including both masters and slaves. */
        VECT(uint64) hdr_slave_list;
} i3c_link_impl_t;

/* Records pair of (slave epid, slave data).
   This is used in two conditions:
   - DAA process. Then 'data' represents slave daa data.
   - Bus arbitration process. Then 'data' represents slave address.
     slave address can be: 0x02 for hot-join;
     addr | 1 for in-band interrupt;
     addr | 0 for secondary master. */
typedef struct {
        uint64 epid;
        uint64 data;
} slave_data_t;

typedef struct {
        conf_object_t obj;
        const i3c_master_interface_t *master_iface;
        const i3c_slave_interface_t *slave_iface;
        const i3c_daa_snoop_interface_t * daa_snoop_iface;
        const i3c_hdr_master_interface_t *hdr_master_iface;
        const i3c_hdr_slave_interface_t *hdr_slave_iface;

        /* Represents the main master after bus configuration */
        uint64 main_master;

        /* The current master and current slave during one bus transaction */
        uint64 current_master;
        uint64 current_slave;

        unsigned pending_acks;
        /* Records the start request address. Used when broadcast
           request or secondary master request. */
        uint8 address;

        VECT(uint64) slave_list;
        i3c_ack_t slave_list_ack;
        /* Count if all slaves in slave_list response */
        uint8 slave_list_counter;

        VECT(slave_data_t) slave_data_list;
        /* Keep the lowest slave data in slave_data */
        slave_data_t slave_data;

        bool in_daa;

        bool in_hdr;

        /* Slave has pending ibi request */
        bool pending_ibi_req;
        /* Used when slave behaves as secondary master */
        uint8 ccc;
        uint64 snd_master;

        /* Used when master communicates with i2c slaves,
           or assign daa address */
        bool legacy_write;
} i3c_link_endpoint_t;

typedef enum {
        start_request,
        start_response,
        read_request,
        read_response,
        write_request,
        sdr_write_request,
        write_response,
        daa_read,
        daa_response,
        daa_address,
        daa_address_bcast,
        stop,
        ibi_request,
        ibi_start,
        ibi_address,
        ibi_acknowledge,
        hdr_write_request,
        hdr_read_request,
        hdr_restart_request,
        hdr_exit_request,
        hdr_acknowledge_response,
        hdr_read_response,
} i3c_link_action_type_t;

typedef struct {
        link_message_t common;
        uint64 src_epid;
        i3c_link_action_type_t type;
        uint32 status;
        bytes_t payload;
} i3c_link_message_t;

#define BUFFER_T(buf) (buffer_t){ .len = sizeof(buf), .data = buf }

static void il_ibi_address(conf_object_t *ep, uint8 address);
static void
handle_hdr_acknowledge(i3c_link_message_t *msg, uint64 epid_from,
                       i3c_link_endpoint_t *ilep, uint64 current_epid,
                       conf_object_t *device);

/* Return the name of the message type */
static const char *
i3c_type_name(i3c_link_action_type_t type)
{
        switch(type) {
        case start_request:
                return "start request";
        case start_response:
                return "start response";
        case read_request:
                return "read request";
        case read_response:
                return "read response";
        case write_request:
                return "i2c write request";
        case sdr_write_request:
                return "write request";
        case write_response:
                return "write response";
        case daa_read:
                return "daa read";
        case daa_response:
                return "daa response";
        case daa_address:
                return "daa address";
        case daa_address_bcast:
                return "daa address broadcast";
        case stop:
                return "stop";
        case ibi_request:
                return "ibi request";
        case ibi_start:
                return "ibi start";
        case ibi_address:
                return "ibi address";
        case ibi_acknowledge:
                return "ibi acknowledge";
        case hdr_write_request:
                return "hdr write";
        case hdr_read_request:
                return "hdr read";
        case hdr_restart_request:
                return "hdr restart";
        case hdr_exit_request:
                return "hdr exit";
        case hdr_acknowledge_response:
                return "hdr acknowledge response";
        case hdr_read_response:
                return "hdr read response";
        }
        return "unknown type";
}

/* Link methods */
static link_message_t *
new_status_message(uint64 src_epid, i3c_link_action_type_t type,
                   uint32 status, const uint8 *data, uint32 len)
{
        i3c_link_message_t *msg = MM_MALLOC(1, i3c_link_message_t);
        SIMLINK_init_message(&msg->common);
        uint8 *d = MM_ZALLOC(len, uint8);
        memcpy(d, data, len);
        msg->src_epid = src_epid;
        msg->type = type;
        msg->status = status;
        msg->payload.len = len;
        msg->payload.data = d;
        return &msg->common;
}

static attr_value_t
msg_to_attr(conf_object_t *link, const link_message_t *lm)
{
        i3c_link_message_t *msg = (i3c_link_message_t *) lm;
        return SIM_make_attr_list(4,
                                  SIM_make_attr_uint64(msg->src_epid),
                                  SIM_make_attr_uint64(msg->type),
                                  SIM_make_attr_uint64(msg->status),
                                  SIM_make_attr_data(msg->payload.len,
                                                     msg->payload.data));
}

static link_message_t *
msg_from_attr(conf_object_t *link, attr_value_t attr)
{
        uint64 src_epid =
                SIM_attr_integer(SIM_attr_list_item(attr, 0));
        i3c_link_action_type_t type =
                SIM_attr_integer(SIM_attr_list_item(attr, 1));
        uint32 status =
                SIM_attr_integer(SIM_attr_list_item(attr, 2));

        attr_value_t payload = SIM_attr_list_item(attr, 3);
        uint32 len = SIM_attr_data_size(payload);
        const uint8 *data = SIM_attr_data(payload);

        return new_status_message(src_epid, type, status, data, len);
}

static void
free_msg(conf_object_t *link, link_message_t *lm)
{
        i3c_link_message_t *msg = (i3c_link_message_t *)lm;

        MM_FREE((uint8 *)msg->payload.data);
        msg->payload.data = NULL;

        MM_FREE(msg);
}

static void
marshal(conf_object_t *link, const link_message_t *lm,
        void (*finish)(void *data, const frags_t *msg),
        void *finish_data)
{
        const i3c_link_message_t *msg = (i3c_link_message_t *) lm;
        uint8 buffer[11];
        frags_t frame;

        buffer[0] = msg->type;
        buffer[1] = msg->status;
        UNALIGNED_STORE_LE64(&buffer[2], msg->src_epid);
        buffer[10] = msg->payload.len;

        frags_init_add(&frame, &buffer[0], 11);
        if (msg->payload.len)
                frags_add(&frame, msg->payload.data, msg->payload.len);

        finish(finish_data, &frame);
}

static link_message_t *
unmarshal(conf_object_t *link, const frags_t *msg)
{
        i3c_link_action_type_t type =
                frags_extract_8(msg, 0);
        uint8 status =
                frags_extract_8(msg, 1);
        uint64 src_epid =
                frags_extract_le64(msg, 2);

        uint8 len = frags_extract_8(msg, 10);
        void *data = NULL;
        if (len)
                data = frags_extract_slice_alloc(msg, 11, len);

        link_message_t *m = new_status_message(
                src_epid, type, status, data, len);

        MM_FREE(data);
        return m;
}

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

static void prepare_start_request(conf_object_t* ep, uint8 addr) {
        uint64 epid = SIMLINK_endpoint_id(ep);

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        if (!ilep->main_master) {
                if (addr == BROADCAST << 1)
                        ilep->main_master = epid;
                else
                        SIM_LOG_INFO(2, &ilep->obj, 0,
                                     "main master is not set during start");
        }
        ilep->current_master = epid;

        conf_object_t *link = SIMLINK_endpoint_link(&ilep->obj);
        i3c_link_impl_t *ilink = (i3c_link_impl_t *)link;

        /* Waiting for num_devs-1 devices to response */
        ilep->pending_acks = ilink->num_devs - 1;
        if (ilep->pending_acks == 0) {
                ilep->pending_acks = 1;
                SIM_LOG_INFO(2, &ilep->obj, 0,
                             "No other devices in current"
                             " configuration, noacking start request");
                // Go through message to ensure asynchronous callback
                // if immediate_delivery is not set.
                SIMLINK_send_message(ep, epid,
                                     new_status_message(epid,
                                                        start_response,
                                                        I3C_noack, 0, 0));
        }
}

static void
handle_start_request(i3c_link_message_t *msg, uint64 epid_from,
                     i3c_link_endpoint_t *ilep, uint64 current_epid,
                     conf_object_t *device)
{
        /* main_master will set only once at bus configuration stage during
           DAA process. Slave cannot send broadcast address BROADCAST. */
        if (!ilep->main_master) {
                if (msg->status == BROADCAST << 1)
                        ilep->main_master = epid_from;
                else
                        SIM_LOG_INFO(2, &ilep->obj, 0,
                                     "main master is not set during start");
        }

        /* Repeated start from currently active master */
        /* or, first message during idle */
        if (   (ilep->current_master != epid_from)
            && (ilep->current_master != LINK_NULL_ID)) {
                /* Ignore message sent from other devices who
                   lost arbitration already */
                SIM_LOG_ERROR(&ilep->obj, 0, "At any time, only one master"
                              " can issue start request");
        }

        ilep->current_master = epid_from;
        /* A device on some other endpoint becomes the active device,
           forward its start to this device */
        SIM_LOG_INFO(4, &ilep->obj, 0, "forwarding request to device");
        ilep->slave_iface->start(device, msg->status);
}

static void
handle_start_response(i3c_link_message_t *msg, uint64 epid_from,
                      i3c_link_endpoint_t *ilep, uint64 current_epid,
                      conf_object_t *device)
{
        if (msg->status == I3C_ack) {
                if (ilep->address >> 1 == BROADCAST) {
                        VADD(ilep->slave_list, epid_from);
                        ilep->slave_list_ack = I3C_ack;
                } else if (ilep->current_slave == LINK_NULL_ID) {
                        ilep->current_slave = epid_from;
                } else
                        SIM_LOG_ERROR(&ilep->obj, 0,
                                      "Multiple slaves (%s and %s) acked"
                                      " a start() on the same address",
                                      ep_dev_name(&ilep->obj,
                                                  ilep->current_slave),
                                      ep_dev_name(&ilep->obj,
                                                  epid_from));
        }

        ilep->pending_acks -= 1;
        if (ilep->pending_acks == 0) {
                if (ilep->address >> 1 == BROADCAST) {
                        SIM_LOG_INFO(3, &ilep->obj, 0,
                                     "All slaves responded to the broadcast start call"
                                     " propagating %s to master",
                                     ilep->slave_list_ack == I3C_ack ? "ack" : "noack");
                        ilep->master_iface->acknowledge(device,
                                                        ilep->slave_list_ack);
                } else if (ilep->current_slave == LINK_NULL_ID) {
                        SIM_LOG_INFO(2, &ilep->obj, 0,
                                     "NOACK received from all slave"
                                     " devices, noacking start request");
                        ilep->master_iface->acknowledge(device, I3C_noack);
                } else {
                        /* All slaves have responded to the start call, return
                           ACK since current_slave ack. */
                        SIM_LOG_INFO(3, &ilep->obj, 0,
                                     "Slave responded"
                                     " propagating ack to master");
                        ilep->master_iface->acknowledge(device, I3C_ack);
                }
        }
}

static void
handle_read_response(i3c_link_message_t *msg, uint64 epid_from,
                     i3c_link_endpoint_t *ilep, uint64 current_epid,
                     conf_object_t *device)
{
        ASSERT(ilep->current_slave == epid_from);
        ASSERT(ilep->current_master == current_epid);

        /* The GETACCMST CCC (secondary master) is 0x91. And it is handled
           in Direct Read process. Now the ilep is master, when the ccc is
           GETACCMST, it means the slave which is epid_from requesting to
           be main_master. The main_master change happens in stop stage.
        */
        if (ilep->ccc == 0x91 && !ilep->snd_master)
                ilep->snd_master = epid_from;

        ilep->master_iface->read_response(
                device, *(msg->payload.data), msg->status);
}

static void
handle_daa_address_bcast(i3c_link_message_t *msg, uint64 epid_from,
                         i3c_link_endpoint_t *ilep, uint64 current_epid,
                         conf_object_t *device)
{
        ASSERT(ilep->current_master == epid_from);
        /* Ignore the address if the address is sent to itself. */
        uint64 e = UNALIGNED_LOAD64(msg->payload.data);
        if (e == current_epid)
                return;

        uint64 d = UNALIGNED_LOAD64(msg->payload.data + 8);
        uint64 id = d >> 16;
        uint8 bcr = (d >> 8) & 0xff;
        uint8 dcr = d & 0xff;
        uint8 addr = *(msg->payload.data + 16);
        if (ilep->daa_snoop_iface)
                ilep->daa_snoop_iface->assigned_address(
                        device, id, bcr, dcr, addr);
}

static void
handle_write_response(i3c_link_message_t *msg, uint64 epid_from, i3c_link_endpoint_t *ilep,
                      uint64 current_epid, conf_object_t *device)
{
        ASSERT(ilep->current_master == current_epid);
        /* Handle two cases: normal legacy write response and
           daa assign address write response.
           FIXME. As long there might be other broadcasts in i2c mode
           then daa we first check address and then decrease slaves
           counter
        */

        if (ilep->address >> 1 == BROADCAST) {
            if (ilep->slave_list_counter > 0) {
                ilep->slave_list_counter--;
            }
            if (ilep->slave_list_counter == 0) {
                ilep->master_iface->acknowledge(device, I3C_ack);
            }
        } else {
                ASSERT(ilep->current_slave == epid_from);
                ilep->master_iface->acknowledge(device, msg->status);
        }
}

static void
handle_daa_response(i3c_link_message_t *msg, uint64 epid_from,
                    i3c_link_endpoint_t *ilep, uint64 current_epid,
                    conf_object_t *device)
{
        ASSERT(ilep->current_master == current_epid);
        ASSERT(ilep->address >> 1 == BROADCAST);
        ASSERT(ilep->slave_list_counter > 0);
        ilep->slave_list_counter--;

        slave_data_t item;
        item.epid = epid_from;
        item.data = *(uint64 *)(msg->payload.data);
        VADD(ilep->slave_data_list, item);

        if (ilep->slave_list_counter == 0) {
                uint64 e = LINK_NULL_ID;
                uint64 d = 0xffffffffffffffff;
                /* Pick up the lowest data as current_slave,
                   forward the data to master. */
                VFORI(ilep->slave_data_list, i) {
                        slave_data_t tmp = VGET(ilep->slave_data_list, i);
                        if (tmp.data < d) {
                                e = tmp.epid;
                                d = tmp.data;
                        }
                }
                VFREE(ilep->slave_data_list);
                ilep->slave_data.epid = e;
                ilep->slave_data.data = d;
                uint64 id = d >> 16;
                uint8 bcr = (d >> 8) & 0xff;
                uint8 dcr = d & 0xff;
                ilep->master_iface->daa_response(device, id, bcr, dcr);
        }
}

static void master_stop_cleanup(conf_object_t* ep, uint8 new_master)
{
    i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
    /* main_master changes from master to secondary master. */
    if (new_master != 0)
        ilep->main_master = new_master;

    ilep->current_master = LINK_NULL_ID;
    ilep->current_slave = LINK_NULL_ID;
}


static void
handle_stop(i3c_link_message_t *msg, uint64 epid_from,
            i3c_link_endpoint_t *ilep, uint64 current_epid,
            conf_object_t *device)
{
        /* main_master changes from master to secondary master. */
        if (msg->status)
                ilep->main_master = msg->status;

        ilep->current_master = LINK_NULL_ID;
        ilep->current_slave = LINK_NULL_ID;

        /* Stop messages should never be sent to itself */
        ASSERT(current_epid != epid_from);
        ilep->slave_iface->stop(device);
}

static void prepare_ibi_start(conf_object_t *ep)
{
        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;

        ilep->current_master = SIMLINK_endpoint_id(ep);
        /* start request sent to self ep */
        conf_object_t *link = SIMLINK_endpoint_link(&ilep->obj);
        i3c_link_impl_t *ilink = (i3c_link_impl_t *)link;

        /* Waiting for num_devs-1 devices to response */
        ilep->pending_acks = ilink->num_devs - 1;
        if (ilep->pending_acks == 0) {
                SIM_LOG_ERROR(&ilep->obj, 0,
                              "No other devices in current"
                              " configuration; master only"
                              " issue ibi start after ibi request");
        }
}

static void
handle_ibi_start(i3c_link_message_t *msg, uint64 epid_from,
                 i3c_link_endpoint_t *ilep, uint64 current_epid,
                 conf_object_t *device)
{
        ilep->current_master = epid_from;
        ASSERT(current_epid != epid_from);

        if (ilep->pending_ibi_req) {
                /* Forward master ibi start to this device */
                ilep->pending_ibi_req = false;
                ilep->slave_iface->ibi_start(device);
        } else {
                /* Forward back 0xff as none response */
                il_ibi_address((conf_object_t*)ilep, 0xff);
        }
}

static void
handle_ibi_address(i3c_link_message_t *msg, uint64 epid_from,
                   i3c_link_endpoint_t *ilep, uint64 current_epid,
                   conf_object_t *device)
{
        slave_data_t item;
        item.epid = epid_from;
        item.data = msg->status;
        VADD(ilep->slave_data_list, item);

        ilep->pending_acks -= 1;
        if (ilep->pending_acks == 0) {
                uint64 e = LINK_NULL_ID;
                uint64 d = 0xff;
                /* Pick up the lowest data as current_slave,
                   forward the data to master. */
                VFORI(ilep->slave_data_list, i) {
                        slave_data_t tmp = VGET(ilep->slave_data_list, i);
                        if (tmp.data < d) {
                                e = tmp.epid;
                                d = tmp.data;
                        }
                }
                VFREE(ilep->slave_data_list);
                ilep->current_slave = e;
                ilep->master_iface->ibi_address(device, d);
        }
}

static void
deliver(conf_object_t *ep, const link_message_t *msgdata)
{
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(2, ep, 0, "delivering to %s",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));

        i3c_link_message_t *msg = (i3c_link_message_t *)msgdata;
        uint64 epid_from = msg->src_epid;
        SIM_LOG_INFO(4, ep, 0,
                     "got message from %s:"
                     " type(%s), status(%d), data(%d)",
                     ep_dev_name(ep, epid_from),
                     i3c_type_name(msg->type),
                     msg->status, *(msg->payload.data));

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        const uint64 current_epid = SIMLINK_endpoint_id(ep);
        conf_object_t *device = SIMLINK_endpoint_device(ep);
        switch (msg->type) {
        case start_request:
                handle_start_request(msg, epid_from,
                                     ilep, current_epid, device);
                break;
        case start_response:
                handle_start_response(msg, epid_from,
                                      ilep, current_epid, device);
                break;
        case read_request:
                ASSERT(ilep->current_master == epid_from);
                ASSERT(ilep->current_slave == current_epid);
                ilep->slave_iface->read(device);
                break;
        case read_response:
                handle_read_response(msg, epid_from,
                                     ilep, current_epid, device);
                break;
        case write_request:
                /* The request is to communicate with legacy i2c device. Which is
                   corresponding to write() method in i2c_master_v2 interface. To
                   respond this request, the i2c slave device issues acknowledge.
                */
        case daa_address:
                ASSERT(ilep->current_master == epid_from);
                /* Even in broadcast, this is surfice since for the slave who
                   responds with ACK, will treat itself as current_slave. */
                ASSERT(ilep->current_slave == current_epid);
                ilep->legacy_write = true;
                ilep->slave_iface->write(device, *(msg->payload.data));
                break;
        case daa_address_bcast:
                handle_daa_address_bcast(msg, epid_from,
                                         ilep, current_epid, device);
                break;
        case sdr_write_request:
                ASSERT(ilep->current_master == epid_from);
                /* Even in broadcast, this is surfice since for the slave who
                   responds with ACK, will treat itself as current_slave. */
                ASSERT(ilep->current_slave == current_epid);
                ilep->slave_iface->sdr_write(device, msg->payload);
                break;
        case write_response: // send msg(ack/nack) to endpoint
                handle_write_response(msg, epid_from, ilep, current_epid, device);
                break;
        case daa_read:
                ASSERT(ilep->current_master == epid_from);
                ASSERT(ilep->current_slave == current_epid);
                ilep->slave_iface->daa_read(device);
                break;
        case daa_response:
                handle_daa_response(msg, epid_from, ilep, current_epid, device);
                break;
        case stop:
                handle_stop(msg, epid_from, ilep, current_epid, device);
                break;
        case ibi_request:
                ilep->master_iface->ibi_request(device);
                break;
        case ibi_start:
                handle_ibi_start(msg, epid_from, ilep, current_epid, device);
                break;
        case ibi_address:
                handle_ibi_address(msg, epid_from, ilep, current_epid, device);
                break;
        case ibi_acknowledge:
                ilep->current_slave = current_epid;
                ilep->slave_iface->ibi_acknowledge(device, msg->status);
                break;
        case hdr_write_request:
                ASSERT(ilep->current_master == epid_from);
                ilep->hdr_slave_iface->hdr_write(device, msg->payload);
                break;
        case hdr_read_request:
                ASSERT(ilep->current_master == epid_from);
                ilep->hdr_slave_iface->hdr_read(device, msg->status);
                break;
        case hdr_acknowledge_response:
                ASSERT(ilep->current_master == current_epid);
                handle_hdr_acknowledge(msg, epid_from, ilep,
                                      current_epid, device);
                break;
        case hdr_restart_request:
                ASSERT(ilep->current_master == epid_from);
                ilep->hdr_slave_iface->hdr_restart(device);
                break;
        case hdr_exit_request:
                ASSERT(ilep->current_master == epid_from);
                ilep->hdr_slave_iface->hdr_exit(device);
                break;
        case hdr_read_response:
                ASSERT(ilep->current_slave == epid_from);
                ASSERT(ilep->current_master == current_epid);
                ilep->hdr_master_iface->hdr_read_response(
                        device, msg->payload, msg->status);
                break;
        }
}

static void
link_config_value_updated(
        conf_object_t *link, const char *key, const frags_t *msg)
{
        i3c_link_impl_t *ilink = (i3c_link_impl_t *)link;
        ilink->num_devs += 1;
        SIM_LOG_INFO(4, &ilink->obj, 0,
                     "Added one more device, now in total %d endpoint(s)",
                     ilink->num_devs);
        if (strcmp(key, "hdr-slave-added") == 0) {
                uint64_t epid_added = frags_extract_le64(msg, 0);
                VADD(ilink->hdr_slave_list, epid_added);
                SIM_LOG_INFO(4, &ilink->obj, 0,
                "Added one more HDR slave device id=%zu, now in total %d HDR slave(s)",
                        epid_added, VLEN(ilink->hdr_slave_list));
        }
}

static void
link_config_value_removed(conf_object_t *link, const char *key)
{
        i3c_link_impl_t *ilink = (i3c_link_impl_t *)link;
        ilink->num_devs -= 1;
        SIM_LOG_INFO(4, &ilink->obj, 0,
                     "Remove one device, now in total %d endpoint(s)",
                     ilink->num_devs);
}

static void
link_ep_device_changed(conf_object_t *ep, conf_object_t *old_dev)
{
        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        const char *port = SIMLINK_endpoint_port(ep);
        conf_object_t *dev = SIMLINK_endpoint_device(ep);

        const i3c_master_interface_t *m
                = SIM_c_get_port_interface(dev, I3C_MASTER_INTERFACE, port);
        const i3c_slave_interface_t *s
                = SIM_c_get_port_interface(dev, I3C_SLAVE_INTERFACE, port);
        const i3c_daa_snoop_interface_t *snoop
                = SIM_c_get_port_interface(dev, I3C_DAA_SNOOP_INTERFACE, port);
        if (m == NULL && s == NULL) {
                SIM_LOG_ERROR(ep, 0, "device %s neither implements the "
                              I3C_MASTER_INTERFACE " nor the "
                              I3C_SLAVE_INTERFACE " interface",
                              SIM_object_name(dev));
        }
        const i3c_hdr_master_interface_t *hdr_m
                = SIM_c_get_port_interface(dev, I3C_HDR_MASTER_INTERFACE, port);
        const i3c_hdr_slave_interface_t *hdr_s
                = SIM_c_get_port_interface(dev, I3C_HDR_SLAVE_INTERFACE, port);

        ilep->master_iface = m;
        ilep->slave_iface = s;
        ilep->daa_snoop_iface = snoop;
        ilep->hdr_master_iface = hdr_m;
        ilep->hdr_slave_iface = hdr_s;

        if (old_dev == NULL) {
                /* Create a fragment containing the endpoint ID
                   to notify about the addition of a new HDR slave. */
                frags_t value;
                uint64_t epid = SIMLINK_endpoint_id(ep);
                frags_init_add(&value, &epid, sizeof(epid));
                SIMLINK_config_update_value(
                        SIMLINK_endpoint_link(ep),
                        hdr_s != NULL ? "hdr-slave-added" : "", &value);
        }
}

/* Link class */
static conf_object_t *
i3c_link_alloc_object(void *data)
{
        i3c_link_impl_t *ilink = MM_ZALLOC(1, i3c_link_impl_t);
        return &ilink->obj;
}

static void *
i3c_link_init_object(conf_object_t *obj, void *data)
{
        static const link_type_t link_methods = {
                .msg_to_attr = msg_to_attr,
                .msg_from_attr = msg_from_attr,
                .free_msg = free_msg,
                .marshal = marshal,
                .unmarshal = unmarshal,
                .deliver = deliver,
                .update_config_value = link_config_value_updated,
                .remove_config_value = link_config_value_removed,
                .device_changed = link_ep_device_changed
        };

        i3c_link_impl_t *ilink = (i3c_link_impl_t *)obj;
        SIMLINK_init(&ilink->obj, &link_methods);
        ilink->num_devs = 0;
        VINIT(ilink->hdr_slave_list);
        return &ilink->obj;
}

static void
i3c_link_finalize_instance(conf_object_t *obj)
{
        SIMLINK_finalize(obj);
}

static void
i3c_link_pre_delete_instance(conf_object_t *obj)
{
        SIMLINK_pre_delete(obj);
}

static int
i3c_link_delete_instance(conf_object_t *obj)
{
        i3c_link_impl_t *ilink = (i3c_link_impl_t *)obj;
        VFREE(ilink->hdr_slave_list);
        MM_FREE(obj);
        return 0;
}

/* Endpoint class */
static conf_object_t *
i3c_link_ep_alloc_object(void *data)
{
        i3c_link_endpoint_t *ilep = MM_ZALLOC(1, i3c_link_endpoint_t);
        return &ilep->obj;
}

static void *
i3c_link_ep_init_object(conf_object_t *obj, void *data)
{
        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)obj;
        SIMLINK_endpoint_init(&ilep->obj, false);

        ilep->main_master = 0;
        ilep->current_master = LINK_NULL_ID;
        ilep->current_slave = LINK_NULL_ID;
        ilep->pending_acks = 0;
        ilep->address = 0;
        VINIT(ilep->slave_list);
        ilep->slave_list_ack = I3C_noack;
        ilep->slave_list_counter = 0;
        VINIT(ilep->slave_data_list);
        ilep->in_daa = false;
        ilep->ccc = 0;
        ilep->snd_master = 0;
        ilep->legacy_write = false;

        return &ilep->obj;
}

static void
i3c_link_ep_finalize_instance(conf_object_t *obj)
{
        SIMLINK_endpoint_finalize(obj);
}

static void
i3c_link_ep_pre_delete_instance(conf_object_t *obj)
{
        SIMLINK_endpoint_disconnect(obj);
}

static int
i3c_link_ep_delete_instance(conf_object_t *obj)
{
        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)obj;
        VFREE(ilep->slave_list);
        VFREE(ilep->slave_data_list);
        MM_FREE(obj);
        return 0;
}

/* Methods which slave interface implements */
static void
il_start(conf_object_t *ep, uint8 addr)
{
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.start(%s, 0x%x)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)), addr);

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        const uint64 current_epid = SIMLINK_endpoint_id(ep);

        if (ilep->current_master == LINK_NULL_ID) {
                /* link idle */
        } else if (ilep->current_master == current_epid) {
                /* link busy on self, repeat start */
        } else {
                /* link busy on others */
                SIM_LOG_INFO(2, ep, 0,
                             "Got start request from device %s,"
                             " but link is busy on others",
                             SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));
                return;
        }

        ilep->address = addr;
        if (ilep->address == BROADCAST << 1)
                ilep->ccc = 0;
        /* Clear state for repeat start. */
        VFREE(ilep->slave_list);
        ilep->slave_list_ack = I3C_noack;
        ilep->current_slave = LINK_NULL_ID;

        prepare_start_request(ep, addr);

        /* Broadcast message */
        SIMLINK_send_message(ep, LINK_BROADCAST_ID,
                             new_status_message(current_epid,
                                                start_request,
                                                addr, 0, 0));
        return;
}

static void
write_common(conf_object_t *ep, bytes_t data, uint8 msg_type)
{
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.%s(%s, %d)",
                     msg_type == sdr_write_request? "sdr_write" : "write",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)),
                     *(data.data));

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        const uint64 current_epid = SIMLINK_endpoint_id(ep);

        if (current_epid != ilep->current_master)
                SIM_LOG_ERROR(ep, 0, "write request does not come from"
                              " current_master");

        /* broadcast */
        if (VLEN(ilep->slave_list) && !ilep->in_daa) {
                ilep->slave_list_counter = VLEN(ilep->slave_list);
                VFORI(ilep->slave_list, i) {
                        SIMLINK_send_message(
                                ep,
                                VGET(ilep->slave_list, i),
                                new_status_message(
                                        SIMLINK_endpoint_id(ep),
                                        msg_type,
                                        0, data.data, data.len));
                }
                return;
        }
        /* 1:1 normal write.
           Or daa address write. current_slave will get the assigned address,
           other slaves will know itself lost arbitration when they receive
           repeat start request.
        */
        if (ilep->in_daa) {
                msg_type = daa_address;
                ilep->current_slave = ilep->slave_data.epid;
        }
        SIMLINK_send_message(ep, ilep->current_slave,
                             new_status_message(SIMLINK_endpoint_id(ep),
                                                msg_type,
                                                0, data.data, data.len));

        /* Broadcast the assigned address to devices which implement
           i3c_daa_snoop interface */
        if (ilep->in_daa) {
                /* epid | daa data | assigned address */
                uint8 d[17];
                UNALIGNED_STORE64(d, ilep->slave_data.epid);
                UNALIGNED_STORE64(d + 8, ilep->slave_data.data);
                d[16] = *(data.data) >> 1;
                SIMLINK_send_message(ep, LINK_BROADCAST_ID,
                                     new_status_message(SIMLINK_endpoint_id(ep),
                                                        daa_address_bcast,
                                                        0, d, 17));
        }
}

static void
il_write(conf_object_t *ep, uint8 data)
{
        bytes_t d = (bytes_t){ .data = &data, .len = 1 };
        write_common(ep, d, write_request);
}

static void
il_sdr_write(conf_object_t *ep, bytes_t data)
{

        /* When the address is broadcast address, write down the following
           data sent by master. Used in secondary master scenario. */
        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        conf_object_t *link = SIMLINK_endpoint_link(ep);
        i3c_link_impl_t *ilink = (i3c_link_impl_t *)link;

        bool in_hdr = false;
        if ((ilep->address == BROADCAST << 1) && (ilep->ccc == 0)) {
                ilep->ccc = *(data.data);
                /* Enter HDR command codes */
                if (ilep->ccc >= 0x20 && ilep->ccc <= 0x27) {
                        uint8 buf[MAX_BUF_SIZE];
                        SIM_LOG_INFO(2, ep, 0, "i3c.%s.sdr_write entering HDR mode",
                                SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));
                        in_hdr = true;
                }
        }

        write_common(ep, data, sdr_write_request);

        if (in_hdr) {
                ilep->in_hdr = true;
                ilep->current_slave = LINK_NULL_ID;
                VFORI(ilep->slave_list, i) {
                        uint64 ep_id = VGET(ilep->slave_list, i);
                        if (VCONTAINSP(ilink->hdr_slave_list, (void *)ep_id)) {
                                continue;
                        }
                        VREMOVE(ilep->slave_list, i);
                }
        }
}

static void
il_read(conf_object_t *ep)
{
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.read(%s)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        if (SIMLINK_endpoint_id(ep) != ilep->current_master)
                SIM_LOG_ERROR(ep, 0, "read request does not come from"
                              " current_master");

        /* master signals read() to initiate normal read request. */
        SIMLINK_send_message(ep, ilep->current_slave,
                             new_status_message(SIMLINK_endpoint_id(ep),
                                                read_request,
                                                0, 0, 0));
}

static void
il_daa_read(conf_object_t *ep)
{
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.daa_read(%s)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        const uint64 current_epid = SIMLINK_endpoint_id(ep);

        if (current_epid != ilep->current_master)
                SIM_LOG_ERROR(ep, 0, "daa read request does not come from"
                              " current_master");
        ilep->in_daa = true;
        /* master signals daa read to initiate daa request. master only
           read from one slave when in normal read request, but it will
           read from a list of slaves in daa request.
        */
        if (VLEN(ilep->slave_list)) {
                ilep->slave_list_counter = VLEN(ilep->slave_list);
                VFORI(ilep->slave_list, i) {
                        SIMLINK_send_message(
                                ep,
                                VGET(ilep->slave_list, i),
                                new_status_message(
                                        current_epid,
                                        daa_read,
                                        0, 0, 0));
                }
        } else {
                SIM_LOG_ERROR(ep, 0, "daa read request should follow a"
                              " broadcast start");
        }
}

static void
il_stop(conf_object_t *ep)
{
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.stop(%s)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        uint8 status = 0;
        if (ilep->snd_master) {
                status = ilep->snd_master;
                ilep->snd_master = 0;
        }
        ilep->address = 0;
        VFREE(ilep->slave_list);
        ilep->slave_list_ack = I3C_noack;
        ilep->in_daa = false;
        ilep->ccc = 0;
        ilep->slave_list_counter = 0;

        /* Do some final self cleanup */
        master_stop_cleanup(ep, status);
        /* Broadcast stop message */
        SIMLINK_send_message(ep, LINK_BROADCAST_ID,
                             new_status_message(SIMLINK_endpoint_id(ep),
                                                stop,
                                                status, 0, 0));
}

static void
il_ibi_start(conf_object_t *ep)
{
        /* master receives ibi request, issues ibi start
           then slaves can send their address to enter into
           bus arbitration process. */
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.ibi_start(%s)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        if (!ilep->main_master)
                SIM_LOG_ERROR(ep, 0,
                              "The link is not configured with main master");
        if (ilep->current_master != LINK_NULL_ID)
                SIM_LOG_ERROR(ep, 0,
                              "The link is not idle when slave issues"
                              " ibi request");

        const uint64 current_epid = SIMLINK_endpoint_id(ep);
        prepare_ibi_start(ep);
        SIMLINK_send_message(ep, LINK_BROADCAST_ID,
                             new_status_message(
                                     current_epid,
                                     ibi_start,
                                     0, 0, 0));
}

static void
il_ibi_acknowledge(conf_object_t *ep, i3c_ack_t ack)
{
        /* master issues ibi acknowledge to current_slave,
           slave which does not receive ibi acknowledge will know itself
           lose arbitration. */
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.ibi_acknowledge(%s)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        if (ilep->current_slave == LINK_NULL_ID)
                SIM_LOG_ERROR(ep, 0,
                              "There is no current slave when master issues"
                              " ibi acknowledge");

        SIMLINK_send_message(ep, ilep->current_slave,
                             new_status_message(SIMLINK_endpoint_id(ep),
                                                ibi_acknowledge,
                                                ack, 0, 0));
}

/* Methods which master interface implements */
static void
il_acknowledge(conf_object_t *ep, i3c_ack_t ack)
{
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.acknowledge(%s, %d)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)), ack);

        /* Sanity check */
        if (ack != I3C_noack && ack != I3C_ack) {
                SIM_LOG_ERROR(ep, 0, "acknowledge: invalid ack value: %d", ack);
                ack = I3C_noack;
        }

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        uint64 current_epid = SIMLINK_endpoint_id(ep);

        uint8 msg_type = start_response;
        if (ilep->legacy_write) {
                /* The device is I2C slave device, it responds write request
                   with acknowledge. Or, this is acknowledge on daa address
                   write. */
                msg_type = write_response;
                ilep->legacy_write = false;
        } else {
                /* When in 1:1 transaction, current_slave is used as
                   communication target. When in broadcasting transaction,
                   every slave who responds start request with ACK treat
                   itself as current_slave. This also includes response to
                   daa address.
                */
                ilep->current_slave =
                        ack == I3C_ack ? current_epid : LINK_NULL_ID;
        }

        SIMLINK_send_message(ep, ilep->current_master,
                             new_status_message(current_epid,
                                                msg_type,
                                                ack, 0, 0));
}

static void
il_read_response(conf_object_t *ep, uint8 data, bool more)
{
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.read_response(%s, %d)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)), data);

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        if (SIMLINK_endpoint_id(ep) != ilep->current_slave)
                SIM_LOG_ERROR(ep, 0, "read response does not come from"
                              " current_slave");

        SIMLINK_send_message(ep, ilep->current_master,
                             new_status_message(SIMLINK_endpoint_id(ep),
                                                read_response,
                                                more, &data, 1));
}

static void
il_daa_response(conf_object_t *ep, uint64 id, uint8 bcr, uint8 dcr)
{
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.daa_response(%s, %lld, %d, %d)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)),
                     id, bcr, dcr);

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        uint64 data = id << 16 | bcr << 8 | dcr;
        SIMLINK_send_message(ep, ilep->current_master,
                             new_status_message(SIMLINK_endpoint_id(ep),
                                                daa_response,
                                                0, (uint8 *)&data, 8));
}

static void
il_ibi_request(conf_object_t *ep)
{
        /* slave issues this in three conditions: hot-join, IBI,
           secondary master */
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.ibi_request(%s)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        if (!ilep->main_master)
                SIM_LOG_ERROR(ep, 0,
                              "The link is not configured with main master");
        if (ilep->current_master != LINK_NULL_ID)
                SIM_LOG_ERROR(ep, 0,
                              "The link is not idle when slave issues"
                              " ibi request");

        ilep->pending_ibi_req = true;
        SIMLINK_send_message(ep, ilep->main_master,
                             new_status_message(SIMLINK_endpoint_id(ep),
                                                ibi_request,
                                                0, 0, 0));
}

static void
il_ibi_address(conf_object_t *ep, uint8 address)
{
        /* slave sends its ibi address to enter into bus arbitration,
           if the slave does not mean to participate in the arbitration,
           0xff is sent. */
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.ibi_address(%s)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)));

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        if (ilep->current_master == LINK_NULL_ID)
                SIM_LOG_ERROR(ep, 0,
                              "No current master to send ibi address to");

        SIMLINK_send_message(ep, ilep->current_master,
                             new_status_message(SIMLINK_endpoint_id(ep),
                                                ibi_address,
                                                address, 0, 0));
}

/* Method which daa snoop interface implements */
static void
il_assigned_address(conf_object_t *ep,
                    uint64 id, uint8 bcr, uint8 dcr, uint8 address)
{
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.assigned_address(%s, %lld, %d, %d, %d)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)),
                     id, bcr, dcr, address);

        /* epid | daa data | assigned address */
        uint8 d[17];
        uint64 data = id << 16 | bcr << 8 | dcr;
        UNALIGNED_STORE64(d, SIMLINK_endpoint_id(ep));
        UNALIGNED_STORE64(d + 8, data);
        d[16] = address;
        SIMLINK_send_message(ep, LINK_BROADCAST_ID,
                             new_status_message(SIMLINK_endpoint_id(ep),
                                                daa_address_bcast,
                                                0, d, 17));
}

static void
il_hdr_read_response(conf_object_t *ep, bytes_t bytes, bool more)
{
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.hdr_read_response(%s, len=%zu, more=%d)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)), bytes.len, more);

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        if (SIMLINK_endpoint_id(ep) != ilep->current_slave)
                SIM_LOG_ERROR(ep, 0, "read response does not come from"
                              " current_slave");

        SIMLINK_send_message(ep, ilep->current_master,
                             new_status_message(SIMLINK_endpoint_id(ep),
                                                hdr_read_response,
                                                more, bytes.data, bytes.len));

}

static void
il_hdr_acknowledge(conf_object_t *ep, i3c_ack_t ack)
{
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.hdr_acknowledge(%s, %d)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)), ack);

        /* Sanity check */
        if (ack != I3C_noack && ack != I3C_ack) {
                SIM_LOG_ERROR(ep, 0, "hdr_acknowledge: invalid ack value: %d", ack);
                ack = I3C_noack;
        }

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        uint64 current_epid = SIMLINK_endpoint_id(ep);

        SIMLINK_send_message(ep, ilep->current_master,
                             new_status_message(current_epid,
                                                hdr_acknowledge_response,
                                                ack, 0, 0));
}

static void
handle_hdr_acknowledge(i3c_link_message_t *msg, uint64 epid_from,
                       i3c_link_endpoint_t *ilep, uint64 current_epid,
                       conf_object_t *device)
{
        if (ilep->pending_acks == 0) {
                SIM_LOG_ERROR(&ilep->obj, 0,
                              "Unexpected hdr_acknowledge call from %s",
                              ep_dev_name(&ilep->obj, epid_from));
                return;
        }

        if (msg->status == I3C_ack) {
                if (ilep->current_slave == LINK_NULL_ID) {
                        ilep->current_slave = epid_from;
                        ilep->slave_list_ack = I3C_ack;
                } else if (ilep->current_slave != epid_from) {
                        SIM_LOG_ERROR(&ilep->obj, 0,
                                      "Multiple slaves (%s and %s) acked"
                                      " a hdr_write() on the same address",
                                      ep_dev_name(&ilep->obj,
                                                  ilep->current_slave),
                                      ep_dev_name(&ilep->obj,
                                                  epid_from));
                } else {
                        ilep->slave_list_ack = I3C_ack;
                }
        }

        ilep->pending_acks -= 1;
        if (ilep->pending_acks == 0) {
                if (ilep->current_slave == LINK_NULL_ID) {
                        SIM_LOG_INFO(2, &ilep->obj, 0,
                                     "NOACK received from all slave"
                                     " devices, noacking hdr_write");
                }
                /* All slaves have responded the hdr_write call, return
                   ACK since current_slave ack. */
                ilep->hdr_master_iface->hdr_acknowledge(device, ilep->slave_list_ack);
        }
}

static void
il_hdr_write(conf_object_t *ep, bytes_t data)
{
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.hdr_write(%s len=%zu)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)),
                     data.len);

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        const uint64 current_epid = SIMLINK_endpoint_id(ep);

        if (current_epid != ilep->current_master)
                SIM_LOG_ERROR(ep, 0, "hdr_write() request does not come from"
                              " current_master");

        if (!ilep->in_hdr) {
                SIM_LOG_ERROR(ep, 0, "hdr_write() while not in hdr mode");
                return;
        }

        ilep->slave_list_ack = I3C_noack;
        if (ilep->current_slave != LINK_NULL_ID) {
                ilep->pending_acks = 1;
                SIMLINK_send_message(
                        ep,
                        ilep->current_slave,
                        new_status_message(
                                SIMLINK_endpoint_id(ep),
                                hdr_write_request,
                                0, data.data, data.len));
        } else {
                ilep->pending_acks = VLEN(ilep->slave_list);
                VFORI(ilep->slave_list, i) {
                        uint64_t ep_id = VGET(ilep->slave_list, i);
                        SIMLINK_send_message(
                                ep,
                                ep_id,
                                new_status_message(
                                        SIMLINK_endpoint_id(ep),
                                        hdr_write_request,
                                        0, data.data, data.len));
                }
        }
}

static void
il_hdr_read(conf_object_t *ep, uint32 max_len)
{
        uint8 buf[MAX_BUF_SIZE];
        SIM_LOG_INFO(4, ep, 0, "i3c.hdr_read(%s max_len=%d)",
                     SIMLINK_endpoint_dev_name(ep, BUFFER_T(buf)),
                     max_len);

        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        const uint64 current_epid = SIMLINK_endpoint_id(ep);

        if (current_epid != ilep->current_master)
                SIM_LOG_ERROR(ep, 0, "hdr_read() request does not come from"
                              " current_master");
        if (ilep->current_slave == LINK_NULL_ID) {
                SIM_LOG_ERROR(ep, 0, "unexpected hdr_read() request");
                return;
        }
        if (!ilep->in_hdr) {
                SIM_LOG_ERROR(ep, 0, "hdr_read() while not in hdr mode");
                return;
        }

        SIMLINK_send_message(
                ep,
                ilep->current_slave,
                new_status_message(
                        SIMLINK_endpoint_id(ep),
                        hdr_read_request,
                        max_len, 0, 0));
}

static void
il_hdr_restart(conf_object_t *ep)
{
        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        conf_object_t *link = SIMLINK_endpoint_link(ep);
        i3c_link_impl_t *ilink = (i3c_link_impl_t *)link;

        if (!ilep->in_hdr) {
                SIM_LOG_ERROR(ep, 0, "hdr_restart() while not in hdr mode");
                return;
        }
        ilep->current_slave = LINK_NULL_ID;
        ilep->slave_list_ack = I3C_noack;
        VCLEAR(ilep->slave_list);
        VFORI(ilink->hdr_slave_list, i) {
                uint64 ep_id = VGET(ilink->hdr_slave_list, i);
                VADD(ilep->slave_list, ep_id);

                SIMLINK_send_message(
                        ep,
                        ep_id,
                        new_status_message(
                                SIMLINK_endpoint_id(ep),
                                hdr_restart_request,
                                0, NULL, 0));
        }
}

static void
il_hdr_exit(conf_object_t *ep)
{
        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)ep;
        conf_object_t *link = SIMLINK_endpoint_link(ep);
        i3c_link_impl_t *ilink = (i3c_link_impl_t *)link;

        if (!ilep->in_hdr) {
                SIM_LOG_ERROR(ep, 0, "hdr_exit() while not in hdr mode");
                return;
        }
        ilep->current_slave = LINK_NULL_ID;
        ilep->slave_list_ack = I3C_noack;
        VCLEAR(ilep->slave_list);
        ilep->in_hdr = false;
        VFORI(ilink->hdr_slave_list, i) {
                uint64 ep_id = VGET(ilink->hdr_slave_list, i);

                SIMLINK_send_message(
                        ep,
                        ep_id,
                        new_status_message(
                                SIMLINK_endpoint_id(ep),
                                hdr_exit_request,
                                0, NULL, 0));
        }
}

static attr_value_t
get_int(conf_object_t *obj, void *user_data)
{
        uint8 val = *(uint8 *)((uintptr_t)obj + (uintptr_t)user_data);
        return SIM_make_attr_int64(val);
}

static set_error_t
set_int(conf_object_t *obj, attr_value_t *val, void *user_data)
{
        uint8 value = SIM_attr_integer(*val);
        uint8 *p = (uint8 *)((uintptr_t)obj + (uintptr_t)user_data);
        *p = value;
        return Sim_Set_Ok;
}

static attr_value_t
get_bool(conf_object_t *obj, void *user_data)
{
        bool val = *(bool *)((uintptr_t)obj + (uintptr_t)user_data);
        return SIM_make_attr_boolean(val);
}

static set_error_t
set_bool(conf_object_t *obj, attr_value_t *val, void *user_data)
{
        bool value = SIM_attr_boolean(*val);
        bool *p = (bool *)((uintptr_t)obj + (uintptr_t)user_data);
        *p = value;
        return Sim_Set_Ok;
}

static attr_value_t
get_slave_list(conf_object_t *obj)
{
        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)obj;
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
        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)obj;
        size_t len = SIM_attr_list_size(*val);
        VRESIZE(ilep->slave_list, len);
        for (int i = 0; i < len; i++) {
                VSET(ilep->slave_list, i,
                     SIM_attr_integer(SIM_attr_list_item(*val, i)));
        }

        return Sim_Set_Ok;
}

static attr_value_t
get_slave_data_list(conf_object_t *obj)
{
        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)obj;
        attr_value_t l = SIM_alloc_attr_list(VLEN(ilep->slave_data_list));
        VFORI(ilep->slave_data_list, i) {
                slave_data_t tmp = VGET(ilep->slave_data_list, i);
                attr_value_t item = SIM_alloc_attr_list(2);
                SIM_attr_list_set_item(
                        &item, 0, SIM_make_attr_uint64(tmp.epid));
                SIM_attr_list_set_item(
                        &item, 1, SIM_make_attr_uint64(tmp.data));
                SIM_attr_list_set_item(&l, i, item);
        }
        return l;
}

static set_error_t
set_slave_data_list(conf_object_t *obj, attr_value_t *val)
{
        i3c_link_endpoint_t *ilep = (i3c_link_endpoint_t *)obj;
        size_t len = SIM_attr_list_size(*val);
        VRESIZE(ilep->slave_data_list, len);
        for (int i = 0; i < len; i++) {
                slave_data_t item;
                item.epid = SIM_attr_integer(
                        SIM_attr_list_item(SIM_attr_list_item(*val, i), 0));
                item.data = SIM_attr_integer(
                        SIM_attr_list_item(SIM_attr_list_item(*val, i), 1));
                VSET(ilep->slave_data_list, i, item);
        }

        return Sim_Set_Ok;
}

static attr_value_t
get_num_hdr_devs(conf_object_t *obj)
{
        i3c_link_impl_t *ilink = (i3c_link_impl_t*)obj;
        return SIM_make_attr_int64(VLEN(ilink->hdr_slave_list));
}

void
init_i3c_link()
{
        const class_data_t link_cls_funcs = {
                .alloc_object = i3c_link_alloc_object,
                .init_object = i3c_link_init_object,
                .finalize_instance = i3c_link_finalize_instance,
                .pre_delete_instance = i3c_link_pre_delete_instance,
                .delete_instance = i3c_link_delete_instance,
                .class_desc = "model of I3C link",
                .description = "I3C link"
        };
        conf_class_t *link_cls = SIM_register_class("i3c_link_impl",
                                                    &link_cls_funcs);
        SIMLINK_register_class(link_cls);

        SIM_register_attribute(
                link_cls, "num_hdr_devs",
                get_num_hdr_devs,
                NULL,
                Sim_Attr_Read_Only | Sim_Attr_Pseudo, "i",
                "Number of devices that supports HDR traffic on the link");

        const class_data_t ep_cls_funcs = {
                .alloc_object = i3c_link_ep_alloc_object,
                .init_object = i3c_link_ep_init_object,
                .finalize_instance = i3c_link_ep_finalize_instance,
                .pre_delete_instance = i3c_link_ep_pre_delete_instance,
                .delete_instance = i3c_link_ep_delete_instance,
                .class_desc = "model of I3C link endpoint",
                .description = "I3C link endpoint"
        };
        conf_class_t *ep_cls = SIM_register_class("i3c_link_endpoint",
                                                  &ep_cls_funcs);
        SIMLINK_register_endpoint_class(ep_cls, "[iiid]");

        SIM_register_attribute_with_user_data(
                ep_cls, "main_master",
                get_int,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, main_master),
                set_int,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, main_master),
                Sim_Attr_Optional, "i",
                "Endpoint ID connecting to the device that has overall control"
                " of the I3C link.");
        SIM_register_attribute_with_user_data(
                ep_cls, "current_master",
                get_int,
                (void *)(uintptr_t)offsetof(
                        i3c_link_endpoint_t, current_master),
                set_int,
                (void *)(uintptr_t)offsetof(
                        i3c_link_endpoint_t, current_master),
                Sim_Attr_Optional, "i",
                "The endpoint id of current active master, initialized as"
                " LINK_NULL_ID which indicates invalid endpoint id");
        SIM_register_attribute_with_user_data(
                ep_cls, "current_slave",
                get_int,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, current_slave),
                set_int,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, current_slave),
                Sim_Attr_Optional, "i",
                "The endpoint id of current active slave, initialized as"
                " LINK_NULL_ID which indicates invalid endpoint id");
        SIM_register_attribute_with_user_data(
                ep_cls, "pending_acks",
                get_int,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, pending_acks),
                set_int,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, pending_acks),
                Sim_Attr_Optional, "i",
                "The number of devices we are awaiting a start response");
        SIM_register_attribute_with_user_data(
                ep_cls, "address",
                get_int,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, address),
                set_int,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, address),
                Sim_Attr_Optional, "i",
                "Save address status for start request");
        SIM_register_attribute(
                ep_cls, "slave_list",
                get_slave_list,
                set_slave_list,
                Sim_Attr_Optional, "[i*]",
                "IDs of endpoints used when more than one slave"
                " communicates with master");
        SIM_register_attribute_with_user_data(
                ep_cls, "slave_list_ack",
                get_int,
                (void *)(uintptr_t)offsetof(
                        i3c_link_endpoint_t, slave_list_ack),
                set_int,
                (void *)(uintptr_t)offsetof(
                        i3c_link_endpoint_t, slave_list_ack),
                Sim_Attr_Optional, "i",
                "Save the combined response come from slaves in slave_list");
        SIM_register_attribute_with_user_data(
                ep_cls, "slave_list_counter",
                get_int,
                (void *)(uintptr_t)offsetof(
                        i3c_link_endpoint_t, slave_list_counter),
                set_int,
                (void *)(uintptr_t)offsetof(
                        i3c_link_endpoint_t, slave_list_counter),
                Sim_Attr_Optional, "i",
                "The number of slaves we are awaiting response in slave_list");
        SIM_register_attribute(
                ep_cls, "slave_data_list",
                get_slave_data_list,
                set_slave_data_list,
                Sim_Attr_Optional, "[[ii]*]",
                "Keeps a list of pair (ID and data) come from slave."
                " The 'data' can be slave daa data when in DAA process,"
                " or slave address when slave issues IBI request"
                " (hot-join, IBI, secondary master)");
        SIM_register_attribute_with_user_data(
                ep_cls, "in_daa",
                get_bool,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, in_daa),
                set_bool,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, in_daa),
                Sim_Attr_Optional, "b",
                "True when the endpoint is in DAA process");
        SIM_register_attribute_with_user_data(
                ep_cls, "ccc",
                get_int,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, ccc),
                set_int,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, ccc),
                Sim_Attr_Optional, "i",
                "Save data sent following start request");
        SIM_register_attribute_with_user_data(
                ep_cls, "secondary_master",
                get_int,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, snd_master),
                set_int,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, snd_master),
                Sim_Attr_Optional, "i",
                "Endpoind ID of secondary master");
        SIM_register_attribute_with_user_data(
                ep_cls, "legacy_write",
                get_bool,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, legacy_write),
                set_bool,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, legacy_write),
                Sim_Attr_Optional, "b",
                "True when master is communicating with i2c slaves, or"
                " write daa address");
        SIM_register_attribute_with_user_data(
                ep_cls, "hdr_mode",
                get_bool,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, in_hdr),
                set_bool,
                (void *)(uintptr_t)offsetof(i3c_link_endpoint_t, in_hdr),
                Sim_Attr_Optional, "b",
                "True when master has entered HDR mode");

        static const i3c_slave_interface_t i3c_slave_ifc = {
                .start = il_start,
                .write = il_write,
                .sdr_write = il_sdr_write,
                .read = il_read,
                .daa_read = il_daa_read,
                .stop = il_stop,
                .ibi_start = il_ibi_start,
                .ibi_acknowledge = il_ibi_acknowledge,
        };
        SIM_register_interface(ep_cls, I3C_SLAVE_INTERFACE, &i3c_slave_ifc);

        static const i3c_master_interface_t i3c_master_ifc = {
                .acknowledge = il_acknowledge,
                .read_response = il_read_response,
                .daa_response = il_daa_response,
                .ibi_request = il_ibi_request,
                .ibi_address = il_ibi_address,
        };
        SIM_register_interface(ep_cls, I3C_MASTER_INTERFACE, &i3c_master_ifc);

        static const i3c_daa_snoop_interface_t i3c_daa_snoop_ifc = {
                .assigned_address = il_assigned_address,
        };
        SIM_register_interface(ep_cls, I3C_DAA_SNOOP_INTERFACE,
                               &i3c_daa_snoop_ifc);

        static const i3c_hdr_master_interface_t i3c_hdr_master_ifc = {
                .hdr_read_response = il_hdr_read_response,
                .hdr_acknowledge = il_hdr_acknowledge,
        };
        SIM_register_interface(ep_cls, I3C_HDR_MASTER_INTERFACE,
                               &i3c_hdr_master_ifc);

        static const i3c_hdr_slave_interface_t i3c_hdr_slave_ifc = {
                .hdr_write = il_hdr_write,
                .hdr_read = il_hdr_read,
                .hdr_restart = il_hdr_restart,
                .hdr_exit = il_hdr_exit,
        };
        SIM_register_interface(ep_cls, I3C_HDR_SLAVE_INTERFACE,
                               &i3c_hdr_slave_ifc);
}
