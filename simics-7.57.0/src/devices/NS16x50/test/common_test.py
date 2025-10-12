# © 2011 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import os
import sys
sys.path.append(os.path.join('..','common'))
import simics, conf
import cli, dev_util
import stest
from stest import expect_equal

import conf

# SIMICS-21543
conf.sim.deprecation_level = 0

IRQ_ID = 12345

class TestConfig:
    def __init__(self, classname):
        # Small system with a serial interface connected to an
        # interrupt controller
        self.ic = dev_util.Dev([dev_util.SimpleInterrupt])
        self.serial = dev_util.Dev([dev_util.SerialDevice])

        clock = simics.pre_conf_object('clock', 'clock')
        uart = simics.pre_conf_object('uart', classname)

        clock.freq_mhz = 1.8432
        uart.queue = clock
        uart.irq_dev = self.ic.obj
        uart.irq_level = IRQ_ID
        uart.console = self.serial.obj
        uart.xmit_time = 4711

        simics.SIM_add_configuration([clock, uart], None)
        self.clock = conf.clock
        self.uart = conf.uart

        # bug 12178: the model ignored xmit_time settings on object creation.
        expect_equal(self.uart.xmit_time, 4711)
        self.uart.xmit_time = 1000

class UartRegs:
    def __init__(self, uart, initiator=None):
        self.uart = uart

        # Receive/Transmit (POP/PUSH FIFO)/Buffer.
        self.rtb = self.rfr = self.tfr = dev_util.Register_LE(
            (uart, 0, 0x0), 1, initiator=initiator)

        # Interrupt Enable Register
        ier_bf = dev_util.Bitfield_LE({
                'emsi': 3,             # Enable modem status interrupt
                'erlsi': 2,            # Enable receive line status interrupt
                'etfei': 1,            # Enable transmit FIFO empty interrupt
                'erdaiti': 0})         # Enable receive data available
                                       #  interrupt and timeout interrupt
        self.ier = dev_util.Register_LE(
            (uart, 0, 0x1), 1, ier_bf, initiator=initiator)

        # Divisor register.
        self.dlr = dev_util.Register_LE(uart, 0x0, 1,
                                        initiator=initiator)
        self.dmr = dev_util.Register_LE(uart, 0x1, 1,
                                        initiator=initiator)

        # Interrupt Identification Register (Read-only)
        iir_bf = dev_util.Bitfield_LE({
                'fi': (7, 6),   # FIFO identification
                'ii': (1, 3),   # Interrupt ID.
                'ipal': 0})     # Interrupt pending.
        self.iir = dev_util.Register_LE(
            (uart, 0, 0x2), 1, iir_bf, initiator=initiator)

        # FIFO Control Register (Write-only)
        fcr_bf = dev_util.Bitfield_LE({
                'rftl': (6, 7), # Receiver FIFO trigger level
                'dsm': 3,       # DMA signaling mode
                'ctf': 2,       # Clear transmit FIFO
                'crf': 1,       # Clear receive FIFO
                'ef' : 0})      # Enable FIFO
        self.fcr = dev_util.Register_LE(
            (uart, 0, 0x2), 1, fcr_bf, initiator=initiator)

        # Line Control Register - All receive errors abstracted/unimplemented
        lcr_bf = dev_util.Bitfield_LE({
                'drab': 7,              # Divisor registers access bit
                'bc' : 6,               # Break condition
                'sp' : 5,               # Stick parity
                'ep' : 4,               # Even parity
                'pe' : 3,               # Parity enable
                'sb' : 2,               # Stop bits
                'cl' : (0, 1)})         # Character length
        self.lcr = dev_util.Register_LE(
            (uart, 0, 0x3), 1, lcr_bf, initiator=initiator)

        # Modem Control Register
        mcr_bf = dev_util.Bitfield_LE({
                'loop' : 4,            # Loop-back mode.
                'udo2': 3,             # User designated output 2
                'udo1': 2,             # User designated output 1
                'rts': 1,              # Request to send
                'dtr': 0})             # Data terminal ready
        self.mcr = dev_util.Register_LE(
            (uart, 0, 0x4), 1, mcr_bf, initiator=initiator)

        # Line Status Register. (Read-only)
        lsr_bf = dev_util.Bitfield_LE({
                'ef': 7,               # Error flag
                'tef': 6,              # Transmitter empty flag
                'thre': 5,             # Transmitter holding empty flag
                'be': 4,               # Break indication
                'fe': 3,               # Framing error
                'pe': 2,               # Parity error
                'oe': 1,               # Overrun error
                'rdr': 0})             # Receiver data ready
        self.lsr = dev_util.Register_LE(
            (uart, 0, 0x5), 1, lsr_bf, initiator=initiator)

        # Modem Status Register. (Read-only)
        msr_bf = dev_util.Bitfield_LE({
                'dcd': 7,   # Data carrier detect
                'ri': 6,    # Ring indicator
                'dsr': 5,   # Data send request
                'cts': 4,   # Clear to send
                'dcdc': 3,  # DCDn changed
                'rire': 2,  # RIn rising edge
                'dsrc': 1,  # DSRn changed
                'ctsc': 0}) # CTSn changed
        self.msr = dev_util.Register_LE(
            (uart, 0, 0x6), 1, msr_bf, initiator=initiator)

        # Scratch Register. (Storage-only)
        self.sr = dev_util.Register_LE(uart, 0x7, 1,
                                       initiator=initiator)

# test read-only registers
def test_read_only_regs(uart, regs, iir_writable):
    stest.expect_log(regs.lsr.write, [~regs.lsr.read()],
                     uart.bank.regs, "spec-viol")
    stest.expect_log(regs.msr.write, [~regs.msr.read()],
                     uart.bank.regs, "spec-viol")
    # if a FIFO is available, writes to IIR's address are mapped to
    # FCR; if no FIFO is available the address is read-only
    if not iir_writable:
        stest.expect_log(regs.iir.write, [~regs.iir.read()], uart.bank.regs,
                         "spec-viol")

IID_RS   = 0x3
IID_RD   = 0x2
IID_CT   = 0x6
IID_TE   = 0x1
IID_MS   = 0x0
fifo_size = 0x10
data = 0x73

# Test getting and setting receive FIFO.

def xmit_time_cycles(config):
    # Add 3 to allow some fuzz.
    return int(1.0 * config.uart.xmit_time / config.clock.freq_mhz / 1000) + 3

def await_chars(config, n, remain = 0):
    '''Awaiting sending of n chars, minus 'remain' cycles (but at least 1
    cycle). Returns the number of cycles remaining until n chars are
    sent. If remain is non-zero, the return value is always positive
    (so it's safe to use as parameter to SIM_continue()).'''
    cycles = n * xmit_time_cycles(config)
    if remain:
        cycles -= remain
        if cycles < 0:
            remain = -cycles
            cycles = 0
    if cycles:
        simics.SIM_continue(cycles)
    return remain

def int_expect_high(ic, regs, hid, ignore_ipal = False):
    if not ic.simple_interrupt.raised.get(IRQ_ID):
        stest.fail("UART Interrupt low, expected high.")
    expect_equal(regs.iir.ii, hid, "Interrupt Identification")
    if not ignore_ipal:
        expect_equal(regs.iir.ipal, 0, "Interrupt Pending AL")

def int_expect_low(ic, regs):
    if ic.simple_interrupt.raised.get(IRQ_ID):
        stest.fail("UART Interrupt high, expected low.")
    expect_equal(regs.iir.ii, 0, "Interrupt Identification")
    expect_equal(regs.iir.ipal, 1, "Interrupt Pending AL")

def cycle(c):
    return (c + 0x27) % 0x100

def expect_cleared(regs):
    expect_equal(regs.ier.read(), 0x00)
    expect_equal(regs.iir.read(), 0x01)
    expect_equal(regs.lcr.read(), 0x00)
    expect_equal(regs.mcr.read(), 0x00)
    expect_equal(regs.lsr.read(), 0x60)
    expect_equal(regs.msr.read(), 0xb0)

def test_hard_reset(uart, regs):
    regs.sr.write(0xba)
    regs.lcr.drab = 1
    regs.dlr.write(0xab)
    regs.dmr.write(0xcd)
    uart.ports.HRESET.signal.signal_raise()
    uart.ports.HRESET.signal.signal_lower()
    expect_cleared(regs)
    # Now everything should have cleared.
    regs.lcr.drab = 1
    expect_equal(regs.dlr.read(), 0x00)
    expect_equal(regs.dmr.read(), 0x00)
    expect_equal(regs.sr.read(), 0x00)
    regs.lcr.drab = 0

def test_soft_reset(uart, regs, test_scratch_clear=True):
    regs.sr.write(0xba)
    regs.lcr.drab = 1
    regs.dlr.write(0xab)
    regs.dmr.write(0xcd)
    # Use Reset instead of SRESET to test legacy support.
    uart.ports.Reset.signal.signal_raise()
    uart.ports.Reset.signal.signal_lower()
    expect_cleared(regs)
    # These registers should not be modified by soft reset.
    regs.lcr.drab = 1
    if test_scratch_clear:
        expect_equal(regs.sr.read(), 0xba)
    expect_equal(regs.dlr.read(), 0xab)
    expect_equal(regs.dmr.read(), 0xcd)
    regs.lcr.drab = 0

def test_receive(config, regs):
    print("testing device receiver")

    # Not in FIFO mode.
    assert regs.iir.fi == 0x00

    # Test that device receives properly
    for (datalen, clen, rda_int) in (
        (datalen, clen, rda_int)
                    for datalen in (1, 16, 18)
                    for clen in (0, 1, 2, 3)
                    for rda_int in (0, 1)):

        # Individual testing parameters must be set.
        regs.ier.write(erlsi = 1, erdaiti = rda_int)
        regs.lcr.cl = clen

        # Get the mask for the byte length.
        cmask = [0x1F, 0x3F, 0x7F, 0xFF][clen]

        # The LSR might contain invalid status.
        expect_equal(regs.lsr.ef, 0)
        expect_equal(regs.lsr.tef, 1)
        expect_equal(regs.lsr.thre, 1)
        expect_equal(regs.lsr.be, 0)
        expect_equal(regs.lsr.fe, 0)
        expect_equal(regs.lsr.pe, 0)
        expect_equal(regs.lsr.oe, 0)
        expect_equal(regs.lsr.rdr, 0)

        # No interrupt should be pending now.
        int_expect_low(config.ic, regs)

        # Verify that device reception and interrupts works.
        c = data
        for i in range(datalen):
            c = cycle(c)
            config.uart.iface.serial_device.write(c)
            if rda_int == 1:
                int_expect_high(config.ic, regs, IID_RD)
            expect_equal(regs.lsr.rdr, 1)
            exp = c & cmask
            expect_equal(regs.rtb.read(), exp)
            int_expect_low(config.ic, regs)

        # Pass the time to flush events.
        await_chars(config, datalen)

def test_transmit(config, regs, test_loopback=True):
    print("testing device transmitter")

    # Not in FIFO mode.
    assert regs.iir.fi == 0x00

    # Reset device interrupts.
    regs.ier.write(0x00)

    # Test that device transmits properly.
    for (datalen, loopback, clen, ms_int, etf_int) in (
        (datalen, loopback, clen, ms_int, etf_int)
                    for datalen in (1, 16, 18)
                    for loopback in ((0, 1) if test_loopback else (0,))
                    for clen in (1, 3)
                    for ms_int in (True, False)
                    for etf_int in (True, False)):

        # Individual testing parameters must be set.
        regs.lcr.cl = clen
        regs.ier.etfei = etf_int
        regs.ier.emsi = ms_int
        if etf_int:
            # Verify that transmitter empty interrupt works as intended.
            regs.ier.erdaiti = 1
            r = config.uart.iface.serial_device.write(0x11)
            expect_equal(r, 1)
            int_expect_high(config.ic, regs, IID_RD)
            expect_equal(regs.rtb.read(), 0x11)
            int_expect_high(config.ic, regs, IID_TE, True)
            int_expect_low(config.ic, regs)
            regs.ier.etfei = 0
            regs.ier.etfei = 1
            int_expect_high(config.ic, regs, IID_TE, True)
            int_expect_low(config.ic, regs)
            regs.ier.erdaiti = 0

        regs.mcr.write(0x00)

        # Get the mask for the byte length.
        cmask = [0x1F, 0x3F, 0x7F, 0xFF][clen]

        # The LSR might contain invalid status.
        expect_equal(regs.lsr.ef, 0)
        expect_equal(regs.lsr.thre, 1)
        expect_equal(regs.lsr.tef, 1)
        expect_equal(regs.lsr.be, 0)
        expect_equal(regs.lsr.fe, 0)
        expect_equal(regs.lsr.pe, 0)
        expect_equal(regs.lsr.oe, 0)
        expect_equal(regs.lsr.rdr, 0)

        # No interrupt should be pending after reading IIR.
        regs.iir.read()
        int_expect_low(config.ic, regs)

        c = data

        regs.mcr.loop = loopback
        if loopback == 1:
            # Test that loop-back, modem interrupts,
            # modem status delta and rising edge works.
            regs.mcr.dtr = 1
            if ms_int:
                int_expect_high(config.ic, regs, IID_MS)
            expect_equal(regs.msr.dsr, 1)
            expect_equal(regs.msr.cts, 0)
            int_expect_low(config.ic, regs)
            regs.mcr.rts = 1
            if ms_int:
                int_expect_high(config.ic, regs, IID_MS)
            expect_equal(regs.msr.ctsc, 1)
            expect_equal(regs.msr.cts, 1)
            expect_equal(regs.msr.ctsc, 0)
            int_expect_low(config.ic, regs)
            expect_equal(regs.msr.ri, 0)
            expect_equal(regs.msr.dcd, 0)
            regs.mcr.rts = 0
            expect_equal(regs.msr.ctsc, 1)
            expect_equal(regs.msr.cts, 0)
            expect_equal(regs.msr.ctsc, 0)
            regs.mcr.udo1 = 1
            regs.mcr.udo2 = 1
            if ms_int:
                int_expect_high(config.ic, regs, IID_MS)
            expect_equal(regs.msr.rire, 1)
            int_expect_low(config.ic, regs)
            expect_equal(regs.msr.dcdc, 0)
            expect_equal(regs.msr.dcd, 1)
            expect_equal(regs.msr.ri, 1)
            expect_equal(regs.msr.cts, 0)
            int_expect_low(config.ic, regs)
            regs.mcr.udo1 = 0
            int_expect_low(config.ic, regs)
            expect_equal(regs.msr.rire, 0)
            expect_equal(regs.msr.ri, 0)
            for i in range(datalen):
                c = cycle(c)
                # Transmitter buffer should be flagged as empty.
                expect_equal(regs.lsr.thre, 1)
                expect_equal(regs.lsr.tef, 1)
                # Writing a char should loop it to receive FIFO.
                regs.rtb.write(c)
                # Transmitter buffer should be flagged as non-empty.
                expect_equal(regs.lsr.thre, 0)
                expect_equal(regs.lsr.tef, 0)
                # Respect event timing.
                await_chars(config, 1)
                # Reception might be invalid.
                expect_equal(regs.rtb.read(), c & cmask)
            # Disable this for clear transmit test to work properly.
            regs.mcr.loop = 0
            regs.ier.emsi = 0
            # Read the MSR to reset potential modem status interrupt.
            regs.msr.read()
        else:
            # Verify that MCR indicates ready to receive and data send request.
            expect_equal(regs.msr.cts, 1)
            expect_equal(regs.msr.dsr, 1)
            # Sending the data to verify reception, interrupts and flags.
            for i in range(datalen):
                # Write dummy char and then real char.
                regs.rtb.write(0xFF)
                await_chars(config, 1)
                c = cycle(c)
                regs.rtb.write(c)
                rem = await_chars(config, 1, 10)
                # Transmitter should not be flagged as empty.
                expect_equal(regs.lsr.thre, 0)
                expect_equal(regs.lsr.tef, 0)
                # Respect event timing.
                simics.SIM_continue(rem)
                # Transmitter should be flagged as empty.
                expect_equal(regs.lsr.thre, 1)
                expect_equal(regs.lsr.tef, 1)
                # Reception might be invalid.
                expect_equal(config.serial.serial_device.value, c & cmask)
                if etf_int:
                    # Switching between two different tests.
                    if i % 2 == 0:
                        # Check that transmitter empty interrupt was really thrown.
                        int_expect_high(config.ic, regs, IID_TE, True)
                        # IIR have been read and the interrupt should have reset.
                        int_expect_low(config.ic, regs)
                    else:
                        # Writing to transmit FIFO should reset the interrupt.
                        regs.rtb.write(0xFF)
                        int_expect_low(config.ic, regs)
                # Pass time to flush chars.
                await_chars(config, 2)

        # No interrupt should be pending after reading IIR.
        regs.iir.read()
        int_expect_low(config.ic, regs)

def test_recv_fifo(config, regs, test_dma = True, test_chartimeout = True,
                   test_trigger_level = True):
    print("testing device reception with FIFO")

    if test_dma:
        rxrdyn = dev_util.Dev([dev_util.Signal])
        config.uart.RXRDYn = rxrdyn.obj


    # Reset device interrupts.
    regs.ier.write(0x00)
    # Test that device can switch into FIFO mode.
    regs.fcr.write(0, ef = 1)
    expect_equal(regs.iir.fi, 0x03)

    # Test that device receives properly
    for (datalen, clen, trg_lvl, clr_recv, multi_dma, rdait_int) in (
        (datalen, clen, trg_lvl, clr_recv, multi_dma, rdait_int)
                    for datalen in (1, 16, 18)
                    for clen in (0, 1, 2, 3)
                    for clr_recv in (0, 1)
                    for multi_dma in ((0, 1) if test_dma else (0,))
                    for trg_lvl in (1, 3)
                    for rdait_int in (0, 1)):

        # Individual testing parameters must be set.
        regs.lcr.cl = clen
        regs.ier.write(erlsi = 1, erdaiti = rdait_int)
        if test_dma:
            regs.fcr.write(0, ef = 1, rftl = trg_lvl, dsm = multi_dma)
        else:
            regs.fcr.write(0, ef = 1, rftl = trg_lvl)

        # Get the mask for the byte length.
        cmask = (1 << (clen + 5)) - 1
        ctriggers = [1,4,8,14]
        ctrigger = ctriggers[trg_lvl]

        # The LSR might contain invalid status.
        expect_equal(regs.lsr.ef, 0)
        expect_equal(regs.lsr.tef, 1)
        expect_equal(regs.lsr.thre, 1)
        expect_equal(regs.lsr.be, 0)
        expect_equal(regs.lsr.fe, 0)
        expect_equal(regs.lsr.pe, 0)
        expect_equal(regs.lsr.oe, 0)
        expect_equal(regs.lsr.rdr, 0)

        # No interrupt should be pending now.
        int_expect_low(config.ic, regs)

        if test_dma:
            # Verify DMA signal is properly set.
            expect_equal(rxrdyn.signal.level, 1)


        # Sending and transforming everything at once for interrupt testing.
        c = data
        for i in range(datalen):
            c = cycle(c)
            result = config.uart.iface.serial_device.write(c)
            expect_equal(result, i < fifo_size)

            if test_chartimeout:
                # For the first char being sent, verify absence char
                # timeout interrupt.
                if i == 0 and rdait_int == 1:
                    # Verify potential char time out interrupt.
                    # As we wait 2 characters, timeout event should not happen.
                    await_chars(config, 2)
                    int_expect_low(config.ic, regs)

                # For the second char being sent, verify char timeout interrupt.
                if i == 1 and rdait_int == 1:
                    # Verify potential char time out interrupt.
                    await_chars(config, 5)
                    int_expect_high(config.ic, regs, IID_CT)
                    if test_dma:
                        if multi_dma == 1:
                            expect_equal(rxrdyn.signal.level, 0)

        # It won't be able to receive more data than the FIFO size.
        gotdatalen = fifo_size if datalen > fifo_size else datalen

        # Error flag should only indicate parity, break condition or frame errors.
        expect_equal(regs.lsr.ef, 0)


        if test_chartimeout and test_trigger_level:
            # Verify potential received data (by trigger level) interrupt.
            if rdait_int == 1:
                if gotdatalen >= ctrigger:
                    int_expect_high(config.ic, regs, IID_RD)
                else:
                    # Make sure a char timeout interrupt should trigger.
                    await_chars(config, 5)
                    int_expect_high(config.ic, regs, IID_CT)
                # Both above cases should have lower RXRDYn if multi_dma,
                # and if not, it should already have been zero.
                expect_equal(rxrdyn.signal.level, 0)
            else:
                int_expect_low(config.ic, regs)
        expect_equal(regs.lsr.rdr, 1, "Receiver Data Ready")

        if clr_recv == 1:
            # Verify that clearing receive FIFO works.
            regs.fcr.write(0, ef = 1, rftl = trg_lvl, dsm = multi_dma, crf = 1)
            # Read the receiver, because it should work
            # and will clear char timeout if raised.
            regs.rfr.read()
        else:
            # Using the same transformation to
            # check integrity of FIFO transmission.
            c = data
            remain = gotdatalen
            for i in range(gotdatalen):
                c = cycle(c)
                exp = c & cmask
                expect_equal(regs.rfr.read(),exp,"Receive FIFO")
                remain -= 1
                if test_trigger_level:
                    # All interrupts should clear as soon as the
                    # receive FIFO goes below the trigger level.
                    if remain < ctrigger:
                        int_expect_low(config.ic, regs)

        if test_dma:
            # Verify that DMA signal goes high when no remaining chars in FIFO.
            expect_equal(rxrdyn.signal.level, 1)

        # No interrupt should be pending now.
        int_expect_low(config.ic, regs)

        # Pass the time to flush events.
        await_chars(config, datalen)

def test_xmit_fifo(config, regs,
                   test_checkpointing=True, test_dma=True, test_clear=True,
                   test_loopback=True):
    print("testing device transmission with FIFO")

    if test_dma:
        txrdyn = dev_util.Dev([dev_util.Signal])
        config.uart.TXRDYn = txrdyn.obj

    # Reset device interrupts.
    regs.ier.write(0x00)
    # Test that device can switch into FIFO mode.
    regs.fcr.write(0, ef = 1)
    expect_equal(regs.iir.fi, 0x03)

    # Test that device transmits properly.
    for (datalen, loopback, clen, clr_xmit, multi_dma, ms_int, etf_int) in (
        (datalen, loopback, clen, clr_xmit, multi_dma, ms_int, etf_int)
                    for datalen in (1, 16, 18)
                    for loopback in ((0, 1) if test_loopback else (0,))
                    for clen in (1, 3)
                    for clr_xmit in (0, 1)
                    for multi_dma in ((0, 1) if test_dma else (0,))
                    for ms_int in (True, False)
                    for etf_int in (True, False)):

        # Individual testing parameters must be set.
        regs.lcr.cl = clen
        regs.ier.erlsi = 1
        regs.ier.etfei = etf_int
        regs.ier.emsi = ms_int
        if etf_int:
            # Verify that transmitter empty interrupt works as intended.
            regs.ier.erdaiti = 1
            regs.fcr.write(0, ef = 0)
            r = config.uart.iface.serial_device.write(0x11)
            expect_equal(r, 1)
            int_expect_high(config.ic, regs, IID_RD)
            expect_equal(regs.rfr.read(), 0x11)
            int_expect_high(config.ic, regs, IID_TE, True)
            int_expect_low(config.ic, regs)
            regs.ier.etfei = 0
            regs.ier.etfei = 1
            int_expect_high(config.ic, regs, IID_TE, True)
            int_expect_low(config.ic, regs)
            regs.ier.erdaiti = 0

        # Reconfiguring FIFO for test.
        regs.fcr.write(0, ef = 1, dsm = multi_dma)
        regs.mcr.write(0x00)

        # Get the mask for the byte length.
        cmask = [0x1F, 0x3F, 0x7F, 0xFF][clen]

        # The LSR might contain invalid status.
        expect_equal(regs.lsr.ef, 0)
        expect_equal(regs.lsr.tef, 1)
        expect_equal(regs.lsr.thre, 1)
        expect_equal(regs.lsr.be, 0)
        expect_equal(regs.lsr.fe, 0)
        expect_equal(regs.lsr.pe, 0)
        expect_equal(regs.lsr.oe, 0)
        expect_equal(regs.lsr.rdr, 0)

        # No interrupt should be pending after reading IIR.
        regs.iir.read()
        int_expect_low(config.ic, regs)

        c = data

        regs.mcr.loop = loopback
        if loopback == 1:
            # Test that loop-back, modem interrupts,
            # modem status delta and rising edge works.
            regs.mcr.dtr = 1
            if ms_int:
                int_expect_high(config.ic, regs, IID_MS)
            expect_equal(regs.msr.dsr, 1)
            expect_equal(regs.msr.cts, 0)
            int_expect_low(config.ic, regs)
            regs.mcr.rts = 1
            if ms_int:
                int_expect_high(config.ic, regs, IID_MS)
            expect_equal(regs.msr.ctsc, 1)
            expect_equal(regs.msr.cts, 1)
            expect_equal(regs.msr.ctsc, 0)
            int_expect_low(config.ic, regs)
            expect_equal(regs.msr.ri, 0)
            expect_equal(regs.msr.dcd, 0)
            regs.mcr.rts = 0
            expect_equal(regs.msr.ctsc, 1)
            expect_equal(regs.msr.cts, 0)
            expect_equal(regs.msr.ctsc, 0)
            regs.mcr.udo1 = 1
            regs.mcr.udo2 = 1
            if ms_int:
                int_expect_high(config.ic, regs, IID_MS)
            expect_equal(regs.msr.rire, 1)
            int_expect_low(config.ic, regs)
            expect_equal(regs.msr.dcdc, 0)
            expect_equal(regs.msr.dcd, 1)
            expect_equal(regs.msr.ri, 1)
            expect_equal(regs.msr.cts, 0)
            int_expect_low(config.ic, regs)
            regs.mcr.udo1 = 0
            int_expect_low(config.ic, regs)
            expect_equal(regs.msr.rire, 0)
            expect_equal(regs.msr.ri, 0)
            transmitted_chars = []
            # Transmitter and transmit FIFO should be flagged as empty.
            expect_equal(regs.lsr.tef, 1)
            expect_equal(regs.lsr.thre, 1)
            for i in range(datalen):
                c = cycle(c)
                # Writing a char should loop it to receive FIFO.
                regs.tfr.write(c)
                transmitted_chars.append(c)
                # Transmitter and transmit FIFO should be flagged as non-empty.
                expect_equal(regs.lsr.tef, 0)
                expect_equal(regs.lsr.thre, 0)
                await_chars(config, 1)
                if i >= fifo_size:
                    int_expect_high(config.ic, regs, IID_RS)
                    expect_equal(regs.lsr.oe, 1)
                if not etf_int:
                    int_expect_low(config.ic, regs)
                expect_equal(regs.lsr.oe, 0)
            for i in range(min(datalen, fifo_size)):
                expect_equal(regs.lsr.tef, 1)
                expect_equal(regs.lsr.thre, 1)
                # Reception might be invalid.
                expect_equal(regs.rfr.read(), transmitted_chars[i] & cmask)
            expect_equal(regs.lsr.tef, 1)
            expect_equal(regs.lsr.thre, 1)

            # Disable this for clear transmit test to work properly.
            regs.mcr.loop = 0
            regs.ier.emsi = 0
            # Read the MSR to reset potential modem status interrupt.
            regs.msr.read()
        else:
            # Verify that MCR indicates ready to receive and data send request.
            expect_equal(regs.msr.cts, 1)
            expect_equal(regs.msr.dsr, 1)
            # Sending the data to verify reception, interrupts and flags.
            for i in range(datalen):
                regs.tfr.write(0xFF)
                regs.tfr.write(0xFF)
                regs.tfr.write(0xFF)
                regs.tfr.write(0xFF)
                c = cycle(c)
                regs.tfr.write(c)
                # Transmitter and transmit FIFO should not be flagged as empty.
                expect_equal(regs.lsr.tef, 0)
                expect_equal(regs.lsr.thre, 0)
                if test_checkpointing:
                    # Test check pointing.
                    config.uart.xmit_fifo = config.uart.xmit_fifo
                # Respect event timing.
                rem = await_chars(config, 5, 40)
                expect_equal(regs.lsr.tef, 0)
                expect_equal(regs.lsr.thre, 0)
                simics.SIM_continue(rem)
                # Transmitter and transmit FIFO should be flagged as empty.
                expect_equal(regs.lsr.tef, 1)
                expect_equal(regs.lsr.thre, 1)
                # Reception might be invalid.
                expect_equal(config.serial.serial_device.value, c & cmask)
                if etf_int:
                    # Switching between two different tests.
                    if i % 2 == 0:
                        # Check that transmitter empty interrupt was really thrown.
                        int_expect_high(config.ic, regs, IID_TE, True)
                        # IIR have been read and the interrupt should have reset.
                        int_expect_low(config.ic, regs)
                    else:
                        # Writing to transmit FIFO should reset the interrupt.
                        regs.tfr.write(0xFF)
                        regs.tfr.write(0xFF)
                        int_expect_low(config.ic, regs)
                # Pass time to flush chars.
                await_chars(config, 2)

        if test_dma:
            # Verify DMA
            expect_equal(txrdyn.signal.level, 0)

        if test_clear:
            # Filling and clearing transmit FIFO should have no effect.
            if clr_xmit == 1:
                for i in range(datalen):
                    regs.tfr.write(0x7F)
                if datalen > 1:
                    # Verify break condition.
                    regs.lcr.bc = 1
                    await_chars(config, datalen + 4)
                # Verify DMA and empty flagging.
                if multi_dma == 0:
                    exp_tx = 1
                else:
                    exp_tx = datalen >= fifo_size
                if test_dma:
                    expect_equal(txrdyn.signal.level, exp_tx)
                expect_equal(regs.lsr.thre, 0)
                # Verify that clearing has effect.
                regs.lcr.bc = 0
                if test_dma:
                    regs.fcr.write(0, ef = 1, ctf = 1, dsm = multi_dma)
                else:
                    regs.fcr.write(0, ef = 1, ctf = 1)
            # If a char is still being shifted, wait for it.
            await_chars(config, 1)
        # The transmitter and XMIT FIFO should be clear now.
        expect_equal(regs.lsr.tef, 1)
        expect_equal(regs.lsr.thre, 1)
        # Verify DMA and transmitter empty.
        if test_dma:
            expect_equal(txrdyn.signal.level, 0)

        # No interrupt should be pending after reading IIR.
        regs.iir.read()
        int_expect_low(config.ic, regs)
