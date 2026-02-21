#!/usr/bin/env python3
"""Generate universal PCB SVG for 24×18 board.

All connectors use male pin headers (オスピンヘッダ).
All wiring (buses + signal wires) is on the solder side.
Component side is clean — only pin headers and R1.
"""

PITCH = 26
BASE_X = 100
BASE_Y = 85
COLS = 24  # A-X
ROWS = 18

def col_letter(j):
    """0-indexed column → letter(s)."""
    if j < 26:
        return chr(65 + j)
    return "A" + chr(65 + j - 26)

def cx(j):
    """Column index (0-based) → x position."""
    return BASE_X + j * PITCH

def ry(i):
    """Row number (1-based) → y position."""
    return BASE_Y + (i - 1) * PITCH

def cell_name(j, i):
    """(col_index 0-based, row 1-based) → cell name like '3A'."""
    return f"{i}{col_letter(j)}"

# Board rect
BOARD_X = BASE_X - 18  # 82
BOARD_Y = BASE_Y - 17  # 68
BOARD_W = (COLS - 1) * PITCH + 36  # 634
BOARD_H = (ROWS - 1) * PITCH + 30  # 472

# Solder side
SOLDER_TITLE_Y = BOARD_Y + BOARD_H + 28  # 568
SOLDER_BOARD_Y = SOLDER_TITLE_Y + 12     # 580
SOLDER_BASE_Y = SOLDER_BOARD_Y + 17      # 597

def smx(j):
    """Mirrored x for solder side."""
    return BASE_X + (COLS - 1 - j) * PITCH

def sry(i):
    """Solder side row y."""
    return SOLDER_BASE_Y + (i - 1) * PITCH

lines = []
def emit(s=""):
    lines.append(s)

# ============================================================
# SVG Header
# ============================================================
total_h = 1580
emit('<?xml version="1.0" encoding="UTF-8"?>')
emit(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 {total_h}" font-family="sans-serif">')
emit(f'  <rect width="880" height="{total_h}" fill="#fff"/>')
emit()
emit('  <!-- Title -->')
emit('  <text x="440" y="22" text-anchor="middle" font-size="15" font-weight="bold" fill="#333">水耕栽培 Phase 1-3 ユニバーサル基板 配線図</text>')
emit('  <text x="440" y="40" text-anchor="middle" font-size="10" fill="#666">24×18ホール (2.54mmピッチ) ― 全配線はんだ面・部品面はピンヘッダのみ</text>')
emit()

# Defs - 24-hole row template
emit('  <defs>')
emit('    <g id="hr">')
for chunk_start in range(0, COLS, 8):
    chunk_end = min(chunk_start + 8, COLS)
    line = "      "
    for j in range(chunk_start, chunk_end):
        line += f'<circle cx="{j * PITCH}" cy="0" r="2.5"/>'
    emit(line)
emit('    </g>')
emit('  </defs>')
emit()

# ============================================================
# VIEW 1: Component Side
# ============================================================
emit('  <!-- ============================================================ -->')
emit('  <!--  VIEW 1: 部品面                                                -->')
emit('  <!-- ============================================================ -->')
emit('  <text x="440" y="62" text-anchor="middle" font-size="12" font-weight="bold" fill="#2E7D32">▼ 部品面（表から見た図） ― オスピンヘッダ＋R1 のみ（メスDuPontで抜き差し）</text>')
emit()
emit('  <g id="comp-side">')
emit(f'    <rect x="{BOARD_X}" y="{BOARD_Y}" width="{BOARD_W}" height="{BOARD_H}" rx="4" fill="#d4edda" fill-opacity="0.35" stroke="#2d5016" stroke-width="1.5"/>')
emit()

# Column labels A-X
emit('    <!-- Column labels -->')
emit('    <g font-size="7" fill="#999" text-anchor="middle">')
cl = "      "
for j in range(COLS):
    cl += f'<text x="{cx(j)}" y="{BOARD_Y + 10}">{col_letter(j)}</text>'
emit(cl)
emit('    </g>')

# Row labels 1-18
emit('    <!-- Row labels -->')
emit('    <g font-size="7" fill="#999" text-anchor="end">')
for i in range(1, ROWS + 1):
    emit(f'      <text x="{BASE_X - 10}" y="{ry(i) + 3}">{i}</text>')
emit('    </g>')
emit()

# Hole grid
emit('    <!-- Hole grid -->')
emit('    <g fill="#ccc">')
for i in range(1, ROWS + 1):
    emit(f'      <use href="#hr" x="{BASE_X}" y="{ry(i)}"/>')
emit('    </g>')
emit()

# ========== Used hole highlights ==========
emit('    <!-- *** Used hole highlights *** -->')

# J1 Pi Header: cols A(0)-B(1), rows 3-8
j1_pins = [
    (0, 3, "#e74c3c", "3A 3.3V"),
    (1, 3, "#e67e22", "3B 5V"),
    (0, 4, "#27ae60", "4A G4"),
    (1, 4, "#27ae60", "4B G17"),
    (0, 5, "#27ae60", "5A G5"),
    (1, 5, "#27ae60", "5B G27"),
    (0, 6, "#27ae60", "6A G22"),
    (1, 6, "#27ae60", "6B G23"),
    (1, 7, "#27ae60", "7B G24"),
    (0, 8, "#3498db", "8A GND"),
    (1, 8, "#3498db", "8B GND"),
]
emit('    <!-- J1: Pi Header -->')
for j, i, color, comment in j1_pins:
    emit(f'    <circle cx="{cx(j)}" cy="{ry(i)}" r="3.5" fill="{color}" opacity="0.8"/><!-- {comment} -->')
emit()

# R1: col G(6), rows 3-6
emit('    <!-- R1 holes -->')
emit(f'    <circle cx="{cx(6)}" cy="{ry(3)}" r="3" fill="#e74c3c" opacity="0.7"/><!-- 3G R1top -->')
emit(f'    <circle cx="{cx(6)}" cy="{ry(6)}" r="3" fill="#27ae60" opacity="0.7"/><!-- 6G R1btm -->')
emit()

# J2 DS18B20: cols F(5)-H(7), row 11
emit('    <!-- J2 DS18B20 -->')
for j, color, comment in [(5, "#e74c3c", "11F VCC"), (6, "#27ae60", "11G DATA"), (7, "#3498db", "11H GND")]:
    emit(f'    <circle cx="{cx(j)}" cy="{ry(11)}" r="3" fill="{color}" opacity="0.7"/><!-- {comment} -->')
emit()

# J3 DHT22: cols K(10)-M(12), row 11
emit('    <!-- J3 DHT22 -->')
for j, color, comment in [(10, "#e74c3c", "11K VCC"), (11, "#27ae60", "11L DATA"), (12, "#3498db", "11M GND")]:
    emit(f'    <circle cx="{cx(j)}" cy="{ry(11)}" r="3" fill="{color}" opacity="0.7"/><!-- {comment} -->')
emit()

# J4 Float: cols P(15)-Q(16), row 11
emit('    <!-- J4 Float -->')
for j, color, comment in [(15, "#27ae60", "11P SIG"), (16, "#3498db", "11Q GND")]:
    emit(f'    <circle cx="{cx(j)}" cy="{ry(11)}" r="3" fill="{color}" opacity="0.7"/><!-- {comment} -->')
emit()

# J5 Relay: cols S(18)-X(23), row 11
emit('    <!-- J5 Relay -->')
for j, color, comment in [(18, "#e67e22", "11S 5V"), (19, "#3498db", "11T GND"),
                           (20, "#27ae60", "11U IN1"), (21, "#27ae60", "11V IN2"),
                           (22, "#27ae60", "11W IN3"), (23, "#27ae60", "11X IN4")]:
    emit(f'    <circle cx="{cx(j)}" cy="{ry(11)}" r="3" fill="{color}" opacity="0.7"/><!-- {comment} -->')
emit()

# 3.3V bus holes: Row 1, cols A-K
emit('    <!-- 3.3V bus holes Row 1 -->')
emit('    <g fill="#e74c3c" opacity="0.5">')
bus = "      "
for j in range(11):  # A(0) to K(10)
    bus += f'<circle cx="{cx(j)}" cy="{ry(1)}" r="3"/>'
emit(bus)
emit('    </g>')

# GND bus holes: Row 18, full width
emit('    <!-- GND bus holes Row 18 -->')
emit('    <g fill="#3498db" opacity="0.4">')
bus = "      "
for j in range(COLS):
    bus += f'<circle cx="{cx(j)}" cy="{ry(18)}" r="3"/>'
emit(bus)
emit('    </g>')
emit()

# 3.3V vertical drop holes (cols A, F, G, K)
emit('    <!-- 3.3V vertical drop holes -->')
emit('    <g fill="#e74c3c" opacity="0.3">')
for i in [2]:
    emit(f'      <circle cx="{cx(0)}" cy="{ry(i)}" r="2.5"/>')
for i in range(2, 11):
    emit(f'      <circle cx="{cx(5)}" cy="{ry(i)}" r="2.5"/>')
emit(f'      <circle cx="{cx(6)}" cy="{ry(2)}" r="2.5"/>')
for i in range(2, 11):
    emit(f'      <circle cx="{cx(10)}" cy="{ry(i)}" r="2.5"/>')
emit('    </g>')

# GND vertical drop holes
emit('    <!-- GND vertical drop holes -->')
emit('    <g fill="#3498db" opacity="0.3">')
for j in [0, 1]:
    for i in range(9, 18):
        emit(f'      <circle cx="{cx(j)}" cy="{ry(i)}" r="2.5"/>')
for j in [7, 12, 16, 19]:
    for i in range(12, 18):
        emit(f'      <circle cx="{cx(j)}" cy="{ry(i)}" r="2.5"/>')
emit('    </g>')

# Signal drop holes: col G rows 7-10
emit('    <!-- Signal vertical drop holes -->')
emit('    <g fill="#27ae60" opacity="0.3">')
for i in range(7, 11):
    emit(f'      <circle cx="{cx(6)}" cy="{ry(i)}" r="2.5"/>')
emit('    </g>')
emit()

# ========== COMPONENT OUTLINES ==========
emit('    <!-- *** COMPONENT OUTLINES *** -->')

# J1: cols A-B, rows 3-8
j1_x1, j1_y1 = cx(0), ry(3)
j1_x2, j1_y2 = cx(1), ry(8)
emit(f'    <rect x="{j1_x1 - 11}" y="{j1_y1 - 9}" width="{j1_x2 - j1_x1 + 22}" height="{j1_y2 - j1_y1 + 18}" rx="3" fill="none" stroke="#2E7D32" stroke-width="1.5"/>')
emit(f'    <text x="{(j1_x1 + j1_x2) // 2}" y="{j1_y2 + 22}" text-anchor="middle" font-size="7" fill="#2E7D32" font-weight="bold">J1: Pi GPIO</text>')

# J1 pin labels
emit('    <g font-size="5.5" fill="#333" text-anchor="middle">')
pin_labels = [
    (0, 3, "3.3V"), (1, 3, "5V"),
    (0, 4, "G4"),   (1, 4, "G17"),
    (0, 5, "G5"),   (1, 5, "G27"),
    (0, 6, "G22"),  (1, 6, "G23"),
    (0, 7, "nc"),   (1, 7, "G24"),
    (0, 8, "GND"),  (1, 8, "GND"),
]
for j, i, label in pin_labels:
    emit(f'      <text x="{cx(j)}" y="{ry(i) - 5}">{label}</text>')
emit('    </g>')

# J1 destination annotations (reference only, no wires on component side)
emit('    <g font-size="4" fill="#888" text-anchor="middle">')
dest_annotations = [
    (1, 3, "→11S 5V", None),
    (0, 4, "→R1/DS18B20", None),
    (1, 4, "→11U IN1", None),
    (0, 5, "→11L DHT22", None),
    (1, 5, "→11V IN2", None),
    (0, 6, "→11P Float", None),
    (1, 6, "→11W IN3", None),
    (1, 7, "→11X IN4", None),
]
for j, i, label, fill in dest_annotations:
    fill_attr = f' fill="{fill}"' if fill else ""
    emit(f'      <text x="{cx(j)}" y="{ry(i) + 9}"{fill_attr}>{label}</text>')
emit('    </g>')
emit()

# R1: col G(6), rows 3-6
r1_x = cx(6)
r1_top_y = ry(3)
r1_bot_y = ry(6)
emit(f'    <!-- R1: 4.7kΩ (vertical, 3G to 6G) -->')
emit(f'    <rect x="{r1_x - 6}" y="{r1_top_y - 7}" width="12" height="{r1_bot_y - r1_top_y + 14}" rx="2" fill="#d7ccc8" stroke="#5d4037" stroke-width="1.2"/>')
for idx, color in enumerate(["#FDD835", "#7B1FA2", "#e74c3c", "#FFB300"]):
    by = r1_top_y + 8 + idx * 8
    emit(f'    <line x1="{r1_x - 5}" y1="{by}" x2="{r1_x + 5}" y2="{by}" stroke="{color}" stroke-width="2"/>')
emit(f'    <text x="{r1_x}" y="{r1_top_y - 12}" text-anchor="middle" font-size="7" fill="#5d4037" font-weight="bold">R1</text>')
emit(f'    <text x="{r1_x + 12}" y="{(r1_top_y + r1_bot_y) // 2 + 2}" font-size="5.5" fill="#5d4037">4.7kΩ</text>')
emit()

# J2: DS18B20
j2_x1, j2_y = cx(5), ry(11)
j2_x2 = cx(7)
emit(f'    <rect x="{j2_x1 - 8}" y="{j2_y - 8}" width="{j2_x2 - j2_x1 + 16}" height="16" rx="2" fill="#fffde7" stroke="#333" stroke-width="1"/>')
emit(f'    <text x="{cx(6)}" y="{j2_y + 18}" text-anchor="middle" font-size="6.5" fill="#333" font-weight="bold">J2: DS18B20</text>')
emit('    <g font-size="5" fill="#555" text-anchor="middle">')
for j, label in [(5, "VCC"), (6, "DATA"), (7, "GND")]:
    emit(f'      <text x="{cx(j)}" y="{j2_y + 1}">{label}</text>')
emit('    </g>')
emit()

# J3: DHT22
j3_x1, j3_y = cx(10), ry(11)
j3_x2 = cx(12)
emit(f'    <rect x="{j3_x1 - 8}" y="{j3_y - 8}" width="{j3_x2 - j3_x1 + 16}" height="16" rx="2" fill="#fffde7" stroke="#333" stroke-width="1"/>')
emit(f'    <text x="{cx(11)}" y="{j3_y + 18}" text-anchor="middle" font-size="6.5" fill="#333" font-weight="bold">J3: DHT22</text>')
emit('    <g font-size="5" fill="#555" text-anchor="middle">')
for j, label in [(10, "VCC"), (11, "DATA"), (12, "GND")]:
    emit(f'      <text x="{cx(j)}" y="{j3_y + 1}">{label}</text>')
emit('    </g>')
emit()

# J4: Float
j4_x1, j4_y = cx(15), ry(11)
j4_x2 = cx(16)
emit(f'    <rect x="{j4_x1 - 8}" y="{j4_y - 8}" width="{j4_x2 - j4_x1 + 16}" height="16" rx="2" fill="#fffde7" stroke="#333" stroke-width="1"/>')
emit(f'    <text x="{(cx(15) + cx(16)) // 2}" y="{j4_y + 18}" text-anchor="middle" font-size="6.5" fill="#333" font-weight="bold">J4: Float</text>')
emit('    <g font-size="5" fill="#555" text-anchor="middle">')
for j, label in [(15, "SIG"), (16, "GND")]:
    emit(f'      <text x="{cx(j)}" y="{j4_y + 1}">{label}</text>')
emit('    </g>')
emit()

# J5: Relay
j5_x1, j5_y = cx(18), ry(11)
j5_x2 = cx(23)
emit(f'    <rect x="{j5_x1 - 8}" y="{j5_y - 8}" width="{j5_x2 - j5_x1 + 16}" height="16" rx="2" fill="#fffde7" stroke="#333" stroke-width="1"/>')
emit(f'    <text x="{(cx(18) + cx(23)) // 2}" y="{j5_y + 18}" text-anchor="middle" font-size="6.5" fill="#333" font-weight="bold">J5: 4chリレー</text>')
emit('    <g font-size="5" fill="#555" text-anchor="middle">')
for j, label in [(18, "5V"), (19, "GND"), (20, "IN1"), (21, "IN2"), (22, "IN3"), (23, "IN4")]:
    emit(f'      <text x="{cx(j)}" y="{j5_y + 1}">{label}</text>')
emit('    </g>')
emit()

# NO jumper wires on component side — all wiring is on solder side

# Row 1 / Row 18 bus labels
emit(f'    <text x="{cx(5)}" y="{ry(1) - 8}" text-anchor="middle" font-size="6" fill="#c0392b" font-weight="bold">3.3V バス (Row 1)</text>')
emit(f'    <text x="{cx(11)}" y="{ry(18) + 14}" text-anchor="middle" font-size="6" fill="#2980b9" font-weight="bold">GND バス (Row 18)</text>')

# Note about clean component side
emit(f'    <text x="{cx(17)}" y="{ry(6)}" text-anchor="middle" font-size="7" fill="#888" font-style="italic">部品面には配線なし</text>')
emit(f'    <text x="{cx(17)}" y="{ry(7)}" text-anchor="middle" font-size="7" fill="#888" font-style="italic">全てはんだ面で配線</text>')

emit('  </g>')
emit()

# ============================================================
# VIEW 2: Solder Side
# ============================================================
emit('  <!-- ============================================================ -->')
emit('  <!--  VIEW 2: はんだ面                                              -->')
emit('  <!-- ============================================================ -->')
emit(f'  <text x="440" y="{SOLDER_TITLE_Y}" text-anchor="middle" font-size="12" font-weight="bold" fill="#c0392b">▼ はんだ面（裏から見た図・左右反転） ― バス＋被覆導線＋ブリッジ</text>')
emit()
emit('  <g id="solder-side">')
emit(f'    <rect x="{BOARD_X}" y="{SOLDER_BOARD_Y}" width="{BOARD_W}" height="{BOARD_H}" rx="4" fill="#fef9e7" fill-opacity="0.4" stroke="#7d6608" stroke-width="1.5"/>')
emit()

# Mirrored column labels
emit('    <g font-size="7" fill="#999" text-anchor="middle">')
cl = "      "
for j in range(COLS):
    cl += f'<text x="{cx(j)}" y="{SOLDER_BOARD_Y + 10}">{col_letter(COLS - 1 - j)}</text>'
emit(cl)
emit('    </g>')

# Row labels on RIGHT
emit(f'    <g font-size="7" fill="#999">')
for i in range(1, ROWS + 1):
    emit(f'      <text x="{cx(COLS - 1) + 15}" y="{sry(i) + 3}">{i}</text>')
emit('    </g>')
emit()

# Hole grid
emit('    <g fill="#ddd">')
for i in range(1, ROWS + 1):
    emit(f'      <use href="#hr" x="{BASE_X}" y="{sry(i)}"/>')
emit('    </g>')
emit()

# ========== SOLDER BRIDGES ==========

# RED = 3.3V
emit('    <!-- RED = 3.3V -->')
emit('    <g stroke="#e74c3c" stroke-width="4" stroke-linecap="round" fill="none" opacity="0.65">')
emit(f'      <line x1="{smx(10)}" y1="{sry(1)}" x2="{smx(0)}" y2="{sry(1)}"/><!-- 3.3V bus -->')
emit(f'      <line x1="{smx(0)}" y1="{sry(1)}" x2="{smx(0)}" y2="{sry(3)}"/><!-- to J1 3.3V -->')
emit(f'      <line x1="{smx(5)}" y1="{sry(1)}" x2="{smx(5)}" y2="{sry(11)}"/><!-- to DS18B20 VCC -->')
emit(f'      <line x1="{smx(6)}" y1="{sry(1)}" x2="{smx(6)}" y2="{sry(3)}"/><!-- to R1 top -->')
emit(f'      <line x1="{smx(10)}" y1="{sry(1)}" x2="{smx(10)}" y2="{sry(11)}"/><!-- to DHT22 VCC -->')
emit('    </g>')
emit()

# BLUE = GND
emit('    <!-- BLUE = GND -->')
emit('    <g stroke="#3498db" stroke-width="4" stroke-linecap="round" fill="none" opacity="0.65">')
emit(f'      <line x1="{smx(COLS-1)}" y1="{sry(18)}" x2="{smx(0)}" y2="{sry(18)}"/><!-- GND bus -->')
for j, from_row, comment in [
    (0, 8, "J1 GND"), (1, 8, "J1 GND"),
    (7, 11, "DS18B20 GND"), (12, 11, "DHT22 GND"),
    (16, 11, "Float GND"), (19, 11, "Relay GND"),
]:
    emit(f'      <line x1="{smx(j)}" y1="{sry(from_row)}" x2="{smx(j)}" y2="{sry(18)}"/><!-- {comment} -->')
emit('    </g>')
emit()

# GREEN = Signal (R1 bottom → DS18B20 DATA)
emit('    <!-- GREEN = Signal -->')
emit('    <g stroke="#27ae60" stroke-width="3.5" stroke-linecap="round" fill="none" opacity="0.7">')
emit(f'      <line x1="{smx(6)}" y1="{sry(6)}" x2="{smx(6)}" y2="{sry(11)}"/><!-- 6G→11G: R1btm→DATA -->')
emit('    </g>')
emit()

# ========== INSULATED WIRES (被覆導線) W1-W8 on solder side ==========
emit('    <!-- PURPLE = 被覆導線 W1-W8 (insulated, can cross buses) -->')
# W1-W8 connect GPIO pins to sensor pins, all on solder side
# Using mirrored coordinates
solder_wires = [
    # (from_j, from_i, to_j, to_i, label, color_override)
    (0, 4, 6, 7, "W1:G4→R1", None),       # GPIO4 → 7G (R1/DATA junction)
    (0, 5, 11, 11, "W2:G5→DHT", None),     # GPIO5 → 11L (DHT22 DATA)
    (0, 6, 15, 11, "W3:G22→Float", None),  # GPIO22 → 11P (Float SIG)
    (1, 3, 18, 11, "W4:5V→Relay", "#e67e22"),  # 5V → 11S (Relay VCC)
    (1, 4, 20, 11, "W5:G17→IN1", None),    # GPIO17 → 11U (Relay IN1)
    (1, 5, 21, 11, "W6:G27→IN2", None),    # GPIO27 → 11V (Relay IN2)
    (1, 6, 22, 11, "W7:G23→IN3", None),    # GPIO23 → 11W (Relay IN3)
    (1, 7, 23, 11, "W8:G24→IN4", None),    # GPIO24 → 11X (Relay IN4)
]
emit('    <g stroke="#9b59b6" stroke-width="1.8" fill="none" opacity="0.8">')
for fj, fi, tj, ti, label, color in solder_wires:
    stroke = f' stroke="{color}"' if color else ""
    emit(f'      <line x1="{smx(fj)}" y1="{sry(fi)}" x2="{smx(tj)}" y2="{sry(ti)}"{stroke}/>')
emit('    </g>')

# Wire labels on solder side
emit('    <g font-size="5" fill="#7d3c98">')
for fj, fi, tj, ti, label, color in solder_wires:
    mx_pos = (smx(fj) + smx(tj)) // 2
    my_pos = (sry(fi) + sry(ti)) // 2 - 4
    fill_attr = f' fill="{color}"' if color else ""
    emit(f'      <text x="{mx_pos}" y="{my_pos}"{fill_attr}>{label}</text>')
emit('    </g>')
emit()

# Solder bridge labels
emit('    <g font-size="5.5" font-weight="bold">')
emit(f'      <text x="{(smx(0) + smx(10)) // 2}" y="{sry(1) - 5}" text-anchor="middle" fill="#c0392b">3.3V バス (1A〜1K)</text>')
emit(f'      <text x="{smx(0) + 6}" y="{sry(2) + 3}" fill="#c0392b" font-size="5">1A→3A</text>')
emit(f'      <text x="{smx(5) + 6}" y="{sry(6)}" fill="#c0392b" font-size="5">1F→11F</text>')
emit(f'      <text x="{smx(6) + 6}" y="{sry(2) + 3}" fill="#c0392b" font-size="5">1G→3G</text>')
emit(f'      <text x="{smx(10) - 30}" y="{sry(6)}" fill="#c0392b" font-size="5">1K→11K</text>')
emit(f'      <text x="{(smx(0) + smx(COLS-1)) // 2}" y="{sry(18) + 12}" text-anchor="middle" fill="#2980b9">GND バス (18A〜18X)</text>')
gnd_labels = [(0, "8A↓"), (1, "8B↓"), (7, "11H↓"), (12, "11M↓"), (16, "11Q↓"), (19, "11T↓")]
for j, label in gnd_labels:
    emit(f'      <text x="{smx(j)}" y="{sry(14)}" text-anchor="middle" fill="#2980b9" font-size="4.5">{label}</text>')
emit(f'      <text x="{smx(6) + 8}" y="{sry(8) + 3}" fill="#27ae60" font-size="5">6G→11G</text>')
emit('    </g>')
emit()

# Component ghosts
emit('    <g fill="none" stroke="#aaa" stroke-width="1" stroke-dasharray="3,2">')
emit(f'      <rect x="{smx(1) - 11}" y="{sry(3) - 9}" width="{smx(0) - smx(1) + 22}" height="{sry(8) - sry(3) + 18}" rx="2"/>')
emit(f'      <rect x="{smx(6) - 6}" y="{sry(3) - 7}" width="12" height="{sry(6) - sry(3) + 14}" rx="2"/>')
emit(f'      <rect x="{smx(7) - 8}" y="{sry(11) - 8}" width="{smx(5) - smx(7) + 16}" height="16" rx="2"/>')
emit(f'      <rect x="{smx(12) - 8}" y="{sry(11) - 8}" width="{smx(10) - smx(12) + 16}" height="16" rx="2"/>')
emit(f'      <rect x="{smx(16) - 8}" y="{sry(11) - 8}" width="{smx(15) - smx(16) + 16}" height="16" rx="2"/>')
emit(f'      <rect x="{smx(23) - 8}" y="{sry(11) - 8}" width="{smx(18) - smx(23) + 16}" height="16" rx="2"/>')
emit('    </g>')
emit('    <g font-size="5.5" fill="#aaa" text-anchor="middle">')
emit(f'      <text x="{(smx(0) + smx(1)) // 2}" y="{sry(3) - 14}">J1</text>')
emit(f'      <text x="{smx(6)}" y="{sry(3) - 14}">R1</text>')
emit(f'      <text x="{smx(6)}" y="{sry(11) + 14}">J2</text>')
emit(f'      <text x="{smx(11)}" y="{sry(11) + 14}">J3</text>')
emit(f'      <text x="{(smx(15) + smx(16)) // 2}" y="{sry(11) + 14}">J4</text>')
emit(f'      <text x="{(smx(18) + smx(23)) // 2}" y="{sry(11) + 14}">J5</text>')
emit('    </g>')
emit('  </g>')
emit()

# ============================================================
# LEGEND
# ============================================================
legend_y = sry(18) + 30
emit(f'  <g id="legend" transform="translate(0,{legend_y})">')
emit('    <rect x="30" y="0" width="820" height="65" rx="4" fill="#f8f9fa" stroke="#dee2e6" stroke-width="1"/>')
emit('    <text x="50" y="16" font-size="10" font-weight="bold" fill="#333">凡例</text>')
emit('    <g font-size="8" fill="#333">')
emit('      <line x1="50" y1="32" x2="80" y2="32" stroke="#e74c3c" stroke-width="4" stroke-linecap="round"/>')
emit('      <text x="85" y="35">3.3V（すずめっき線）</text>')
emit('      <line x1="240" y1="32" x2="270" y2="32" stroke="#3498db" stroke-width="4" stroke-linecap="round"/>')
emit('      <text x="275" y="35">GND（すずめっき線）</text>')
emit('      <line x1="420" y1="32" x2="450" y2="32" stroke="#27ae60" stroke-width="3.5" stroke-linecap="round"/>')
emit('      <text x="455" y="35">信号（はんだブリッジ）</text>')
emit('      <line x1="610" y1="32" x2="650" y2="32" stroke="#9b59b6" stroke-width="1.8"/>')
emit('      <text x="655" y="35">被覆導線（はんだ面）</text>')
emit('    </g>')
emit('    <g font-size="8" fill="#333">')
emit('      <circle cx="60" cy="52" r="3.5" fill="#e74c3c" opacity="0.7"/><text x="70" y="55">3.3V穴</text>')
emit('      <circle cx="140" cy="52" r="3.5" fill="#3498db" opacity="0.7"/><text x="150" y="55">GND穴</text>')
emit('      <circle cx="210" cy="52" r="3.5" fill="#e67e22" opacity="0.7"/><text x="220" y="55">5V穴</text>')
emit('      <circle cx="270" cy="52" r="3.5" fill="#27ae60" opacity="0.7"/><text x="280" y="55">信号穴</text>')
emit('      <rect x="340" y="48" width="16" height="8" rx="1" fill="#d7ccc8" stroke="#5d4037" stroke-width="0.8"/><text x="360" y="55">抵抗</text>')
emit('      <rect x="400" y="48" width="16" height="8" rx="1" fill="#fffde7" stroke="#333" stroke-width="0.8"/><text x="420" y="55">ピンヘッダ（オス）</text>')
emit('    </g>')
emit('  </g>')
emit()

# ============================================================
# CONNECTION TABLE
# ============================================================
table_y = legend_y + 80
emit(f'  <g id="conn-table" transform="translate(0,{table_y})">')
emit('    <text x="50" y="16" font-size="11" font-weight="bold" fill="#333">接続一覧</text>')
emit('    <rect x="30" y="24" width="820" height="18" fill="#e8e8e8"/>')
emit('    <text x="40" y="37" font-size="8" font-weight="bold" fill="#333">はんだ面の配線 ― すずめっき線 / はんだブリッジ（バス・電源・信号）</text>')
emit('    <g font-size="7.5" fill="#333">')
emit('      <text x="40" y="54" fill="#e74c3c" font-weight="bold">3.3V バス:</text>')
emit('      <text x="110" y="54">1A-1B-...-1K （Row 1 横方向・すずめっき線推奨）</text>')
emit('      <text x="40" y="68" fill="#e74c3c" font-weight="bold">3.3V 縦:</text>')
emit('      <text x="110" y="68">1A→3A (J1)　|　1F→11F (DS18B20 VCC)　|　1G→3G (R1上端)　|　1K→11K (DHT22 VCC)</text>')
emit('      <text x="40" y="82" fill="#3498db" font-weight="bold">GND バス:</text>')
emit('      <text x="110" y="82">18A-18B-...-18X （Row 18 横方向・すずめっき線推奨）</text>')
emit('      <text x="40" y="96" fill="#3498db" font-weight="bold">GND 縦:</text>')
emit('      <text x="110" y="96">8A→18A, 8B→18B (J1)　|　11H→18H (DS18B20)　|　11M→18M (DHT22)　|　11Q→18Q (Float)　|　11T→18T (Relay)</text>')
emit('      <text x="40" y="110" fill="#27ae60" font-weight="bold">信号:</text>')
emit('      <text x="110" y="110">6G→7G→...→11G （R1下端→DS18B20 DATA はんだブリッジ）</text>')
emit('    </g>')
emit()
emit('    <rect x="30" y="122" width="820" height="18" fill="#e8e8e8"/>')
emit('    <text x="40" y="135" font-size="8" font-weight="bold" fill="#333">はんだ面の配線 ― 被覆導線（GPIO→センサー信号線）</text>')
emit('    <g font-size="7.5" fill="#333">')
emit('      <text x="40" y="152" fill="#7d3c98" font-weight="bold">W1:</text>')
emit('      <text x="60" y="152">4A (GPIO4) → 7G（R1下端と同じ列、裏面で11G DS18B20 DATAまでブリッジ済み）</text>')
emit('      <text x="40" y="166" fill="#7d3c98" font-weight="bold">W2:</text>')
emit('      <text x="60" y="166">5A (GPIO5) → 11L（DHT22 DATA に直結）</text>')
emit('      <text x="40" y="180" fill="#7d3c98" font-weight="bold">W3:</text>')
emit('      <text x="60" y="180">6A (GPIO22) → 11P（フロートスイッチ SIG）</text>')
emit('      <text x="440" y="152" fill="#c0392b" font-weight="bold">W4:</text>')
emit('      <text x="460" y="152">3B (5V) → 11S（リレー VCC）</text>')
emit('      <text x="440" y="166" fill="#7d3c98" font-weight="bold">W5:</text>')
emit('      <text x="460" y="166">4B (GPIO17) → 11U（リレー IN1 循環ポンプ）</text>')
emit('      <text x="440" y="180" fill="#7d3c98" font-weight="bold">W6:</text>')
emit('      <text x="460" y="180">5B (GPIO27) → 11V（リレー IN2 予備）</text>')
emit('      <text x="440" y="194" fill="#7d3c98" font-weight="bold">W7:</text>')
emit('      <text x="460" y="194">6B (GPIO23) → 11W（リレー IN3 UV予約）</text>')
emit('      <text x="440" y="208" fill="#7d3c98" font-weight="bold">W8:</text>')
emit('      <text x="460" y="208">7B (GPIO24) → 11X（リレー IN4 予備）</text>')
emit('    </g>')
emit('  </g>')
emit()

# ============================================================
# NOTES
# ============================================================
notes_y = table_y + 230
emit(f'  <g id="notes" transform="translate(0,{notes_y})">')
emit('    <rect x="30" y="0" width="820" height="94" rx="4" fill="#fff3e0" stroke="#ff9800" stroke-width="1"/>')
emit('    <text x="50" y="16" font-size="9" font-weight="bold" fill="#e65100">作業手順</text>')
emit('    <g font-size="8" fill="#333">')
emit('      <text x="50" y="30">1. 部品面に J1〜J5 のオスピンヘッダと R1 を差し込む</text>')
emit('      <text x="50" y="42">2. 基板を裏返し（左右反転！）、各ピンヘッダのリード線と R1 をはんだ付け</text>')
emit('      <text x="50" y="54">3. はんだ面で 3.3V バス (Row1) と GND バス (Row18) にすずめっき線を置き、はんだ付け</text>')
emit('      <text x="50" y="66">4. 縦方向のドロップ（VCC/GND→各センサー）もすずめっき線 or はんだブリッジで接続</text>')
emit('      <text x="50" y="78">5. はんだ面で W1〜W8 の被覆導線を配線（ピンヘッダのリードに直接はんだ付け）</text>')
emit('      <text x="50" y="90">6. 部品面のピンヘッダにメス DuPont コネクタで Pi GPIO とセンサーを差し込む → 完成</text>')
emit('    </g>')
emit('  </g>')
emit()

# ============================================================
# SAFETY
# ============================================================
safety_y = notes_y + 109
emit(f'  <g id="safety" transform="translate(0,{safety_y})">')
emit('    <rect x="30" y="0" width="820" height="38" rx="4" fill="#ffebee" stroke="#c62828" stroke-width="1"/>')
emit('    <text x="50" y="15" font-size="8" font-weight="bold" fill="#c62828">注意: リレーモジュールの12V出力側は基板に載せない。リレー出力端子(COM/NO)と12V電源・ポンプの接続はネジ端子で行うこと。</text>')
emit('    <text x="50" y="30" font-size="8" fill="#c62828">R1(4.7kΩ)=DS18B20プルアップ。DHT22は3ピンモジュール内蔵プルアップ使用。フロートスイッチはGPIO内部プルアップ使用。</text>')
emit('  </g>')
emit('</svg>')

output = "\n".join(lines)
with open("/Users/shotaro/projects/raspi-hydroponics/docs/diagrams/universal_pcb_24x18.svg", "w", encoding="utf-8") as f:
    f.write(output)

print(f"Generated: {len(lines)} lines, {len(output)} bytes")
print(f"Board: {COLS}cols x {ROWS}rows, {BOARD_W}x{BOARD_H}px")
print(f"Component side: y={BOARD_Y}-{BOARD_Y+BOARD_H}")
print(f"Solder side: y={SOLDER_BOARD_Y}-{SOLDER_BOARD_Y+BOARD_H}")
