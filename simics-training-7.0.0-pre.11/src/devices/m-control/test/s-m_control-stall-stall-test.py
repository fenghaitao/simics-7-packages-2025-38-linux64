# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

#
# Test that the stalling variant of the module
# actually does stall a processor that accesses it. 
#

import dev_util
import stest
import m_control_common
import simics
import pyobj

##
## Create a stall-checking stub processor
##
class stub_processor(pyobj.ConfObject):
    def _initialize(self):
        super()._initialize()  
        self.stall_cycles = 0
        self.total_stall_cycles = 0
        self.cycle_count = 0
        self.frequency = 100_000_000 ## in Hz
        self.program_counter = 0x1000
        self.enabled = True

    class phys_mem(pyobj.SimpleAttribute(None,"o|n")):
        """Pointer to phys mem"""
        pass

    # Stall interface is used to stall and read out stalling, key to test
    class stall(pyobj.Interface):
        def get_total_stall_cycles(self):
            return self._up.total_stall_cycles
        def set_stall_cycles(self,c):
            self._up.stall_cycles = c
            self._up.total_stall_cycles += c
            self._up.cycle_count += c
        def get_stall_cycles(self):
            return self._up.stall_cycles
        
           
    # The stub processor has to implement processor_info 
    # to make SIM_object_is_processor happy.  This implementation is
    # just a set of placeholders; none of these methods are expected
    # to get called by the tests.  
    class processor_info(pyobj.Interface):
        def architecture(self):
            return "fake"
        def disassemble(self,_addr,_instrdata, _suboperation):
            return 0
        def set_program_counter(self,pc):
            self._up.program_counter = pc
        def get_program_counter(self):
            return self._up.program_counter
        def logical_to_physical(self,_addr,_type):
            return (1,1,1,1)   # Totally dummy value
        def enable_processor(self):
            self._up.enabled = True
        def disable_processor(self):
            self._up.enabled = False
        def get_enabled(self):
            return self._up.enabled
        def get_endian(self):
            return simics.Sim_Endian_Little
        def get_physical_memory(self):
            return self._up.phys_mem.val
        def get_logical_address_width(self):
            return 64   # 64 bits looks modern
        def get_physical_address_width(self):
            return 48   # Arbitrary value

##
## Generate a read that can trigger a stall
## - Currently, on memop.  Update to transaction will come later.
## - This has to be changed in conjunction with the code path for
##   stalling in the device itself. 
##
def generate_stallable_read_mem_op(addr, size, initiator):
    m = simics.generic_transaction_t(logical_address=addr, 
                                     physical_address=addr,
                                     size=size, 
                                     type=simics.Sim_Trans_Load)
    simics.SIM_set_mem_op_initiator(m, 
                                    simics.Sim_Initiator_CPU, 
                                    initiator)
    return m

##
## Actual test code
##
def do_test(dev, clock, stub_register_memory):
    spname = 'stub_proc'
    # Setting the queue of the stub processor to the actual clock
    # is necessary, as an easy way to make the stub processor have
    # sufficient smarts for SIM_stall to work.
    sp = simics.pre_conf_object(spname, 'stub_processor', queue=clock)
    # Add to configuration etc.
    simics.SIM_add_configuration( [sp], None )
    stub_proc = simics.SIM_get_object(spname)

    # Raise log level so that stall messages from inside the device
    # are printed to the test log.   
    cli.global_cmds.log_level(level=3)

    ## 
    ## Read status register, check for stalling
    ## 
    sc0 = stub_proc.iface.stall.get_stall_cycles()
    print(f"Initial stall cycles total: {sc0}")
    stest.expect_equal(sc0, 0, "Initial stall state broken")

    # Do a read that is not from a processor
    reg_status = dev_util.Register_LE(dev.bank.ctrl, offset=0x10, size=8)
    reg_status.read()
    sc1 = stub_proc.iface.stall.get_total_stall_cycles()
    stest.expect_equal(sc1, sc0, "Stall when not expected")

    reg_compute_units = dev_util.Register_LE(dev.bank.ctrl, offset=0x00, size=8)
    reg_compute_units.read()
    sc1 = stub_proc.iface.stall.get_total_stall_cycles()
    stest.expect_equal(sc1, sc0, "Stall when not expected")

    # Create a memory operation that looks like it comes from a processor
    #
    # Stall test:
    #   Create memop with required properties
    #   Send into the stub register memory map 
    #   
    reg_status_read_memop = generate_stallable_read_mem_op(0x1000+0x10,
                                                           8,stub_proc)
    # Check that the processor was stalled as a result of the access
    stub_register_memory.iface.memory_space.access(reg_status_read_memop)
    sc2 = stub_proc.iface.stall.get_total_stall_cycles()
    print(f"After stalling read: {sc2}")
    stest.expect_different(sc2, sc1, "We did not get stalled")

    reg_status_read_memop_2 = generate_stallable_read_mem_op(0x1000+0x10,
                                                           8,stub_proc)
    stub_register_memory.iface.memory_space.access(reg_status_read_memop_2)
    sc3 = stub_proc.iface.stall.get_total_stall_cycles()
    print(f"After another stalling read: {sc3}")
    stest.expect_different(sc3, sc2, "We did not get stalled on the second read")

    reg_compute_units_from_cpu = dev_util.Register_LE(dev.bank.ctrl, offset=0x00, size=8, initiator=stub_proc)
    reg_compute_units_from_cpu.read()
    sc4 = stub_proc.iface.stall.get_total_stall_cycles()
    stest.expect_equal(sc3, sc4, "Stall was not expected for that register")

##
## Create the test system - using the stallable version of m_control
##
[dev, clock, _stub_done, 
 _stub_notified, _stub_cu_control,
 _stub_local_memory, stub_register_memory 
 ] = m_control_common.create_m_control(classname="m_control_stall")

## Initial sanity test to check that we have the feature at all 
if(hasattr(dev.attr,"status_reg_stall_time")):
    do_test(dev, clock, stub_register_memory)
else:
    stest.fail("Stalling not present - compilation must have gone wrong")
