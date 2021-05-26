from artiq.language.core import kernel, delay, delay_mu, portable
from artiq.language.types import *
from artiq.language.units import ns
from artiq.coredevice.rtio import rtio_output, rtio_input_data
from artiq.language.types import TInt32
from elhep_cores.coredevice.rtlink_csr import RtlinkCsr
import json


class RtioBaselineTriggerGenerator:

    def __init__(self, dmgr, channel):
        self.identifier = f"{prefix}_baseline_tg"
        self.index = index

    @property
    def rising_edge(self):
        return self.identifier + "_re"

    @property
    def falling_edge(self):
        return self.identifier + "_fe"


class RtioTriggerGenerator:

    def __init__(self, dmgr, channel, core_device="core"):
        self.channel = channel

    @kernel
    def trigger(self):
        rtio_output(self.channel << 8, 0)


# TODO: Can we reamove this class?
class TriggerGenerator:
    
    kernel_invariants = ["layout"]

    def __init__(self, dmgr, phy_csr, channel, layout, core_device="core"):
        self.channel = channel
        self.core = dmgr.get(core_device)
        self.ref_period_mu = self.core.seconds_to_mu(
            self.core.coarse_ref_period)

        self.phy = dmgr.get(phy_csr)

    @kernel
    def set_trigger_value(self, address, data):
        self.write((self.channel << 8) | address << 1 | 1, data)

        
    @kernel
    def read_trigger_value(self, address):
        value = self.read((self.channel << 8) | address << 1 | 0, 0)
        return value


class RtioCoincidenceTriggerGenerator:

    kernel_invariants = {"mask_mapping", "channel"}

    def __init__(self, dmgr, mask_mapping, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.mask_mapping = {}
        self.max_mask_adr = 0
        for adr, mm in enumerate(mask_mapping):
            for idx, label in enumerate(mm):
                self.mask_mapping[label] = (adr, idx)
                self.max_mask_adr = max(self.max_mask_adr, adr)
        self.channel = channel

    @kernel
    def set_pulse_length(self, pulse_length):
        self.core.break_realtime()
        rtio_output(self.channel << 8 | 1 << 1 | 1, pulse_length)
        delay_mu(8)

    @kernel
    def set_enabled(self, enabled):
        self.core.break_realtime()
        rtio_output(self.channel << 8 | 0 << 1 | 1, enabled)
        delay_mu(8)

    @kernel
    def disable_all_sources(self):
        self.core.break_realtime()
        for adr in range(self.max_mask_adr+1):
            rtio_output(self.channel << 8 | (adr+2) << 1 | 1, 0)
            delay_mu(8)

    @kernel
    def enable_source(self, adr, idx):
        self.core.break_realtime()
        rtio_output(self.channel << 8 | (adr+2) << 1 | 0, 0)
        delay_mu(8)
        value = rtio_input_data(self.channel)
        delay_mu(10000)
        value |= (1 << idx)
        rtio_output(self.channel << 8 | (adr+2) << 1 | 1, value)
        delay_mu(8)       
