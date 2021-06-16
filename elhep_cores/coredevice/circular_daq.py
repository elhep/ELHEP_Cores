from artiq.coredevice.rtio import rtio_output, rtio_input_timestamped_data, rtio_input_data
from artiq.language import TInt32, TInt64
from artiq.language.core import kernel, delay_mu, now_mu
from artiq.language.core import rpc
from artiq.language.units import us, ns, ms
from elhep_cores.coredevice.rtlink_csr import RtlinkCsr
from artiq.coredevice.ttl import TTLOut
from artiq.coredevice.exceptions import RTIOOverflow
from numpy import int64, int32


class CircularDaq:

    kernel_invariants = {"channel", "core", "ref_period_mu", "buffer_len"}

    def __init__(self, dmgr, channel, buffer_len=1024, core_device="core"):
        self.channel = channel
        self.core = dmgr.get(core_device)
        self.ref_period_mu = self.core.seconds_to_mu(
            self.core.coarse_ref_period)
        
        self.buffer_len = buffer_len
        self.data_buffer = [int32(0)]*(buffer_len)
        self.ts_buffer = [int64(0)]*(buffer_len)
        self.buffer_ptr = 0

    @kernel
    def configure_rt(self, pretrigger, posttrigger):
        rtio_output((self.channel << 8) | 0, pretrigger)
        delay_mu(self.ref_period_mu)
        rtio_output((self.channel << 8) | 1, posttrigger)
        delay_mu(self.ref_period_mu)

    @rpc(flags={"async"})
    def store(self, samples):
        raise NotImplementedError

    @kernel
    def transfer_samples(self, chunk=200):
        idx = 0
        while True:
            timestamp, sample = \
                rtio_input_timestamped_data(self.core.get_rtio_counter_mu(), self.channel)
            if timestamp < 0:
                break
            self.data_buffer[idx] = sample
            idx += 1
        if idx:
            self.store(self.data_buffer[:idx])
        
    @kernel
    def drain_channel(self):
        ts, data = rtio_input_timestamped_data(self.core.get_rtio_counter_mu(), int32(self.channel))
        return ts

    @kernel
    def clear_fifo(self):
        ts = 0
        count = 0 
        while ts >= 0:
            try:
                ts = self.drain_channel()
                count += 1
            except RTIOOverflow:
                pass
        print("Cleared:", count)
        
