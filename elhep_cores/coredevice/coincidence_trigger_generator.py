from artiq.language.core import kernel, delay_mu
from artiq.coredevice.rtio import rtio_output, rtio_input_data


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
        print(adr, idx)
        self.core.break_realtime()
        rtio_output(self.channel << 8 | (adr+2) << 1 | 0, 0)
        delay_mu(8)
        value = rtio_input_data(self.channel)
        print("old", value)
        delay_mu(10000)
        value |= (1 << idx)
        print("new", value)
        self.core.break_realtime()
        rtio_output(self.channel << 8 | (adr+2) << 1 | 1, value)
        delay_mu(8)       