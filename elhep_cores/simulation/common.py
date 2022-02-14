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


def get_rtio_signals(rtlink, link_name=None):
    ios = set()
    if hasattr(rtlink, "i"):
        ios.add(rtlink.i.stb)
        if link_name:
            rtlink.i.stb.name_override = f"{link_name}_stb_o"
        if hasattr(rtlink.i, "data"):
            ios.add(rtlink.i.data)
            if link_name:
                rtlink.i.data.name_override = f"{link_name}_data_o"

    if hasattr(rtlink, "o"):
        if hasattr(rtlink.o, "address"):
            ios.add(rtlink.o.address)
            if link_name:
                rtlink.o.address.name_override = f"{link_name}_address_i"
        if hasattr(rtlink.o, "data"):
            ios.add(rtlink.o.data)
            if link_name:
                rtlink.o.data.name_override = f"{link_name}_data_i"
        ios.add(rtlink.o.stb)
        if link_name:
            rtlink.o.stb.name_override = f"{link_name}_stb_i"
    if link_name:
        for signal in ios:
            print(signal.__dict__)
    return ios


def get_ios(f):
    """Finds all IOs following _i/_o suffixes and includes sink/source fields"""
    ios = {getattr(f, x) for x in f.__dict__.keys() if x.endswith("_o") or x.endswith("_i")}
    return ios


def get_all_ios(f):
    ios = get_ios(f)
    if hasattr(f, "source"):
        ios = ios.union(get_stream_signals(f.source))
    if hasattr(f, "sink"):
        ios = ios.union(get_stream_signals(f.sink))
    return ios


def generate_verilog(f, output_file, ios=None):
    if ios is None:
        ios = get_all_ios(f)
    verilog.convert(f, ios, display_run=True).write(output_file)
    update_tb(output_file)

