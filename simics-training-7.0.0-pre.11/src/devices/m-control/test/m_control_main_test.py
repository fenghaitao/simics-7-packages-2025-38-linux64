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

##
## Break out the testing common to both variants of the class into a file.
## This should pass for either variant.
##
## Called from actual s-test files with different classnames 
##

import dev_util
import stest
import cli
import simics
import m_control_common

# Good to have function to count non-zero bits
# Since we should have < 10 set bits performance does not matter
def bitmask(lo,hi):
    return ((~(~0<<(hi-lo+1))) << lo)

# Create an instance of the device to test + utilities

def test_control(classname="m_control"):
    [dev, 
     clock, 
     stub_done, 
     stub_notified, 
     stub_cu_control,
     stub_local_memory, 
     stub_register_memory ] = m_control_common.create_m_control(classname=classname)

    # Log level 2 for some narration in the tests
    cli.global_cmds.log_level(level=2)

    num_compute_units = m_control_common.num_compute_units

    if(num_compute_units <= 1):
        stest.fail("This is pointless, should use two or more compute units!")

    # Registers
    reg_compute_units = dev_util.Register_LE(dev.bank.ctrl,     # object
                                            offset=0x00,    # offset in bank
                                            size=8)   # register size
    reg_start   = dev_util.Register_LE(dev.bank.ctrl, offset=0x08, size=8)
    reg_status  = dev_util.Register_LE(dev.bank.ctrl, offset=0x10, size=8)
    reg_present = dev_util.Register_LE(dev.bank.ctrl, offset=0x20, size=8)
    reg_used    = dev_util.Register_LE(dev.bank.ctrl, offset=0x28, size=8) 
    reg_done    = dev_util.Register_LE(dev.bank.ctrl, offset=0x30, size=8)

    # Check initial state - do registers reflect the configuration?
    stest.expect_equal(reg_compute_units.read(),num_compute_units,"Compute unit register incorrect")
    stest.expect_equal(reg_present.read().bit_count(),num_compute_units,"Present register incorrect")

    # Start operation
    # - In real setup, the software first sets up descriptors and registers
    #   in the compute units.  For the control unit, none of that happens. 
    reg_start.write(num_compute_units)
    stest.expect_equal(reg_start.read(),num_compute_units, "Start register not updated")

    # Check that we mark all units as used
    stest.expect_equal(reg_used.read().bit_count(),num_compute_units,
                        "Used register incorrect at start of operation")

    # And that nothing is completed
    stest.expect_equal(reg_done.read().bit_count(),0,
                        "Done register incorrect at start of operation")

    # And that the status register is set up to indicate processing
    stest.expect_equal(reg_status.read(),0x4000_0000_0000_0000, "Processing status not indicated")

    # Check that all controlled units got a start signal!
    for cu in stub_cu_control:
        stest.expect_equal(cu.attr.start_count, 1, "Compute unit did not see a start")

    # Check what happens if we try to start a new one immediately
    with stest.expect_log_mgr(log_type="spec-viol"):
        reg_start.write(num_compute_units)

    # Do not run time forward, as there is no actual compute work being done

    # Signal from the compute units that the are done.
    # Start with the last one to strain the logic a bit more
    for i in range (num_compute_units,0,-1):
        ## i is one bigger than the actual index in each case
        n = i-1
        dev.port.done[n].iface.signal.signal_raise()
        stest.expect_equal( (reg_done.read() & (1<<n)),(1<<n),
                            f"Compute unit {n} completion not noticed")

    stest.expect_equal(reg_done.read(),bitmask(0,num_compute_units-1), "Did not set all the completion bits")
    stest.expect_equal(reg_done.read(),reg_used.read(), "Used and Done registers diverge!")

    # Check that the status register updated correctly 
    stest.expect_equal(reg_status.read(),0x8000_0000_0000_0000, "Global done flag not set")

    # Check that the global done signal is signalled 
    stest.expect_equal(stub_done.attr.raised,True,"Done signal not signalled")

    # Check that the notifier notified
    stest.expect_equal(stub_notified.notifier_seen, True, "Notification not raised")
    stub_notified.notifier_seen = False

    # Clear done
    reg_status.write( 0x8000_0000_0000_0000 )

    # Check that it had the expected effect
    stest.expect_equal(reg_status.read(), 0x0000_0000_0000_0000,
                    "Failed to clear done flag")
    stest.expect_equal(stub_done.attr.raised,False, 
                        "Failed to lower done signal")
    stest.expect_equal(reg_start.read(), 0, "Start register not zeroed")
    stest.expect_equal(reg_used.read(), 0, "Used register not zeroed")
    stest.expect_equal(reg_done.read(), 0, "Done register not zeroed")

    # Check that the clear_done signals are signalled
    for cu in stub_cu_control:
        stest.expect_equal(cu.attr.start_count - cu.attr.clear_count, 
                        0, "Compute unit did not see a clear_done")

    # And then call back to clear all done signals from the outside
    # - The compute units would be expected to lower this only once they get clear_done 
    #   from the control unit
    for i in range (num_compute_units):
        dev.port.done[i].iface.signal.signal_lower()
        stest.expect_equal( (reg_done.read() & (1<<i)), 0,
                            f"Compute unit {i} clearing done not noticed")


    ##
    ## Additional error detection/corner case testing
    ##
    # Bad value to start should trigger a warning
    with stest.expect_log_mgr(log_type="spec-viol"):
        reg_start.write(num_compute_units+1)
    with stest.expect_log_mgr(log_type="spec-viol"):
        reg_start.write(0)

    # Writing to read-only regs or fields should trigger a warning
    with stest.expect_log_mgr(log_type="spec-viol"):
        reg_compute_units.write(0xffff_ffff_ffff_ffff)
    with stest.expect_log_mgr(log_type="spec-viol"):
        reg_present.write(0xffff_ffff_ffff_ffff)
    with stest.expect_log_mgr(log_type="spec-viol"):
        reg_used.write(0xffff_ffff_ffff_ffff)
    with stest.expect_log_mgr(log_type="spec-viol"):
        reg_done.write(0xffff_ffff_ffff_ffff)

    ## 
    ## Check the behavior of clearing done when starting a
    ## new operation without having cleared the done state
    ##
    # Start operation
    # - In real setup, the software first sets up descriptors and registers
    #   in the compute units.  For the control unit, none of that happens. 
    reg_start.write(num_compute_units)
    stest.expect_equal(reg_start.read(),num_compute_units, "Start register not updated")

    # Check that all controlled units got a start signal!
    for cu in stub_cu_control:
        stest.expect_equal(cu.attr.start_count - cu.attr.clear_count, 
                            1, "Compute unit did not see a start")

    # Do not run time forward, as there is no actual compute work being done

    # Signal from the compute units that they are done.
    for n in range (num_compute_units):
        dev.port.done[n].iface.signal.signal_raise()
        stest.expect_equal( (reg_done.read() & (1<<n)),(1<<n),
                            f"Compute unit {n} completion not noticed")

    # Check that the done bit is now low
    stest.expect_equal(reg_done.read(),reg_used.read(), "Used and Done registers diverge!")

    # Check that the status register updated correctly 
    stest.expect_equal(reg_status.read(),0x8000_0000_0000_0000, "Global done flag not set")

    # At this point, we have completed one operation, but not hit clear_done.
    # Expectation is that the device will now let us run a new operation immediately. 

    # And then start a new operation without clearing done
    old_clear_done_count = stub_cu_control[0].attr.clear_count
    reg_start.write(num_compute_units)
    stest.expect_equal(reg_start.read(),num_compute_units, "Start register not updated")

    # Check that the clear_done command was given when starting the operation
    for cu in stub_cu_control:
        stest.expect_equal(cu.attr.clear_count - old_clear_done_count, 
                        1, "Compute unit did not see a clear_done")

    # Clear the done signals from the compute units, mimicking the effect of
    # calling clear_done on them. 
    for i in range (num_compute_units):
        dev.port.done[i].iface.signal.signal_lower()
        stest.expect_equal( (reg_done.read() & (1<<i)), 0,
                            f"Compute unit {i} clearing done not noticed")

    # Check that the status register updated correctly - processing, not done
    stest.expect_equal(reg_status.read(),0x4000_0000_0000_0000, "Processing not set")

    # Check that the global done signal is NOT signalled anymore 
    stest.expect_equal(stub_done.attr.raised,False,"Done signal still raised, should not be")

    # Signal from the compute units that they are done.
    for n in range (num_compute_units):
        dev.port.done[n].iface.signal.signal_raise()
        stest.expect_equal( (reg_done.read() & (1<<n)),(1<<n),
                            f"Compute unit {n} completion not noticed")

    # Check that the status register updated correctly 
    stest.expect_equal(reg_status.read(),0x8000_0000_0000_0000, "Global done flag not set")

    ##
    ## Testing the max_compute_count pseudo attribute
    ##
    # Can we read it and get an integer back
    stest.expect_true( type(dev.model_max_compute_unit_count) == int )
    # And do we get an exception on trying to write it?
    with stest.expect_exception_mgr(simics.SimExc_AttrNotWritable):
        dev.model_max_compute_unit_count = 16

    ##
    ## Testing the interrupt-raising attribute
    ##
    #if simics.SIM_class_has_attribute(dev.classname,"test_pcie_msix_intr"): 
    #    print(f"{dev} has test_pcie_msix_intr attribute, testing it")
    with stest.expect_exception_mgr(simics.SimExc_General):
        simics.SIM_get_attribute(dev, "test_sending_intr")
    with stest.expect_log_mgr(log_type="info"):
        dev.test_sending_intr = 1
