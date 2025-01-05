# test file to examine binary pipes


import os
import sys
import numpy as np
from struct import pack, unpack

max_version = 1
size_of_double = 8

FIFO_IN = 'pytest_in'
FIFO_OUT = 'pytest_out'
# FIFO_IN = '../x_processIn_c/graycode_in'
# FIFO_OUT = '../x_processIn_c/graycode_out'

report_port = sys.stdout
size_in = np.dtype(np.double).itemsize

class PipeData():
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
        byte 2: number of output bits 1,2,3..
        """
        if len(header) > 3:
            raise Exception('header to long.')
        self.version = int(header[0])
        if self.version > max_version:
            raise Exception('version not supported.')
        self.input_bits = int(header[1])
        self.input_bytes =  0 if self.input_bits == 0 else (self.input_bits-1)//8 + 1
        self.output_bits = int(header[2])
        self.output_bytes =  0 if self.input_bits == 0 else (self.input_bits-1)//8 + 1
        self.output_data = bytearray(self.output_bytes)
        self.counter = 0  # counting the entries
        self._reset = False
        self._time = float(0)
        self.last_input = bytearray(b'')
        self.last_output = bytearray(b'')

    def print_status(self, stream):
        print(f'version           : {self.version}', file=stream)
        print(f'nr of input bits  : {self.input_bits}', file=stream)
        print(f'nr of input bytes : {self.input_bytes}', file=stream)
        print(f'nr of output bits : {self.output_bits}', file=stream)
        print(f'nr of output byte : {self.output_bytes}', file=stream)
        print(f'reset             : {self._reset}', file=stream)
        print(f'counter           : {self.counter}', file=stream)
        print(f'simulation time   : {self._time}', file=stream)

    def io_update(self, input_data):
        """update data object with new data from stream
        input data is an bytearray with length of 8 (time) plus number of input bytes"""
        self.last_input = input_data
        self._time = unpack('@d', self.last_input[0:size_of_double])[0]
        self._reset = self._time < 0.0

    def io_get_result(self):
        """get byte array for sending to pipe"""
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
        #       bounderies are crossed.
        pass

    def set_bits(self, low, high, bit_data):
        """set bits in output stream, data is int (so max 64 bits) """
        pass

print(f'expected input size: {size_in}', file=report_port)
# try:
#     os.mkfifo(FIFO)
# except OSError as oe:
#     if oe.errno != errno.EEXIST:
#         raise

print(f"Opening FIFOs:  {FIFO_IN}  and {FIFO_OUT}", file=report_port)

pipe_in = open(FIFO_IN, 'rb', buffering=0)
# pipe_in = open(FIFO_IN, 'rb')
print(pipe_in, file=report_port)
pipe_out = open(FIFO_OUT, 'wb', buffering=0)
# pipe_out = open(FIFO_OUT, 'wb')
print(pipe_out, file=report_port)


# read pipe binary header
print('reading header', file=report_port)
header = pipe_in.read(3)
version = header[0]
input_bits = header[1]
output_bits = header[2]

print(' header info:', file=report_port)
for n,v in [('version',version),('input_bits',input_bits),('output_bits', output_bits)]:
    print(f'{n:12}: {v} ', file=report_port)

# respond with header as acknowledge
print('respond header', file=report_port)
r = pipe_out.write(header)
print(f'written {r} bytes')
counter = 0
print('starting loop', file=report_port)
while True:
    if  pipe_in.closed:
        print('pipe in closed', file=report_port)
        break
    if  pipe_out.closed:
        print('pipe out closed', file=report_port)
        break
    data = pipe_in.read(size_in)  # read a float
    if len(data) == 0:
        print(' no input data', file=report_port)
        break
    print(' next.', file=report_port)
    # r = pipe_out.write(bytes(counter))
    r = pipe_out.write(b'3')
    if r == 0:
        print(f'could not write data (r is {r}), port closed is {pipe_out.closed}', file=report_port)
        break
    counter = (counter + 1) % (2 ** input_bits)
    # if counter == 0:
    print(f'time {data.hex()}', file=report_port)


# todo: check working on stdin and stdout (for regular calls) whit/without shell
# todo: solve blocking at end of program (is it blocking)
# probably solution:
# register POLLHUP and POLLIN dan de functie komt terug wanneer een van deze atief is.
# vercolgens kijken of er data is en os einde file (gesloten pipe). (POLLHUP)
# import select
#
# # ...
#
# poller = select.poll()
# # Register the "hangup" event on p
# poller.register(p, select.POLLHUP)
#
# # Call poller.poll with 0s as timeout
# for descriptor, mask in poller.poll(0):
#     # Can contain at most one element, but still:
#     if descriptor == p.fileno() and mask & select.POLLHUP:
#         print('The pipe is closed on the other end.')
#         p.close()
#

print('\n\ndone...', file=report_port)




