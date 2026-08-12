# Copyright 2026 Max Planck Institute for Software Systems,
# National University of Singapore, and SimBricks UG (haftungsbeschränkt)
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


PREFIX            ?= /usr/local
CXX               ?= c++
SIMBRICKS_INC_DIR ?= $(PREFIX)/include
SIMBRICKS_LIB_DIR ?= $(PREFIX)/lib

SIMBRICKS_LDLIBS  ?= -L$(SIMBRICKS_LIB_DIR) \
    -Wl,--start-group -lnicbm -lnicif -lnetwork -lpcie -lbase -Wl,--end-group
ENSO_LDLIBS       ?= -lboost_fiber -lboost_context -lpthread

DEPFLAGS   = -MMD -MP
CPPFLAGS  += -I$(SIMBRICKS_INC_DIR) $(EXTRA_CPPFLAGS)
CXXFLAGS  += -Wall -Wextra -Wno-unused-parameter -O3 -fPIC -std=gnu++17 $(EXTRA_CXXFLAGS)

SRCS := enso_bm.cc logger.cc
OBJS := $(SRCS:.cc=.o)
BIN  := simb_enso_bm

.PHONY: all install-enso clean

all: $(BIN)

$(BIN): $(OBJS)
	$(CXX) $(LDFLAGS) -o $@ $(OBJS) $(SIMBRICKS_LDLIBS) $(ENSO_LDLIBS)

%.o: %.cc
	$(CXX) $(DEPFLAGS) $(CPPFLAGS) $(CXXFLAGS) -c -o $@ $<

install-enso:
	install -d $(PREFIX)/bin
	install -m 755 $(BIN) $(PREFIX)/bin/$(BIN)

clean:
	rm -f $(OBJS) $(OBJS:.o=.d) $(BIN)

-include $(OBJS:.o=.d)
