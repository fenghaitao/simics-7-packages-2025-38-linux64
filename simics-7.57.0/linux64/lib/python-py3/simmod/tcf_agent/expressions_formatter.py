# © 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


# This file decodes expressions from debugger API into formatter classes that
# can output the data formatted for the sym-* commands or symdebug interface.

import cli
import sys
import itertools
import simics

class TypeFormatter:
    parent = None
    child = None
    formatter_name = None

    def sym_type_formatter(self):
        raise NotImplementedError('formatter not implemented')

    def expr_type_formatter(self):
        raise NotImplementedError('expr_type not implemented')

    def set_child(self, child):
        self.child = child
        if child:
            child.parent = self

    def get_child_of_type(self, searched_type):
        c = self.child
        while c:
            if isinstance(c, searched_type):
                return c
            c = c.child
        return None

    def _get_ptr_child(self):
        return self.get_child_of_type(PointerTypeFormatter)

    def is_pointer(self):
        if isinstance(self, PointerTypeFormatter):
            return True
        return self._get_ptr_child() is not None


class BasicTypeFormatter(TypeFormatter):
    formatter_name = 'basic'
    def __init__(self, expr_type):
        self.expr_type = expr_type

    def sym_type_formatter(self):
        return self.expr_type

    def expr_type_formatter(self):
        return self.expr_type


class UnknownTypeFormatter(TypeFormatter):
    formatter_name = 'unknown'
    def __init__(self, expr_type):
        self.expr_type = expr_type

    def sym_type_formatter(self):
        if isinstance(self.expr_type, list):
            return '??'
        return str(self.expr_type)

    def expr_type_formatter(self):
        return self.expr_type


class PointerTypeFormatter(TypeFormatter):
    formatter_name = 'pointer'
    def __init__(self, child):
        self.set_child(child)

    def _child_is_function(self):
        return isinstance(self.child, FunctionTypeFormatter)

    def get_class_child(self):
        return self.get_child_of_type(ClassTypeFormatter)

    def sym_type_formatter(self):
        if self._child_is_function():
            return self.child.sym_type_formatter()
        return self.child.sym_type_formatter() + ' *'

    def expr_type_formatter(self):
        return ['*', self.child.expr_type_formatter()]


class FunctionTypeFormatter(TypeFormatter):
    formatter_name = 'function'
    def __init__(self, func_type, args):
        self.func_type = func_type
        assert isinstance(args, list)
        self.args = args

    def sym_type_formatter(self):
        formatted_args = ', '.join([a.sym_type_formatter() for a in self.args])
        return f'{self.func_type.sym_type_formatter()} (*)({formatted_args})'

    def expr_type_formatter(self):
        return ['()', self.func_type.expr_type_formatter(),
                [a.expr_type_formatter() for a in self.args]]


class ArrayTypeFormatter(TypeFormatter):
    formatter_name = 'array'
    def __init__(self, array_type, size):
        assert isinstance(array_type, TypeFormatter)
        assert isinstance(size, int)
        self.array_type = array_type
        self.size = size

    def get_type(self):
        return self.array_type

    def sym_type_formatter(self):
        return f'{self.array_type.sym_type_formatter()}[{self.size}]'

    def expr_type_formatter(self):
        return ['[]', self.size, self.array_type.expr_type_formatter()]


class QualifierFormatter(TypeFormatter):
    formatter_name = 'qualifier'
    def __init__(self, child, qualifier):
        self.set_child(child)
        self.qualifier = qualifier

    def sym_type_formatter(self):
        ptr_child = self._get_ptr_child()
        if ptr_child and not ptr_child.get_class_child():
            # e.g. char * const
            return f'{self.child.sym_type_formatter()} {self.qualifier}'
        # e.g. const char *
        return f'{self.qualifier} {self.child.sym_type_formatter()}'

    def expr_type_formatter(self):
        return [self.qualifier, self.child.expr_type_formatter()]


class EnumTypeFormatter(TypeFormatter):
    formatter_name = 'enum'
    def __init__(self, enum_name, members):
        self.enum_name = enum_name
        self.members = members

    def sym_type_formatter(self):
        if self.enum_name is None:
            return 'enum'
        return f'enum {self.enum_name}'

    def expr_type_formatter(self):
        if self.enum_name is None:
            return ['enum']
        return ['enum', self.enum_name]


class ContainerTypeFormatter(TypeFormatter):
    container_type = None
    def __init__(self, container_name, members=[]):
        assert self.container_type, "container_type must be set"
        self.container_name = container_name
        self.members = members

    def sym_type_formatter(self):
        res = f'{self.container_type}'
        if self.container_name:
            res += f' {self.container_name}'
        return res

    def expr_type_formatter(self):
        res = [self.container_type]
        if self.container_name is not None:
            res.append(self.container_name)
        return res

class StructTypeFormatter(ContainerTypeFormatter):
    formatter_name = 'struct'
    container_type = 'struct'


class UnionTypeFormatter(ContainerTypeFormatter):
    formatter_name = 'union'
    container_type = 'union'


class ClassTypeFormatter(ContainerTypeFormatter):
    formatter_name = 'class'
    container_type = 'class'
    def __init__(self, container_name):
        assert isinstance(container_name, str)
        super().__init__(container_name, None)


class TypedefFormatter(TypeFormatter):
    formatter_name = 'typedef'
    def __init__(self, typedef_name):
        assert isinstance(typedef_name, str)
        self.typedef_name = typedef_name

    def sym_type_formatter(self):
        return self.typedef_name

    def expr_type_formatter(self):
        return ['typedef', self.typedef_name]


class BitfieldTypeFormatter(TypeFormatter):
    formatter_name = 'bitfield'
    def __init__(self, base_type, bits):
        assert isinstance(base_type, TypeFormatter)
        assert isinstance(bits, int)
        self.base_type = base_type
        self.bits = bits

    def sym_type_formatter(self):
        return f'{self.base_type.sym_type_formatter()}'

    def expr_type_formatter(self):
        # No bitfield handling in expr_type
        return self.base_type.expr_type_formatter()

def max_string_length():
    return 20

def is_qualifier(kind):
    return kind in ('const', 'volatile', 'restrict')

def is_char_type(type_formatter):
    if isinstance(type_formatter, BasicTypeFormatter):
        basic_type = type_formatter
    else:
        # Pointer to char is not a char type
        if type_formatter.get_child_of_type(PointerTypeFormatter) is not None:
            return False
        basic_type = type_formatter.get_child_of_type(BasicTypeFormatter)
    if not basic_type:
        return False
    return basic_type.sym_type_formatter() == 'char'


class ValueFormatter:
    formatter_name = None

    def formatted_value(self):
        raise NotImplementedError('formatter_value not implemented')

    def expr_value_formatter(self):
        raise NotImplementedError('expr_value_formatter not implemented')


class IntValueFormatter(ValueFormatter):
    formatter_name = 'int value'
    def __init__(self, value):
        assert isinstance(value, int)
        self.value = value

    def sym_value_formatter(self):
        return cli.number_str(self.value)

    def expr_value_formatter(self):
        return self.value


class FloatValueFormatter(ValueFormatter):
    formatter_name = 'float value'
    def __init__(self, value):
        assert isinstance(value, float)
        self.value = value

    def sym_value_formatter(self):
        return str(self.value)

    def expr_value_formatter(self):
        return self.value


class PointerValueFormatter(ValueFormatter):
    formatter_name = 'pointer value'
    def __init__(self, string_read_fun, type_formatter, value):
        assert isinstance(value, int)
        assert isinstance(type_formatter, TypeFormatter)
        assert type_formatter.is_pointer()
        self.type_formatter = type_formatter
        self.value = value
        self.string_read_fun = string_read_fun

    def _read_string(self):
        assert self.value is not None
        if self.value == 0:
            return '<NULL pointer>'
        (ok, string) = self.string_read_fun(self.value)
        if not ok:
            return '<cannot read memory>'
        # Limit "preview" of string pointed to by char [const] * to max 20
        # characters.
        max_len = max_string_length()
        if len(string) > max_len:
            string = string[:max_len - 2] + ".."
        return cli.format_attribute(string, True)

    def _is_pointer_to_char_type(self):
        return is_char_type(self.type_formatter)

    def sym_value_formatter(self):
        if self._is_pointer_to_char_type():
            extra_data = f' {self._read_string()}'
        else:
            extra_data = ''
        return (f'({self.type_formatter.sym_type_formatter()}) 0x{self.value:x}'
                f'{extra_data}')

    def expr_value_formatter(self):
        type_format = self.type_formatter.expr_type_formatter()
        assert isinstance(type_format, list)
        return type_format + [self.value]


class CharValueFormatter(IntValueFormatter):
    formatter_name = 'char value'
    def chr_value(self):
        rep = "%r" % bytes((abs(self.value),))
        # Remove initial 'b'
        return rep[1:]

    def get_numeric_value(self):
        return self.value

    def sym_value_formatter(self):
        return f'{super().sym_value_formatter()} {self.chr_value()}'

    def expr_value_formatter(self):
        return ['c', self.value]


class ArrayValueFormatter(ValueFormatter):
    formatter_name = 'array value'
    def __init__(self, type_formatter, elems):
        assert isinstance(type_formatter, TypeFormatter)
        self.type_formatter = type_formatter
        self.elems = elems

    # Given a list of strings, replace runs of repeated values with either one
    # instance and a repeat count, or all the instances comma-separated,
    # whichever is shortest.
    def _rle(self, strings):
        def r(s, n):
            a = ", ".join(s for i in range(n))
            b = "%s <repeats %d times>" % (s, n)
            return a if len(a) < len(b) else b
        return [r(x, len(list(elems))) for (x, elems)
                in itertools.groupby(strings)]

    def _is_char_array(self):
        return (len(self.elems) > 0
                and isinstance(self.elems[0], CharValueFormatter))

    def _format_chars_as_string(self):
        char_array = [chr(abs(c.get_numeric_value())) for c in self.elems]
        return ''.join(char_array)

    def sym_value_formatter(self):
        if self._is_char_array():
            return cli.format_attribute(self._format_chars_as_string())

        formatted_elems = [e.sym_value_formatter() for e in self.elems]
        elems_str = ', '.join(self._rle(formatted_elems))
        return (f'({self.type_formatter.sym_type_formatter()})'
                + '{' + f'{elems_str}' + '}')

    def expr_value_formatter(self):
        return ['[]', self.type_formatter.get_type().expr_type_formatter(),
                [e.expr_value_formatter() for e in self.elems]]


class StructValueFormatter(ValueFormatter):
    formatter_name = 'struct value'
    def __init__(self, elems):
        assert isinstance(elems, list)
        for e in elems:  # Should be [name, element value]
            assert isinstance(e, list) and len(e) == 2
        self.elems = elems

    def sym_value_formatter(self):
        formatted_elems = []
        for (name, val) in self.elems:
            name_str = f'{name} = ' if name else ''
            elem = f'{name_str}{val.sym_value_formatter()}'
            formatted_elems.append(elem)
        return '{' + ', '.join(formatted_elems) + '}'

    def expr_value_formatter(self):
        return ['{}', [[n or '', v.expr_value_formatter()]
                       for (n, v) in self.elems]]


class EnumValueFormatter(ValueFormatter):
    formatter_name = 'enum value'
    def __init__(self, name, num):
        self.name = name
        self.num = num

    def sym_value_formatter(self):
        if self.name is None:
            return cli.number_str(self.num)
        return self.name

    def expr_value_formatter(self):
        if self.name:
            return ['enum', self.name, self.num]
        return ['enum', self.num]


class BitfieldValueFormatter(IntValueFormatter):
    formatter_name = 'bitfield value'


class UnknownValueFormatter(ValueFormatter):
    formatter_name = 'unknown value'
    def __init__(self, value):
        self.value = value

    def sym_value_formatter(self):
        return repr(self.value)

    def expr_value_formatter(self):
        return self.value


def decode_type_from_api(t):
    if isinstance(t, (int, str, float)):
        return BasicTypeFormatter(t)
    if not isinstance(t, list):
        return UnknownTypeFormatter(t)
    kind = t[0]
    if kind == '*':
        return PointerTypeFormatter(decode_type_from_api(t[1]))
    if kind == '()':
        func_type = decode_type_from_api(t[1])
        args = [decode_type_from_api(a) for a in t[2]]
        return FunctionTypeFormatter(func_type, args)
    if kind == '[]':
        array_size = t[1]
        array_type = decode_type_from_api(t[2])
        return ArrayTypeFormatter(array_type, array_size)
    if is_qualifier(kind):
        return QualifierFormatter(decode_type_from_api(t[1]), kind)
    if kind == 'bitfield':
        return BitfieldTypeFormatter(decode_type_from_api(t[1]), t[2])
    if kind == 'enum':
        if len(t) == 2:
            # Anonymous enum
            name = None
            members = t[1]
        else:
            assert len(t) == 3
            name = t[1]
            members = t[2]
        return EnumTypeFormatter(name, members)
    struct_formatters = {'struct': StructTypeFormatter,
                         'union': UnionTypeFormatter}
    if kind in struct_formatters:
        name = t[1] if len(t) > 1 and isinstance(t[1], str) else None
        members = t[-1] if isinstance(t[-1], list) else []
        return struct_formatters[kind](name, members)
    composite_formatters = {'class': ClassTypeFormatter,
                            'typedef': TypedefFormatter}
    if kind in composite_formatters:
        name = t[1] if len(t) > 1 and isinstance(t[1], str) else None
        return composite_formatters[kind](name)
    return UnknownTypeFormatter(t)

def is_unknown_type(t):
    return isinstance(t, UnknownTypeFormatter)

def is_api_char_type(formatter_type, e_val):
    if not isinstance(formatter_type, BasicTypeFormatter):
        return False
    if not isinstance(e_val, int):
        return False
    if e_val < -128 or e_val > 255:
        return False
    e_type = formatter_type.expr_type
    if 'char' in e_type:
        return True
    return e_type.endswith('int8') or e_type.endswith('int8_t')

def api_read_string(ctx_id, addr, max_size):
    debugger = simics.SIM_get_debugger()
    (err, string) = debugger.iface.debug_symbol.address_string(
        ctx_id, addr, max_size)
    return (err == simics.Debugger_No_Error, string)

def decode_value_from_type_formatter(ctx_id, type_formatter, e_val):
    if isinstance(type_formatter, BasicTypeFormatter):
        if isinstance(e_val, int):
            if is_api_char_type(type_formatter, e_val):
                return CharValueFormatter(e_val)
            return IntValueFormatter(e_val)

        if isinstance(e_val, float):
            return FloatValueFormatter(e_val)

        return UnknownValueFormatter(e_val)

    if type_formatter.is_pointer():
        return PointerValueFormatter(
            lambda addr: api_read_string(ctx_id, addr, max_string_length() + 1),
            type_formatter, e_val)
    if isinstance(type_formatter, BitfieldTypeFormatter):
        return BitfieldValueFormatter(e_val)
    if isinstance(type_formatter, EnumTypeFormatter):
        named = [n for (n, v) in type_formatter.members if v == e_val]
        name = named[0] if named else None
        return EnumValueFormatter(name, e_val)
    if isinstance(type_formatter, ArrayTypeFormatter):
        elem_formatter = type_formatter.get_type()
        assert type_formatter.size == len(e_val)
        elems_res = [decode_value_from_type_formatter(ctx_id, elem_formatter,
                                                      e_val[i])
                     for i in range(type_formatter.size)]
        return ArrayValueFormatter(type_formatter, elems_res)
    if isinstance(type_formatter, (StructTypeFormatter, UnionTypeFormatter)):
        elems_res = []
        assert len(type_formatter.members) == len(e_val)
        for (i, (elem_type, elem_name)) in enumerate(type_formatter.members):
            elem_formatted = decode_value_from_api(ctx_id, elem_type, e_val[i])
            elems_res.append([elem_name, elem_formatted])
        return StructValueFormatter(elems_res)
    if isinstance(type_formatter, QualifierFormatter):
        # Qualifier types in output are only included for types already handled
        # above. That is why currently the value formatter of the child is used.
        return decode_value_from_type_formatter(ctx_id, type_formatter.child,
                                                e_val)
    if isinstance(type_formatter, TypedefFormatter):
        base_type = find_base_type(ctx_id, type_formatter.typedef_name)
        if base_type:
            return decode_value_from_api(ctx_id, base_type, e_val)
        return UnknownValueFormatter(e_val)
    # Function type should always be pointed to.
    assert not isinstance(type_formatter, FunctionTypeFormatter)
    # Values for class types are not supported and returned as unknown.
    return UnknownValueFormatter(e_val)

def decode_value_from_api(ctx_id, e_type, e_val):
    if isinstance(e_type, list) and len(e_type) > 1 and e_type[0] == '()':
        # In debugger API function pointers do not explicity have a '*' to mark
        # that they are pointers, in expr_type they do.
        e_type = ['*', e_type]
    return decode_value_from_type_formatter(
        ctx_id, decode_type_from_api(e_type), e_val)

def is_unknown_value(v):
    return (isinstance(v, UnknownValueFormatter)
            or not isinstance(v, ValueFormatter))

def find_base_type(ctx_id, type_name):
    debugger = simics.SIM_get_debugger()
    (err, e_type) = debugger.iface.debug_symbol.type_info(ctx_id, 0, type_name)
    if err != simics.Debugger_No_Error:
        return None
    return e_type
