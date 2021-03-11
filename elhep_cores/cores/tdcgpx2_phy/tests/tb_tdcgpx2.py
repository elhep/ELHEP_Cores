import random
import cocotb

from cocotb.triggers import Timer, RisingEdge, FallingEdge, Combine, Join
from cocotb.clock import Clock
from cocotb.result import TestFailure
from gateware.simulation.cocotb_rtlink import RtLinkCSR
from itertools import product
from random import randint


def int_to_bits(i, length):
    if i < 0:
        raise ValueError("Number mus be >= 0")
    return [int(x) for x in bin(i)[2:].zfill(length)]


# noinspection PyStatementEffect
class TbTdcGpx2Phy:

    def __init__(self, dut, dclk_freq_mhz, rio_phy_freq_mhz):
        self.dut = dut
        self.clk_period_ps = int(1.0 / dclk_freq_mhz * 1e6)
        self.rio_period_ps = int(1.0 / rio_phy_freq_mhz * 1e6)

        self.re = RisingEdge(dut.dclk_p)
        self.fe = FallingEdge(dut.dclk_p)

        self.channel_csr = [
            RtLinkCSR(definition_file_path="rtlinkcsr_tdc_gpx_channel_phy.txt",
                      rio_phy_clock=self.dut.rio_phy_clk,
                      stb_i=getattr(self.dut, "rtlink{}_stb_i".format(i)),
                      data_i=getattr(self.dut, "rtlink{}_data_i".format(i)),
                      address_i=getattr(self.dut, "rtlink{}_address_i".format(i)),
                      stb_o=getattr(self.dut, "rtlink{}_stb_o".format(i)),
                      data_o=getattr(self.dut, "rtlink{}_data_o".format(i)))
            for i in range(4)]

    def set_diff(self, signal, ch, v):
        p = getattr(self.dut, "{}{}_p".format(signal, ch))
        n = getattr(self.dut, "{}{}_n".format(signal, ch))
        p <= v
        n <= ~v

    def set_all_diff(self, signal, v):
        for i in range(4):
            self.set_diff(signal, i, v)

    @cocotb.coroutine
    def initialize(self):
        self.dut.sys_rst <= 1
        self.dut.rio_phy_rst <= 1

        self.set_all_diff("frame", 0)
        self.set_all_diff("data", 0)

        cocotb.fork(Clock(self.dut.dclk_p, self.clk_period_ps).start(start_high=True))
        cocotb.fork(Clock(self.dut.dclk_n, self.clk_period_ps).start(start_high=False))

        cocotb.fork(Clock(self.dut.rio_phy_clk, self.rio_period_ps).start())

        for _ in range(10):
            yield self.re
        self.dut.sys_rst <= 0
        for _ in range(100):
            yield self.re
        self.dut.rio_phy_rst <= 0

    @cocotb.coroutine
    def generate_frame_signal(self, ch, frame_offset):
        offset = self.clk_period_ps / 2.0 + frame_offset
        yield self.re
        yield Timer(offset)
        self.set_diff("frame", ch, 1)
        yield Timer(4 * self.clk_period_ps)
        self.set_diff("frame", ch, 0)

    @cocotb.coroutine
    def generate_data_signal(self, ch, bits, data_offset):
        offset = self.clk_period_ps/2.0+data_offset

        yield self.re
        yield Timer(offset)
        for b in bits:
            self.set_diff("data", ch, b)
            yield Timer(self.clk_period_ps/2.0)
        self.set_diff("data", ch, 0)

    @cocotb.coroutine
    def transfer_frame(self, ch, bits, frame_offset=0.0, data_offset=0.0):
        frame = cocotb.fork(self.generate_frame_signal(ch, frame_offset))
        data = cocotb.fork(self.generate_data_signal(ch, bits, data_offset))

        yield Combine(Join(frame), Join(data))

    @cocotb.coroutine
    def data_out_monitor(self, ch, values, lengths):
        stb_o = "data_stb_o" if ch == 0 else "data_stb_o_{}".format(ch)
        stb_o = getattr(self.dut, stb_o)

        data_o = "data_o" if ch == 0 else "data_o_{}".format(ch)
        data_o = getattr(self.dut, data_o)

        for l, v in zip(lengths, values):
            while True:
                yield self.fe
                if stb_o == 1:
                    ro = data_o.value.integer & (2**l-1)
                    if ro != v:
                        raise TestFailure("Invalid data received on channel {}, expected {:011x}, got: {:011x}, length: {}".format(ch, v, ro, l))
                    break

    @cocotb.coroutine
    def frame_driver(self, ch, values, lengths):
        for l, v in zip(lengths, values):
            yield self.channel_csr[ch].frame_length.write(l)
            yield self.transfer_frame(ch, int_to_bits(v, l), 0, 0)


@cocotb.test()
def csr_test(dut):
    tb = TbTdcGpx2Phy(dut, 100, 125)
    yield tb.initialize()

    regs = ["frame_length", "frame_delay_value", "data_delay_value"]
    for r, ch in product(regs, range(4)):
        print(r, ch)
        v = randint(0, 31)
        reg = getattr(tb.channel_csr[ch], r)
        yield reg.write(v)
        readout = yield reg.read()
        readout = readout.value.integer
        if readout != v:
            raise TestFailure("CSR readout error at channel {}, expected 0x{:02x}, got 0x{:02x}".format(ch, v, readout))


@cocotb.test()
def data_test(dut):
    tb = TbTdcGpx2Phy(dut, 100, 125)
    yield tb.initialize()

    lengths = [14, 20, 38, 44]*5
    values = [randint(0, 2**l-1) for l in lengths]

    monitors = [Join(cocotb.fork(tb.data_out_monitor(ch, values, lengths))) for ch in range(4)]
    drivers = [Join(cocotb.fork(tb.frame_driver(ch, values, lengths))) for ch in range(4)]

    yield Combine(*monitors, *drivers)
