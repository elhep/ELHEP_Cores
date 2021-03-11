## Simulating cores

It is assumed `dartiq` is available in your `PATH`.

Some cores use Cocotb for TB implementation. It's recommended to use venv with Cocotb installed.

You can create one with command:

```bash
python3 -m venv ./env
source ./env/bin/activate
pip install --no-cache-dir cocotb
```