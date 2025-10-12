# © 2010 Intel Corporation

# empty_component.py - sample code for a Simics configuration component
# Use this file as a skeleton for your own component implementations.

from comp import (StandardConnectorComponent, PciBusUpConnector,
                  ConfigAttribute, SimpleConfigAttribute)

class empty_components(StandardConnectorComponent):
    """The empty component class."""
    _class_desc = "empty component"
    _help_categories = ()

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self.add_objects()
        # TODO: replace the example pci-bus connector with relevant connectors
        self.add_connector('pci', PciBusUpConnector(0, 'sample_dev'))

    def add_objects(self):
        # TODO: create relevant conf_objects and set initial attributes in them
        self.add_pre_obj('clock', 'clock', freq_mhz = 10)
        sample = self.add_pre_obj('sample_dev', 'sample_pci_device')
        sample.int_attr = 4711

    # TODO: replace attribute with relevant attributes
    class attribute0(ConfigAttribute):
        """attribute0"""
        attrtype = "i"
        def _initialize(self):
            self.val = 4711
        def getter(self):
            return self.val
        def setter(self, val):
            self.val = val

    # TODO: replace attribute with relevant attributes
    class attribute1(SimpleConfigAttribute(0, 'i')):
        """attribute1"""
        def setter(self, val):
            self.val = val
