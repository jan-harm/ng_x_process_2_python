#!/usr/bin/python3

import os
import sys

import argparse
import logging
import ng_x_py as ng

#   code start ################################

sys.stderr.writelines(f'{sys.argv} \n\n')
parser = argparse.ArgumentParser(prog=sys.argv[0], exit_on_error=False)
parser.add_argument('--verbose', '-v', action='count', default=0,
                    help='log level use  -vv for debug info')
parser.add_argument('--named_pipe', action='store_true',
                    help='with named pipe logging will be done to stderr')
parser.add_argument('function', action='store',
                    help='function to be used for processing, like counter')
parser.add_argument('--log_file', action='store', default='',
                    help='when nog logfile is used stderr will be used')
args = parser.parse_args(sys.argv[1:])

use_stdin = not args.named_pipe

if args.log_file != '':
    report_port = open(args.log_file, 'w')
else:
    report_port = sys.stderr

# setup logging
lg = logging.getLogger()
db_level = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
if args.verbose >= len(db_level):
    lg.setLevel(logging.DEBUG)
else:
    lg.setLevel(db_level[args.verbose])

handler = logging.StreamHandler(report_port)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
lg.addHandler(handler)

lg.info('start logging of %s', __name__)
lg.info('log level is %s', logging.getLevelName(lg.level))

if use_stdin:
    lg.debug('opening stdin and stdout for data transfer')
    pipe_in = os.fdopen(sys.stdin.fileno(), "rb", closefd=False)
    pipe_out = os.fdopen(sys.stdout.fileno(), "wb", closefd=False)
else:
    lg.debug('Opening FIFOs:  %s for input and  %s for output', ng.FIFO_IN, ng.FIFO_OUT)
    pipe_in = open(ng.FIFO_IN, 'rb', buffering=0)
    pipe_out = open(ng.FIFO_OUT, 'wb', buffering=0)

d_function =  ng.get_loop_function(args.function)

# prepare loop
lg.info('reading header')
sim_dat = ng.PipeData(pipe_in, pipe_out)

sim_dat.log_status(lg)
loop_function = d_function(sim_dat.input_bits, sim_dat.output_bits)

lg.info('starting loop')
while True:
    if pipe_in.closed:
        lg.debug('pipe in closed')
        break
    if pipe_out.closed:
        lg.debug('pipe out closed')
        break
    # data = pipe_in.read(size_in)  # read a float
    if not sim_dat.io_update_from_pipe():
        lg.debug('could not read input (0 bytest)')
        break
    lg.debug('simulation time: %5.3e', sim_dat.time)
    result = loop_function.update(sim_dat.input_data)
    lg.debug('input:  %s, output: %s', str(sim_dat.input_data), str(result))
    res2 = sim_dat.io_send_result_to_pipe(result)
    if res2 == 0:
        lg.debug('could not write data (r is %d), port closed is %d ', res2, pipe_out.closed)
        break

sim_dat.log_status(lg)

lg.info('closing..')
