# © 2020 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import io
import json
import os
import select
import sys
import time
import traceback
from queue import Queue

RM_RESUME = 0
RM_STEP_OVER = 1
RM_STEP_INTO = 2
RM_STEP_OVER_LINE = 3
RM_STEP_INTO_LINE = 4
RM_STEP_OUT = 5
RM_REVERSE_RESUME = 6
RM_REVERSE_STEP_OVER = 7
RM_REVERSE_STEP_INTO = 8
RM_REVERSE_STEP_OVER_LINE = 9
RM_REVERSE_STEP_INTO_LINE = 10
RM_REVERSE_STEP_OUT = 11
RM_STEP_OVER_RANGE = 12
RM_STEP_INTO_RANGE = 13
RM_REVERSE_STEP_OVER_RANGE = 14
RM_REVERSE_STEP_INTO_RANGE = 15
RM_UNTIL_ACTIVE = 16
RM_REVERSE_UNTIL_ACTIVE = 17

# No documentation for the TCF message format has been found. From
# the code and Wireshark it appears as if the communication consists
# of a series of \x03\x01-terminated messages. Each message is a
# series of \x00-terminated chunks. \x03 bytes in messages are
# serialized as \x03\x00, and the \x00 here should not be interpreted
# as a message chunk delimiter.
ESC='\x03'
EOS='\x02'
EOM='\x01'
ZERO = '\x00'

# inserted everytime an end-of-stream marker appears
EOS_MSG = object()

class TCFClientError(Exception):
    pass

class TCFCommandNotUnderstood(TCFClientError):
    pass

class TCFCommandFailure(TCFClientError):
    pass

def ensure_binary(s, encoding='utf-8', errors='strict'):
    assert isinstance(s, (str, bytes))
    if isinstance(s, str):
        return s.encode(encoding, errors)
    else:
        return s

def ensure_text(s, encoding='utf-8', errors='strict'):
    assert isinstance(s, (str, bytes))
    if isinstance(s, bytes):
        return s.decode(encoding, errors)
    else:
        return s

def parser():
    """A generator that consumes byte-strings and produces lists of messages.

    Each time you send it a byte-string it will generate as many
    messages as possible. Any trailing bytes that did not form a
    complete message is used the next time you provide data."""
    messages = []
    s = io.StringIO()
    esc = False
    while True:
        data = yield messages
        data = ensure_text(data)
        messages = []
        for c in data:
            if esc:
                if c == ZERO:
                    s.write(ESC)
                elif c == EOM:
                    msg = s.getvalue()
                    if not msg.endswith(ZERO):
                        raise TCFClientError(
                            'Message not zero terminated: ' + msg)
                    messages.append(msg.split(ZERO)[:-1])
                    s = io.StringIO()
                elif c == EOS:
                    messages.append(EOS_MSG)
                else:
                    raise TCFClientError('Illegal escape')
                esc = False
            else:
                if c == ESC:
                    esc = True
                else:
                    s.write(c)

def parse_payload(payload):
    return json.loads(ensure_text(payload, encoding='utf-8'))

def serialize_payload(js):
    return json.dumps(js)

def serialize_message(m):
    return ensure_binary((ZERO.join(m) + ZERO).replace(ESC, ESC + ZERO)
                         + ESC + EOM)

class Logger:
    def __init__(self, logfile):
        self.log = open(logfile, 'w')

    def handle_in(self, msg):
        if msg is EOS_MSG:
            print('<- <<EOS>>', file=self.log)
        else:
            print(f'<-{msg}', file=self.log)
        self.log.flush()

    def handle_out(self, msg):
        print(f'->{msg}', file=self.log)
        self.log.flush()

    def annotate(self, msg):
        print(f'#{msg}', file=self.log)
        self.log.flush()


class OutstandingCommands:
    def __init__(self):
        self.outstanding_cmds = []

    def handle_out(self, msg):
        if not self._is_command(msg):
            return
        token = msg[1]
        self.outstanding_cmds.append(token)

    def handle_in(self, msg):
        if not self._is_reply(msg):
            return
        token = msg[1]
        self.outstanding_cmds.remove(token)

    def has_outstanding_commands(self):
        return len(self.outstanding_cmds) > 0

    def _is_reply(self, msg):
        if msg is EOS_MSG:
            return False
        if len(msg) <= 1:
            return False
        return msg[0] == 'R'

    def _is_command(self, msg):
        if msg is EOS_MSG:
            return False
        if len(msg) <= 1:
            return False
        return msg[0] == 'C'


class Connection:
    def __init__(self, host, port, logfile):
        import socket
        self.logger = Logger(logfile)
        self.outstanding = OutstandingCommands()
        self.listeners = [self.logger, self.outstanding]
        self.socket = socket.create_connection((host, port))
        self.is_connected = True
        self.parser = parser()
        next(self.parser) # Prime the generator
        self.send_event('Locator', 'Hello', ['Locator'])
        self.next_token = 0
        self.messages = []
        self.handler = lambda p, m: p(m)
        # IPv6 sockets have additional name data that we don't care about.
        (self.ip_addr, self.port) = self.socket.getsockname()[:2]
        self.annotate('Client %s:%s connected with %s:%s'
                      % (self.ip_addr, self.port, host, port))

    def disconnect(self):
        self.socket.close()
        self.is_connected = False

    def send_message(self, *args):
        for l in self.listeners:
            l.handle_out(args)
        self.socket.sendall(ensure_binary(serialize_message(args)))

    def send_command(self, service, name, *payload):
        ps = (serialize_payload(p) for p in payload)
        token = str(self.next_token)
        self.next_token += 1
        self.send_message('C', token, service, name, *ps)
        return token

    def send_event(self, service, name, *payload):
        ps = (serialize_payload(p) for p in payload)
        self.send_message('E', service, name, *ps)

    def _receive_messages(self, timeout, start):
        (rs, _, _) = select.select([self.socket], [], [], 1.0)
        if rs:
            data = rs[0].recv(8192)
            if len(data) == 0:
                raise TCFClientError('Connection closed')
            for m in self.parser.send(data):
                for l in self.listeners:
                    l.handle_in(m)
                if m is not EOS_MSG:
                    self.messages.append(m)
        if (time.time() - start) > timeout:
            raise TCFClientError('Timeout')

    def complete_commands(self, timeout=60):
        start = time.time()
        while self.outstanding.has_outstanding_commands():
            self._receive_messages(timeout, start)

    def run(self, predicate=lambda: False, timeout=90):
        start = time.time()
        while True:
            # First check the predicate as we can still have
            # unprocessed messages in the log
            for (i, m) in enumerate(self.messages):
                if self.handler(predicate, m):
                    self.messages = self.messages[i+1:]
                    return m
            self.messages = []
            self._receive_messages(timeout, start)

    def set_handler(self, handler):
        self.handler = handler

    def annotate(self, msg):
        self.logger.annotate(msg)


class TCF:
    def __init__(self, host, port, logfile):
        self.connection = Connection(host, port, logfile)

    def disconnect(self):
        self.connection.disconnect()

    def annotate(self, msg):
        self.connection.annotate(msg)

    def add_listener(self, listener):
        assert listener
        self.connection.listeners.append(listener)

    def run_until(self, pred, timeout=30):
        return self.connection.run(pred, timeout)

    def run_until_event(self, service, name, extra_pred=None, timeout=30):
        if not isinstance(name, list):
            name = [name]
        if extra_pred is None:
            extra_pred = lambda msg: True

        def pred(msg):
            if msg[0] != 'E':
                return False
            (_, s, n) = msg[:3]
            return s == service and n in name and extra_pred(msg)

        return self.run_until(pred, timeout)

    def run_until_reply(self, token, timeout=30):
        def pred(msg):
            if msg[0] not in ['R', 'N']:
                return False
            (_, msg_token) = msg[:2]
            return token == msg_token
        return self.run_until(pred, timeout)

    def verbose_print_sending(self, service, name, payload):
        def quote(s):
            return f"'{str(s)}'"
        cmd_str = ' '.join([quote(x) for x in (service, name)] + [
            quote(x) for x in list(payload)])
        print(f'Sending command: {cmd_str}')

    def verbose_print_reply(self, reply):
        print(f'Received reply:  {reply}')

    def command(self, service, name, *payload, **kwargs):
        """Send a command and wait for the reply.

        Returns the reply with the reply kind and token stripped.

        If kwargs contains a "timeout" keyword then that will be used as
        timeout for the run_until call."""
        verbose = kwargs.pop('verbose', False)
        if verbose:
            self.verbose_print_sending(service, name, payload)
        token = self.connection.send_command(service, name, *payload)
        timeout = kwargs.get("timeout")
        if (timeout):
            reply = self.run_until_reply(token, timeout)
        else:
            reply = self.run_until_reply(token)
        if verbose:
            self.verbose_print_reply(reply)
        if reply[0] == 'N':
            raise TCFCommandNotUnderstood(
                f'Command {service}.{name}{payload!r} not understood: {reply}')
        return reply[2:]

    def std_command(self, service, name, *payload, **kwargs):
        """Send a command with a standard reply and wait for the reply.

        Returns the reply payload or raise Exception if the reply
        contains an error message."""
        reply = self.command(service, name, *payload, **kwargs)
        (error, result) = (reply[0], reply[1:])
        if error not in ('', 'null'):
            raise TCFCommandFailure(f'Command {service}.{name}{payload!r}'
                                    f' failed: {error}',
                                    service, error, result)
        if not result or len(result) == 0:
            return None
        elif len(result) == 1:
            return parse_payload(result[0])
        else:
            return [parse_payload(r) for r in result]

    def resume(self, ctx, mode=RM_RESUME):
        """Resume ctx"""
        return self.std_command('RunControl', 'resume', ctx, mode, 1)

    def resume_and_wait(self, ctx, mode=RM_RESUME, reason=None, timeout=30):
        """Resume and wait for TCF to suspend"""
        self.resume(ctx, mode)

        def reason_pred(msg):
            if reason is None:
                return True
            return parse_payload(msg[5]) == reason

        return self.run_until_event('RunControl',
                                    ['contextSuspended', 'containerSuspended'],
                                    extra_pred = reason_pred,
                                    timeout=timeout)

    def suspend(self, ctx):
        return self.std_command('RunControl', 'suspend', ctx)

    def complete_commands(self, timeout=60):
        self.connection.complete_commands(timeout)
