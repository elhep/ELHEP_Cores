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

    def __init__(self, data_width=22, length=7):
        
        
        
        self.baseline_in = Signal(data_width)   
        self.data_in = Signal(data_width)      
        self.stb_i = Signal()        
        self.cnt = Signal(max=length+1)
        self.data_out = Signal(data_width + ceil(log2(length)))
        self.stb_o = Signal()   
        
        reg = Array(Signal(data_width) for a in range(length))

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
                self.stb_o.eq(1)).Else(
                    self.stb_o.eq(0)
                )
        ]


def testbench(dut, length):
    yield dut.data_in.eq(1000)
    yield dut.baseline_in.eq(100)
    for i in range(1000):
        if i > 10 and i <= 10 + length:
            yield dut.stb_i.eq(1)
        else :
            yield dut.stb_i.eq(0)
        yield

        
if __name__ == "__main__":

    # data_in = Signal(20)
    # baseline_in = Signal(20)
    # stb_i = Signal()
    data_width = 20
    length = 4

    dut = Integral(data_width, length)
    run_simulation(dut, testbench(dut, length), vcd_name="Integral.vcd")

