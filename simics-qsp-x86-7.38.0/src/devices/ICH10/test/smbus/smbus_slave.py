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


# smbus_slave.py,
# a series of pseudo slave devices on the SMBus responding
# to the commands from the SMBus host controller

import pyobj
import simics

from simics import (I2C_ack, I2C_noack)

rt_primary_bus_both = 2

class I2cConst:
    # Following constants come from <simics>/src/include/simics/dev/i2c.h
    status_success      = 0
    status_noack        = 1
    status_bus_busy     = 2

class Smbus_Slave_Base(pyobj.ConfObject):
    '''A base class for different pseudo SMBus slave devices'''
    def _initialize(self):
        super()._initialize()
        self.stop_called = 0
        self.stop_cond = []
        self.addr = 0
        self.addr_mask = 0
        self.conf_obj = None
        self.smbus = None

    class smbus(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'o'
        def getter(self):
            return self._up.smbus
        def setter(self, val):
            self._up.smbus = val

    class i2c_link_v2(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'o'
        def getter(self):
            return self._up.smbus
        def setter(self, val):
            self._up.smbus = val

    class addr(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Required
        attrtype = 'i'
        def getter(self):
            return self._up.addr
        def setter(self, val):
            self._up.addr = val

    class addr_mask(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Required
        attrtype = 'i'
        def getter(self):
            return self._up.addr_mask
        def setter(self, val):
            self._up.addr_mask = val

    class register(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = 'o'
        def getter(self):
            return None
        def setter(self, val):
            self._up.conf_obj = val
            self._up.smbus.iface.i2c_link.register_slave_address(
                    val, self._up.addr, self._up.addr_mask)

    class unregister(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = 'o'
        def getter(self):
            return None
        def setter(self, val):
            self._up.smbus.iface.i2c_link.unregister_slave_address(
                    val, self._up.addr, self._up.addr_mask)

    class stop_called(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = 'i'
        def getter(self):
            return self._up.stop_called
        def setter(self, val):
            self._up.stop_called = val

    class stop_condition(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = '[i*]'
        def getter(self):
            return self._up.stop_cond
        def setter(self, val):
            self._up.stop_cond = val


class Smbus_Slave_Quick(Smbus_Slave_Base):
    '''A pseudo SMBus slave receiving quick command from ICH9 SMBus host controller'''
    def _initialize(self):
        super()._initialize()
        self.caps_lock  = 0
        self.num_lock   = 0

    class i2c_slave(pyobj.Interface):
        def start_request(self, address):
            if address == self._up.addr: # Write command
                self._up.caps_lock = not self._up.caps_lock
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_success)
            elif address == (self._up.addr + 1): # Read command
                self._up.num_lock = not self._up.num_lock
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_success)
            else:
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_noack)

        def stop(self, repeated_start):
            self._up.stop_cond.append(repeated_start)
            self._up.stop_called = self._up.stop_called + 1

    class i2c_slave_v2(pyobj.Interface):
        def start(self, address):
            if address == self._up.addr: # Write command
                self._up.caps_lock = not self._up.caps_lock
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_ack)
            elif address == (self._up.addr + 1): # Read command
                self._up.num_lock = not self._up.num_lock
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_ack)
            else:
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_noack)

        def stop(self):
            self._up.stop_cond.append(0)
            self._up.stop_called = self._up.stop_called + 1
        def addresses(self):
            return [self._up.addr, self._up.addr+1]

    class caps_lock(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return int(self._up.caps_lock)
        def setter(self, val):
            self._up.caps_lock = val

    class num_lock(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return int(self._up.num_lock)
        def setter(self, val):
            self._up.num_lock = val


class Smbus_Slave_Byte(Smbus_Slave_Base):
    '''A pseudo SMBus slave receiving byte command from ICH9 SMBus host controller'''
    def _initialize(self):
        super()._initialize()
        self.caps_lock  = 0
        self.num_lock   = 0
        self.cmd_data   = 0

    class i2c_slave(pyobj.Interface):
        def start_request(self, address):
            if address == self._up.addr: # Write command
                self._up.caps_lock = not self._up.caps_lock
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_success)
            elif address == (self._up.addr + 1): # Read command
                self._up.num_lock = not self._up.num_lock
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_success)
            else:
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_noack)

        def write_request(self, val):
            self.cmd_data = val
            self._up.smbus.iface.i2c_link.write_response(
                                self._up.conf_obj, I2cConst.status_success)

        def read_request(self):
            self._up.smbus.iface.i2c_link.read_response(
                                self._up.conf_obj, self._up.cmd_data)

        def ack_read_request(self, ack):
            if ack == I2cConst.status_success:
                self._up.smbus.iface.i2c_link.ack_read_response(self._up.conf_obj)
            else:
                print("No response from smbus slave device (unsuccessful)")

        def stop(self, repeated_start):
            self._up.stop_cond.append(repeated_start)
            self._up.stop_called = self._up.stop_called + 1

    class i2c_slave_v2(pyobj.Interface):
        def start(self, address):
            if address == self._up.addr: # Write command
                self._up.caps_lock = not self._up.caps_lock
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_ack)
            elif address == (self._up.addr + 1): # Read command
                self._up.num_lock = not self._up.num_lock
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_ack)
            else:
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_noack)

        def write(self, val):
            self.cmd_data = val
            self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_ack)

        def read(self):
            self._up.smbus.iface.i2c_master_v2.read_response(self._up.cmd_data)

        def stop(self):
            self._up.stop_cond.append(0)
            self._up.stop_called = self._up.stop_called + 1

        def addresses(self):
            return [self._up.addr, self._up.addr+1]

    class caps_lock(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return int(self._up.caps_lock)
        def setter(self, val):
            self._up.caps_lock = val

    class num_lock(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return int(self._up.num_lock)
        def setter(self, val):
            self._up.num_lock = val

    class cmd_data(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.cmd_data
        def setter(self, val):
            self._up.cmd_data = val



class Smbus_Slave_Byte_Data(Smbus_Slave_Byte):
    '''A pseudo SMBus slave receiving byte data command from ICH9 SMBus host controller'''
    def _initialize(self):
        super()._initialize()
        self.read_repeats = 0
        self.write_repeats = 0
        self.cmd_code   = 0

    class i2c_slave(pyobj.Interface):
        def start_request(self, address):
            if address == self._up.addr: # Write command
                self._up.caps_lock = not self._up.caps_lock
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_success)
            elif address == (self._up.addr + 1): # Read command
                self._up.num_lock = not self._up.num_lock
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_success)
            else:
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_noack)

        def write_request(self, val):
            self._up.write_repeats = self._up.write_repeats + 1
            status = I2cConst.status_success
            if self._up.write_repeats == 1:
                self._up.cmd_code = val
            elif self._up.write_repeats == 2:
                self._up.cmd_data = val
            else:
                status = I2cConst.status_noack
            self._up.smbus.iface.i2c_link.write_response(self._up.conf_obj, status)

        def read_request(self):
            self._up.read_repeats = self._up.read_repeats + 1
            if self._up.read_repeats == 1:
                self._up.smbus.iface.i2c_link.read_response(
                                    self._up.conf_obj, self._up.cmd_data)
            else:
                assert (0)

        def ack_read_request(self, ack):
            if ack == I2cConst.status_success:
                self._up.smbus.iface.i2c_link.ack_read_response(self._up.conf_obj)
            else:
                print("No response from smbus slave device (unsuccessful)")

        def stop(self, repeated_start):
            self._up.stop_cond.append(repeated_start)
            self._up.stop_called = self._up.stop_called + 1
            # Clear the counter of read/write
            self._up.read_repeats = 0
            self._up.write_repeats = 0

    class i2c_slave_v2(pyobj.Interface):
        def start(self, address):
            print(f'Start for {hex(address)} while I am {hex(self._up.addr)}')
            if address == self._up.addr: # Write command
                self._up.caps_lock = not self._up.caps_lock
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_ack)
            elif address == (self._up.addr + 1): # Read command
                self._up.num_lock = not self._up.num_lock
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_ack)
            else:
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_noack)

        def write(self, val):
            self._up.write_repeats = self._up.write_repeats + 1
            status = I2C_ack
            if self._up.write_repeats == 1:
                self._up.cmd_code = val
            elif self._up.write_repeats == 2:
                self._up.cmd_data = val
            else:
                status = I2C_noack
            self._up.smbus.iface.i2c_master_v2.acknowledge(status)

        def read(self):
            self._up.read_repeats = self._up.read_repeats + 1
            if self._up.read_repeats == 1:
                self._up.smbus.iface.i2c_master_v2.read_response(self._up.cmd_data)
            else:
                assert (0)

        def stop(self):
            self._up.stop_cond.append(0)
            self._up.stop_called = self._up.stop_called + 1
            # Clear the counter of read/write
            self._up.read_repeats = 0
            self._up.write_repeats = 0

        def addresses(self):
            return [self._up.addr, self._up.addr+1]

    class cmd_code(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.cmd_code
        def setter(self, val):
            self._up.cmd_code = val



class Smbus_Slave_Word_Data(Smbus_Slave_Byte):
    '''A pseudo SMBus slave receiving word data command from ICH9 SMBus host controller'''
    def _initialize(self):
        super()._initialize()
        self.read_repeats = 0
        self.write_repeats = 0
        self.cmd_code   = 0
        self.cmd_data1  = 0
        self.cmd_data2  = 0

    class i2c_slave(pyobj.Interface):
        def start_request(self, address):
            if address == self._up.addr: # Write command
                self._up.caps_lock = not self._up.caps_lock
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_success)
            elif address == (self._up.addr + 1): # Read command
                self._up.num_lock = not self._up.num_lock
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_success)
            else:
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_noack)

        def write_request(self, val):
            self._up.write_repeats = self._up.write_repeats + 1
            status = I2cConst.status_success
            if self._up.write_repeats == 1:
                self._up.cmd_code = val
            elif self._up.write_repeats == 2:
                self._up.cmd_data1 = val
            elif self._up.write_repeats == 3:
                self._up.cmd_data2 = val
            else:
                status = I2cConst.status_noack
            self._up.smbus.iface.i2c_link.write_response(self._up.conf_obj, status)

        def read_request(self):
            self._up.read_repeats = self._up.read_repeats + 1
            if self._up.read_repeats == 1:
                self._up.smbus.iface.i2c_link.read_response(
                                    self._up.conf_obj, self._up.cmd_data1)
            elif self._up.read_repeats == 2:
                self._up.smbus.iface.i2c_link.read_response(
                                    self._up.conf_obj, self._up.cmd_data2)
            else:
                assert (0)

        def ack_read_request(self, ack):
            if ack == I2cConst.status_success:
                self._up.smbus.iface.i2c_link.ack_read_response(self._up.conf_obj)
            else:
                print("No response from smbus slave device (unsuccessful)")

        def stop(self, repeated_start):
            self._up.stop_cond.append(repeated_start)
            self._up.stop_called = self._up.stop_called + 1
            # Clear the counter of read/write
            self._up.read_repeats = 0
            self._up.write_repeats = 0

    class i2c_slave_v2(pyobj.Interface):
        def start(self, address):
            if address == self._up.addr: # Write command
                self._up.caps_lock = not self._up.caps_lock
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_ack)
            elif address == (self._up.addr + 1): # Read command
                self._up.num_lock = not self._up.num_lock
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_ack)
            else:
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_noack)

        def write(self, val):
            self._up.write_repeats = self._up.write_repeats + 1
            status = I2C_ack
            if self._up.write_repeats == 1:
                self._up.cmd_code = val
            elif self._up.write_repeats == 2:
                self._up.cmd_data1 = val
            elif self._up.write_repeats == 3:
                self._up.cmd_data2 = val
            else:
                status = I2C_noack
            self._up.smbus.iface.i2c_master_v2.acknowledge(status)

        def read(self):
            self._up.read_repeats = self._up.read_repeats + 1
            if self._up.read_repeats == 1:
                self._up.smbus.iface.i2c_master_v2.read_response(self._up.cmd_data1)
            elif self._up.read_repeats == 2:
                self._up.smbus.iface.i2c_master_v2.read_response(self._up.cmd_data2)
            else:
                assert (0)

        def stop(self):
            self._up.stop_cond.append(0)
            self._up.stop_called = self._up.stop_called + 1
            # Clear the counter of read/write
            self._up.read_repeats = 0
            self._up.write_repeats = 0

        def addresses(self):
            return [self._up.addr, self._up.addr+1]

    class cmd_code(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.cmd_code
        def setter(self, val):
            self._up.cmd_code = val

    class cmd_data1(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.cmd_data1
        def setter(self, val):
            self._up.cmd_data1 = val

    class cmd_data2(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.cmd_data2
        def setter(self, val):
            self._up.cmd_data2 = val



class Smbus_Slave_Process_Call(Smbus_Slave_Word_Data):
    '''A pseudo SMBus slave receiving process call command from ICH9 SMBus host controller'''
    def _initialize(self):
        super()._initialize()
        self.cmd_data3 = 0
        self.cmd_data4 = 0

    class i2c_slave(pyobj.Interface):
        def start_request(self, address):
            if address == self._up.addr: # Write command
                self._up.caps_lock = not self._up.caps_lock
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_success)
            elif address == (self._up.addr + 1): # Read command
                self._up.num_lock = not self._up.num_lock
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_success)
            else:
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_noack)

        def write_request(self, val):
            self._up.write_repeats = self._up.write_repeats + 1
            status = I2cConst.status_success
            if self._up.write_repeats == 1:
                self._up.cmd_code = val
            elif self._up.write_repeats == 2:
                self._up.cmd_data1 = val
            elif self._up.write_repeats == 3:
                self._up.cmd_data2 = val
            else:
                status = I2cConst.status_noack
            self._up.smbus.iface.i2c_link.write_response(self._up.conf_obj, status)

        def read_request(self):
            self._up.read_repeats = self._up.read_repeats + 1
            if self._up.read_repeats == 1:
                self._up.smbus.iface.i2c_link.read_response(
                                    self._up.conf_obj, self._up.cmd_data3)
            elif self._up.read_repeats == 2:
                self._up.smbus.iface.i2c_link.read_response(
                                    self._up.conf_obj, self._up.cmd_data4)
            else:
                assert (0)

        def ack_read_request(self, ack):
            if ack == I2cConst.status_success:
                self._up.smbus.iface.i2c_link.ack_read_response(self._up.conf_obj)
            else:
                print("No response from smbus slave device (unsuccessful)")

        def stop(self, repeated_start):
            self._up.stop_cond.append(repeated_start)
            self._up.stop_called = self._up.stop_called + 1
            # Clear the counter of read/write
            self._up.read_repeats = 0
            self._up.write_repeats = 0

    class i2c_slave_v2(pyobj.Interface):
        def start(self, address):
            if address == self._up.addr: # Write command
                self._up.caps_lock = not self._up.caps_lock
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_ack)
            elif address == (self._up.addr + 1): # Read command
                self._up.num_lock = not self._up.num_lock
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_ack)
            else:
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_noack)

        def write(self, val):
            self._up.write_repeats = self._up.write_repeats + 1
            status = I2C_ack
            if self._up.write_repeats == 1:
                self._up.cmd_code = val
            elif self._up.write_repeats == 2:
                self._up.cmd_data1 = val
            elif self._up.write_repeats == 3:
                self._up.cmd_data2 = val
            else:
                status = noI2C_ack
            self._up.smbus.iface.i2c_master_v2.acknowledge(status)

        def read(self):
            self._up.read_repeats = self._up.read_repeats + 1
            if self._up.read_repeats == 1:
                self._up.smbus.iface.i2c_master_v2.read_response(self._up.cmd_data3)
            elif self._up.read_repeats == 2:
                self._up.smbus.iface.i2c_master_v2.read_response(self._up.cmd_data4)
            else:
                assert (0)

        def stop(self):
            self._up.stop_cond.append(0)
            self._up.stop_called = self._up.stop_called + 1
            # Clear the counter of read/write
            self._up.read_repeats = 0
            self._up.write_repeats = 0

        def addresses(self):
            return [self._up.addr, self._up.addr+1]

    class cmd_data3(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.cmd_data3
        def setter(self, val):
            self._up.cmd_data3 = val

    class cmd_data4(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.cmd_data4
        def setter(self, val):
            self._up.cmd_data4 = val

class Smbus_Slave_Block(Smbus_Slave_Byte_Data):
    '''A pseudo SMBus slave receiving block transfer command from ICH9 SMBus host controller'''
    def _initialize(self):
        super()._initialize()
        self.byte_cnt   = 0
        self.block_data = []

    class i2c_slave(pyobj.Interface):
        def start_request(self, address):
            if address == self._up.addr: # Write command
                self._up.caps_lock = not self._up.caps_lock
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_success)
            elif address == (self._up.addr + 1): # Read command
                self._up.num_lock = not self._up.num_lock
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_success)
            else:
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_noack)

        def write_request(self, val):
            self._up.write_repeats = self._up.write_repeats + 1
            status = I2cConst.status_success
            if self._up.write_repeats == 1:
                self._up.cmd_code = val
            elif self._up.write_repeats == 2:
                self._up.byte_cnt = val
            else:
                if self._up.write_repeats <= (self._up.byte_cnt + 2):
                    self._up.block_data.append(val)
                else:
                    status = I2cConst.status_noack
            self._up.smbus.iface.i2c_link.write_response(self._up.conf_obj, status)

        def read_request(self):
            self._up.read_repeats = self._up.read_repeats + 1
            if self._up.read_repeats == 1:
                self._up.smbus.iface.i2c_link.read_response(
                                    self._up.conf_obj, self._up.byte_cnt)
            else:
                if self._up.read_repeats <= (self._up.byte_cnt + 1):
                    self._up.smbus.iface.i2c_link.read_response(
                        self._up.conf_obj,
                        self._up.block_data[self._up.read_repeats - 2])
                else:
                    assert (0)

        def ack_read_request(self, ack):
            if ack == I2cConst.status_success:
                self._up.smbus.iface.i2c_link.ack_read_response(self._up.conf_obj)
            else:
                print("No response from smbus slave device (unsuccessful)")

        def stop(self, repeated_start):
            self._up.stop_cond.append(repeated_start)
            self._up.stop_called = self._up.stop_called + 1
            # Clear the counter of read/write
            self._up.read_repeats = 0
            self._up.write_repeats = 0

    class i2c_slave_v2(pyobj.Interface):
        def start(self, address):
            if address == self._up.addr: # Write command
                self._up.caps_lock = not self._up.caps_lock
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_ack)
            elif address == (self._up.addr + 1): # Read command
                self._up.num_lock = not self._up.num_lock
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_ack)
            else:
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_noack)

        def write(self, val):
            self._up.write_repeats = self._up.write_repeats + 1
            status = I2C_ack
            if self._up.write_repeats == 1:
                self._up.cmd_code = val
            elif self._up.write_repeats == 2:
                self._up.byte_cnt = val
            else:
                if self._up.write_repeats <= (self._up.byte_cnt + 2):
                    self._up.block_data.append(val)
                else:
                    status = I2C_noack
            self._up.smbus.iface.i2c_master_v2.acknowledge(status)

        def read(self):
            self._up.read_repeats = self._up.read_repeats + 1
            if self._up.read_repeats == 1:
                self._up.smbus.iface.i2c_master_v2.read_response(self._up.byte_cnt)
            else:
                if self._up.read_repeats <= (self._up.byte_cnt + 1):
                    self._up.smbus.iface.i2c_master_v2.read_response(self._up.block_data[self._up.read_repeats - 2])
                else:
                    assert (0)

        def stop(self):
            self._up.stop_cond.append(0)
            self._up.stop_called = self._up.stop_called + 1
            # Clear the counter of read/write
            self._up.read_repeats = 0
            self._up.write_repeats = 0

        def addresses(self):
            return [self._up.addr, self._up.addr+1]

    class block_data(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = '[i*]'
        def getter(self):
            return self._up.block_data
        def setter(self, val):
            self._up.block_data = val

    class byte_cnt(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.byte_cnt
        def setter(self, val):
            self._up.byte_cnt = val

class Smbus_Slave_Block_Process(Smbus_Slave_Block):
    '''A pseudo SMBus slave receiving block process call command from ICH9 SMBus host controller'''
    def _initialize(self):
        super()._initialize()
        self.rd_byte_cnt   = 0
        self.rd_block_data = []

    class i2c_slave(pyobj.Interface):
        def start_request(self, address):
            if address == self._up.addr: # Write command
                self._up.caps_lock = not self._up.caps_lock
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_success)
            elif address == (self._up.addr + 1): # Read command
                self._up.num_lock = not self._up.num_lock
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_success)
            else:
                self._up.smbus.iface.i2c_link.start_response(
                                    self._up.conf_obj, I2cConst.status_noack)

        def write_request(self, val):
            self._up.write_repeats = self._up.write_repeats + 1
            status = I2cConst.status_success
            if self._up.write_repeats == 1:
                self._up.cmd_code = val
            elif self._up.write_repeats == 2:
                self._up.byte_cnt = val
            else:
                if self._up.write_repeats <= (self._up.byte_cnt + 2):
                    self._up.block_data.append(val)
                else:
                    status = I2cConst.status_noack
            self._up.smbus.iface.i2c_link.write_response(self._up.conf_obj, status)

        def read_request(self):
            self._up.read_repeats = self._up.read_repeats + 1
            if self._up.read_repeats == 1:
                self._up.smbus.iface.i2c_link.read_response(
                                    self._up.conf_obj, self._up.rd_byte_cnt)
            else:
                if self._up.read_repeats <= (self._up.rd_byte_cnt + 1):
                    self._up.smbus.iface.i2c_link.read_response(
                        self._up.conf_obj,
                        self._up.rd_block_data[self._up.read_repeats - 2])
                else:
                    assert (0)

        def ack_read_request(self, ack):
            if ack == I2cConst.status_success:
                self._up.smbus.iface.i2c_link.ack_read_response(self._up.conf_obj)
            else:
                print("No response from smbus slave device (unsuccessful)")

        def stop(self, repeated_start):
            self._up.stop_cond.append(repeated_start)
            self._up.stop_called = self._up.stop_called + 1
            # Clear the counter of read/write
            self._up.read_repeats = 0
            self._up.write_repeats = 0

    class i2c_slave_v2(pyobj.Interface):
        def start(self, address):
            if address == self._up.addr: # Write command
                self._up.caps_lock = not self._up.caps_lock
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_ack)
            elif address == (self._up.addr + 1): # Read command
                self._up.num_lock = not self._up.num_lock
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_ack)
            else:
                self._up.smbus.iface.i2c_master_v2.acknowledge(I2C_noack)

        def write(self, val):
            self._up.write_repeats = self._up.write_repeats + 1
            status = I2C_ack
            if self._up.write_repeats == 1:
                self._up.cmd_code = val
            elif self._up.write_repeats == 2:
                self._up.byte_cnt = val
            else:
                if self._up.write_repeats <= (self._up.byte_cnt + 2):
                    self._up.block_data.append(val)
                else:
                    status = I2C_noack
            self._up.smbus.iface.i2c_master_v2.acknowledge(status)

        def read(self):
            self._up.read_repeats = self._up.read_repeats + 1
            if self._up.read_repeats == 1:
                self._up.smbus.iface.i2c_master_v2.read_response(self._up.rd_byte_cnt)
            else:
                if self._up.read_repeats <= (self._up.rd_byte_cnt + 1):
                    self._up.smbus.iface.i2c_master_v2.read_response(self._up.rd_block_data[self._up.read_repeats - 2])
                else:
                    assert (0)

        def stop(self):
            self._up.stop_cond.append(0)
            self._up.stop_called = self._up.stop_called + 1
            # Clear the counter of read/write
            self._up.read_repeats = 0
            self._up.write_repeats = 0

        def addresses(self):
            return [self._up.addr, self._up.addr+1]

    class rd_block_data(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = '[i*]'
        def getter(self):
            return self._up.rd_block_data
        def setter(self, val):
            self._up.rd_block_data = val

    class rd_byte_cnt(pyobj.Attribute):
        attrattr = simics.Sim_Attr_Optional
        attrtype = 'i'
        def getter(self):
            return self._up.rd_byte_cnt
        def setter(self, val):
            self._up.rd_byte_cnt = val
