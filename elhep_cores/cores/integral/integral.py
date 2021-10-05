from migen.build.xilinx.platform import XilinxPlatform
from migen.build.generic_platform import *

from migen import *
from migen.genlib.cdc import BusSynchronizer, PulseSynchronizer, ElasticBuffer, MultiReg
from migen.genlib.fifo import AsyncFIFO, AsyncFIFOBuffered
from migen.fhdl import verilog
from artiq.gateware.rtio import rtlink, Channel

from functools import reduce
from operator import and_

from math import log2, ceil


class Integral(Module):

    """Integral

    Implementation of integral according to https://github.com/elhep/MCORD_DAQ_Firmware/issues/5
    """

    def __init__(self, data_in, baseline_in, stb_i, length=7):
        
        
        iiface_width = len(data_in + ceil(log2(length)))
        assert iiface_width <= 32, f"Data width ({iiface_width}) must be <= 32"
        
        self.baseline_in = baseline_in        
        self.data_in = data_in        
        self.stb_i = stb_i        
        self.cnt = Signal(max=length+1)
        self.data_out = Signal(iiface_width)
        self.stb_out = Signal()   
        
        reg = Array(Signal.like(data_in) for a in range(length))

        for i in range(length - 1):
            self.sync += [
                If(self.stb_i == 1, 
                    reg[i+1].eq(reg[i]),
                    self.cnt.eq(self.cnt + 1))
            ]

        self.sync += [
            If(self.stb_i == 1, reg[0].eq(self.data_in - self.baseline_in))
        ]
        

        sum = 0
        for i in range(length):
            sum = sum + reg[i] 

        self.sync += [
            If(self.cnt == length, 
                self.data_out.eq(sum),
                self.cnt.eq(0),
                self.stb_out.eq(1)).Else(
                    self.stb_out.eq(0)
                )
        ]


def testbench(dut, length):
    yield dut.data_in.eq(1000)
    for i in range(1000):
        if i > 10 and i <= 10 + length:
            yield dut.stb_i.eq(1)
        else :
            yield dut.stb_i.eq(0)
        yield

        
if __name__ == "__main__":

    data_in = Signal(20)
    baseline_in = Signal(20)
    stb_i = Signal()
    length = 4

    dut = Integral(data_in, baseline_in, stb_i, length)
    run_simulation(dut, testbench(dut, length), vcd_name="Integral.vcd")

