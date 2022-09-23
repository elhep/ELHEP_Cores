from migen.build.xilinx.platform import XilinxPlatform
from migen.build.generic_platform import *

from migen import *
from migen.fhdl.specials import Memory
from migen.genlib.cdc import BusSynchronizer, PulseSynchronizer
from migen.fhdl import verilog
from artiq.gateware.rtio import rtlink


class SignalBaselineAverage(Module):
    def __init__(self, wsize=16, divider_power_of_two=8):
        """Simple signal baseline averaging module

        Use `i` and `o` for connecting input and outpu data respectively.

        Args:
            wsize (int, optional): Width of the signal vector. Defaults to 16.
            divider_power_of_two (int, optional): Size of the averaging module. Defaults to 2**8.
        """
        self.i = Signal(wsize)
        self.o = Signal(wsize)

        out_reg = Signal(wsize + divider_power_of_two)
        reg = Array(Signal(wsize) for a in range(2**divider_power_of_two + 1))

        for i in range(2**divider_power_of_two-1):
            self.sync += [
                reg[i+1].eq(reg[i]),
            ]

        self.sync += [
            reg[0].eq(self.i),
        ]

        sum = 0
        for i in range(2**divider_power_of_two):
            sum = sum + reg[i] 

        self.sync += [
            out_reg.eq(sum),
        ]

        self.comb += [
            self.o.eq(out_reg[len(out_reg) - wsize:len(out_reg)])
        ]



def testbench(dut):
    yield dut.i.eq(1000)
    for i in range(1000):
        yield

        
if __name__ == "__main__":

    dut = SignalBaselineAverage(16, 8)
    run_simulation(dut, testbench(dut), vcd_name="SignalBaselineAverage.vcd")

    # dut = SignalBaselineAverage(16, 8)
    # print(verilog.convert(dut, {dut.i, dut.o}))