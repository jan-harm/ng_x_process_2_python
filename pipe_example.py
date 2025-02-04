#!/usr/bin/python3


import ng_x_py as ng
import logging
import logging_tree

# todo: register available functions
#  register
logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

app = ng.App(logger)

with open('logtree.tmp', 'w') as file_object:
    file_object.write(logging_tree.format.build_description())
    file_object.close()
# lg.setLevel(ng.logging.DEBUG)
logger.info('----------------------starting loop  log from main')
app.run()
logger.info('-------------------------ending loop  log from main')




