CC = gcc
CFLAGS = -Wall -Wextra -O2 -D_GNU_SOURCE
LDFLAGS =

# ARM cross-compilation for Kindle
# CC = arm-linux-gnueabihf-gcc
# CFLAGS += -march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=softfp -mtune=cortex-a53
# LDFLAGS += -static

SRCDIR = src
BINDIR = .

# Working components only
WORKING_SOURCES = $(SRCDIR)/vhci_stpbt_bridge.c

all: vhci_stpbt_bridge

vhci_stpbt_bridge: $(SRCDIR)/vhci_stpbt_bridge.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)
	@echo "Built VHCI bridge: $@"

clean:
	rm -f vhci_stpbt_bridge
	@echo "Cleaned binaries"

.PHONY: all clean
