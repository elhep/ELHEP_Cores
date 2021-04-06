VERILOG_SOURCES=$(XILINX_VIVADO)/data/verilog/src/glbl.v sim_build/dut.v
TOPLEVEL=top
TOPLEVEL_LANG=verilog
MODULE=tb_trigger_controller
SIM=icarus
WAVES=1

# SIM_ARGS=-voptargs=\"-L unisims_ver -L unimacro_ver -L secureip\" work.glbl

ELHEP_CORES=$(PWD)/../../../..
DARTIQ_IMAGE=dartiq

export PYTHONPATH := $(PYTHONPATH):$(ELHEP_CORES)

include $(shell cocotb-config --makefiles)/Makefile.sim

sim_build/dut.v: $(PWD)/../trigger_controller.py
	mkdir -p sim_build
	dartiq run -m $(PWD)/../../../.. --workspace=sim_build/ --image=$(DARTIQ_IMAGE) "python -m elhep_cores.cores.trigger_controller.trigger_controller"
