# © 2024 Intel Corporation

# empty_blueprint.py - sample code for a Simics configuration blueprint
# Use this file as a skeleton for your own blueprint implementations.

from blueprints import Builder, Namespace, State, blueprint, ConfObject
from blueprints.types import Config
from blueprints.params import params_from_config
from simmod.std_bp.state import Queue, pcie_device_slot, PCIEFunction

# TODO: replace with relevant parameters
class EmptyConfig(Config):
    attribute0 = 0
    attribute1 = 4711

# TODO: replace with relevant state
class EmptyState(State):
    clock: ConfObject = None
    device: ConfObject = None

@blueprint(params_from_config(EmptyConfig))
def empty(builder: Builder, name: Namespace, config: EmptyConfig):
    queue = builder.expose_state(name, Queue)
    queue.queue = name.clock
    builder.obj(name, "blueprint-namespace", queue=queue.queue)

    # TODO: replace with relevant state
    state = builder.expose_state(name, EmptyState)
    state.clock = name.clock
    state.device = name.sample.dev
    builder.expand(name, "sample", pcie_device_slot,
                   fn=PCIEFunction(0, name.sample.dev))

    # TODO: register relevant conf_objects and set initial attributes in them
    builder.obj(name.clock, "clock", freq_mhz=10)
    builder.obj(name.sample.dev, "sample_pci_device", int_attr=4711)
