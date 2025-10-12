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

import os, socket, inspect, json, threading, sys, time
import conf
import simics
from simicsutils.host import is_windows
from getpass import getuser
import stat

def ipc_path(path=None):
    suffix = os.getenv("SIMICS_CONTROLLER_SUFFIX", "")
    # Out of an abundance of caution we don't want to trust the environment
    # variable to affect the controller path except in our CI.
    # getfqdn can take several seconds, so only run it when needed.
    if suffix and not socket.getfqdn().endswith('igk.intel.com'):
        suffix = ""
    if path is None:
        if is_windows():
            path = f"simics-controller-{getuser()}{suffix}"
        else:
            # This defines socket path, so it must be hard coded to make
            # the definition clear, hence ignore the Bandit problem.
            path = f"/tmp/.simics-controller-{os.getuid()}/controller{suffix}" # nosec
    if is_windows():
        path = rf'\\.\pipe\{path}'
    return path

def check_pipe_owner(pipe):
    import win32api
    import win32pipe
    import win32process
    import win32security

    # Obtain handles of current and pipe owner processes
    curProc = win32api.OpenProcess(
        0x400, 0, win32process.GetCurrentProcessId())
    otherProc = win32api.OpenProcess(
        0x400, 0, win32pipe.GetNamedPipeServerProcessId(pipe))

    sids = []
    for p in (curProc, otherProc):
        token = win32security.OpenProcessToken(p, win32security.TOKEN_QUERY)

        # Obtain SID of the corresponding users
        (sid, _) = win32security.GetTokenInformation(
            token, win32security.TokenUser)
        sids.append(sid)
        win32api.CloseHandle(token)
        win32api.CloseHandle(p)

    return sids[0] == sids[1]

def close_and_log_error(sock, msg=""):
    try:
        sock.close()
    except Exception as ex:
        print(f"{str(ex)}{': ' if msg else ''}{msg}", file=sys.stderr)

class PipeSocket:
    __slots__ = ("pipe", "read_event", "write_event", "overlapped", "data")
    def __init__(self, pipe_name, buf_size=1024):
        import win32file
        import win32event
        import pywintypes

        # Connect to named pipe
        try:
            self.pipe = win32file.CreateFile(
                pipe_name, win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0, None, win32file.OPEN_EXISTING,
                win32file.FILE_FLAG_OVERLAPPED, None)
            if self.pipe == win32file.INVALID_HANDLE_VALUE:
                raise ConnectionRefusedError
        except pywintypes.error:
            raise ConnectionRefusedError

        # Create event for notifications
        self.read_event = win32event.CreateEvent(None, True, False, None)
        self.write_event = win32event.CreateEvent(None, True, False, None)
        assert(self.read_event != None)
        self.overlapped = win32file.OVERLAPPED()

        # Buffer for read operations
        self.data = win32file.AllocateReadBuffer(buf_size)
        # Start asynchronous read
        self._read()

    def _read(self):
        import win32file
        self.overlapped.Offset = 0
        self.overlapped.OffsetHigh = 0
        self.overlapped.hEvent = self.read_event
        win32file.ReadFile(self.pipe, self.data, self.overlapped)

    def sendall(self, data):
        import win32file
        import win32event
        overlapped = win32file.OVERLAPPED()
        overlapped.Offset = 0
        overlapped.OffsetHigh = 0
        overlapped.hEvent = self.write_event
        # Must use overlapped since pipe opened with that flag
        win32file.WriteFile(self.pipe, data, overlapped)
        # Wait for write to finish
        win32file.GetOverlappedResult(self.pipe, overlapped, True)
        win32event.ResetEvent(self.write_event)

    def recv(self, size):
        import win32file
        # Get data from latest read
        num_bytes = win32file.GetOverlappedResult(self.pipe,
                                                  self.overlapped, False)
        data = bytes(self.data[:min(size, num_bytes)])
        # Start next read
        self._read()
        return data

    def close(self):
        self.read_event.Close()
        self.write_event.Close()
        self.pipe.Close()

class Controller:
    __slots__ = ("_parent", "_lock", "_canceled", "_data", "_sock", "_handler")
    def __init__(self, parent, sock, handler):
        # Never changes after construction
        self._parent = parent
        self._sock = sock
        self._handler = handler

        self._lock = threading.Lock()
        # Protected by the lock
        self._canceled = False

        # Only one _on_data callback active at a time
        self._data = b""

        if is_windows():
            simics.SIM_notify_on_object(int(sock.read_event), 1,
                                        self._on_data, None)
        else:
            simics.SIM_notify_on_socket(sock.fileno(),
                                        simics.Sim_NM_Read, 1,
                                        self._on_data, None)

    def cancel(self, reconnect=True):
        def on_cancel(unused):
            if is_windows():
                simics.SIM_notify_on_object(int(self._sock.read_event),
                                            1, None, None)
            else:
                fd = self._sock.fileno()
                simics.SIM_notify_on_socket(fd, simics.Sim_NM_Read,
                                            1, None, None)
                self._sock.shutdown(socket.SHUT_RDWR)
            close_and_log_error(self._sock, "Controller.cancel.on_cancel")
        with self._lock:
            if not self._canceled:
                simics.SIM_thread_safe_callback(on_cancel, None)
                self._canceled = True
        if reconnect:
            # Make parent re-connect
            self._parent.connect(True)

    def send(self, cmd, info):
        # TODO For performance it would be better to do this in the worker
        # thread, but then the locking must be done there as well,
        # which complicates matters.
        msg = json.dumps([cmd, info]).encode() + b"\n"
        def sendall(msg):
            try:
                self._sock.sendall(msg)
            except Exception:
                # TODO: Log errors other than sendall to closed socket?
                self.cancel()
        # TODO For performance it would be better to have one thread running
        # as long as possible, but this complicates the locking scheme.
        simics.SIM_run_in_thread(sendall, msg)

    def _on_data(self, unused):
        try:
            d = self._sock.recv(1024)
            if not d:
                self.cancel()
        except Exception:
            # TODO: Log errors other than recv from closed socket?
            self.cancel()
        else:
            if d:
                self._data += d
                self._parse()

    def _parse(self):
        while True:
            ind = self._data.find(b"\n")
            if ind == -1:
                break
            else:
                d = self._data[:ind]
                self._data = self._data[ind + 1:]
                req = json.loads(d)
                simics.SIM_thread_safe_callback(self._handler, req)


def setup_connection(path):
    def _init_socket(path):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(path)
        except (ConnectionRefusedError, FileNotFoundError, PermissionError):
            close_and_log_error(
                sock, f"setup_connection._init_socket: '{str(path)}'")
            sock = None
        return sock

    def _init_pipe(path):
        try:
            sock = PipeSocket(path)
        except ConnectionRefusedError:
            sock = None
        else:
            if not check_pipe_owner(sock.pipe):
                close_and_log_error(
                    sock, f"setup_connection._init_pipe: '{str(path)}'")
                sock = None
        return sock

    if is_windows():
        return _init_pipe(path)
    else:
        return _init_socket(path)


class SessionServer:
    __slots__ = ("_controller", "_session_id", "_state", "_state_delta",
                 "_handlers", "_path", "_lock")

    def __init__(self, path=None, connect=None):
        self._path = ipc_path(path)
        # Only accessed from Global Context
        self._handlers = []

        self._lock = threading.Lock()
        self._controller = None
        self._session_id = None
        self._state = {
            "sim:simics": {
                "cwd": os.getcwd(),
                "pid": os.getpid(),
                "projectPath": conf.sim.project,
                "group": os.environ.get("SIMICS_CLIENT_GROUP", None),
            }
        }
        self._state_delta = {}

        if connect or not conf.sim.batch_mode:
            self.connect(True)

    def connect(self, retry=False):
        if not self._connect(None) and retry:
            simics.SIM_run_in_thread(self._try_connecting, None)

    def terminate(self):
        with self._lock:
            self._terminate()

    # Assumes self._lock held
    def _terminate(self):
        """Tear down connection to Simics controller."""
        assert self._lock.locked()
        self._controller.cancel(False)
        self._controller = None

    # Assumes Global Context
    def add_handler(self, handler):
        self._handlers.append(handler)

    def update_key(self, key, value):
        "Specify a new value for key"
        with self._lock:
            self._state[key] = value
            self._state_delta[key] = value
            self._send_update()

    def _connect(self, _unused):
        """Set up connection to Simics controller."""
        with self._lock:
            if self._controller:
                self._terminate()

            sock = setup_connection(self._path)
            if sock:
                self._controller = Controller(self, sock, self._handle_request_in_gc)
                self._send_create()
            return self._controller is not None

    def _try_connecting(self, _unused):
        with self._lock:
            controller = self._controller

        while controller is None:
            self._connect(None)
            time.sleep(1)
            with self._lock:
                controller = self._controller

    # Assumes Global Context
    def _handle_request_in_gc(self, req):
        (cmd, info) = req
        if cmd == "create":
            with self._lock:
                self._handle_create(info.get("id"))
        elif cmd == "command" and info.get("cmd") == "run-command":
            simics.SIM_run_command(info.get("command"))
        elif cmd == "command":
            self._handle_command_in_gc(info)
        elif cmd == "error":
            print("session-server:", info, file=sys.stderr)
        elif cmd == "info":
            return
        else:
            print("REQUEST:unknown session-server request", req,
                  file=sys.stderr)

    # Assumes Global Context
    def _handle_command_in_gc(self, info):
        for func in self._handlers:
            func(info)

    # Assumes self._lock held
    def _handle_create(self, session_id):
        assert self._lock.locked()
        self._session_id = session_id
        # If we have accumulated state changes since we sent "create"
        # we need to send the deltas.
        if self._state_delta:
            self._send_update()

    # Assumes self._lock held
    def _send_update(self):
        assert self._lock.locked()
        if self._controller and self._session_id is not None:
            self._controller.send(
                "update",
                {"id": self._session_id, "state": self._state_delta})
            self._state_delta.clear()

    # Assumes self._lock held
    def _send_create(self):
        assert self._lock.locked()
        # Clear the delta since we now send the full state to the controller
        self._state_delta.clear()
        if self._controller:
            self._controller.send("create", {"state": self._state})

session = None

def init_session():
    global session
    session = SessionServer()

def VT_update_session_key(key, value):
    """Set data in Simics session.
    This sends the data to the simics-controller, if connected. Otherwise it
    will be sent upon connect.
    Can be called in any thread context."""
    session.update_key(key, value)

def VT_add_session_handler(handler):
    """Add handler for incoming Simics session data.
    The handler should take a single parameter, which will be the command
    info dictionary. All handlers are executed in Global Context.

    Should be called in Global Context only."""
    info = inspect.getframeinfo(inspect.currentframe())
    simics.VT_assert_outside_execution_context(
        info.function, info.filename, info.lineno)
    session.add_handler(handler)
