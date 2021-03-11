VERILOG_SOURCES = $(XILINX_VIVADO)/data/verilog/src/glbl.v $(PWD)/ADS5296A_XS7.v
TOPLEVEL=top
TOPLEVEL_LANG=verilog
MODULE=tb_ads5296a_xs7
SIM=questa
WAVES=1
# GUI=1

SIM_ARGS=-voptargs=\"-L unisims_ver -L unimacro_ver -L secureip\" work.glbl

#COMPILE_ARGS=-y$(XILINX_VIVADO)/data/verilog/src/unisims -s glbl

include $(shell cocotb-config --makefiles)/Makefile.inc
include $(shell cocotb-config --makefiles)/Makefile.sim
