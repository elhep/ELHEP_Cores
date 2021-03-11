## Simulating cores

It is assumed `dartiq` is available in your `PATH` and that DARTIQ image is tagged 'dartiq'. 

Some cores use Cocotb for TB implementation. It's recommended to use venv with Cocotb installed.

You can create one with command:

```bash
python3 -m venv ./env
source ./env/bin/activate
pip install --no-cache-dir cocotb
```

Simulation of some cores can be executed by issueing `make` command. However, a few comes with 
dedicated `run_sim` script. If the script is present in cores `tests` directory, it should be 
used to run the simulation.