from migen.build.xilinx.platform import XilinxPlatform
from migen.build.generic_platform import *

from migen import *
from migen.genlib.cdc import BusSynchronizer, PulseSynchronizer, ElasticBuffer, MultiReg
from migen.genlib.fifo import AsyncFIFO, AsyncFIFOBuffered
from migen.fhdl import verilog
from artiq.gateware.rtio import rtlink, Channel

from functools import reduce
from operator import and_

from elhep_cores.cores.circular_daq.triggered_circular_buffer import TriggeredCircularBuffer


class CircularDAQ(Module):

    """
    RT Link wrapper for TriggeredCircularBuffer

    This module provides RTIO channels and  is to be used with rtlink.Channel.from_phy.
    No combinatorial interface is exposed.

    RTIO channel map:
     * 0: pretrigger
     * 1: posttrigger

    No readout is implemented. 
    """

    def __init__(self, data_i, stb_i, trigger_dclk, trigger_id_dclk=None, 
            circular_buffer_length=128):

        iiface_width = len(data_i) + len(trigger_id_dclk)
        assert iiface_width <= 32, f"Data width summarized with trigger " \
            "ID width ({iiface_width}) must be <= 32"

        self.data_i = data_i        
        pretrigger_rio_phy = Signal(max=circular_buffer_length)
        posttrigger_rio_phy = Signal.like(pretrigger_rio_phy)
        pretrigger_dclk = Signal.like(pretrigger_rio_phy)
        posttrigger_dclk = Signal.like(posttrigger_rio_phy)
        
        # Interface - rtlink
        self.rtlink = rtlink_iface = rtlink.Interface(
            rtlink.OInterface(data_width=len(pretrigger_rio_phy), address_width=1),
            rtlink.IInterface(data_width=iiface_width, timestamped=False))

        self.sync.rio_phy += [
            If(rtlink_iface.o.stb,
               If(self.rtlink.o.address == 0, pretrigger_rio_phy.eq(rtlink_iface.o.data)),
               If(self.rtlink.o.address == 1, posttrigger_rio_phy.eq(rtlink_iface.o.data)),
            )
        ]

        # We're embedding stb into data stream going into the cyclic buffer
        cb_data_in = Signal(len(data_i)+1)
        self.comb += [
            cb_data_in.eq(Cat(stb_i, data_i))
        ]

        self.cbuf = circular_buffer = ClockDomainsRenamer({"sys": "dclk"})(
            TriggeredCircularBuffer(
                data_width=len(cb_data_in),
                trigger_id_width=len(trigger_id_dclk),
                length=circular_buffer_length
            )
        )
        async_fifo = ClockDomainsRenamer({"write": "dclk", "read": "rio_phy"})(     
            AsyncFIFOBuffered(
                width=len(circular_buffer.data_out), 
                depth=16
            )
        )
        trigger_cdc = PulseSynchronizer("rio_phy", "dclk")
        pretrigger_cdc = MultiReg(pretrigger_rio_phy, pretrigger_dclk, "dclk")
        posttrigger_cdc = MultiReg(posttrigger_rio_phy, posttrigger_dclk, "dclk")
        self.submodules += [circular_buffer, async_fifo, trigger_cdc]
        self.specials += [pretrigger_cdc, posttrigger_cdc]

        self.comb += [
            circular_buffer.data_in.eq(cb_data_in),
            circular_buffer.we.eq(1),
            circular_buffer.trigger.eq(trigger_dclk),
            circular_buffer.trigger_id.eq(trigger_id_dclk),
            circular_buffer.pretrigger.eq(pretrigger_dclk),
            circular_buffer.posttrigger.eq(posttrigger_dclk),
            async_fifo.din.eq(circular_buffer.data_out),
            async_fifo.re.eq(async_fifo.readable),
            async_fifo.we.eq(circular_buffer.stb_out),
            rtlink_iface.i.data.eq(async_fifo.dout[1:]),
            rtlink_iface.i.stb.eq(async_fifo.dout[0] & async_fifo.readable)  # stb if there is data and frame
        ]


class SimulationWrapper(Module):

    # TODO: Update simulation

    def __init__(self):

        data_width = 22
        trigger_id_width = 1

        data_i = Signal(bits_sign=data_width, name="data_i")
        stb_i  = Signal(name="data_stb_i")


        trigger_rio_phy = Signal(name="trigger")
        trigger_id = Signal(trigger_id_width)

        # self.data_clk = Signal(name="dclk_clk")

        self.clock_domains.cd_rio_phy = cd_rio_phy = ClockDomain()
        self.clock_domains.cd_dclk = cd_dclk = ClockDomain()

        # self.comb += [cd_dclk.clk.eq(self.data_clk)]

        self.io = []

        self.io += [

            cd_rio_phy.clk,
            cd_rio_phy.rst,
            cd_dclk.clk,
            cd_dclk.rst,

        ]

        self.submodules.dut = dut = ClockDomainsRenamer("dclk")(CircularDAQ(
            data_i=data_i, 
            stb_i=stb_i,
            trigger_dclk=trigger_rio_phy,
            trigger_id_dclk = trigger_id,
            circular_buffer_length=256,
            # channel_depth=128,
            # trigger_cnt_len=4
        ))
        
        dut.rtlink.o.stb.name_override = "rtlink_stb_i"
        dut.rtlink.o.address.name_override = "rtlink_adr_i"
        dut.rtlink.o.data.name_override = "rtlink_data_i"

        dut.rtlink.i.stb.name_override = "rtlink_stb_o"
        dut.rtlink.i.data.name_override = "rtlink_data_o"

        # dut.trigger_dclk.name_override = "trigger_dclk"

        self.io+= [
            # cd_dclk.clk,
            # cd_dclk.rst,

            data_i,
            stb_i,
            trigger_rio_phy,
            trigger_id,

            # cd_rio_phy.clk,
            # cd_rio_phy.rst,

            dut.rtlink.o.stb,
            dut.rtlink.o.address,
            dut.rtlink.o.data,

            dut.rtlink.i.stb,
            dut.rtlink.i.data,

            # dut.trigger_dclk
        ]

        
        # self.io.append(dut.rtlink.o)
        # for i in range(8):
        #     self.io.append(dut.data_o[i])
        # self.io.append(dut.bitslip_done)

        
        # self.io = {*self.io}


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
