# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import sys
import abc
import operator
from dataclasses import dataclass
import traceback
import functools
import typing
from typing import Callable, Optional
import weakref
import unittest

import conf
import simics
import dev_util

__all__ = ['ExecContext', 'GlobalContext', 'CellContext', 'ThreadedContext',
           'Snooper', 'Handle', 'object_handle',
           'Error', 'InvalidObjError',
           'add_callback_simple',
           'catch_exceptions',
           'Hap',
           'Log',
           'Notifier',
           'DeviceAttribute',
           'RegisterValue',
           'Seconds',
           'Cycles',
           'Steps',
           'ConsoleString',
           'MemoryRead',
           'MemoryWrite',
           'MemoryExecute',
           'Filter',
           'Poll',
           'CompoundSnooper',
           'Latest',
           'Any',
           'AnyObject',
           ]


def _run_alone_wrapper(arg):
    (fn, stack) = arg
    try:
        fn()
    except BaseException as e:
        if stack is not None:
            print('*** Error in callback invoked from here:', file=sys.stderr)
            traceback.print_list(stack)
        raise e


def run_alone(fn, stack):
    '''Run fn in Global Context. If user errors can cause exceptions in
    fn, then 'stack' contains additional stack frames from the caller,
    as returned from traceback.extract_stack().'''
    simics.SIM_run_alone(_run_alone_wrapper, (fn, stack))


class Handle(abc.ABC):
    '''Handle returned by Future.Callback.add_callback'''
    @abc.abstractmethod
    def cancel(self) -> None:
        '''Stop receiving callbacks. Idempotent.'''


class ObjectHandle(Handle):
    def __init__(self, obj, cancel):
        self._cancel = cancel
        self._obj = obj
        # Notifier handle for deletion notifier; None if already cancelled
        self._delete_handle = None
    def register(self):
        self._delete_handle = simics.SIM_add_notifier(
            self._obj, simics.Sim_Notify_Object_Delete, None,
            self._on_delete, self)
    @staticmethod
    def _on_delete(obj, notifier, self):
        # Notifier implicitly deleted when object is deleted.
        # This can't happen after the notifier is deleted.
        assert self._delete_handle is not None
        simics.VT_python_decref(self)
        self._cancel()
        self._delete_handle = None
    def cancel(self):
        if self._delete_handle is None:
            # already cancelled
            return
        self._cancel()
        simics.SIM_delete_notifier(self._obj, self._delete_handle)
        self._delete_handle = None

def object_handle(obj, cancel):
    '''Return a `Handle` object that calls `cancel()` when cancelled,
    and which self-cancels when `obj` is deleted.'''
    handle = ObjectHandle(obj, cancel)
    handle.register()
    return handle


@dataclass
class ExecContext(abc.ABC):
    '''Base class for execution context specifiers.
    Should not be subclassed by users, mainly exposed for typing annotations'''


@dataclass
class CellContext(ExecContext):
    '''Callback can be called in Cell Context within the cell given by
    the `cell` member, or in Global Context. If `cell` is `None`,
    can be called from Cell Context in any cell or from Global
    Context.'''
    cell: Optional[simics.conf_object_t]
    def __init__(self, obj: Optional[simics.conf_object_t]):
        '''The `obj` argument can be any object or `None`; if it is an
        object then the `cell` attribute is set to the object's
        associated cell, or `None` if the object is not associated to
        a cell.'''
        if obj is not None:
            if obj.classname == 'cell':
                self.cell = obj
                return
            clk = simics.SIM_object_clock(obj)
            if clk is not None:
                self.cell = clk.cell
                return
        self.cell = None


class GlobalContext(ExecContext):
    '''Callback can only be called in Global Context.'''


class ThreadedContext(ExecContext):
    '''Callback can be called in any context, Threaded, Global or Cell.'''


class TestCellContext(unittest.TestCase):
    def test(self):
        self.assertEqual(GlobalContext(), GlobalContext())
        self.assertEqual(CellContext(None), CellContext(None))
        self.assertEqual(ThreadedContext(), ThreadedContext())
        self.assertEqual(CellContext(None).cell, None)
        self.assertEqual(CellContext(conf.sim).cell, None)
        cell = simics.SIM_create_object('cell', 'mycell')
        clk = simics.SIM_create_object('clock', 'clk', freq_mhz=1, cell=cell)
        ms = simics.SIM_create_object('memory-space', 'ms', queue=clk)
        try:
            for obj in [cell, clk, ms]:
                self.assertEqual(CellContext(obj).cell, cell)
        finally:
            simics.SIM_delete_objects([cell, clk, ms])


T = typing.TypeVar('T')
T1 = typing.TypeVar('T1')
T2 = typing.TypeVar('T2')


class Snooper(abc.ABC, typing.Generic[T]):
    '''Abstract class for snoopers. A snooper observes a class of simulation
    events and yields values when they happen.'''

    @abc.abstractmethod
    def add_callback(self, yield_value: Callable[[T], None],
                     yield_exception: Callable[[Exception], None]) -> None:
        '''Make sure that functions `yield_value` and `yield_exc` are
        called when the snooper yields a value or an exception,
        respectively.  Return `Handle` object for disposal. Neither
        `yield_value` nor `yield_exc` may be called after this handle
        has been cancelled.

        The `add_callback` method typically uses some simulation
        primitive to register a low-level callback on relevant
        simulation events.  The registered callback is typically *not*
        the `yield_value` argument, but a wrapper function with
        whatever signature the simulation primitive requires. This
        wrapper studies its arguments and calls `fun` zero or one
        time, and then returns. If an exception can happen when
        studying arguments, the function body may that and call
        `yield_exc` with the exception object as argument.
        This way it will be passed to typically useful when the
        snooper's constructor arguments cannot be validated until the
        callback happens.

        If one callback from the simulation primitive may trigger
        multiple calls to `yield_value` or `yield_exc`, then the
        callback must make sure to check between calls that the handle
        has not been cancelled.

        Neither `yield_value` nor `yield_exc` are required to be
        thread safe, so `add_callback` must ensure that neither is
        invoked concurrently from different threads. However, both
        functions may be reentrantly called if they trigger
        simulation side-effects.
        '''

    # In future revisions, we may extend this class with an optional
    # registration_exec_context method, which specifies the exec
    # context required for registration and cancellation. This will be
    # essential for performance when adding support for cell-local
    # event loops.
    @abc.abstractmethod
    def exec_context(self) -> ExecContext:
        '''Specifies in what execution contexts the callback
        registered with `add_callback()` can be called. The execution
        context also covers entering/exiting the callback's associated
        exception bridge. The return value is one of
        `CellContext(obj)`, `GlobalContext()` and `ThreadedContext()`.
        The execution context applies only to callbacks themselves;
        callback registration and cancellation may only be called in
        Global Context.
        '''

class Error(Exception):
    '''Base class for errors emitted by the snoop library'''
class InvalidObjError(Error):
    '''Raised by snooper constructors if an object passed as argument to the
    constructor does not fulfil the requirements of this snooper'''


class TestObjectHandle(unittest.TestCase):
    calls = []
    def make_handle(self, obj, cb):
        return object_handle(
            obj, lambda: self.calls.append(('cancel', cb)))
    def test_orphan_cancellation(self):
        '''Test that a callback on an object is cancelled
        if the listened object is deleted'''
        # arbitrary easy-to-instantiate class
        cls = "memory-space"
        obj = simics.SIM_create_object(cls, 'ms', [])
        try:
            def cb():
                assert False
            ref = weakref.ref(cb)
            handle1 = self.make_handle(obj, cb)
            handle1.cancel()
            self.assertEqual(self.calls, [('cancel', cb)])
            del self.calls[:]
            # idempotent
            handle1.cancel()
            self.assertEqual(self.calls, [])
            del handle1
            assert ref() is cb
            del cb
            self.assertIsNone(ref())

            def cb2():
                assert False
            ref2 = weakref.ref(cb2)
            handle2 = self.make_handle(obj, cb2)
        finally:
            simics.SIM_delete_object(obj)
        self.assertEqual(self.calls, [('cancel', cb2)])
        del self.calls[:]
        del handle2
        assert ref2() is cb2
        del cb2
        self.assertIsNone(ref2())


def catch_exceptions(exc_handler: Callable[[Exception], None]) -> Callable[
        [Callable[..., T]], Callable[..., T]]:
    '''Decorator to capture exceptions raised by a function by calling the
    function `exc_handler`. Typically useful for low-level callbacks created
    by implementations of Snooper.add_callback, if the callback can
    raise an exception. In this case, the following makes sure the exception
    is propagated:

    @catch_exceptions(yield_exception)
    def callback(...):
        ...
    '''
    def make_wrapper(fun):
        @functools.wraps(fun)
        def wrapper(*args, **kwargs):
            try:
                return fun(*args, **kwargs)
            except Exception as e:
                exc_handler(e)
        return wrapper
    return make_wrapper


class TestCatchExceptions(unittest.TestCase):
    def test_catch_exceptions(self):
        calls = []
        @catch_exceptions(lambda exc: calls.append(exc))
        def f(*args, **kwargs):
            calls.append((args, kwargs))
            if 'exc' in kwargs:
                raise kwargs['exc']
            return kwargs.get('ret')
        exc = Exception('hello')
        self.assertEqual(f(3, a=4, ret=5), 5)
        self.assertEqual(calls, [((3,), dict(a=4, ret=5))])
        del calls[:]
        self.assertIs(f(6, ret=7, exc=exc), None)
        self.assertEqual(calls, [((6,), dict(exc=exc, ret=7)), exc])


def add_callback_simple(
        snooper: Snooper[T], yield_value: Callable[[T], None],
        yield_exc: Optional[Callable[[Exception], None]]=None, *,
        once: bool=False):
    '''Wrapper around `Snooper.add_callback`:

    * The `yield_exc` argument is optional; leaving it out makes
    sense in the common case where the snooper is known to never yield
    exceptions. If an exception happens without explicit
    `yield_exc`, then a critical error is signalled.

    * If the `once` flag is `True`, then the callback will be
    automatically cancelled after the first `yield_value` call.
    '''
    if yield_exc is None:
        stack = traceback.extract_stack()[:-2]
        def yield_exc(exc):
            full_message = (
                'Unhandled exception in snooper. To capture gracefully,'
                ' pass an explicit exception handler to'
                ' add_callback_simple.'
                + ' Exception:\n'
                + ''.join(traceback.format_exception(
                    type(exc), exc, exc.__traceback__))
                + 'Callback registered here:\n'
                + ''.join(traceback.format_list(stack)))
            # reports problem immediately in appropriate manner;
            # then raises CriticalErrors
            simics.VT_critical_error(
                "unhandled snooper exception",
                full_message)

    @functools.wraps(yield_value)
    def safe_yield_value(value):
        '''The yield_value callback isn't supposed to raise
        exceptions, but if it does, then yielding it to the exception
        handler may help debugging.'''
        try:
            yield_value(value)
        except Exception as e:
            simics.VT_critical_error(
                'exception in add_callback_simple callback',
                "Exception in callback registered with add_callback_simple:\n"
                + ''.join(traceback.format_exception(
                    type(e), e, e.__traceback__)))

    if once:
        first = True
        @functools.wraps(yield_value)
        def cb(value):
            nonlocal first
            if first:
                first = False
                run_alone_or_now(handle.cancel)
                safe_yield_value(value)
        @functools.wraps(yield_exc)
        def exc_cb(exc):
            if first:
                yield_exc(exc)
    else:
        cb = safe_yield_value
        exc_cb = yield_exc

    handle = snooper.add_callback(cb, exc_cb)
    return handle


class TestSimpleCallback(unittest.TestCase):
    def test_add_callback_simple(self):
        calls = []
        cbs = []
        dummy_exc = Exception('dummy exc')
        class DummyHandle(Handle):
            def cancel(self): calls.append(self)
        class MockSnooper(Snooper):
            def add_callback(cb, exc_cb):
                def inner_cb(value):
                    if value:
                        cb(value)
                    else:
                        exc_cb(dummy_exc)
                cbs.append(inner_cb)
                return DummyHandle()
        handle = add_callback_simple(MockSnooper, lambda x: calls.append(x))
        [inner_cb] = cbs
        del cbs[:]
        inner_cb(7)
        self.assertEqual(calls, [7])
        del calls[:]
        prev = conf.sim.stop_on_error
        conf.sim.stop_on_error = False
        try:
            with self.assertRaisesRegex(
                    simics.CriticalErrors, "unhandled snooper exception"):
                inner_cb(False)
        finally:
            conf.sim.stop_on_error = prev
        handle.cancel()
        self.assertEqual(calls, [handle])
        del calls[:]

        handle = add_callback_simple(MockSnooper, lambda x: calls.append(x),
                                     yield_exc=lambda exc: calls.append(exc),
                                     once=True)
        [inner_cb] = cbs
        del cbs[:]
        inner_cb(False)
        self.assertEqual(calls, [dummy_exc])
        del calls[:]
        inner_cb(11)
        self.assertEqual(calls, [handle, 11])
        del calls[:]
        # a snooper *should* not call its callback after cancellation,
        # but if it does then we suppress the extra call
        inner_cb(11)
        self.assertEqual(calls, [])

        # An explicit exception handler does not forgive an exception in
        # the callback
        for once in [False, True]:
            bad_exc = Exception('bad exception')
            def bad_cb(_):
                raise bad_exc
            handle = add_callback_simple(
                MockSnooper, bad_cb, yield_exc=lambda exc: calls.append(exc),
                once=once)
            [inner_cb] = cbs
            del cbs[:]
            prev = conf.sim.stop_on_error
            conf.sim.stop_on_error = False
            try:
                with self.assertRaisesRegex(simics.CriticalErrors,
                                            '1 critical error'):
                    inner_cb(1)
            finally:
                conf.sim.stop_on_error = prev
            self.assertEqual(calls, [handle] if once else [])


def test_decref(tc, snooper):
    '''Test that a snooper's `cancel` calls simics.VT_python_decref just the
    right (non-zero) number of times to free the callback'''
    def weakref_after_cancel(snooper):
        def cb(_): pass
        ref = weakref.ref(cb)
        handle = snooper.add_callback(cb, cb)
        handle.cancel()
        del handle
        assert ref() is not None
        del cb
        return ref()
    tc.assertIsNone(weakref_after_cancel(snooper))
    orig = simics.VT_python_decref
    try:
        first = True
        def decref(obj):
            nonlocal first
            if first:
                first = False
            else:
                orig(obj)
        simics.VT_python_decref = decref
        tc.assertIsNotNone(weakref_after_cancel(snooper))
    finally:
        simics.VT_python_decref = orig


class Hap(Snooper):
    '''Yield a value when a hap occurs on a given object. The value
    is a tuple of the hap arguments, excluding the object.'''
    def __init__(self, obj: simics.conf_object_t, name: str,
                 exec_context: ExecContext=None):
        '''The `obj` argument denotes the object on which we listen to a hap.
        `name` denotes the name of the hap.
        The `exec_context` argument declares the
        execution context of the notifier. The default `CellContext(obj)`
        is correct for most notifier types, but some haps only happen
        in Global Context; passing `GlobalContext()` for such notifiers may
        have advantages.'''
        self.obj = obj
        self.name = name
        self._exec_context = (CellContext(obj) if exec_context is None
                              else exec_context)
    @staticmethod
    def apply_callback(fun, obj, *args):
        return fun(args)
    def add_callback(self, cb, _):
        hap_id = simics.SIM_hap_add_callback_obj(
            self.name, self.obj, 0, self.apply_callback, cb)
        def cancel():
            simics.SIM_hap_delete_callback_obj_id(self.name, self.obj,
                                                  hap_id)
        return object_handle(self.obj, cancel)

    def exec_context(self):
        return self._exec_context


class TestHap(unittest.TestCase):
    def test_hap(self):
        hap_type = simics.SIM_hap_add_type('My_Hap', 'ii', 'x y', '', '', 0)
        calls = []
        def cb(args):
            calls.append(args)
        ref = weakref.ref(cb)
        handle = add_callback_simple(Hap(conf.sim, 'My_Hap'), cb)
        simics.SIM_hap_occurred_always(hap_type, conf.sim, 0, [1, 2])
        simics.SIM_hap_occurred_always(hap_type, conf.sim, 0, [3, 4])
        self.assertEqual(calls, [(1, 2), (3, 4)])
        del calls[:]
        handle.cancel()
        assert ref() is cb
        del cb
        self.assertIsNone(ref())
        simics.SIM_hap_occurred_always(hap_type, conf.sim, 0, [5, 6])
        self.assertEqual(calls, [])

        self.assertEqual(
            Hap(conf.sim, 'My_Hap', GlobalContext()).exec_context(),
            GlobalContext())
        cell = simics.SIM_create_object('cell', 'mycell')
        try:
            self.assertEqual(
                Hap(cell, 'My_Hap').exec_context(), CellContext(cell))
        finally:
            simics.SIM_delete_object(cell)


@dataclass
class LogData:
    kind: str
    message: str


class Log(Hap):
    '''Yield a value when a message is logged.
    The value has two members: the log type `kind`, and the message `message`,
    both strings.'''
    log_types = conf.sim.log_types
    def __init__(self, obj):
        '''`obj` is the object from which we listen to all logged messages.'''
        super().__init__(obj, "Core_Log_Message_Filtered")
    def add_callback(self, cb, yield_exc):
        def wrapped(args):
            (kind, msg, level, groups) = args
            cb(LogData(self.log_types[kind], msg))
        return super().add_callback(wrapped, yield_exc)


class TestLog(unittest.TestCase):
    def test_log(self):
        calls = []
        def cb(arg):
            calls.append(arg)
        ref = weakref.ref(cb)
        handle = add_callback_simple(Log(conf.sim), cb)
        simics.SIM_log_info(1, conf.sim, 0, 'cow')
        simics.SIM_log_unimplemented(1, conf.sim, 0, 'horse')
        self.assertEqual(calls, [LogData('info', 'cow'),
                              LogData('unimpl', 'horse')])
        del calls[:]
        handle.cancel()
        assert ref() is cb
        del cb
        self.assertIsNone(ref())
        simics.SIM_log_info(1, conf.sim, 0, 'pig')
        self.assertEqual(calls, [])


class Notifier(Snooper[None]):
    '''Yield the value `None` when a notifier is notified on an object.'''
    def __init__(self, obj: simics.conf_object_t,
                 notifier_type: typing.Union[int, str],
                 exec_context: ExecContext=None):
        '''`notifier_type` specifies the notifier type, as either a string
        or an integer. The `exec_context` argument declares the
        execution context of the notifier. The default `CellContext(obj)`
        is correct for most notifier types, but some notifiers only happen
        in Global Context; passing `GlobalContext()` for such notifiers may
        have advantages.'''
        if isinstance(notifier_type, str):
            notifier_type = simics.SIM_notifier_type(notifier_type)
        if not simics.SIM_has_notifier(obj, notifier_type):
            names = [n for (n, i, *_) in conf.sim.notifier_list
                     if i == notifier_type]
            if not names:
                raise TypeError(f'not a notifier ID: {notifier_type}')
            [name] = names
            raise InvalidObjError(f'object {obj.name} has no notifier {name}')
        self.obj = obj
        self.notifier_type = notifier_type
        self._exec_context = (CellContext(obj) if exec_context is None
                              else exec_context)
    @staticmethod
    def _apply_callback(obj, notifier, cb):
        cb(None)
    def add_callback(self, cb: Callable[[None], None], yield_exc):
        handle = simics.SIM_add_notifier(
            self.obj, self.notifier_type, None,
            Notifier._apply_callback, cb)
        def cancel():
            simics.SIM_delete_notifier(self.obj, handle)
        return object_handle(self.obj, cancel)
    def exec_context(self):
        return self._exec_context


class TestNotifier(unittest.TestCase):
    def test_notifier(self):
        with self.assertRaises(TypeError):
            Notifier(conf.sim, 1 << 30)
        not_type = simics.SIM_notifier_type('my-notifier')
        with self.assertRaises(InvalidObjError):
            Notifier(conf.sim, not_type)
        simics.SIM_register_notifier('sim', not_type, '')
        calls = []
        def cb0(arg):
            calls.append((0, arg))
        def cb1(arg):
            calls.append((1, arg))
        ref0 = weakref.ref(cb0)
        handle0 = add_callback_simple(Notifier(conf.sim, not_type), cb0)
        handle1 = add_callback_simple(Notifier(conf.sim, 'my-notifier'), cb1)
        simics.SIM_notify(conf.sim, not_type)
        self.assertEqual(sorted(calls), [(0, None), (1, None)])
        del calls[:]
        simics.SIM_notify(conf.sim, not_type)
        self.assertEqual(sorted(calls), [(0, None), (1, None)])
        del calls[:]
        handle0.cancel()
        handle1.cancel()
        del handle0
        assert ref0() is cb0
        del cb0
        self.assertIsNone(ref0())
        simics.SIM_notify(conf.sim, not_type)
        self.assertEqual(calls, [])

        self.assertEqual(
            Notifier(conf.sim, not_type, GlobalContext()).exec_context(),
            GlobalContext())
        simics.SIM_register_notifier('cell', not_type, '')
        cell = simics.SIM_create_object('cell', 'mycell')
        try:
            self.assertEqual(
                Notifier(cell, not_type).exec_context(), CellContext(cell))
        finally:
            simics.SIM_delete_object(cell)


@dataclass
class Poll(Snooper[T]):
    '''Abstract snooper that yields the value returned by the method
    `poll`, called whenever a specified subordinate snooper yields a
    value, but only when the value returned from `poll` differs from
    the last returned value. The initial value is read on
    `add_callback`. Exceptions from `poll` and from the subordinate
    snooper are propagated.

    The `Poll` class has an abstract method `poll`, with no
    arguments, returning the current value of the polled state. The
    `__init__` method of the class accepts a single argument, the
    subordinate snooper that controls when to poll.

    This snooper has two use cases, one good and one bad: The good use
    case is when an object fires a custom notifier, say
    `'my-notifier'`, whenever a particular attribute, say `attr`, changes,
    and one wants to subscribe to that state. This can be expressed as:
    ```
    class MySnooper(Poll):
        def __init__(self, obj: simics.conf_object_t)
            self._obj = obj
            super().__init__(Notifier(obj, 'my-notifier'))
        def poll(self):
            return self._obj.attr
    ```

    The bad use case is to use a `Seconds` snooper as the subordinate
    snooper, to periodically poll for state changes.  This can work as
    a fallback for snooping an attribute that does not provide an explicit
    callback mechanism, but this technique has two problems:

    * With a too long interval, it will take some time from the state
      change until a value is yielded. The state might also change
      twice between `poll` calls, causing a complete omission of
      a yield; this may cause intermittent hard-to-debug bugs
      if simulation is not deterministic.

    * With a too short interval, the polling may harm simulation
      speed.

    For these reasons, `Seconds`-based polling should only be used as
    a temporary measure until the object has been extended with a
    custom notifier type.
    '''
    _subordinate: Snooper

    def add_callback(self, yield_value, yield_exception):
        prev = self.poll()
        @catch_exceptions(yield_exception)
        def cb(_):
            nonlocal prev
            new = self.poll()
            if new != prev:
                prev = new
                yield_value(new)
        return self._subordinate.add_callback(cb, yield_exception)

    def exec_context(self):
        return self._subordinate.exec_context()

    @abc.abstractmethod
    def poll(self) -> T:
        pass


class TestPoll(unittest.TestCase):
    def test_poll(self):
        calls = []
        test_exc = Exception('test')
        class MockSnooper(Snooper):
            class Handle(Handle):
                def cancel(self): calls.append(('cancel', self))
            def add_callback(self, cb, exc_cb):
                handle = self.Handle()
                calls.append((cb, exc_cb, handle))
                return handle
            def exec_context(self):
                return ThreadedContext()
        class MockPoll(Poll):
            def poll(self):
                calls.append('poll')
                if isinstance(val, Exception):
                    raise val
                return val
            def __init__(self):
                super().__init__(MockSnooper())

        self.assertEqual(MockPoll().exec_context(),
                         ThreadedContext())
        val =  3
        handle = MockPoll().add_callback(
            lambda arg: calls.append(('cb', arg)),
            lambda exc: calls.append(('exc', exc)))
        [get, (poll, exc_cb, inner_handle)] = calls
        self.assertEqual(get, 'poll')
        del calls[:]
        exc_cb(test_exc)
        self.assertEqual(calls, [('exc', test_exc)])
        del calls[:]
        poll(7)
        poll(8)
        val = 5
        poll(9)
        self.assertEqual(calls, ['poll', 'poll', 'poll', ('cb', 5)])
        del calls[:]
        poll(10)
        val = 6
        poll(11)
        self.assertEqual(calls, ['poll', 'poll', ('cb', 6)])
        del calls[:]
        val = test_exc
        poll(12)
        self.assertEqual(calls, ['poll', ('exc', test_exc)])
        del calls[:]
        handle.cancel()
        self.assertEqual(calls, [('cancel', inner_handle)])
        del calls[:]


state_change = simics.Sim_Notify_State_Change


@dataclass
class _c_DeviceAttribute(Snooper):
    notifier_obj: simics.conf_object_t
    attr_obj: simics.conf_object_t
    attr_name: str

    def add_callback(self, yield_value, yield_exception):
        simics.SIM_load_module('snooper-helpers')
        import simmod.snooper_helpers.snooper_helpers as h
        handle = h.add_device_attribute_notifier(
            self.notifier_obj, self.attr_obj, self.attr_name, yield_value)
        def cancel():
            h.delete_device_attribute_notifier(handle)
        return object_handle(self.notifier_obj, cancel)

    def exec_context(self):
        return CellContext(self.notifier_obj)


class DeviceAttribute(Poll[int]):
    '''Yield the value of an attribute in a DML device when it changes'''
    def __init__(self, obj: simics.conf_object_t, attr: str):
        '''Listen to changes to the `attr` attribute in `obj`. The `obj`
        object must belong to a DML device; it may either be the device object
        itself, or one of its ports, banks or subdevices.'''
        self._attr_obj = obj
        self._attr = attr
        if not simics.SIM_class_has_attribute(
                simics.SIM_object_class(obj), attr):
            raise InvalidObjError(f'object {obj} has no attribute "{attr}"')
        if simics.SIM_has_notifier(obj, state_change):
            notifier_obj = obj
        else:
            parent = simics.SIM_port_object_parent(obj)
            if not parent or not simics.SIM_has_notifier(
                    parent, state_change):
                raise InvalidObjError(
                    f'object has no state-change notifier: {obj}')
            notifier_obj = parent
        super().__init__(_c_DeviceAttribute(notifier_obj, obj, attr))

    def poll(self):
        return simics.SIM_get_attribute(self._attr_obj, self._attr)


class TestDeviceAttribute(unittest.TestCase):
    def test_attribute(self):
        with self.assertRaises(InvalidObjError):
            # attribute exists, but not a DML dev
            assert hasattr(conf.sim, 'version')
            DeviceAttribute(conf.sim, 'version')
        dev = simics.SIM_create_object('sample_device_dml', 'dev', [])
        try:
            with self.assertRaises(InvalidObjError):
                # attribute doesn't exist
                DeviceAttribute(dev, 'version')
            dev.log_level = 0
            calls = []
            dev.int_attr = 4
            handle1 = add_callback_simple(DeviceAttribute(dev, 'int_attr'),
                lambda x: calls.append(('int_attr', x)))
            handle2 = add_callback_simple(DeviceAttribute(dev.bank.regs, 'r1'),
                lambda x: calls.append(('r1', x)))
            dev.int_attr = 3
            dev.int_attr = 4
            dev.bank.regs.r1 = 2
            dev.bank.regs.r1 = 2
            dev.int_attr = 4
            dev.int_attr = 3
            dev.bank.regs.r1 = 3
            self.assertEqual(calls, [('int_attr', 3), ('int_attr', 4),
                                  ('r1', 2), ('int_attr', 3), ('r1', 3)])
            del calls[:]
            handle2.cancel()
            dev.bank.regs.r1 = 4
            self.assertEqual(calls, [])
            handle1.cancel()

            def cb(x):
                pass
            ref = weakref.ref(cb)
            handle = add_callback_simple(DeviceAttribute(dev, 'int_attr'), cb)
            handle.cancel()
            del handle
            assert ref() is cb
            del cb
            self.assertIsNone(ref())

            self.assertEqual(
                DeviceAttribute(dev.bank.regs, 'r1').exec_context(),
                CellContext(dev.bank.regs))

        finally:
            simics.SIM_delete_object(dev)


@dataclass
class _c_RegisterValueStateChange(Snooper):
    notifier_obj: simics.conf_object_t
    notifier_type: int  # notifier_type_t
    bank_obj: simics.conf_object_t
    regnum: int

    def add_callback(self, yield_value, yield_exception):
        simics.SIM_load_module('snooper-helpers')
        import simmod.snooper_helpers.snooper_helpers as h
        handle = h.add_register_value_state_change_notifier(
            self.notifier_obj, self.notifier_type, self.bank_obj,
            self.regnum, yield_value)
        def cancel():
            h.delete_register_value_state_change_notifier(handle)
        return object_handle(self.notifier_obj, cancel)

    def exec_context(self):
        return CellContext(self.notifier_obj)


_reg_value_change = simics.Sim_Notify_Bank_Register_Value_Change
class RegisterValue(Poll[int]):
    '''Yield the value of a register or field of a C++ or DML bank when
    it changes. Depends on the `bank-register-value-change` or
    `state-change` notifier, together with register metadata from the
    `register_view` interface.
    '''
    def __init__(self, reg: dev_util.BankRegister, equal: Optional[int]=None):
        '''Listen to changes to the register defined by `reg`, as
        returned by the `dev_util.bank_regs` function.

        If `equal` is set, then instead of yielding register values,
        yield `True` when the register changes to the given value, and
        `False` when it changes from the given value to something
        else.'''
        bank = reg.bank
        if simics.SIM_has_notifier(bank, _reg_value_change):
            notifier_snooper = _c_RegisterValueStateChange(
                bank, _reg_value_change, bank, reg.get_set_reg._num)
        else:
            parent = simics.SIM_port_object_parent(bank)
            if not parent or not simics.SIM_has_notifier(
                    parent, state_change):
                raise InvalidObjError(
                    'bank has no state-change or bank-register-value-change'
                    f' notifier: {bank}')
            notifier_snooper = _c_RegisterValueStateChange(
                parent, state_change, bank, reg.get_set_reg._num)
        self._reg = reg
        super().__init__(notifier_snooper)

    def poll(self):
        return self._reg.val


class TestRegisterValue(unittest.TestCase):
    def test_register_value_dml(self):
        obj = simics.SIM_create_object('sample_device_dml', 'dev')
        try:
            calls = []
            obj.bank.regs.r1 = 0
            handle = RegisterValue(
                dev_util.bank_regs(obj.bank.regs).r1).add_callback(
                calls.append, calls.append)
            obj.bank.regs.r1 = 7
            self.assertEqual(calls, [7])
            del calls[:]
            handle.cancel()
            obj.bank.regs.r1 = 5
            self.assertEqual(calls, [])

            def cb(x):
                pass
            ref = weakref.ref(cb)
            handle = add_callback_simple(RegisterValue(
                dev_util.bank_regs(obj.bank.regs).r1), cb)
            handle.cancel()
            del handle
            assert ref() is cb
            del cb
            self.assertIsNone(ref())
        finally:
            simics.SIM_delete_object(obj)

    def test_register_value_cc(self):
        obj = simics.SIM_create_object('test_field_array_via_data', 'dev')
        try:
            calls = []
            obj.bank.b.r = 0
            handle = RegisterValue(
                dev_util.bank_regs(obj.bank.b).r).add_callback(
                calls.append, calls.append)
            obj.bank.b.r = 7
            self.assertEqual(calls, [7])
            del calls[:]
            handle.cancel()
            obj.bank.b.r = 0
            self.assertEqual(calls, [])

            def cb(x):
                pass
            ref = weakref.ref(cb)
            handle = add_callback_simple(RegisterValue(
                dev_util.bank_regs(obj.bank.b).r), cb)
            handle.cancel()
            del handle
            assert ref() is cb
            del cb
            self.assertIsNone(ref())
        finally:
            simics.SIM_delete_object(obj)


class FieldValue(RegisterValue):
    '''Yield the value of a field of a C++ or DML bank when
    it changes. Depends on the `bank-register-value-change` or
    `state-change` notifier, together with register metadata from the
    `register_view` interface.
    '''
    def __init__(self, field: dev_util.Field):
        '''Listen to changes to the field `field`, as returned by the
        `dev_util.bank_regs` function.
        '''
        super().__init__(field.reg)
        self._field = field

    def poll(self):
        return self._field.val


class TestFieldValue(unittest.TestCase):
    def test_register_value_cc(self):
        obj = simics.SIM_create_object('test_field_array_via_data', 'dev')
        try:
            calls=[]
            # f0[1] is bits 9:8, mask 0x300
            handle = FieldValue(
                dev_util.bank_regs(obj.bank.b).r.field.f0[1]).add_callback(
                calls.append, calls.append)
            obj.bank.b.r = 0xffcff
            self.assertEqual(calls, [])
            obj.bank.b.r = 0xffdff
            obj.bank.b.r = 0xfffff
            obj.bank.b.r = 0xffeff
            self.assertEqual(calls, [1, 3, 2])
            del calls[:]
            obj.bank.b.r = 0x00200
            self.assertEqual(calls, [])
            handle.cancel()
            obj.bank.b.r = 0
            self.assertEqual(calls, [])
        finally:
            simics.SIM_delete_object(obj)


@dataclass
class Time(Snooper[None]):
    '''Common implementation between event based snoopers'''
    clk: simics.conf_object_t

    def __mul__(self, other):
        return type(self)(self.clk, self.interval * other)

    def __rmul__(self, other):
        return self.__mul__(other)

    def __add__(self, other):
        if not isinstance(other, type(self)) or other.clk != self.clk:
            return NotImplemented
        return type(self)(self.clk, self.interval + other.interval)

    def __sub__(self, other):
        if not isinstance(other, type(self)) or other.clk != self.clk:
            return NotImplemented
        return type(self)(self.clk, self.interval - other.interval)

    def exec_context(self):
        return CellContext(self.clk)

    @dataclass
    class Handle(Handle):
        cb: callable
        clk: simics.conf_object_t
        # low-level functions for posting event, accepting self as arg
        # to avoid a GC-unfriendly cyclic reference. Both functions
        # leak the handle arg.
        _post: Callable[['Time.Handle'], None]
        _cancel: Callable[['Time.Handle'], None]
        def post(self):
            if type(self.clk).__name__ == 'deleted conf_object_t':
                return
            self._post(self)
        @staticmethod
        def _ev_callback(obj, handle):
            # callback must happen before repost:
            # this is needed if callback cancels handle, because we want
            # that to cancel the newly posted event
            handle._post(handle)
            handle.cb(None)
            # compensate for reference leak from SIM_event_post_time
            simics.VT_python_decref(handle)
        def cancel(self):
            if type(self.clk).__name__ == 'deleted conf_object_t':
                # skip decref also from SIM_event_post_time, to avoid double
                # decref in case clk was deleted at the time of _post
                return
            self._cancel(self)
            # compensate for reference leak from SIM_event_cancel_time
            simics.VT_python_decref(self)
            # compensate for reference leak from SIM_event_post_time
            simics.VT_python_decref(self)


Time.evclass = simics.SIM_register_event(
    "snoop-callback", 'sim',
    simics.Sim_EC_Notsaved, Time.Handle._ev_callback,
    None, None, None, lambda *args: f"callback from {__name__}.Seconds")


@dataclass
class Seconds(Time):
    '''Yield `None` when the given number of simulated seconds have
    passed.  Seconds form a vector space over numbers: `Second`
    objects can be added or subtracted, and multiplied or divided by
    numbers.'''
    interval: float
    def __init__(self, clk: simics.conf_object_t, seconds: float=1):
        '''`None` is yielded once every `seconds` cycles on the clock `clk`.
        '''
        if simics.SIM_picosecond_clock(clk) is None:
            raise Error(f'object {clk.name} does not have an associated clock')
        self.clk = clk
        self.interval = seconds

    def __truediv__(self, other):
        return Seconds(self.clk, self.interval / other)

    def add_callback(self, cb: Callable[[None], None], yield_exc):
        clk = simics.SIM_picosecond_clock(self.clk)
        handle = Time.Handle(
            cb, self.clk,
            functools.partial(
                simics.SIM_event_post_time,
                clk, Time.evclass, self.clk, self.interval),
            functools.partial(simics.SIM_event_cancel_time,
                clk, Time.evclass, self.clk, operator.is_))
        handle.post()
        return handle


@dataclass
class Cycles(Time):
    '''Yield `None` when the given number of simulated cycles have
    passed.  Cycles form an abelian group: `Cycles` objects on the
    same clock can be added or subtracted from each other, and
    multiplied by integers.'''
    interval: int
    def __init__(self, clk: simics.conf_object_t, cycles: int):
        '''`None` is yielded once every `cycles` cycles on the clock `clk`.
        '''
        if simics.SIM_object_clock(clk) is None:
            raise Error(f'object {clk.name} does not have an associated clock')
        self.clk = clk
        self.interval = cycles

    def add_callback(self, cb: Callable[[None], None], yield_exc):
        handle = Time.Handle(
            cb, self.clk,
            functools.partial(
                simics.SIM_event_post_cycle, self.clk, Time.evclass,
                self.clk, self.interval),
            functools.partial(
                simics.SIM_event_cancel_time,
                self.clk, Time.evclass, self.clk, operator.is_))
        handle.post()
        return handle


@dataclass
class Steps(Time):
    '''Yield `None` when the given number of simulated steps have
    passed.  Steps form an abelian group: `Steps` objects on the
    same clock can be added or subtracted from each other, and
    multiplied by integers.'''
    interval: int
    def __init__(self, cpu: simics.conf_object_t, steps: int):
        '''`None` is yielded once every `steps` steps on the CPU `cpu`,
        which must implement the `step` interface.
        '''
        clk = simics.SIM_object_clock(cpu)
        if clk is None:
            raise Error(f'object {cpu.name} does not have an associated clock')
        if not simics.SIM_c_get_interface(clk, 'step'):
            raise Error(f'object {clk.name} does not implement'
                        ' the step interface')
        self.clk = cpu
        self.interval = steps

    def add_callback(self, cb: Callable[[None], None], yield_exc):
        handle = Time.Handle(
            cb, self.clk,
            functools.partial(
                simics.SIM_event_post_step, self.clk, Time.evclass,
                self.clk, self.interval),
            functools.partial(
                simics.SIM_event_cancel_step,
                self.clk, Time.evclass, self.clk, operator.is_))
        handle.post()
        return handle


class TestTime(unittest.TestCase):
    def callback_tests(self, cls, clk, ktick, tick_count):
        ns1 = simics.SIM_create_object('namespace', 'ns1', queue=clk)
        ns2 = simics.SIM_create_object('namespace', 'ns2', queue=None)
        try:
            calls = []
            simics.SIM_continue(1500)
            def cb1(arg):
                assert arg is None
                calls.append(tick_count(clk))
            ref1 = weakref.ref(cb1)
            handle1 = add_callback_simple(
                cls(clk, ktick), cb1)
            simics.SIM_continue(1)
            handle2 = add_callback_simple(
                cls(ns1, ktick),
                lambda _: calls.append(tick_count(clk)))
            simics.SIM_continue(2501)
            self.assertEqual(calls, [2500, 2501, 3500, 3501])
            del calls[:]
            handle1.cancel()
            del handle1
            assert ref1() is cb1
            del cb1
            self.assertIsNone(ref1())
            simics.SIM_continue(1000)
            self.assertEqual(calls, [4501])
            handle2.cancel()
            try:
                cell = simics.SIM_create_object('cell', 'my_cell')
                old = clk.cell
                clk.cell = cell
                self.assertEqual(cls(clk, 1).exec_context(),
                                 CellContext(clk))
            finally:
                clk.cell = old
                simics.SIM_delete_object(cell)
            with self.assertRaises(Error):
                cls(ns2, ktick)
            test_decref(self, cls(clk, ktick))
        finally:
            simics.SIM_delete_object(ns1)
            simics.SIM_delete_object(ns2)

    def test_seconds(self):
        time_clk = simics.SIM_create_object('clock', 'clk', freq_mhz=1)
        try:
            self.callback_tests(Seconds, time_clk, 0.001,
                                simics.SIM_cycle_count)
        finally:
            simics.SIM_delete_object(time_clk)
        time_clk = simics.SIM_create_object('clock', 'clk', freq_mhz=1)
        try:
            self.callback_tests(Cycles, time_clk, 1000, simics.SIM_cycle_count)
        finally:
            simics.SIM_delete_object(time_clk)
        step_clk = simics.SIM_create_object('step_clock', 'sclk', freq_mhz=1)
        try:
            self.callback_tests(Steps, step_clk, 1000, simics.SIM_step_count)
        finally:
            simics.SIM_delete_object(step_clk)

    def abelian_group_tests(self, cls, clk):
        two = cls(clk, 2)
        three = cls(clk, 3)
        five = cls(clk, 5)
        six = cls(clk, 6)
        self.assertEqual(five, cls(clk, 5))
        self.assertNotEqual(five, six)
        ns = simics.SIM_create_object('namespace', 'ns', queue=clk)
        try:
            other_five = cls(ns, 5)
            self.assertNotEqual(five, other_five)
        finally:
            simics.SIM_delete_object(ns)
        self.assertEqual(two + three, five)
        self.assertEqual(five - three, two)
        self.assertEqual(three * 2, six)
        self.assertEqual(3 * two, six)
        self.assertEqual(two * 2.5, five)
        with self.assertRaises(TypeError):
            # fisketur[unused-value]
            five + other_five
        with self.assertRaises(TypeError):
            # fisketur[unused-value]
            five - other_five
        with self.assertRaises(TypeError):
            # fisketur[unused-value]
            five + 5
        with self.assertRaises(TypeError):
            # fisketur[unused-value]
            5 + five

    def test_arithmetic(self):
        time_clk = simics.SIM_create_object('clock', 'clk', freq_mhz=1)
        step_clk = simics.SIM_create_object('step_clock', 'sclk', freq_mhz=1)
        try:
            # All time classes are abelian groups, meaning they support
            # integer addition and multiplication.
            self.abelian_group_tests(Seconds, time_clk)
            self.abelian_group_tests(Cycles, time_clk)
            self.abelian_group_tests(Steps, step_clk)
            # Seconds also have vector space properties: supports
            # floating-point numbers and division.
            two_point_five = Seconds(time_clk, 2.5)
            five = Seconds(time_clk, 5)
            self.assertEqual(2 * two_point_five, five)
            self.assertEqual(five / 2, two_point_five)
            with self.assertRaises(TypeError):
                # fisketur[unused-value]
                5 / five

            # Interval arg is optional only for Seconds.
            self.assertEqual(Seconds(time_clk), Seconds(time_clk, 1))
            with self.assertRaises(TypeError):
                # fisketur[call-args]
                Cycles(time_clk)
            with self.assertRaises(TypeError):
                # fisketur[call-args]
                Steps(step_clk)
            with self.assertRaises(Error):
                Steps(time_clk, 1)
        finally:
            simics.SIM_delete_object(time_clk)
            simics.SIM_delete_object(step_clk)


@dataclass
class ConsoleString(Snooper[None]):
    '''Yield `None` when a matching string appears on a console.'''
    con: simics.conf_object_t
    string: str
    regexp: bool
    def __init__(self, con: simics.conf_object_t, string: str,
                 regexp: bool=False):
        '''The text `string` should appear on the `con` object,
        which should implement the `break_strings_v2` interface.
        If `regexp` is `True`,
        then the string is interpreted as a regular expression, as defined
        by the [Hyperscan](https://hyperscan.io) library.'''
        if simics.SIM_c_get_interface(con, 'break_strings_v2') is None:
            raise InvalidObjError(f'object {con.name} does not implement'
                                  f' the break_strings_v2 interface')
        self.con = con
        self.string = string
        self.regexp = regexp
    @staticmethod
    def trampoline(con, string, con_id, cb):
        cb(None)
        return 1
    def add_callback(self, cb, yield_exc):
        if self.regexp:
            bpid = self.con.iface.break_strings_v2.add_regexp(
                self.string, self.trampoline, cb)
        else:
            bpid = self.con.iface.break_strings_v2.add(
                self.string, self.trampoline, cb)
        def cancel():
            self.con.iface.break_strings_v2.remove(bpid)
            simics.VT_python_decref(cb)
        return object_handle(self.con, cancel)

    def exec_context(self):
        return CellContext(self.con)


class TestConsoleString(unittest.TestCase):
    def test_console_string(self):
        # TODO: test regexp
        rec = simics.SIM_create_object('recorder', 'rec', [])
        con = simics.SIM_create_object('textcon', 'con', [['recorder', rec],
                                                          ['visible', False]])
        calls = []
        def cb(string):
            calls.append(string)
        with self.assertRaises(InvalidObjError):
            ConsoleString(conf.sim, 'foo')
        ref = weakref.ref(cb)
        snooper = ConsoleString(con, 'foo')
        self.assertEqual(snooper.exec_context(), CellContext(con))
        handle = add_callback_simple(snooper, cb)
        for char in b'ufo':
            con.iface.serial_device.write(char)
        self.assertEqual(calls, [])
        con.iface.serial_device.write(ord('o'))
        self.assertEqual(calls, [None])
        del calls[:]
        handle.cancel()
        del handle
        assert ref() is cb
        del cb
        self.assertIsNone(ref())
        for c in b'foo':
            con.iface.serial_device.write(c)
        self.assertEqual(calls, [])

        def cb2(string):
            calls.append(string)
        handle = add_callback_simple(ConsoleString(con, 'a.*b',
                                                   regexp=True), cb2)
        for c in b'acdefg':
            con.iface.serial_device.write(c)
        self.assertEqual(calls, [])
        con.iface.serial_device.write(ord('b'))
        self.assertEqual(calls, [None])
        handle.cancel()

        test_decref(self, ConsoleString(con, 'foo'))

        simics.SIM_delete_object(con)
        simics.SIM_delete_object(rec)

class _MemoryAccess(Snooper):
    @abc.abstractproperty
    def access(self): pass
    break_type = simics.Sim_Break_Physical
    def __init__(self, obj, address, length):
        if simics.SIM_c_get_interface(obj, 'breakpoint') is None:
            raise InvalidObjError(f'object {obj.name} does not implement'
                                  ' the breakpoint interface')
        self.obj = obj
        self.address = address
        self.length = length

    @classmethod
    def trampoline(cls, cb, obj, idx, memop):
        if not simics.SIM_get_mem_op_inquiry(memop):
            cb(cls._decode_memop(memop))
    def add_callback(self, cb, yield_exc):
        bp_id = simics.SIM_breakpoint(self.obj, self.break_type, self.access,
                                      self.address, self.length, 0)
        hap_id = simics.SIM_hap_add_callback_obj_index(
            "Core_Breakpoint_Memop", self.obj, 0, self.trampoline, cb,
            bp_id)
        def cancel():
            simics.SIM_delete_breakpoint(bp_id)
            simics.SIM_hap_delete_callback_obj_id("Core_Breakpoint_Memop",
                                                  self.obj, hap_id)
        return object_handle(self.obj, cancel)

    def exec_context(self):
        return CellContext(self.obj)


@dataclass
class MemoryReadData:
    initiator: Optional[simics.conf_object_t]
    address: int
    size: int


class MemoryRead(_MemoryAccess):
    '''Yield a value when memory is read from a given address in a memory space.
    The value describes the matching transaction and has three members:
    `initiator: Optional(conf_object_t)`, `address: int` and `size:
    int`.'''
    def __init__(self, mem: simics.conf_object_t, address: int, length: int):
        '''Capture all read transactions on memory-space `mem`, that overlap
        with the interval defined by `address` and `length`.'''
        super().__init__(mem, address, length)
    access = simics.Sim_Access_Read
    @staticmethod
    def _decode_memop(memop):
        return MemoryReadData(
            initiator=simics.SIM_get_mem_op_initiator(memop),
            address=simics.SIM_get_mem_op_physical_address(memop),
            size=simics.SIM_get_mem_op_size(memop))

@dataclass
class MemoryWriteData:
    initiator: Optional[simics.conf_object_t]
    address: int
    value: bytes


class MemoryWrite(_MemoryAccess):
    '''Yield a value when memory is written to a given address in a memory space.
    The value describes the matching transaction and has three members:
    `initiator: Optional(conf_object_t)`, `address: int` and `value:
    bytes`.'''
    def __init__(self, obj: simics.conf_object_t, address: int, length: int):
        '''Capture all write transactions on memory-space `obj`, that overlap
        with the interval defined by `address` and `length`.'''
        super().__init__(obj, address, length)
    access = simics.Sim_Access_Write
    @staticmethod
    def _decode_memop(memop):
        return MemoryWriteData(
            initiator=simics.SIM_get_mem_op_initiator(memop),
            address=simics.SIM_get_mem_op_physical_address(memop),
            value=bytes(simics.SIM_get_mem_op_value_buf(memop)))


@dataclass
class MemoryExecuteData:
    initiator: Optional[simics.conf_object_t]
    address: int
    size: int


class MemoryExecute(_MemoryAccess):
    '''Yield a value when an instruction is fetched from a given
    location. The value describes the matching transaction and has
    three members: `initiator: Optional(conf_object_t)`, `address:
    int` and `size: int`.'''
    def __init__(self, obj: simics.conf_object_t, address: int, length: int):
        '''Capture all instruction fetch transactions on memory-space
        `obj`, that overlap with the interval defined by `address`
        and `length`.'''
        super().__init__(obj, address, length)
    access = simics.Sim_Access_Execute
    @staticmethod
    def _decode_memop(memop):
        return MemoryExecuteData(
            initiator=simics.SIM_get_mem_op_initiator(memop),
            address=simics.SIM_get_mem_op_physical_address(memop),
            size=simics.SIM_get_mem_op_size(memop))


class TestMemoryAccess(unittest.TestCase):
    def test_memory_access(self):
        for cls in [MemoryRead, MemoryWrite, MemoryExecute]:
            with self.assertRaises(InvalidObjError):
                cls(conf.sim, 0, 4)
        mem = simics.SIM_create_object('set-memory', 'mem', value=0xfe)
        ms = simics.SIM_create_object('memory-space', 'ms',
                                      map=[[0, mem, 0, 0, 100]])
        try:
            calls = []
            def cb(data):
                calls.append(data)
            ref = weakref.ref(cb)
            snooper = MemoryRead(ms, 90, 20)
            self.assertEqual(snooper.exec_context(), CellContext(ms))
            handle = add_callback_simple(snooper, cb)
            self.assertEqual(calls, [])
            # normal read included
            ms.iface.memory_space.read(conf.sim, 90, 2, False)
            # access outside breakpoint ignored
            ms.iface.memory_space.read(None, 89, 1, False)
            # overlapping access included
            ms.iface.memory_space.read(None, 88, 4, False)
            # inquiry access ignored
            ms.iface.memory_space.read(None, 91, 2, True)
            # write access ignored
            ms.iface.memory_space.write(None, 92, (0x47, 0x11), False)
            with self.assertRaises(simics.SimExc_Memory):
                # miss included
                ms.iface.memory_space.read(None, 100, 3, False)
            with self.assertRaises(simics.SimExc_Memory):
                # outside break interval excluded
                ms.iface.memory_space.read(None, 110, 1, False)
            self.assertEqual(calls, [
                MemoryReadData(initiator=conf.sim, address=90, size=2),
                MemoryReadData(initiator=None, address=88, size=4),
                MemoryReadData(initiator=None, address=100, size=3)])
            del calls[:]
            handle.cancel()
            del handle
            # no reference leak
            assert ref() is cb
            del cb
            self.assertIsNone(ref())
            # cancel did cause unregistration
            try:
                ms.iface.memory_space.read(None, 90, 2, False)
            except simics.SimExc_Memory: pass
            self.assertEqual(calls, [])

            # write works, and adds 'value' key to dict
            snooper = MemoryWrite(ms, 90, 20)
            def cb2(data):
                calls.append(data)
            handle = add_callback_simple(snooper, cb2)
            ms.iface.memory_space.write(None, 90, (0x47, 0x11), False)
            # read is ignored
            ms.iface.memory_space.read(None, 91, 2, False)
            with self.assertRaises(simics.SimExc_Memory):
                # miss is included
                ms.iface.memory_space.write(
                    None, 100, (0xde, 0xad, 0xbe, 0xef), False)
            self.assertEqual(calls, [
                MemoryWriteData(initiator=None, address=90, value=b'\x47\x11'),
                MemoryWriteData(initiator=None, address=100,
                     value=b'\xde\xad\xbe\xef')])
            del calls[:]
            handle.cancel()

            # execution triggered by sending a Fetch transaction
            # (incidentally, this also covers that a pure transaction_t
            # is captured)
            snooper = MemoryExecute(ms, 90, 20)
            handle = add_callback_simple(snooper, cb2)
            # normal fetch included
            t = simics.transaction_t(size=2, flags=simics.Sim_Transaction_Fetch)
            self.assertEqual(simics.SIM_issue_transaction(ms, t, 90),
                             simics.Sim_PE_No_Exception)
            self.assertEqual(t.data, b'\xfe\xfe')
            # non-fetch read ignored
            ms.iface.memory_space.read(conf.sim, 90, 2, False)
            # fetch miss included
            t = simics.transaction_t(size=3, flags=simics.Sim_Transaction_Fetch)
            self.assertEqual(simics.SIM_issue_transaction(ms, t, 100),
                             simics.Sim_PE_IO_Not_Taken)
            self.assertEqual(calls, [
                MemoryExecuteData(initiator=None, address=90, size=2),
                MemoryExecuteData(initiator=None, address=100, size=3)])
            del calls[:]
            handle.cancel()
        finally:
            simics.SIM_delete_object(ms)
            simics.SIM_delete_object(mem)


@dataclass
class Global(Snooper):
    '''Wraps a snooper and raises its exec_context ta GlobalContext,
    by deferring callbacks into Global Context. The constructor has a
    single argument, the snooper to wrap.
    '''
    snooper: Snooper
    def add_callback(self, yield_value, yield_exc):
        stack = traceback.extract_stack()
        def wrapped_yield_value(arg):
            if simics.VT_is_oec_thread():
                yield_value(arg)
            else:
                run_alone(lambda: yield_value(arg), stack)
        def wrapped_yield_exc(exc):
            run_alone_or_now(yield_exc, exc)
        return self.snooper.add_callback(wrapped_yield_value,
                                         wrapped_yield_exc)
    def exec_context(self):
        return GlobalContext()


class TestGlobal(unittest.TestCase):
    def test(self):
        calls = []
        class MockHandle(Handle):
            def cancel(self):
                calls.append(self)
        @dataclass
        class MockSnooper(Snooper):
            exec_context: ExecContext
            def add_callback(self, cb, ctx):
                handle = MockHandle()
                calls.append((cb, ctx, handle))
                return handle
            def exec_context(self): return self.exec_context
        snooper = Global(MockSnooper(CellContext(None)))
        self.assertEqual(snooper.exec_context(), GlobalContext())
        class TestException(Exception): pass
        exc = TestException()
        def log(value):
            calls.append((simics.VT_is_oec_thread(), value))
        handle = add_callback_simple(snooper, log, yield_exc=log)
        [(cb, exc_cb, inner_handle)] = calls
        del calls[:]
        cb(simics.VT_is_oec_thread())
        exc_cb(exc)
        self.assertEqual(calls, [(True, True), (True, exc)])
        del calls[:]
        clk = simics.SIM_create_object('clock', None, freq_mhz=1)
        handles = []
        try:
            handles.append(add_callback_simple(
                Seconds(clk, 1.1),
                lambda _: cb(simics.VT_is_oec_thread())))
            handles.append(add_callback_simple(
                Seconds(clk, 1.2), lambda _: exc_cb(exc), yield_exc=log))
            simics.SIM_continue(1200010)
            self.assertEqual(calls, [(True, False), (True, exc)])
            del calls[:]
            handle.cancel()
            self.assertEqual(calls, [inner_handle])
            del calls[:]
        finally:
            for h in handles:
                h.cancel()
            simics.SIM_delete_object(clk)


def run_alone_or_now(fun, *args):
    if simics.VT_is_oec_thread():
        fun(*args)
    else:
        run_alone(lambda: fun(*args), traceback.extract_stack()[:-2])


class CompoundSnooper(Snooper):
    '''
    Abstract class for a snooper composed of multiple snoopers.
    Implements `exec_context()` and validates that
    constituent snoopers cannot issue callbacks concurrently.

    The `add_callback` method is kept abstract.
    '''
    def __init__(self, snoopers: list[Snooper]):
        '''`snoopers` is the list of subordinate snoopers, stored in
        `self.snoopers`. Raises an exception if these belong to incompatible
        execution contexts; in particular, if one snooper belongs to a
        different cell, then it needs to be wrapped in a `Global` snooper.'''
        cells = {}
        for snooper in snoopers:
            ctx = snooper.exec_context()
            if isinstance(ctx, CellContext):
                if ctx.cell is None and None in cells:
                    raise Error(
                        'Compound snooper may not combine two snoopers'
                        ' called in CellContext(None):'
                        f' {snooper}, {cells[None]}.'
                        ' Consider wrapping snoopers in Global.')
                cells[ctx.cell] = snooper
            elif isinstance(ctx, ThreadedContext):
                raise Error(
                    'Compound snooper may not contain a'
                    f'snooper called in Threaded Context: {snooper}.'
                    'Consider wrapping snoopers in Global.')
        if len(cells) > 1:
            c = list(cells)
            raise Error(
                'Cannot combine snoopers across simulation cells:'
                f' {cells[c[0]]} in cell {c[0]}),'
                f' {cells[c[1]]} in cell {c[1]}).'
                f' Consider wrapping snoopers in Global.')
        self._exec_context = (
            CellContext(list(cells)[0]) if cells else GlobalContext())
        self.snoopers = snoopers
    def exec_context(self):
        return self._exec_context


class TestCompoundSnooper(unittest.TestCase):
    def test(self):
        [cell0, cell1] = [simics.SIM_create_object('cell', f'mycell{i}')
                          for i in range(2)]
        try:
            class Comp(CompoundSnooper):
                def add_callback(*args): assert False
            @dataclass
            class Snp(Snooper):
                _exec_context: ExecContext
                def add_callback(*args): assert False
                def exec_context(self): return self._exec_context

            # cross-cell is generally unsafe
            with self.assertRaises(Error):
                Comp([Snp(CellContext(cell1)), Snp(CellContext(cell0))])
            # cell=None means we don't know from which cell calls happen,
            # so generally unsafe to combine other than with GlobalContext
            # snoopers
            with self.assertRaises(Error):
                Comp([Snp(CellContext(None)), Snp(CellContext(None))])
            with self.assertRaises(Error):
                Comp([Snp(CellContext(None)), Snp(CellContext(cell0))])
            # we conservatively reject snoopers with threaded context:
            # such snoopers are obscure and scary so we don't want to
            # provide any guarantees.
            with self.assertRaises(Error):
                Comp([Snp(ThreadedContext())])
            self.assertEqual(Comp([]).exec_context(), GlobalContext())
            self.assertEqual(
                Comp([Snp(GlobalContext()),
                      Snp(CellContext(None))]).exec_context(),
                CellContext(None))
            self.assertEqual(
                Comp([Snp(GlobalContext()),
                      Snp(CellContext(cell1)),
                      Snp(CellContext(cell1))]).exec_context(),
                CellContext(cell1))
        finally:
            simics.SIM_delete_objects([cell0, cell1])


class Sequence(CompoundSnooper):
    '''Deliver a callback when all the given snoopers deliver a callback
    in order. The delivered callback's argument is a tuple of the respective
    values from the subordinate snoopers.
    The constructor is inherited from `CompoundSnooper`.'''
    def add_callback(self, cb, exc_cb):
        handle = self.Handle(cb, list(self.snoopers), [], [])
        for snooper in self.snoopers:
            handle.handles.append(
                snooper.add_callback(functools.partial(
                    handle.callback, snooper), exc_cb))
        return handle
    @dataclass
    class Handle(Handle):
        cb: callable
        snoopers: list
        handles: list
        acc: list
        def callback(self, snooper, arg):
            next_snooper = self.snoopers[len(self.acc)]
            if snooper is next_snooper:
                self.acc.append(arg)
                if len(self.acc) == len(self.snoopers):
                    seq = tuple(self.acc)
                    del self.acc[:]
                    self.cb(seq)
        def cancel(self):
            for handle in self.handles:
                handle.cancel()


class TestSequence(unittest.TestCase):
    def test_sequence(self):
        calls = []
        # TODO test with nontrivial ctx
        class MockSnooper(Snooper):
            def __init__(self):
                self.cbs = []
                self.handles = []
            class Handle(Handle):
                cancelled = []
                def cancel(self): self.cancelled.append(self)
            def add_callback(self, cb, exc_cb):
                self.cbs.append(cb)
                handle = MockSnooper.Handle()
                self.handles.append(handle)
                return handle
            def exec_context(self):
                return GlobalContext()
        snooper1 = MockSnooper()
        snooper2 = MockSnooper()
        snooper3 = MockSnooper()
        snooper = Sequence([snooper1, snooper2, snooper3])
        handle = snooper.add_callback(
            lambda arg: calls.append(arg), None)
        ([cb1], [cb2], [cb3]) = (snooper1.cbs, snooper2.cbs, snooper3.cbs)
        ([handle1], [handle2], [handle3]) = (
            snooper1.handles, snooper2.handles, snooper3.handles)
        self.assertNotEqual(handle1, handle2)
        cb2(4)
        cb3(5)
        cb2(6)
        cb1(7)
        cb2(8)
        cb1(9)
        self.assertEqual(calls, [])
        cb3(10)
        self.assertEqual(calls, [(7, 8, 10)])
        del calls[:]
        cb1(11)
        cb2(12)
        cb3(13)
        self.assertEqual(calls, [(11, 12, 13)])
        del calls[:]
        # disposal propagates
        handle.cancel()
        self.assertEqual(set(snooper1.Handle.cancelled),
                         {handle1, handle2, handle3})

        # callback triggers subordinate snoopers
        def cb(arg):
            calls.append(arg)
            cb1('rec1')
            cb2('rec2')
        (snooper1.cbs, snooper2.cbs, snooper3.cbs) = ([], [], [])
        handle = snooper.add_callback(cb, None)
        ([cb1], [cb2], [cb3]) = (snooper1.cbs, snooper2.cbs, snooper3.cbs)
        cb1(14)
        cb2(15)
        cb3(16)
        self.assertEqual(calls, [(14, 15, 16)])
        del calls[:]
        cb3(17)
        self.assertEqual(calls, [('rec1', 'rec2', 17)])
        del calls[:]
        handle.cancel()


class Filter(Snooper[T]):
    '''Wraps a snooper and selectively yields the values yielded by the
    wrapped snooper.'''
    def __init__(self, predicate: Callable[[T], bool], snooper: Snooper[T]):
        '''Whenever the wrapped snooper yields, the function
        `predicate` is called on the result, and the value is yielded only if
        the predicate returns `True`.'''
        self.predicate = predicate
        self.snooper = snooper
    def add_callback(self, cb, exc_cb):
        def filtered(arg):
            try:
                ok = self.predicate(arg)
            except Exception as e:
                exc_cb(e)
            else:
                if ok:
                    cb(arg)
        return self.snooper.add_callback(filtered, exc_cb)
    def exec_context(self):
        return self.snooper.exec_context()


class TestFilter(unittest.TestCase):
    def test_filter(self):
        calls = []
        test_exc = Exception('test')
        class MockSnooper(Snooper):
            class Handle(Handle):
                def cancel(self): calls.append(('cancel', self))
            def add_callback(self, cb, exc_cb):
                handle = self.Handle()
                calls.append((cb, exc_cb, handle))
                return handle
            def exec_context(self):
                return ThreadedContext()
        def pred(arg):
            calls.append(('filter', arg))
            return cond

        self.assertEqual(Filter(pred, MockSnooper()).exec_context(),
                         ThreadedContext())
        handle = Filter(pred, MockSnooper()).add_callback(
            lambda arg: calls.append(('cb', arg)),
            lambda exc: calls.append(('exc', exc)))
        [(cb, exc_cb, inner_handle)] = calls
        del calls[:]
        cond = False
        cb(1)
        # emulate an exception signalled by the inner snooper
        exc_cb(test_exc)
        cond = True
        cb(2)
        exc_cb(test_exc)
        self.assertEqual(
            calls, [('filter', 1), ('exc', test_exc),
                 ('filter', 2), ('cb', 2), ('exc', test_exc)])
        del calls[:]
        handle.cancel()
        self.assertEqual(calls, [('cancel', inner_handle)])
        del calls[:]

        class Exc(Exception): pass
        exc = Exc()
        def bad_pred(arg):
            raise exc
        handle = Filter(bad_pred, MockSnooper()).add_callback(
            lambda _: None, calls.append)
        [(cb, exc_cb, inner_handle)] = calls
        del calls[:]
        cb(5)
        self.assertEqual(calls, [exc])
        del calls[:]
        handle.cancel()


class Map(Snooper[T2]):
    '''Snooper equivalent of `builtins.map`: Wraps a snooper and
    transform every yielded value. Exceptions remain unchanged.'''
    def __init__(self, function: Callable[[T1], T2], snooper: Snooper[T1]):
        '''Whenever the wrapped snooper yields a value `v1`,
        this snooper yields `function(v1)`.'''
        self.function = function
        self.snooper = snooper
    def add_callback(self, cb, exc_cb):
        def transformed(arg):
            try:
                value = self.function(arg)
            except Exception as e:
                exc_cb(e)
            else:
                cb(value)
        return self.snooper.add_callback(transformed, exc_cb)
    def exec_context(self):
        return self.snooper.exec_context()


class TestMap(unittest.TestCase):
    def test_map(self):
        calls = []
        test_exc = Exception('test')
        @dataclass
        class MockSnooper(Snooper):
            class Handle(Handle):
                def cancel(self): calls.append(('cancel', self))
            handle: Handle
            def add_callback(self, cb, exc_cb):
                calls.append(('add_callback', cb, exc_cb))
                return self.handle
            def exec_context(self):
                return ThreadedContext()
        @dataclass
        class Wrap:
            sub: object
        def fun(sub):
            calls.append(('fun', sub))
            return Wrap(sub)

        self.assertEqual(Map(fun, MockSnooper(None)).exec_context(),
                         ThreadedContext())
        inner_handle = MockSnooper.Handle()
        handle = Map(fun, MockSnooper(inner_handle)).add_callback(
            lambda arg: calls.append(('cb', arg)),
            lambda exc: calls.append(('exc', exc)))
        [(tag, *args)] = calls
        del calls[:]
        self.assertEqual(tag, 'add_callback')
        (cb, exc_cb) = args
        cb(1)
        # emulate an exception signalled by the inner snooper
        exc_cb(test_exc)
        cb(2)
        exc_cb(test_exc)
        self.assertEqual(
            calls, [('fun', 1), ('cb', Wrap(1)), ('exc', test_exc),
                    ('fun', 2), ('cb', Wrap(2)), ('exc', test_exc)])
        del calls[:]
        handle.cancel()
        self.assertEqual(calls, [('cancel', inner_handle)])
        del calls[:]

        class Exc(Exception): pass
        exc = Exc()
        def bad_fun(arg):
            raise exc
        inner_handle = MockSnooper.Handle()
        handle = Filter(bad_fun, MockSnooper(inner_handle)).add_callback(
            lambda exc: None, calls.append)
        [(tag, cb, exc_cb)] = calls
        self.assertEqual(tag, 'add_callback')
        del calls[:]
        cb(5)
        self.assertEqual(calls, [exc])
        del calls[:]
        handle.cancel()


class Accumulate(Snooper[T]):
    '''Snooper equivalent of `itertools.accumulate`: Accumulate yielded
    values from one snooper by consecutively applying a binary function,
    and yield each intermediate result. Exceptions remain unchanged.
    '''
    class Sentinel: pass
    sentinel = Sentinel()
    def __init__(self, snooper: Snooper[T], func: Callable[[T, T], T]):
        '''Whenever the wrapped snooper yields a value `v1`,
        this snooper yields `transform(v1)`.'''
        self.func = func
        self.snooper = snooper
    def add_callback(self, cb, exc_cb):
        acc = self.sentinel
        def accumulate(arg):
            nonlocal acc
            if acc is self.sentinel:
                acc = arg
            else:
                try:
                    acc = self.func(acc, arg)
                except Exception as e:
                    exc_cb(e)
            cb(acc)
        return self.snooper.add_callback(accumulate, exc_cb)
    def exec_context(self):
        return self.snooper.exec_context()


class TestAccumulate(unittest.TestCase):
    def test_accumulate(self):
        calls = []
        test_exc = Exception('test')
        @dataclass
        class MockSnooper(Snooper):
            class Handle(Handle):
                def cancel(self): calls.append(('cancel', self))
            handle: Handle
            def add_callback(self, cb, exc_cb):
                calls.append(('add_callback', cb, exc_cb))
                return self.handle
            def exec_context(self):
                return ThreadedContext()
        @dataclass
        class Binop:
            lh: object
            rh: object
        def fun(lh, rh):
            calls.append(('fun', lh, rh))
            return Binop(lh, rh)

        self.assertEqual(Accumulate(MockSnooper(None), fun).exec_context(),
                         ThreadedContext())
        inner_handle = MockSnooper.Handle()
        handle = Accumulate(MockSnooper(inner_handle), fun).add_callback(
            lambda arg: calls.append(('cb', arg)),
            lambda exc: calls.append(('exc', exc)))
        [(tag, *args)] = calls
        del calls[:]
        self.assertEqual(tag, 'add_callback')
        (cb, exc_cb) = args
        cb(1)
        # emulate an exception signalled by the inner snooper
        exc_cb(test_exc)
        cb(2)
        cb(3)
        exc_cb(test_exc)
        self.assertEqual(
            calls, [('cb', 1), ('exc', test_exc),
                    ('fun', 1, 2), ('cb', Binop(1, 2)),
                    ('fun', Binop(1, 2), 3), ('cb', Binop(Binop(1, 2), 3)),
                    ('exc', test_exc),])
        del calls[:]
        handle.cancel()
        self.assertEqual(calls, [('cancel', inner_handle)])
        del calls[:]

        class Exc(Exception): pass
        exc = Exc()
        def bad_fun(arg):
            raise exc
        inner_handle = MockSnooper.Handle()
        handle = Filter(bad_fun, MockSnooper(inner_handle)).add_callback(
            lambda exc: None, calls.append)
        [(tag, *args)] = calls
        del calls[:]
        self.assertEqual(tag, 'add_callback')
        (cb, exc_cb) = args
        cb(5)
        self.assertEqual(calls, [exc])
        del calls[:]
        handle.cancel()


class Any(CompoundSnooper):
    '''Deliver a callback when any of the given callbacks are
    delivered.  The delivered value is a pair, (triggered Snooper
    object, value from subordinate snooper). Exceptions are propagated
    unchanged. The constructor is inherited from `CompoundSnooper`.'''
    def __str__(self):
        return "any of " + ", ".join(f"({snooper})"
                                     for snooper in self.snoopers)
    def add_callback(self, cb, exc_cb):
        def wrap_callback(cb, snooper):
            return lambda arg: cb((snooper, arg))
        return Any.Handle(
            [snooper.add_callback(wrap_callback(cb, snooper), exc_cb)
             for snooper in self.snoopers])
    @dataclass
    class Handle(Handle):
        handles: list
        def cancel(self):
            for handle in self.handles:
                handle.cancel()


class TestAny(unittest.TestCase):
    def test_any(self):
        calls = []
        test_exc = Exception('test')
        class MockSnooper(Snooper):
            def __init__(self):
                self.cbs = []
            class Handle(Handle):
                cancelled = []
                def cancel(self): self.cancelled.append(self)
            def add_callback(self, cb, exc_cb):
                handle = MockSnooper.Handle()
                self.cbs.append((cb, exc_cb, handle))
                return handle
            def exec_context(self):
                return GlobalContext()
        snooper1 = MockSnooper()
        snooper2 = MockSnooper()
        handle = Any([snooper1, snooper2]).add_callback(
            calls.append, calls.append)
        [(cb1, exc_cb1, handle1)] = snooper1.cbs
        [(cb2, exc_cb2, handle2)] = snooper2.cbs
        self.assertNotEqual(handle1, handle2)
        cb1(4)
        self.assertEqual(calls, [(snooper1, 4)])
        del calls[:]
        cb2(5)
        self.assertEqual(calls, [(snooper2, 5)])
        del calls[:]
        exc_cb1(test_exc)
        self.assertEqual(calls, [test_exc])
        del calls[:]
        exc_cb2(test_exc)
        self.assertEqual(calls, [test_exc])
        del calls[:]
        # disposal propagates
        handle.cancel()
        self.assertEqual(set(snooper1.Handle.cancelled), {handle1, handle2})

class AnyObject(Any, Snooper[tuple[simics.conf_object_t, T]]):
    '''Applies a snooper recursively to a set of objects.

    The value passed to the callback is a pair: the first element is the
    object passed to `make_snooper`, the second element is the value produced
    by the snooper returned by `make_snooper`.

    For instance, the snooper `AnyObject(lambda o: DeviceAttribute(o, 'foo'))`
    yields pairs `(obj, value)` whenever the value of any attribute named
    `foo` changes, in any device.
    '''
    def __init__(self, make_snooper: Callable[[simics.conf_object_t], Snooper[T]],
                 *, objs: list[simics.conf_object_t]=None,
                 root: simics.conf_object_t=None):
        '''The set of
        objects is either specified as a list in the `objs` argument, or
        as a full subtree using the `root` argument. If both `objs` and `root`
        are `None`, then all objects in the configuration are considered.
        `make_snooper` is a
        function that produces a `Snooper` from an object, e.g. `lambda obj:
        Notifier(obj, 'my-notifier')`. If `objs` is provided,
        all objects must be valid and any `InvalidObjError` exception
        is propagated; if `root` is provided, or both `objs` and `root`
        are `None`, then the
        `make_snooper` function may raise `InvalidObjError` to signal that an
        object should be excluded. Standard snooper constructors raise this
        exception automatically when encountering an incompatible object.'''
        assert objs is None or root is None
        if objs is not None:
            snooper_objs = {make_snooper(obj): obj for obj in objs}
        else:
            objs = (simics.SIM_object_iterator(None) if root is None
                    else [root] + list(simics.SIM_object_iterator(root)))
            def traverse():
                for obj in objs:
                    try:
                        yield (make_snooper(obj), obj)
                    except InvalidObjError:
                        pass
            snooper_objs = dict(traverse())

        self.snooper_objs = snooper_objs
        super().__init__(list(snooper_objs))
    def add_callback(self, cb, exc_cb):
        def wrapper(value):
            (snooper, arg) = value
            cb((self.snooper_objs[snooper], arg))
        return super().add_callback(wrapper, exc_cb)


class TestAnyObject(unittest.TestCase):
    def test_recursive(self):
        calls = []
        class MockSnooper(Snooper):
            cbs = {}
            handles = {}
            class Handle(Handle):
                cancelled = set()
                def cancel(self):
                    assert self not in self.cancelled
                    self.cancelled.add(self)
            def add_callback(self, cb, exc_cb):
                handle = MockSnooper.Handle()
                self.cbs.setdefault(self, []).append((cb, handle))
                return handle
            def exec_context(self): return GlobalContext()
        names = ['barn', 'barn.cow', 'barn.horse']
        objs = [simics.SIM_create_object('namespace', name, [])
                for name in names]
        try:
            [barn, cow, horse] = objs
            snoopers = {o: MockSnooper() for o in objs + [conf.sim]}
            def f(obj):
                '''a typical predicate would blindly instantiate a snooper
                with some params; this emulates the same behaviour'''
                if obj in {barn, horse, conf.sim}:
                    return snoopers[obj]
                else:
                    raise InvalidObjError()
            snooper = AnyObject(f)
            handle = snooper.add_callback(
                lambda arg: calls.append(arg), None)
            self.assertEqual(
                MockSnooper.cbs.keys(),
                {snoopers[barn], snoopers[horse], snoopers[conf.sim]})
            handle.cancel()
            self.assertEqual(MockSnooper.Handle.cancelled,
                             {handle for [(_, handle)]
                              in MockSnooper.cbs.values()})
            MockSnooper.cbs.clear()
            MockSnooper.Handle.cancelled.clear()

            snooper = AnyObject(f, objs=[horse, conf.sim])
            snooper.add_callback(lambda arg: None, None)
            self.assertEqual(MockSnooper.cbs.keys(),
                             {snoopers[horse], snoopers[conf.sim]})
            MockSnooper.cbs.clear()

            snooper = AnyObject(f, root=barn)
            handle = snooper.add_callback(lambda arg: calls.append(arg), None)
            self.assertEqual(
                MockSnooper.cbs.keys(), {snoopers[barn], snoopers[horse]})
            [(barn_cb, barn_handle)] = MockSnooper.cbs[snoopers[barn]]
            [(horse_cb, horse_handle)] = MockSnooper.cbs[snoopers[horse]]
            horse_cb(4)
            self.assertEqual(calls, [(horse, 4)])
            del calls[:]
            barn_cb(5)
            self.assertEqual(calls, [(barn, 5)])
            del calls[:]
            # cancellation propagates
            handle.cancel()
            self.assertEqual(MockSnooper.Handle.cancelled,
                             {barn_handle, horse_handle})
        finally:
            simics.SIM_delete_objects(objs)


class Latest(CompoundSnooper):
    '''Given a set of named snoopers, keeps track of the latest
    produced value from each one. Whenever one of the snoopers yields
    a value, this snooper yields an object composed of the latest
    values from all snoopers, accessed as object members. For
    instance, `Latest(x=X(), Y=Y())` would yield values `v` such that
    `v.x` and `v.y` contain the latest value of `X()` and `Y()`,
    respectively.
    '''
    def __init__(self, **snoopers):
        '''The keyword arguments specify the snoopers to combine.

        The produced tuple will contain `None` for snoopers that have not
        yet produced a value.'''
        super().__init__(list(snoopers.values()))
        self.snoopers_dict = snoopers
        self.polled = [(name, snooper) for (name, snooper) in snoopers.items()
                       if isinstance(snooper, Poll)]

    class LatestValue:
        def __init__(self, **args):
            for (key, value) in args.items():
                setattr(self, key, value)

    @dataclass
    class State:
        yield_value: callable
        state: dict[str, typing.Any]
        polled: list[(str, Poll)]
        def change(self, ident, arg):
            self.state[ident] = arg
            self.yield_value(Latest.LatestValue(**self.state))
        def poll(self, arg):
            changed = False
            for (name, snooper) in self.polled:
                new_value = snooper.poll()
                if self.state[name] != new_value:
                    self.state[name] = new_value
                    changed = True
            if changed:
                self.yield_value(Latest.LatestValue(**self.state))

    @dataclass
    class Handle(Handle):
        handles: list[Handle]
        def cancel(self):
            for h in self.handles:
                h.cancel()

    def add_callback(self, cb, ctx):
        state = self.State(
            cb,
            {name: s.poll() if isinstance(s, Poll) else None
             for (name, s) in self.snoopers_dict.items()},
            self.polled)
        return self.Handle([
            snooper.add_callback(
                state.poll if isinstance(snooper, Poll)
                else functools.partial(state.change, ident), ctx)
            for (ident, snooper) in self.snoopers_dict.items()])


class TestLatest(unittest.TestCase):
    def test_latest(self):
        calls = []
        test_exc = Exception('test')
        class MockSnooper(Snooper):
            def __init__(self):
                self.cbs = []
            class Handle(Handle):
                cancelled = []
                def cancel(self): self.cancelled.append(self)
            def add_callback(self, cb, exc_cb):
                handle = MockSnooper.Handle()
                self.cbs.append((cb, exc_cb, handle))
                return handle
            def exec_context(self):
                return GlobalContext()
        class MockPoll(Poll):
            def __init__(self):
                self.value = None
                self.sub = MockSnooper()
                super().__init__(self.sub)
            def poll(self):
                return self.value

        snooper1 = MockSnooper()
        snooper2 = MockSnooper()
        snooper = Latest(s1=snooper1, s2=snooper2)
        self.assertEqual(snooper.exec_context(), GlobalContext())
        handle = snooper.add_callback(calls.append, calls.append)
        [(cb1, exc_cb1, handle1)] = snooper1.cbs
        [(cb2, exc_cb2, handle2)] = snooper2.cbs
        del snooper1.cbs[:]
        del snooper2.cbs[:]
        self.assertNotEqual(handle1, handle2)
        cb1(4)
        [v] = calls
        self.assertEqual((v.s1, v.s2), (4, None))
        del calls[:]
        cb2(5)
        [v] = calls
        self.assertEqual((v.s1, v.s2), (4, 5))
        del calls[:]
        exc_cb1(test_exc)
        self.assertEqual(calls, [test_exc])
        del calls[:]
        exc_cb2(test_exc)
        self.assertEqual(calls, [test_exc])
        del calls[:]
        # disposal propagates
        handle.cancel()
        self.assertEqual(set(snooper1.Handle.cancelled), {handle1, handle2})
        del snooper1.Handle.cancelled[:]

        poll1 = MockPoll()
        poll1.value = 3
        poll2 = MockPoll()
        poll2.value = 4
        snooper3 = MockSnooper()
        latest = Latest(p1=poll1, p2=poll2, s=snooper3)
        handle = latest.add_callback(calls.append, calls.append)
        [(cb1, _, handle1)] = poll1.sub.cbs
        [(cb2, _, handle2)] = poll2.sub.cbs
        [(cb3, _, handle3)] = snooper3.cbs
        poll1.value = 5
        cb3(6)
        [v] = calls
        del calls[:]
        # poll1 changed state without its subordinate snooper
        # yielding, so not yet visible, but the initial values of both
        # poll1 and poll2 are visible in the yielded value.
        self.assertEqual((v.p1, v.p2, v.s), (3, 4, 6))
        cb1(None)
        [v] = calls
        del calls[:]
        # state is updated after a late yield from subordinate snooper
        self.assertEqual((v.p1, v.p2, v.s), (5, 4, 6))
        poll1.value = 7
        poll2.value = 8
        cb1(None)
        # if two Poll snoopers change state simultaneously, both changes
        # are captured when one of them yields.
        [v] = calls
        del calls[:]
        self.assertEqual((v.p1, v.p2, v.s), (7, 8, 6))
        cb2(None)
        self.assertEqual(calls, [])
        handle.cancel()
        self.assertEqual(MockSnooper.Handle.cancelled,
                         [handle1, handle2, handle3])


print("Enabling Snoop Technology Preview.")
