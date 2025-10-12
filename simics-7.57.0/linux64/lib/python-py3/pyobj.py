# © 2010 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import cli, simics, traceback, sys
import inspect
import pyclass_common

# used by cli.doc()
__simicsapi_doc_id__ = 'pyobj module'

def _copy_class_attr(v):
    # create a new subclass of the ClassAttribute class
    v = type(v.__name__, (v,), {})
    if hasattr(v, "val"):
        val = v.val
        # make a shallow copy, in case val is modified in place
        if isinstance(val, dict) or isinstance(val, list):
            val = type(val)(val)
        # ensures val exists in the derived class (we do not want the value
        # to change in the superclass if it is modified from the subclass)
        v.val = val
    return v

class _ObjMeta(type):
    def __init__(cls, name, bases, dct):
        subs = []
        for k in dir(cls):
            v = getattr(cls, k)
            if (not issubclass(type(v), _ObjMeta)
                or k == '_up' or k == '_top'):
                continue
            if issubclass(v, ClassAttribute) and v not in cls.__dict__:
                v = _copy_class_attr(v)
                setattr(cls, k, v)
            if issubclass(v, ConfObject):
                continue
            subs.append(k)
        cls._subs = tuple(subs)
        super(_ObjMeta, cls).__init__(name, bases, dct)

class _ConfObjectMeta(_ObjMeta):
    def __init__(self, name, bases, dct):
        super(_ConfObjectMeta, self).__init__(name, bases, dct)
        if automatic_registration(self):
            self._register(name)

def _instantiate_subobjects(o, top):
    if o != top:
        top._all_subs.append(o)
    cls = type(o)
    for k in cls._subs:
        val = getattr(cls, k)(top, o)
        setattr(o, k, val)
        top._omap[type(val)] = val

class _Obj:
    @classmethod
    def _mangle_name(cls, sort, name):
        name = getattr(cls, '_mangle_%s_name' % sort, lambda n: n)(name)
        if hasattr(cls, '_up'):
            return cls._up._mangle_name(sort, name)
        else:
            return name
    def _initialize(self): pass
    def _finalize(self): pass
    def _pre_delete(self): pass

class _SubObj(_Obj, metaclass=_ObjMeta):
    @classmethod
    def _register(cls, classname): pass
    def __init__(self, top, up):
        self._up = up
        self._top = top
        _instantiate_subobjects(self, top)

class Port(
        _SubObj,
        metaclass=cli.doc(
            'a Simics port',
            synopsis = False,
            see_also = 'pyobj.Interface, pyobj.ConfObject',
            metaclass = _ObjMeta,
            example = '''
            <pre size="small">class wee(pyobj.Port):
                class signal(pyobj.Interface):
                    def signal_raise(self): self.val = 2
                    def signal_lower(self): self.val = 1
                    def _initialize(self): self.val = 0</pre>''')):
    '''To have your <class>ConfObject</class>-based Simics object implement
    port interfaces, put a subclass of <class>pyobj.Port</class> as an inner
    class of your <class>ConfObject</class>, and put one or more
    <class>pyobj.Interface</class> subclasses inside it. The
    <class>pyobj.Interface</class> subclasses will work just as if they were at
    the top level, except that they will be registered with
    <fun>SIM_register_port_interface</fun> instead of
    <fun>SIM_register_interface</fun>.

    The <fun>_initialize</fun> method can be overridden if special
    initialization behavior is required.'''

    @classmethod
    def _mangle_port_name(cls, name):
        if name:
            raise Exception('Nested ports: %s and %s' % (name, cls.__name__))
        else:
            return cls.__name__

class PortObject(
        _SubObj,
        metaclass=cli.doc(
            'a Simics port object',
            see_also = 'pyobj.ConfObject',
            synopsis = False,
            metaclass = _ObjMeta,
            example = '''
            <pre size="small">class portname(pyobj.PortObject):
                """Documentation for the port object goes here."""
                class signal(pyobj.Interface):
                    def signal_raise(self): self.val = 2
                    def signal_lower(self): self.val = 1
                    def _initialize(self): self.val = 0</pre>''')):
    '''The <class>pyobj.PortObject</class> class defines a port object class
    that will be registered as a port object for the containing
    <class>ConfObject</class> class.

    The port object will be registered with the name "port.&lt;name&gt;",
    but this can be changed by defining <var>namespace</var> to something other
    than "port". One possibility is the empty string.

    If <var>classname</var> is set, then the port object will be
    an instance of this external class rather than defining the class
    locally. The external class cannot be modified by adding e.g.
    an interface definition inside the <class>PortObject</class> definition.
'''

    namespace = "port"
    def __init__(self, top, up):
        prefix = "%s." % self.namespace if self.namespace else ""
        self.obj = simics.SIM_object_descendant(
            up.obj, prefix + type(self).__name__)
        super(PortObject, self).__init__(top, up)
        self.obj.object_data = self
        # share object mapper with parent for simplicity
        self._omap = top._omap

    @classmethod
    def _getobj(cls, obj, sub_cls):
        return obj.object_data._omap[sub_cls]

    @classmethod
    def _register(cls, classname):
        port_cls = getattr(cls, "classname", None)
        prefix = "%s." % cls.namespace if cls.namespace else ""
        name = prefix + cls.__name__
        if port_cls:
            simics.SIM_register_port(classname, name, port_cls, cls.__doc__)
            # disallow subobjects (the external must not be modified)
            cls._classname = None
        else:
            port_cls = simics.SIM_register_simple_port(
                classname, name, cls.__doc__)
            cls._classname = port_cls.classname


# NOTE, not documented on purpose
class AttrGroup(_SubObj):
    @classmethod
    def _mangle_attr_name(cls, name):
        return '%s_%s' % (cls.__name__, name)

class Attribute(
        _SubObj,
        metaclass=cli.doc(
            'a Simics attribute',
            see_also = ('pyobj.SimpleAttribute, pyobj.ClassAttribute,'
                        ' pyobj.ConfObject'),
            synopsis = False,
            metaclass = _ObjMeta,
            example = '''
            <pre size="small">class wee(pyobj.Attribute):
                """Documentation for the attribute goes here."""
                attrattr = simics.Sim_Attr_Pseudo
                attrtype = 'i'
                def _initialize(self):
                    self.val = 4711
                def getter(self):
                    self.val += 3
                    return self.val
                def setter(self, val):
                    self.val = val</pre>''')):
    '''The <class>pyobj.Attribute</class> class defines an attribute that will
    be registered for the containing <class>ConfObject</class> class. The
    attribute will be registered with Simics using the
    <fun>SIM_register_attribute</fun> function. See documentation for
    <fun>SIM_register_attribute</fun> for detailed information about
    attributes.

    The arguments to <fun>SIM_register_attribute</fun> is taken from the
    class members. The <var>attrattr</var> member is an
    <type>attr_attr_t</type> type and its default value is
    <tt>Sim_Attr_Optional</tt>. The <var>attrtype</var> member is a string
    defining the type of the attribute, default value is <em>'a'</em>.

    The class methods named <fun>getter</fun> and <fun>setter</fun> will be
    used as <fun>get_attr</fun> and <fun>set_attr</fun> functions when
    registering the attribute. The methods are optional. An attribute without a
    <fun>getter</fun> can not be read. An attribute without a <fun>setter</fun>
    can not be written.

    The attribute description is the same as the Python class description.

    The <fun>_initialize</fun> method can be defined if special initialization
    behavior is required. This can for instance be used to set the default
    value.'''

    attrattr = simics.Sim_Attr_Optional
    attrtype = 'a'
    register_function = simics.SIM_register_typed_attribute
    @classmethod
    def _register(cls, class_name):
        attr_name = cls._mangle_name('attr', cls.__name__)
        def desc():
            return '%s.%s' % (class_name, attr_name)
        obj_mapper = cls._getobj
        gfun = getattr(cls, "getter", None)
        sfun = getattr(cls, "setter", None)
        # we need the unbound version of classmethods
        gfun = gfun if gfun else None
        sfun = sfun if sfun else None
        if gfun is not None and hasattr(gfun, '__func__'):
            gfun = gfun.__func__
        if sfun is not None and hasattr(sfun, '__func__'):
            sfun = sfun.__func__

        def getter(arg, obj, idx):
            py_obj = obj_mapper(obj, cls)
            return pyclass_common.handle_attr_get_errors(
                desc(), gfun, py_obj)

        def setter(arg, obj, val, idx):
            py_obj = obj_mapper(obj, cls)
            return pyclass_common.handle_attr_set_errors(
                desc(), sfun, py_obj, val)

        cls.register_function(
            class_name, attr_name,
            getter if getattr(cls, 'getter', None) != None else None, None,
            setter if getattr(cls, 'setter', None) != None else None, None,
            cls.attrattr, cls.attrtype, None, cls.__doc__)

class ClassAttribute(
        Attribute,
        metaclass=cli.doc(
            'a Simics class attribute',
            see_also = 'pyobj.Attribute, pyobj.ConfObject',
            synopsis = False,
            metaclass = _ObjMeta,
            example = '''
            <pre size="small">class wee(pyobj.ClassAttribute):
                """Documentation for the attribute goes here."""
                attrtype = 'i'
                val = 4711
                @classmethod
                def getter(cls): return cls.val
                @classmethod
                def setter(cls, val): cls.val = val</pre>''')):
    '''The <class>pyobj.ClassAttribute</class> class defines an attribute that
    will be registered for the containing <class>ConfObject</class> class. The
    attribute will be registered with Simics using the
    <fun>SIM_register_class_attribute</fun> function. See documentation
    for <fun>SIM_register_class_attribute</fun> for detailed information
    about class attributes.

    The value stored in the class should always be stored in the
    attribute named <tt>val</tt>. This is to avoid problems when a
    class that defines a <class>pyobj.Attribute</class> class is
    inherited by more than one class.

    The <class>pyobj.ClassAttribute</class> class is very similar to the
    <class>pyobj.Attribute</class> class. See the documentation for the
    <class>pyobj.Attribute</class> class for how to use this class.'''

    attrattr = simics.Sim_Attr_Pseudo
    register_function = simics.SIM_register_typed_class_attribute
    @classmethod
    def _getobj(cls, obj, sub_cls): return cls
    def __new__(cls, *args, **kw): return cls
    @classmethod
    def _initialize(cls): pass
    @classmethod
    def _finalize(cls): pass


@cli.doc('a simple Simics attribute',
         see_also = 'pyobj.Attribute, pyobj.ConfObject',
         return_value = 'pyobj.Attribute class',
         example = '''
         <pre size="small">class wee(pyobj.SimpleAttribute(17, 'i')):
             """Documentation for the attribute goes here."""</pre>''')
def SimpleAttribute(init, type = 'a', attr = simics.Sim_Attr_Optional):
    '''The <fun>pyobj.SimpleAttribute</fun> function returns a new subclass of
    <class>pyobj.Attribute</class>, with predefined getter and setter functions
    that simply store and retrieve the value without further side effects. The
    value is stored in the <tt>val</tt> member.

    The <arg>init</arg> argument is the initial value, <arg>type</arg> is the
    attribute type string, <arg>attr</arg> is the attribute type. If
    <arg>init</arg> is callable, it will be called, and the return value is the
    initial value; otherwise, <arg>init</arg> itself is the initial value.

    The attribute value is stored in the <var>val</var> member of the class.'''
    class SA(Attribute):
        attrattr = attr
        attrtype = type
        def _initialize(self):
            try:
                self.val = init()
            except TypeError:
                self.val = init
        def getter(self): return self.val
        def setter(self, val): self.val = val
    return SA

class Interface(
        _SubObj,
        metaclass=cli.doc(
            'a Simics interface',
            synopsis = False,
            see_also = 'pyobj.Port, pyobj.ConfObject',
            metaclass = _ObjMeta,
            example = '''
            <pre size="small">class signal(pyobj.Interface):
                def signal_raise(self): self.val = True
                def signal_lower(self): self.val = False
                def _initialize(self): self.val = False</pre>''')):
    '''The <class>pyobj.Interface</class> class implements a Simics
    interface for the containing <class>ConfObject</class> class. The
    interface is registered using the <fun>SIM_register_interface</fun>
    function. The interface name is taken from the class name.

    The <fun>_initialize</fun> method can be overridden if special
    initialization behavior is required.

    To implement port interfaces instead of regular interfaces, place
    one or more <class>pyobj.Interface</class> subclasses inside a
    <class>pyobj.Port</class> class.'''

    @classmethod
    def _register(cls, class_name):
        def ifacefun(m):
            mapper = cls._getobj
            def f2(obj, *args):
                return f(mapper(obj, cls), *args)
            f = getattr(cls, m)
            argspec = inspect.getfullargspec(f)
            static = len(argspec.args) > 0 and argspec.args[0] != 'self'
            # There seem to be no better way than the following in Python
            # 3 to determine if a class method is static since all methods
            # now are functions. Compare with the old mechanism while
            # we can.
            return f if static else f2

        ifc_class = simics.SIM_get_python_interface_type(cls.__name__)
        if ifc_class is None:
            raise LookupError('%s.%s: cannot find Python support'
                              ' for the %r interface' % (
                    (Interface.__module__, Interface.__name__,
                     cls.__name__,)))
        ifc = ifc_class()
        methods = [m for m in dir(ifc) if not m.startswith('_')]
        for m in methods:
            if hasattr(cls, m):
                setattr(ifc, m, ifacefun(m))

        port = cls._mangle_name('port', None)
        if port:
            simics.SIM_register_port_interface(class_name, cls.__name__, ifc,
                                               port, cls._up.__doc__)
        else:
            simics.SIM_register_interface(class_name, cls.__name__, ifc)

class Event(
        _SubObj,
        metaclass=cli.doc(
            'a Simics event',
            synopsis = False,
            see_also = 'SIM_register_event, pyobj.ConfObject',
            metaclass = _ObjMeta,
            example = '''
            <pre size="small">class foo(pyobj.ConfObject):
                class ev1(pyobj.Event):
                    def callback(self, data):
                        do_something(data)
                class ev2(pyobj.Event):
                    def callback(self, data):
                        self.do_something_else(data)
                    def get_value(self, data):
                        return str(data)
                    def set_value(self, val):
                        return int(val)
                    def describe(self, data):
                        return 'ev2 with %s' % data
                class ev3(pyobj.Event):
                    flags = simics.Sim_EC_Notsaved
                    def callback(self, data):
                        self._up.do_this_third_thing(data)</pre>''')):
    '''<class>pyobj.Event</class> defines an event that will be registered
    for the containing <class>ConfObject</class> class. Internally,
    registration is done with <fun>SIM_register_event</fun>; see the
    documentation for that API function for detailed information.

    Events are posted with the <fun>post(clock, data,
    &lt;duration&gt;)</fun> method. <arg>clock</arg> determines which
    clock the event is posted on, and <arg>data</arg> is the event
    data. The duration is the number of <arg>seconds</arg>,
    <arg>cycles</arg>, or <arg>steps</arg> until the event triggers,
    specified with the appropriate keyword argument:

    <pre>
    ev.post(a_clock, some_data, seconds=4.711)
    ev.post(a_clock, some_data, cycles=4711)
    ev.post(a_clock, some_data, steps=4711)
    </pre>

    Events can be cancelled before they trigger with either
    <fun>cancel_time(clock, match_fun)</fun> or <fun>cancel_step(clock,
    match_fun)</fun> (depending on whether the event duration was
    specified in steps or not). The <arg>match_fun</arg> argument is
    optional: if given, it should be a function that accepts an event
    data parameter, and returns true for the events that should be
    cancelled; if not given, all events are cancelled.

    A subclass may define the following methods:

    <dl>

    <dt><fun>callback(data)</fun></dt> <dd>Called when the event
    triggers. Overriding this method is not optional.</dd>

    <dt><fun>destroy(data)</fun></dt> <dd>Called when the event is
    removed from the queue without being called. The method is not
    allowed to use any event API calls; it is mainly intended for
    freeing event data.</dd>

    <dt><fun>get_value(data)</fun> and <fun>set_value(val)</fun></dt>
    <dd>Converts the given event data to an <tt>attr_value_t</tt> value,
    and the other way around. If the event carries no data that needs
    checkpointing, you may omit these methods.</dd>

    <dt><fun>describe(data)</fun></dt> <dd>Called to generate a
    human-readable description of the event to be used in the
    print-event-queue command. If you do not supply this method, the
    event's name will be used.</dd>

    </dl>

    Additionally, it may set the <var>flags</var> parameter to
    <tt>Sim_EC_Notsaved</tt>, if the event should not be checkpointed.
    In this case, neither <fun>get_value</fun> nor <fun>set_value</fun>
    should be defined.'''

    flags = 0
    @classmethod
    def _register(cls, class_name):
        obj_mapper = cls._getobj
        def callback(obj, data):
            obj_mapper(obj, cls).callback(data)
        def destroy(obj, data):
            obj_mapper(obj, cls).destroy(data)
        def get_value(obj, data):
            return obj_mapper(obj, cls).get_value(data)
        def set_value(obj, val):
            return obj_mapper(obj, cls).set_value(val)
        def describe(obj, data):
            return obj_mapper(obj, cls).describe(data)
        def maybe(fun, name):
            return fun if getattr(cls, name, None) != None else None
        if not getattr(cls, 'callback', None):
            raise Exception('callback not defined')
        if cls.flags == 0:
            if (bool(getattr(cls, 'get_value', None))
                != bool(getattr(cls, 'set_value', None))):
                raise Exception('get_value and set_value must be both'
                                ' set or both unset')
        elif cls.flags == simics.Sim_EC_Notsaved:
            if any(getattr(cls, f, None) for f in ['get_value', 'set_value']):
                raise Exception('get_value and set_value must be unset'
                                ' for Sim_EC_Notsaved')
        else:
            raise Exception('Illegal flag value %r' % cls.flags)
        cls._evclass = simics.SIM_register_event(
            cls.__name__, class_name, cls.flags, callback,
            maybe(destroy, 'destroy'), maybe(get_value, 'get_value'),
            maybe(set_value, 'set_value'), maybe(describe, 'describe'))
    def post(self, clock, data, **kw):
        if len(kw) != 1:
            raise Exception('Need duration: seconds, cycles, or steps')
        [(key, val)] = list(kw.items())
        if key == 'seconds':
            simics.SIM_event_post_time(clock, self._evclass, self._top.obj,
                                       val, data)
        elif key == 'cycles':
            simics.SIM_event_post_cycle(clock, self._evclass, self._top.obj,
                                        val, data)
        elif key == 'steps':
            simics.SIM_event_post_step(clock, self._evclass, self._top.obj,
                                       val, data)
        else:
            raise Exception('Bad duration specifier: %s' % key)
    def cancel_time(self, clock, match_fun = None):
        def pred(data, match_data): return bool(match_fun(data))
        simics.SIM_event_cancel_time(clock, self._evclass, self._top.obj,
                                     pred if match_fun else None, None)
    def cancel_step(self, clock, match_fun = None):
        def pred(data, match_data): return bool(match_fun(data))
        simics.SIM_event_cancel_step(clock, self._evclass, self._top.obj,
                                     pred if match_fun else None, None)

def automatic_registration(cls):
    return cls._do_not_init in [
        getattr(b, '_do_not_init', None) for b in cls.__bases__]

class ConfObject(
        _Obj,
        metaclass=cli.doc(
            'a Simics configuration object',
            synopsis = False,
            metaclass = _ConfObjectMeta,
            example = '''
            <pre size="small">class foo(pyobj.ConfObject):
                """This is the long-winded documentation for this Simics class.
                It can be as long as you want."""
                _class_desc = 'One-line doc for the class'

                def _initialize(self):
                    super()._initialize()
                    self.my_val = 4711

                def _info(self):
                     return [("Python device info", [("my_val", self.my_val)])]

                def _status(self):
                     return [("Python device status",
                              [("woot", self.woot.val),
                               ("signal", self.signal.val)])]

                class woot(pyobj.SimpleAttribute(0, 'i|n')):
                    """A four-letter attribute"""

                class lost(pyobj.Attribute):
                    """A pseudo attribute"""
                    attrattr = simics.Sim_Attr_Pseudo
                    def getter(self):
                        return self._up.my_val

                class signal(pyobj.Interface):
                    def signal_raise(self): self.val = True
                    def signal_lower(self): self.val = False
                    def _initialize(self): self.val = False</pre>''')):
    '''The <class>pyobj.ConfObject</class> class defines a new Simics class
    using the <fun>SIM_register_class</fun> function. You could call
    <fun>SIM_register_class</fun> and all the related functions for
    attribute and interface registration yourself, but
    <class>ConfObject</class> will make your code much more concise.

    The name of the Simics class is identical to the Python
    class. The class description is the same as the Python class
    description.

    The class implements the methods <fun>_initialize</fun>,
    <fun>_finalize</fun>, <fun>_pre_delete</fun>, <fun>_info</fun>, and
    <fun>_status</fun>. All of these methods can be overridden if
    required.

    The <fun>_initialize</fun> method is called when an object of the
    class is instantiated. The <fun>_finalize</fun> method is called
    when the object is finalized. The <fun>_pre_delete</fun> method is
    called right before an object of the class is deleted.

    The <fun>_info</fun> and <fun>_status</fun> methods provide data for
    the class's <cmd>info</cmd> and <cmd>status</cmd> commands; the
    format of their return value is documented with
    <fun>cli.new_info_command</fun> and
    <fun>cli.new_status_command</fun>.

    If you need to get hold of the Simics <tt>conf_object_t</tt> object
    associated with a <class>ConfObject</class> instance&mdash;for
    example, in order to call a Simics API function&mdash;you can find
    it in the <var>obj</var> member.

    The <class>pyobj.ConfObject</class> class can contain inner classes
    that define attributes, interfaces, etc. See
    <class>pyobj.Port</class>, <class>pyobj.Attribute</class>,
    <class>pyobj.ClassAttribute</class>, and
    <class>pyobj.Interface</class> for more documentation. An inner
    class has a reference to the class that contains it in its
    <var>_up</var> member.

    By default, a Simics class is registered automatically whenever a
    subclass of <class>pyobj.ConfObject</class> is declared. Sometimes
    this is not desirable; e.g., the class may be a base class, or you
    may want to allow importing the containing Python file without
    side-effects. The automatic registration of a Simics class can
    then be suppressed by setting the member <tt>_do_not_init</tt> to
    <tt>object()</tt>. That will cause it to not be registered as a
    Simics class (but its subclasses will be, unless they too employ
    the same trick).

    The class method <fun>register</fun> may be called once on each
    <class>pyobj.ConfObject</class> subclass, to register the Simics
    class. For a class that doesn't suppress automatic registration, the
    method currently does nothing.

    In future Simics versions, a Simics class will no longer be
    registered automatically, and an explicit call to the
    <fun>register</fun> method will be required for that.

    The <var>_class_kind</var> member tells Simics whether objects of
    this class should be saved when a checkpoint is created.
    The value is passed to <fun>SIM_register_class</fun>, as the
    <var>kind</var> field of the <type>class_data_t</type> structure.
    The default value is <type>Sim_Class_Kind_Vanilla</type>.
    See the documentation of <fun>SIM_register_class</fun> for details.'''

    _do_not_init = object()
    _class_kind = simics.Sim_Class_Kind_Vanilla
    def __init__(self):
        self._omap = {}
        self._all_subs = []
        _instantiate_subobjects(self, self)
        self._initialize()
    @classmethod
    def _register(cls, class_name):
        def deinit(unused, obj, _): obj.object_data._pre_delete()
        def init(obj):
            # Ugly hack: We call __new__ manually in order to be able
            # to set .obj before we call __init__. It would be much
            # prettier to simply pass obj as an argument to __init__,
            # but that breaks compatibility.
            pyobj = cls.__new__(cls)
            pyobj.obj = obj
            pyobj.__init__()
            simics.SIM_add_notifier(obj, simics.Sim_Notify_Object_Delete,
                                    None, deinit, None)
            return pyobj
        def finalize(obj):
            try:
                obj.object_data._finalize()
            except Exception as ex:
                traceback.print_exc(file = sys.stdout)
                simics.SIM_attribute_error(
                    "unexpected Python exception in finalize_instance: %s" % ex)
        class_info = simics.class_info_t(
            init        = init,
            finalize    = finalize,
            kind        = cls._class_kind,
            description = cls.__doc__,
            short_desc  = getattr(cls, '_class_desc', ''))
        # No port to use of new class methods, since this relies on the
        # pre_delete_instance being called at the right time, and in this
        # case the delete notifier does not work, because of what we do
        # in init_object above.
        simics.SIM_create_class(class_name, class_info)
        cli.new_info_command(class_name, lambda obj: obj.object_data._info())
        cli.new_status_command(class_name,
                               lambda obj: obj.object_data._status())
        # register subclasses
        all_subs = []
        def do_register(xcls, up, mapper):
            if hasattr(xcls, "_getobj"):
                mapper = xcls._getobj
            else:
                xcls._getobj = mapper
            if up is not None:
                all_subs.append(xcls)
                xcls._up = up
                xcls._top = cls
            for sub in (getattr(xcls, k) for k in xcls._subs):
                do_register(sub, xcls, mapper)
        do_register(cls, None, None)

        def register_subs(xcls, xclass_name):
            if hasattr(xcls, "_classname"):
                xclass_name = xcls._classname
                if xclass_name is None and xcls._subs:
                    raise Exception('Subobject not allowed under %s' %
                                    cls.__name__)
            for sub in (getattr(xcls, k) for k in xcls._subs):
                sub._register(xclass_name)
                register_subs(sub, xclass_name)
        register_subs(cls, class_name)

    def _initialize(self):
        for o in self._all_subs:
            o._initialize()
    def _finalize(self):
        for o in self._all_subs:
            o._finalize()
    def _pre_delete(self):
        for o in self._all_subs:
            o._pre_delete()
    def _info(self): return []
    def _status(self): return []
    def __is_configured(self):
        return bool(simics.SIM_object_is_configured(self.obj))
    def __set_configured(self, is_configured):
        assert is_configured
        simics.SIM_set_object_configured(self.obj)
    _configured = property(__is_configured, __set_configured)
    # For forward compatibility, see bug 19735 comment 31
    @classmethod
    def register(cls):
        if not automatic_registration(cls):
            cls._register(cls.__name__)

    @classmethod
    def _getobj(cls, obj, sub_cls):
        return obj.object_data._omap[sub_cls]

    @classmethod
    def _obj_mapper(cls, obj):
        return obj.object_data._omap[cls]

class ClassExtension(ConfObject):
    '''Class Extension'''
    _class_kind = simics.Sim_Class_Kind_Extension
    _do_not_init = object()

    @classmethod
    def _getobj(cls, obj, sub_cls):
        return simics.SIM_extension_data(obj, cls.__name__)._omap[sub_cls]
