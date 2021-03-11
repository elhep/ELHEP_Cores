from migen import *
from migen.build.generic_platform import *
from migen.genlib.io import DifferentialInput
from migen.genlib.cdc import PulseSynchronizer, MultiReg
from migen.genlib.resetsync import AsyncResetSynchronizer

from gateware.cores.xilinx import XilinxIdelayE2
from gateware.cores.rtlink_csr import RtLinkCSR

from artiq.gateware import rtio


class ADS5296A_XS7(Module):

    def __init__(self, adclk_i, lclk_i, dat_i):
        """ADS5296A ADC phy for Xilinx Series 7

        Args:
            adclk_i (differential signal): frame clock
            lclk_i (differential signal): bit clock
            dat_i (array of differential signals): data lines
        """


        # Module constants
        # ==========================================

        DAT_O_LEN = 10
        BUFR_DIVIDE = 5
        VALID_FRAME_OUT = 0b1111100000

        # Outputs
        # ==========================================

        self.data_clk_o = Signal()
        self.bitslip_done = Signal()
        self.data_o = [Signal(DAT_O_LEN, name="data_{}_o".format(i)) for i in range(9)]

        # RTLink Control Status Registers
        # ==========================================

        regs = [
            *[("data{}_delay_value".format(x), 5) for x in range(9)],
            ("adclk_delay_value", 5),
            ("phy_reset", 1, 1),
            ("bitslip_done", 1, 0, "ro")
        ]

        csr = RtLinkCSR(regs, "ads5296a_phy")
        self.submodules.csr = csr
        self.rtio_channels = [rtio.Channel.from_phy(self.csr)]

        # Design
        # ==========================================

        input_lines = [*dat_i, adclk_i]
        lines_delayed = [Signal(name="line_delayed_{}".format(i)) for i in range(9)]
        # 0 - data[0]
        # 1 - data[1]
        # ...
        # 7 - data[7]
        # 8 - adclk
        for idx, (input_line, line_delayed) in enumerate(zip(input_lines, lines_delayed)):
            line_buffer = Signal()
            self.specials += DifferentialInput(i_p=input_line.p,
                                               i_n=input_line.n,
                                               o=line_buffer)
            self.submodules += XilinxIdelayE2(
                data_i=line_buffer,
                data_o=line_delayed,
                delay_value_i=getattr(csr, regs[idx][0]),
                delay_value_ld_i=getattr(csr, regs[idx][0]+"_ld")
            )

        # Clocking
        lclk_ibuf = Signal()
        lclk_bufg = Signal()
        self.lclk = lclk_bufg
        self.lclk_bufio = lclk_bufio = Signal()

        self.clock_domains.cd_adclk_clkdiv = cd_adclk_clkdiv = ClockDomain()
        self.specials += [AsyncResetSynchronizer(cd_adclk_clkdiv, csr.phy_reset)]

        self.specials += DifferentialInput(i_p=lclk_i.p,
                                           i_n=lclk_i.n,
                                           o=lclk_ibuf)
        self.specials += Instance("BUFIO",
                                  i_I=lclk_ibuf,
                                  o_O=lclk_bufio)
        self.specials += Instance("BUFR",
                                  p_BUFR_DIVIDE=str(BUFR_DIVIDE),
                                  i_I=lclk_ibuf,
                                  i_CE=1,
                                  i_CLR=0,
                                  o_O=lclk_bufg)
        self.specials += Instance("BUFG",
                                  i_I=lclk_bufg,
                                  o_O=cd_adclk_clkdiv.clk)

        # Bitslip logic
        bitslip = Signal()
        bitslip_cnt = Signal(4)

        self.sync.adclk_clkdiv += [
            bitslip.eq(0),
            bitslip_cnt.eq(bitslip_cnt + 1),
            self.bitslip_done.eq(self.data_o[8] == VALID_FRAME_OUT),
            If(bitslip_cnt == 0x0,
               If(~self.bitslip_done,
                  bitslip.eq(1))),
        ]

        self.specials += MultiReg(i=self.bitslip_done, o=csr.bitslip_done, odomain="rio_phy")

        # ISERDES
        # For 10b deserialization we'll be using two ISERDES modules connected in MASTER-SLAVE mode.

        self.specials += Instance("BUFG", i_I=cd_adclk_clkdiv.clk, o_O=self.data_clk_o)

        for idx, (line_delayed, dat_o) in enumerate(zip(lines_delayed, self.data_o)):
            shift1 = Signal(name="shift1_{}".format(idx))
            shift2 = Signal(name="shift2_{}".format(idx))
            self.specials += Instance("ISERDESE2",
                                      p_DATA_RATE="DDR",
                                      p_DATA_WIDTH=10,
                                      p_INTERFACE_TYPE="NETWORKING",
                                      p_NUM_CE=1,
                                      p_SERDES_MODE="MASTER",
                                      p_IOBDELAY="BOTH",
                                      o_Q1=dat_o[0], o_Q2=dat_o[1], o_Q3=dat_o[2], o_Q4=dat_o[3],
                                      o_Q5=dat_o[4], o_Q6=dat_o[5], o_Q7=dat_o[6], o_Q8=dat_o[7],
                                      o_SHIFTOUT1=shift1,
                                      o_SHIFTOUT2=shift2,
                                      o_O=Signal(name="output_test_master_{}".format(idx)),
                                      i_DDLY=line_delayed,
                                      i_CLK=lclk_bufio,
                                      i_CLKB=~lclk_bufio,
                                      i_CE1=1,
                                      i_RST=ResetSignal("adclk_clkdiv"),
                                      i_CLKDIV=lclk_bufg,
                                      i_CLKDIVP=0,
                                      i_BITSLIP=bitslip,
                                      i_DYNCLKDIVSEL=0,
                                      i_DYNCLKSEL=0)
            self.specials += Instance("ISERDESE2",
                                      p_DATA_RATE="DDR",
                                      p_DATA_WIDTH=10,
                                      p_INTERFACE_TYPE="NETWORKING",
                                      p_NUM_CE=1,
                                      p_SERDES_MODE="SLAVE",
                                      p_IOBDELAY="BOTH",
                                      o_Q3=dat_o[8], o_Q4=dat_o[9],
                                      i_SHIFTIN1=shift1,
                                      i_SHIFTIN2=shift2,
                                      i_CLK=lclk_bufio,
                                      i_CLKB=~lclk_bufio,
                                      i_CE1=1,
                                      i_RST=ResetSignal("adclk_clkdiv"),
                                      i_CLKDIV=lclk_bufg,
                                      i_CLKDIVP=0,
                                      i_BITSLIP=bitslip,
                                      i_DYNCLKDIVSEL=0,
                                      i_DYNCLKSEL=0)

        # Debugging definition
        # self.bitslip_done.attr.add(("mark_debug", "true"))
        # bitslip_cnt.attr.add(("mark_debug", "true"))
        # bitslip.attr.add(("mark_debug", "true"))
        # self.data_o[0].attr.add(("mark_debug", "true"))
        # csr.data0_delay_value.attr.add(("mark_debug", "true"))
        # self.data_o[8].attr.add(("mark_debug", "true"))
        # csr.adclk_delay_value.attr.add(("mark_debug", "true"))


class SimulationWrapper(Module):

    def __init__(self):

        def add_diff_signal(name):
            setattr(self, name, Signal(name=name))
            sig = getattr(self, name)
            setattr(sig, "p", Signal(name=name+"_p"))
            setattr(sig, "n", Signal(name=name+"_n"))
            return [getattr(sig, "p"), getattr(sig, "n")]

        self.io = []
        self.io += add_diff_signal("adclk_i")
        self.io += add_diff_signal("lclk_i")
        dat_i = []
        for i in range(8):
            self.io += add_diff_signal("dat_{}_i".format(i))
            dat_i.append(getattr(self, "dat_{}_i".format(i)))

        self.clock_domains.cd_rio_phy = cd_rio_phy = ClockDomain()
        self.clock_domains.cd_sys = cd_sys = ClockDomain()

        self.io += [
            cd_rio_phy.clk,
            cd_rio_phy.rst,
            cd_sys.rst
        ]

        self.submodules.dut = dut = ADS5296A_XS7(self.adclk_i, self.lclk_i, dat_i)

        self.io.append(dut.data_clk_o)
        for i in range(8):
            self.io.append(dut.data_o[i])
        self.io.append(dut.bitslip_done)

        dut.rtio_channels[0].interface.o.stb.name_override = "rtlink_stb_i"
        dut.rtio_channels[0].interface.o.data.name_override = "rtlink_data_i"
        dut.rtio_channels[0].interface.o.address.name_override = "rtlink_address_i"

        dut.rtio_channels[0].interface.i.stb.name_override = "rtlink_stb_o"
        dut.rtio_channels[0].interface.i.data.name_override = "rtlink_data_o"

        self.io += [
            dut.rtio_channels[0].interface.o.stb,
            dut.rtio_channels[0].interface.o.data,
            dut.rtio_channels[0].interface.o.address,
            dut.rtio_channels[0].interface.i.stb,
            dut.rtio_channels[0].interface.i.data
        ]

        self.io = {*self.io}


if __name__ == "__main__":

    from migen.build.xilinx import common
    from gateware.simulation.common import update_tb

    module = SimulationWrapper()
    so = dict(common.xilinx_special_overrides)
    so.update(common.xilinx_s7_special_overrides)

    verilog.convert(fi=module,
                    name="top",
                    special_overrides=so,
                    ios=module.io,
                    create_clock_domains=False).write('ADS5296A_XS7.v')
    # update_tb('gateware/cores/tests/adc_phy_daq/adc_phy_daq.v')









