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


import base64
import abc

import simics
import cli
import connectors
from simicsutils.internal import ensure_text

import target_info
from . import (
    SystemPanelException, LayoutObject,
    BOOL_INPUT, BOOL_OUTPUT, NUMBER_INPUT, NUMBER_OUTPUT, NumberOutputKind,
)

# Layout description objects. They are used in the 'layout' class
# variable in system panel python objects to describe the layout.

__all__ = ['Led', 'Button', 'ToggleButton', 'NumberInput',
           'NumberOutput', 'Canvas', 'Container', 'Grid', 'Column', 'Row',
           'Empty', 'Label', 'LabeledBox', 'MultiImageOutput',
           'BitmapButton', 'BitmapToggleButton', 'BitmapLed', 'Image',
           'BLUE', 'GREEN', 'PURPLE', 'RED', 'WHITE', 'YELLOW',
           'Subpanel']

# <add id="system panel api">
# <name>Standard Widgets Colors</name>
# <doc>
#  <di name="NAME" label="Standard Widgets Colors">standard color names</di>
#  <di name="NAMESPACE"><tt>systempanel.widgets</tt></di>
#  <di name="DESCRIPTION">
#    The standard widgets colors are used for creating LED widgets with
#    different colors.
#  </di>
#  <di name="SYNOPSIS">
#    <pre size="small">systempanel.widgets.BLUE
#systempanel.widgets.GREEN
#systempanel.widgets.PURPLE
#systempanel.widgets.RED
#systempanel.widgets.WHITE
#systempanel.widgets.YELLOW
#    </pre>
#  </di>
#  <di name="SEE ALSO">systempanel.widgets.Led</di>
# </doc>
# </add>

builtin_colors = []

class Color:
    def __init__(self, name):
        self.name = name
        builtin_colors.append(self)

BLUE   = Color("blue")
GREEN  = Color("green")
PURPLE = Color("purple")
RED    = Color("red")
WHITE  = Color("white")
YELLOW = Color("yellow")

__simicsapi_doc_id__ = 'system panel api widgets'

def describe_tuple_type(obj):
    if isinstance(obj, tuple):
        return str(tuple(type(el).__name__ for el in obj))
    else:
        return type(obj).__name__

def typecheck_init_param(obj, param, value):
    """Helper to typecheck a LayoutObject constructor parameter based on
    its name"""
    param_types = {
        #'bit_count': int,
        'obj_name': str,
        'columns': int,
        'container': LayoutObject,
        'contents': list,
        'filename': str,
        'label': str,
        'name': str,
        'off_bitmap': str,
        'offset': int,
        'on_bitmap': str,
        }

    if not isinstance(value, param_types[param]):
        raise SystemPanelException(
            "'%s'(<%s>) is not a valid type for parameter %s in %s,"
            " type <%s> is expected"
            % (value, type(value).__name__,
               param, obj._type,
               param_types[param].__name__))

class InteractionObject(LayoutObject):
    @abc.abstractproperty
    def _kind(self): '''PanelObjectKind instance'''
    def __init__(self, obj_name):
        typecheck_init_param(self, 'obj_name', obj_name)
        self.obj_name = obj_name
        # self.object_name is set in .add_to_component
    def params(self, context):
        return [['oname', [context.state_manager().name, self.obj_name]]]
    def _objects(self):
        return [(self.obj_name, self._kind)]

class Led(
        InteractionObject,
        metaclass=cli.doc(
            'A standard LED',
            synopsis = 'Led(obj_name, color=None)',
            see_also = 'Standard Widgets Colors',
            metaclass = abc.ABCMeta)):
    '''A LED, which can be on or off. Driven by the <iface>signal</iface>
    interface. The parameter <param>color</param> specifies the color of
    the LED, all supported colors are described in <cite>Standard Widgets
    Colors</cite>. The look-and-feel of the LED is frontend specific.'''
    _type = "Led"
    _kind = BOOL_OUTPUT
    def __init__(self, obj_name, color=None):
        InteractionObject.__init__(self, obj_name)
        if color not in [None] + builtin_colors:
            raise SystemPanelException('Unsupported color')
        self.color = color
    def params(self, context):
        p = InteractionObject.params(self, context)
        if self.color:
            p.append(['color', self.color.name])
        return p

class Button(
        InteractionObject,
        metaclass=cli.doc(
            'A standard button',
            synopsis = 'Button(obj_name, label)',
            metaclass = abc.ABCMeta)):
    '''A button, that can be pressed. The button state is propagated using the
    <iface>signal</iface> interface, and can be raised or lowered. Raising and
    lowering the signal is frontend specific.'''
    _type = "Button"
    _kind = BOOL_INPUT

    def __init__(self, obj_name, label):
        typecheck_init_param(self, 'label', label)
        InteractionObject.__init__(self, obj_name)
        self.label = label
    def params(self, context):
        p = InteractionObject.params(self, context)
        p.append(['label', self.label])
        return p

class ToggleButton(
        Button,
        metaclass=cli.doc(
            'A toggle button',
            synopsis = 'ToggleButton(obj_name, label)',
            metaclass = abc.ABCMeta)):
    '''A toggle button, that can be pressed or released. The button state is
    propagated using the <iface>signal</iface> interface. When button is
    pressed, signal is raised. When button is released, signal is lowered. The
    button must have a label indicating its purpose.'''
    _type = "ToggleButton"

class NumberInput(
        InteractionObject,
        metaclass=cli.doc(
            'An input text field for integer numbers',
            synopsis = 'NumberInput(obj_name)',
            metaclass = abc.ABCMeta)):
    '''An input text field for integer numbers, provided by the panel user. The
    value is propagated to the model using the <iface>uint64_state</iface>
    interface.'''
    _type = "NumberInput"
    _kind = NUMBER_INPUT
    def __init__(self, obj_name):
        InteractionObject.__init__(self, obj_name)

class NumberOutput(
        InteractionObject,
        metaclass=cli.doc(
            'An output text field for integer numbers',
            synopsis = 'NumberOutput(obj_name)',
            metaclass = abc.ABCMeta)):
    '''An output text field for integer numbers, presenting integer state from
    the model. Driven by the <iface>uint64_state</iface> interface.'''
    _type = "NumberOutput"
    _kind = NUMBER_OUTPUT

#class MicroSwitches(InteractionObject):
#    _type = "MicroSwitches"
#    inout = INPUT
#    confclass = "system_panel_number_out"
#    def __init__(self, obj_name, bit_count, init=None):
#        InteractionObject.__init__(self, obj_name)
#        typecheck_init_param(self, 'initial_value', init)
#        self.init = init
#        self.bit_count = bit_count
#    def params(self):
#        p = InteractionObject.params(self)
#        p.append(['bit_count', self.bit_count])
#        return p
#    def add_to_component(self, panel):
#        conn = input_connector(self.confclass)
#        pobj = panel.add_panel_object(self.inout, self.obj_name,
#                                      self.confclass, conn,
#                                      number_state=self.init)
#        self.obj_name = pobj.component_slot

def read_bitmap_file(path):
    full_path = target_info.find_image(path)

    if not full_path:
        raise SystemPanelException("Cannot find file: %r" % (path,))

    try:
        with open(full_path, 'rb') as f:
            png_header = f.read(8)
            if png_header != b"\x89\x50\x4E\x47\x0D\x0A\x1A\x0A":
                raise SystemPanelException(
                    "File %r does not appear to be a valid PNG file"
                    % (full_path,))
            return png_header + f.read()
    except IOError as e:
        raise SystemPanelException("Error reading bitmap file: %s" % (e,))

class BitmapButton(
        InteractionObject,
        metaclass=cli.doc(
            'A bitmap-based button',
            synopsis = ('BitmapButton(obj_name, off_bitmap, on_bitmap)'),
            metaclass = abc.ABCMeta)):
    '''A bitmap-based button. Similar to the standard <class>Button</class>
    class, but can be put inside a <class>Canvas</class>, and the appearance is
    based on custom images. The bitmap parameters are filenames of the same
    type as in the <class>Image</class> class.'''
    _type = "BitmapButton"
    _kind = BOOL_INPUT
    def __init__(self, obj_name, offBitmap, onBitmap):
        typecheck_init_param(self, 'off_bitmap', offBitmap)
        typecheck_init_param(self, 'on_bitmap', onBitmap)
        InteractionObject.__init__(self, obj_name)
        self.images = [read_bitmap_file(f) for f in [offBitmap, onBitmap]]
    def params(self, context):
        p = InteractionObject.params(self, context)
        p.append(['offImage',
                  ['png', ensure_text(base64.b64encode(self.images[0]),
                                      encoding='ascii')]])
        p.append(['onImage',
                  ['png', ensure_text(base64.b64encode(self.images[1]),
                                      encoding='ascii')]])
        return p

class BitmapToggleButton(
        BitmapButton,
        metaclass=cli.doc(
            'A bitmap-based toggle button',
            synopsis = 'BitmapToggleButton(obj_name, off_bitmap, on_bitmap)',
            metaclass = abc.ABCMeta)):
    '''A bitmap-based toggle button. Similar to the standard
    <class>ToggleButton</class> class, but can be put inside a
    <class>Canvas</class>, and the appearance is based on custom images. The
    bitmap parameters are file names of the same type as in the
    <class>Image</class> class.'''
    _type = "BitmapToggleButton"
    _kind = BOOL_INPUT

class BitfieldImageOutput(
        InteractionObject,
        metaclass=cli.doc(
            'Multiple two-state image outputs driven by a single integer state',
            synopsis = 'BitfieldImageOutput(obj_name, contents)',
            metaclass = abc.ABCMeta)):
    '''An output consisting of multiple two-state images, driven by a
    single integer state. such that each two-state image is driven by
    a single bit in the integer.  Useful e.g. when creating 7-segment
    displays.

    The <param>contents</param> parameter is a list of tuples <tt>(mask, x, y,
    [off_filename, on_filename])</tt>, where the integer <tt>mask</tt> is a
    power of two, <tt>x</tt> and <tt>y</tt> are integer offsets, and
    <tt>off_filename</tt> and <tt>on_filename</tt> are file names given on the
    same form as in the <class>Image</class> class. The <tt>off_filename</tt>
    image is shown at the given offset whenever the bit indicated by
    <tt>mask</tt> is 0; <tt>on_filename</tt> is shown otherwise.'''
    _type = 'BitfieldImageOutput'
    # Don't impose any restrictions on the number range, a too
    # large number will just have an extra bit which will be
    # ignored, and nobody will be harmed.  Adding checks for
    # unused bits probably adds more complexity than it's worth.
    _kind = NUMBER_OUTPUT

    def __init__(self, obj_name, contents):
        InteractionObject.__init__(self, obj_name)
        if not isinstance(contents, list):
            raise SystemPanelException(
                'Expected contents to be list of (int, int, int,'
                ' ["off.png", "on.png"]), got %r' % (contents,))
        for element in contents:
            try:
                mask, x, y, files = element
                if (not all(isinstance(i, int) for i in [mask, x, y])
                    or not isinstance(files, list) or not all(isinstance(f, str)
                                                              for f in files)):
                    raise SystemPanelException()
            except (SystemPanelException, ValueError, TypeError):
                raise SystemPanelException(
                    "Bad element in parameter contents: Expected tuple"
                    " (int, int, int, [string, string]), got %r" % (element,))
            if (mask & (mask - 1)) or mask == 0:
                raise SystemPanelException(
                    "Invalid mask specification in parameter contents: Expected"
                    " power of two, got %d (0x%x)" % (mask, mask))

        self.contents = [
            [mask, x, y, [read_bitmap_file(filename) for filename in filenames]]
            for mask, x, y, filenames in contents]

    def params(self, context):
        p = InteractionObject.params(self, context)
        p.append(['contents',
                  [[mask, x, y,
                    [['png', ensure_text(base64.b64encode(image),
                                         encoding='ascii')]
                     for image in images]]
                   for mask, x, y, images in self.contents]])
        return p

class MultiImageOutput(
        InteractionObject,
        metaclass=cli.doc(
            'A bitmap-based output that toggles between multiple images',
            synopsis = 'MultiImageOutput(obj_name, images)',
            metaclass = abc.ABCMeta)):
    '''An output that toggles between multiple custom images.  This
    can be used, among other things, for multi-coloured LEDs or
    seven-segment display elements.  The <param>images</param>
    parameter is a list of paths to image filenames, each one given on
    the same form as in the <class>Image</class> class.  Numeric input
    to the panel object via the <iface>uint64_state</iface> interface
    is used as a 0-based index in the image list.'''
    _type = 'BitmapLed'
    @property
    def _kind(self):
        return NumberOutputKind(len(self.images))

    def __init__(self, obj_name, images):
        if (not isinstance(images, list)
            or any(not isinstance(i, str) for i in images)):
            raise SystemPanelException(
                'Expected list of strings in the images parameter, got %r'
                % (images,))
        super().__init__(obj_name)
        self.images = [read_bitmap_file(filename)
                       for filename in images]

    def params(self, context):
        p = InteractionObject.params(self, context)
        p.append(['images', [['png', ensure_text(base64.b64encode(img),
                                                 encoding='ascii')]
                             for img in self.images]])
        return p

class BitmapLed(
        MultiImageOutput,
        metaclass=cli.doc(
            'A bitmap-based LED',
            synopsis = 'BitmapLed(obj_name, off_bitmap, on_bitmap)',
            metaclass = abc.ABCMeta)):
    '''A bitmap-based LED. Same as the standard <class>Led</class> class, but
    can be put inside a <class>Canvas</class>, and custom images can be
    supplied.  The bitmap constructor parameters are file names of the same
    type as in the <class>Image</class> class.'''
    # This works by luck; bool and number have the same representation
    # when sent over TCF.
    _kind = BOOL_OUTPUT

    def __init__(self, obj_name, offBitmap, onBitmap):
        typecheck_init_param(self, 'off_bitmap', offBitmap)
        typecheck_init_param(self, 'on_bitmap', onBitmap)
        super().__init__(obj_name, [offBitmap, onBitmap])

class Image(
        LayoutObject,
        metaclass=cli.doc(
            'An image',
            synopsis = 'Image(filename)',
            metaclass = abc.ABCMeta)):
    '''An image, that can be put inside a <class>Canvas</class>
    class. Currently the only supported file format is PNG, but with full
    support for transparency. See <class>Canvas</class> class for more
    information.'''
    _type = 'Image'

    def __init__(self, filename):
        typecheck_init_param(self, 'filename', filename)
        self.contents = read_bitmap_file(filename)
    def params(self, context):
        return [['image',
                 ['png', ensure_text(base64.b64encode(self.contents),
                                     encoding='ascii')]]]

class Canvas(
        LayoutObject,
        metaclass=cli.doc(
            'A canvas (i.e bitmap container)',
            synopsis = 'Canvas(contents)',
            metaclass = abc.ABCMeta)):
    '''A canvas for painting bitmap-based widgets.  A canvas contains multiple
    bitmap-based widgets, each drawn at a specified offset.  The
    <param>contents</param> parameter is a list of elements on the form
    <param>(x, y, widget)</param>.  Here <param>x</param> and <param>y</param>
    are integers, and <param>widget</param> is an instance of one of
    <class>Image</class>, <class>BitmapLed</class>, <class>BitmapButton</class>,
    <class>BitmapToggleButton</class>,
    <class>MultiImageOutput</class>, <class>Canvas</class>, or a subclass
    thereof.  The items are rendered in the same order as they appear in the
    list; this means that if any widgets overlap, the last one will be drawn on
    top.'''
    _type = "Canvas"
    def __init__(self, contents):
        self.contents = []
        typecheck_init_param(self, 'contents', contents)
        for content in contents:
            try:
                (x, y, child) = content
            except (ValueError, TypeError):
                raise SystemPanelException(
                    "The format inside parameter contents of Canvas is"
                    " incorrect, expected tuple (int, int, LayoutObject),"
                    " got %s" % (describe_tuple_type(content),))
            if (not isinstance(x, int) or not isinstance(y, int)
                or not issubclass(type(child), LayoutObject)):
                raise SystemPanelException(
                    "'(%s, %s, %s)'(<%s, %s, %s>) is not a valid type"
                    " inside parameter contents in Canvas,"
                    " type <int, int, LayoutObject> is expected"
                    % (x, y, child, type(x).__name__,
                       type(y).__name__, type(child).__name__))
            self.contents += [[x, y, child]]
    def _objects(self):
        return (o for x, y, l in self.contents for o in l._objects())
    def params(self, context):
        return [['contents', [[x, y, b.as_attr(context)]
                              for (x, y, b) in self.contents]]]

class Container(LayoutObject):
    def __init__(self, contents):
        typecheck_init_param(self, 'contents', contents)
        self.contents = contents
    def _objects(self):
        return (o for l in self.contents for o in l._objects())

class Grid(
        Container,
        metaclass=cli.doc(
            'A two-dimensional widget container',
            synopsis = 'Grid(contents, columns)',
            metaclass = abc.ABCMeta)):
    '''A two-dimensional widget container.  Containers are used to group other
    widgets, and enforce a specific layout scheme.  The <param>contents</param>
    constructor parameter is a list of widget objects; it can contain any other
    widget except for bitmap-based ones.  Widgets are laid out from left to
    right, top to bottom. Use the <class>Empty</class> class to fill empty
    cells. The number of rows in a <class>Grid</class> container is implicitly
    defined by the length of the <param>contents</param> list and the number of
    columns specified when creating the container.  See also the
    <class>Column</class> and <class>Row</class> containers, which are
    convenience classes for the one-dimensional cases. Containers can contain
    other containers.'''
    _type = "GridContainer"
    def __init__(self, contents, columns):
        typecheck_init_param(self, 'contents', contents)
        for widgets in contents:
            if not issubclass(type(widgets), LayoutObject):
                raise SystemPanelException(
                    "'%s'(<%s>) is not a valid type inside parameter contents"
                    " in Grid, type <LayoutObject> is expected"
                    % (widgets, type(widgets).__name__))
        typecheck_init_param(self, 'columns', columns)
        self.contents = contents
        self.columns = columns
    def params(self, context):
        return [['columns', self.columns],
                ['contents', [b.as_attr(context) for b in self.contents]]]

class Column(
        Grid,
        metaclass=cli.doc(
            'A one-dimensional widget container',
            synopsis = 'Column(contents)',
            metaclass = abc.ABCMeta)):
    '''A container for normal (non bitmap-based) widgets. The
    <class>Column</class> container is a special case of <class>Grid</class>
    container; the contained widgets are laid out vertically.'''
    def __init__(self, contents):
        Grid.__init__(self, contents, 1)

class Row(
        Grid,
        metaclass=cli.doc(
            'A one-dimensional widget container',
            synopsis = 'Row(contents)',
            metaclass = abc.ABCMeta)):
    '''A container for normal (non bitmap-based) widgets. The
    <class>Row</class> container is a special case of <class>Grid</class>
    container; the contained widgets are laid out horizontally.'''
    def __init__(self, contents):
        Grid.__init__(self, contents, len(contents))

class Empty(
        LayoutObject,
        metaclass=cli.doc(
            'An empty widget',
            synopsis = 'Empty()',
            metaclass = abc.ABCMeta)):
    '''An empty widget, used to fill containers for layout purposes.'''
    _type = "Empty"
    def params(self, context):
        return []

class Label(
        LayoutObject,
        metaclass=cli.doc(
            'An label',
            synopsis = 'Label(label)',
            metaclass = abc.ABCMeta)):
    '''A label, used to present static text.'''
    _type = "Label"
    def __init__(self, label):
        typecheck_init_param(self, 'label', label)
        self.label = label
    def params(self, context):
        return [['label', self.label]]

class LabeledBox(
        LayoutObject,
        metaclass=cli.doc(
            'A container with a label and box drawn around it',
            synopsis = 'LabeledBox(label, container)',
            metaclass = abc.ABCMeta)):
    '''A single-element container with a text label and a box drawn around
    it. The single widget given by the <param>container</param> parameter can
    be of any widget type, but it is typically of a container type.'''
    _type = "LabeledBox"
    def __init__(self, label, container):
        typecheck_init_param(self, 'label', label)
        typecheck_init_param(self, 'container', container)
        self.label = label
        self.container = container
    def params(self, context):
        return [['label', self.label],
                ['container', self.container.as_attr(context)]]
    def _objects(self):
        return self.container._objects()

class Subpanel(LayoutObject):
    _type = "Subpanel"
    def __init__(self, name):
        typecheck_init_param(self, 'name', name)
        self.name = name
    def params(self, context):
        return [['slot', self.name]]
