# © 2024 Intel Corporation
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

from . import common

# Helper class for key/value properties of graph-specification which verifies
# the type, and checks that a property is not assigned twice.
class Property(abc.ABC):
    __slots__ = ('_key', '_value', '_assigned', '_default', '_property_type')

    def __init__(self, key, default=None):
        self._default = default
        self._value = default
        self._key = key
        self._assigned = False

    @property
    def assigned(self):
        return self._assigned

    def _name_for_prop_type(self):
        if isinstance(self._property_type, tuple):
            return " or ".join(
                sorted([p.__name__ for p in self._property_type]))
        return self._property_type.__name__

    def set(self, value):
        if self._assigned:
            raise common.GraphSpecException(
                f"{self._key} parameter already set")

        if self._property_type and (
                not isinstance(value, self._property_type)):
            raise common.GraphSpecException(
                f"{self._key} property must" +
                f" be {self._name_for_prop_type()}, got" +
                f" {type(value).__name__}"
            )

        self._value = value
        self._assigned = True

    def get(self):
        return self._value

    # Returns strings of the property documentation details
    def document(self):
        return common.PropDoc(
            self._key,
            self._name_for_prop_type(),
            self._default,
            self.valid_values(),
            self.desc())

    def valid_values(self):
        return None

    # Needs to be implemented in each property, returning a string
    # with the description of what the property do.
    @abc.abstractmethod
    def desc(self):
        pass

# Generic types which inherits from the Property class
class StrProp(Property):  __slots__ = (); _property_type = str
class BoolProp(Property): __slots__ = (); _property_type = bool
class IntProp(Property):  __slots__ = (); _property_type = int
class FloatProp(Property):  __slots__ = (); _property_type = float
class ListProp(Property): __slots__ = (); _property_type = list
class ListOrStrProp(Property): __slots__ = (); _property_type = (list, str)

# Properties with some additional checking
class StrSetProp(StrProp):
    __slots__ = ('_str_set')
    def set(self, value):
        # Validate that value is a string first
        super().set(value)
        if self._value not in self._str_set:
            self._value = None
            raise common.GraphSpecException(
                f"{self._key} parameter must be" +
                f" any of {self.valid_values}, got {value}")

    def valid_values(self):
        strings = sorted([f'"{s}"' for s in self._str_set])
        return ', '.join(strings)



#
# Actual properties used by the graph-specification
#


class TitleProp(StrProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name)

    def desc(self):
        return (
            "Mandatory. Specifies the main title of the graph. The title"
            " is also used to identification, if there is a problem"
            " in the json file.")

class XAxisTitleProp(StrProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name)

    def desc(self):
        return (
            "Optional. Specifies the title of the x-axis. If not supplied,"
            " the name will be taken from the x-probe's display-name."
            " For histogram-probes' the key-value pairs are unnamed"
            " so here the name can represent the key type.")

class YAxisTitleProp(StrProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name)

    def desc(self):
        return (
            "Optional. Specifies the title of the y-axis. If not supplied,"
            " the name will be taken from the first y-probe's display-name."
            " For histogram-probes' the key-value pairs are unnamed"
            " so here the name can represent value type.")

class GraphTypeProp(StrSetProp):
    _str_set = ('line', 'bar', 'pie')
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, 'line')

    def desc(self):
        return (
            "Optional. The type of graph that should be generated.")

class XProbeProp(StrProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, None)

    def set(self, value):
        super().set(value)
        if not ":" in self._value:
            raise common.GraphSpecException(
                f'property "{self._key}", missing ":" in probe-name'
                f' ("{self._value}")')

    def desc(self):
        return (
            "Optional. The probe data representing the X-axis values."
            " This is typically sim:sim.time.wallclock-session"
            " or sim:sim.time.virtual-session."
        )

class YProbesProp(ListOrStrProp):
    __slots__ = ('expanded_probes')
    def __init__(self, name):
        super().__init__(name, None)
        # List of ExpandedDataProbe after wildcard expansion
        self.expanded_probes = []

    def set(self, value):
        super().set(value)
        # Normalize the value
        self._value = self.parse_y_probes(value)
        for (probe_name, annotations) in self._value:
            if not ":" in probe_name:
                raise common.GraphSpecException(
                    f'property "{self._key}", missing ":" in probe-name'
                    f' ("{probe_name}")')
            for ann in annotations:
                if not ":" in ann:
                    raise common.GraphSpecException(
                        f'property "{self._key}", missing ":" in annotation'
                        f' probe-name ("{ann}")')


    def desc(self):
        return (
            'The probe(s) representing the data on the Y-axis, for the sampled'
            ' X-values.'
            'It can be specified in multiple ways:\n\n'
            '- "sim:sim.mips"  - The global MIPS data\n'
            '- "cpu0:cpu.mips" - The MIPS data for cpu0 only\n'
            '- "*:cpu.mips"    - All objects MIPS data each as its own graph\n'
            '\n'
            'Note, that the wildcard (*) syntax is only used for the complete'
            ' object, it is not possible to use it as a filter, with prefix or'
            ' suffix characters.'
            ' Multiple probes can also be specified as a single-list:\n\n'
            '- ["sim:sim.exec_mode.interpreter_percent",'
            '   "sim:sim.exec_mode.jit_percent",",'
            '   "sim:sim.exec_mode.vmp_percent"]\n'
            '\nHere three graphs would be shown, however if any prope'
            ' is missing this is silently ignored. If no probes are found'
            ' no chart will be generated.'
            ' It is also possible to add annotations to each graph:\n\n'
            '- ["sim:sim.mips", ["sim:sim.module_profile"]]\n\n'
            ' Annotation probes provides additional data shown when hovering'
            ' over a specific point in the graph.'
            'In this example, the module profile information is shown'
            ' when hovering over a data-point in the mips graph.\n'
            'Wildcard (*) is also handled in the annotation probes,'
            ' however if the probe assigned with annotations, the *-annotation'
            ' objects must match those in the original probe-object.'
        )

    # y-probes can be specified in multiple ways:
    # - probe
    # - [probes]
    # - [probe,[anotations,...]]
    # - [[probe, [anotations, ...]]]
    # Regardless of format, normalize the result as:
    #   [probe, [annotations]*]*
    def parse_y_probes(self, spec):
        # fisketur[syntax-error]
        match spec:
            case str(): # Single probe
                return [[spec, []]]
            case [*probes] if all([isinstance(e, str) for e in probes]):
                # List of probes
                return [[e,[]] for e in spec]
            case [str(), [*ann]] if all([isinstance(e, str) for e in ann]):
                # Probe with annotation-list
                return [[spec[0],spec[1]]]
            case [*complex]:
                return [self.parse_y_probes(s)[0] for s in complex]
            case _:
                # Invalid type detected
                raise common.GraphSpecException(spec)

    def wildcard_expand(self, session):
        for probe_name, annotation_list in self._value:
            (obj, kind) = probe_name.split(":")

            # Expand wildcard objects
            found_probes = session.get_object_probes_from_wildcard(obj, kind)
            for p in found_probes:
                (robj, _) = p.split(":")

                new_annotations = []
                for a in annotation_list:
                    (aobj, akind) = a.split(":")

                    if obj == "*" and aobj == "*":
                        ann_probes = session.get_object_probes_from_wildcard(
                            robj, akind)
                    else:
                        ann_probes = session.get_object_probes_from_wildcard(
                            aobj, akind)
                    new_annotations += ann_probes

                wildcard_obj = robj if obj == "*" else None
                n = common.ExpandedDataProbe(p, new_annotations, wildcard_obj)
                self.expanded_probes.append(n)


class HistogramProbeProp(StrProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, None)

    def set(self, value):
        super().set(value)
        if not ":" in value:
            raise common.GraphSpecException(
                f'property "{self._key}", missing ":" in probe-name'
                f' ("{self._value}")')

    def desc(self):
        return (
            'If a probe is of histogram type, it holds two datapoints:'
            ' key and value. Such a probe can be used to show a pie or'
            ' bar chart from the gathered final value. It can also be'
            ' used by looking at all samples and stack the bars on-top'
            ' of each-other. In this case the "x-probe" must also be'
            ' supplied.')

    def wildcard_expand(self, session):
        probe_name = self._value
        (obj, kind) = probe_name.split(":")
        return sorted(session.get_object_probes_from_wildcard(obj, kind))

class DescriptionProp(ListOrStrProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, "No description")

    def get(self):
        if isinstance(self._value, list):
            return " ".join(self._value)
        return self._value

    def desc(self):
        return "Optional. A textual description of what a graph represents."


class StackedProp(BoolProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, False)

    def desc(self):
        return (
            "If graph-data should be placed stacked on-top of each graph,"
            " instead as a separate line/bar."
        )

class HistogramDataSetProp(StrSetProp):
    _str_set = ('final', 'samples')
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, 'samples')

    def desc(self):
        return (
            "For histogram data, selects if the graph should be based on all"
            " the samples or just the final data in the end."
        )

class ArithMeanProp(BoolProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, False)

    def desc(self):
        return (
            "TODO re-implement"
        )

class PercentProp(BoolProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, False)

    def desc(self):
        return (
            "Show the Y-data in percent format."
        )

class YRangeProp(ListProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, None)

    def set(self, value):
        # Validate that value is a string first
        super().set(value)
        if len(value) != 2:
            raise common.GraphSpecException(
                f"{self._key} parameter must have two elements" +
                f", got {value}")
        if not all([isinstance(e, (int, float)) for e in value]):
            raise common.GraphSpecException(
                f"{self._key} parameter must contain numbers" +
                f", got {value}")
        if value[0] >= value[1]:
            raise common.GraphSpecException(
                f"{self._key} min-value greater or equal to max-value" +
                f", got {value}")

    def desc(self):
        return (
            "The range shown on the y-axis by default."
            " If not specified, this will be automatic from the actual"
            " y-values given."
        )


class MinDataSeriesProp(IntProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, None)

    def desc(self):
        return (
            "The minimum number of data-series to draw, for the the"
            " graph be shown."
        )

class CutoffProp(FloatProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, 0.0)

    def set(self, value):
        # Validate that value is a string first
        super().set(value)
        if value > 100.0 or value < 0.0:
            raise common.GraphSpecException(
                f"{self._key} parameter be between 0 and 100," +
                f" got {value}")

    def desc(self):
        return (
            "Reduce the number of data-series by putting all series"
            " that totals in less than the cutoff% value in a special"
            " cutoff-bucket"
        )

class MaxDataSeriesProp(IntProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, None)

    def desc(self):
        return (
            "The minimum number of data-series to draw, for the the"
            " graph be shown."
        )

class MultiGraphProp(BoolProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, False)

    def desc(self):
        return (
            "Generate a separate graph for each object."
        )

class MinGraphsProp(IntProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, None)

    def desc(self):
        return (
            "With multi-graph, the minimum graphs that must be generated"
            " or all of these graphs are skipped."
        )

class MaxGraphsProp(IntProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, None)

    def desc(self):
        return (
            "With multi-graph, the maximum number of graphs that may generated"
            " or all of these graphs are skipped."
        )


class HtmlPageProp(StrProp):
    __slots__ = ()
    def __init__(self, name):
        super().__init__(name, "index.html")

    def desc(self):
        return (
            "The name of the html-page where this graph should be included"
            " if not set, defaults to 'index.html'"
        )

def unit_test_yprobes():
    # The y_probes property supports many ways to express the
    # probe with possible annotations.
    # Check that the various way to express it still resolves
    # to a normalized representation.
    def expect_norm_val(value, expected):
        yp = YProbesProp('name')
        yp.set(value)
        assert yp._value == expected

    expect_norm_val(
        value="*:foo",
        expected=[
            ["*:foo", []]
        ])

    expect_norm_val(
        value=["sim:foo", "*:bar"],
        expected=[
            ['sim:foo', []],
            ['*:bar', []]
        ])

    expect_norm_val(
        value=["*:foo", ["*:ann1"]],
        expected=[
            ["*:foo", ["*:ann1"]]
        ])

    expect_norm_val(
        value=[["*:foo", ["sim:ann1"]], ["*:bar", ["sim:ann2"]]],
        expected=[
            ["*:foo", ["sim:ann1"]],
            ["*:bar", ["sim:ann2"]]
        ])

    expect_norm_val(
        value=[["sim:foo", ["sim:ann1", "sim:sann1"]],
               ["sim:bar", ["sim:ann2"]]],
        expected=[
            ["sim:foo", ["sim:ann1", "sim:sann1"]],
            ["sim:bar", ["sim:ann2"]]
        ])

    expect_norm_val(
        value=[["sim:foo"], ["sim:bar", ["sim:ann2"]]],
        expected=[
            ["sim:foo", []],
            ["sim:bar", ["sim:ann2"]]
        ])


unit_test_yprobes()
