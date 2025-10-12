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

/* Sample implementation of a link that broadcasts byte strings to all other
   devices connected to the same link. */

#include <stdlib.h>

#include <simics/module-host-config.h>
#include <simics/base/types.h>
#include <simics/base/conf-object.h>
#include <simics/devs/datagram-link.h>

#include <simics/devs/liblink.h>

/* The main link object type. */
/*                        <add id="dl_dl_t"><insert-upto text="k_t;"/></add> */
typedef struct {
        conf_object_t obj;

        /* Any link-specific parameters would go here. */
} datagram_link_t;

/* The endpoint object type. */
/*                        <add id="dl_de_t"><insert-upto text="t_t;"/></add> */
typedef struct {
        conf_object_t obj;

        /* Any endpoint-specific state would go here. */
} datagram_link_endpoint_t;

/* A single message. */                      
/*                       <add id="dl_msg_t"><insert-upto text="e_t;"/></add> */
typedef struct {
        link_message_t common;               /* should always be first */
        /* The actual data in the message - in our case an allocated
           byte string owned by this structure. */
        bytes_t payload;
} datagram_link_message_t;

/* Constructor for messages; allocates and returns a new message. */
/*               <add id="dl_new"><insert-until text="// dl_new_end"/></add> */
static link_message_t *
new_datagram_message(const uint8 *data, size_t len)
{
        datagram_link_message_t *m = MM_MALLOC(1, datagram_link_message_t);
        SIMLINK_init_message(&m->common);
        uint8 *d = MM_MALLOC(len, uint8);
        memcpy(d, data, len);
        m->payload = (bytes_t){.data = d, .len = len};
        return &m->common;
}
                                                      // dl_new_end

/* Free a message. This allows messages to be allocated in link-specific
   ways, as long as the chosen mechanism is thread-safe. */
/*                           <add id="dl_free"><insert-upto text="}"/></add> */
static void
free_msg(conf_object_t *link, link_message_t *lm)
{
        datagram_link_message_t *m = (datagram_link_message_t *)lm;
        MM_FREE((uint8 *)m->payload.data);
        m->payload.data = NULL;
        MM_FREE(m);
}

/* Convert a message to an attribute value. */
/*                           <add id="dl_to_a"><insert-upto text="}"/></add> */
static attr_value_t
msg_to_attr(conf_object_t *link, const link_message_t *lm)
{
        const datagram_link_message_t *m = 
                (const datagram_link_message_t *)lm;
        return SIM_make_attr_data(m->payload.len, m->payload.data);
}

/* Create a message from an attribute value. */
/*                           <add id="dl_fr_a"><insert-upto text="}"/></add> */
static link_message_t *
msg_from_attr(conf_object_t *link, attr_value_t attr)
{
        return new_datagram_message(SIM_attr_data(attr),
                                    SIM_attr_data_size(attr));
}

/* Convert a message to a byte string, which is then passed to finish(). */
/*                           <add id="dl_mrsh"><insert-upto text="}"/></add> */
static void
marshal(conf_object_t *link, const link_message_t *lm,
        void (*finish)(void *data, const frags_t *msg), 
        void *finish_data)
{
        const datagram_link_message_t *m = 
                (const datagram_link_message_t *)lm;

        /* Our message just consists of a byte string, 
           so this is very easy. */
        frags_t buf;
        frags_init_add(&buf, m->payload.data, m->payload.len);
        finish(finish_data, &buf);
}

/* Create a message from marshalled data and return it. */
/*                            <add id="dl_unm"><insert-upto text="}"/></add> */
static link_message_t *
unmarshal(conf_object_t *link, const frags_t *data)
{
        size_t len = frags_len(data);
        uint8 bytes[len];
        frags_extract(data, bytes);
        return new_datagram_message(bytes, len);
}

/* Deliver a message to the indicated endpoint. */
/*                            <add id="dl_dlv"><insert-upto text="}"/></add> */
static void
deliver(conf_object_t *ep, const link_message_t *lm)
{
        const datagram_link_message_t *m = 
                (const datagram_link_message_t *)lm;
        conf_object_t *dev = SIMLINK_endpoint_device(ep);
        const char *port = SIMLINK_endpoint_port(ep);
        const datagram_link_interface_t *dli =
                SIM_c_get_port_interface(dev, "datagram_link", port);
        if (dli)
                dli->receive(dev, m->payload);
        else
                SIM_LOG_ERROR(ep, 0, "Device does not implement"
                              " datagram_link interface");
}

static void
link_config_value_updated(conf_object_t *link, const char *key, 
                          const frags_t *msg)
{
        /* We have no link-specific configuration data, so no action here. */
}

static void
link_config_value_removed(conf_object_t *link, const char *key)
{
        /* We have no link-specific configuration data, so no action here. */
}

/* Called to create a new link object. */
/*                     <add id="dl_ni"><insert-until text="// dlnie"/></add> */
static conf_object_t *
datagram_link_alloc_object(void *data)
{
        datagram_link_t *dl = MM_ZALLOC(1, datagram_link_t);
        return &dl->obj;
}

static void *
datagram_link_init_object(conf_object_t *obj, void *data)
{
        datagram_link_t *dl = (datagram_link_t *)obj;

        static const link_type_t link_methods = {
                .msg_to_attr = msg_to_attr,
                .msg_from_attr = msg_from_attr,
                .free_msg = free_msg,
                .marshal = marshal,
                .unmarshal = unmarshal,
                .deliver = deliver,
                .update_config_value = link_config_value_updated,
                .remove_config_value = link_config_value_removed,
        };
        SIMLINK_init(&dl->obj, &link_methods);

        return &dl->obj;
}
                                                                       // dlnie

/* Called when the link object has been set up (all attributes set). */
/*                            <add id="dl_fin"><insert-upto text="}"/></add> */
static void
datagram_link_finalize_instance(conf_object_t *obj)
{
        SIMLINK_finalize(obj);
}

static void
datagram_link_pre_delete_instance(conf_object_t *obj)
{
        SIMLINK_pre_delete(obj);
}

static int
datagram_link_delete_instance(conf_object_t *obj)
{
        MM_FREE(obj);
        return 0;
}

/* Send a message to all other endpoints connected to the link. */
/*                            <add id="dl_lsm"><insert-upto text="}"/></add> */
static void
receive(conf_object_t *NOTNULL ep, bytes_t msg)
{
        SIMLINK_send_message(ep, LINK_BROADCAST_ID, 
                             new_datagram_message(msg.data, msg.len));
}

static conf_object_t *
datagram_link_endpoint_alloc_object(void *data)
{
        datagram_link_endpoint_t *dlep =
                MM_ZALLOC(1, datagram_link_endpoint_t);
        return &dlep->obj;
}

/*                           <add id="dl_nepi"><insert-upto text="}"/></add> */
static void *
datagram_link_endpoint_init_object(conf_object_t *obj, void *data)
{
        datagram_link_endpoint_t *dlep =
                (datagram_link_endpoint_t *)obj;
        SIMLINK_endpoint_init(&dlep->obj, false);
        return dlep;
}

/*                           <add id="dl_nepf"><insert-upto text="}"/></add> */
static void
datagram_link_endpoint_finalize_instance(conf_object_t *ep)
{
        SIMLINK_endpoint_finalize(ep);
}

static int
datagram_link_endpoint_delete_instance(conf_object_t *ep)
{
        MM_FREE(ep);
        return 0;
}

/*                  <add id="dl_init"><insert-upto text="library();"/></add>
                    <add id="dl_ini2"><insert-until text="// dl_ini2_end"/></add> */
void
init_local()
{
        /* The link library must always be initialised first. */
        SIMLINK_init_library();

        const class_data_t cl_methods = {
                .alloc_object = datagram_link_alloc_object,
                .init_object = datagram_link_init_object,
                .finalize_instance = datagram_link_finalize_instance,
                .pre_delete_instance = datagram_link_pre_delete_instance,
                .delete_instance = datagram_link_delete_instance,
                .class_desc = "link that broadcasts byte strings",
                .description = "A link that broadcasts byte strings."
        };
        conf_class_t *cl = SIM_register_class("datagram_link_impl", 
                                              &cl_methods);

        /* Tell the link library what class represents the link */
        SIMLINK_register_class(cl);

        const class_data_t epcl_methods = {
                .alloc_object = datagram_link_endpoint_alloc_object,
                .init_object = datagram_link_endpoint_init_object,
                .finalize_instance = datagram_link_endpoint_finalize_instance,
                .pre_delete_instance = SIMLINK_endpoint_disconnect,
                .delete_instance = datagram_link_endpoint_delete_instance,
                .class_desc = "endpoint for datagram links",
                .description = "Endpoint for datagram link objects."
        };
        conf_class_t *epcl = SIM_register_class("datagram_link_endpoint",
                                                &epcl_methods);

        static const datagram_link_interface_t dgram_link_if = {
                .receive = receive
        };
        SIM_register_interface(epcl, "datagram_link", &dgram_link_if);

        /* Tell the link library what class we use for endpoints */
        SIMLINK_register_endpoint_class(epcl, "d");
}
                                                                 // dl_ini2_end
