#!/usr/bin/python3

import os
import sys

import numpy as np
import bitarray as ba
from bitarray.util import int2ba, zeros
import argparse

# constants
max_version = 1
size_of_double = 8  # time is double
header_length = 3

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

    def log_status(self, report_stream):
        # todo: simplify
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
        print(f'last input data       : {self.last_input_data}', file=report_stream)
        print(f'last output data      : {self.last_output_data}', file=report_stream)
        report_stream.flush()

    def io_update_from_pipe(self):
        """update data object with new data from stream
        input data is a bytearray with length of 8 (time) plus number of input bytes"""
        self._raw_in = np.array(bytearray(self.stream_in.read(self.size_in)), dtype=np.uint8)
        report(f'raw in: {bytearray(self._raw_in.tobytes()).hex()}')
        report(f'raw in hex: {self._raw_in}')
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
            report(f'total input bits {tmp_input_data}')
            self.input_data = tmp_input_data[-self.input_bits:]
        else:
            self.input_data = zeros(0)  # empty bitarray

        return True

    def io_send_result_to_pipe(self, result_bits):
        """Input is bitarray with result from digital function
        - book keeping is updated
        - data converted to bytes()
        - data send to pipe
        return number of bytes send"""
        self.last_input_data = self.input_data
        self.last_output_data = self.output_data
        self.output_data = result_bits
        # align to bytes first and den convert to bytes
        tmp_data = ba.bitarray(result_bits, endian='big')
        o_data = ba.bitarray(self.output_bytes * 8 - len(tmp_data), endian='big') + tmp_data
        # cnt = self.stream_out.write(bytearray(o_data.tobytes()))
        # self.stream_out.flussh()
        report(f'bits {o_data}')
        report(f'hex {o_data.tobytes().hex()}')
        nr_of_bytes =  self.stream_out.write(o_data.tobytes())
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
        report(f' updown {self.updown}  enable {self.enable}')

    def update(self, input_bits):
        """Input bit array or None"""
        # report(f'count enable {input_bits[-1]}  up_down {input_bits[-2]}')
        increment = 1
        if self.enable:
            if input_bits[-1] != 1:
                increment = 0
            report(f' enabled  {input_bits[-1]}  ')
            if self.updown:
                report('up/down enabled')
                if input_bits[-2] == 0:
                    report('decrement')
                    increment = -increment
        self.count = self.count + increment
        if self.count > self.count_max:
            self.count = 0
        if self.count < 0:
            self.count = self.count_max
        report(f'counter {self.count}')

        return int2ba(self.count, self.nr_output_bits)


def report(msg):
    msg = msg + '\n'
    report_port.write(msg)
    report_port.flush()


# table with allowed functions.
function_table = {'counter': Counter}
#   code start ################################

parser = argparse.ArgumentParser(prog=sys.argv[0], exit_on_error=False)
parser.add_argument('--named_pipe', action='store_true')
parser.add_argument('function', action='store', default='Counter')
parser.add_argument('--log_file', action='store', default='ng_x_py.log')
args = parser.parse_args(sys.argv[1:])


use_stdin = not args.named_pipe

if use_stdin:
    report_port = open(args.log_file, 'w')
    report_port.write('start logging\n')
    report_port.flush()
else:
    report_port = sys.stdout

if use_stdin:
    report('using stdin and out in detached mode')
    pipe_in = os.fdopen(sys.stdin.fileno(), "rb", closefd=False)
    pipe_out = os.fdopen(sys.stdout.fileno(), "wb", closefd=False)
else:
    report(f"Opening FIFOs:  {FIFO_IN}  and {FIFO_OUT}")
    pipe_in = open(FIFO_IN, 'rb', buffering=0)
    report(f'{pipe_in}')
    pipe_out = open(FIFO_OUT, 'wb', buffering=0)
    report(f'{pipe_out}')

if args.function in function_table:
    d_function = function_table[args.function]
else:
    report(f'function {args.function} not found')
    report('functions available:')
    for f in function_table:
        report(f'   {f}')
    raise Exception(' no function found')

# prepare loop
report('reading header')
sim_dat = PipeData(pipe_in, pipe_out)

sim_dat.log_status(report_port)
loop_function = d_function(sim_dat.input_bits, sim_dat.output_bits)

report('starting loop')
while True:
    if pipe_in.closed:
        report('pipe in closed')
        break
    if pipe_out.closed:
        report('pipe out closed')
        break
    # data = pipe_in.read(size_in)  # read a float
    if not sim_dat.io_update_from_pipe():
        report(' no input data')
        break
    report(f' >>>>>>>>>>>>>  input data : {sim_dat.input_data}')
    result = loop_function.update(sim_dat.input_data)
    report(f' <<<<<<<<<<<<<  output data : {result}')
    res2 = sim_dat.io_send_result_to_pipe(result)
    report(f'nr of bytes send to pipe: {res2}')
    if res2 == 0:
        report(f'could not write data (r is {r}), port closed is {pipe_out.closed}')
        break
    report(f'loop time {sim_dat.time:3.3e}')
    report(f'counter is {sim_dat.counter}')
    report('')

sim_dat.log_status(report_port)

report('\n\ndone...')
report_port.flush()
report_port.close()

# todo: make a clear startup and loop. Note that a second ngspice run will resend the header without reopening the pipe.
