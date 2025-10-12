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


import simics, cli, pyobj, component_utils, cmputil, re
import os  # os is not needed by the comp module but some users' packages
           # expect to see it imported after doing "from comp import *"
from pyobj import (
    Port,
    AttrGroup,
    Attribute,
    ClassAttribute,
    SimpleAttribute,
    Interface,
    Event,
)
from pyclass_common import (
    _SimpleMessageException,
)
from functools import cmp_to_key
import itertools
from simicsutils.internal import py3_cmp

# used by cli.doc()
__simicsapi_doc_id__ = 'comp module'

class CompException(Exception):
    pass

class pre_obj(simics.pre_conf_object):
    'Generate pre_conf_object with unique name'
    __slots__ = ('__conf_object__', )

    def __init__(self, object_name, class_name, **attrs):
        simics.pre_conf_object.__init__(self, object_name, class_name, **attrs)
        self._rename(object_name)
        self.__conf_object__ = None

    def _pre_obj_rename(self, name):
        name = name.replace("-", "_")
        seq = str(component_utils.next_sequence(name))
        name = name.replace('$', seq)
        if '(' in name or ')' in name:
            raise component_utils.ComponentError(
                'parenthesis not allowed in object names: %s' % name)
        self.name = name
        return name

    def _rename(self, name):
        if name:
            self._pre_obj_rename(name)

def set_pre_obj_object(pre, obj):
    pre.__conf_object__ = obj

# TODO: move to pre_obj(), but currently the component code does SIM_get_object
# on both pre_obj and conf_object_t objects when translating from pre_obj to
# conf_object_t
def get_pre_obj_object(pre):
    """return conf_object_t reference from pre_obj or a conf_object_t"""
    if isinstance(pre, simics.pre_conf_object):
        return pre.__conf_object__
    else:
        return pre

class pre_obj_noprefix(pre_obj):
    'Generate pre_conf_object with unique name, no prefix added'
    __slots__ = ()

    def __init__(self, object_name, class_name, **attrs):
        pre_obj.__init__(self, object_name, class_name, **attrs)
        self._rename(object_name)

# control if slot is a valid slot name
def _supported_slot_name(slot, array = False):
    parts = slot.split(".")
    def fail():
        raise CompException('illegal slot name %r' % slot)
    if not slot:
        fail()
    for s in parts[:-1]:
        if not cmputil.is_valid_slot_name_with_indices(s):
            fail()
    last = parts[-1]
    if ((not array and not cmputil.is_valid_slot_name(last))
        or (array and not cmputil.is_valid_slot_name_with_indices(last))):
        fail()

# control if val is a supported slot value
def _supported_slot_value(val):
    if not cmputil.is_valid_slot_value(val):
        raise CompException('unsupported slot value %r' % val)

# return slot name without trailing array indices
def _extract_slot(slot):
    while slot.endswith("]"):
        slot = slot[:-1].split("[")[0]
    return slot

# This class is used in array slots to maintain the legacy behaviour
# that after add_slot('name[5]'), get_slot('name') returns [None] * 5.
class index_map_pre_obj(simics.pre_conf_object):
    '''implicitly created index-map pre-conf object'''
    __slots__ = ('_min_length',)
    def __init__(self, min_length):
        super(index_map_pre_obj, self).__init__('index-map')
        self._min_length = min_length

# The _Slots class is used to keep track of pre conf objects belonging to
# a components, before they are instantiated.
class _Slots:
    def __init__(self, comp):
        self.comp = comp
        # _dict maps strings (slot names) to pre conf objects.  For
        # slot arrays, it is an index-map object.  If an array item is
        # included in the dict, e.g. "alpha[0]", then its parent pre
        # object arrays must also be included in the dict.  Slots are
        # always looked up in the real configuration space before
        # looking in _dict. After instantiation, pre-conf objects
        # remain in _dict, and *generally* have no effect since they are
        # shadowed by the instantiated conf-object. There is one known
        # exception: if an index_map_pre_obj object with no children remains
        # in the dict, then it causes get_slot to return a list of None
        # elements.
        self._dict = {}

    def __contains__(self, slot):
        return (slot in self._dict
                or simics.SIM_object_descendant(self.comp, slot))

    # lookup with list handling
    def _lookup(self, slot, expand_arrays=True):
        obj = simics.SIM_object_descendant(self.comp, slot)
        if obj:
            self._dict[slot] = obj
            return obj
        if slot not in self._dict:
            if slot.endswith(']'):
                # See if slot can be reached as ancestor slot
                (parent, index) = slot.rsplit('[', 1)
                try:
                    index = int(index[:-1])
                    parent = self._lookup(parent, False)
                    self._dict[slot] = parent[index]
                except (ValueError, KeyError, TypeError, IndexError):
                    # let _dict lookup fail with full slot name
                    pass
            elif '.' in slot:
                (parent, member) = slot.rsplit('.', 1)
                parent = self._lookup(parent)
                if isinstance(parent, simics.pre_conf_object):
                    parent._lookup(member)  # trigger linking
                    if member in parent._d:
                        self._dict[slot] = parent._d[member]

        return self._dict[slot]

    # make sure a pre-object is present in the dictionary
    def _ensure_pre_object(self, slot, default):
        try:
            return self._lookup(slot)
        except KeyError:
            pass
        if slot.endswith(']'):
            (base, index) = slot.rsplit('[', 1)
            index = int(index[:-1])
            parent = self._ensure_pre_object(
                base, simics.pre_conf_object('index-map'))
            parent[index] = default
        elif '.' in slot:
            (base, member) = slot.rsplit('.', 1)
            parent = self._ensure_pre_object(
                base, simics.pre_conf_object('namespace'))
            parent._link(member, default)
        else:
            default.name = f'{self.comp.name}.{slot}'
        self._dict[slot] = default
        return default

    # make sure ancestors are present in the dictionary,
    def _prepare_slot(self, slot, is_array = False):
        if self.comp.instantiated:
            return
        if slot.endswith(']'):
            if is_array:
                # add_pre_obj('x[3].y[4][5]') adds a two-dimensional
                # array of 20 objects under x[3].y
                all_dims = []
                base = slot
                while base.endswith(']'):
                    (base, dim) = base.rsplit('[', 1)
                    all_dims[0:0] = [int(dim[:-1])]

                # when preparing x[2][3][4], we need to create one index-map x
                # of length 2, two index-maps x[0] and x[1] of length 3,
                # and six index-maps x[0][0]..x[1][2] of length 4.
                for level in range(len(all_dims)):
                    inner_dim = all_dims[level]
                    for coord in itertools.product(
                            *[range(dim) for dim in all_dims[:level]]):
                        parent_name = base + ''.join(
                            f'[{i}]' for i in coord)
                        self._ensure_pre_object(
                            parent_name, index_map_pre_obj(inner_dim))
            else:
                (base, index) = slot.rsplit('[', 1)
                self._ensure_pre_object(
                    base, simics.pre_conf_object('index-map'))
        elif '.' in slot:
            (base, member) = slot.rsplit('.', 1)
            self._ensure_pre_object(base, simics.pre_conf_object('namespace'))

    # get slot value, returns None if slot is missing
    def _null_local_get(self, slot):
        try:
            return self.local_get(slot)
        except KeyError:
            return None

    # get slot value
    def local_get(self, slot):
        obj = simics.SIM_object_descendant(self.comp, slot)
        if obj and obj.classname == 'index-map':
            nums = [int(o.name.rpartition("[")[2].rstrip("]"))
                    for o in simics.SIM_shallow_object_iterator(obj)]
            n = max(nums) + 1 if nums else 0
            return [self._null_local_get("{}[{}]".format(slot, i))
                    for i in range(n)]
        elif obj:
            return obj
        else:
            obj = self._lookup(slot)
            if isinstance(obj, index_map_pre_obj):
                # legacy: lookup of array slot gives list with some
                # None elements. Only for implicitly created index map objects.
                return [self._null_local_get("{}[{}]".format(slot, i))
                        for i in range(max(len(obj), obj._min_length))]
            else:
                return obj

    # find component "owning" slot. Returns (cmp, slot).
    def _find_comp(self, slot):
        ind = -1
        while True:
            ind = slot.rfind(".", 0, ind)
            if ind < 0:
                return (self.comp, slot)
            obj = simics.SIM_object_descendant(self.comp, slot[:ind])
            if obj and cli.is_component(obj):
                return (obj, slot[ind + 1:])

    # set slot value (without component redirect)
    def set(self, slot, v):
        self._prepare_slot(slot)
        if isinstance(v, list):
            self._ensure_pre_object(slot, index_map_pre_obj(len(v)))
            for (i, val) in enumerate(v):
                self.set("{}[{}]".format(slot, i), val)
        elif not isinstance(v, simics.conf_object_t):
            # we only store pre_conf_obj_t or NULL in our dictionary;
            # complain if there is a name conflict with an instantiated object
            if simics.SIM_object_descendant(self.comp, slot):
                raise CompException("an object with name {}.{} already "
                                    "exists".format(self.comp.name, slot))
            self._dict[slot] = v

            if slot.endswith(']'):
                (parent, index) = slot.rsplit('[', 1)
                index = int(index[:-1])
                try:
                    parent = self._lookup(parent)
                except KeyError:
                    # conf-object parent?
                    pass
                else:
                    if v and not isinstance(parent, simics.conf_object_t):
                        parent[index] = v
            elif '.' in slot:
                (parent, member) = slot.rsplit('.', 1)
                try:
                    parent = self._lookup(parent)
                except KeyError:
                    # conf-object parent?
                    pass
                else:
                    if not isinstance(parent, simics.conf_object_t):
                        parent |= v

    # get slot value; redirect request to subcomponent when appropriate
    def get(self, slot):
        (comp, slot) = self._find_comp(slot)
        if comp == self.comp:
            return self.local_get(slot)
        else:
            if not comp.iface.component.has_slot(slot):
                raise KeyError("component {} does not have slot {}".format(
                    comp, slot))
            return comp.iface.component.get_slot_value(slot)

    def delete(self, slot):
        try:
            del self._dict[slot]
        except KeyError:
            pass

    # return individual array items given an array "declaration";
    # e.g. "abc[2][2]" -> ("abc[0][0]", "abc[0][1]", "abc[1][0]", "abc[1][1]")
    def _array_elements(self, slot):
        if slot.endswith("]"):
            (base, _, ind) = slot.rpartition("[")
            for i in range(int(ind.strip("]"))):
                for r in self._array_elements(base):
                    yield "{}[{}]".format(r, i)
        else:
            yield slot

    # set slot (or all slots in an array) using the factory function f
    def fill_set(self, slot, factory):
        self._prepare_slot(slot, is_array = True)
        for s in self._array_elements(slot):
            self.set(s, factory(s))
        return self.local_get(_extract_slot(slot))

    # make sure objects in the specified slot are finalized
    def require_objects_in_slot(self, slot):
        obj = simics.SIM_object_descendant(self.comp, slot)
        if obj:
            if obj.classname != "index-map":
                simics.SIM_require_object(obj)
            else:
                for o in simics.CORE_shallow_object_iterator(obj, True):
                    simics.SIM_require_object(o)

    # all slots (trailing array indices excluded)
    def _keys(self):
        keys = {k for k in self._dict if not k.endswith(']')}
        work = [self.comp]
        while work:
            base = work.pop()
            for o in simics.CORE_shallow_object_iterator(base, True):
                relname = o.name.replace(self.comp.name, "", 1)
                if relname.startswith('.'):
                    relname = relname[1:]
                keys.add(_extract_slot(relname))
                if not cli.is_component(o):
                    work.append(o)
        return keys

    # return a dictionary 'slot: object', with array slots excluded
    def all_slots(self):
        return dict((k, self.local_get(k)) for k in self._keys())

    # return a dictionary with all objects, with expanded arrays
    def all_objects_dict(self):
        ret = dict()
        def append(slot):
            v = self._null_local_get(slot)
            if isinstance(v, list):
                for i in range(len(v)):
                    append("{}[{}]".format(slot, i))
            elif v is not None:
                ret[slot] = v
        for k in self._keys():
            append(k)
        return ret

    # return a sorted list with all objects (pre_object or conf_object)
    def all_objects(self):
        ret = []
        def append(slot):
            v = self._null_local_get(slot)
            if isinstance(v, list):
                for i in range(len(v)):
                    append("{}[{}]".format(slot, i))
            elif v is not None:
                ret.append(v)
        for k in sorted(self._keys()):
            append(k)
        return ret


def _get_slots_attribute(d):
    # remove pre objects or not checkpointable objects from list v
    # return new list and flag indicating if any valid object was found
    def remove_non_check(val, template):
        if isinstance(val, list):
            ret_l = []
            ret_c = False
            for e in val:
                (nl, c) = remove_non_check(e, template)
                ret_l.append(nl)
                ret_c = ret_c or c
            return (ret_l, ret_c)
        if template:
            # template, return connector and component objects
            if (isinstance(val, simics.conf_object_t)
                and (hasattr(val.iface, 'connector')
                     or (hasattr(val.iface, 'component')
                         and component_utils.is_component_hardware(val)))):
                return (val, True)
        else:
            # non template, return all checkpointable objects
            if (isinstance(val, simics.conf_object_t)
                and simics.VT_object_checkpointable(val)):
                return (val, True)
        return (None, False)

    template = component_utils.get_writing_template()
    ret = {}
    for (k, v) in d.items():
        (val, conv) = remove_non_check(v, template)
        if conv:
            ret[k] = val
    return ret

default_rtc_start_time = "2008-06-05 23:52:01 UTC"

def mac_as_list(str):
    try:
        val = [int(x, 16) for x in str.split(':')]
        if len(val) == 6:
            return val
        else:
            return []
    except ValueError:
        return []

class ConfigAttribute(
        Attribute,
        metaclass=cli.doc(
            'component configuration attribute',
            synopsis = False,
            see_also = 'pyobj.Attribute',
            metaclass = pyobj._ObjMeta,
            example = '''
            <pre size="small">class foo(ConfigAttribute):
                """The foo attribute."""
                valid = [667, 4711]
                def _initialize(self): self.val = 4711
                def getter(self): return self.val
                def setter(self, val): self.val = val</pre>''')):
    '''The <class>ConfigAttribute</class> class inherits the
    <class>pyobj.Attribute</class> class. The
    <class>ConfigAttribute</class> class just adds the special property
    to the <class>pyobj.Attribute</class> class that it is a config
    attribute.

    A config attribute defines how the component should be
    configured. Therefore, all config attributes are also arguments to the
    <cmd>new-</cmd> and <cmd>create-</cmd> commands that are used to
    instantiate the component.

    Because of this, the config attribute must always be documented
    and the default value of the <var>attrattr</var> member is
    <tt>Sim_Attr_Optional</tt>.

    The <class>ConfigAttribute</class> class contains the
    <var>valid</var> member, which is a list of valid values for the
    config attribute. The list gives the user a hint about valid
    values when creating a component. There is no check that the value
    written to the attribute is a value in the list of valid values.
    The list of valid value(s) does not need to contain the default
    initial value for the config attribute, but it usually does. The
    valid list should at least contain one valid value even if several
    values are valid.
    '''

    _config_attr = True
    valid = []
    attrattr = simics.Sim_Attr_Optional

@cli.doc('simple component configuration attribute',
         return_value = 'comp.ConfigAttribute class',
         see_also = 'pyobj.Attribute, pyobj.ConfObject',
         example = '''
            <pre size="small">class cpu_frequency(SimpleConfigAttribute(
                    None, 'i', simics.Sim_Attr_Required)):
                """Processor frequency in MHz."""</pre>''')
def SimpleConfigAttribute(init, type, attr = simics.Sim_Attr_Optional, val = []):
    '''The <fun>pyobj.SimpleConfigAttribute</fun> method creates an
    attribute using the <class>comp.ConfigAttribute</class> class. The
    purpose of the method is to make it easier and faster to create a
    simple config attribute.

    A config attribute defines how the component should be
    configured. Therefore, all config attributes are also arguments to the
    <cmd>new-</cmd> and <cmd>create-</cmd> commands that are used to
    instantiate the component.

    The <arg>init</arg> argument is the initial value for the
    attribute. The type of the attribute is defined by the
    <arg>type</arg> string (currently objects 'o' and dictionaries 'D'
    are not supported). The <arg>attr</arg> argument sets the
    attribute kind. The default value for <arg>attr</arg> is
    <tt>Sim_Attr_Optional</tt>.
    The valid value(s) for the
    <class>comp.ConfigAttribute</class> class is set by the
    <arg>val</arg> argument. See the documentation for
    <fun>SIM_register_attribute</fun> for more information about
    the arguments.'''
    class SCA(ConfigAttribute):
        attrattr = attr
        attrtype = type
        valid = val
        def _initialize(self):
            try:
                self.val = init()
            except TypeError:
                self.val = init
        def getter(self): return self.val
        def setter(self, val):
            if (simics.SIM_object_is_configured(self._up.obj)
                and not simics.SIM_is_restoring_state(self._up.obj)
                and val != self.val):
                raise _SimpleMessageException(
                    "Cannot assign component attribute after instantiation."
                    " Access attributes of contained objects directly instead.")
            else:
                self.val = val
    return SCA

class StandardComponent(
        pyobj.ConfObject,
        metaclass=cli.doc(
            'base class for components',
            see_also = 'pyobj.ConfObject',
            synopsis = False,
            metaclass = pyobj._ConfObjectMeta,
            docu_suffix = '''
            <doclist id="comp.StandardComponent methods"
                     name="comp.StandardComponent Methods" sort="az"
                     numbering="false"/>''',
            example = '''
            <pre size="small">class my_comp(StandardComponent):
                """The my_comp component."""
                _class_desc = "my_comp"

                class bar(SimpleConfigAttribute(
                        None, 'i', simics.Sim_Attr_Required)):
                    """My favorite bar."""

            class my_comp(StandardComponent):
                """The my_comp component."""
                _class_desc = "my_comp"
                _no_create_command = object()</pre>''')):
    '''The <class>StandardComponent</class> class is the base class for
    components written in Python. It is a subclass of
    <class>pyobj.ConfObject</class>.

    The class will automatically register the
    required component attributes. Any attribute may be overridden;
    however, overriding the internal attributes is not recommended.

    The automatically registered attributes are:
    <dl>
     <dt>basename</dt><dd>String to prepend to component name when creating
     components when not specifying name.</dd>
     <dt>component_icon</dt><dd>String with the name of the component
     icon.</dd>
     <dt>component_queue</dt><dd>The default queue object for this
     component.</dd>
     <dt>top_level</dt><dd>Default set to <tt>False</tt>.</dd>
     <dt>system_icon</dt><dd>The system icon.</dd>
     <dt>machine_icon</dt><dd>The machine icon.</dd>
     <dt>cpu_list</dt><dd>List of processors in the component tree.</dd>
     <dt>static_slots</dt><dd>Internal.</dd>
     <dt>dynamic_slots</dt><dd>Internal.</dd>
     <dt>object_list</dt><dd>Internal.</dd>
     <dt>object_prefix</dt><dd>Internal.</dd>
     <dt>top_component</dt><dd>Internal.</dd>
     <dt>instantiated</dt><dd>Internal.</dd>
     <dt>pending_cell_object_factories</dt><dd>Internal.</dd>
     <dt>config_attributes</dt><dd>Internal.</dd>
     <dt>system_info</dt><dd>Internal.</dd>
     <dt>components</dt><dd>Internal.</dd>
     <dt>domain</dt><dd>Internal.</dd>
    </dl>

    The class will automatically implement the <iface>component</iface>
    interface. The individual methods of this interface are user-overridable.

    Components will automatically get <cmd>new-</cmd> and <cmd>create-</cmd>
    commands that can be used to create and instantiate the component. It is
    possible to override this by setting <em>_no_create_command</em> or
    <em>_no_new_command</em> to <em>object()</em> to avoid to automatically get
    <cmd>create-</cmd> or <cmd>new-</cmd> commands.'''

    _docargs = {
        'doc_id'    : 'comp.StandardComponent methods',
        'namespace' : 'StandardComponent' }

    _do_not_init = object()

    @classmethod
    def _register(cls, class_name):
        super(StandardComponent, cls)._register(class_name)
        _register_component_commands(cls, class_name)

    def _initialize(self):
        pyobj.ConfObject._initialize(self)
        # slots dictionaries contain pre-conf objects only
        self._slots = _Slots(self.obj)
        simics.SIM_add_global_notifier(simics.Sim_Global_Notify_Object_Delete,
                                       self.obj, self.deletion_cleanup, None)

    def _finalize(self):
        pyobj.ConfObject._finalize(self)
        try:
            self.setup()
        except CompException as ex:
            simics.SIM_attribute_error("%s" % ex)

    def setup(self):
        pass # do nothing

    def _check_slot_name_clash(self, slot):
        slot = _extract_slot(slot)
        methods = set(c.method for c in
                      cli.get_class_commands(self.obj.classname))
        attrs = set(a[0] for a in self.obj.attributes)
        if slot in methods:
            simics.SIM_log_info(1, self.obj, 0,
                                "warning: creating slot '%s'" % slot +
                                " which is also a component command")
        if slot in attrs:
            simics.SIM_log_info(1, self.obj, 0,
                                "warning: creating slot '%s'" % slot +
                                " which is also a component attribute")

    def _is_loading_checkpoint(self):
        return (not simics.SIM_object_is_configured(self.obj)
                and simics.SIM_is_restoring_state(self.obj))

    # Take a slot value and go through all elements in value and make
    # sure that they are made ready for being removed from the slot.
    # This includes converting connectors to pre objects.
    def _delete_slot_hook(self, slot, val):
        if isinstance(val, list):
            return [self._delete_slot_hook(v, "{}[{}]".format(slot, i))
                    for (v, i) in enumerate(val)]
        if isinstance(val, simics.conf_object_t) and cli.is_connector(val):
            if self._is_loading_checkpoint():
                return
            if val.child:
                raise CompException(
                    'cannot delete slot "%s" as it contains copied connectors'
                    % (slot,))
            if val.parent:
                val.parent.child = None
            ret = self._create_connector(
                None, val.type, val.hotpluggable, val.required,
                val.multi, val.direction, True)
            val.component = None
            val.component_slot = None
            simics.SIM_delete_object(val)
            return ret
        if isinstance(val, simics.conf_object_t):
            raise CompException(
                'cannot delete slot "%s" as it contains non connector conf objects'
                % (slot,))
        if isinstance(val, simics.pre_conf_object):
            val.component = None
            val.component_slot = None
        return val

    # Take a slot value and go through all elements in the value and make
    # sure that all pre objects and conf objects are set correctly. This
    # includes setting component_slot and component attributes, creating
    # connector objects from pre objects, etc.
    #
    # val: slot value, i.e. nested lists of objects and None values
    # cmp: component object
    # slot: base slot name
    def _slot_assign_hook(self, slot, val):
        if isinstance(val, list):
            return [self._slot_assign_hook("{}[{}]".format(slot, i), v)
                    for (i, v) in enumerate(val)]

        is_connector = cli.is_connector(val)
        is_pre_obj = isinstance(val, simics.pre_conf_object)
        is_component = (cli.is_component(val)
                        and not hasattr(val, "__non_component__"))

        # handle the case when a pre-conf object is assigned to multiple slots
        if is_pre_obj:
            if (hasattr(val, "component")
                and hasattr(val, "component_slot")
                and val.component == self.obj
                and val.component_slot
                and val.component_slot in self._slots
                and val.component_slot != slot):
                simics.SIM_log_info(
                    1, self.obj, 0,
                    "Object {} is assigned to the {} slot in the {} component"
                    " while it was already assigned to the {} slot".format(
                        val.name, slot, self.obj.name, val.component_slot))
            # assign new name to pre-object
            val.component = self.obj
            val.component_slot = slot
            val.name = self.obj.name + "." + slot

        # set connector_name
        if is_connector:
            val.connector_name = slot

        if isinstance(val, simics.conf_object_t):
            # rename objects when necessary
            fullname = self.obj.name + "." + slot
            if val.name != fullname:
                simics.VT_rename_object(val, fullname)
        elif is_connector:
            # instantiate connectors
            obj = simics.SIM_object_descendant(self.obj, slot)
            if not obj and not self._is_loading_checkpoint():
                try:
                    obj = simics.VT_add_objects([val])[0]
                except Exception as ex:
                    raise CompException("failed creating object: %s" % ex)
            if obj:
                if obj.parent:
                    obj.parent.child = obj
                elif isinstance(self, StandardConnectorComponent):
                    cnt_cls = self._connectors[val]
                    self._connectors[obj] = cnt_cls
            val = obj
        elif is_component:
            # instantiate components
            try:
                obj = simics.VT_add_objects([val])[0]
            except Exception as ex:
                raise CompException("failed creating sub component: %s" % ex)
            val = obj

        # rename "overwritten" objects
        cur_obj = simics.SIM_object_descendant(self.obj, slot)
        if cur_obj and cur_obj != val:
            simics.VT_rename_object(cur_obj, cur_obj.object_id)
        return val

    def _create_connector(self, slot, type, hotpluggable,
                          required, multi, direction, anonymous):
        p = pre_obj('', 'connector')
        p.owner = self.obj
        p.type = type
        p.hotpluggable = hotpluggable
        p.required = required
        p.multi = multi
        p.direction = direction
        if not anonymous:
            p.connector_name = slot
            p.component_slot = slot
            p.component = self.obj
        if slot:
            try:
                return simics.VT_add_objects([p])[0]
            except Exception as ex:
                raise CompException("failed creating connector: %s" % ex)
        return p

    class component(Interface):
        _docargs = {
            'doc_id' : 'comp.StandardComponent.component methods',
            'namespace' : 'StandardComponent.component' }

        @cli.doc('instantiate component status',
                 return_value = '<const>True</const>',
                 **_docargs)
        def pre_instantiate(self):
            '''Should return <tt>True</tt> if component is allowed to be
            instantiated, <tt>False</tt> otherwise. The default behavior is to
            return <tt>TRUE</tt>.'''
            return True

        @cli.doc('post instantiation functionality',
                 **_docargs)
        def post_instantiate(self):
            '''The function will be called when the component has been
            instantiated.

            The default behavior is to do nothing.'''
            pass

        @cli.doc('create cell for component',
                 return_value = '''Returns <tt>True</tt> if automatic cell
                 partitioning is enabled and the component is a top-level
                 component, otherwise it returns <tt>False</tt>.''',
                 **_docargs)
        def create_cell(self):
            '''Returns cell creation status for component. The default behavior
            depends on the <attr>automatic_cell_partition</attr> attribute in
            the <obj>sim</obj> object and if the component is a top-level
            component.'''
            sim = simics.SIM_get_object('sim')
            if sim.automatic_cell_partition:
                return self._up.top_level.val
            else:
                return False

        @cli.doc('get slot objects',
                 return_value = 'list of objects',
                 **_docargs)
        def get_slot_objects(self):
            '''Standard implementation, see the <iface>component</iface>
            interface. The function will return all objects in the static and
            dynamic slots.'''
            return self._up._slots.all_objects()

        @cli.doc('get slot dictionary',
                 return_value = 'dictionary with all slots',
                 **_docargs)
        def get_slots(self):
            '''Standard implementation, see the <iface>component</iface>
            interface. The function will return all static and dynamic slots as
            a dictionary.'''
            return self._up._slots.all_slots()

        @cli.doc('get slot',
                 return_value = 'value in slot',
                 **_docargs)
        def get_slot_value(self, slot):
            '''Standard implementation, see the <iface>component</iface>
            interface. The function will return the slot value for the slot
            named <arg>slot</arg>.'''
            try:
                _supported_slot_name(slot, True)
            except CompException:
                simics.SIM_log_error(
                    self._up.obj, 0, 'get_slot_value, unsupported slot name "%s"' % slot)
                return None
            try:
                return self._up._slots.local_get(slot)
            except KeyError:
                simics.SIM_log_error(
                    self._up.obj, 0, 'get_slot_value, unknown slot "%s"' % slot)
            return None

        @cli.doc('set slot',
                 **_docargs)
        def set_slot_value(self, slot, val):
            '''Standard implementation, see the <iface>component</iface>
            interface. The function sets the slot named <arg>slot</arg> to
            <arg>val</arg>.'''
            try:
                _supported_slot_value(val)
            except CompException:
                simics.SIM_log_error(
                    self._up.obj, 0, 'set_slot_value, unsupported slot value %r' % val)
                return
            def any_pre_conf_obj(val):
                if isinstance(val, list):
                    return any(any_pre_conf_obj(e) for e in val)
                return isinstance(val, simics.pre_conf_object)
            if (not slot in self._up._slots
                and any_pre_conf_obj(val)):
                simics.SIM_log_error(
                    self._up.obj, 0, 'set_slot_value, unknown slot "%s"' % slot)
                return
            val = self._up._slot_assign_hook(slot, val)
            self._up._slots.set(slot, val)

        @cli.doc('check if valid slot',
                 return_value = '<const>True</const> or <const>False</const>',
                 **_docargs)
        def has_slot(self, slot):
            '''Standard implementation, see the <iface>component</iface>
            interface. The function returns <tt>True</tt> if there exists a
            static or dynamic slot named <arg>slot</arg> in the component,
            otherwise it returns <tt>False</tt>.'''
            try:
                self._up._slots.local_get(slot)
                return True
            except KeyError:
                return False

        @cli.doc('add slot',
                 return_value = '<const>True</const> or <const>False</const>',
                 **_docargs)
        def add_slot(self, slot):
            '''Standard implementation, see the <iface>component</iface>
            interface. The function adds a dynamic slot named <arg>slot</arg>
            if it does not already exist. It returns <tt>True</tt> if it could
            add the slot.'''
            try:
                _supported_slot_name(slot)
            except CompException:
                simics.SIM_log_error(
                    self._up.obj, 0, 'add_slot, unsupported slot name "%s"' % slot)
                return False
            if slot in self._up._slots:
                return False
            self._up._slots.set(slot, None)
            return True

        @cli.doc('delete slot',
                 return_value = '<const>True</const> or <const>False</const>',
                 **_docargs)
        def del_slot(self, slot):
            '''Standard implementation, see the <iface>component</iface>
            interface. The function deletes the dynamic slot named
            <arg>slot</arg>. The function returns <tt>True</tt> if it could
            remove the slot, otherwise it returns <tt>False</tt>.'''
            try:
                _supported_slot_name(slot)
            except CompException:
                simics.SIM_log_error(
                    self._up.obj, 0, 'del_slot, unsupported slot name "%s"' % slot)
                return False
            if not slot in self._up._slots:
                return False
            self._up._slots.delete(slot)
            return True

    @cli.doc('copy connector to component',
             return_value = 'arrays of conf_object connector objects',
             see_also = 'comp.StandardComponent.get_slot',
             **_docargs)
    def copy_connector(self, slot, src):
        '''Copy connectors from another component. The <arg>slot</arg> argument
        is the new slot name for the connector in this component. The
        <arg>src</arg> argument is the name of the slot with connectors to
        copy. The <arg>src</arg> can be a relative slot name, see the
        <fun>get_slot</fun> method.'''
        cpy = self.get_slot(src)
        def create_connector_copies(val):
            if isinstance(val, list):
                ret = []
                for e in val:
                    ret.append(create_connector_copies(e))
                return ret
            if cli.is_connector(val):
                p = pre_obj('', 'connector')
                p.type = val.type
                p.hotpluggable = val.hotpluggable
                p.required = val.required
                p.multi = val.multi
                p.direction = val.direction
                p.owner = val.owner
                p.master = val.master
                p.parent = val
                return p
            else:
                return None
        val = create_connector_copies(cpy)
        if slot:
            _supported_slot_name(slot)
            _supported_slot_value(val)
            val = self._slot_assign_hook(slot, val)
            self._slots.set(slot, val)
        return val

    @cli.doc('add connector to component',
             return_value = 'arrays of conf_object connector objects',
             see_also = 'comp.StandardComponent.get_slot',
             **_docargs)
    def add_connector(self, slot, type, hotpluggable, required,
                      multi, direction):
        '''Add a connector or nested array of connectors to the component. The
        connector(s) will be created immediately when the method is called.

        The <arg>slot</arg> argument is the slot name concatenated with a
        nested array string, defining the number of connectors to create.
        Setting <arg>slot</arg> to <em>foo</em> will create one connector in
        the slot <em>foo</em>, setting <arg>slot</arg> to <em>foo[3]</em> will
        create an array of three connectors in the slot <em>foo</em>, setting
        <arg>slot</arg> to <em>foo[3][2]</em> will create an array of three
        arrays of two arrays with connectors in the slot <em>foo</em>.

        The <arg>type</arg> is the type of connection as a string,
        <arg>hotpluggable</arg> is <tt>True</tt> or <tt>False</tt> depending on
        whether the connector is hot-pluggable, <arg>required</arg> is
        <tt>True</tt> if the connector must be connected before the component
        is instantiated, <arg>multi</arg> is <tt>True</tt> if the connector
        supports multiple connections, <arg>direction</arg> is a
        <type>connector_direction_t</type> which is <tt>up</tt>, <tt>down</tt>,
        or <tt>any</tt>.'''
        if slot:
            s = _extract_slot(slot)
            self._check_slot_name_clash(s)
            if self._is_loading_checkpoint():
                return self._slots.local_get(s) if s in self._slots else None
            _supported_slot_name(slot, array = True)
            if s in self._slots:
                simics.SIM_log_info(
                    2, self.obj, 0,
                    "warning: slot '%s' already used, ignoring new connector" % slot)
                return self._slots.local_get(_extract_slot(slot))
            return self._slots.fill_set(
                slot, lambda x:self._create_connector(
                    x, type, hotpluggable, required, multi, direction, False))
        return self._create_connector(None, type, hotpluggable,
                                 required, multi, direction, False)

    def add_pre_obj_with_name(self, slot, cls, name, **attr):
        '''Helper method which add a pre conf objects to the component. This
        method supports distributed links that require a name as identifier.
        Internal only, use add_pre_obj().'''
        def _create_pre_obj(s, cls, name, **attr):
            if s and not name:
                name = self.obj.name + "." + s
            p = pre_obj(name, cls, **attr)
            p.component = self.obj
            p.component_slot = s
            try:
                c = simics.SIM_get_class(cls)
            except simics.SimExc_General as ex:
                raise CompException("failed creating pre conf object: %s" % ex)
            else:
                if hasattr(c.iface, 'component'):
                    # Until we have separated the hierarchical naming from
                    # components (bug 22162), allow non-components to implement
                    # the component interface (SIMICS-9532).
                    p.__non_component__ = True
                    if not hasattr(c.iface, 'sc_simcontext'):
                        simics.SIM_log_info(
                            1, self.obj, 0,
                            "Warning: .add_pre_obj(slot = '%s') unsupported for"
                            " object implementing component interface" % slot)
            return p
        if slot:
            self._check_slot_name_clash(slot)
            _supported_slot_name(slot, array = True)
            return self._slots.fill_set(
                slot, lambda x:_create_pre_obj(x, cls, name, **attr))
        return _create_pre_obj(None, cls, name, **attr)

    @cli.doc('add pre_conf_obj to component',
             return_value = 'arrays of pre conf objects',
             **_docargs)
    def add_pre_obj(self, slot, cls, name = '', **attr):
        '''Add pre conf objects to the component. The pre conf objects will
        be converted to regular conf objects when the component is
        instantiated.

        The <arg>slot</arg> argument is the slot name concatenated with
        a nested array string, defining the number of pre objects to
        create. Setting <arg>slot</arg> to <em>foo</em> will create one
        pre object in the slot <em>foo</em>, setting <arg>slot</arg> to
        <em>foo[3]</em> will create an array of three pre objects in
        the slot <em>foo</em>, setting <arg>slot</arg> to
        <em>foo[3][2]</em> will create an array of three arrays of two
        arrays with pre objects in the slot <em>foo</em>. The
        <arg>cls</arg> argument is the type of object class to
        create. The <arg>name</arg> argument is deprecated. The
        <arg>attr</arg> argument is optional attribute values for the
        object(s).'''
        if name:
            raise CompException("The name argument to add_pre_obj should"
                                " not be used ('%s')." % name)
        return self.add_pre_obj_with_name(slot, cls, '', **attr)

    @cli.doc('add sub component to component',
             return_value = 'arrays of conf_object_t component object',
             **_docargs)
    def add_component(self, slot, cls, attr, name = ''):
        '''Add a subcomponent or arrays of subcomponents to the
        component. The subcomponent(s) will be created immediately when
        the method is called.

        The <arg>slot</arg> argument is the slot name concatenated with
        a nested array string, defining the number of subcomponents to
        create. Setting <arg>slot</arg> to <em>foo</em> will create one
        subcomponent in the slot <em>foo</em>, setting <arg>slot</arg>
        to <em>foo[3]</em> will create an array of three subcomponents
        in the slot <em>foo</em>, setting <arg>slot</arg> to
        <em>foo[3][2]</em> will create an array of three arrays of two
        arrays with subcomponents in the slot <em>foo</em>.

        The <arg>cls</arg> is the component class, <arg>attr</arg> is
        arguments to the component, and <arg>name</arg> is an optional
        name.'''
        def _create(slot, cls, attr, name):
            p = pre_obj(name, cls)
            p.component_slot = slot
            p.component = self.obj
            for (a_name, a_val) in attr:
                setattr(p, a_name, a_val)
            if slot:
                try:
                    o = simics.VT_add_objects([p])[0]
                except Exception as ex:
                    raise CompException("failed creating sub component: %s"
                                        % ex)
                return o
            return p
        if not slot:
            return _create(None, cls, attr, name)
        _supported_slot_name(slot, array = True)
        self._check_slot_name_clash(slot)
        s = _extract_slot(slot)
        if self._is_loading_checkpoint() and s in self._slots:
            # loading a checkpoint - finalize subcomponents
            self._slots.require_objects_in_slot(s)
            return self._slots.local_get(s)
        else:
            return self._slots.fill_set(
                slot, lambda x:_create(x, cls, attr, name))

    @cli.doc('add slot to component',
             return_value = 'new slot value, i.e. <arg>val</arg>',
             **_docargs)
    def add_slot(self, slot, val):
        '''Add a slot to the component. <arg>slot</arg> is the slot name and
        <arg>val</arg> is the value. The value must be a conf object,
        a pre conf object, or None, or nested lists of these types.'''
        _supported_slot_name(slot)
        _supported_slot_value(val)
        self._check_slot_name_clash(slot)
        val = self._slot_assign_hook(slot, val)
        self._slots.set(slot, val)
        return self._slots.local_get(slot)

    @cli.doc('connect connectors',
             **_docargs)
    def connect(self, cnt0, cnt1):
        '''Connect two connectors <arg>cnt0</arg> and <arg>cnt1</arg>. The
        connectors must be connector objects. A <tt>CompException</tt>
        exception will be raised if the connection failed.'''
        for c in (cnt0, cnt1):
            if not cli.is_connector(c):
                raise CompException('%r is not a connector' % c)
        # workaround for template issues, SIMICS-8938
        if (cnt0 in cnt1.iface.connector.destination() or
            cnt1 in cnt0.iface.connector.destination()):
            return
        import component_commands
        try:
            component_commands.connect_connectors_cmd(cnt0, cnt1)
        except cli.CliError as msg:
            raise CompException('connecting %r to %r failed: %s' % (
                    cnt0, cnt1, msg))

    @cli.doc('delete slot in component',
             **_docargs)
    def del_slot(self, slot):
        '''Delete slot in component. The <arg>slot</arg> argument is the
        slot name. The function returns the slot value if the slot
        exists. All connectors in the slot will be converted to pre conf
        objects and the original connectors will be deleted when
        returning the slot value. A <tt>CompException</tt> exception
        will be raised if the slot does not exist, the slot contains
        non connector conf objects, or the slot contains connectors that
        have been copied with the <fun>copy_connector</fun>
        method. Slots with sub components can not be deleted.'''
        if not slot in self._slots:
            raise CompException('slot "%s" not found and can not be deleted'
                                % slot)
        v = self._slots.local_get(slot)
        ret = self._delete_slot_hook(slot, v)
        self._slots.delete(slot)
        return ret

    @cli.doc('get slot from component',
             return_value = 'slot value',
             **_docargs)
    def get_slot(self, slot):
        '''Get a slot from the component. <arg>slot</arg> is the slot name.
        <arg>slot</arg> can be a slot in this component or a
        hierarchical slot; e.g., looking up <attr>foo.bar</attr> will
        return the slot <attr>bar</attr> from the component in slot
        <attr>foo</attr> from this component. If the lookup fails, a
        <tt>CompException</tt> exception will be raised.'''
        try:
            return self._slots.get(slot)
        except KeyError:
            raise CompException('get_slot lookup error "%s"' % slot)

    def has_slot(self, slot):
        '''Return true if slot exists otherwise False. <arg>slot</arg> is the
        slot name. <arg>slot</arg> can be a slot in this component or
        a hierarchical slot; e.g., looking up <attr>foo.bar</attr> will
        return the slot <attr>bar</attr> from the component in slot
        <attr>foo</attr> from this component.'''
        if slot in self._slots:
            return True
        try:
            self._slots.get(slot)
            return True
        except KeyError:
            return False

    def _info(self):
        connectors = []
        def cmp_connectors(c0, c1):
            return py3_cmp(c0.connector_name, c1.connector_name)
        for c in sorted(component_utils.get_connectors(self.obj),
                        key = cmp_to_key(cmp_connectors)):
            descr = "%-20s %-4s" % (c.iface.connector.type(),
                                    component_utils.convert_direction(c.iface.connector.direction()))
            if c.iface.connector.hotpluggable():
                descr += "  hotplug"
            connectors.append((c.connector_name, descr))
        objs = simics.CORE_shallow_object_iterator(self.obj, True)
        info = [('Slots',
                 sorted([(o.name.rsplit(".")[-1], o.name) for o in objs])),
                ('Connectors', connectors)]
        return info

    def _status(self):
        # setup
        if self.obj.top_level:
            sys_info = [("System Info", self.obj.system_info)]
        else:
            sys_info = []
        status = [("Setup",
                   ([("Top component", self.obj.top_component),
                     ("Instantiated", self.obj.instantiated)]
                    + sys_info))]
        # attributes
        attrs = []
        for (k, v) in self.obj.config_attributes:
            if getattr(self, k, False):
                attrs.append((k, getattr(self.obj, k)))
        if len(attrs):
            status += [("Attributes", sorted(attrs))]
        # connectors
        cnt = [c for c in component_utils.get_connectors(self.obj)
               if c.iface.connector.destination()]
        def dst_connectors(cnt):
            return ["%s:%s" % ((d.component.name
                                   if d.component
                                   else '.'.join(d.name.split('.')[0:-1])),
                               d.connector_name)
                    for d in cnt.iface.connector.destination()]
        cnt = [[c.component_slot, dst_connectors(c)] for c in cnt]
        status += [("Connections", sorted(cnt))]
        return status

    class object_list(Attribute):
        """Dictionary with the instantiated objects that the
        component consists of."""
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = "D|n"
        def getter(self):
            return self._up._slots.all_objects_dict()

    class static_slots(Attribute):
        """Do not use. Kept for checkpoint compatibility."""
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = "D|n"
        def getter(self):
            return self._up._slots.all_objects_dict()
        def setter(self, val):
            # assign hierarchical names to legacy "flat" checkpoints
            if self._up.obj.configured:
                return
            for (slot, v) in val.items():
                self._up._slot_assign_hook(slot, v)
                self._up._slots.set(slot, v)

    class dynamic_slots(Attribute):
        """Do not use. Kept for checkpoint compatibility."""
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = "D|n"
        def getter(self):
            return self._up._slots.all_objects_dict()
        def setter(self, val):
            # assign hierarchical names to legacy "flat" checkpoints
            if self._up.obj.configured:
                return
            for (slot, v) in val.items():
                self._up._slot_assign_hook(slot, v)
                self._up._slots.set(slot, v)

    class basename(ClassAttribute):
        """The basename of the component."""
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = 's|n'
        val = "component"
        @classmethod
        def getter(cls):
            return cls.val
        @classmethod
        def setter(cls, val):
            cls.val = val

    class object_prefix(Attribute):
        """Object prefix string used by the component."""
        attrtype = 's'
        def _initialize(self):
            self.val = ""
        def getter(self):
            if component_utils.get_writing_template():
                return ""
            return self.val
        def setter(self, val):
            self.val = val

    class component_icon(ClassAttribute):
        """Name of a 24x24 pixels large icon in PNG format used to
        graphically represent the component in a configuration viewer."""
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = 's|n'
        val = ""
        @classmethod
        def getter(cls):
            return cls.val
        @classmethod
        def setter(cls, val):
            cls.val = val

    class top_component(Attribute):
        """The top level component. Attribute is not valid until
        the component has been instantiated."""
        attrtype = 'o|n'
        def _initialize(self):
            self.val = None
        def getter(self):
            if component_utils.get_writing_template():
                return None
            return self.val
        def setter(self, val):
            self.val = val

    class instantiated(Attribute):
        """Set to TRUE if the component has been instantiated."""
        attrtype = 'b'
        def _initialize(self):
            self.val = False
        def getter(self):
            if component_utils.get_writing_template():
                return False
            return self.val
        def setter(self, val):
            self.val = val

    class component_queue(Attribute):
        """The queue object for this component. It is only used as
        a placeholder for the real queue object before the component is
        instantiated. It can point to an instantiated cycle object or
        a pre_conf object."""
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = 'a' # so we can use it with pre-conf-object (!!!)
        def _initialize(self):
            self.val = None
        def getter(self):
            if not self._up.instantiated.val:
                if self.val:
                    return self.val
                elif self._up.obj.component:
                    # Inherit default from the "parent" component
                    return self._up.obj.component.queue
                else:
                    return None
            else:
                simics.SIM_attribute_error(
                    "component_queue is not available after component "
                    "instantiation. Use the component's queue attribute "
                    "instead.")
                return None
        def setter(self, val):
            self.val = val

    class pending_cell_object_factories(Attribute):
        """Internal attribute for pending cell objects factories."""
        attrtype = '[[ss]*]'
        def _initialize(self):
            self.val = []
        def getter(self):
            return self.val
        def setter(self, val):
            self.val = val

    class top_level(Attribute):
        """Set to TRUE for top-level components, i.e. the root of a hierarchy."""
        attrtype = 'b'
        def _initialize(self):
            self.val = False
        def getter(self):
            return self.val
        def setter(self, val):
            if val and not self.val:
                # changing from non top-level to top-level
                try:
                    cmputil.cmp_support_top_level(self._up.obj)
                except cmputil.CmpUtilException as ex:
                    print("Warning changing to top-level component: ", ex)
            self.val = val

    class config_attributes(ClassAttribute):
        """Internal attribute see bug 12881. List of all config
        attributes as name of config attribute and default value
        pairs."""
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = '[[s[a*]]*]'
        val = []
        @classmethod
        def getter(cls):
            return cls.val
        @classmethod
        def setter(cls, val):
            cls.val = val

    # required top-level attributes
    class system_info(Attribute):
        """This attribute is only valid for top-level components.
        A short single-line description of the current configuration
        of the  system that the component is a top-level of. The line may
        include the Linux name of the simulated machine, the installed
        operating system, or similar information. For example Tango -
        Fedora Core 5 Linux"""
        attrtype = 's|n'
        def _initialize(self):
            self.val = ""
        def getter(self):
            if component_utils.get_writing_template():
                return ""
            return self.val
        def setter(self, val):
            self.val = val if val else ""
            if self._up.instantiated.val:
                component_utils.trigger_hier_change(self._up.obj)

    class system_icon(ClassAttribute):
        """This attribute is only valid for top-level components.
        Name of an 80x80 pixels large icon in PNG format used to
        graphically represent the system that the component is a
        top-level of."""
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = 's|n'
        val = ""
        @classmethod
        def getter(cls):
            return cls.val

    class machine_icon(Attribute):
        """This attribute is only valid for top-level components.
        An instance of a top-level component may override the default
        <attr>system_icon</attr> with its own icon. This attribute is
        the name of an 80x80 pixel large icon in PNG format that should
        reside in the [host]/lib/images/ directory of the Simics installation
        or the project."""
        attrtype = 's|n'
        def _initialize(self):
            self.val = ""
        def getter(self):
            return self.val
        def setter(self, val):
            self.val = val
            if self._up.instantiated.val:
                component_utils.trigger_hier_change(self._up.obj)

    class components(Attribute):
        """This attribute is only valid for top-level components.
        List of components below the top-level component. This
        attribute is not valid until the object has been instantiated."""
        attrattr = simics.Sim_Attr_Optional
        attrtype = '[o*]'
        def _initialize(self):
            self._val = []
            self._haps = {}
        def getter(self):
            if component_utils.get_writing_template():
                return []
            return [o for o in self._val
                    if not simics.SIM_marked_for_deletion(o)]
        # handle subcomponent deletion
        def _obj_delete(self, dummy, obj):
            self._remove(obj)
        # add component to components attribute
        def add(self, obj):
            if obj in self._val:
                return
            self._val.append(obj)
            self._haps[obj] = simics.SIM_hap_add_callback_obj(
                "Core_Conf_Object_Pre_Delete", obj, 0, self._obj_delete, None)
        # remove component from components attribute
        def _remove(self, obj):
            self._val.remove(obj)
            simics.SIM_hap_delete_callback_id(
                "Core_Conf_Object_Pre_Delete", self._haps.pop(obj))
        def _remove_all(self):
            while self._val:
                self._remove(self._val[0])
        def _pre_delete(self):
            self._remove_all()
        def setter(self, val):
            if val != self._val:
                self._remove_all()
                for obj in val:
                    self.add(obj)

    def deletion_cleanup(self, obj, arg):
        objs = self.components.getter()
        self.components.setter(objs)

    class cpu_list(Attribute):
        """A list of all processors that belong to the component. This
        attribute is not valid until the object has been instantiated. This
        attribute is only used in top-level components and other components
        that are used as software domains."""
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = '[o*]'
        # Components should override the getter, but for historical
        # reasons it is also possible to set cpu_list.val to the list.
        def _initialize(self):
            self.val = []
        def getter(self):
            if component_utils.get_writing_template():
                return []
            return self.val
        def setter(self, val):
            self.val = val

    class domain(Attribute):
        """This attribute is only valid for top-level components.
        Domain to put the component in."""
        attrtype = 'o|n'
        def _initialize(self):
            self.val = None
        def getter(self):
            return self.val
        def setter(self, val):
            if self._up.instantiated.val:
                return simics.Sim_Set_Not_Writable
            else:
                self.val = val

class StandardConnectorComponent(
        StandardComponent,
        metaclass=cli.doc(
            'convenience class for connector components',
            see_also = 'comp.StandardComponent',
            synopsis = False,
            metaclass = pyobj._ConfObjectMeta,
            docu_suffix = '''
            <doclist id="comp.StandardConnectorComponent methods"
                     name="comp.StandardConnectorComponent Methods" sort="az"
                     numbering="false"/>''')):
    """The <class>StandardConnectorComponent</class> is a convenience class for
    connector components. It is a subclass of
    <class>comp.StandardComponent</class> and implements the
    <iface>component_connector</iface> interface."""

    _docargs = {
        'doc_id'    : 'comp.StandardConnectorComponent methods',
        'namespace' : 'StandardConnectorComponent' }

    _do_not_init = object()

    def _initialize(self):
        self._connectors = {}
        StandardComponent._initialize(self)

    def setup(self):
        StandardComponent.setup(self)

    @cli.doc('create a connector component',
             return_value = 'the conf_object connector component',
             doc_id = 'comp.StandardConnectorComponent methods',
             namespace = 'StandardConnectorComponent')
    def add_connector(self, slot, cls):
        """Create a connector component.

        The <arg>slot</arg> argument is the slot name for the connector.

        The <arg>cls</arg> argument is an instance of a connector class."""
        c = StandardComponent.add_connector(
            self, slot, cls.type, cls.hotpluggable,
            cls.required, cls.multi, cls.direction)
        def rec_register_connector(c):
            if isinstance(c, list):
                for c_e in c:
                    rec_register_connector(c_e)
            elif cli.is_connector(c):
                self._connectors[c] = cls
        rec_register_connector(c)
        return c

    class component_connector(Interface):
        def get_check_data(self, cnt):
            return self._up._connectors[cnt].get_check_data(self._up, cnt)
        def get_connect_data(self, cnt):
            return self._up._connectors[cnt].get_connect_data(self._up, cnt)
        def check(self, cnt, attr):
            return self._up._connectors[cnt].check(self._up, cnt, attr)
        def connect(self, cnt, attr):
            self._up._connectors[cnt].connect(self._up, cnt, attr)
        def disconnect(self, cnt):
            self._up._connectors[cnt].disconnect(self._up, cnt)

# connectors
from connectors import *

### create-/new- commands

def _create_component_cmd(attr_names, cls_name, instantiate, obj_name, *attr_vals):
    # attrs
    if len(attr_vals) != len(attr_names):
        raise CompException('create error')
    a_list = []
    for idx in range(len(attr_vals)):
        if attr_vals[idx] != None:
            a_list.append([attr_names[idx], attr_vals[idx]])
    # create name
    if obj_name:
        if component_utils.object_exists(obj_name):
            raise cli.CliError("There already exists an object called '%s'"
                               % obj_name)
    else:
        base = simics.SIM_get_class_attribute(
            simics.SIM_get_class(cls_name), 'basename')
        obj_name = cli.get_available_object_name(base)
    # create object
    try:
        obj = simics.SIM_create_object(cls_name, obj_name, a_list)
    except Exception as ex:
        raise cli.CliError("Failed creating component %s: %s" % (obj_name, ex))

    # instantiate
    if instantiate:
        all_cmps = set(o for o in simics.SIM_object_iterator(obj)
                       if hasattr(o.iface, 'component'))
        all_cmps.add(obj)
        import component_commands
        try:
            component_commands.instantiate_cmd(False, [c for c in all_cmps])
        except cli.CliError as ex:
            if isinstance(obj, simics.conf_object_t):
                # for new- commands, do not leave non-instantiated component
                # objects behind after failure
                try:
                    simics.SIM_delete_object(obj)
                except Exception as del_ex:
                    raise CompException("Cleanup of '%s' failed: %s. Original "
                                        "problem: %s" % (obj_name, del_ex, ex))
            # re-raise the CliError
            raise

        def message():
            return "Created instantiated '%s' component '%s'" % (
                cls_name, obj.name)
        return cli.command_return(value = obj.name,
                                  message = message)
    else:
        def message():
            return "Created non-instantiated '%s' component '%s'" % (
                cls_name, obj.name)
        return cli.command_return(value = obj.name,
                                  message = message)

def _create_arg(arg_name, arg_attr, arg_type, valid):
    arg_seq = []
    arg_dct = {}
    # generic expander
    def _arg_expander(x, valid, arg_type):
        if arg_type in ['i', 'f']:
            return cli.get_completions(x, [str(s) for s in valid])
        elif arg_type == 'b':
            val = []
            val += ['TRUE'] if True in valid else []
            val += ['FALSE'] if False in valid else []
            return cli.get_completions(x, val)
        elif arg_type == 's':
            return cli.get_completions(x, valid)
        return x
    # argument type
    def gen_arg_error(arg_name, arg_type):
        raise CompException(
            'Config attribute %s has unsupported type %s. The supported '
            'types for config attributes are limited to integers, booleans, '
            'strings, floats, or fixed-size lists thereof.' % (arg_name, arg_type))
    def gen_arg_type_error(valid, t):
        raise CompException(
            'The list of valid values does not match argument type. The argument '
            'type is "%s" and the list of valid values are %r.' % (t, valid))
    attrs = arg_type.split('|')
    if 'n' in attrs:
        attrs.remove('n')
    if len(attrs) == 1:
        t = attrs[0] # type of arg
        if t == 'i':
            if [x for x in valid if not isinstance(x, int)]:
                gen_arg_type_error(valid, 'integer')
            arg_seq.append(cli.int_t)
            arg_dct['expander'] = lambda x: _arg_expander(x, valid, t)
        elif t == 'b':
            if [x for x in valid if not isinstance(x, bool)]:
                gen_arg_type_error(valid, 'boolean')
            arg_seq.append(cli.int_t)
            arg_dct['expander'] = lambda x: _arg_expander(x, valid, t)
        elif t == 's':
            if [x for x in valid if not isinstance(x, str)]:
                gen_arg_type_error(valid, 'string')
            arg_seq.append(cli.str_t)
            arg_dct['expander'] = lambda x: _arg_expander(x, valid, t)
        elif t == 'f':
            if [x for x in valid if not isinstance(x, float)]:
                gen_arg_type_error(valid, 'float')
            arg_seq.append(cli.float_t)
            arg_dct['expander'] = lambda x: _arg_expander(x, valid, t)
        else:
            r = re.compile(r'\[[ibsf]*\]\Z')
            if re.match(r, t):
                arg_seq.append(cli.list_t)
            else:
                gen_arg_error(arg_name, arg_type)
    else:
        gen_arg_error(arg_name, arg_type)
    # argument name
    arg_seq.append(arg_name)
    # argument required/optional
    flag = arg_attr & simics.Sim_Attr_Flag_Mask
    if flag == simics.Sim_Attr_Required:
        pass
    elif flag in (simics.Sim_Attr_Optional, simics.Sim_Attr_Pseudo):
        arg_seq.append('?')
    else:
        raise CompException('Unsupported attribute flag %s.' % arg_attr)
    return (arg_seq, arg_dct)

def _create_arg_list(cls_name, config_attrs):
    args_list = [cli.arg(cli.str_t, 'name', '?')]
    l = simics.SIM_get_class(cls_name).attributes
    for (attr, valid) in config_attrs:
        for (a_name, a_attr, a_doc, a_type) in l:
            if a_name == attr:
                (seq, dct) = _create_arg(a_name, a_attr, a_type, valid)
                args_list.append(cli.arg(*seq, **dct))
    return args_list

def _get_attr_list(cls):
    attr_list = []
    for k in cls._subs:
        v = getattr(cls, k)
        if getattr(v, '_config_attr', False):
            attr_list.append([k, v.valid])
    return sorted(attr_list)

def _register_component_commands(cls, cls_name):
    # get _help_categories (if any) only from the class not from the class bases
    extra_help_categories = cls.__dict__.get('_help_categories', [])

    # extra_help_categories must be a list of strings
    if isinstance(extra_help_categories, str):
        raise TypeError('%s._help_categories must be a tuple of strings' % (
            cls_name,))

    # create-<cmp>
    config_attrs = _get_attr_list(cls)
    cls.config_attributes.val = config_attrs
    args = _create_arg_list(cls_name, config_attrs)
    attr_list = [a for (a, d) in config_attrs]
    mod_name = cls_name.replace('_', '-')

    # Prepare for "parent" argument to the new- and create- commands
    if 'parent' in attr_list:
        simics.pr_err("Warning: the component attribute \"parent\" is reserved."
                      " Currently used in the %s class." % cls_name)

    def register_command(cls_name, mod_name, attr_list, args, new):
        # class description
        cdesc, ckind, cifaces, cattrs, cmodule, cports = simics.VT_get_class_info(cls_name)

        # attributes
        attr_str = ""
        attr_a_str = {simics.Sim_Attr_Required: 'Required',
                      simics.Sim_Attr_Optional: 'Optional'}
        cl = simics.SIM_get_class(cls_name).attributes
        attrs = [x for x in cl if x[0] in attr_list]
        attr_str += "<dl>"
        attr_str += "<dt><arg>name</arg> is Optional</dt>"
        attr_str += "<dd>If not specified, the component will get a class-specific default name.</dd>"

        internal_attrs = [x[0]
                          for x in attrs if x[1] & simics.Sim_Attr_Internal]
        for a in attrs:
            (a_name, a_attr, a_doc, a_type) = a
            if a_name in internal_attrs:
                continue
            attr_str += "\n\n<dt><arg>%s</arg> is %s</dt>" % (
                a_name, attr_a_str.get(a_attr & simics.Sim_Attr_Flag_Mask, 'Unknown'))
            attr_str += "<dd>%s</dd>" % a_doc
        attr_str += "</dl>"

        internal_args = [x.name for x in args if x.name in internal_attrs]

        # register command
        if new:
            special = {'prefix': 'new',
                       'inst': 'an instantiated'}
        else:
            special = {'prefix': 'create',
                       'inst': 'a non-instantiated'}
        cli.new_command('%s-%s' % (special['prefix'], mod_name),
                        lambda *x: _create_component_cmd(attr_list, cls_name, new, *x),
                        args,
                        type = ["Components"] + list(extra_help_categories),
                        short = 'create %s %s' % (special['inst'], cls_name),
                        internal_args = internal_args,
                        doc = (
                    """This command creates %s component of the class
                    <class>%s</class>.

                    The class description for the <class>%s</class> class: %s

                    %s""" % (
                    special['inst'], cls_name, cls_name, cdesc, attr_str)))

    if not hasattr(cls, '_no_new_command'):
        register_command(cls_name, mod_name, attr_list, args, True)
    if not hasattr(cls, '_no_create_command'):
        register_command(cls_name, mod_name, attr_list, args, False)
