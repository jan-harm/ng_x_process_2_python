#!/usr/bin/python3

import os
import sys

import numpy as np
import bitarray as ba
from bitarray.util import ba2int, int2ba, zeros


# =ba.bitarray(buffer=a, endian='big')
# from systemd.journal import stream

max_version = 1
size_of_double = 8  # time is double
header_length = 3

FIFO_IN = 'pytest_in'
FIFO_OUT = 'pytest_out'
use_stdin = False
# log_file = "tmp.log"
log_file = None



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
        self.input_bytes =  0 if self.input_bits == 0 else (self.input_bits-1)//8 + 1
        self.size_in = self.input_bytes + size_of_double
        self.output_bits = int(self.header[2])
        self.output_bytes =  0 if self.output_bits == 0 else (self.output_bits-1)//8 + 1
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

    def print_status(self, report_stream):
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

    def io_update(self):
        """update data object with new data from stream
        input data is a bytearray with length of 8 (time) plus number of input bytes"""
        self._raw_in = np.array(bytearray(self.stream_in.read(self.size_in)), dtype=np.uint8)
        report(f'raw in: {bytearray(self._raw_in.tobytes()).hex()}')
        report(f'raw in hex: {self._raw_in}')
        if len(self._raw_in) == 0: # we are done
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
            self.input_data = zeros(0) # empty bitarray

        return True


    def io_send_result(self, result_bits):
        """get byte array for sending to pipe"""
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

#todo: define simple counter function
#      o in count
#      1 in enable
#      2 in up/down
#      n out -> nbit counter
class Counter:
    """Simple function to test interface
    nr of input bits:
    0  just count
    1  1st input is enable (count when high)
    2  2nd input is up/down (high is up)
    nr of output bits:
    n  count to 2**n-1
    """
    def __init__(self, nr_input_bits, nr_output_bits):
        self.enable = nr_input_bits > 0
        self.updown = nr_input_bits > 1
        self.count_max = nr_output_bits ** 2 -1
        self.count = 0
        self.nr_output_bits = nr_output_bits
        report(f' updown {self.updown}  enable {self.enable}')

    def update(self, input_bits):
        report(f'count enable {input_bits[-1]}  up_down {input_bits[-2]}')
        if self.enable and input_bits[-1] == 1:
            report(f' enabled  {input_bits[-1]}  ')
            increment = 1
            if self.updown and  input_bits[-2] == 0:
                report('decrement')
                increment = -1
            self.count = self.count + increment
            report(f'counter {self.count}')
            if self.count > self.count_max:
                self.count = 0
            if self.count < 0:
                self.count = self.count_max

        return  int2ba(self.count, self.nr_output_bits)


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




size_in = np.dtype(np.double).itemsize + 1
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
sim_dat = PipeData(pipe_in, pipe_out)

sim_dat.print_status(report_port)
cnt = Counter(sim_dat.input_bits, sim_dat.output_bits)
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
    # data = pipe_in.read(size_in)  # read a float
    if not sim_dat.io_update():
        report(' no input data')
        break
    report(f' >>>>>>>>>>>>>  input data : {sim_dat.input_data}')
    result = cnt.update(sim_dat.input_data)
    report(f' <<<<<<<<<<<<<  output data : {result}')
    res2 = sim_dat.io_send_result(result)
    # report(' next.')
    # r = pipe_out.write(bytes(counter))
    r = pipe_out.write(bytearray(b'\x03'))
    pipe_out.flush()
    if r == 0:
        report(f'could not write data (r is {r}), port closed is {pipe_out.closed}')
        break
    counter = (counter + 1) % (2 ** sim_dat.output_bits)
    # if counter == 0:
    report(f'loop time {sim_dat.time:3.3e}')
    report(f'counter is {sim_dat.counter}')
    report('')

sim_dat.print_status(report_port)
report_port.flush()
report('\n\ndone...')
report_port.close()




