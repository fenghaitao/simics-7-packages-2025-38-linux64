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


import abc
import unittest
from comp import StandardComponent
from simics import Sim_Attr_Pseudo
import pyobj
import cli

__all__ = ['SystemPanelException', 'SystemPanel',
           'BOOL_OUTPUT', 'BOOL_INPUT', 'NUMBER_OUTPUT', 'NUMBER_INPUT']

__simicsapi_doc_id__ = 'system panel api'

class LayoutObject(object, metaclass=abc.ABCMeta):
    '''Base class for layout objects'''
    @abc.abstractproperty
    def _type(self): pass
    @abc.abstractmethod
    def params(self, context): pass

    def as_attr(self, context):
        return [self._type, self.params(context)]
    def objects(self):
        '''Return a dictionary mapping slot to kind, representing the
        layout's minimum requirements on the panel'''
        result = {}
        for slot, kind in self._objects():
            # TODO: the type checking here can fail incorrectly.  If
            # two slots are not comparable, there may still exist a
            # common subkind that can be used.
            if slot in result:
                if kind.is_subkind(result[slot]):
                    # the new value is stricter
                    result[slot] = kind
                elif not result[slot].is_subkind(kind):
                    raise SystemPanelException(
                        "Panel object %s appears twice in the same layout as"
                        " conflicting types: %s and %s"
                        % (slot, kind, result[slot]))
            else:
                result[slot] = kind
        return result

    def _objects(self):
        return []

class SystemPanelException(
        Exception,
        metaclass=cli.doc('System panel error', synopsis = False)):
    '''Exception thrown for various errors in the system_panel module'''

class PanelObjectKind(object, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def confclass(self): pass

    @abc.abstractmethod
    def conf_attributes(self): pass

    @abc.abstractmethod
    def is_subkind(self, superkind):
        '''Return true if a panel object with this kind can be used
        for a widget whose kind is given by superkind.  The subkind
        relation is assumed to be:

        - reflexive: x.is_subkind(x) is always true

        - antisymmetric: if x.is_subkind(y) and y.is_subkind(x), then
          y and x are equivalent with respect to the is_subkind
          relation

        - transitive: if x.is_subkind(y) and y.is_subkind(z), then
          x.is_subkind(z).'''

class StaticKind(PanelObjectKind):
    def __init__(self, name, confclass):
        self._name = name
        self._confclass = confclass

    def __repr__(self):
        return self.__module__ + "." + self._name

    def confclass(self):
        return self._confclass

    def conf_attributes(self):
        return {}

    def is_subkind(self, superkind):
        return (isinstance(superkind, StaticKind)
                and superkind.confclass == self.confclass)

class NumberOutputKind(PanelObjectKind):
    def __init__(self, restriction):
        self.restriction = restriction

    def __repr__(self):
        return "%s.%s(%r)" % (self.__module__, self.__class__.__name__,
                              self.restriction)

    def is_subkind(self, superkind):
        return (isinstance(superkind, NumberOutputKind)
                and (superkind.restriction == None
                     or (self.restriction != None
                         and self.restriction <= superkind.restriction)))

    def confclass(self):
        return "system_panel_number"

    def conf_attributes(self):
        return {"restriction": self.restriction}

BOOL_OUTPUT = StaticKind('BOOL_OUTPUT', 'system_panel_bool')
BOOL_INPUT = StaticKind('BOOL_INPUT', 'system_panel_bool')
NUMBER_OUTPUT = NumberOutputKind(None)
NUMBER_INPUT = StaticKind('NUMBER_INPUT', 'system_panel_number')

class Test_kinds(unittest.TestCase):
    def test_repr(self):
        self.assertEqual(repr(StaticKind('foo', 'bar')), 'systempanel.foo')
        self.assertEqual(str(StaticKind('foo', 'bar')), 'systempanel.foo')
        self.assertEqual(repr(NumberOutputKind(47)),
                         'systempanel.NumberOutputKind(47)')
        self.assertEqual(str(NumberOutputKind(None)),
                         'systempanel.NumberOutputKind(None)')

    def test_is_subkind(self):
        # reflexive
        for kind in [BOOL_OUTPUT, BOOL_INPUT, NUMBER_OUTPUT, NUMBER_INPUT,
                 NumberOutputKind(None), NumberOutputKind(11)]:
            self.assertTrue(kind.is_subkind(kind))
        self.assertTrue(NumberOutputKind(1).is_subkind(NumberOutputKind(1)))
        #self.assertTrue(NumberOutputKind(None).is_subkind(NUMBER_OUTPUT))
        self.assertTrue(NUMBER_OUTPUT.is_subkind(NumberOutputKind(None)))

        # incompatible types are not subtypes of each other
        incompatible = [BOOL_OUTPUT, BOOL_INPUT, NUMBER_INPUT,
                        NumberOutputKind(18)]
        for a in incompatible:
            for b in incompatible:
                if a != b:
                    self.assertFalse(a.is_subkind(b))

        # in the parameterized NumberOutput, smaller numbers are
        # stricter types than bigger numbers, and None counts as
        # infinity.
        self.assertTrue(NumberOutputKind(1).is_subkind(NumberOutputKind(14)))
        self.assertFalse(NumberOutputKind(14).is_subkind(NumberOutputKind(1)))
        self.assertTrue(NumberOutputKind(14).is_subkind(NumberOutputKind(None)))
        self.assertFalse(NumberOutputKind(None).is_subkind(
                NumberOutputKind(14)))

class SystemPanel(
        StandardComponent,
        metaclass=cli.doc(
            'Base class for system panel components',
            synopsis = False, metaclass = pyobj._ConfObjectMeta)):
    """A base class for system panels. A system panel class should
    inherit from this and set the 'layout' class variable to describe
    the contents of the panel."""
    _do_not_init = object()

    def setup(self):
        # We may want to make default_layout optional in the future,
        # but currently it is the only way to provide a layout so we'd
        # better catch early if it's missing.
        for attr in ["objects", "default_layout"]:
            if not hasattr(self.__class__, attr):
                raise SystemPanelException(
                    "Missing required class attribute %r in component %s"
                    % (attr, self.__class__.__name__))
        if not isinstance(self.__class__.objects, dict):
            raise SystemPanelException(
                "Wrong type of 'objects' class attribute, expected 'dict'")
        if not isinstance(self.__class__.default_layout, LayoutObject):
            raise SystemPanelException(
                "Wrong type of 'default_layout' class attribute, expected "
                "instance of LayoutObject")

        self.validate_layout(self.default_layout)

        StandardComponent.setup(self)
        self.panel_connectors = {}
        self.subpanel_slots = set()
        if not self.instantiated.val:
            self.add_objects()

    class basename(StandardComponent.basename):
        val = "panel"

    class subpanel_slots(pyobj.Attribute):
        """A list of slot names for all subpanel slots."""
        attrattr = Sim_Attr_Pseudo
        type = "[s*]"
        def getter(self):
            return sorted(self._up.subpanel_slots)

    def add_subpanel(self, connector_name):
        assert connector_name not in self.subpanel_slots
        self.subpanel_slots.add(connector_name)
        self.add_slot(connector_name, None)

    def validate_layout(self, layout):
        layout_objs = layout.objects()
        for o in layout_objs:
            if not o in self.__class__.objects:
                raise SystemPanelException(
                    'Panel object %s.%s required by layout not found in'
                    ' this panel' % (self.obj.name, o))
            if not self.__class__.objects[o].is_subkind(layout_objs[o]):
                raise SystemPanelException(
                    'Mismatching panel object types for object %s.%s:'
                    ' Layout expects %s, panel contains %s'
                    % (self.obj.name, o, layout_objs[o],
                       self.__class__.objects[o]))

    def add_objects(self):
        panel_state_manager = self.add_pre_obj("panel_state_manager",
                                                    "system_panel_state_manager",
                                                    panel_component = self.obj,
                                                    use_recorder = True)

        # Read the 'objects' attribute as a class attribute to
        # discourage instance-specific overrides, which too easily
        # breaks checkpointing.  We should instead encourage the use
        # of some not-yet-implemented clean way to override layouts.
        for name, kind in self.__class__.objects.items():
            if name.startswith('panel'):
                raise SystemPanelException(
                    "Invalid panel element name %r.  Names may not start"
                    " with 'panel'" % name)
            if not isinstance(kind, PanelObjectKind):
                raise SystemPanelException(
                    "Invalid panel element kind for element %r:"
                    " Expected BOOL_OUTPUT, BOOL_INPUT etc, got %r"
                    % (name, kind))
            self.add_pre_obj(name, kind.confclass(),
                             panel = panel_state_manager,
                             **kind.conf_attributes())
    # Override the component::set_slot_value implementation to catch
    # when subpanels are set.
    class component(StandardComponent.component):
        def set_slot_value(self, slot, val):
            super().set_slot_value(slot, val)
            #TODO: Notify frontend the changes
        def post_instantiate(self):
            # TODO: it would be better if authority could be set
            # declaratively, then this could be moved to add_objects()
            all_objs = [
                self._up.get_slot(slot) for slot in self._up.__class__.objects]
            self._up.obj.panel_state_manager.panel_objects = all_objs
            self._up.obj.panel_state_manager.polled_panel_objects = [
                o for o in all_objs if hasattr(o, 'authority') and o.authority]

    class system_panel_layout(pyobj.Interface):
        def get_layout(self):
            sm = self._up.obj.panel_state_manager
            class Context:
                def __init__(self, sm):
                    self.sm = sm
                def state_manager(self):
                    return self.sm
            return self._up.__class__.default_layout.as_attr(Context(sm))
        def state_manager(self):
            return self._up.obj.panel_state_manager

    # Show layout in info command
    def get_layout(self, layout, level=0):
        [type, params] = layout
        params = dict(params)
        ret = ["  " * level + "%s:" % type]

        if type == 'GridContainer':
            columns = params['columns']
            contents = params['contents']
            i = 0
            for content in contents:
                if columns > 1:
                    if i == columns:
                        ret += [""]
                        i = 1
                    else:
                        i = i + 1
                ret += self.get_layout(content, level+1)
        elif type == 'LabeledBox':
            ret[-1] += ' ' + params['label']
            container = params['container']
            ret += self.get_layout(container, level+1)
        elif type == 'Canvas':
            contents = params['contents']
            for content in contents:
                ret += self.get_layout(content[-1], level+1)
        elif type == 'Label':
            ret[-1] += ' ' + params['label']
        elif type in ['Led', 'NumberOutput', 'NumberInput',
                      'ToggleButton', 'Button', 'BitmapLed',
                      'BitmapToggleButton']:
            ret[-1] += ' ' + params['oname'][1]
        elif type == 'Image':
            ret[-1] += '  can not display in text mode'
        elif type == 'Empty':
            pass
        else:
            print("Unsupported format %s" % type)
        return ret

    def _info(self):
        component_info = super()._info()
        layout = self.get_layout(self.system_panel_layout.get_layout())
        return component_info + [('Layout', [('Panel', layout)])]

_all_panels = []
_all_frontends = []

def register_panel(obj):
    global _all_panels
    assert hasattr(obj.iface, "system_panel_layout")
    _all_panels.append(obj)
    for frontend in _all_frontends:
        frontend.iface.system_panel_frontend.layout_changed()

def register_frontend(obj):
    global _all_frontends
    assert hasattr(obj.iface, "system_panel_frontend")
    _all_frontends.append(obj)

def all_panels():
    global _all_panels
    return _all_panels
