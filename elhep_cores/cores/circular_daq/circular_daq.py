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

    def __init__(self, data_i, stb_i, trigger_rio_phy, 
        circular_buffer_length=128, channel_depth=128, trigger_cnt_len=4):

        data_width = len(data_i)
        assert data_width <= 32-trigger_cnt_len

        pretrigger_rio_phy = Signal(max=circular_buffer_length)
        posttrigger_rio_phy = Signal.like(pretrigger_rio_phy)
        pretrigger_dclk = Signal.like(pretrigger_rio_phy)
        posttrigger_dclk = Signal.like(posttrigger_rio_phy)
        self.trigger_dclk = trigger_dclk = Signal()

        # Interface - rtlink
        self.rtlink = rtlink_iface = rtlink.Interface(
            rtlink.OInterface(data_width=len(pretrigger_rio_phy), address_width=2),
            rtlink.IInterface(data_width=data_width+trigger_cnt_len, timestamped=True))
        self.rtlink_channels = [Channel(rtlink_iface, ififo_depth=channel_depth)]

        self.sync.rio_phy += [
            If(rtlink_iface.o.stb,
               If(self.rtlink.o.address == 0, pretrigger_rio_phy.eq(rtlink_iface.o.data)),
               If(self.rtlink.o.address == 1, posttrigger_rio_phy.eq(rtlink_iface.o.data)),
            )
        ]

        trigger_cnt = Signal(trigger_cnt_len, reset=0)
        trigger_d = Signal()

        self.sync.dclk += [
            If(trigger_dclk & ~trigger_d,  # detect trigger re
                trigger_cnt.eq(trigger_cnt+1)),
            trigger_d.eq(trigger_dclk)
        ]

        # Data format (MSb first):
        # <tdc_data, 22b>
        # <data valid, 1b>

        cb_data_in = Signal(data_width+1)
        self.comb += [
            cb_data_in.eq(Cat(stb_i, data_i))
        ]

        circular_buffer = ClockDomainsRenamer({"sys": "dclk"})(TriggeredCircularBuffer(len(cb_data_in), circular_buffer_length))
        async_fifo = ClockDomainsRenamer({"write": "dclk", "read": "rio_phy"})(AsyncFIFOBuffered(data_width+trigger_cnt_len+1, 16))
        trigger_cdc = PulseSynchronizer("rio_phy", "dclk")
        pretrigger_cdc = MultiReg(pretrigger_rio_phy, pretrigger_dclk, "dclk")
        posttrigger_cdc = MultiReg(posttrigger_rio_phy, posttrigger_dclk, "dclk")
        self.submodules += [circular_buffer, async_fifo, trigger_cdc]
        self.specials += [pretrigger_cdc, posttrigger_cdc]

        self.comb += [
            trigger_cdc.i.eq(trigger_rio_phy),
            trigger_dclk.eq(trigger_cdc.o),
            circular_buffer.data_in.eq(cb_data_in),
            circular_buffer.we.eq(1),
            circular_buffer.trigger.eq(trigger_dclk),
            circular_buffer.pretrigger.eq(pretrigger_dclk),
            circular_buffer.posttrigger.eq(posttrigger_dclk),
            async_fifo.din.eq(Cat(circular_buffer.data_out, trigger_cnt)),
            async_fifo.re.eq(async_fifo.readable),
            async_fifo.we.eq(circular_buffer.stb_out),
            rtlink_iface.i.data.eq(async_fifo.dout[1:]),  # two LSb are data valid (TDC frame)
            rtlink_iface.i.stb.eq(reduce(and_, [async_fifo.dout[0], async_fifo.readable]))  # stb if there are data and frame
        ]


class SimulationWrapper(Module):

    def __init__(self):

        data_width = 22

        data_i = Signal(bits_sign=data_width, name="data_i")
        stb_i  = Signal(name="data_stb_i")
        trigger_rio_phy = Signal(name="trigger")

        self.data_clk = Signal(name="dclk_clk")

        self.clock_domains.cd_rio_phy = cd_rio_phy = ClockDomain()
        self.clock_domains.cd_dclk = cd_dclk = ClockDomain()

        self.comb += [cd_dclk.clk.eq(self.data_clk)]

        self.submodules.dut = dut = CircularDAQ(
            data_i=data_i, 
            stb_i=stb_i,
            trigger_rio_phy=trigger_rio_phy,
            circular_buffer_length=128,
            channel_depth=128,
            trigger_cnt_len=4)

        dut.rtlink_channels[0].interface.o.stb.name_override = "rtlink_stb_i"
        dut.rtlink_channels[0].interface.o.address.name_override = "rtlink_adr_i"
        dut.rtlink_channels[0].interface.o.data.name_override = "rtlink_data_i"

        dut.rtlink_channels[0].interface.i.stb.name_override = "rtlink_stb_o"
        dut.rtlink_channels[0].interface.i.data.name_override = "rtlink_data_o"

        dut.trigger_dclk.name_override = "trigger_dclk"

        self.io = {
            cd_dclk.clk,
            cd_dclk.rst,

            data_i,
            stb_i,
            trigger_rio_phy,

            cd_rio_phy.clk,
            cd_rio_phy.rst,

            dut.rtlink_channels[0].interface.o.stb,
            dut.rtlink_channels[0].interface.o.address,
            dut.rtlink_channels[0].interface.o.data,

            dut.rtlink_channels[0].interface.i.stb,
            dut.rtlink_channels[0].interface.i.data,

            dut.trigger_dclk
        }


if __name__ == "__main__":

    from migen.build.xilinx import common
    from elhep_cores.simulation.common import update_tb

    module = SimulationWrapper()
    so = dict(common.xilinx_special_overrides)
    so.update(common.xilinx_s7_special_overrides)

    verilog.convert(fi=module,
                    name="top",
                    special_overrides=so,
                    ios=module.io,
                    create_clock_domains=False).write('dut.v')
    update_tb('dut.v')
