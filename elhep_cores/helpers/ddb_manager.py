from collections import OrderedDict
import json
import os


class DdbManager:

    def __init__(self, core_addr, output_dir, ref_period=1e-9):
        self.rtio_channels = []
        self.rtio_labels = []
        self.device_ids = []
        self.coredevices = OrderedDict()
        self.core_addr = core_addr
        self.ref_period = ref_period

    def add_rtio_channels(self, channel, device_id, channel_idx_arg="channel", **kwargs):
        channel_idx = len(self.rtio_channels)
        if isinstance(channel, list):
            self.rtio_channels += channel
            self.rtio_labels += [device_id]*len(channel)
        else:
            self.rtio_channels.append(channel)
            self.rtio_labels.append(device_id)
        
        if "module" in kwargs:
            if "class_name" not in kwargs:
                raise ValueError("Both module and class_name must be given")
            module = kwargs.get("module")
            class_name = kwargs.get("class_name")
            arguments = kwargs.get("arguments", {})
            arguments[channel_idx_arg] = channel_idx
            self.register_coredevice(device_id, module, class_name, arguments)
        self.device_ids.append(device_id)
        
    def register_coredevice(self, device_id, module, class_name, arguments=None):
        coredevice = self._local_device(module, class_name, arguments)
        self.coredevices[device_id] = coredevice

    def print_design_info(self):
        print("RTIO Channels:")
        print("="*80)
        for idx, (label, device_id) in enumerate(zip(self.rtio_labels, self.device_ids)):
            if device_id:
                class_name = self.coredevices[device_id]['class']
                print(f"{idx:3d}: {label} -> {device_id}({class_name})")
            else:
                print(f"{idx:3d}: {label}")

    @staticmethod
    def _local_device(module, class_name, arguments=None):
        coredevice = OrderedDict([
            ("type", "local"),
            ("module", module),
            ("class", class_name)
        ])
        if arguments:
            coredevice['arguments'] = arguments
        return coredevice

    @staticmethod
    def _controller(host, port, command):
        return OrderedDict([
            ("type", "controller"),
            ("host", host),
            ("port", port),
            ("command", command)
        ])

    def store_ddb(self, output_dir):
        device_db = OrderedDict([
            ("core", self._local_device(
                module="artiq.coredevice.core",
                class_name="Core",
                arguments={
                    "host": self.core_addr,
                    "ref_period": self.ref_period
                }
            )),
            ("core_cache", self._local_device(
                module="artiq.coredevice.cache",
                class_name="CoreCache"
            )),
            ("code_dma", self._local_device(
                module="artiq.coredevice.dma",
                class_name="CoreDMA"
            )),
            *(list(self.coredevices.items()))
        ])

        if not os.path.exists(output_dir):
            os.mkdir(output_dir)
        
        with open(os.path.join(output_dir, "device_db.py"), "w") as f:
            json.dump(device_db, f, indent=4)
    