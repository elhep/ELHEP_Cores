import cocotb
from cocotb.result import ReturnValue
from cocotb.triggers import RisingEdge, FallingEdge
import csv


class RtLinkIface:

    def __init__(self, rio_phy_clock, stb_i, data_i, address_i=None, stb_o=None, data_o=None):
        self.rio_phy_clk = rio_phy_clock

        self.stb_i = stb_i
        self.data_i = data_i
        self.address_i = address_i

        self.stb_o = stb_o
        self.data_o = data_o

        self.clear_interface()

    def clear_interface(self):
        self.stb_i <= 0
        self.data_i <= 0
        if self.address_i:
            self.address_i <= 0

    @cocotb.coroutine
    def write(self, data, address=None):
        yield FallingEdge(self.rio_phy_clk)
        self.stb_i <= 1
        if self.address_i:
            if address is None:
                raise ValueError("Address required for RtLink")
            self.address_i <= address
        self.data_i <= data
        yield FallingEdge(self.rio_phy_clk)
        self.clear_interface()

    @cocotb.coroutine
    def read(self, timeout=None):
        while True:
            yield RisingEdge(self.rio_phy_clk)
            if self.stb_o == 1:
                return self.data_o
            if timeout is None:
                continue
            timeout -= 1
            if timeout < 0:
                raise RuntimeError("RtLink readout timedout")


class RtLinkCSR:

    class Reg:
        def __init__(self, rtlink, address, length):
            self.address = address
            self.length = length
            self.rtlink = rtlink  # type: RtLinkIface

        @cocotb.coroutine
        def write(self, value):
            yield self.rtlink.write(value, self.address << 1 | 1)

        @cocotb.coroutine
        def read(self):
            yield self.rtlink.write(0, self.address << 1 | 0)
            return (yield self.rtlink.read())

    def __init__(self, definition_file_path, rio_phy_clock, stb_i, data_i, address_i, stb_o, data_o):
        with open(definition_file_path, 'r') as f:
            regs = list(csv.reader(f, delimiter=','))[1:]

        rtlink = RtLinkIface(rio_phy_clock, stb_i, data_i, address_i, stb_o, data_o)

        for r in regs:
            name = r[1].strip()
            addr = int(r[0])
            length = int(r[2])
            # print("RtLinkCSR {:03x} {}({})".format(addr, name, length))
            setattr(self, name, RtLinkCSR.Reg(rtlink, addr, length))
