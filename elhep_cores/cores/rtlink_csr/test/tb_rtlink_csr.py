import cocotb

from cocotb.triggers import Timer, RisingEdge, FallingEdge, Combine, Edge, Event
from cocotb.clock import Clock
from cocotb.result import TestSuccess, TestError
from random import randint
import random
import time
from itertools import product


class TbBaseline:
    def __init__(self, dut):
        self.dut = dut

        cocotb.fork(Clock(self.dut.sys_clk, 10000).start())

    @cocotb.coroutine
    def reset(self):
        # self.dut.i <= 0
        self.dut.sys_rst <= 0

        self.dut._log.info("Waiting initial 120 ns")
        yield Timer(120, 'ns')
        self.dut._log.info("Starting reset... ")
        self.dut.sys_rst <= 1
        yield Timer(120, 'ns')
        self.dut.sys_rst <= 0
        self.dut._log.info("Reset finished")


    @cocotb.coroutine
    def simple_run(self):
        yield self.reset()
        yield Timer(100, 'ns')

        
@cocotb.test()
def test(dut):
    tb = TbBaseline(dut)
    yield tb.simple_run()