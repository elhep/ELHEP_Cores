from migen import *
from migen.build.generic_platform import *


def _fmc_pin(fmc: str, bank: str, i: int, pol: str):
    bank = bank.upper()
    pol = pol.upper()
    cc_pin_name_tmp = "fmc{fmc}:{bank}{i:02d}_CC_{pol}"
    pin_name_tmp = "fmc{fmc}:{bank}{i:02d}_{pol}"
    cc_pins = {
        "LA": [0, 1, 17, 18],
        "HA": [0, 1, 17],
        "HB": [0, 6, 17],
    }
    if i in cc_pins[bank]:
        return cc_pin_name_tmp.format(fmc=fmc, bank=bank, i=i, pol=pol)
    else:
        return pin_name_tmp.format(fmc=fmc, bank=bank, i=i, pol=pol)


class _FMC:
    @classmethod
    def add_extension(cls, target, fmc, iostd_single, iostd_diff):
        name = cls.__name__
        target.platform.add_extension(cls.io(fmc, iostd_single, iostd_diff))
        print("{} (FMC{}) starting at RTIO channel 0x{:06x}"
              .format(name, fmc, len(target.rtio_channels)))

    @classmethod
    def io(cls, fmc, iostd_single, iostd_diff):
        raise NotImplementedError

    @classmethod
    def signal_name(cls, signal_name, fmc):
        return "fmc{}_{}".format(fmc, signal_name)

    @classmethod
    def diff_signal(cls, signal_name, fmc, bank, i, iostd_diff, idx=0):
        return (cls.signal_name(signal_name, fmc), idx,
                Subsignal("p", Pins(_fmc_pin(fmc, bank, i, "p"))),
                Subsignal("n", Pins(_fmc_pin(fmc, bank, i, "n"))),
                *(iostd_diff[f"fmc{fmc}_{bank}"]))

    @classmethod
    def single_signal(cls, signal_name, fmc, bank, i, pol, iostd_single, idx=0):
        return (cls.signal_name(signal_name, fmc), idx, Pins(_fmc_pin(fmc, bank, i, pol)),
                *(iostd_single[f"fmc{fmc}_{bank}"]))




