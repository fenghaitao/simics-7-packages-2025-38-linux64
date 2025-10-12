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


from abc import ABC, abstractmethod
import table
import math

# Helper classes part of the Probe class for handling the type specific
# conversions of the values.

class ProbeValueException(Exception):
    pass


class ProbeType(ABC):
    __slots__ = ()

    @classmethod
    @abstractmethod
    def valid_value(cls, value):
        '''Must be implemented in the subclass.  Returns True if the valid is
        in the correct representation for the probe type, otherwise False.'''

    @classmethod
    @abstractmethod
    def neutral_value(cls):
        '''Must be implemented in the subclass.  Returns a "zero" start value
        to diff from.  Can be 0, [], [0,0] depending of type.'''

    @classmethod
    @abstractmethod
    def raw_value(cls, value, cell_formatter=None):
        '''Must be implemented in the subclass.  Returns a representation of
        the value as shown in the 'raw' format of the commands. That
        is, it is fine to return the scalar value as is. But for
        complex types, a string that explains the contents should be
        used.'''

    @classmethod
    @abstractmethod
    def table_cell_value(cls, value, cell_formatter=None):
        '''Must be implemented in the subclass.  Returns the value suitable
        for insertion in a Simics table, valid types are int, float,
        string, bool, but not any kind of lists. For example, a
        fraction list [a,b] will return the calculation of a/b.'''

    @classmethod
    @abstractmethod
    def value_as_fraction(cls, value):
        '''Must be implemented in the subclass. Returns a value as fraction.
        Used for generic fraction calculation of two numbers.  For
        scalar number a, the list [a,1] is returned.  May raise
        ProbeValueException for types not suitable for doing fraction
        calculation on them.'''

    @classmethod
    @abstractmethod
    def sorting_support(cls):
        '''Must be implemented in the subclass. Returns True if
           sorted() can apply, False otherwise.'''

    @classmethod
    @abstractmethod
    def sorted(cls, value):
        '''Must be implemented in the subclass. Returns a sorted
        representation of a probe value. Typically only used for
        histograms. Other types trigger an assertion.'''

    @classmethod
    @abstractmethod
    def delta_support(cls):
        '''Must be implemented in the subclass. Returns True if the
        diff_values() can be made, False otherwise.'''

    @classmethod
    @abstractmethod
    def diff_values(cls, a, b):
        '''Must be implemented in the subclass. Returns the difference
        of two probe values a - b.'''

    @classmethod
    def scaler_sum(cls, values):
        return sum(values)

    @classmethod
    def scaler_min(cls, values):
        return min(values)

    @classmethod
    def scaler_max(cls, values):
        return max(values)

    @classmethod
    def scaler_object_histogram(cls, obj_values):
        return [[o.name, v] for (o, v) in obj_values]

    @classmethod
    def scaler_class_histogram(cls, obj_values):
        h = {}
        for (o, v) in obj_values:
            cls_str = f"<{o.classname}>"
            h.setdefault(cls_str, 0)
            h[cls_str] += v
        return [[k, h[k]] for k in h]

class IntValue(ProbeType):
    __slots__ = ()

    @classmethod
    def valid_value(cls, value):
        return isinstance(value, int)

    @classmethod
    def neutral_value(cls):
        return 0

    @classmethod
    def raw_value(cls, value, cell_formatter=None):
        if not cls.valid_value(value):
            return "invalid int:" + repr(value)
        return value

    @classmethod
    def table_cell_value(cls, value, cell_formatter=None):
        if not cls.valid_value(value):
            return "invalid int:" + repr(value)
        return value

    @classmethod
    def value_as_fraction(cls, value):
        if not cls.valid_value(value):
            raise ProbeValueException("not an integer")
        return [value, 1]

    @classmethod
    def sorting_support(cls):
        return False

    @classmethod
    def sorted(cls, value):
        assert 0

    @classmethod
    def delta_support(cls):
        return True

    @classmethod
    def diff_values(cls, a, b):
        return a - b

    @classmethod
    def int_arith_mean(cls, values):
        return sum(values) // len(values)

    @classmethod
    def int_median(cls, values):
        l = len(values)
        s = sorted(values)
        if (l % 2) == 0:
            return (s[l // 2 - 1] + s[l // 2]) // 2
        else:
            return s[l // 2]

class Int128Value(ProbeType):
    __slots__ = ()

    @classmethod
    def _python_to_int128_attr(cls, v):
        mask = (1 << 64) - 1
        return [(v >> 64) & mask, v & mask]

    @classmethod
    def _int128_attr_to_python(cls, v):
        if (v[0] >> 63) == 1:
            return ((v[0] << 64) | v[1]) - (2 ** 128) # negative
        return (v[0] << 64) | v[1]

    @classmethod
    def valid_value(cls, value):
        return (isinstance(value, list) and len(value) == 2
                and isinstance(value[0], int)
                and isinstance(value[1], int))

    @classmethod
    def neutral_value(cls):
        return [0, 0]

    @classmethod
    def raw_value(cls, value, cell_formatter=None):
        if not cls.valid_value(value):
            return "invalid int128:" + repr(value)
        s = cls._int128_attr_to_python(value)
        return f"[{value[0]}, {value[1]}]\n= {s}"

    @classmethod
    def table_cell_value(cls, value, cell_formatter=None):
        if not cls.valid_value(value):
            return "invalid int128:" + repr(value)
        return cls._int128_attr_to_python(value)

    @classmethod
    def value_as_fraction(cls, value):
        if not cls.valid_value(value):
            raise ProbeValueException("not an int128")
        return [cls._128_array_to_python(value), 1]

    @classmethod
    def sorting_support(cls):
        return False

    @classmethod
    def sorted(cls, value):
        assert 0

    @classmethod
    def delta_support(cls):
        return True

    @classmethod
    def diff_values(cls, a, b):
        d = (Int128Value._int128_attr_to_python(a)
             - Int128Value._int128_attr_to_python(b))
        return cls._python_to_int128_attr(d)

    @classmethod
    def int128_sum(cls, values):
        s = sum([cls._int128_attr_to_python(x) for x in values])
        return cls._python_to_int128_attr(s)

    @classmethod
    def int128_min(cls, values):
        vs = [cls._int128_attr_to_python(v) for v in values]
        max_int128 = cls._int128_attr_to_python([ (1 << 63) - 1, (1 << 64) - 1])
        mi = max_int128
        for v in vs:
            if v < mi:
                mi = v
        return cls._python_to_int128_attr(mi)

    @classmethod
    def int128_max(cls, values):
        vs = [cls._int128_attr_to_python(v) for v in values]
        min_int128 = cls._int128_attr_to_python([ (1 << 63), 0])
        ma = min_int128
        for v in vs:
            if v > ma:
                ma = v
        return cls._python_to_int128_attr(ma)

    @classmethod
    def int128_arith_mean(cls, values):
        values = [cls._int128_attr_to_python(v) for v in values]
        l = len(values)
        mean = sum(values) // l
        return cls._python_to_int128_attr(mean)

    @classmethod
    def int128_median(cls, values):
        values = [cls._int128_attr_to_python(v) for v in values]
        l = len(values)
        s = sorted(values)
        if (l % 2) == 0:
            median = (s[l // 2 - 1] + s[l // 2]) // 2
        else:
            median = s[l // 2]
        return cls._python_to_int128_attr(median)


class FloatValue(ProbeType):
    __slots__ = ()

    @classmethod
    def valid_value(cls, value):
        return isinstance(value, (int, float))

    @classmethod
    def neutral_value(cls):
        return 0.0

    @classmethod
    def raw_value(cls, value, cell_formatter=None):
        if not cls.valid_value(value):
            return "invalid float:" + repr(value)
        return float(value)

    @classmethod
    def table_cell_value(cls, value, cell_formatter=None):
        if not cls.valid_value(value):
            return "invalid float:" + repr(value)
        return float(value)

    @classmethod
    def value_as_fraction(cls, value):
        if not cls.valid_value(value):
            raise ProbeValueException("not a float")
        return [value, 1]

    @classmethod
    def sorting_support(cls):
        return False

    @classmethod
    def sorted(cls, value):
        assert 0

    @classmethod
    def delta_support(cls):
        return True

    @classmethod
    def diff_values(cls, a, b):
        return a - b

    @classmethod
    def float_arith_mean(cls, values):
        return sum(values) / len(values)

    @classmethod
    def float_median(cls, values):
        l = len(values)
        s = sorted(values)
        if (l % 2) == 0:
            return (s[l // 2 - 1] + s[l // 2]) / 2
        else:
            return s[l // 2]

class FractionValue(ProbeType):
    __slots__ = ()

    @classmethod
    def valid_value(cls, value):
        return (isinstance(value, list)
                and len(value) == 2
                and isinstance(value[0], (int, float))
                and isinstance(value[1], (int, float)))

    @classmethod
    def neutral_value(cls):
        return [0,0]

    @classmethod
    def raw_value(cls, value, cell_formatter=None):
        if not cls.valid_value(value):
            return "invalid fraction:" + repr(value)

        decimals = cell_formatter.float_decimals if cell_formatter else None
        if decimals == None:
            decimals = 2

        if value[1]:
            res = float(value[0] / value[1])
            s = (f"{res:.{decimals}e} ({res:.{decimals}f})")
        else:
            s = "inf"
        return f"{value[0]:.{decimals}e} / {value[1]:.{decimals}e}\n= {s}"

    @classmethod
    def table_cell_value(cls, value, cell_formatter=None):
        if not cls.valid_value(value):
            return "invalid fraction:" + repr(value)

        if value[1]:
            return float(value[0] / value[1])
        return "-"

    @classmethod
    def value_as_fraction(cls, value):
        if not cls.valid_value(value):
            raise ProbeValueException("not a fraction")
        return value            # already a fraction

    @classmethod
    def sorting_support(cls):
        return False

    @classmethod
    def sorted(cls, value):
        assert 0

    @classmethod
    def delta_support(cls):
        return True

    @classmethod
    def diff_values(cls, a, b):
        return [a[0] - b[0], a[1] - b[1]]

    # Special fraction aggregators

    @classmethod
    def fraction_sum(cls, values):
        has_floats = False
        for n, d in values:
            if isinstance(n, float) or isinstance(d, float):
                has_floats = True
            if d == 0:
                return [0, 0]   # Give up on division-by-zero

        if has_floats:
            return [sum([float(n) / float(d) for (n, d) in values]), 1.0]

        # All integers
        numerator = 0
        denominator = 1
        for (n, d) in values:
            numerator = numerator * d + n * denominator
            denominator = d * denominator
            g = math.gcd(numerator, denominator)
            numerator = numerator // g
            denominator = denominator // g
        return [numerator, denominator]

    @classmethod
    def fraction_min(cls, values):
        mi = None
        mif = None

        for (n, d) in values:
            if d == 0:
                return [0, 0]
            f = float(n) / float(d)
            if mi == None or f < mi:
                mi = f
                mif = [n, d]
        return mif

    @classmethod
    def fraction_max(cls, values):
        ma = None
        maf = None

        for (n, d) in values:
            if d == 0:
                return [0, 0]
            f = float(n) / float(d)
            if ma == None or f > ma:
                ma = f
                maf = [n, d]
        return maf

    @classmethod
    def fraction_arith_mean(cls, values):
        [n, d] = cls.fraction_sum(values)
        return [n, d * len(values)]

    @classmethod
    def fraction_weighted_mean(cls, values):
        sum = [0, 0]
        for (n, d) in values:
            sum[0] += n
            sum[1] += d
        return sum

class HistogramValue(ProbeType):
    __slots__ = ()

    # Convert a key-value list to a table, and return the multi-line
    # string representation.
    @classmethod
    def _histogram_to_cell(cls, kv_data, cell_formatter):
        def default_widths():
            percent_col_width = 4   # "100%" max-value
            if cell_formatter and cell_formatter.total_width:
                # Remove two from both columns to account for the borderless
                # separator (2 characters), 4 characters
                w = cell_formatter.total_width - percent_col_width - 4
                if w < 0:
                    return (20, 10, percent_col_width)

                part = w // 4
                rest = w % 4
                return (part * 3 + rest, # key: 3/4 of the remaining width
                        part,            # val: 1/4
                        percent_col_width)
            else:
                return (25, 10, percent_col_width)

        if kv_data == []:
            return ""

        cf = cell_formatter
        max_lines = cf.max_lines if cf else None
        key_col_width = cf.key_col_width if cf else None
        val_col_width = cf.val_col_width if cf else None
        ignore_column_widths = cf.ignore_column_widths if cf else False

        (default_key_width,
         default_val_width,
         percent_col_width) = default_widths()

        if key_col_width == None:
            key_col_width = default_key_width
        if val_col_width == None:
            val_col_width = default_val_width

        data = [(k,v) for (k,v) in kv_data if v > 0] # Remove zero value data
        if data == []:
            return ""
        if max_lines != None and len(data) > max_lines:
            rm = sum([v for (k,v) in kv_data[max_lines:]])
            data = data[:max_lines]   # Truncate the data
            data.append(("...", rm))  # Add how many we don't present

        # Add a percent column
        total =  sum([v for (k,v) in data])
        tbl_data = []
        for (k, v) in data:
            percent = int((100.0 * v / total) + 0.5)
            tbl_data.append((k, v, f"{percent:3d}%"))

        properties = [(table.Table_Key_Columns, [
            [(table.Column_Key_Width, key_col_width)],
            [(table.Column_Key_Width, val_col_width),
             (table.Column_Key_Int_Radix, 10)],
            [(table.Column_Key_Width, percent_col_width)]]
        )]
        tbl = table.Table(properties, tbl_data)

        return tbl.to_string(
            border_style="borderless",
            no_row_column=True,
            ignore_column_widths=ignore_column_widths,
            rows_printed=0)

    @classmethod
    def valid_value(cls, value):
        if not isinstance(value, list):
            return False

        for e in value:
            if (len(e) != 2
                or not isinstance(e[0], str)
                or not isinstance(e[1], (int, float))):
                return False
        return True

    @classmethod
    def neutral_value(cls):
        return []

    @classmethod
    def raw_value(cls, value, cell_formatter=None):
        if not cls.valid_value(value):
            return "invalid histogram:" + repr(value)

        max_lines = cell_formatter.max_lines if cell_formatter else None
        value.sort(key=lambda kv: kv[1], reverse=True)
        s = ",\n".join([repr(v) for v in value[:max_lines]])
        if max_lines and max_lines < len(value):
            s += ",\n..."

        return f"[{s}]"

    @classmethod
    def table_cell_value(cls, value, cell_formatter=None):
        if not cls.valid_value(value):
            return "invalid histogram:" + repr(value)
        return cls._histogram_to_cell(value, cell_formatter)

    @classmethod
    def value_as_fraction(cls, value):
        raise ProbeValueException("cannot convert histogram to fraction")

    @classmethod
    def sorting_support(cls):
        return True

    @classmethod
    def sorted(cls, value):
        return sorted(value, key=lambda kv: kv[1], reverse=True)

    @classmethod
    def delta_support(cls):
        return True

    @classmethod
    def diff_values(cls, a, b): # a (current) - b (previous)
        d = dict(a)
        for (k, v) in b:
            diff = d.get(k, 0) - v
            if diff:
                d[k] = diff
            else:
                del d[k] # Remove dict entries with zero values
        return cls.sorted(d.items())

    @classmethod
    def histogram_max_widths(cls, value, lines=None):
        '''Return the max width for keys and values in a specific
        probe. Cut the histogram after lines number of lines.
        None, means unlimited.'''

        def value_len(v):
            if isinstance(v[1], int):
                return len(str(v[1]))
            else:
                return len(f"{v[1]:.2f}")

        if value == [] or lines == 0:
            return [0,0]

        value.sort(key=lambda kv: kv[1], reverse=True)
        max_key = max(map(lambda t: len(t[0]), value[:lines]))
        max_val = max(map(value_len, value[:lines]))
        return (max_key, max_val)

    @classmethod
    def histogram_sum(cls, values):
        sum = dict()
        for histogram in values:
            for k, v in histogram:
                sum.setdefault(k, 0)
                sum[k] += v
        sum = [[k, v] for (k, v) in sum.items()]
        return cls.sorted(sum)


class StringValue(ProbeType):
    __slots__ = ()

    @classmethod
    def valid_value(cls, value):
        return isinstance(value, str)

    @classmethod
    def neutral_value(cls):
        return ""

    @classmethod
    def raw_value(cls, value, cell_formatter=None):
        if not cls.valid_value(value):
            return "invalid string:" + repr(value)
        return value

    @classmethod
    def table_cell_value(cls, value, cell_formatter=None):
        if not cls.valid_value(value):
            return "invalid string:" + repr(value)
        return value

    @classmethod
    def value_as_fraction(cls, value):
        raise ProbeValueException("Cannot convert string to fraction")

    @classmethod
    def sorting_support(cls):
        return False

    @classmethod
    def sorted(cls, value):
        assert 0

    @classmethod
    def aggregate_values(cls, values, function):
        raise ProbeValueException("Cannot aggregate strings")

    @classmethod
    def delta_support(cls):
        return False

    @classmethod
    def diff_values(cls, a, b):
        raise ProbeValueException("Cannot diff strings")

probe_type_to_class = {
    "int"       : IntValue,
    "float"     : FloatValue,
    "fraction"  : FractionValue,
    "histogram" : HistogramValue,
    "int128"    : Int128Value,
    "string"    : StringValue,
}

# Used by AttributeProbeFactory
attr_type_to_probe_type = {
    "i": "int",
    "f": "float",
    "b": "int",
    "s": "string"
}

defined_aggregator_functions = [
    "sum",
    "min",
    "max",
    "arith-mean",
    "weighted-arith-mean",
    "median",
    "object-histogram",
    "class-histogram",
]

aggregator_descriptions = {
    "sum" : "All probe values are summed together.",
    "min" : ("The lowest value among the probe values is returned."
             " For fraction-probes, if any denominator contains a zero value,"
             " the calculated sum returned is [0, 0]."),
    "max" : "The highest value among probe values is returned.",
    "arith-mean" : "The arithmetic mean is calculated for all the probe values.",
    "weighted-arith-mean" : """
        The denominators are used as weights.
        Using these weights implies that the weighted arithmetic mean can be
        calculated by adding all numerators and denominators, producing a new
        fraction of these sums.
        For example, when calculating the mean instruction per cycles (IPC)
        on all processors (where the IPC per processor is represented as a
        fraction: instructions / cycles).
        With two processors having [20/30] and [40/50], the total IPC
        becomes [(20+40)/(30+50)] or [60/80] and the IPC value of 0.75.""",
    "median" : "The median among the probe values is returned.",
    "object-histogram" : ("A histogram probe is created using the"
                          " probe-owner-objects as key"
                          " and their probe-values value."),
    "class-histogram" : (
        "Similar to the object-histogram, but here the histogram"
        " uses the classname of the owner-object as key, and the"
        " value is the sum of the probe-values with the same class.")
}

NotSupported = None

function_map = {
    "int" : {
        "sum" : ProbeType.scaler_sum,
        "min" : ProbeType.scaler_min,
        "max" : ProbeType.scaler_max,
        "arith-mean" : IntValue.int_arith_mean,
        "weighted-arith-mean" : NotSupported,
        "median" : IntValue.int_median,
        "object-histogram": ProbeType.scaler_object_histogram,
        "class-histogram": ProbeType.scaler_class_histogram,
    },
    "float": {
        "sum" : ProbeType.scaler_sum,
        "min" : ProbeType.scaler_min,
        "max" : ProbeType.scaler_max,
        "arith-mean" : FloatValue.float_arith_mean,
        "weighted-arith-mean" : NotSupported,
        "median" : FloatValue.float_median,
        "object-histogram": ProbeType.scaler_object_histogram,
        "class-histogram": ProbeType.scaler_class_histogram,
    },
    "fraction" : {
        "sum": FractionValue.fraction_sum,
        "min" : FractionValue.fraction_min,
        "max" : FractionValue.fraction_max,
        "arith-mean" : FractionValue.fraction_arith_mean,
        "weighted-arith-mean": FractionValue.fraction_weighted_mean,
        "median" : NotSupported,
        "object-histogram": NotSupported,
        "class-histogram": NotSupported,
    },
    "histogram" : {
        "sum" : HistogramValue.histogram_sum,
        "min" : NotSupported,
        "max" : NotSupported,
        "arith-mean" : NotSupported,
        "weighted-arith-mean": NotSupported,
        "median" : NotSupported,
        "object-histogram": NotSupported,
        "class-histogram": NotSupported,
    },
    "int128" : {
        "sum": Int128Value.int128_sum,
        "min" : Int128Value.int128_min,
        "max" : Int128Value.int128_max,
        "arith-mean" : Int128Value.int128_arith_mean,
        "weighted-arith-mean": NotSupported,
        "median" : Int128Value.int128_median,
        "object-histogram": NotSupported,
        "class-histogram": NotSupported,
    },
    "string" : {
        "sum" : NotSupported,
        "min" : NotSupported,
        "max" : NotSupported,
        "arith-mean" : NotSupported,
        "weighted-arith-mean": NotSupported,
        "median" : NotSupported,
        "object-histogram": NotSupported,
        "class-histogram": NotSupported,
    },
}

def simple_values(proxy_probes):
    return [p.value() for p in proxy_probes]

# For class-histogram, it is up to the implementation to sort the
# object values into different class buckets.
def object_values(proxy_probes):
    return [[p.prop.owner_obj, p.value()] for p in proxy_probes]

# What each aggregates function expects as argument
value_map = {
    "sum" :                simple_values, # List of the probe values
    "min" :                simple_values,
    "max" :                simple_values,
    "arith-mean" :         simple_values,
    "weighted-arith-mean": simple_values,
    "median" :             simple_values,
    "object-histogram":    object_values, # List of (object, values)
    "class-histogram":     object_values,
}


# Helper functions to extract possible configurations for the probes
def get_value_class(ptype):
    return probe_type_to_class[ptype]

def get_supported_probe_types():
    return set(probe_type_to_class.keys())

def get_supported_aggregator_functions():
    return defined_aggregator_functions

def supports_aggregate_function(ptype, function_string):
    return function_map[ptype][function_string] != NotSupported

def get_aggregate_function(ptype, function_string):
    return function_map[ptype][function_string]

def get_aggregate_value_map_function(function_string):
    return value_map[function_string]

# Test that concrete classes implements all needed abstract method
# We need to create instances of the classes to find these
for key in probe_type_to_class:
    probe_type_to_class[key]()
