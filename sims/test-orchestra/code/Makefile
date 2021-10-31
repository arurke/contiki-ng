CONTIKI_PROJECT = node
all: $(CONTIKI_PROJECT)
ifeq ($(TARGET),cooja)
CONTIKI=../../..
else
CONTIKI=../../../../../..
endif

# Add any given extra-config from command-line (e.g. simulation-scripts)
CFLAGS += $(CFLAGSEXTRA)

# NOTE! Energest seems to give 0 on radio measumrent for native platform
# An alternative to energest and duty-cycle is to somehow fetch the # of
# cell scheduled 
MODULES += $(CONTIKI_NG_SERVICES_DIR)/simple-energest

# Use TSCH
MAKE_MAC = MAKE_MAC_TSCH

# Use storing-mode RPL
MAKE_ROUTING = MAKE_ROUTING_RPL_CLASSIC

# Use Orchestra
#MODULES += os/services/orchestra

# Use Layered
MODULES += os/services/layered

ifdef TESTBED
CFLAGS += -DTESTBED=$(TESTBED)
MODULES += $(CONTIKI_NG_SERVICES_DIR)/deployment
endif

include $(CONTIKI)/Makefile.include
