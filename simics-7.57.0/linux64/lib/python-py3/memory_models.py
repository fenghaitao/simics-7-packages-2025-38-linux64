# © 2018 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import simics
import simics_common
import itertools
import unittest
import device_info
from types import SimpleNamespace

from map_commands import get_mapped_devices
from map_commands import probe_address

uint64_max = (1 << 64) - 1

def objectAndPort(d):
    if isinstance(d, list):
        return d
    else:
        return d, None

class Simics:
    """Wraps the Simics API functions used to make it easier to replace with
    a mock.
    """
    def isScripted(self):
        return simics_common.run_state.script_active

    def isRunning(self):
        return simics.SIM_simics_is_running()

    def getAllObjects(self):
        return list(simics.SIM_object_iterator(None))

    def getPortInterface(self, obj, name, port):
        return simics.SIM_get_port_interface(obj, name, port)

    def portImplementsInterface(self, dev, name):
        obj, port = objectAndPort(dev)
        try:
            self.getPortInterface(obj, name, port)
            # Got the interface, so it must be there
            return True
        except TypeError:
            # Not a conf_object_t
            return False
        except simics.SimExc_Lookup:
            # Interface not found
            return False
        except simics.SimExc_PythonTranslation:
            # Unable to wrap interface
            return True

    def addHapCallback(self, hap, callback):
        return simics.SIM_hap_add_callback(hap, lambda *a: callback(*a[1:]),
                                           None)

    def removeHapCallback(self, hap, hid):
        simics.SIM_hap_delete_callback(hap, hid, None)

defaultSimics = None
def getDefaultSimics():
    global defaultSimics
    if not defaultSimics:
        defaultSimics = Simics()
    return defaultSimics


class HapListenerMixin:
    def __getHids(self):
        try:
            return self.__hids
        except AttributeError:
            self.__hids = []
            return self.__hids

    def _registerHap(self, hap, handler):
        h = self.getSim().addHapCallback(hap, handler)
        self.__getHids().append((hap, h))

    def destroyHaps(self):
        for n, h in self.__getHids():
            self.getSim().removeHapCallback(n, h)

    def getSim(self):
        raise NotImplementedError

class ObservableMixin:
    def __getListeners(self, aspect):
        try:
            ls = self.__listeners
        except AttributeError:
            self.__listeners = {}
            ls = self.__listeners
        return ls.setdefault(aspect, [])

    def addListener(self, aspect, listener):
        """Add a listener for the given aspect. When the aspect is triggered
        the listener will be called with two arguments: the object it
        registered with and the aspect. The handler will be invoked in a
        simics thread, not the GUI thread.
        """
        self.__getListeners(aspect).append(listener)

    def removeListener(self, aspect, listener):
        """Remove an already registered listener. It is an error to remove
        a listener from an aspect it isn't already registered for.
        """
        self.__getListeners(aspect).remove(listener)

    def _signalAspect(self, aspect):
        for l in self.__getListeners(aspect):
            l(self, aspect)

###
### Memory viewer models
###
printable = list(range(32, 127))
def char(byte):
    if byte in printable:
        return chr(byte)
    return '.'

class ByteValue:
    def __init__(self, value):
        self.value = value

    def asHex(self):
        return '%02x' % self.value

    def asChar(self):
        return char(self.value)

    def getValue(self):
        return self.value

    def isSpecial(self):
        return False

class SpecialByteValue:
    def __init__(self, hex_str, char_str, description):
        self.hex_str = hex_str
        self.char_str = char_str
        self.description = description

    def asHex(self):
        return self.hex_str

    def asChar(self):
        return self.char_str

    def isSpecial(self):
        return True

    def getDescription(self):
        return self.description

noTranslationValue = SpecialByteValue('--', '.', 'No Translation')
outsideMemoryValue = SpecialByteValue('**', '.', 'Outside Memory')
noInquiryValue = SpecialByteValue('??', '.', 'Unknown')

specialByteValues = [noTranslationValue, outsideMemoryValue, noInquiryValue]

class Empty:
    """An empty memory model.
    """
    def getNumberOfBytes(self):
        return 0

    def getBytes(self, frm, length):
        return []

    def getName(self):
        return ''

    def destroyModel(self):
        pass

    def getSymbolAddress(self, sym):
        return None

emptyMemory = Empty()

class SimicsMemory:
    def __init__(self, name):
        self.name = name

    def getBytes(self, frm, length):
        return [self._getByte(addr) for addr in range(frm, frm + length)]

    def getName(self):
        return self.name

    def _getByte(self, addr):
        raise NotImplementedError

    def setByteValue(self, addr, value):
        raise NotImplementedError

class MemorySpaceModel(SimicsMemory):
    @staticmethod
    def canWrapObject(obj):
        return isSpaceObject(obj)

    def __init__(self, memories, mem):
        SimicsMemory.__init__(self, mem.name)
        self.mem = mem
        if hasattr(self.mem.iface, "memory_space"):
            self.iface = self.mem.iface.memory_space
        else:
            self.iface = self.mem.iface.port_space

    def getSimicsObject(self):
        return self.mem

    def getNumberOfBytes(self):
        if self.mem.default_target:
            return 2**64
        size = 0
        for m in self.mem.map:
            base = m[0]
            length = m[4]
            size = max(size, base + length)
        return size

    def _getByte(self, addr):
        try:
            # Use the read method since the memory attribute doesn't raise the
            # right exceptions
            [byte] = self.iface.read(None, addr, 1, True)
            return ByteValue(byte)
        except simics.SimExc_InquiryUnhandled:
            return noInquiryValue
        except simics.SimExc_Memory:
            return outsideMemoryValue

    def setByteValue(self, addr, value):
        try:
            self.iface.write(None, addr, (value,), True)
            return self.iface.read(None, addr, 1, True)[0]
        except simics.SimExc_InquiryUnhandled:
            pass
        except simics.SimExc_Memory:
            pass
        return -1

    def _getSymbols(self):
        for m in self.mem.map:
            base = m[0]
            obj = m[1]
            if isinstance(obj, list):
                yield obj[0].name, base
                yield obj[0].name + ':' + obj[1], base
            else:
                yield obj.name, base

    def getSymbolAddress(self, symbol):
        for sym, addr in self._getSymbols():
            if sym == symbol:
                return addr
        return None

def isSimicsProcessor(o):
    return hasattr(o.iface, 'processor_info')

def get_physical_memory(cpu):
    return cpu.iface.processor_info.get_physical_memory()

def get_port_memory(cpu):
    return cpu.port_space if hasattr(cpu, "port_space") else None

def get_cpu_mem(cpu, port_mem):
    return get_port_memory(cpu) if port_mem else get_physical_memory(cpu)

class CPUVirtualMemoryModel(SimicsMemory):
    @staticmethod
    def canWrapObject(obj):
        return isSimicsProcessor(obj)

    def __init__(self, memories, cpu):
        SimicsMemory.__init__(self, "%s's virtual memory" % cpu.name)
        self.cpu = cpu
        self.mem = memories._getModelForSimicsObject(get_physical_memory(cpu))

    def getNumberOfBytes(self):
        return 2**self.cpu.iface.processor_info.get_logical_address_width()

    def _getByte(self, vaddr):
        try:
            paddr = self._virtualToPhysical(vaddr)
        except simics.SimExc_Memory:
            return noTranslationValue
        return self.mem._getByte(paddr)

    def setByteValue(self, vaddr, value):
        try:
            paddr = self._virtualToPhysical(vaddr)
        except simics.SimExc_Memory:
            return -1
        return self.mem.setByteValue(paddr, value)

    def getSymbolAddress(self, sym):
        return None

    def getSimicsObject(self):
        return self.cpu

    def _virtualToPhysical(self, vaddr):
        if not hasattr(self.cpu.iface, 'processor_info'):
            raise simics.SimExc_Memory('missing interface')
        block = self.cpu.iface.processor_info.logical_to_physical(
            vaddr, simics.Sim_Access_Read)
        if not block.valid:
            raise simics.SimExc_Memory('invalid address')
        return block.address

    def destroyModel(self):
        self.mem.destroyModel()

class ScMemoryModel(SimicsMemory):
    @staticmethod
    def canWrapObject(obj):
        return hasattr(obj.iface, 'sc_memory_access')

    def __init__(self, memories, mem):
        SimicsMemory.__init__(self, mem.name)
        self.mem = mem
        self.iface = self.mem.iface.sc_memory_access

    def getNumberOfBytes(self):
        # The value is arbitrarily chosen as the size
        # of the memory is unknown
        return 2**32

    def _getByte(self, addr):
        b = simics.buffer_t(1)
        ex = self.iface.read(addr, b, True)
        if ex != simics.Sim_PE_No_Exception:
            return noInquiryValue
        return ByteValue(b[0])

    def setByteValue(self, addr, value):
        ex = self.iface.write(addr, bytes(value), True)
        if ex != simics.Sim_PE_No_Exception:
            return -1
        return self._getByte(addr)

    def getSymbolAddress(self, sym):
        return None

    def getSimicsObject(self):
        return self.mem

MEMORY_LIST_ASPECT = 'MemoryListAspect'
SIMULATION_STOPPED_ASPECT = 'SimulationStoppedAspect'
MAP_CHANGED_ASPECT = 'MapChangedAspect'
class SimicsMemoryListModel(HapListenerMixin, ObservableMixin):
    """Keeps track of all the memory models in Simics.
    """

    MODEL_MAKERS = [MemorySpaceModel, CPUVirtualMemoryModel, ScMemoryModel]

    def __init__(self, sim):
        self.sim = sim
        self.newMems = set()
        self.memories = {}
        self._registerHap('Core_Conf_Object_Create', self._onObjectCreated)
        self._registerHap('Core_Configuration_Loaded', self._onLoaded)
        self._registerHap('Core_Conf_Object_Delete', self._onObjectDeleted)
        self._registerHap('Core_Simulation_Stopped', self._onSimulationStopped)
        self._registerHap('Core_Memory_Space_Map_Changed',
                          self._onSpaceChanged)

    def _populateList(self):
        for o in self._getSimicsMemories():
            self._ensureObjectIsWrapped(o)

    def destroyModel(self):
        self.destroyHaps()
        for m in list(self.memories.values()):
            m.destroyModel()

    def _getModelsSortedByName(self):
        return sorted(list(self.memories.values()), key=lambda o: o.getName())

    def getAllObjects(self):
        return list(self.memories.values())

    def getObjectForIndex(self, idx):
        """Return the memory model object at the given index.

        The models are in the same order as the list of model names
        returned by getAllNames.
        """
        return self._getModelsSortedByName()[idx]

    def getAllNames(self):
        """Return a sequence with the names of all memory objects.
        """
        return [m.getName() for m in self._getModelsSortedByName()]

    def _makeMemoryFromSimicsObject(self, obj):
        return self._findModelMaker(obj)(self, obj)

    def _findModelMaker(self, obj):
        """Return the model maker for obj or None.
        """
        for mm in self.MODEL_MAKERS:
            if mm.canWrapObject(obj):
                return mm
        return None

    def _getSimicsMemories(self):
        """Return an iterable of all simics objects which can be wrapped into
        memory models.
        """
        return (o for o in self.sim.getAllObjects()
                if self._findModelMaker(o))

    def _ensureObjectIsWrapped(self, simObj):
        if not simObj in self.memories:
            self.memories[simObj] = self._makeMemoryFromSimicsObject(simObj)

    def _findWrappedObject(self, simObj):
        return self.memories.get(simObj, None)

    def _onObjectCreated(self, simObj):
        if self._findModelMaker(simObj):
            self.newMems.add(simObj)

    def _onLoaded(self, trigger):
        for simObj in self.newMems:
            self._ensureObjectIsWrapped(simObj)
        if self.newMems: self._signalAspect(MEMORY_LIST_ASPECT)
        self.newMems = set()

    def _onObjectDeleted(self, simObj, name):
        wrapped = self._findWrappedObject(simObj)
        if wrapped is None: return
        self.memories.remove(wrapped)
        self._signalAspect(MEMORY_LIST_ASPECT)

    def _onSimulationStopped(self, obj, exception, errorString):
        self._signalAspect(SIMULATION_STOPPED_ASPECT)

    def _onSpaceChanged(self, obj):
        if self.sim.isRunning(): return
        self._signalAspect(MAP_CHANGED_ASPECT)

    def getModelForSimicsObject(self, simObj):
        return self._getModelForSimicsObject(simObj)

    def _getModelForSimicsObject(self, simObj):
        self._ensureObjectIsWrapped(simObj)
        return self.memories[simObj]

    def getSim(self):
        return self.sim

def createSimicsMemoryListModel(sim):
    model = SimicsMemoryListModel(sim)
    # Populate the initial list of model after construction to avoid
    # infinite recursion
    model._populateList()
    return model

defaultSimicsMemoryListModel = None
def getDefaultSimicsMemoryListModel():
    global defaultSimicsMemoryListModel
    if not defaultSimicsMemoryListModel:
        defaultSimicsMemoryListModel = createSimicsMemoryListModel(
            getDefaultSimics())
    return defaultSimicsMemoryListModel


###
### Memory space tree
###

def isSpaceObject(obj):
    # This condition is not necessarily correct; it is a bit unclear
    # exactly what one expects from a memory-space-like device. See
    # bug 14820 and SIMICS-8965.
    return (obj
            and (hasattr(obj.iface, "memory_space")
                 or hasattr(obj.iface, "port_space"))
            and hasattr(obj, "map"))

class Mapping:
    def __init__(self, sim, device, function, offset, target):
        self.keys = {
            'base': self.getBase,
            'device': self.getDevice,
            'offset': self.getOffset,
            'length': self.getLength,
            'target': self.getTarget
            }
        self.sim = sim
        self.device = device
        self.function = function
        self.offset = offset
        self.target = target
        self.object, self.port = objectAndPort(self.device)
        self.target_object, self.target_port = objectAndPort(self.target)

    def isTargetMapping(self):
        return ((self.sim.portImplementsInterface(self.device, 'translate')
                 or self.sim.portImplementsInterface(self.device, 'bridge'))
                and isSpaceObject(self.target_object))

    def isSpaceMapping(self):
        return (self.sim.portImplementsInterface(self.device, 'memory_space')
                or self.sim.portImplementsInterface(self.device, 'port_space'))

    def get(self, key):
        return self.keys[key]()

    def getDevice(self):
        if self.port is not None:
            return '%s:%s' % (self.object.name, self.port)
        elif self.function != 0:
            return '%s:%d' % (self.object.name, self.function)
        else:
            return self.object.name

    def getDeviceId(self):
        return self.object.object_id

    def getOffset(self):
        return '0x%x' % self.offset

    def getTarget(self):
        if self.target_object is None:
            return ''
        elif self.target_port is None:
            return self.target.name
        else:
            return '%s:%s' % (self.target.name, self.target_port)

    def getTargetObject(self):
        if self.target_object is not None:
            return self.target_object
        else:
            return self.object

    def getBase(self):
        raise NotImplementedError

    def getLength(self):
        raise NotImplementedError

class MapMapping(Mapping):
    def __init__(self, sim, map_line):
        if len(map_line) == 5:
            map_line = map_line + [None]
        (base, device, function, offset, length, target) = map_line[0:6]
        Mapping.__init__(self, sim, device, function, offset, target)
        self.base = base
        self.length = length

    def getBase(self):
        return '0x%x' % self.base

    def getLength(self):
        return '0x%x' % self.length

class DefaultMapping(Mapping):
    def __init__(self, sim, default_target):
        (device, function, offset, target) = default_target[:4]
        Mapping.__init__(self, sim, device, function, offset, target)

    def getBase(self):
        return 'default'

    def getLength(self):
        return ''

class EmptyNode:
    def getName(self):
        return ''

    def getComponents(self):
        return []

    def getChildren(self):
        return []

    def getMap(self):
        return []

    def getFlatMap(self):
        return [], False

    def getProcessors(self, port_mem):
        return []

    def isEmptyNode(self):
        return True

emptyNode = EmptyNode()

class MemorySpaceNode:
    """A node in the tree of memory spaces. It wraps a Simics memory space.
    """
    def __init__(self, sim, obj):
        self.sim = sim
        self.obj = obj
        self.children = []
        self.processors = [[], []]

    def destroyModel(self):
        pass

    def _clearProcessors(self):
        self.processors = [[], []]

    def _addProcessor(self, processor, port_mem):
        self.processors[port_mem].append(processor)

    def _fillInChildren(self, spaces):
        self.children = [spaces[o] for o in self._generateSimicsChildren()]

    def _generateSimicsChildren(self):
        children = set()
        for m in self.getMap():
            if m.isTargetMapping():
                children.add(m.target)
            elif m.isSpaceMapping():
                children.add(m.device)
        return children

    def getChildren(self):
        return self.children

    def getMap(self):
        return list(self._generateMap())

    def _generateMap(self):
        for m in self.obj.map:
            yield MapMapping(self.sim, m)
        if self.obj.default_target != None:
            yield DefaultMapping(self.sim, self.obj.default_target)

    def getFlatMap(self):
        return get_mapped_devices()

    def getSimicsObject(self):
        return self.obj

    def getName(self):
        return self.obj.name

    def getComponents(self):
        componentChain = []
        comp = self.obj.component
        while comp is not None:
            componentChain.append([comp.name, comp.object_id])
            comp = comp.component
        return componentChain

    def getProcessors(self, port_mem):
        return self.processors[port_mem]

    def hasChildren(self):
        return bool(len(self.getChildren()))

    def _replaceChildWithTombstone(self, child):
        i = self.children.index(child)
        self.children[i] = TombstoneNode(child)

    def isEmptyNode(self):
        return False

class TombstoneNode:
    """A tombstone is a special node which is inserted into the graph to break
    cycles. It has no children, but the same other attributes as the node
    it replaces.
    """
    def __init__(self, realNode):
        self.realNode = realNode

    def destroyModel(self):
        pass

    def getName(self):
        return self.realNode.getName()

    def getComponents(self):
        return self.realNode.getComponents()

    def getProcessors(self, port_mem):
        return self.realNode.getProcessors(port_mem)

    def getChildren(self):
        return []

    def getMap(self):
        return self.realNode.getMap()

    def getFlatMap(self):
        return self.realNode.getFlatMap()

    def getSimicsObject(self):
        return self.realNode.getSimicsObject()

    def isEmptyNode(self):
        return False

class DummyObject:
    def __init__(self, name, object_id,  obj):
        self.name = name
        self.object_id = object_id
        self.component = obj

class Test_component_structure(unittest.TestCase):
    def test_return_no_component(self):
        dummy = DummyObject("dummy", "object", None)
        node = MemorySpaceNode(None, dummy)
        self.assertEqual([], node.getComponents())

    def test_return_component_array(self):
        comp = DummyObject("dummy2", "obj_2", None)
        obj = DummyObject("dummy1", "obj_1", comp)
        node = MemorySpaceNode(None, obj)
        self.assertEqual([["dummy2", "obj_2"]], node.getComponents())

    def test_tombstone_node(self):
        comp = DummyObject("dummy2", "obj_2", None)
        obj = DummyObject("dummy1", "obj_1", comp)
        node = MemorySpaceNode(None, obj)
        tomb = TombstoneNode(node)
        self.assertEqual([["dummy2", "obj_2"]], tomb.getComponents())

    def test_empty_node(self):
        self.assertEqual([], emptyNode.getComponents())

def fillInChildren(spaces):
    for s in list(spaces.values()):
        s._fillInChildren(spaces)

def findPlainRoots(nodes):
    visited = set()
    for s in nodes:
        for c in s.getChildren():
            visited.add(c)
    for s in nodes:
        if s not in visited:
            yield s

def nothing(*args):
    pass

def dfs(roots, pre=nothing, post=nothing, edgeVisitor=nothing):
    visited = set()
    def inner(v):
        pre(v)
        visited.add(v)
        for i in v.getChildren():
            edgeVisitor((v, i))
            if i not in visited:
                inner(i)
        post(v)
    for r in roots:
        if r not in visited:
            inner(r)

def findReachable(roots):
    res = set()
    def pre(n):
        res.add(n)
    dfs(roots, pre=pre)
    return res

def breakCycles(roots):
    active = set()
    def pre(v):
        active.add(v)
    def post(v):
        active.remove(v)
    def edgeVisitor(data):
        (a, b) = data
        if b in active:
            a._replaceChildWithTombstone(b)
    dfs(roots, pre, post, edgeVisitor)

def findRealRoots(spaces):
    """Find a set of node from which you can reach all the nodes in the graph.
    """
    plain = set(findPlainRoots(spaces))
    reachable = findReachable(plain)
    # Unreachables all have at least one parent, since they would be a plain
    # root otherwise. They must have a cycle member as an ancestor.
    unreachable = spaces - reachable
    return plain | unreachable

def nameKey(o):
    return o.getName()

specialClassNames = {'sim'}
def isObjectSpecial(o):
    """Special objects are created outside configuration loads.
    """
    return o.classname in specialClassNames

MEMORY_SPACE_TREE_ASPECT = 'MemorySpaceTreeAspect'
class MemorySpaceTrees(HapListenerMixin, ObservableMixin):
    """A model with all the memory spaces in the system in a tree. It also
    functions as a root for all the trees.
    """
    def __init__(self, sim):
        self.sim = sim
        self.spaces = self.createInitialNodes()
        self._connectNodes()
        self._registerHap('Core_Conf_Object_Create', self._onObjectCreated)
        self._registerHap('Core_Configuration_Loaded', self._onLoaded)
        self._registerHap('Core_Memory_Space_Map_Changed',
                          self._onMapChanged)
        self._registerHap('UI_Run_State_Changed', self._onSimulationStopped)
        self.inLoad = False
        self.mapUpdated = False
        self.newNodes = set()
        # Don't handle object deletion since memory-spaces can't be deleted

    def getSpaces(self):
        return list(self.spaces.values())

    def allMemorySpaces(self):
        for o in self.sim.getAllObjects():
            if isSpaceObject(o):
                yield o

    def allProcessors(self):
        for o in self.sim.getAllObjects():
            if isSimicsProcessor(o):
                yield o

    def createInitialNodes(self):
        res = {}
        for ms in self.allMemorySpaces():
            res[ms] = MemorySpaceNode(self.sim, ms)
        return res

    def clearProcessors(self):
        for space in list(self.spaces.values()):
            space._clearProcessors()

    def findCpuMemRoots(self, spaces, port_mem):
        roots = set()
        for cpu in self.allProcessors():
            cpu_mem = get_cpu_mem(cpu, port_mem)
            if not cpu_mem in spaces:
                continue
            node = spaces[cpu_mem]
            node._addProcessor(cpu, port_mem)
            if node in roots:
                continue
            roots.add(node)
        return roots

    def destroyModel(self):
        self.destroyHaps()
        for n in list(self.spaces.values()):
            n.destroyModel()

    def _connectNodes(self):
        """Create the child pointers between the nodes in the tree and decide
        who the root is.
        """
        fillInChildren(self.spaces)
        self.clearProcessors()
        # Real roots is the roots of the trees. All nodes should be reachable
        # from the real roots.
        # phys mem roots are the memory-spaces which are physical memories
        # for a processor. This is the user centric view of what a root is.
        # Other roots are the real roots which are not phys mem roots. Used
        # to have all the memory spaces in the model.
        physMemRoots = self.findCpuMemRoots(self.spaces, False)
        portMemRoots = self.findCpuMemRoots(self.spaces, True)
        realRoots = set(findRealRoots(set(self.spaces.values())))
        physReachable = findReachable(physMemRoots)
        portReachable = findReachable(portMemRoots)
        otherRoots = realRoots - physReachable - portReachable
        self.roots = (sorted(physMemRoots, key = nameKey)
                      + sorted(portMemRoots, key = nameKey)
                      + sorted(otherRoots, key = nameKey))
        breakCycles(self.roots)

    def getChildren(self):
        return self.roots

    def _onObjectCreated(self, simObj):
        if isObjectSpecial(simObj): return
        self.inLoad = True
        if isSpaceObject(simObj):
            node = MemorySpaceNode(self.sim, simObj)
            self.spaces[simObj] = node
            self.newNodes.add(node)

    def _onLoaded(self, trigger):
        self.newNodes = set()
        self._updateEdges()
        self.inLoad = False

    def _onMapChanged(self, space):
        if self.inLoad:
            return
        if self.sim.isRunning() or self.sim.isScripted():
            self.mapUpdated = True
            return
        self._updateEdges()

    def _onSimulationStopped(self, obj, state):
        if self.mapUpdated and state.startswith("Stopped"):
            self._updateEdges()
        self.mapUpdated = False

    def _updateEdges(self):
        self._connectNodes()
        self._signalAspect(MEMORY_SPACE_TREE_ASPECT)

    def getMap(self):
        return []

    def getFlatMap(self):
        return [], False

    def probeAddress(self, memory_id, address):
        try:
            obj = simics.SIM_get_object(memory_id)
        except simics.SimExc_General:
            return (None, [])

        if isSimicsProcessor(obj):
            phys_mem = get_physical_memory(obj)
            if not phys_mem:
                return (None, [])
            mt = simics.SIM_new_map_target(phys_mem, None, None)
            p_info = obj.iface.processor_info
            block = p_info.logical_to_physical(address, simics.Sim_Access_Read)
            if not block.valid:
                return (None, [])
            address = block.address
        else:
            mt = simics.SIM_new_map_target(obj, None, None)

        hits = probe_address(mt, address)
        simics.SIM_free_map_target(mt)
        if not hits:
            return (None, [])

        # Convert to legacy format
        spaces = [LegacySpace(h, nxt) for (h, nxt) in zip(hits, hits[1:])
                  if hasattr(h.map_target_info.object, "map")]
        if hits[-1].map_target_info:
            device = LegacyDeviceMatch(hits[-1])
        else:
            device = None

        return (device, spaces)

    def getSim(self):
        return self.sim

defaultMemorySpaceTrees = None
def getDefaultMemorySpaceTrees():
    global defaultMemorySpaceTrees
    if not defaultMemorySpaceTrees:
        defaultMemorySpaceTrees = MemorySpaceTrees(getDefaultSimics())
    return defaultMemorySpaceTrees


class LegacyDeviceMatch:
    map_warn = False  # can never happen

    def __init__(self, hit):
        self.map_entry = SimpleNamespace(obj=hit.map_target_info.object,
                                         port=hit.map_target_info.port)
        self.func = hit.map_target_info.function
        self.offset = hit.address

    def get_bank(self):
        nfo = device_info.get_device_info(self.map_entry.obj)
        bank_list = nfo.banks if nfo and nfo.banks else []
        if self.map_entry.port:
            banks = [b for b in bank_list
                     if b.name == self.map_entry.port]
        else:
            banks = [b for b in bank_list if b.function == self.func]

        return (nfo, banks[0] if banks else None)

    def has_io_interface(self):
        return simics.SIM_c_get_port_interface(
            self.map_entry.obj, "io_memory", self.map_entry.port)


def isSimicsTranslate(mti):
    if mti.object.classname == "memory-space":
        return False
    return simics.SIM_c_get_port_interface(mti.object, "translate", mti.port)


class LegacySpace:
    byte_swapping = False  # currently can't report byte-swapping correctly
    translate = False
    ambiguous = False

    def __init__(self, hit, nxt):
        self.space = hit.map_target_info.object
        self.address = hit.address
        self.loop = hit.loop
        if nxt.map_target_info:
            self.translate = isSimicsTranslate(nxt.map_target_info)
            self.ambiguous = nxt.flags & simics.Sim_Translation_Ambiguous
