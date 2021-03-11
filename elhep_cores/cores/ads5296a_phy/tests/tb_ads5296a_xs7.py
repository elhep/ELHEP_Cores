import random
import cocotb

from cocotb.triggers import Timer, RisingEdge, FallingEdge, Combine, Join, First
from cocotb.clock import Clock
from cocotb.result import TestFailure
from gateware.simulation.cocotb_rtlink import RtLinkCSR
from itertools import product
from random import randint

from collections import namedtuple


def int_to_bits(i, length):
    if i < 0:
        raise ValueError("Number mus be >= 0")
    return [int(x) for x in bin(i)[2:].zfill(length)]


class DiffLine:

    def __init__(self, p, n):
        self.p = p
        self.n = n

    def set(self, v):
        self.p <=  (v & 0x1)
        self.n <= ~(v & 0x1)


class Ads5296AMock:

    def __init__(self, adclk_o, lclk_o, out_o, mode="RAMP"):
        self.adclk = adclk_o
        self.lclk = lclk_o
        self.out = out_o

        self.mode = mode
        self.generator_function = {
            "RAMP": self._ramp_generator
        }[mode]

        self.sample_period = 10.0 * 1e3
        
        self.tpdi = (4./5. * 10.0 + 11.8)*1e3 
        self.tsu = 0.2 * 1e3 
        self.th = 0.16 * 1e3 
        self.frame_line_delay = 0.12 * 1e3
        self.bit_clock_line_delay = 0.21 * 1e3
        self.data_line_delay = 0.17 * 1e3

        self.lclk_period = self.sample_period/10.0
        self.data_jitter = self.lclk_period/2.0 - self.tsu - self.th
        self.frame_high_t = self.sample_period/2.0
        self.data_val_t = self.tsu + self.th

    def initialize(self):
        self.adclk.set(0)
        self.lclk.set(0)
        for o in self.out:
            o.set(0)

    def _ramp_generator(self):
        for i in range(1024):
            yield i

    def _infinite_generator(self, function):
        g = function()
        while True:
            try:
                yield next(g)
            except StopIteration: 
                g = function()
                continue

    @cocotb.coroutine
    def frame_clock_driver(self):
        yield Timer(self.tpdi+self.frame_line_delay)
        while True:
            self.adclk.set(1)
            yield Timer(self.lclk_period/2.0*4+self.tsu+self.th)
            self.adclk.set(0)
            yield Timer(self.lclk_period/2.0*6-self.tsu-self.th)

    @cocotb.coroutine
    def bit_clock_driver(self):
        yield Timer(self.tpdi+self.tsu+self.bit_clock_line_delay)
        while True:
            self.lclk.set(1)
            yield Timer(self.lclk_period/2.0)
            self.lclk.set(0)
            yield Timer(self.lclk_period/2.0)

    @cocotb.coroutine
    def output_data_driver(self, channel):
        out = self.out[channel]
        data_generator = self._infinite_generator(self.generator_function)
        yield Timer(self.tpdi+self.data_line_delay)
        while True:
            value = next(data_generator)
            if channel == 0:
                print(value)
            for i in reversed(range(10)):
                out.p <=  ((value >> i) & 0x1)
                out.n <= ~((value >> i) & 0x1)
                yield Timer(self.tsu+self.th)
                out.p <= 0
                out.n <= 1
                yield Timer(self.lclk_period/2-self.th-self.tsu)

    def start(self):
        cocotb.fork(self.frame_clock_driver())
        cocotb.fork(self.bit_clock_driver())
        for channel in range(8):
            cocotb.fork(self.output_data_driver(channel))
        
    # def get_full_cycle_data(self):
        # return list(self.generator())





# noinspection PyStatementEffect
class TbAds5296APhy:

    def __init__(self, dut, rio_phy_freq_mhz=125.0):
        self.dut = dut
        self.adc = Ads5296AMock(
            adclk_o=DiffLine(dut.adclk_i_p, dut.adclk_i_n),
            lclk_o=DiffLine(dut.lclk_i_p, dut.lclk_i_n), 
            out_o=[
                DiffLine(getattr(dut, "dat_{}_i_p".format(i)), getattr(dut, "dat_{}_i_n".format(i))) for i in range(8)
            ])

        self.csr = RtLinkCSR(definition_file_path="../rtlinkcsr_ads5296a_phy.txt",
                      rio_phy_clock=self.dut.rio_phy_clk,
                      stb_i=getattr(self.dut, "rtlink_stb_i"),
                      data_i=getattr(self.dut, "rtlink_data_i"),
                      address_i=getattr(self.dut, "rtlink_address_i"),
                      stb_o=getattr(self.dut, "rtlink_stb_o"),
                      data_o=getattr(self.dut, "rtlink_data_o"))

        self.rio_period_ps = 1/rio_phy_freq_mhz*1e6

    @cocotb.coroutine
    def initialize(self):
        self.dut.sys_rst <= 1
        self.dut.rio_phy_rst <= 1

        cocotb.fork(Clock(self.dut.rio_phy_clk, self.rio_period_ps).start())

        self.adc.initialize()

        yield Timer(200)

        self.dut.sys_rst <= 0
        self.dut.rio_phy_rst <= 0


@cocotb.test()
def first_test(dut):
    tb = TbAds5296APhy(dut)
    yield tb.initialize()

    tb.adc.start()

    yield First(Timer(5000, 'ns'), RisingEdge(dut.bitslip_done))

    yield Timer(5000, 'ns')

    

    # regs = ["frame_length", "frame_delay_value", "data_delay_value"]
    # for r, ch in product(regs, range(4)):
    #     print(r, ch)
    #     v = randint(0, 31)
    #     reg = getattr(tb.channel_csr[ch], r)
    #     yield reg.write(v)
    #     readout = yield reg.read()
    #     readout = readout.value.integer
    #     if readout != v:
    #         raise TestFailure("CSR readout error at channel {}, expected 0x{:02x}, got 0x{:02x}".format(ch, v, readout))


# @cocotb.test()
# def data_test(dut):
#     tb = TbTdcGpx2Phy(dut, 100, 125)
#     yield tb.initialize()

#     lengths = [14, 20, 38, 44]*5
#     values = [randint(0, 2**l-1) for l in lengths]

#     monitors = [Join(cocotb.fork(tb.data_out_monitor(ch, values, lengths))) for ch in range(4)]
#     drivers = [Join(cocotb.fork(tb.frame_driver(ch, values, lengths))) for ch in range(4)]

#     yield Combine(*monitors, *drivers)
