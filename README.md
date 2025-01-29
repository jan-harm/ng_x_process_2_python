# ngspice d_process interface in python

 A small python program to interface to the pipes of x_process.
  
## usage
go to the local folder and then type
```commandline
ngspice pipe_test.cir
``` 
In the given solution ngspice will run pipe_test.cir and the lines
```
; test with python, different log files for tracebility
ap0_4 [enable up_down] clk1 null [q1 q2 q3 q4] proc0
.model proc0 d_process (process_file="pytest" process_params=["-vvv", "--log_file", "first.log", "counter"])

ap1_4 [up_down enable] clk1 null [o1 o2 o3 o4] proc1
.model proc1 d_process (process_file="pytest", process_params=["shifter","-v", "--log_file", "shifter.log]))

```
will call the simple shell pytest that in return calls the pyhon interpreter and the script file pipe_example.py
arguments are passed to the script. when calling with -h
```
usage: pipe_example.py
       [-h] [--verbose] [--named_pipe] [--log_file LOG_FILE] function

positional arguments:
  function             function to be used for processing, like counter

options:
  -h, --help           show this help message and exit
  --verbose, -v        log level use -vv for debug info
  --named_pipe         with named pipe logging will be done to stderr
  --log_file LOG_FILE  when nog logfile is used stderr will be used

Process finished with exit code 0

```
The function should be counter or shifter, see the classes in ng_x_py.py
A simple bitarray is used for interface to shifter and counter.

## requirements
- tests done on  Ubuntu 24.04.1 LTS
- ngspice must be installed for command line use (Kicad uses a dll)
- ngspice version 44, a complete build was done to avoid conflicting with Kicad. (.cm file folder will conflict)