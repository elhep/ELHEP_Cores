import random
from itertools import product
from random import randint
from collections import namedtuple

import cocotb
from cocotb.triggers import Timer, RisingEdge, FallingEdge, Combine, Join, First
from cocotb.clock import Clock
from cocotb.result import TestFailure

import numpy as np

import os
print(os.environ)
import sys
print(sys.path)

from elhep_cores.simulation.cocotb_rtlink import RtLinkIface


def int_to_bits(i, length):
    if i < 0:
        raise ValueError("Number mus be >= 0")
    return [int(x) for x in bin(i)[2:].zfill(length)]


class TriggerDriver:

    def __init__(self, trigger_lines, trigger_clocks, 
                 min_period=1, max_period=20, 
                 min_sep=1000, max_sep=2000,
                 periods=100):
        assert len(trigger_lines) == len(trigger_clocks)

        self.min_sep = min_sep
        self.max_sep = max_sep
        self.periods = periods

        for tclk in trigger_clocks:
            cocotb.fork(Clock(tclk, randint(min_period, max_period), 'ns').start())

        self.inactive_drivers = [self.drive_trigger(tl, tclk) for tl, tclk in zip(trigger_lines, trigger_clocks)]
    
    async def drive_trigger(self, trigger_line, trigger_clock):
        trigger_line <= 0
        for _ in range(self.periods):
            await Timer(randint(self.min_sep, self.max_sep), 'ns')
            await FallingEdge(trigger_clock)
            trigger_line <= 1
            await FallingEdge(trigger_clock)
            trigger_line <= 0

    def start(self):
        self.active_drivers = [cocotb.fork(driver) for driver in self.inactive_drivers]

    async def join(self):
        await Combine(*[Join(driver) for driver in self.active_drivers])


class TriggerDriverMonitor:

    def __init__(self, trigger_lines, pulse_lengths, pulse_offset=8, resolution=0.25):
        self.resolution = resolution
        self.values = [[] for _ in trigger_lines]
        self.trigger_lines = trigger_lines
        self.pulse_lengths = [int(pl * 8/resolution) for pl in pulse_lengths]
        self.pulse_offset = int(pulse_offset/resolution)

    async def monitor(self):
        while True:
            await Timer(self.resolution, 'ns')
            for line_idx, trigger_line in enumerate(self.trigger_lines):
                self.values[line_idx].append(bool(trigger_line.value))

    @staticmethod
    def get_pulses(values, pulse_length, pulse_offset=0):        
        prev = values[0]
        pulses = [False]*len(values)
        i = 1
        while True:
            try:
                if not prev and values[i]:
                    pulse_start = i + pulse_offset
                    pulse_end = pulse_start+pulse_length
                    for j in range(pulse_start, pulse_end):
                        pulses[j] = True
                    i += pulse_length
                prev = values[i]
                i += 1
            except IndexError:
                return pulses

    @classmethod
    def _do_count_coincidence(cls, *args, pulse_offset=0):
        line_pulses = [cls.get_pulses(*a, pulse_offset=pulse_offset) for a in args]
        coincidence_sum = [sum(x) for x in zip(*line_pulses)]
        counter = 0
        prev = coincidence_sum[0] > 1
        for idx in range(1, len(coincidence_sum)):
            if (coincidence_sum[idx] > 1) and not prev:
                counter += 1
            prev = coincidence_sum[idx] > 1
        return counter

    def count_coincidence(self, *channels):
        args = []
        for ch in channels:
            args.append([self.values[ch], self.pulse_lengths[ch]])
        return self._do_count_coincidence(*args, pulse_offset=self.pulse_offset)


class TriggerMonitor:

    def __init__(self, trigger_lines):
        self.counters = [0] * len(trigger_lines)
        self.trigger_lines = trigger_lines

    async def monitor_line(self, idx, line):
        while True:
            await RisingEdge(line)
            self.counters[idx] += 1

    def start_monitor(self):
        for idx, line in enumerate(self.trigger_lines):
            cocotb.fork(self.monitor_line(idx, line))

                
@cocotb.test()
async def coincidence_test(dut):
    GENERATORS = 34
    MONITORS = 35

    # random.seed(99)
    cocotb.fork(Clock(dut.rio_phy_clk, 8, 'ns').start())
    rtlink = RtLinkIface(dut.rio_phy_clk, dut.stb, dut.data, dut.address, dut.stb_1, dut.data_1)
    
    for i in range(0, MONITORS):
        if i < 31:
            data = (0b1 << (i+1)) | 1
            address = (2 + i*2) << 1 | 1
            await rtlink.write(data, address)
        else:
            address = (2 + i*2) << 1 | 1
            await rtlink.write(1, address)
            data = (0b1 << (i-31))
            address = (2 + i*2 + 1) << 1 | 1
            await rtlink.write(data, address)
    await rtlink.write(0xFFFFFFFF, 0x0 << 1 | 1)
    await rtlink.write(0xFFFFFFFF, 0x1 << 1 | 1)

    trigger_lines = [getattr(dut, f"trigger_driver_{i}") for i in range(GENERATORS)]
    trigger_clocks = [getattr(dut, f"trigger_cd_{i}_clk") for i, _ in enumerate(trigger_lines)]
    pulse_lengths = [33 for i, _ in enumerate(trigger_lines)]
    trigger_driver = TriggerDriver(trigger_lines, trigger_clocks, periods=10)
    trigger_driver_monitor = TriggerDriverMonitor(trigger_lines, pulse_lengths, pulse_offset=0)

    trigger_lines = [getattr(dut, f"trigger_monitor_{i}") for i in range(MONITORS)]
    trigger_monitor = TriggerMonitor(trigger_lines)
      
    cocotb.fork(trigger_driver_monitor.monitor())
    trigger_monitor.start_monitor()
    trigger_driver.start()
    await trigger_driver.join()
    await Timer(2, 'us')

    # TODO: Extend to validate all monitors
    # TODO: Make this test more reliable
    failed = False
    for i in range(32):
        expected = trigger_driver_monitor.count_coincidence(0, i+1)
        observed = trigger_monitor.counters[i]
        if expected != observed:
            dut.log.error(f"Coincidence 0 with {i+1} failed, expected: {expected}, observed {observed}")
            failed = True
    if failed:
        raise TestFailure()
