import cocotb

from cocotb.triggers import Timer, RisingEdge, FallingEdge, Combine, Edge, Event
from cocotb.clock import Clock
from cocotb.result import TestSuccess, TestError
from random import randint
import random
import time
from itertools import product


def int_to_bits(i, length):
    if i < 0:
        raise ValueError("Number mus be >= 0")
    return [int(x) for x in bin(i)[2:].zfill(length)]


class TbIntegralRT:

    def __init__(self, dut):
        self.dut = dut

        cocotb.fork(Clock(self.dut.rio_phy_clk, 8000).start())
        cocotb.fork(Clock(self.dut.dclk_clk, 10000).start())

        self.rtio_re = RisingEdge(self.dut.rio_phy_clk)
        self.rtio_fe = FallingEdge(self.dut.rio_phy_clk)
        self.dclk_re = RisingEdge(self.dut.dclk_clk)
        self.dclk_fe = FallingEdge(self.dut.dclk_clk)

        self.rtlink = {
            "main": {
                "clock": self.dut.rio_phy_clk,
                "input": {
                    "stb": dut.rtlink_stb_o,
                    "data": dut.rtlink_data_o},
                #  "output": {
                #      "stb": dut.rtlink_stb_i,
                #      "data": dut.rtlink_data_i,
                #      "addr": dut.rtlink_adr_i}
            }
        }

        self.collected_data = []  # From rlink
        self.monitor_data = []
        self.monitor_baseline = []
        # self.monitor_trigger = []

    # @cocotb.coroutine
    # def write_rtlink(self, channel, address, data):
    #     self.dut._log.info(f"Writing to rtlink {channel} address {address}")

    #     link_clock = self.rtlink[channel]["clock"]
    #     link_addr = self.rtlink[channel]["output"].get("addr", None)
    #     link_data = self.rtlink[channel]["output"]["data"]
    #     link_stb  = self.rtlink[channel]["output"]["stb"]

    #     yield FallingEdge(link_clock)

    #     if link_addr:
    #         link_addr <= address
    #     if link_data:
    #         link_data <= data

    #     link_stb <= 0x1
    #     yield FallingEdge(link_clock)
    #     link_stb <= 0x0
        
    @cocotb.coroutine
    def rtlink_collector(self, channel, callback):
        link_clock = self.rtlink[channel]["clock"]

        link_data = self.rtlink[channel]["input"]["data"]
        link_stb = self.rtlink[channel]["input"]["stb"]

        while True:
            yield RisingEdge(link_clock)
            if link_stb == 1:
                callback(link_data.value.binstr)

    def data_sink(self, target):
        def data_sink_wrapped(data):
            target.append(int(data, 2))
        return data_sink_wrapped

    @cocotb.coroutine
    def reset(self):
        self.dut.data_in <= 0
        self.dut.baseline_in <= 0
        self.dut.data_stb_i <= 0
        self.dut.dclk_rst <= 0
        self.dut.rio_phy_rst <= 0

        self.dut._log.info("Waiting initial 120 ns")
        yield Timer(120, 'ns')
        self.dut._log.info("Starting reset... ")
        self.dut.dclk_rst <= 1
        self.dut.rio_phy_rst <= 1
        yield Combine(self.dclk_re, self.rtio_re)
        yield Combine(self.dclk_re, self.rtio_re)
        yield Combine(self.dclk_re, self.rtio_re)
        yield Combine(self.dclk_re, self.rtio_re)
        self.dut.dclk_rst <= 0
        self.dut.rio_phy_rst <= 0
        self.dut._log.info("Reset finished")

    @cocotb.coroutine
    def data_trigger_monitor(self):
        dclk_num = 0
        # trig_id = 0
        # trigger_dclk_r = 0
        while True:
            yield self.dclk_re
            if self.dut.data_stb_i == 1:
                self.monitor_data.append((dclk_num, int(self.dut.data_in.value.binstr, 2)))
                self.monitor_baseline.append((dclk_num, int(self.dut.baseline_in.value.binstr, 2)))
            # if self.dut.trigger == 1 and trigger_dclk_r == 0:
                # self.monitor_trigger.append((dclk_num, int(self.dut.trigger_id)))
                dclk_num += 1
            # trigger_dclk_r = int(self.dut.trigger)

    @cocotb.coroutine
    def random_data_generator(self, sep_min=1, sep_max=14):
        max_data_value = 2**len(self.dut.data_in)-1
        yield self.dclk_fe
        while True:
            wait_periods = randint(sep_min, sep_max)
            for _ in range(wait_periods):
                yield self.dclk_fe
            self.dut.data_in <= randint(0, max_data_value)
            self.dut.baseline_in <= 1000
            self.dut.data_stb_i <= 1
            yield self.dclk_fe
            self.dut.data_stb_i <= 0

    # @cocotb.coroutine
    # def data_generator(self):
    #     val = 0
    #     while True:
    #         yield self.dclk_fe
    #         self.dut.data_i <= val
    #         self.dut.data_stb_i <= 0
    #         if val % 10 == 0:
    #             self.dut.data_stb_i <= 1
    #         val = val+1 #if val < 4096 else 0

    # @cocotb.coroutine
    # def generate_trigger(self):
    #     yield self.dclk_fe
    #     self.dut.trigger <= 1
    #     yield self.dclk_fe
    #     self.dut.trigger <= 0

    def verify_data(self):
        input_data = []

        number_of_data_sets = (len(self.monitor_data) - (len(self.monitor_data) % 8))/8

        # self.dut._log.info(self.monitor_data)
        # self.dut._log.info(self.monitor_baseline)

        # self.dut._log.info(number_of_data_sets)

        value = 0
        j = 1

        for i in range(len(self.monitor_data)):
            value += self.monitor_data[i][1] - self.monitor_baseline[i][1]
            # self.dut._log.info(i)
            # self.dut._log.info(value)
            if (i == 8 * j - 1):

                input_data.append([int(i/8), value])
                value = 0
                j += 1

        # self.dut._log.info(input_data)
        # self.dut._log.info(self.collected_data)

        output_data = []

        for i in range(len(self.collected_data)):
            output_data.append([i, self.collected_data[i]])

        self.dut._log.debug(input_data)
        self.dut._log.debug(output_data)

        assert len(input_data) == len(output_data)
        for id, od in zip(input_data, output_data):
            self.dut._log.debug(id)
            self.dut._log.debug(od)
            assert id[0] == od[0]
            assert id[1] == od[1]

        self.dut._log.info("Data verified successfully")
            

    @cocotb.coroutine
    def simple_run(self, seed=None):
        if seed is None:
            seed = time.time()
        self.dut._log.info(f"Seed: {seed}")
        random.seed(seed)
        yield self.reset()
        yield Timer(200, 'ns')
        
        dgen = cocotb.fork(self.random_data_generator(sep_min=0, sep_max=0))
        dmon = cocotb.fork(self.data_trigger_monitor())
        collector = cocotb.fork(self.rtlink_collector("main", self.data_sink(self.collected_data)))
        

        for _ in range(100):
            yield Timer(10 * 8, 'ns')
            # yield Timer(randint(500, 5000), 'ns')

        yield Timer(5, 'ns')
        self.dut.data_stb_i <= 0
        dgen.kill()
        dmon.kill()
        
        yield Timer(100, 'ns')
        collector.kill()

        
        

        self.verify_data()


@cocotb.test()
def test(dut):
    tb = TbIntegralRT(dut)
    yield tb.simple_run(seed=1615387608.370478)
    # TODO: Add corner cases for pre/post trigger