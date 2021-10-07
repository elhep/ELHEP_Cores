import os

from migen import *
from migen.fhdl import verilog


def update_tb(verilog_path):
    with open(verilog_path) as f:
        design = f.read()

    design = design.replace("/* Machine-generated using Migen */", """/* Machine-generated using Migen */

`timescale 1ns/1ps
""")
    design = design.replace("endmodule", """`ifdef COCOTB_SIM
initial begin
  $dumpfile ("top.vcd");
  $dumpvars (0, top);
  #1;
end
`endif

endmodule
""")

    with open(verilog_path, 'w') as f:
        f.write(design)


def get_record_signals(record):
    signals = set()
    for k, v in record.__dict__.items():
        if isinstance(v, Signal):
            signals.add(v)
        elif isinstance(v, Record):
            signals = signals.union(get_record_signals(v))
    return signals


def get_stream_signals(endpoint):
    ios = {getattr(endpoint, x) for x in ["stb", "ack", "eop"]}
    ios = ios.union(get_record_signals(endpoint.payload))
    return ios


def get_ios(f):
    """Finds all IOs following _i/_o suffixes and includes sink/source fields"""
    ios = {getattr(f, x) for x in f.__dict__.keys() if x.endswith("_o") or x.endswith("_i")}
    if hasattr(f, "source"):
        ios = ios.union(get_stream_signals(f.source))
    if hasattr(f, "sink"):
        ios = ios.union(get_stream_signals(f.sink))
    return ios


def generate_verilog(f, output_file):
    verilog.convert(f, get_ios(f)).write(output_file)
    update_tb(output_file)

