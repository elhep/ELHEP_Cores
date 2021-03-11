from migen.build.xilinx.platform import XilinxPlatform
from migen.build.generic_platform import *
from migen.genlib.io import DifferentialInput
from gateware.cores.xilinx import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from artiq.gateware import rtio
from gateware.cores.rtlink_csr import RtLinkCSR


class TdcGpx2Phy(Module):

    def __init__(self, data_clk_i, frame_signals_i, data_signals_i):

        # Outputs
        # ==========================================

        self.data_clk_o = Signal(name="data_clk_o")
        self.data_o = []
        self.data_stb_o = []

        # Design
        # ==========================================

        data_clk_to_bufr = Signal()
        self.clock_domains.cd_dclk = cd_dclk = ClockDomain()  # !!!! Inverted!

        self.specials += DifferentialInput(data_clk_i.p, data_clk_i.n, data_clk_to_bufr)
        self.specials += Instance("BUFG", i_I=~data_clk_to_bufr, o_O=cd_dclk.clk)  # !!!! Inverted!
        # platform.add_period_constraint(cd_dclk.clk, 4.)

        self.specials += [AsyncResetSynchronizer(cd_dclk, ResetSignal("sys"))]

        self.rtio_channels = []
        for channel, (frame, data) in enumerate(zip(frame_signals_i, data_signals_i)):
            frame_se = Signal()
            data_se = Signal()
            self.specials += DifferentialInput(frame.p, frame.n, frame_se)
            self.specials += DifferentialInput(data.p, data.n, data_se)

            channel_phy = ClockDomainsRenamer("dclk")(TdcGpx2ChannelPhy(frame_i=frame_se, data_i=data_se))
            setattr(self.submodules, "channel{}".format(channel), channel_phy)
            self.data_o.append(channel_phy.data_o)
            self.data_stb_o.append(channel_phy.stb_o)
            self.rtio_channels.append(rtio.Channel.from_phy(channel_phy.csr))


class TdcGpx2ChannelPhy(Module):

    """
    Single TDC GPX2 channel

    This module runs in clock domain defined by TdcGpx2Phy module.
    """

    def __init__(self, frame_i, data_i, max_frame_length=44):

        # Outputs
        # ==========================================

        self.data_o = Signal(max_frame_length, name="data_o")
        self.stb_o = Signal(name="data_stb_o")

        # RTLink Control Status Registers
        # ==========================================

        regs = [
            ("frame_length", max_frame_length.bit_length(), 44),
            ("frame_delay_value", 5),
            ("data_delay_value", 5)
        ]

        csr = RtLinkCSR(regs, "tdc_gpx_channel_phy")
        self.submodules.csr = csr

        # Design
        # ==========================================

        frame = Signal(2)
        frame_in = Signal()
        self.submodules += ClockDomainsRenamer("rio_phy")(XilinxIdelayE2(
            data_i=frame_i,
            data_o=frame_in,
            delay_value_i=csr.frame_delay_value,
            delay_value_ld_i=csr.frame_delay_value_ld))

        self.sync += [frame.eq(frame << 1 | frame_in)]
        frame_start = Signal()
        self.comb += frame_start.eq(frame[0] & ~frame[1])

        data_delayed = Signal()
        self.submodules += ClockDomainsRenamer("rio_phy")(XilinxIdelayE2(
            data_i=data_i,
            data_o=data_delayed,
            delay_value_i=csr.data_delay_value,
            delay_value_ld_i=csr.data_delay_value_ld))

        data_q1 = Signal()
        data_q2 = Signal()
        data_q1q2 = Signal(2)
        self.submodules += XilinxDDRInputImplS7(i=data_delayed, o1=data_q2, o2=data_q1, clk=ClockSignal(),
                                                clk_edge="OPPOSITE_EDGE")
        self.comb += data_q1q2.eq(Cat(data_q1, data_q2))

        shift_register = Signal(max_frame_length+2)
        shift_register_reg = Signal(max_frame_length)
        shift_register_view = Signal(max_frame_length)
        stb_reg = Signal()
        bit_counter = Signal(max=max_frame_length)
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
                NextValue(bit_counter, csr.frame_length-2),
                NextValue(stb_reg, 0),
                If(frame_start,
                   NextState("FRAMEACQ")
                )
        )
        fsm.act("FRAMEACQ",
                NextValue(bit_counter, bit_counter-2),
                NextValue(stb_reg, 0),
                If(bit_counter == 0,
                   NextValue(shift_register_reg, shift_register[:-2]),
                   NextValue(stb_reg, 1),
                   If(frame_start,
                      NextValue(bit_counter, csr.frame_length-2)
                   ).Else(
                       NextState("IDLE"))
                )
        )

        self.sync += [
            shift_register.eq((shift_register << 2) | data_q1q2)
        ]

        self.comb += [
            self.data_o.eq(shift_register_reg),
            self.stb_o.eq(stb_reg),
            shift_register_view.eq(shift_register[1:-1])
        ]

        csr.frame_length.attr.add(("mark_debug", "true"))
        bit_counter.attr.add(("mark_debug", "true"))
        shift_register.attr.add(("mark_debug", "true"))
        frame_start.attr.add(("mark_debug", "true"))
        self.data_o.attr.add(("mark_debug", "true"))
        self.stb_o.attr.add(("mark_debug", "true"))


class SimulationWrapper(Module):

    def __init__(self):

        def add_diff_signal(name):
            setattr(self, name, Signal(name=name))
            sig = getattr(self, name)
            setattr(sig, "p", Signal(name=name+"_p"))
            setattr(sig, "n", Signal(name=name+"_n"))
            return [getattr(sig, "p"), getattr(sig, "n")]

        self.clock_domains.cd_rio_phy = cd_rio_phy = ClockDomain()
        self.clock_domains.cd_sys = cd_sys = ClockDomain()

        self.io = [
            cd_rio_phy.clk,
            cd_rio_phy.rst,
            cd_sys.rst
        ]
        self.io += add_diff_signal("dclk")
        for i in range(4):
            self.io += add_diff_signal("frame{}".format(i))
            self.io += add_diff_signal("data{}".format(i))

        self.submodules.dut = dut = TdcGpx2Phy(self.dclk, [getattr(self, "frame{}".format(i)) for i in range(4)],
                                         [getattr(self,  "data{}".format(i)) for i in range(4)])

        for idx, ch in enumerate(dut.rtio_channels):
            ch.interface.o.stb.name_override = "rtlink{}_stb_i".format(idx)
            ch.interface.o.data.name_override = "rtlink{}_data_i".format(idx)
            ch.interface.o.address.name_override = "rtlink{}_address_i".format(idx)

            ch.interface.i.stb.name_override = "rtlink{}_stb_o".format(idx)
            ch.interface.i.data.name_override = "rtlink{}_data_o".format(idx)

            self.io += [
                ch.interface.o.stb,
                ch.interface.o.data,
                ch.interface.o.address,
                ch.interface.i.stb,
                ch.interface.i.data,

                dut.data_clk_o,
                *[s for s in dut.data_stb_o],
                *[s for s in dut.data_o]
            ]


if __name__ == "__main__":

    # Generate simulation source for Cocotb
    from migen.build.xilinx import common
    from gateware.simulation.common import update_tb

    module = SimulationWrapper()
    so = dict(common.xilinx_special_overrides)
    so.update(common.xilinx_s7_special_overrides)

    verilog.convert(fi=module,
                    name="top",
                    special_overrides=so,
                    ios={*module.io},
                    create_clock_domains=False).write('tdc_gpx2.v')
    update_tb('tdc_gpx2.v')