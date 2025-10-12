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


import dev_util
import stest
import m_compute_common

#
# Perform the same test for all four variants of the m_compute device
#
for cls in ['m_compute', 'm_compute_threaded', 'm_compute_dummy', 'm_compute_threaded_dummy',]:
    #
    # Create an instance of the device to test
    # Along with supporting stubs - all documented in m_compute_common.py
    #
    print(f"-----------------\nTesting class: {cls}\n-----------------")
    [dev, stub_notified, stub_done, mem_space, mem, clock] = m_compute_common.create_m_compute(cls+'_uut', cls)

    # 
    # Create utility proxies for the (rather few) registers in the compute unit.
    #
    reg_addr = dev_util.Register_LE((dev,     # object
                                    'ctrl',   # bank
                                    0x00),    # offset in bank
                                    size=8)   # register size

    reg_status = dev_util.Register_LE((dev,     # object
                                       'ctrl',   # bank
                                       0x08),    # offset in bank
                                       size=8)   # register size

    #
    # For interesting test output, raise the global log level to 3
    # And to help interpret the timing, add time stamps to log messages
    #
    cli.global_cmds.log_level(level=3)
    cli.global_cmds.log_setup(_time_stamp=True, _level=True)

    ##
    ## Check device status after creation - should be clear
    ## 
    stest.expect_equal(reg_status.read(), 0)

    ##
    ## Put descriptor at non-zero address 
    ##   So that it is necessary to write the descriptor_addr
    ##   register to find it. 
    ##
    desc_addr = 0x1000
    work_addr = 0x2000
    test_width  = 10
    test_height = 10
    reg_addr.write(desc_addr)

    ##
    ## Create descriptor in memory using dev_utils. 
    ##
    desc = dev_util.Layout_LE(
        mem, desc_addr,
        {'bottom'    : (0,  4), 
         'left'      : (4,  4),  
         'top'       : (8,  4), 
         'right'     : (12, 4),  
         'width_px'  : (16, 4), 
         'height_px' : (20, 4),  
         'max_iter'  : (24, 4),  
         'dummy'     : (28, 4),
         'addr_px'   : (32, 8)
        })

    def float_to_descriptor(fl_num):
        if (fl_num > 2.0) or (fl_num < -2.0):
            stest.fail(f"Error: {fl_num} is not within the supported range [-2.0, 2.0]")
            return 0x8000_0000
        return int((fl_num * 0x4000_0000) + 0x8000_0000) 

    desc.bottom = float_to_descriptor(-1.0)
    desc.top    = float_to_descriptor(1.0)
    desc.left   = float_to_descriptor(-1.0)
    desc.right  = float_to_descriptor(1.0)
    desc.width_px  = test_width
    desc.height_px = test_height
    desc.max_iter  = 200
    desc.dummy     = 0    
    desc.addr_px   = 0x2000
    # desc.dummy has to be initialized too - since the sparse-memory utility 
    # will give an error if any memory is read that has not been initialized. 
    # And the device does a DMA on the entire descriptor, including the dummy
    # field.  You can try commenting-out the line to see what happens. 

    addr_beyond_last = work_addr + 2 * test_width*test_height

    ps_to_complete = (test_width * test_height * dev.pixel_compute_time)

    ## Reuse basic run operation flow 
    def test_operation_until_done():
        mem_space.cli_cmds.write(address=work_addr, value=0xeeffeeff, size=4, _l=True)
        mem_space.cli_cmds.write(address=addr_beyond_last, value=0xeeff, size=2, _l=True)

        # Send in an edge
        dev.port.control_in.iface.m_compute_control.start_operation()

        # Check that the processing state is correct
        stest.expect_equal(reg_status.read(), 0x4000_0000_0000_0000,
                           "Device not indicating processing state")

        # Test error handling of multiple start calls
        with stest.expect_log_mgr(log_type="spec-viol"):
            dev.port.control_in.iface.m_compute_control.start_operation()

        # Run the simulation forward until the operation is supposed to complete
        cli.global_cmds.run(unit="ps", count=ps_to_complete)

        # Check for completion 
        stest.expect_equal(reg_status.read(), 0x8000_0000_0000_0064,
                           "Status register state incorrect after compute completed")
        stest.expect_equal(stub_done.raised,True,
                            "Done signal not raised after compute completed")

        # Check that memory was updated in a reasonable way:
        stest.expect_different(mem_space.cli_cmds.read(address=work_addr, size=4, _l=True), 0xeeffeeff, 
                               "Device did not write results to memory")
        stest.expect_equal(mem_space.cli_cmds.read(address=addr_beyond_last, size=2, _l=True), 0xeeff,
                           "Device wrote too far in memory")

        stest.expect_equal(stub_notified.notifier_seen, True, "Notification not raised")
        stub_notified.notifier_seen = False

    # Note that there is no check of the the actual validity of the output
    # -- This would basically amount to running the accelerator once, 
    #    checking the results, and saving off the result data. Then,
    #    having a test here that compares the generated bytes

    ## 
    ## Run operation once, clearing done via register
    ##
    test_operation_until_done()
    ## Clear state via register
    reg_status.write( 0x8000_0000_0000_0064 )
    stest.expect_equal(reg_status.read(), 0x0000_0000_0000_0064,
                       "Failed to clear done flag")
    stest.expect_equal(stub_done.raised, False,
                        "Failed to lower done signal")

    ## Check error handling on writing done flag when it has been cleared
    with stest.expect_log_mgr(log_type="spec-viol"):
        reg_status.write(0x8000_0000_0000_0064)

    ##
    ## Run operation again, clearing done via port
    ## 
    test_operation_until_done()
    # Clear done, via interface instead of register
    dev.port.control_in.iface.m_compute_control.clear_done()

    # Check signal and register
    stest.expect_equal(reg_status.read(), 0x0000_0000_0000_0064,
                       "Failed to clear done flag")
    stest.expect_equal(stub_done.raised, False,
                        "Failed to lower done signal")

    # Test error handling of multiple clear done calls
    with stest.expect_log_mgr(log_type="spec-viol"):
        dev.port.control_in.iface.m_compute_control.clear_done()

    ##
    ## Run operation again, with per-pixel updates to test that logic path
    ## 
    # Test per-pixel update variant
    # -- But not for the threaded variant that does not support it
    if(dev.is_threaded==False):
        dev.individual_pixel_update = True

        test_operation_until_done()

        # Clear done, via interface instead of register
        dev.port.control_in.iface.m_compute_control.clear_done()
    else:
        dev.individual_pixel_update = True
        # Set up run
        mem_space.cli_cmds.write(address=work_addr, value=0xeeffeeff, size=4, _l=True)
        mem_space.cli_cmds.write(address=addr_beyond_last, value=0xeeff, size=2, _l=True)

        with stest.expect_log_mgr(log_type="error"):
            # start the compute, should result in an error
            dev.port.control_in.iface.m_compute_control.start_operation()




