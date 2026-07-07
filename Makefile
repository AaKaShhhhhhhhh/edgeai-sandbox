CXX = aarch64-linux-g++

CXXFLAGS = -std=c++17 -O3 -Wall -Werror

LIBS = `pkg-config --cflags --libs opencv4 gstreamer-1.0`

TARGET = edge_ai_node

all: $(TARGET)

$(TARGET): main.cpp
	$(CXX) $(CXXFLAGS) main.cpp -o $(TARGET) $(LIBS)

clean:
	rm -f $(TARGET)

