CC = gcc
CFLAGS = -Wall -Wextra -O2 -D_GNU_SOURCE
LDFLAGS =

# ARM cross-compilation settings (uncomment for Kindle)
# CC = arm-linux-gnueabihf-gcc
# LDFLAGS += -static

SRCDIR = src
OBJDIR = obj
BINDIR = .

SOURCES = $(wildcard $(SRCDIR)/*.c)
PROGRAMS = $(patsubst $(SRCDIR)/%.c,%,$(SOURCES))

all: $(PROGRAMS)

%: $(SRCDIR)/%.c
	@mkdir -p $(OBJDIR)
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)
	@echo "Built: $@"

# Specific target for PTY bridge
pty_stpbt_bridge: $(SRCDIR)/pty_stpbt_bridge.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)
	@echo "Built PTY bridge: $@"

clean:
	rm -f $(PROGRAMS)
	rm -rf $(OBJDIR)
	@echo "Cleaned all binaries"

.PHONY: all clean
