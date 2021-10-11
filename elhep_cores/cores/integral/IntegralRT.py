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

from elhep_cores.cores.integral.integral import Integral


class IntegralRT(Module):

    """
    RT Link wrapper for Integral

    This module provides RTIO channels and  is to be used with rtlink.Channel.from_phy.
    No combinatorial interface is exposed.

    """

    def __init__(self, data_in, baseline_in, stb_i, integral_length=7):

        
        iiface_width = len(data_in) + (ceil(log2(integral_length)))
        assert iiface_width <= 32, f"Data width ({iiface_width}) must be <= 32"

        self.data_in = data_in
        self.baseline_in = baseline_in

        # Interface - rtlink
        self.rtlink = rtlink_iface = rtlink.Interface(
            rtlink.OInterface(data_width=0),
            rtlink.IInterface(data_width=iiface_width, timestamped=False))
            
        self.intg = intg = ClockDomainsRenamer({"sys": "dclk"})(
            Integral(
                data_width=len(data_in),
                length=integral_length
            )
        )
        
        # int_data_out = Signal(len(intg.data_out)+1)
        # self.comb += [
        #     int_data_out.eq(Cat(intg.stb_o, intg.data_out))
        # ]
        
        async_fifo = ClockDomainsRenamer({"write": "dclk", "read": "rio_phy"})(     
            AsyncFIFOBuffered(
                width=len(intg.data_out), 
                depth=16
            )
        )

        
        self.submodules += [intg, async_fifo]

        
        self.comb += [
            intg.data_in.eq(data_in),
            intg.baseline_in.eq(baseline_in),
            intg.stb_i.eq(stb_i),
            async_fifo.din.eq(intg.data_out),
            async_fifo.re.eq(async_fifo.readable),
            async_fifo.we.eq(intg.stb_o),
            rtlink_iface.i.data.eq(async_fifo.dout),
            rtlink_iface.i.stb.eq(async_fifo.readable)  # stb if there is data and frame
        ]

        
class SimulationWrapper(Module):

    def __init__(self):


        data_width = 22

        data_in = Signal(bits_sign=data_width, name="data_in")
        baseline_in = Signal(bits_sign=data_width, name="baseline_in")
        stb_i  = Signal(name="data_stb_i")



        # self.data_clk = Signal(name="dclk_clk")

        self.clock_domains.cd_rio_phy = cd_rio_phy = ClockDomain()
        self.clock_domains.cd_dclk = cd_dclk = ClockDomain()

        
        # trigger_rio_phy = Signal(name="trigger")
        # trigger_id = Signal(trigger_id_width)

        # self.comb += [cd_dclk.clk.eq(self.data_clk)]

        self.io = []

        self.io += [

            cd_rio_phy.clk,
            cd_rio_phy.rst,
            cd_dclk.clk,
            cd_dclk.rst,

        ]

        self.submodules.dut = dut = ClockDomainsRenamer("dclk")(IntegralRT(
            data_in=data_in, 
            baseline_in=baseline_in, 
            stb_i=stb_i,
            integral_length=8
        ))
        
        # dut.rtlink.o.stb.name_override = "rtlink_stb_i"
        # dut.rtlink.o.address.name_override = "rtlink_adr_i"
        # dut.rtlink.o.data.name_override = "rtlink_data_i"

        dut.rtlink.i.stb.name_override = "rtlink_stb_o"
        dut.rtlink.i.data.name_override = "rtlink_data_o"

        # dut.trigger_dclk.name_override = "trigger_dclk"

        self.io+= [
            # cd_dclk.clk,
            # cd_dclk.rst,

            data_in,
            baseline_in,
            stb_i,
            # trigger_rio_phy,
            # trigger_id,

            # cd_rio_phy.clk,
            # cd_rio_phy.rst,

            # dut.rtlink.o.stb,
            # dut.rtlink.o.address,
            # dut.rtlink.o.data,

            dut.rtlink.i.stb,
            dut.rtlink.i.data,

            # dut.trigger_dclk
        ]
    
if __name__ == "__main__":

    from migen.build.xilinx import common
    from elhep_cores.simulation.common import update_tb

    module = SimulationWrapper()
    so = dict(common.xilinx_special_overrides)
    so.update(common.xilinx_s7_special_overrides)

    verilog.convert(fi=module,
                    name="top",
                    special_overrides=so,
                    ios={*module.io},
                    create_clock_domains=False).write('dut.v')
    update_tb('dut.v')