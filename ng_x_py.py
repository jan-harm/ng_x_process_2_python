#!/usr/bin/python3

import os
import sys

import numpy as np
import bitarray as ba
from bitarray.util import int2ba, zeros
import logging

# constants
max_version = 1  # version of pipe interface
size_of_double = 8  # time is a double
header_length = 3  # three uint8 version, input bit and output bits

FIFO_IN = 'pytest_in'
FIFO_OUT = 'pytest_out'


class PipeData:
    """contains the data from and to the pipes to ngspice
    note that all ins and outs are bits and are packed in bytes
    first the header is send and must be returned as acknowledge
    then ng spice will send a float with simulation time and the input bits packed in bytes if any.
    there will always be a return value so at least one byte is returned.

    use header to construct an object
    then transform the input data
    perform the calculations on the object
    return the output data
    """

    def __init__(self, stream_in, stream_out):
        """ stream is a fifo input from which the header is read.
        header is a 3 byte array received from ng spice:
        byte 0: version of format (0x1)
        byte 1: number of input bits 0,1,2...
        byte 2: number of output bits 1,2,3...
        The io bits are packed in bytes
        """
        self.stream_in = stream_in
        self.stream_out = stream_out

        header = stream_in.read(header_length)
        self.header = np.array(bytearray(header), dtype=np.uint8)
        self.version = int(self.header[0])
        if self.version > max_version:
            raise Exception('version not supported.')
        self.input_bits = int(self.header[1])
        self.input_bytes = 0 if self.input_bits == 0 else (self.input_bits - 1) // 8 + 1
        self.size_in = self.input_bytes + size_of_double
        self.output_bits = int(self.header[2])
        self.output_bytes = 0 if self.output_bits == 0 else (self.output_bits - 1) // 8 + 1
        self._raw_in = np.array(bytearray(b'\x00'), dtype=np.uint8)
        self.input_data = zeros(self.input_bits)
        self.output_data = zeros(self.output_bits)
        self._raw_out = np.array(bytearray(b'\x00'), dtype=np.uint8)
        self.counter = 0  # counting the entries
        self._reset = False
        self._reset_count = 0
        self._time = float(0)
        self._first_time = np.nan
        self._first_time_valid = False
        self.last_input_data = self.input_data
        self.last_output_data = self.output_data
        # response to pipe
        self.stream_out.write(self.header)
        self.stream_out.flush()

    def log_status(self, logger):
        if logger.level <= logging.DEBUG:
            logger.debug('header;')
            logger.debug('version               : %d', self.version)
            logger.debug('nr of input bits      : %d', self.input_bits)
            logger.debug('nr of input bytes     : %d', self.input_bytes)
            logger.debug('nr of output bits     : %d', self.output_bits)
            logger.debug('nr of output bytes    : %d', self.output_bytes)
            logger.debug('reset                 : %d', self._reset)
            logger.debug('counter               : %d', self.counter)
            logger.debug('first simulation time : %5.3e', self._first_time)
            logger.debug('last simulation time  : %5.3e', self.time)
            logger.debug('number of resets      : %d', self._reset_count)
            logger.debug('last input data       : %s', str(self.last_input_data))
            logger.debug('last output data      : %s', str(self.last_output_data))

    def io_update_from_pipe(self):
        """update data object with new data from stream
        input data is a bytearray with length of 8 (time) plus number of input bytes"""
        self._raw_in = np.array(bytearray(self.stream_in.read(self.size_in)), dtype=np.uint8)
        if len(self._raw_in) == 0:  # we are done
            return False
        self._time = self._raw_in[0:size_of_double].view(np.float64)[0]
        self._reset = self._time < 0.0
        if self._reset:
            self._reset_count += 1
        self.counter = 0 if self._reset else self.counter + 1
        if self._first_time_valid == False and not self._reset:
            self._first_time = self._time
            self._first_time_valid = True

        if self.input_bytes > 0:
            tmp_input_data = ba.bitarray(buffer=self._raw_in[size_of_double:], endian='big')
            self.input_data = tmp_input_data[-self.input_bits:]
        else:
            self.input_data = zeros(0)  # empty bitarray

        return True

    def io_send_result_to_pipe(self, result_bits):
        """Input is bitarray with result from digital function
        - bookkeeping is updated
        - data converted to bytes()
        - data send to pipe
        return number of bytes send"""
        self.last_input_data = self.input_data
        self.last_output_data = self.output_data
        self.output_data = result_bits
        # align to bytes first and den convert to bytes
        tmp_data = ba.bitarray(result_bits, endian='big')
        o_data = ba.bitarray(self.output_bytes * 8 - len(tmp_data), endian='big') + tmp_data
        nr_of_bytes = self.stream_out.write(o_data.tobytes())
        self.stream_out.flush()
        return nr_of_bytes

    @property
    def time(self):
        return self._time

    @property
    def reset(self):
        return self._reset


class Counter:
    """Simple function to test interface
    nr of input bits:
    0  just count
    1  1st input is enable (count when high)
    2  2nd input is up/down (high is up)
    nr of output bits:
    n  count to 2**n-1
    Counter is initialized on 0 and an update updates the counter and returns the new state
    """

    def __init__(self, nr_input_bits, nr_output_bits):
        self.enable = nr_input_bits > 0
        self.updown = nr_input_bits > 1
        self.count_max = nr_output_bits ** 2 - 1
        self.count = 0
        self.nr_output_bits = nr_output_bits
        lg.debug(f'init counter, updown %s  enable %s', str(self.updown), str(self.enable))

    def update(self, input_bits):
        """Input bit array or None"""
        increment = 1
        if self.enable:
            if input_bits[-1] != 1:
                increment = 0
            if self.updown:
                if input_bits[-2] == 0:
                    increment = -increment
        self.count = self.count + increment
        if self.count > self.count_max:
            self.count = 0
        if self.count < 0:
            self.count = self.count_max
        value = int2ba(self.count, self.nr_output_bits)
        lg.debug('counter update: value %d, input bits %s  output bits %s',
                 self.count, str(input_bits), str(value))

        return value

class Shifter:
    """Simple shift function
    with one input shift input in register
    with two inputs, first is data second is enable
    nr of outputs bits:
    n gives a register of nbits"""
    def __init__(self, nr_input_bits, nr_output_bits):
        if nr_input_bits == 0:
            lg.warning(' shifter should have at least one bit input for data')
            raise Exception('not enough inputs for shifter')
        self.enable = nr_input_bits > 1
        self.shift_register = zeros(nr_output_bits)
        self.nr_output_bits = nr_output_bits
        lg.debug(f'init shifter, enable %s', str(self.enable))

    def update(self, input_bits):
        """ update shift register when enabled"""
        enabled = True
        if self.enable:
            enabled = input_bits[1] == 1
        if enabled:
            self.shift_register >>= 1
            self.shift_register[0] = input_bits[0]
        return self.shift_register


# table with allowed functions (lower case keys only)
function_table = {'counter': Counter,
                  'shifter': Shifter}

def get_loop_function(name):
    if name in function_table:
        d_function = function_table[name]
    else:
        lg.debug('function %s not found', name)
        lg.debug('functions available:')
        for f in function_table:
            lg.debug('  %s', f)
        raise Exception(' no function found')
    return d_function


lg = logging.getLogger(__name__)