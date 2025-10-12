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


import pyobj
import simics

class can_controller(pyobj.ConfObject):
    ''' this is a faked CAN controller'''
    _class_desc = 'fake CAN Controller'
    def _initialize(self):
        super()._initialize()
        self.frame_extended.val    = False
        self.frame_identifier.val  = 0
        self.frame_rtr.val         = False
        self.frame_data_length.val = 0
        self.frame_data.val        = [0]*8
        self.frame_crc.val         = 0

    def get_message(self):
        return self.rev_buf
    class can_device(pyobj.Interface):
        def receive(self, message):
            self._up.frame_extended.val    = message.extended
            self._up.frame_identifier.val  = message.identifier
            self._up.frame_rtr.val         = message.rtr
            self._up.frame_data_length.val = message.data_length
            self._up.frame_data.val        = list(message.data)
            self._up.frame_crc.val         = message.crc

            if message.rtr:
                rtr_d = 1
            else:
                rtr_d = 0
            if message.extended:
                extended_d = "True"
            else:
                extended_d = "False"

            print("extended = %s, identifier = %d, rtr = %d," \
                    " data_length = %d, data = %s, crc = %d" \
                    %(extended_d,
                      message.identifier,
                      rtr_d,
                      message.data_length,
                      message.data,
                      message.crc))
    class frame_extended(pyobj.SimpleAttribute(None, 'b')):
        '''can frame extended'''

    class frame_identifier(pyobj.SimpleAttribute(None, 'i')):
        '''can frame identifier'''

    class frame_rtr(pyobj.SimpleAttribute(None, 'b')):
        '''can frame rtp'''

    class frame_data_length(pyobj.SimpleAttribute(None, 'i')):
        '''can frame data_length'''

    class frame_data(pyobj.SimpleAttribute(None, '[iiiiiiii]')):
        '''can frame data'''

    class frame_crc(pyobj.SimpleAttribute(None, 'i')):
        '''can frame crc'''

    class link(pyobj.SimpleAttribute(None, 'n|o')):
        '''can link '''
