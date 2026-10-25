"""Run with ESPHome's Python environment; requires a C++ compiler."""
from pathlib import Path
import subprocess
import tempfile
import os

import yaml


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor("!secret", lambda loader, node: loader.construct_scalar(node))
Loader.add_constructor("!lambda", lambda loader, node: loader.construct_scalar(node))
config = yaml.load(Path(__file__).with_name("lab-controller.yaml").read_text(), Loader=Loader)
scenes = ["bright_white_lab", "golden_lab", "red_lab", "night_lab"]
for i, button in enumerate(config["binary_sensor"]):
    assert (button["x_min"], button["x_max"], button["y_min"], button["y_max"]) == (
        8 + i * 78, 77 + i * 78, 160, 229
    )
    assert button["on_press"][1]["script.execute"] == {"id": "tap_feedback", "button": i}
    action = button["on_press"][-1]["homeassistant.action"]
    assert action == {"action": "scene.turn_on", "data": {"entity_id": f"scene.{scenes[i]}"}}
feedback = config["script"][0]
assert feedback["mode"] == "restart"
assert feedback["then"][0]["globals.set"]["value"] == "return button;"
assert feedback["then"][2] == {"delay": "350ms"}
assert feedback["then"][3]["globals.set"]["value"] == "-1"
assert feedback["then"][1] == feedback["then"][4] == {"component.update": "screen"}
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

assert config["time"] == [{"platform": "homeassistant", "id": "ha_time"}]
assert set("0123456789:") <= set(config["font"][1]["glyphs"])

# Execute the actual drawing lambda against a recording display, not a duplicate implementation.
source = r'''
#include <cassert>
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>
#include <fstream>
#include <cstdlib>
#include <ctime>
struct Color {
  int r, g, b;
  Color(int r, int g, int b): r(r), g(g), b(b) {}
  bool operator==(const Color &c) const { return r==c.r && g==c.g && b==c.b; }
};
enum class TextAlign { CENTER, CENTER_RIGHT };
struct Sensor { float state; } desk_temperature, desk_humidity;
struct Unit { std::string state; } temperature_unit;
struct API {
  bool online = true;
  bool is_connected_with_state_subscription() const { return online; }
} ha_api;
int reading_font = 0, caption_font = 1, title_font = 2;
struct Time {
  bool valid = true;
  int hour = 14, minute = 5;
  bool is_valid() const { return valid; }
};
struct Clock {
  Time value;
  Time now() const { return value; }
} ha_time;
int tapped_button = -1;
#define id(x) x
struct Text { int x, y, font; Color color; std::string text; TextAlign align; };
struct Box { int x, y, w, h; Color color; };
struct Display {
  std::vector<Text> texts;
  std::vector<Box> boxes;
  std::vector<Color> pixels = std::vector<Color>(320*240, Color(0,0,0));
  void pixel(int x,int y,Color c) {
    assert(x>=0 && x<320 && y>=0 && y<240);
    pixels[y*320+x]=c;
  }
  Color at(int x,int y) const { return pixels[y*320+x]; }
  void fill(Color c) { texts.clear(); boxes.clear(); std::fill(pixels.begin(),pixels.end(),c); }
  void print(int x, int y, int f, Color c, TextAlign a, const char *s) {
    texts.push_back({x,y,f,c,s,a});
  }
  void printf(int x, int y, int f, Color c, TextAlign a, const char *fmt, double n) {
    char s[64]; std::snprintf(s, sizeof(s), fmt, n); print(x,y,f,c,a,s);
  }
  void strftime(int x, int y, int f, Color c, TextAlign a, const char *fmt, Time now) {
    std::tm tm{}; tm.tm_hour = now.hour; tm.tm_min = now.minute;
    char s[64]; std::strftime(s, sizeof(s), fmt, &tm); print(x,y,f,c,a,s);
  }
  void filled_rectangle(int x,int y,int w,int h,Color c) {
    boxes.push_back({x,y,w,h,c});
    for(int yy=y;yy<y+h;yy++) for(int xx=x;xx<x+w;xx++) pixel(xx,yy,c);
  }
  void filled_circle(int x,int y,int r,Color c) {
    for(int dy=-r;dy<=r;dy++) for(int dx=-r;dx<=r;dx++)
      if(dx*dx+dy*dy<=r*r) pixel(x+dx,y+dy,c);
  }
  void circle(int x,int y,int r,Color c) {
    for(int dy=-r;dy<=r;dy++) for(int dx=-r;dx<=r;dx++)
      if(dx*dx+dy*dy<=r*r && dx*dx+dy*dy>(r-1)*(r-1)) pixel(x+dx,y+dy,c);
  }
  void line(int x,int y,int end_x,int end_y,Color c) {
    const int dx=std::abs(end_x-x), sx=x<end_x?1:-1;
    const int dy=-std::abs(end_y-y), sy=y<end_y?1:-1;
    int error=dx+dy;
    while(true) {
      pixel(x,y,c);
      if(x==end_x && y==end_y) break;
      const int twice=2*error;
      if(twice>=dy) { error+=dy; x+=sx; }
      if(twice<=dx) { error+=dx; y+=sy; }
    }
  }
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
  for(int x=0; x<320; x++) {
    const Color expected = x>=8 && x<=311 ? Color(128,128,128) : Color(0,0,0);
    assert(d.at(x,48)==expected && d.at(x,149)==expected);
    for(int y=49; y<149; y++)
      assert(d.at(x,y)==Color(0,0,0)); // no card fills or vertical borders; text recorded separately
  }
  for(const auto &t:d.texts) {
    if(t.text=="Temperature" || t.text=="Humidity") assert(t.y==73);
    if(t.text=="21.5°C" || t.text=="46%") assert(t.y==111);
    if(t.text=="Lab") assert(t.y==18);
  }
  assert(d.has("14:05") && !d.has("HA offline"));
  for(const auto &t:d.texts) if(t.text=="14:05")
    assert(t.x==310 && t.y==18 && t.font==caption_font && t.align==TextAlign::CENTER_RIGHT && t.color==Color(184,184,184));
  ha_time.value.hour=0; ha_time.value.minute=0;
  draw(d); assert(d.has("00:00"));
  ha_time.value.hour=23; ha_time.value.minute=59;
  draw(d); assert(d.has("23:59"));
  ha_time.value.valid=false;
  draw(d);
  for(const auto &t:d.texts) assert(!(t.x==310 && t.y==18));
  ha_time.value.valid=true;
  draw(d);
  const char *labels[] = {"White", "Gold", "Red", "Black"};
  assert(!d.has("SCENES"));
  const Color colors[] = {Color(255,255,255),Color(255,215,0),Color(200,0,0),Color(210,210,210)};
  for(int i=0;i<4;i++) {
    int x=8+i*78;
    assert(d.at(x,160)==Color(0,0,0)); // rounded corner, touch box unchanged
    assert(d.at(x+35,170)==Color(0,0,0));
    assert(d.at(x+35,160)==Color(0,0,0));
    assert(d.at(x+10,195)==Color(0,0,0));
    assert(!d.has(labels[i]));
    assert(d.at(x+35,180)==colors[i]);
    assert(d.at(x+35,214)==colors[i]);
    if(i<3) {
      assert(d.at(x+35,186)==colors[i]);
      assert(d.at(x+35,200)==colors[i]);
      assert(d.at(x+35,210)==colors[i]);
    } else {
      assert(d.at(x+16,218)==colors[i] && d.at(x+54,171)==colors[i]);
      assert(d.at(x+39,186)==Color(0,0,0)); // black separation beside the slash
    }
    for(const auto &t:d.texts) assert(t.y<160);
  }
  if(const char *path=std::getenv("CYD_PREVIEW")) {
    std::ofstream image(std::string(path)+".ppm",std::ios::binary);
    image << "P6\n320 240\n255\n";
    for(const auto &c:d.pixels) {image.put(c.r);image.put(c.g);image.put(c.b);}
    std::ofstream text(std::string(path)+".tsv");
    for(const auto &t:d.texts)
      text<<t.x<<'\t'<<t.y<<'\t'<<t.font<<'\t'<<t.color.r<<'\t'<<t.color.g<<'\t'<<t.color.b<<'\t'<<t.text<<'\t'<<(t.align==TextAlign::CENTER_RIGHT?"rm":"mm")<<'\n';
  }
  for(int i=0;i<4;i++) {
    tapped_button=i; draw(d);
    for(int j=0;j<4;j++)
      assert(d.at(43+j*78,160)==(i==j?Color(255,255,255):Color(0,0,0)));
  }
  tapped_button=-1; draw(d);
  assert(d.at(121,160)==Color(0,0,0));
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
  draw(d); assert(d.has("--°C") && d.has("--%") && d.has("HA offline") && !d.has("23:59"));
  for(const auto &t:d.texts) if(t.text=="HA offline")
    assert(t.x==310 && t.y==18 && t.align==TextAlign::CENTER_RIGHT);
  ha_time.value.valid=false;
  draw(d); assert(d.has("HA offline"));
  ha_api.online=true; ha_time.value.valid=true;
  draw(d); assert(d.has("23:59") && !d.has("HA offline"));
}
'''
with tempfile.TemporaryDirectory() as tmp:
    cpp, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
    cpp.write_text(source)
    subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
if preview := os.environ.get("CYD_PREVIEW"):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.open(preview + ".ppm")
    draw = ImageDraw.Draw(image)
    for row in Path(preview + ".tsv").read_text().splitlines():
        x, y, font_id, r, g, b, text, anchor = row.split("\t")
        font_config = config["font"][int(font_id)]
        weight = 500 if int(font_id) == 2 else 400
        font = ImageFont.truetype(f".esphome/font/Roboto@{weight}@False@v1.ttf", font_config["size"])
        assert set(text) <= set(font_config["glyphs"]), text
        width = draw.textbbox((0, 0), text, font=font)[2]
        assert width <= 148, (text, width)
        draw.text((int(x), int(y)), text, font=font, anchor=anchor, fill=(int(r), int(g), int(b)))
    image.save(preview + ".png")
print("PASS: scene mappings, touch bounds, layout, colors, Celsius/Fahrenheit, unavailable and offline states, clock formatting and priority")
