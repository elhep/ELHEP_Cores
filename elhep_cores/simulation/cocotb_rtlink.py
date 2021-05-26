import cocotb
from cocotb.result import ReturnValue
from cocotb.triggers import RisingEdge, FallingEdge
import csv


class RtLinkIface:

    def __init__(self, rio_phy_clock, stb_o, data_o, address_o=None, 
            stb_i=None, data_i=None, debug=False):
        self.rio_phy_clk = rio_phy_clock
        self.stb_i = stb_i
        self.data_i = data_i
        self.address_o = address_o
        self.stb_o = stb_o
        self.data_o = data_o
        self.debug = debug

        self.clear_interface()

    @classmethod
    def get_iface_by_prefix(cls, dut, prefix, rio_phy_clk="rio_phy_clk", 
            debug=False):
        params = {
            "rio_phy_clock": getattr(dut, rio_phy_clk),
            "stb_i": getattr(dut, f"{prefix}_i_stb", None),
            "data_i": getattr(dut, f"{prefix}_i_data", None),
            "address_o": getattr(dut, f"{prefix}_o_address", None),
            "stb_o": getattr(dut, f"{prefix}_o_stb"),
            "data_o": getattr(dut, f"{prefix}_o_data")
        }
        return cls(**params, debug=debug)

    def clear_interface(self):
        self.stb_o <= 0
        self.data_o <= 0
        if self.address_o:
            self.address_o <= 0

    async def write(self, data, address=None):
        if self.debug: print(f"rtlink write {data:x} >> {address}")
        await FallingEdge(self.rio_phy_clk)
        self.stb_o <= 1
        if self.address_o:
            if address is None:
                raise ValueError("Address required for RtLink output")
            self.address_o <= address
        self.data_o <= data
        await FallingEdge(self.rio_phy_clk)
        self.clear_interface()

    async def read(self, timeout=None):
        while True:
            await RisingEdge(self.rio_phy_clk)
            if self.stb_i == 1:
                return self.data_i
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

    def __init__(self, definition_file_path, rio_phy_clock, stb_i, data_i, 
            address_i, stb_o, data_o):
        with open(definition_file_path, 'r') as f:
            regs = list(csv.reader(f, delimiter=','))[1:]

        rtlink = RtLinkIface(rio_phy_clock, stb_i, data_i, address_i, stb_o, 
            data_o)

        for r in regs:
            name = r[1].strip()
            addr = int(r[0])
            length = int(r[2])
            # print("RtLinkCSR {:03x} {}({})".format(addr, name, length))
            setattr(self, name, RtLinkCSR.Reg(rtlink, addr, length))
