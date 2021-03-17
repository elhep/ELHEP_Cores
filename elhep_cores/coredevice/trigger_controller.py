from artiq.language.core import kernel, delay, portable
from artiq.language.units import ns
from artiq.coredevice.rtio import rtio_output, rtio_input_data
from artiq.language.types import TInt32
import json


class TriggerController:
    
    kernel_invariants = ["layout"]

    def __init__(self, dmgr, channel, layout, core_device="core"):
        self.channel = channel
        self.core = dmgr.get(core_device)
        self.ref_period_mu = self.core.seconds_to_mu(
            self.core.coarse_ref_period)

        with open(layout, 'r') as f:
            self.layout = json.load(f)

    @kernel
    def write_rt(self, address, data):
        rtio_output((self.channel << 8) | address << 1 | 1, data)

    @kernel
    def read_rt(self, address) -> TInt32:
        rtio_output((self.channel << 8) | address << 1 | 0, 0)
        return rtio_input_data(self.channel)

    @kernel
    def enable_trigger(self, channel_id, trigger_id):
        channel_address = self.layout[channel_id]
        trigger_pointer = self.layout["channel_layout"][trigger_id]
        adr = channel_address+trigger_pointer["address_offset"]
        old_value = self.read_rt(adr)
        new_value = old_value | (1 << trigger_pointer['word_offset'])
        self.write_rt(adr, new_value)

    @kernel
    def disable_trigger(self, channel_id, trigger_id):
        channel_address = self.layout[channel_id]
        trigger_pointer = self.layout["channel_layout"][trigger_id]
        adr = channel_address+trigger_pointer["address_offset"]
        old_value = self.read_rt(adr)
        new_value = old_value & ~(1 << trigger_pointer['word_offset'])
        self.write_rt(adr, new_value)

    @kernel
    def sw_trigger(self, n):
        if n >= self.layout['sw_trigger_num']:
            raise ValueError("Invalid sw trigger number")
        self.write_rt(self.layout['sw_trigger_start']+n, 1)