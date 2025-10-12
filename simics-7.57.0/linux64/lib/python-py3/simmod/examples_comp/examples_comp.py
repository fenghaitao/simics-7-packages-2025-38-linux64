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


#:: pre comp-emmet-example {{
import simics
from comp import *

class emmett(StandardComponent):
    """The long description for the Emmett component."""
    _class_desc = 'short Emmett description'
# }}

#:: pre comp-mcfly-example {{
class mcfly(StandardComponent):
    """The McFly component."""
    _class_desc = 'a McFly component'

    class top_level(StandardComponent.top_level):
        def _initialize(self):
            self.val = True
# }}

#:: pre comp-deckard-example
class deckard(StandardComponent):
    """The Deckard component."""
    _class_desc = 'a Deckard component'

    def _initialize(self):
        super()._initialize()
        self.replicants = 0
# }}

class rachel(deckard):
    """The Rachel component."""
    _class_desc = 'a Rachel component'

    def _initialize(self):
        super()._initialize()
        self.i_am_young = True
# }}

#:: pre comp-tyrell-example {{
class tyrell(StandardComponent):
    """The Tyrell component."""
    _class_desc = 'a Tyrell component'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.olws = 1
            self.add_tyrell_objects()

    def add_tyrell_objects(self):
        self.add_pre_obj('mem', 'memory-space')

class sebastian(tyrell):
    """The Sebastian component."""
    _class_desc = 'a Sebastian component'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_sebastian_objects()

    def add_sebastian_objects(self):
        self.add_pre_obj('mem', 'memory-space')
# }}


#:: pre comp-roy_batty-example {{
class roy_batty(StandardComponent):
    """The Roy Batty component."""
    _class_desc = 'a Roy Batty component'

    def _initialize(self):
        super()._initialize()
        self.replicants = 4

    def _finalize(self):
        super()._finalize()
        if not self.instantiated.val:
            self.add_roy_batty_objects()

    def add_roy_batty_objects(self):
        self.add_pre_obj('mem', 'memory-space')
# }}

#:: pre comp-henry_hill-example {{
class henry_hill(StandardComponent):
    """The wiseguy, Henry Hill component."""
    _class_desc = 'a Henry Hill component'
    _do_not_init = object()

class frankie_carbone(henry_hill):
    """The wiseguy, Frankie Carbone component."""
    _class_desc = 'a Frankie Carbone component'
    def _initialize(self):
        super()._initialize()
# }}


#:: pre comp-tyler_durden-example {{
class tyler_durden(StandardComponent):
    """The Tyler Durden component."""
    _class_desc = 'a Tyler Durden component'

    def setup(self):
        super().setup()
        print("state_of_mind is", self.state_of_mind.val)

    class state_of_mind(Attribute):
        """State of the mind."""
        attrtype = "i"
        def _initialize(self):
            self.val = 50
        def getter(self):
            return self.val
        def setter(self, val):
            if val > 1000:
                return simics.Sim_Set_Illegal_Value
            self.val = val
# }}


#:: pre comp-maria_singer-example {{
class maria_singer(StandardComponent):
    """The Maria Singer component."""
    _class_desc = 'a Maria Singer component'

    def setup(self):
        super().setup()
        print("club_member", self.club_member.val)

    class club_member(SimpleAttribute(False, 'b')):
        """True if club member, default is False."""
# }}


#:: pre comp-ripley-example {{
class ripley(StandardComponent):
    """The Ripley component."""
    _class_desc = 'a Ripley component'

    def setup(self):
        super().setup()
        print("sequels is", self.sequels.val)
        print("eggs is", self.eggs.val)
        print("marine is", self.marine.val)

    class sequels(SimpleConfigAttribute(
            None, 'i', simics.Sim_Attr_Required, [4])):
        """Number of sequels."""

    class eggs(ConfigAttribute):
        """The number of hatched eggs."""
        attrtype = "i"
        valid = [821, 1023]
        def _initialize(self):
            self.val = 50
        def getter(self):
            return self.val
        def setter(self, val):
            if val == 0:
                return simics.Sim_Set_Illegal_Value
            self.val = val

    class marine(SimpleConfigAttribute(
            'hudson', 's', val = ['hudson', 'gorman', 'vasquez'])):
        """The name of the marine."""
# }}


#:: pre comp-nemo-example {{
class nemo(StandardComponent):
    """The Nemo component."""
    _class_desc = 'a Nemo component'

    class component_icon(StandardComponent.component_icon):
        def _initialize(self):
            self.val = "stanton.png"
# }}


#:: pre comp-nikita-example {{
class nikita(StandardComponent):
    """The Nikita component."""
    _class_desc = 'a Nikita component'

    class besson(SimpleAttribute(True, 'b')):
        """True if Luc Besson, default is True."""

    class light_level(Attribute):
        """The light level."""
        attrtype = "i"
        def _initialize(self):
            self.light = 0
        def getter(self):
            return self.light
        def setter(self, val):
            self.light = val
            self._up.light_multiply(val)

    def light_multiply(self, val):
        self.signal.green_light = val * 10

    class signal(Interface):
        def _initialize(self):
            self.green_light = 2
        def signal_raise(self):
            print("signal raise", self._up.besson.val)
        def signal_lower(self):
            print("signal lower", self.green_light)
# }}


#:: pre comp-wall_e-example {{
class wall_e(StandardComponent):
    """The WALL-E component."""
    _class_desc = 'a WALL-E component'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_wall_e_objects()

    def add_wall_e_objects(self):
        p = self.add_pre_obj('p_mem', 'memory-space')
        v = self.add_pre_obj('v_mem', 'memory-space')
        self.add_pre_obj('clock', 'clock', freq_mhz = 10)
        p.map = [[0x100, v, 0, 0, 0x10]]

    class cpu_list(StandardComponent.cpu_list):
        def getter(self):
            return [self._up.get_slot('clock')]
# }}

#:: pre comp-hal-example {{
class hal(StandardComponent):
    """The HAL component."""
    _class_desc = 'a HAL component'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_hal_objects()
            self.do_hal_stuff()

    def add_hal_objects(self):
        self.add_pre_obj('clock', 'clock', freq_mhz = 2001)

        self.add_pre_obj('p_mem[4]', 'memory-space')
        self.add_pre_obj('v_mem[6][10]', 'memory-space')

    def do_hal_stuff(self):
        c = self.get_slot('clock')

        self.get_slot('p_mem[1]').queue = c
        self.get_slot('p_mem')[1].queue = c

        self.get_slot('v_mem[2][3]').queue = c
        self.get_slot('v_mem[2]')[3].queue = c
        self.get_slot('v_mem')[2][3].queue = c
# }}


#:: pre comp-marvin-example {{
class marvin(StandardComponent):
    """The Marvin component."""
    _class_desc = 'a Marvin component'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_marvin_objects()

    def add_marvin_objects(self):
        self.add_pre_obj('clock', 'clock', freq_mhz = 2001)
        p_mem = [None,
                 self.add_pre_obj(None, 'memory-space'),
                 self.add_pre_obj(None, 'memory-space'),
                 None]
        self.add_slot('p_mem', p_mem)
# }}


#:: pre comp-elliot-example {{
class elliot(StandardComponent):
    """The Elliot component."""
    _class_desc = 'an Elliot component'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_elliot_objects()

    def add_elliot_objects(self):
        self.add_connector(
             'eth0', 'ethernet-link', True, False, False,
             simics.Sim_Connector_Direction_Down)
        self.add_connector(
             'uart[2]', 'serial', True, False, False,
             simics.Sim_Connector_Direction_Down)
        dbg = self.add_connector(
             None, 'serial', True, False, False,
             simics.Sim_Connector_Direction_Down)
        self.add_slot('debug', dbg)

    class component_connector(Interface):
        def get_check_data(self, cnt):
            # same as connect_data
            return self._up.get_connect_data(cnt)
        def get_connect_data(self, cnt):
            return self._up.get_connect_data(cnt)
        def check(self, cnt, attr):
            return True
        def connect(self, cnt, attr):
            self._up.connect(cnt, attr)
        def disconnect(self, cnt):
            self._up.disconnect(cnt)

    def get_connect_data(self, cnt):
        if cnt in self.get_slot('uart'):
            num = self.get_slot('uart').index(cnt)
            return [None, self.get_slot('uart_dev%d' % num), 'uart%d' % num]
        elif cnt == self.get_slot('debug'):
            return [None, self.get_slot('dbg_dev'), 'debug']
        elif cnt.type == 'ethernet-link':
            return []

    def connect(self, cnt, attr):
        if cnt in self.get_slot('uart'):
            (link, console) = attr
            num = self.get_slot('uart').index(cnt)
            self.get_slot('uart_dev%d' % num).console = console
        elif cnt == self.get_slot('debug'):
            (link, console) = attr
            self.get_slot('dbg_dev').console = console
        elif cnt == self.get_slot('eth0'):
            self.get_slot('emac0').link = attr[0]

    def disconnect(self, cnt):
        if cnt in self.get_slot('uart'):
            num = self.get_slot('uart').index(cnt)
            self.get_slot('uart_dev%d' % num).console = None
        elif cnt == self.get_slot('debug'):
            self.get_slot('dbg_dev').console = None
        elif cnt == self.get_slot('eth0'):
            self.get_slot('emac0').link = None
# }}


#:: pre comp-gertie-example {{
class gertie(StandardConnectorComponent):
    """The Gertie PCI component."""
    _class_desc = "a Gertie PCI component"
    _help_categories = ('PCI',)

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_gertie_objects()
        self.add_gertie_connectors()

    def add_gertie_connectors(self):
        self.add_connector('pci', PciBusUpConnector(0, 'sample_dev'))

    def add_gertie_objects(self):
        self.add_pre_obj('sample_dev', 'sample_pci_device',
                         int_attr = 10)
# }}


#:: pre comp-brody-example {{
class HarpoonUpConnector(StandardConnector):
    def __init__(self, device, required = False):
        if not isinstance(device, str):
            raise CompException('device must be a string')
        self.device = device
        self.type = 'harpoon-bus'
        self.hotpluggable = False
        self.required = required
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Up

    def get_check_data(self, cmp, cnt):
        return []
    def get_connect_data(self, cmp, cnt):
        return [cmp.get_slot(self.device)]
    def check(self, cmp, cnt, attr):
        return True
    def connect(self, cmp, cnt, attr):
        (num,) = attr
        cmp.get_slot(self.device).int_attr = num
    def disconnect(self, cmp, cnt):
        cmp.get_slot(self.device).int_attr = 0

class brody(StandardConnectorComponent):
    """The Brody component."""
    _class_desc = 'a Brody component'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_brody_objects()
        self.add_brody_connectors()

    def add_brody_connectors(self):
        self.add_connector('jaws', HarpoonUpConnector('sample'))

    def add_brody_objects(self):
        self.add_pre_obj('sample', 'sample_device_dml')
# }}


#:: pre comp-ethan-hunt-example {{
class hunt(StandardConnectorComponent):
    """The Hunt component."""
    _class_desc = 'a Hunt component'

    class impossible(SimpleAttribute(False, 'b')):
        """True if impossible, default is False."""

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_hunt_objects()
        self.add_hunt_connectors()

    def add_hunt_connectors(self):
        self.add_connector('mission1', HarpoonUpConnector('sample'))
        self.add_connector('mission2', HarpoonUpConnector('sample'))

    def add_hunt_objects(self):
        self.add_pre_obj('sample', 'sample_device_dml')
        self.add_pre_obj('clock', 'clock', freq_mhz = 4711)

class ethan(StandardConnectorComponent):
    """The Ethan component."""
    _class_desc = 'an Ethan component'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_ethan_objects()

    def add_ethan_objects(self):
        self.add_component('last', 'hunt', [['impossible', True]])
        self.copy_connector('copy', 'last.mission1')
        mem = self.add_pre_obj('mem', 'memory-space')
        mem.queue = self.get_slot('last.clock')
# }}

#:: pre comp-besson-example {{
class BessonUpConnector(StandardConnector):
    def __init__(self):
        self.type = 'besson'
        self.hotpluggable = False
        self.required = False
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Up
    def get_check_data(self, cmp, cnt):
        return []
    def get_connect_data(self, cmp, cnt):
        return []
    def check(self, cmp, cnt, attr):
        return True
    def connect(self, cmp, cnt, attr):
        pass
    def disconnect(self, cmp, cnt):
        pass

class BessonDownConnector(StandardConnector):
    def __init__(self):
        self.type = 'besson'
        self.hotpluggable = False
        self.required = False
        self.multi = False
        self.direction = simics.Sim_Connector_Direction_Down
    def get_check_data(self, cmp, cnt):
        return []
    def get_connect_data(self, cmp, cnt):
        return []
    def check(self, cmp, cnt, attr):
        return True
    def connect(self, cmp, cnt, attr):
        pass
    def disconnect(self, cmp, cnt):
        pass

class korben(StandardConnectorComponent):
    """The Korben component."""
    _class_desc = 'a Korben component'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_korben_objects()
        self.add_korben_connectors()

    def add_korben_connectors(self):
        self.add_connector('earth', BessonUpConnector())

    def add_korben_objects(self):
        pass

class zorg(StandardConnectorComponent):
    """The Zorg component."""
    _class_desc = 'a Zorg component'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_zorg_objects()
        self.add_zorg_connectors()

    def add_zorg_connectors(self):
        self.add_connector('water', BessonDownConnector())

    def add_zorg_objects(self):
        pass

class leeloo(StandardConnectorComponent):
    """The Leeloo component."""
    _class_desc = 'a Leeloo component'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_leeloo_objects()

    def add_leeloo_objects(self):
        self.add_pre_obj('clock', 'clock', freq_mhz = 10)
        self.add_component('korb_slot', 'korben', [])
        self.add_component('zorg_slot', 'zorg', [])
        self.connect(self.get_slot('korb_slot.earth'),
                     self.get_slot('zorg_slot.water'))
# }}

#:: pre comp-godzilla-example {{
class godzilla(StandardComponent):
    """The Godzilla component."""
    _class_desc = 'a Godzilla component'

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_godzilla_objects()

    def add_godzilla_objects(self):
        self.add_pre_obj('mem', 'memory-space')
        self.add_pre_obj('p_mem', 'memory-space')

    class component(StandardComponent.component):
        def post_instantiate(self):
            self._up.get_slot('mem').default_target = [
                self._up.get_slot('p_mem'), 0, 0, None]
# }}
