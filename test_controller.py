"""Run with ESPHome's Python environment; requires a C++ compiler."""
from pathlib import Path
import subprocess
import tempfile

import yaml


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!secret", lambda loader, node: loader.construct_scalar(node))
config = yaml.load(Path(__file__).with_name("lab-controller.yaml").read_text(), Loader=Loader)
scenes = ["bright_white_lab", "golden_lab", "red_lab", "night_lab"]
for i, button in enumerate(config["binary_sensor"]):
    assert (button["x_min"], button["x_max"], button["y_min"], button["y_max"]) == (
        8 + i * 78, 77 + i * 78, 160, 229
    )
    action = button["on_press"][-1]["homeassistant.action"]
    assert action == {"action": "scene.turn_on", "data": {"entity_id": f"scene.{scenes[i]}"}}
assert config["display"][0]["platform"] == "ili9xxx"
assert config["display"][0]["model"] == "ILI9341"
assert config["display"][0]["color_palette"] == "8BIT"
assert config["display"][0]["color_order"] == "RGB"
assert config["display"][0]["data_rate"] == "10MHz"
assert config["display"][0]["dimensions"] == {"width": 320, "height": 240}
assert config["display"][0]["rotation"] == 180
assert config["touchscreen"]["transform"] == {"swap_xy": True, "mirror_x": False, "mirror_y": False}
# Prior White/Gold/Red/Black samples must map to the opposite coordinates after the 180° flip.
calibration = config["touchscreen"]["calibration"]
for button, (raw_x, raw_y) in zip(config["binary_sensor"], [(857, 3379), (813, 2495), (836, 1523), (840, 516)]):
    x = (calibration["x_max"] - raw_y) * 320 / (calibration["x_max"] - calibration["x_min"])
    y = (calibration["y_max"] - raw_x) * 240 / (calibration["y_max"] - calibration["y_min"])
    assert button["x_min"] <= x <= button["x_max"], (button["id"], x)
    assert button["y_min"] <= y <= button["y_max"], (button["id"], y)
    flipped_x = (raw_y - calibration["x_min"]) * 320 / (calibration["x_max"] - calibration["x_min"])
    flipped_y = (raw_x - calibration["y_min"]) * 240 / (calibration["y_max"] - calibration["y_min"])
    assert abs(x + flipped_x - 320) < 1e-6
    assert abs(y + flipped_y - 240) < 1e-6
assert [sensor["entity_id"] for sensor in config["sensor"]] == [
    "sensor.desk_temperature", "sensor.desk_humidity"
]
assert config["text_sensor"][0]["attribute"] == "unit_of_measurement"

# Execute the actual drawing lambda against a recording display, not a duplicate implementation.
source = r'''
#include <cassert>
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>
struct Color {
  int r, g, b;
  Color(int r, int g, int b): r(r), g(g), b(b) {}
  bool operator==(const Color &c) const { return r==c.r && g==c.g && b==c.b; }
};
enum class TextAlign { CENTER };
struct Sensor { float state; } desk_temperature, desk_humidity;
struct Unit { std::string state; } temperature_unit;
struct API {
  bool online = true;
  bool is_connected_with_state_subscription() const { return online; }
} ha_api;
int reading_font = 0, label_font = 1;
#define id(x) x
struct Text { int x, y; Color color; std::string text; };
struct Box { int x, y, w, h; Color color; };
struct Display {
  std::vector<Text> texts;
  std::vector<Box> boxes;
  void fill(Color) { texts.clear(); boxes.clear(); }
  void print(int x, int y, int, Color c, TextAlign, const char *s) {
    texts.push_back({x,y,c,s});
  }
  void printf(int x, int y, int f, Color c, TextAlign a, const char *fmt, double n) {
    char s[64]; std::snprintf(s, sizeof(s), fmt, n); print(x,y,f,c,a,s);
  }
  void filled_rectangle(int x,int y,int w,int h,Color c) { boxes.push_back({x,y,w,h,c}); }
  void rectangle(int,int,int,int,Color) {}
  bool has(const char *s) const {
    for (const auto &t: texts) if (t.text == s) return true;
    return false;
  }
};
void draw(Display &it) {
''' + config["display"][0]["lambda"] + r'''
}
int main() {
  Display d;
  desk_temperature.state = 21.5f; temperature_unit.state = "°C";
  desk_humidity.state = 46.0f;
  draw(d); assert(d.has("21.5°C") && d.has("46%"));
  const char *labels[] = {"White", "Gold", "Red", "Black"};
  for (int i=0; i<4; i++) {
    const auto &b = d.boxes.at(i);
    assert(b.x == 8+i*78 && b.y == 160 && b.w == 70 && b.h == 70);
    assert(b.x+b.w <= 320 && b.y+b.h <= 240);
    const auto &t = d.texts.at(4+i);
    assert(t.text == labels[i] && t.x == b.x+35 && t.y == 195);
    assert(t.color == (i<2 ? Color(0,0,0) : Color(255,255,255)));
  }
  assert(d.boxes[0].color == Color(255,255,255));
  assert(d.boxes[1].color == Color(255,215,0));
  assert(d.boxes[2].color == Color(200,0,0));
  assert(d.boxes[3].color == Color(0,0,0));
  temperature_unit.state = "°F"; desk_temperature.state = 77;
  draw(d); assert(d.has("25.0°C"));
  temperature_unit.state = "K";
  draw(d); assert(d.has("--°C"));
  temperature_unit.state = "°C"; desk_temperature.state = NAN; desk_humidity.state = NAN;
  draw(d); assert(d.has("--°C") && d.has("--%"));
  desk_temperature.state = INFINITY; desk_humidity.state = 101;
  draw(d); assert(d.has("--°C") && d.has("--%"));
  desk_humidity.state = -1; draw(d); assert(d.has("--%"));
  desk_temperature.state = 22; desk_humidity.state = 50; ha_api.online = false;
  draw(d); assert(d.has("--°C") && d.has("--%") && d.has("HA offline"));
}
'''
with tempfile.TemporaryDirectory() as tmp:
    cpp, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
    cpp.write_text(source)
    subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("PASS: scene mappings, touch bounds, layout, colors, Celsius/Fahrenheit, unavailable and offline states")
