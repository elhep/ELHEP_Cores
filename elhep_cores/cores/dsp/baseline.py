from migen.build.xilinx.platform import XilinxPlatform
from migen.build.generic_platform import *

from migen import *
from migen.fhdl.specials import Memory
from migen.genlib.cdc import BusSynchronizer, PulseSynchronizer
from migen.fhdl import verilog
from artiq.gateware.rtio import rtlink

from functools import reduce
from operator import and_, add

from math import cos, sin, pi
from scipy import signal
import numpy as np


class SignalBaseline(Module):
    def __init__(self, wsize=16, fs=100000000.0, cutoff=10000.0, trans_width=1000000.0, numtaps=266):
        """Signal baseline computation module

        This is basically LPF designed with the given parameters.

        Use `i` and `o` for connecting input and outpu data respectively.

        Args:
            wsize (int, optional): Width of the signal vector. Defaults to 16.
            fs (float, optional): Sampling frequency in Hz. Defaults to 100000000.0.
            cutoff (float, optional): Cutoff frequency in Hz. Defaults to 10000.0.
            trans_width (float, optional): Width of transition from pass band to stop band in Hz. Defaults to 10000.0.
            numtaps (int, optional): Size of the FIR filter. Defaults to 266.
        """
        # Compute filter coefficients with SciPy
        coef = signal.remez(numtaps, [0, cutoff, cutoff + trans_width, 0.5 * fs], [1, 0], fs=fs)

        self.coef = coef
        self.wsize = wsize
        self.i = Signal((self.wsize, True))
        self.o = Signal((self.wsize, True))

        ###

        muls = []
        src = self.i
        for c in self.coef:
            sreg = Signal((self.wsize, True))
            self.sync += sreg.eq(src)
            src = sreg
            c_fp = int(c * 2 ** (self.wsize - 1))
            muls.append(c_fp * sreg)
        sum_full = Signal((2 * self.wsize - 1, True))
        self.sync += sum_full.eq(reduce(add, muls))
        self.comb += self.o.eq(sum_full >> self.wsize - 1)

      
class SimulationWrapper(Module):

    def __init__(self):

        self.clock_domains.cd_sys = cd_sys = ClockDomain()

        self.io = [
            cd_sys.clk,
            cd_sys.rst
        ]

        self.submodules.dut = dut = SignalBaseline()
                                         
        self.io += [    
            dut.o,
            dut.i
        ]



if __name__ == "__main__":
    
    # Generate simulation source for Cocotb
    from migen.build.xilinx import common
    from elhep_cores.simulation.common import update_tb

    module = SimulationWrapper()
    so = dict(common.xilinx_special_overrides)
    so.update(common.xilinx_s7_special_overrides)

    verilog.convert(fi=module,
                    name="top",
                    special_overrides=so,
                    ios={*module.io},
                    create_clock_domains=True).write('dut.v')
    update_tb('dut.v')