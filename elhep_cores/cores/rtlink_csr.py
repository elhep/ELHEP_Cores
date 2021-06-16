import os

from migen import *
from artiq.gateware.rtio import rtlink
from artiq.gateware.rtio.channel import Channel
from elhep_cores.helpers.ddb_manager import HasDdbManager


class RtLinkCSR(Module, HasDdbManager):

    """
    regs:
        - (signal_name, length, [reset_value=0], [mode="rw"])
        - ...
    """

    def __init__(self, regs, name, identifier=None):
        self.name = name
        self.regs = regs

        data_width = max([x[1] for x in regs])

        self.rtlink = rtlink.Interface(
            rtlink.OInterface(data_width=data_width, address_width=len(regs).bit_length()+1),
            rtlink.IInterface(data_width=data_width, timestamped=False))

        write_enable = self.rtlink.o.address[0]
        address = self.rtlink.o.address[1:]

        data_signals_list = []
        for idx, r in enumerate(regs):
            if len(r) > 2:
                reset_value = r[2]
            else:
                reset_value = 0
            if len(r) > 3:
                mode = r[3]
            else:
                mode = "rw"
            signal = Signal(bits_sign=r[1], name=r[0], reset=reset_value)
            setattr(self, r[0], signal)
            data_signals_list.append(signal)

            if mode == "rw":
                ld_signal_name = r[0] + "_ld"
                setattr(self, ld_signal_name, Signal(bits_sign=1, name=ld_signal_name))
                ld_signal = getattr(self, ld_signal_name)
                self.sync.rio_phy += [
                    ld_signal.eq(0),
                    If(self.rtlink.o.stb & write_enable & (address == idx),
                    signal.eq(self.rtlink.o.data),
                    ld_signal.eq(1))
                ]

        data_signals = Array(data_signals_list)
        self.sync.rio_phy += [
            self.rtlink.i.stb.eq(0),
            If(self.rtlink.o.stb & ~write_enable,
               self.rtlink.i.stb.eq(1),
               self.rtlink.i.data.eq(data_signals[address]))
        ]

        if identifier is not None:
            self.add_rtio_channels(
                channel=Channel.from_phy(self),
                device_id=identifier,
                module="elhep_cores.coredevice.rtlink_csr",
                class_name="RtlinkCsr",
                arguments={
                    "regs": regs
                })
