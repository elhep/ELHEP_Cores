from collections import OrderedDict
import json
import os


class HasDdbManager:

    rtio_channels = []
    rtio_labels = []
    device_ids = []
    coredevices = OrderedDict()

    @classmethod
    def add_rtio_channels(cls, channel, device_id, channel_idx_arg="channel", **kwargs):
        channel_idx = len(cls.rtio_channels)
        if isinstance(channel, list):
            cls.rtio_channels += channel
            cls.rtio_labels += [device_id]*len(channel)
        else:
            cls.rtio_channels.append(channel)
            cls.rtio_labels.append(device_id)
        
        if "module" in kwargs:
            if "class_name" not in kwargs:
                raise ValueError("Both module and class_name must be given")
            module = kwargs.get("module")
            class_name = kwargs.get("class_name")
            arguments = kwargs.get("arguments", {})
            arguments[channel_idx_arg] = channel_idx
            cls.register_coredevice(device_id, module, class_name, arguments)
        cls.device_ids.append(device_id)
    
    @classmethod
    def register_coredevice(cls, device_id, module, class_name, arguments=None):
        coredevice = cls._local_device(module, class_name, arguments)
        cls.coredevices[device_id] = coredevice

    @classmethod
    def print_design_info(cls):
        print("RTIO Channels:")
        print("="*80)
        for idx, (label, device_id) in enumerate(zip(cls.rtio_labels, cls.device_ids)):
            if device_id:
                class_name = cls.coredevices[device_id]['class']
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

    @classmethod
    def store_ddb(cls, core_addr, output_dir, ref_period=1e-9):
        device_db = OrderedDict([
            ("core", cls._local_device(
                module="artiq.coredevice.core",
                class_name="Core",
                arguments={
                    "host": core_addr,
                    "ref_period": ref_period
                }
            )),
            ("core_cache", cls._local_device(
                module="artiq.coredevice.cache",
                class_name="CoreCache"
            )),
            ("code_dma", cls._local_device(
                module="artiq.coredevice.dma",
                class_name="CoreDMA"
            )),
            *(list(cls.coredevices.items()))
        ])

        ddb_content = json.dumps(device_db, indent=4)

        if not os.path.exists(output_dir):
            os.mkdir(output_dir)
        
        with open(os.path.join(output_dir, "device_db.py"), "w") as f:
            f.write("device_db = {}\n".format(ddb_content))
    