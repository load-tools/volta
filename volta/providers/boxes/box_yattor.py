import logging
import Queue as queue
import time
import numpy as np
import json

from volta.common.interfaces import VoltaBox
from volta.common.util import Drain, TimeChopper, string_to_np
from volta.common.resource import manager as resource
from ctypes import *
# https://docs.python.org/2/library/ctypes.html


logger = logging.getLogger(__name__)


class YattorBox(VoltaBox):
    """
    Attributes:
        chop_ratio (int): chop ratio for incoming data, 1 means 1 second (500 for sample_rate 500)
        grab_timeout (int): timeout for grabber
    """
    def __init__(self, config):
        VoltaBox.__init__(self, config)
        self.lib = CDLL("libyattor.so")
        #self.source = config.get_option('volta', 'source', '/dev/cu.wchusbserial1420')
        self.sample_rate = 10000 # config.get_option('volta', 'sample_rate', 10000)
        self.chop_ratio = config.get_option('volta', 'chop_ratio', 1)
        self.grab_timeout = config.get_option('volta', 'grab_timeout', 1)
        #self.slope = config.get_option('volta', 'slope', 1)
        #self.offset = config.get_option('volta', 'offset', 0)
        if self.lib.yattor_open()!=0:
            RuntimeError("Unable to open yattor")
        self.grabber_q = None


    def start_test(self, results):
        self.grabber_q = results
        if self.lib.yattor_purge()!=0:
            RuntimeError("Unable to purge yattor")
        if self.lib.yattor_start(0)!=0:
            RuntimeError("Unable to start yattor")

        self.reader = YattorReader(self.lib, self.sample_rate)
        self.pipeline = Drain(
            TimeChopper(
                self.reader, self.sample_rate, self.chop_ratio
            ),
            self.grabber_q
        )
        logger.info('Starting grab thread...')
        self.pipeline.start()
        logger.debug('Waiting grabber thread finish...')


    def end_test(self):
        self.lib.yattor_stop()
        self.reader.close()
        self.pipeline.close()
        self.pipeline.join(10)
        self.lib.yattor_close()
        del self.reader
        del self.lib


    def get_info(self):
        data = {}
        if self.pipeline:
            data['grabber_alive'] = self.pipeline.isAlive()
        if self.grabber_q:
            data['grabber_queue_size'] = self.grabber_q.qsize()
        return data



class YattorReader(object):
    def __init__(self, source, sample_rate):#, slope=1, offset=0):
        self.closed = False
        self.lib = source
        self.sample_rate = sample_rate
        #FloatArray_t = c_float * (sample_rate*2)
        #self.floatBuffer = FloatArray_t()
        WordArray_t = c_ushort * (sample_rate*2)
        self.wordBuffer = WordArray_t()
        """self.slope = slope
        self.offset = offset
        self.SamplesBufferType = c_ushort * (sample_rate*2)
        self.samples_buf = self.SamplesBufferType()
        self.power_voltage = 5.1
        self.AmpGain = 25.07
        self.R_SHUNT = 0.1
        self.BaseVoltageOffset = 36
        self.RAW_MAXf = (float) (0xFFF)
        self.Voffset = self.BaseVoltageOffset * self.power_voltage / self.RAW_MAXf"""


    def _read_chunk(self):
        #amount = self.lib.yattor_read_ampere_float(-1, self.sample_rate*2, self.floatBuffer)
        amount = self.lib.yattor_read_milliampere(-1, self.sample_rate*2, self.wordBuffer)
        if amount>0:
            #chunk = np.frombuffer(buffer=self.floatBuffer, dtype=np.float32, count=amount)
            chunk = np.frombuffer(buffer=self.wordBuffer, dtype=np.uint16, count=amount)#.astype(np.float32)
            return chunk


    """def _read_chunk(self):
        amount = self.lib.yattor_read_raw(-1, self.sample_rate*2, self.samples_buf)
        if amount>0:
            ""logger.info('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
            logger.info(str(len(data))+' '+str(self.sample_rate * 2 * 10))
            logger.info(data[0:20])
            logger.info(":".join("{:02x}".format(ord(c)) for c in data[0:20])) logger.info(' ')""
            chunk = np.frombuffer(buffer=self.samples_buf, dtype=np.uint16, count=amount).astype(np.float32)
            #chunk = chunk * (self.power_voltage/self.RAW_MAXf) * self.slope + self.offset
            chunk = ( chunk * self.power_voltage / self.RAW_MAXf - self.Voffset ) * self.AmpGain / self.R_SHUNT
            return chunk"""


    def __iter__(self):
        while not self.closed:
            yield self._read_chunk()
        yield self._read_chunk()


    def close(self):
        self.closed = True
