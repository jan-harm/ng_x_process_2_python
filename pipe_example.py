#!/usr/bin/python3


import ng_x_py as ng
import logging
import logging_tree
from bitarray.util import zeros

class Delay:
    """Simple delay function
    with one input shift input in delay line
    with two inputs, first is data second is enable
    one output bit active (more are ignored)
    Note minimal delay is one.
    """

    def __init__(self, nr_input_bits, nr_output_bits, arg1=None, arg2=None):
        if nr_input_bits == 0:
            logger.warning(' delay should have at least one bit input for data')
            raise Exception('not enough inputs for delay')
        self.clocks_delay = int(arg1) if int(arg1) > 1 else 1
        self.enable = nr_input_bits > 1
        self.delay_register = zeros(self.clocks_delay)
        self.nr_output_bits = nr_output_bits
        logger.debug(f'init delay, total delay is %d clocks, enable is %s', self.clocks_delay, str(self.enable))

    def update(self, input_bits):
        """ update shift register when enabled"""
        enabled = True
        if self.enable:
            enabled = input_bits[1] == 1
        if enabled:
            self.delay_register >>= 1
            self.delay_register[0] = input_bits[0]
        ret_val = self.delay_register[-1:]
        return ret_val



ng.register_function('delay', Delay)

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

app = ng.App(logger) # initialize all

logger.info('----------------------starting loop  log from main')
app.run()
logger.info('-------------------------ending loop  log from main')




