#!/usr/bin/python3 -u
# test file to examine binary pipes from named pipes and stdin and stdout


import os
import sys
import time

import numpy as np

max_version = 1
size_of_double = 8

FIFO_IN = 'pytest_in'
FIFO_OUT = 'pytest_out'
use_stdin = True
log_file = "tmp.log"


if log_file:
    report_port = open(log_file, 'w')
    report_port.write('start logging\n')
    report_port.flush()
else:
    report_port = sys.stdout
    
def report(msg):
    msg = msg +'\n'
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
header = pipe_in.read(3)
version = header[0]
input_bits = header[1]
output_bits = header[2]

report(' header info:')
for n,v in [('version',version),('input_bits',input_bits),('output_bits', output_bits)]:
    report(f'{n:12}: {v} ')

# respond with header as acknowledge
report('respond header')
dummy_header = bytearray(b'\x01\x00\x04')
r = pipe_out.write(dummy_header)

report(f'written {r} bytes')
# time.sleep(0.01)


report(f' input size is {size_in} bytes')
report(f' output size is {size_out} bytes')
counter = 0
report('starting loop')
while True:
    report(f'count  is {counter}')
    if  pipe_in.closed:
        report('pipe in closed')
        break
    if  pipe_out.closed:
        report('pipe out closed')
        break
    data = pipe_in.read(size_in)  # read a float
    if len(data) == 0:
        report(' no input data')
        break
    report(' next.')
    # r = pipe_out.write(bytes(counter))
    r = pipe_out.write(bytearray(b'\x03'))
    if r == 0:
        report(f'could not write data (r is {r}), port closed is {pipe_out.closed}')
        break
    counter = (counter + 1) % (2 ** output_bits)
    report(f'time {data.hex()}')


# todo: check working on stdin and stdout (for regular calls) whit/without shell
#       best result when using the slash bang, however input stops after header (response is ok)
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
#         report('The pipe is closed on the other end.')
#         p.close()
#

report('\n\ndone...')




