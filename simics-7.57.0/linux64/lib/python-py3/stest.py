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


# <add id="stest">
# <name>stest</name>
# Utilities for testing simics.
# </add>


import os, os.path
import traceback
import unittest
import simics
from simics import *
from cli import (
    arg,
    get_completions,
    new_command,
    str_t,
)
import sim_commands
import contextlib
import pprint
import conf
import re

__all__ = ('TestFailure', 'fail', 'collect_failures', 'check_failures',
           'trap_log', 'untrap_log',
           'expect_true', 'expect_false', 'expect_equal',
           'expect_different', 'expect_log', 'expect_log_mgr',
           'expect_exception', 'expect_exception_mgr',
           'log_file', 'scratch_file', 'deprecation_level')

# exceptions

# <add id="stest.TestFailure">
# Exception class used to signal failures in Simics tests.
#
# Use the <fun>fail</fun> function instead of raising this exception yourself.
# </add>
class TestFailure(Exception):
    pass

collecting_failures = False
failures = []

# <add id="stest.collect_failures">
# Change the behavior of stest to collect failures instead of terminating on
# the first failure detected.
#
# If you use this you have to call <fun>check_failures</fun> at the end of
# your test script to check if it signaled any failures.
# </add>
def collect_failures():
    global collecting_failures
    collecting_failures = True

# <add id="stest.check_failures">
# Check if any failures have occurred and leave collect failures mode.
#
# If any failures have occurred this function will report the failures and
# raise a <class>TestFailure</class> exception.
# If called outside collect failures mode this function will fail.
# </add>
def check_failures():
    global collecting_failures
    if not collecting_failures:
        raise TestFailure("not collecting failures")
    collecting_failures = False
    if failures:
        print("The following failures occurred:\n", pprint.pformat(failures))
        raise TestFailure("%d failures" % len(failures))

# <add id="stest.fail">
# Signal a failure in a test.
#
# Takes a string describing the failure as its single argument.
# If called in collect failures mode this will collect the failure for later
# checking with <fun>check_failures</fun>. If called outside collect failures
# mode it will immediately raise a <class>TestFailure</class> exception
# instead.
# </add>
def fail(msg):
    if collecting_failures:
        traceback.print_stack()
        print("*** FAILURE", msg)
        failures.append(msg)
    else:
        raise TestFailure(msg)

# Log message trapping

class LogTrapper:
    def __init__(self):
        self.trappers = {}

    def callback(self, arg, obj, logtype, msg):
        pass

    def resolve(self, logtype):
        alltypes = conf.sim.log_types
        if logtype in alltypes:
            idx = alltypes.index(logtype)
        else:
            raise Exception("Unknown log type: %r" % logtype)
        return logtype, idx

    def trapped_log_types(self):
        return [x[1] for x in self.trappers]

    def enable(self, logtype, obj = None):
        logtype, idx = self.resolve(logtype)
        if (obj, logtype) in self.trappers:
            return
        if obj:
            self.trappers[(obj, logtype)] = SIM_hap_add_callback_obj_index(
                "Core_Log_Message", obj, 0, self.callback, idx, idx)
        else:
            self.trappers[(obj, logtype)] = SIM_hap_add_callback_index(
                "Core_Log_Message", self.callback, idx, idx)

    def disable(self, logtype, obj = None):
        logtype, idx = self.resolve(logtype)
        if not (obj, logtype) in self.trappers:
            return
        SIM_hap_delete_callback_id("Core_Log_Message",
                                   self.trappers[(obj, logtype)])
        del self.trappers[(obj, logtype)]
        if logtype == "error":
            conf.sim.stop_on_error = False

class LogTrapperFail(LogTrapper):
    def __init__(self):
        LogTrapper.__init__(self)
        self.filter = []

    def callback(self, arg, obj, logtype, msg):
        assert logtype == arg  # sanity check
        if ((obj, logtype) not in self.filter
            and (None, logtype) not in self.filter):
            fail("Trap on %s log: %s %s"
                 % (conf.sim.log_types[logtype], obj, msg))

    def currently_filtered(self, obj = None, logtype = "error"):
        (logtype, idx) = self.resolve(logtype)
        return (obj, idx) in self.filter

    def add_filter(self, obj = None, logtype = "error"):
        (logtype, idx) = self.resolve(logtype)
        self.filter.append((obj, idx))

    def discard_filter(self, obj = None, logtype = "error"):
        (logtype, idx) = self.resolve(logtype)
        self.filter.remove((obj, idx))

    def disable(self, logtype, obj = None):
        LogTrapper.disable(self, logtype, obj)
        if obj and not self.currently_filtered(obj, logtype):
            self.add_filter(obj, logtype)
            if logtype == "error":
                conf.sim.stop_on_error = False

    def enable(self, logtype, obj = None):
        LogTrapper.enable(self, logtype, obj)
        if obj and self.currently_filtered(obj, logtype):
            self.discard_filter(obj, logtype)

trapper = LogTrapperFail()

# <add id="stest.trapped_log_types">
# Returns the log types currently trapped.
# </add>
trapped_log_types = trapper.trapped_log_types

# <add id="stest.trap_log">
# Configure Simics to trap a type of log messages, and cause Simics
# to quit with a test failure on any such log message.
#
# By default the stest trap 'error' and 'spec-viol' log messages.
#
# <fun>trap_log</fun> without an object sets the default handling for the
# given log type. Object specific settings always take precedence over
# the default handling.
#
# Arguments:
# <dl>
# <dt>logtype</dt>
# <dd>the type of log messages to trap, one of 'info', 'error', 'undef',
#     'spec-viol', and 'unimpl'</dd>
# <dt>obj</dt>
# <dd>the configuration object whose log messages to trap, defaults to None,
#     which means that all log messages of the right type are trapped</dd>
# </dl>
# </add>
def trap_log(logtype, obj = None):
    trapper.enable(logtype, obj)

# <add id="stest.untrap_log">
# Explicitly allow messages of a given log type. Can be used to undo
# a previous <fun>trap_log</fun> or to filter objects from a default
# trap.
#
# <fun>untrap_log</fun> without an object sets the default behavior for the
# given log type. Object specific settings always take precedence over
# the default handling.
#
# Arguments:
# <dl>
# <dt>logtype</dt>
# <dd>the type of log messages to untrap, one of 'info', 'error', 'undef',
#     'spec-viol', and 'unimpl'</dd>
# <dt>obj</dt>
# <dd>the configuration object whose log messages to untrap, defaults to None,
#     which means that all log messages of the right type are untrapped</dd>
# </dl>
# </add>
def untrap_log(logtype, obj = None):
    trapper.disable(logtype, obj)

def log_type_expander(string):
    return get_completions(string, conf.sim.log_types)


new_command("trap-log", trap_log,
            [arg(str_t, "log-type", "?", "", expander=log_type_expander)],
            short="trap on log type",
            doc="trap on log type <arg>log-type</arg>")

new_command("untrap-log", untrap_log,
            [arg(str_t, "log-type", "?", "", expander=log_type_expander)],
            short="untrap on log type",
            doc="untrap on log type <arg>log-type</arg>")

# Enable trapping by default
trap_log("error")
trap_log("spec-viol")


# Expectations

# <add id="stest.expect_true">
# Check if a condition is true and cause a test failure if it is not.
#
# Arguments:
# <dl>
# <dt>cond</dt>
# <dd>the condition to test</dd>
# <dt>msg</dt>
# <dd>a message explaining the failure</dd>
# </dl>
# </add>
def expect_true(cond, msg = "expectation failed"):
    if not cond:
        fail(msg)

# <add id="stest.expect_false">
# Check if a condition is false and cause a test failure if it is not.
#
# Arguments:
# <dl>
# <dt>cond</dt>
# <dd>the condition to test</dd>
# <dt>msg</dt>
# <dd>a message explaining the failure</dd>
# </dl>
# </add>
def expect_false(cond, msg = "expectation failed"):
    if cond:
        fail(msg)

def _represent(item):
    def has_int(item):
        if isinstance(item, int):
            return True
        elif isinstance(item, (list, tuple)):
            return any(has_int(i) for i in item)
        else:
            return False
    def rep(item, use_hex):
        if isinstance(item, int):
            return ("0x%x" if use_hex else "%d") % (item,)
        elif isinstance(item, list):
            return "[" + ", ".join(rep(i, use_hex) for i in item) + "]"
        elif isinstance(item, tuple):
            return "(" + ", ".join(rep(i, use_hex) for i in item) + (
                ",)" if len(item) == 1 else ")")
        else:
            return repr(item)
    if has_int(item):
        return rep(item, False) + " = " + rep(item, True)
    elif isinstance(item, dict):
        return "{%s}" % (", ".join("%r: %s" % (k, _represent(v))
                                   for (k, v) in sorted(item.items())))
    else:
        return rep(item, False)

class TestRepresent(unittest.TestCase):
    def test_represent(self):
        self.assertEqual(_represent(10), "10 = 0xa")
        self.assertEqual(_represent([(0, 1), 2]),
                         "[(0, 1), 2] = [(0x0, 0x1), 0x2]")
        self.assertEqual(_represent((0.0, 1)), "(0.0, 1) = (0.0, 0x1)")
        self.assertEqual(_represent("foo"), "'foo'")
        self.assertEqual(_represent((None,)), "(None,)")

# <add id="stest.expect_equal">
# Checks if a value is equal to an expectation and cause a test failure if it
# is not.
#
# Arguments:
# <dl>
# <dt>got</dt>
# <dd>the value to check</dd>
# <dt>expected</dt>
# <dd>what to compare the value with</dd>
# <dt>msg</dt>
# <dd>a message explaining the failure</dd>
# </dl>
# </add>
def expect_equal(got, expected, msg = "expectation failed"):
    if got != expected:
        print("Expected", _represent(expected))
        print("Got     ", _represent(got))
        fail(msg)

# <add id="stest.expect_different">
# Checks if a value is different to an expectation and cause a test failure if
# it is not.
#
# Arguments:
# <dl>
# <dt>got</dt>
# <dd>the value to check</dd>
# <dt>unexpected</dt>
# <dd>what to compare the value with</dd>
# <dt>msg</dt>
# <dd>a message explaining the failure</dd>
# </dl>
# </add>
def expect_different(got, unexpected, msg = "expectation failed"):
    if got == unexpected:
        print("Expected values to differ: ", _represent(got))
        fail(msg)

@contextlib.contextmanager
def allow_log_mgr(obj = None, log_type = "error"):
    restore_fatal_errors = conf.sim.stop_on_error
    if log_type == "error" or log_type == "critical":
        conf.sim.stop_on_error = False

    trapper.add_filter(obj, log_type)
    try:
        yield
    finally:
        trapper.discard_filter(obj, log_type)
        if log_type == "error" or log_type == "critical":
            conf.sim.stop_on_error = restore_fatal_errors

def call_allowing_log(fun, obj = None, log_type = "error"):
    with allow_log_mgr(obj, log_type):
        fun()


class _set_log_level(contextlib.AbstractContextManager):
    def __init__(self, level, obj=None):
        if obj is None:
            objlist = simics.SIM_object_iterator(None)
        elif isinstance(obj, simics.conf_object_t):
            objlist = [obj]
        else:
            objlist = obj
        self.level = level
        self.restore = {o: o.log_level for o in objlist}
        for o in self.restore:
            if not isinstance(o, simics.conf_object_t):
                raise Exception(f"Not a conf_object_t: {o}")

    def __enter__(self):
        for o in self.restore:
            # avoid deleted objects
            if isinstance(o, simics.conf_object_t):
                o.log_level = self.level
        return self

    def __exit__(self, *exc):
        for o, lvl in self.restore.items():
            # avoid deleted objects
            if isinstance(o, simics.conf_object_t):
                o.log_level = lvl
        return False

class TestUntrapLog(unittest.TestCase):
    def local_fail(self, msg):
        self.received_msgs.append(msg)

    def setUp(self):
        global fail
        self.received_msgs = []
        self.o = []
        for i in range(3):
            self.o.append(SIM_create_object('namespace', f'o{i}'))
        self.stest_fail = fail
        fail = self.local_fail

    def tearDown(self):
        global fail
        simics.SIM_delete_objects(self.o)
        fail = self.stest_fail


    def test_untrap_log(self):
        trap_log('info', self.o[1])

        self.received_msgs.clear()
        SIM_log_info(1, self.o[0], 0, "Should not trap!")
        self.assertEqual(len(self.received_msgs), 0)

        self.received_msgs.clear()
        SIM_log_info(1, self.o[1], 0, "Trap me!")
        self.assertEqual(len(self.received_msgs), 1)
        self.assertEqual(self.received_msgs[0],
                            "Trap on info log: <the namespace 'o1'> Trap me!")

        untrap_log('error', self.o[2])

        self.received_msgs.clear()
        SIM_log_error(self.o[0], 0, "Should trap!")
        self.assertEqual(len(self.received_msgs), 1)
        self.assertEqual(self.received_msgs[0],
                            "Trap on error log: <the namespace 'o0'> Should trap!")

        self.received_msgs.clear()
        SIM_log_error(self.o[2], 0, "Should not trap!")
        self.assertEqual(len(self.received_msgs), 0)

        trap_log('error', self.o[2])

        self.received_msgs.clear()
        SIM_log_error(self.o[2], 0, "Should trap now!")
        # we will get two fails in a row, because we have the non-object global
        # callback and the object specific callback
        self.assertEqual(len(self.received_msgs), 2)
        self.assertEqual(self.received_msgs[0],
                            "Trap on error log: <the namespace 'o2'> Should trap now!")
        self.assertEqual(self.received_msgs[1],
                            "Trap on error log: <the namespace 'o2'> Should trap now!")

        untrap_log('info', self.o[1])

        self.received_msgs.clear()
        SIM_log_info(1, self.o[1], 0, "Should no longer trap!")
        self.assertEqual(len(self.received_msgs), 0)



class TestSetLogLevel(unittest.TestCase):
    def setUp(self):
        cls = simics.SIM_create_class('foo321', simics.class_info_t())
        simics.SIM_register_simple_port(cls, 'bank.regs', None)
        simics.SIM_register_simple_port(cls, 'port.foo', None)
        self.obj = simics.SIM_create_object(cls, 'dut')

    def tearDown(self):
        simics.SIM_delete_object(self.obj)

    def assertLogLevels(self, expected):
        actual = {o: o.log_level for o in simics.SIM_object_iterator(None)}
        self.assertEqual(expected, actual)

    def test_set_log_level(self):
        original = {o: simics.SIM_log_level(o)
                    for o in simics.SIM_object_iterator(None)}

        with _set_log_level(3, [self.obj, self.obj.bank.regs]):
            expected = dict(original)
            expected.update({self.obj: 3, self.obj.bank.regs: 3})
            self.assertLogLevels(expected)
        self.assertLogLevels(original)

        with _set_log_level(2):
            expected = {o: 2 for o in simics.SIM_object_iterator(None)}
            self.assertLogLevels(expected)
        self.assertLogLevels(original)

        cm = _set_log_level(4, self.obj)
        self.assertLogLevels(original)
        with cm:
            expected = dict(original)
            expected[self.obj] = 4
            self.obj.bank.regs.log_level = 4  # should not be changed on exit
            expected[self.obj.bank.regs] = 4
            self.assertLogLevels(expected)
        original[self.obj.bank.regs] = 4
        self.assertLogLevels(original)

        with cm:  # context can be reused
            expected[self.obj] = 4
            self.assertLogLevels(expected)
        self.assertLogLevels(original)

        # handles objects being deleted before enter and exit
        cm = _set_log_level(1)
        simics.SIM_delete_object(self.obj.port.foo)
        with cm:
            simics.SIM_delete_object(self.obj.bank.regs)


# <add id="stest.expect_log_mgr">
# Context manager, verifying that, on exit from the with-statement, a
# particular log message has been emitted.
# Arguments:
# <dl>
# <dt>obj</dt>
# <dd>optional object from which a log is expected,
#     default is None which accepts any object</dd>
# <dt>log_type</dt>
# <dd>optional log type which the emitted log must belong to,
#     one of "error" (default), "unimpl", "info", "spec-viol"
#     or "undefined"</dd>
# <dt>msg</dt>
# <dd>optional message emitted on failure</dd>
# <dt>regex</dt>
# <dd>optional regular expression object or a string
#     containing a regular expression suitable for use by
#     <tt>re.search()</tt>, which the emitted log must match
# </dd>
# <dt>with_log_level</dt>
# <dd>optional log level to apply inside the context</dd>
# </dl>
# Example usage:
# <pre>
#with stest.expect_log_mgr(log_type="spec-viol",
#                          msg="Check warning on read-only fields"):
#    reg_compute_units.write(0xffff_ffff_ffff_ffff)
# </pre>
# </add>
@contextlib.contextmanager
def expect_log_mgr(obj=None, log_type="error", msg=None, regex='',
                   with_log_level=None):
    with allow_log_mgr(obj, log_type):
        captured = []

        def callback(_obj, _log_type, _msg):
            if ((obj is None or _obj == obj)
                    and log_type == conf.sim.log_types[_log_type]
                    and re.search(regex, _msg)):
                captured.append((_obj, _msg))
            return False
        with sim_commands.logger.filter(callback):
            if with_log_level is None:
                yield
            else:
                with _set_log_level(with_log_level, obj):
                    yield
        if len(captured) == 0:
            if not msg:
                msg = f"Expected log of {log_type} type"
                if regex:
                    msg += f" matching {regex!r}"
            fail(msg)


# <add id="stest.expect_log">
# Call a function and verify that a particular log message is emitted.
# Returns the called function's return value.
# Arguments:
# <dl>
# <dt>fun</dt>
# <dd>the function to be called</dd>
# <dt>args</dt>
# <dd>the arguments with which to call <arg>fun</arg></dd>
# All other arguments are identical to <fun>expect_log_mgr</fun>
# </dl>
# </add>
def expect_log(fun, args=[], obj=None, log_type="error", msg=None, regex='',
               with_log_level=None):
    with expect_log_mgr(obj, log_type, msg, regex, with_log_level):
        return fun(*args)

class TestExpectLog(unittest.TestCase):
    def test_expect_log(self):
        for obj in [conf.sim, conf.prefs, None]:
            for fun in [SIM_log_info, SIM_log_unimplemented]:
                for level in 1, 2:
                    expect_success = (
                        level < 2 and fun == SIM_log_info
                        and obj != conf.prefs)
                    try:
                        expect_log(fun, (level, conf.sim, 0, "msg"),
                                   obj = obj,
                                   log_type = "info")
                    except TestFailure:
                        success = False
                    else:
                        success = True
                    self.assertEqual(success, expect_success)

        fem = conf.sim.stop_on_error
        try:
            conf.sim.stop_on_error = True
            expect_log(lambda: SIM_log_error(conf.sim, 0, "err"))
        finally:
            conf.sim.stop_on_error = fem

    def test_expect_regex(self):
        with self.assertRaisesRegex(TestFailure, 'cow'):
            with expect_log_mgr(conf.sim, 'error', regex='cow'):
                simics.SIM_log_error(conf.sim, 0, 'a sheep goes baah')
        with expect_log_mgr(conf.sim, 'error', regex='cow'):
            simics.SIM_log_error(conf.sim, 0, 'a cow goes moo')

        regex = re.compile('cow')
        with self.assertRaisesRegex(TestFailure, 'cow'):
            with expect_log_mgr(conf.sim, 'error', regex=regex):
                simics.SIM_log_error(conf.sim, 0, 'a regex sheep goes baah')
        with expect_log_mgr(conf.sim, 'error', regex=regex):
            simics.SIM_log_error(conf.sim, 0, 'a regex cow goes moo')

        regex = 'cow.*moo$'
        with self.assertRaisesRegex(TestFailure, 'cow'):
            with expect_log_mgr(conf.sim, 'error', regex=regex):
                simics.SIM_log_error(conf.sim, 0, 'a regex cow goes moo!')
        with expect_log_mgr(conf.sim, 'error', regex=regex):
            simics.SIM_log_error(conf.sim, 0, 'a regex cow goes moo')


    def test_nested(self):
        with allow_log_mgr(conf.sim, 'error'):
            with expect_log_mgr(conf.sim, 'error'):
                SIM_log_error(conf.sim, 0, "err")
            SIM_log_error(conf.sim, 0, "err")

    def test_expect_log_level(self):
        with self.assertRaisesRegex(TestFailure, 'log of spec-viol'):
            with expect_log_mgr(conf.sim, 'spec-viol'):
                simics.SIM_log_spec_violation(3, conf.sim, 0, 'viol3')
        with expect_log_mgr(conf.sim, 'spec-viol', with_log_level=3):
            simics.SIM_log_spec_violation(3, conf.sim, 0, 'viol3')
        expect_log(simics.SIM_log_spec_violation, [3, conf.sim, 0, 'viol3'],
                   conf.sim, 'spec-viol', with_log_level=3)

# <add id="stest.expect_exception_mgr">
# Context manager verifying that the body of with-statement throws an
# exception of the specified type.
#
# Arguments:
# <dl>
# <dt>exc</dt>
# <dd>exception type</dd>
# <dt>regex</dt>
# <dd>optional regular expression object or a string
#     containing a regular expression suitable for use by
#     <tt>re.search()</tt>, which the string representation of raised exception
#     must match
# </dd>
# </dl>
# Example usage:
# <pre>
#with stest.expect_exception_mgr(simics.SimExc_AttrNotWritable):
#    dev.read_only_attribute = False
# </pre>
# </add>
@contextlib.contextmanager
def expect_exception_mgr(exc, regex=''):
    if not isinstance(exc, type) or not issubclass(exc, BaseException):
        raise TypeError(f"'exc' arg must be an exception type, got {repr(exc)}")
    try:
        yield
    except exc as e:
        if re.search(regex, str(e)) is None:
            fail(
                "Expected exception to contain the pattern defined by regex"
                f" '{regex}'. The actual exception message was: '{str(e)}'"
            )
    except TestFailure:
        raise
    except Exception as e:
        fail("Expected %s exception, got %r" % (exc.__name__, e))
    else:
        fail("Expected %s exception, got no exception" % exc.__name__)

# <add id="stest.expect_exception">
# Call function fun with arguments args, and verify that it raises an
# exception of type exc. If fun does not raise exc, cause a failure.
# </add>
def expect_exception(fun, args, exc, regex=''):
    with expect_exception_mgr(exc, regex):
        fun(*args)

class TestExpectException(unittest.TestCase):
    def test(self):
        def raise_exc(e):
            raise e
        class A(Exception): pass
        class B(A): pass
        expect_exception(raise_exc, [B()], A)
        self.assertRaises(TestFailure, expect_exception, raise_exc, [A()], B)
        self.assertRaises(TestFailure, expect_exception,
                          raise_exc, [TestFailure()], A)
        self.assertRaises(TestFailure, expect_exception,
                          lambda: None, [], A)
        # None is not exception type - expect_exception is to throw TypeError:
        self.assertRaises(TypeError, expect_exception,
                          lambda: None, [], None)
        expect_exception(raise_exc, [B('55 hello world')], A, r"[0-9]+.+world")
        expect_exception(raise_exc, [B('55 hello world')], A, "hello")
        self.assertRaises(TestFailure, expect_exception,
                          raise_exc, [B('55 hello world')], A, "bye")
        self.assertRaises(TestFailure, expect_exception,
                          raise_exc, [B()], A, 'non empty regex')


# <add id="stest.deprecation_level">
# Context manager for temporarily setting a deprecation level and restore it
# when exiting the context.
#
# Arguments:
# <dl>
# <dt>level</dt>
# <dd>deprecation level in context</dd>
# </dl>
# Example usage:
# <pre>
# with stest.deprecation_level(2)
#    stest.expect_equal(conf.sim.deprecation_level, 2)
# </pre>
# </add>
@contextlib.contextmanager
def deprecation_level(level):
    """Allow to temporarily set deprecation level to 'level'."""
    old = conf.sim.deprecation_level
    conf.sim.deprecation_level = level
    try:
        yield
    finally:
        conf.sim.deprecation_level = old

class TestDeprecationLevel(unittest.TestCase):
    def test(self):
        org_lvl = conf.sim.deprecation_level
        temp_lvl = (org_lvl + 1) % 3
        with deprecation_level(temp_lvl):
            self.assertEqual(conf.sim.deprecation_level, temp_lvl)
        self.assertEqual(conf.sim.deprecation_level, org_lvl)

# Sandbox

sandbox = os.environ.get('SANDBOX', '.')

def log_file(name):
    return os.path.join(sandbox, "logs", name)
log_file.vt_internal = True

# <add id="stest.scratch_file">
# Returns a string representing a path within the scratch directory.
#
# Concatenates the path of the test's scratch directory
# (which may or may not be absolute) with the provided string,
# representing a path into the scratch directory, and returns it.
#
# There are no checks for existence of the specified file
# or directory.
# </add>
def scratch_file(name):
    return os.path.join(sandbox, "scratch", name)
scratch_file.vt_internal = True

# note: cpu_type is internal and currently unused in Simics repo
def cpu_type():
    return os.environ.get('CPUCLASS')
