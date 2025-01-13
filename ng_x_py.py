#!/usr/bin/python3

import os
import sys
from struct import unpack

import numpy as np
from systemd.journal import stream

max_version = 1
size_of_double = 8
header_length = 3

FIFO_IN = 'pytest_in'
FIFO_OUT = 'pytest_out'
use_stdin = True
log_file = "tmp.log"
# log_file = None



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
    def __init__(self, header):
        """ header is a 3 byte array received from ng spice:
        byte 0: version of format (0x1)
        byte 1: number of input bits 0,1,2...
        byte 2: number of output bits 1,2,3...
        """
        if len(header) > 3:
            raise Exception(f'header to long.  {header}')
        self.header = np.array(bytearray(header), dtype=np.uint8)
        self.version = int(self.header[0])
        if self.version > max_version:
            raise Exception('version not supported.')
        self.input_bits = int(self.header[1])
        self.input_bytes =  0 if self.input_bits == 0 else (self.input_bits-1)//8 + 1
        self.output_bits = int(self.header[2])
        self.output_bytes =  0 if self.output_bits == 0 else (self.output_bits-1)//8 + 1
        self.input_data = np.zeros(self.input_bytes, dtype=np.uint8)
        self.output_data = bytearray(self.output_bytes)
        self.counter = 0  # counting the entries
        self._reset = False
        self._reset_count = 0
        self._time = float(0)
        self._first_time = np.nan
        self._first_time_valid = False
        self.last_input = self.input_data
        self.last_output = self.output_data

    def print_status(self, report_stream):
        print(f'header                : {self.header}', file=report_stream)
        print(f'version               : {self.version}', file=report_stream)
        print(f'nr of input bits      : {self.input_bits}', file=report_stream)
        print(f'nr of input bytes     : {self.input_bytes}', file=report_stream)
        print(f'nr of output bits     : {self.output_bits}', file=report_stream)
        print(f'nr of output bytes    : {self.output_bytes}', file=report_stream)
        print(f'reset                 : {self._reset}', file=report_stream)
        print(f'counter               : {self.counter}', file=report_stream)
        print(f'first simulation time : {self._first_time:3.5e}', file=report_stream)
        print(f'last simulation time  : {self.time:3.5e}', file=report_stream)
        print(f'number of resets      : {self._reset_count}', file=report_stream)
        print(f'last input data       : {self.last_input}', file=report_stream)
        print(f'last output data      : {self.last_output}', file=report_stream)
        report_stream.flush()


    def io_update(self, input_data):
        """update data object with new data from stream
        input data is an bytearray with length of 8 (time) plus number of input bytes"""
        self.last_input = np.array(bytearray(input_data), dtype=np.uint8)
        self._time = self.last_input[0:8].view(np.float64)[0]
        self._reset = self._time < 0.0
        if self._reset:
            self._reset_count += 1
        self.counter = 0 if self._reset else self.counter + 1
        if self._first_time_valid == False and not self._reset:
            self._first_time = self._time
            self._first_time_valid = True


    def io_get_result(self):
        """get byte array for sending to pipe"""
        self.last_input = self.input_data
        self.last_output = self.output_data
        return self.output_data


    @property
    def time(self):
        return self._time

    @property
    def reset(self):
        return self._reset

    def get_bits(self, low, high):
        """returns bits from input data"""
        if high > self.input_bits:
            raise Exception('wrong bit mapping')
        # todo: implement bits grabbing, note bits grabbing from bytearray might be slow when byte
        #       boundaries are crossed.
        pass

    def set_bits(self, low, high, bit_data):
        """set bits in output stream, data is int (so max 64 bits) """
        pass


if use_stdin:
    if log_file is None:
        report_port = sys.stderr
    else:
        report_port = open(log_file, 'w')
    report_port.write('start logging\n')
    report_port.flush()
else:
    report_port = sys.stdout


def report(msg):
    msg = msg + '\n'
    report_port.write(msg)
    report_port.flush()




size_in = np.dtype(np.double).itemsize
size_out = 1

report(f'expected input size: {size_in}')

if use_stdin:
    report('using stdin and out in detached mode')

    # pipe_in = sys.stdin.buffer
    # remap to binary in and out
    pipe_in = os.fdopen(sys.stdin.fileno(), "rb", closefd=False)
    pipe_out = os.fdopen(sys.stdout.fileno(), "wb", closefd=False)
else:
    report(f"Opening FIFOs:  {FIFO_IN}  and {FIFO_OUT}")
    pipe_in = open(FIFO_IN, 'rb', buffering=0)
    # pipe_in = open(FIFO_IN, 'rb')
    report(f'{pipe_in}')
    pipe_out = open(FIFO_OUT, 'wb', buffering=0)
    # pipe_out = open(FIFO_OUT, 'wb')
    report(f'{pipe_out}')


# read pipe binary header
report('reading header')
sim_dat = PipeData(pipe_in.read(header_length))

sim_dat.print_status(report_port)

report('respond header')
dummy_header = bytearray(b'\x01\x00\x04')
r = pipe_out.write(sim_dat.header)
pipe_out.flush()

report(f'written {r} bytes')


report(f' input size is {size_in} bytes')
report(f' output size is {size_out} bytes')
counter = 0
report('starting loop')
while True:
    if pipe_in.closed:
        report('pipe in closed')
        break
    if pipe_out.closed:
        report('pipe out closed')
        break
    data = pipe_in.read(size_in)  # read a float
    if len(data) == 0:
        report(' no input data')
        break
    sim_dat.io_update(data)
    # report(' next.')
    # r = pipe_out.write(bytes(counter))
    r = pipe_out.write(bytearray(b'\x03'))
    pipe_out.flush()
    if r == 0:
        report(f'could not write data (r is {r}), port closed is {pipe_out.closed}')
        break
    counter = (counter + 1) % (2 ** sim_dat.output_bits)
    if counter == 0:
        report(f'loop time {sim_dat.time:3.3e}')

sim_dat.print_status(report_port)
report_port.flush()
report('\n\ndone...')
report_port.close()




