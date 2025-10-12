# © 2011 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


### Common link component functionality

import component_utils
import cli
import re

# used by cli.doc
__simicsapi_doc_id__ = 'linkcomp_api'

import simics

from pyobj import ConfObject, SimpleAttribute, _ConfObjectMeta
from comp import (StandardComponent, get_pre_obj_object, set_pre_obj_object,
                  ConfigAttribute, Attribute, Interface, pre_obj, CompException)
from simics import Sim_Attr_Required

class _basic_link_connector(ConfObject):
    """Generic class representing a connector object for a link"""
    _do_not_init = object()

    def _finalize(self):
        super()._finalize()
        if not self.endpoint.val:
            simics.SIM_require_object(self.owner.val)
            self.owner.val.object_data.add_connector_ep(self.obj)

    def _pre_delete(self):
        # if this connector contained a valid endpoint, destroy it at the same
        # time
        if isinstance(self.endpoint.val, simics.conf_object_t):
            simics.SIM_delete_objects([self.endpoint.val])
        super()._pre_delete()

    # attributes representing the connector status, identical to those in the
    # standard connector object
    class connector_type(SimpleAttribute(None, 's', Sim_Attr_Required)):
        """Type used to match which other connector objects this connector can
        connect to."""
    class hotpluggable(SimpleAttribute(False, 'b', Sim_Attr_Required)):
        """If true, this connector can be connected or disconnected after
        instantiation. If false, the connection must be made before the
        component is instantiated."""
    class required(SimpleAttribute(False, 'b', Sim_Attr_Required)):
        """If true, this connector should be connected before its component can
        be instantiated. If false, it can be left empty."""
    class multi(SimpleAttribute(False, 'b', Sim_Attr_Required)):
        """If true, more than one connector object can be connected to this
        connector at the same time."""
    class direction(SimpleAttribute(0, 'i', Sim_Attr_Required)):
        """Direction of the connector: up, down or any"""
    class connector_name(SimpleAttribute("", 's', Sim_Attr_Required)):
        """Name of the connector"""
    class owner(SimpleAttribute(None, 'o', Sim_Attr_Required)):
        """Component to which this connector applies"""
        def setter(self, val):
            iface = 'component_connector'
            if not hasattr(val.iface, iface):
                simics.SIM_attribute_error(
                    '%s interface not found in object %s' % (iface, val.name))
                return simics.Sim_Set_Interface_Not_Found

            super(_basic_link_connector.owner, self).setter(val)

    class destination(SimpleAttribute(list, '[o*]')):
        """List of connections to this connector object. The connections listed
        here are not yet valid if the connecting component or the component
        itself are not instantiated yet."""
    class old_destination(SimpleAttribute(list, '[o*]')):
        """List of valid connections as of the last instantiation that
        concerned this component."""

    class endpoint(Attribute):
        """Link endpoint object associated to this connector"""
        attrtype = 'n|o'
        def _initialize(self):
            self.val = None
        def getter(self):
            # we can't just return what we have, since the endpoint object may
            # still be only a pre-conf-object that is not allowed as an
            # attribute value
            return (self.val if (isinstance(self.val, simics.conf_object_t)
                                 and not component_utils.get_writing_template())
                    else None)
        def setter(self, val):
            self.val = val

    class connector_template(SimpleAttribute(None, 's',
                                             Sim_Attr_Required)):
        """Name of the link connector template used to create this connector"""

    class connector(Interface):
        """Connector interface, with the same implementation as the standard
        connector"""
        def type(self):
            return self._up.connector_type.val
        def hotpluggable(self):
            return self._up.hotpluggable.val
        def required(self):
            return self._up.required.val
        def multi(self):
            return self._up.multi.val
        def direction(self):
            return self._up.direction.val
        def add_destination(self, dst):
            # guaranteed by component system
            assert hasattr(dst.iface, 'connector')
            # component system guarantees that connector types don't mismatch
            assert dst.iface.connector.type() == self._up.connector_type.val
            # component system guarantees that we are not already connected
            assert self._up.multi.val or self._up.destination.val == []
            if not hasattr(self._up.owner.val.iface, 'component_connector'):
                raise cli.CliError(
                    'component_connector interface not found in %s'
                    % (self._up.owner.val.name,))
            attr = self._up.owner.val.iface.component_connector.get_check_data(
                self._up.obj)
            if not dst.iface.connector.check(attr):
                simics.SIM_log_error(self._up.obj, 0,
                                     'connection refused by %s' % dst.name)
                return False
            self._up.destination.val.append(dst)
            return True

        def remove_destination(self, dst):
            def is_eth_probe(o):
                return (isinstance(o, simics.conf_object_t)
                        and o.classname == "eth-probe")

            # If there is a probe connected, delete it before removing.
            if hasattr(self._up.endpoint.val, 'device'):
                while hasattr(self._up.endpoint.val.device, 'probe'):
                    probe = getattr(self._up.endpoint.val.device, 'probe')
                    if not probe or not is_eth_probe(probe):
                        break
                    cli.run_command('%s.delete' % probe.name)

            self._up.destination.val.remove(dst)
            return True
        def destination(self):
            return self._up.destination.val
        def update(self):
            for cnt in self._up.destination.val:
                if not cnt in self._up.old_destination.val:
                    comp_iface = self._up.owner.val.iface.component_connector
                    attr = comp_iface.get_connect_data(self._up.obj)
                    cnt.iface.connector.connect(attr)
            for cnt in self._up.old_destination.val:
                if not cnt in self._up.destination.val:
                    cnt.iface.connector.disconnect()
            self._up.old_destination.val = self._up.destination.val[:]
        def check(self, attr):
            return self._up.owner.val.iface.component_connector.check(
                self._up.obj, attr)
        def connect(self, attr):
            self._up.owner.val.iface.component_connector.connect(self._up.obj,
                                                                 attr)
        def disconnect(self):
            self._up.owner.val.iface.component_connector.disconnect(
                self._up.obj)
        def deletion_requested(self):
            # link connectors are always destroyed on disconnect, as they
            # recreate themselves as needed
            return True

class static_link_connector(_basic_link_connector):
    """Static link connector representing one connection to the link. This
    connector does not grow dynamically and can be reused several times. It is
    useful for links that have specific ports to which only one device can
    connect (for example, a serial link with two devices)."""
    _class_desc = "static connector to a link"

    class connector(_basic_link_connector.connector):
        def remove_destination(self, dst):
            _basic_link_connector.connector.remove_destination(self, dst)
            owner = self._up.owner.val.object_data
            slot_name = self._up.obj.component_slot
            owner.dereference_link_connector_object(self._up.obj)
            owner.add_named_link_connector_object(
                slot_name, None,
                owner.connector_templates[self._up.connector_template.val])
            return True

class dynamic_link_connector(_basic_link_connector):
    """Dynamic link connector representing one connection to the
    link. Everytime this connector is filled, it tries---if it is allowed---to
    create a new instance of itself so there is always one free connector
    available. It is useful for links that accept an undetermined number of
    connections (although the component itself may set limit to how this
    connector can grow)."""
    _class_desc = "dynamic link connector"

    def _finalize(self):
        _basic_link_connector._finalize(self)

    class slot_template(SimpleAttribute(None, 's', Sim_Attr_Required)):
        """Name template to be used for newly created connectors. The name
        template is expected to contain at least one '%d' that will be used to
        give the connector a unique number."""

    class connector(_basic_link_connector.connector):
        def add_destination(self, dst):
            if not _basic_link_connector.connector.add_destination(self, dst):
                return False
            owner = self._up.owner.val.object_data
            if owner.check_new_connector_allowed(self._up.obj):
                # add a new connector for the next connection
                owner.add_link_connector_object(
                    self._up.slot_template.val,
                    owner.connector_templates[self._up.connector_template.val])
            return True
        def remove_destination(self, dst):
            _basic_link_connector.connector.remove_destination(self, dst)
            owner = self._up.owner.val.object_data
            slot_name = self._up.obj.component_slot
            owner.dereference_link_connector_object(self._up.obj)
            if not owner.check_destroy_connector_allowed(self._up.obj):
                # if this connector should stay, recreate one with the same
                # name and a new endpoint
                owner.add_named_link_connector_object(
                    slot_name, self._up.slot_template.val,
                    owner.connector_templates[self._up.connector_template.val])
            return True

import random
def create_generic_endpoint(cls, link, dev):
    while True:
        ep_id = random.getrandbits(64)
        if ep_id != 0 and ep_id != (1 << 64) - 1:
            return pre_obj('ep%x' % ep_id, cls,
                           id = ep_id, link = link, device = dev)

class link_component(
        StandardComponent,
        metaclass=cli.doc(
            'link components base class',
            synopsis = False,
            metaclass = _ConfObjectMeta,
            example = '<insert id="ets_comp"/>')):
    """Class from which to inherit when creating a new custom link component."""

    _docargs = { 'namespace': 'link_component' }

    _do_not_init = object()

    @cli.doc('add link object and initial connectors',
             return_value = 'None',
             example = '<insert id="ets_comp"/>',
             **_docargs)
    def add_objects(self):
        '''This function should be overridden when inheriting from
        <class>link_component</class>. It is expected to create a
        pre-conf-object for the link and to add the initial connectors of the
        component using <fun>link_component.add_link_connector()</fun>.
        <fun>add_objects()</fun> is only called when creating a component from
        scratch; when restoring a checkpoint, objects are assumed to have
        already been created.'''
        pass

    @cli.doc('register connector templates',
             return_value = 'None',
             example = '<insert id="ets_comp"/>',
             **_docargs)
    def register_connector_templates(self):
        '''This function should be overridden when inheriting from
        <class>link_component</class>. It is expected to register the connector
        templates that will be used in <fun>add_objects()</fun>. Unlike
        <fun>add_objects()</fun>, this function is always called when creating
        the component, either from scratch or when restoring a checkpoint.'''
        pass

    class component_icon(StandardComponent.component_icon):
        val = 'link.png'

    class basename(StandardComponent.basename):
        val = 'link-component'

    def _initialize(self):
        StandardComponent._initialize(self)
        self.connector_templates = {}
        self.ignore_initial_connectors = False

    def setup(self):
        simics.SIM_set_object_configured(self.obj)
        StandardComponent.setup(self)
        self.register_connector_templates()
        if not self.instantiated.val:
            self.ignore_initial_connectors = (
                component_utils.get_connectors(self.obj) != [])
            self.add_all_objects()
            self.ignore_initial_connectors = False

    class goal_latency(ConfigAttribute):
        """Goal latency in seconds for this link.
        See also the <cmd>set-min-latency</cmd> command."""
        attrtype = 'f'
        def _initialize(self):
            self.val = 1e-5
        def getter(self):
            return self.val
        def setter(self, val):
            self.val = val
            if self._up.instantiated.val:
                link = self._up.obj.iface.component.get_slot_value('link')
                link.goal_latency = val

    class global_id(ConfigAttribute):
        """Global identifier for use in distributed simulation or NIL if the
        link is not distributed."""
        attrtype = 's|n'
        def _initialize(self):
            self.val = None
        def getter(self):
            return self.val
        def setter(self, val):
            if self._up.instantiated.val:
                return simics.Sim_Set_Illegal_Value
            global_ids = [x.global_id
                          for x in simics.SIM_object_iterator_for_interface(["link"])
                          if hasattr(x, "global_id")]
            if not simics.SIM_is_restoring_state(self._up.obj) and val in global_ids:
                simics.SIM_attribute_error(f'Global ID "{val}" already used in local'
                                   ' sync domain.')
                return simics.Sim_Set_Illegal_Value
            self.val = val
            if self._up.obj.configured:
                link = self._up.obj.iface.component.get_slot_value('link')
                link.global_id = val

    class immediate_delivery(ConfigAttribute):
        """Immediate delivery instead of using the specified latency.
         Implies nondeterminism for multi cell messaging."""
        attrtype = 'b'
        def _initialize(self):
            self.val = False
        def getter(self):
            return self.val
        def setter(self, val):
            self.val = val
            if self._up.instantiated.val:
                link = self._up.obj.iface.component.get_slot_value('link')
                link.immediate_delivery = val

    class connector_template:
        pass

    @cli.doc('add a link connector template',
             return_value = 'The registered connector template',
             example = '<insert id="etc_comp"/>',
             **_docargs)
    def add_link_connector_template(self, name, type, growing,
                                    create_unconnected_endpoint,
                                    get_check_data    = None,
                                    get_connect_data  = None,
                                    check             = None,
                                    connect           = None,
                                    disconnect        = None,
                                    allow_new_cnt     = lambda: True,
                                    allow_destroy_cnt = lambda: True):
        '''This function registers a new connector template for the component.
        From this template, connectors will be created either statically, via
        the <fun>add_objects()</fun> function, or dynamically if requested.
        Component templates can be customized through the parameters of
        <fun>add_link_connector_template()</fun>:

        <dl>

          <dt>name</dt> <dd>is the name of the template, which will be saved in
          each connector, so that they can find out from which template they
          were created.</dd>

          <dt>type</dt> <dd>is the connector type.</dd>

          <dt>growing</dt> <dd>indicates whether the connector is static, or
          should grow dynamically as connections are made. Static connectors
          must be created in <fun>add_objects()</fun>, and will act as classic
          component connectors. A dynamic connector will make sure that there
          is always a free connector of that template available, by increasing
          or decreasing the number of connectors of this template in the link.
          Note that several templates can have the same connector type. Each
          template will make sure that its connectors grow or shrink
          separately.</dd>

          <dt>create_unconnected_endpoint</dt> <dd>is the function to call when
          a new endpoint pre-conf-object must be created. This endpoint is not
          yet connected to a device.</dd>

          <dt>get_check_data</dt> <dd>(optional) is called whenever the
          standard <fun>get_check_data()</fun> is called. It may return any
          <em>additional</em> data necessary for the check() call. The standard
          <fun>get_check_data()</fun> will already return the endpoint
          object.</dd>

          <dt>get_connect_data</dt> <dd>(optional) is similar to
          <fun>get_check_data</fun>, but for the <fun>connect()</fun>
          call.</dd>

          <dt>check</dt> <dd>(optional) is called whenever the standard
          <fun>check()</fun> is called. It may return <const>True</const>
          (connection accepted) or <const>False</const> (connection refused).
          The standard implementation returns always <const>True</const>.</dd>

          <dt>connect</dt> <dd>(optional) is called whenever the standard
          <fun>connect()</fun> is called. The standard <fun>connect()</fun>
          will set the device attribute in the endpoint. <fun>connect</fun> may
          take any additional action it deems necessary.</dd>

          <dt>disconnect</dt> <dd>(optional) is called whenever the standard
          <fun>disconnect()</fun> is called. The standard
          <fun>disconnect()</fun> does not do anything as the endpoint object
          will be destroyed soon after. <fun>disconnect()</fun> may take any
          additional action for the disconnection to succeed.</dd>

          <dt>allow_new_nct</dt> <dd>(optional) is used only for growing
          connectors. It is called every time a new connection is made to ask
          if creating a new empty connector is allowed. It may return
          <const>True</const> (new connector allowed) or <const>False</const>
          (no new connector). The default function always returns
          <const>True</const> (unlimited number of connectors allowed, with
          always one free).</dd>

          <dt>allow_destroy_cnt</dt> <dd>(optional) is used only for growing
          connectors. It is called every time a connection is severed to ask if
          the connector being disconnected should be destroyed. It may return
          <const>True</const> (destroy the connector) or <const>False</const>
          (let the connector). The endpoint object associated will be
          automatically destroyed with the connector, or replaced if the
          connector is left. The default function returns always
          <const>True</const> (unlimited number of connectors allowed, with
          always one free).</dd>

        </dl>'''
        if name in self.connector_templates:
            raise cli.CliError("Connector template '%s' already defined" % name)
        cnt_tmpl = self.connector_template()
        cnt_tmpl.name              = name
        cnt_tmpl.type              = type
        cnt_tmpl.connector_class   = ('dynamic_link_connector' if growing
                                      else 'static_link_connector')
        cnt_tmpl.create_endpoint   = create_unconnected_endpoint
        cnt_tmpl.allow_new_cnt     = allow_new_cnt
        cnt_tmpl.allow_destroy_cnt = allow_destroy_cnt
        cnt_tmpl.get_check_data    = get_check_data
        cnt_tmpl.get_connect_data  = get_connect_data
        cnt_tmpl.check             = check
        cnt_tmpl.connect           = connect
        cnt_tmpl.disconnect        = disconnect
        self.connector_templates[name] = cnt_tmpl
        return cnt_tmpl

    def check_new_connector_allowed(self, cnt):
        cnt_tmpl = self.connector_templates[
            cnt.object_data.connector_template.val]
        return cnt_tmpl.allow_new_cnt()

    def check_destroy_connector_allowed(self, cnt):
        cnt_tmpl = self.connector_templates[
            cnt.object_data.connector_template.val]
        return cnt_tmpl.allow_destroy_cnt()

    def get_unconnected_connector_object(self, slot_template):
        if not '%d' in slot_template:
            slot_template += '%d'
        pat = slot_template.replace("%d", "\\d+") + "$"
        for (k, s) in sorted(self._slots.all_slots().items()):
            if s is not None and re.match(pat, k) and not s.destination:
                return s
        return None

    def add_named_link_connector_object(self, slot, slot_template, cnt_tmpl):
        attrs = [['owner',              self.obj],
                 ['connector_type',     cnt_tmpl.type],
                 ['hotpluggable',       True],
                 ['required',           False],
                 ['multi',              False],
                 ['direction',          simics.Sim_Connector_Direction_Any],
                 ['connector_name',     slot],
                 ['component_slot',     slot],
                 ['component',          self.obj],
                 ['connector_template', cnt_tmpl.name]]
        if cnt_tmpl.connector_class == 'dynamic_link_connector':
            attrs += [['slot_template',      slot_template]]
        obj = simics.SIM_create_object(cnt_tmpl.connector_class, '', attrs)
        self.component.add_slot(slot)
        self.component.set_slot_value(slot, obj)
        return obj

    def add_link_connector_object(self, slot_template, cnt_tmpl):
        if not '%d' in slot_template:
            slot_template += '%d'
        for i in range(1000000):
            slot = slot_template % i
            if not self.has_slot(slot):
                break
        else:
            raise cli.CliError('Cannot find name for the connector')
        return self.add_named_link_connector_object(slot, slot_template, cnt_tmpl)

    def dereference_link_connector_object(self, cnt):
        self.component.set_slot_value(cnt.connector_name, None)
        self.component.del_slot(cnt.connector_name)
        # move the connector to be destroyed to a temporary slot so the
        # component system does not lose track of it
        if not self.component.has_slot('internal_connector_state'):
            self.component.add_slot('internal_connector_state')
        self.component.set_slot_value('internal_connector_state', cnt)

    # we can't use attributes directly because ep_obj might be a pre_obj
    def set_connector_endpoint(self, cnt, ep_obj):
        cnt.object_data.endpoint.val = ep_obj

    def get_connector_endpoint(self, cnt):
        return cnt.object_data.endpoint.val

    def add_connector_ep(self, cnt):
        ep_obj = self.create_and_instantiate_endpoint(cnt)
        self.component.add_slot("ep%x" % ep_obj.id)
        self.component.set_slot_value("ep%x" % ep_obj.id, ep_obj)
        self.set_connector_endpoint(cnt, ep_obj)

    def instantiate_pre_obj(self, pre_obj):
        obj = simics.VT_add_objects([pre_obj])[0]
        set_pre_obj_object(pre_obj, obj)
        return obj

    def create_and_instantiate_endpoint(self, cnt):
        cnt_tmpl = self.connector_templates[cnt.connector_template]
        ep_obj = cnt_tmpl.create_endpoint(cnt)

        # Prevent the automatic queue assignment to deduce our queue
        # from another endpoint in this component.
        ep_obj.queue = None

        if self.instantiated.val:
            ep_obj = self.instantiate_pre_obj(ep_obj)
        return ep_obj

    @cli.doc('add a new initial connector',
             return_value = 'None',
             example = '<insert id="ets_comp"/>',
             **_docargs)
    def add_link_connector(self, slot_template, cnt_tmpl):
        '''Add a new initial connector. The <param>slot_template</param>
        argument is the name of the connector in the component. The
        <param>cnt_tmpl</param> argument is the template used for the
        connector, previously registered with
        <fun>add_connector_template()</fun>.'''
        if not self.ignore_initial_connectors:
            self.add_link_connector_object(slot_template, cnt_tmpl)

    @cli.doc('return a unique link object name',
             return_value = 'A unique link name',
             example = '<insert id="ets_comp"/>',
             **_docargs)
    def get_link_object_name(self):
        '''Return a unique link object name based on the link component name.
        This is useful for ensuring that all link components with the same name
        in a distributed simulation will indeed represent the same link.'''
        # convert brackets and other punctuation that can occur in hierarchical
        # components to underscores.
        return re.sub(r"[\[\]\.]", "_", self.obj.name)

    def add_all_objects(self):
        self.add_objects()

    class component_connector(Interface):
        def get_check_data(self, cnt):
            return self._up._get_check_data(cnt)
        def get_connect_data(self, cnt):
            return self._up._get_connect_data(cnt)
        def check(self, cnt, attr):
            return self._up._check(cnt, attr)
        def connect(self, cnt, attr):
            self._up._connect(cnt, attr)
        def disconnect(self, cnt):
            self._up._disconnect(cnt)

    def apply_template_fun(self, cnt, fun, default, *args):
        cnt_tmpl = self.connector_templates[cnt.connector_template]
        f = getattr(cnt_tmpl, fun, None)
        return f(cnt, *args) if f else default

    # return the standard check data plus anything that the
    # template-specific function wants to return
    def _get_check_data(self, cnt):
        return ([self.get_connector_endpoint(cnt)]
                + self.apply_template_fun(cnt, 'get_check_data', []))

    # return the standard connection data plus anything that the
    # template-specific function wants to return
    def _get_connect_data(self, cnt):
        return ([self.get_connector_endpoint(cnt)]
                + self.apply_template_fun(cnt, 'get_connect_data', []))

    # return True, unless a template-specific function needs to be called
    def _check(self, cnt, attr):
        return self.apply_template_fun(cnt, 'check', True, attr)

    # if there is a specific connect, let it return to which device we should
    # connect.
    def _connect(self, cnt, attr):
        try:
            _ = attr[0]
        except (TypeError, IndexError):
            raise CompException(
                "Links expect to receive connection data of the form [device, "
                "...] or [[device, port], ...] but the data is %s" % repr(attr))
        ep_obj = self.get_connector_endpoint(cnt)
        ep_obj.device = self.apply_template_fun(cnt, 'connect', attr[0], attr)

        # Leaving the endpoint queue as Nil will give the automatic
        # queue assignment freedom to take it from another connector,
        # which would break cell boundaries.
        if hasattr(ep_obj.device, "queue"):
            ep_obj.queue = ep_obj.device.queue

    # nothing to be done since the endpoint will be destroyed. The
    # template-specific function is called to clean-up its own stuff.
    def _disconnect(self, cnt):
        self.apply_template_fun(cnt, 'disconnect', None)

    class component(StandardComponent.component):
        def post_instantiate(self):
            # at instantiation, we need to convert all endpoint objects stored
            # in our connectors from pre-conf-objects to real objects
            cnts = component_utils.get_connectors(self._up.obj)
            for cnt in cnts:
                ep = self._up.get_connector_endpoint(cnt)
                if not isinstance(ep, simics.conf_object_t):
                    self._up.set_connector_endpoint(
                        cnt, get_pre_obj_object(ep))

class simple_link_component(link_component):
    """Base class for simple link components, with only one link object and one
    growing connector"""
    _do_not_init = object()

    config_endpoint_class = ""
    config_link_class = ""
    config_connector_type = ""
    config_basename = ""

    def create_unconnected_endpoint(self, cnt):
        return create_generic_endpoint(
            self.config_endpoint_class,
            self.obj.iface.component.get_slot_value('link'), None)

    def register_connector_templates(self):
        self.cnt_tmpl = self.add_link_connector_template(
            name = '%s-connector' % self.config_connector_type,
            type = self.config_connector_type,
            growing = True,
            create_unconnected_endpoint = self.create_unconnected_endpoint)

    def add_objects(self):
        self.add_pre_obj_with_name('link', self.config_link_class,
                                   self.get_link_object_name(),
                                   goal_latency = self.goal_latency.val,
                                   global_id = self.global_id.val,
                                   immediate_delivery = self.immediate_delivery.val)
        self.add_link_connector('device', self.cnt_tmpl)

@cli.doc('create a simple link component class',
         return_value = 'A new component class from which to inherit',
         example = '<insert id="dl_comp"/>')
def create_simple(link_class, endpoint_class, connector_type,
                  class_desc, basename = None, help_categories = []):
    '''Create a simple link component class based on the following parameters:

    <dl>

      <dt>link_class</dt> <dd>Name of the link implementation class</dd>

      <dt>endpoint_class</dt> <dd>Name of the link endpoint class</dd>

      <dt>connector_type</dt> <dd>Name of the connector type for component
                                 connections</dd>

      <dt>class_desc</dt> <dd>Component description</dd>

      <dt>basename</dt> <dd>Prefix used to create new component names when none
                           is provided</dd>

    </dl>'''
    class SLC(simple_link_component):
        _do_not_init = object()
        config_endpoint_class = endpoint_class
        config_link_class = link_class
        config_connector_type = connector_type
        _class_desc = class_desc
        class basename(simple_link_component.basename):
            val = basename

    return SLC
