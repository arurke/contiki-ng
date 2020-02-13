CONTIKI_PROJECT = node
all: $(CONTIKI_PROJECT)
CONTIKI=../..
#CONTIKI=../../../../../..

# Add any given extra-config from command-line (e.g. simulation-scripts)
CFLAGS += $(CFLAGSEXTRA)

# NOTE! Energest seems to give 0 on radio measumrent for native platform
# This software should build for z1 platform, but changes
# are needed in csc
# An alternative to energest and duty-cycle is to somehow fetch the # of
# cell scheduled
MODULES += $(CONTIKI_NG_SERVICES_DIR)/simple-energest

# Use TSCH
MAKE_MAC = MAKE_MAC_TSCH

# Use storing-mode RPL
MAKE_ROUTING = MAKE_ROUTING_RPL_CLASSIC

# Use Orchestra
MODULES += os/services/orchestra

include $(CONTIKI)/Makefile.include
