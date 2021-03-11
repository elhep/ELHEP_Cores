import os

from migen import *
from artiq.gateware.rtio import rtlink


class RtLinkCSR(Module):

    """
    regs:
        - (signal_name, length, [reset_value=0], [mode="rw"])
        - ...
    """

    def __init__(self, regs, name, output_dir=None):
        self.output_dir = output_dir if output_dir is not None else "./"
        self.name = name

        data_width = max([x[1] for x in regs])

        self.rtlink = rtlink.Interface(
            rtlink.OInterface(data_width=data_width, address_width=len(regs).bit_length()+1),
            rtlink.IInterface(data_width=data_width, timestamped=False))

        write_enable = self.rtlink.o.address[0]
        address = self.rtlink.o.address[1:]

        data_signals_list = []
        txt_output = "Address, Name, Length\n"
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
            txt_output += "{}, {}, {}\n".format(idx, *(r[:2]))

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

        with open(os.path.join(self.output_dir, "rtlinkcsr_{}.txt".format(self.name)), 'w') as f:
            f.write(txt_output)
