import cocotb

from cocotb.triggers import Timer, RisingEdge, FallingEdge, Combine, Edge, Event
from cocotb.clock import Clock
from cocotb.result import TestSuccess, TestError
from random import randint
import random
import time
from itertools import product




def generate_signal(freq, fs, resolution=16, n_periods=100):
    n_samples = int(fs/freq*n_periods)
    t_stop = 1/fs*n_samples
    print(n_samples)
    T = np.linspace(0, t_stop, n_samples)
    S = 0.5*(np.sin(T)+1)*(2**resolution-1)
    return S


def run_for_signal(dut, sig):
    output = []
    for s in sig:
        yield dut.i.eq(int(s))
        output.append(dut.o)
        yield
        print(int(s), dut.o)


def testbench(dut, fs, cutoff):
    S1 = generate_signal(0.5 * cutoff, fs)
    S2 = generate_signal(2.0 * cutoff, fs)

    yield from run_for_signal(dut, S1)
    

class TbBaseline:
    def __init__(self, dut):
        self.dut = dut

        cocotb.fork(Clock(self.dut.sys_clk, 10000).start())

    @cocotb.coroutine
    def reset(self):
        self.dut.i <= 0
        self.dut.sys_rst <= 0

        self.dut._log.info("Waiting initial 120 ns")
        yield Timer(120, 'ns')
        self.dut._log.info("Starting reset... ")
        self.dut.sys_rst <= 1
        yield Timer(120, 'ns')
        self.dut.sys_rst <= 0
        self.dut._log.info("Reset finished")
        
    @cocotb.coroutine
    def random_data_generator(self, sep_min=1, sep_max=14):
        max_data_value = 2**(len(self.dut.i)-1)-1
        while True:
        #     wait_periods = randint(sep_min, sep_max)
        #     for _ in range(wait_periods):
        #         yield self.dut.sys_clk
            self.dut.i <= randint(0, max_data_value)
            yield Timer(100, 'ns')


    @cocotb.coroutine
    def simple_run(self):
        # if seed is None:
        #     seed = time.time()
        # self.dut._log.info(f"Seed: {seed}")
        
        seed = time.time()
        random.seed(seed)

        dgen = cocotb.fork(self.random_data_generator(sep_min=0, sep_max=0))
        # dmon = cocotb.fork(self.data_trigger_monitor())
        # collector = cocotb.fork(self.rtlink_collector("main", self.data_sink(self.collected_data)))
        
        yield self.reset()
        yield Timer(100, 'ns')
        
        # yield self.write_rtlink("main", 0, pretrigger)
        # yield self.write_rtlink("main", 1, posttrigger)
        
        yield Timer(1, 'ms')
        
        # for _ in range(20):
        #     yield self.generate_trigger()
        #     yield Timer(randint(500, 5000), 'ns')

        dgen.kill()
        # dmon.kill()
        # collector.kill()

        # self.verify_data(pretrigger, posttrigger)

@cocotb.test()
def test(dut):
    tb = TbBaseline(dut)
    yield tb.simple_run()