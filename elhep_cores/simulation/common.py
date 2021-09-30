import os
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


def generate_verilog(f, output_file):
    ios = {getattr(f, x) for x in f.__dict__.keys() if x.endswith("_o") or x.endswith("_i")}
    hdl_code = verilog.convert(f, ios).write(output_file)
    update_tb(output_file)

