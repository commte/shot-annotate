#!/usr/bin/env python3
"""スクリーンショットに赤枠・矢印・注釈を重ねる（Skitch 風）。

画像を貼っただけでは、見る人はどこを見ればいいのか分からない。
枠で場所を示し、短い注釈で何が問題かを書く。

使い方

  python3 annotate-shot.py \
    --in  before.png \
    --out after.png \
    --px \
    --box   1505,320,240,72 \
    --arrow 1400,356,1490,356 \
    --label 1090,330,"更新日がない"

座標は既定では画像の幅・高さに対する %（0〜100）。--px を付けると実寸ピクセル。

  --box     x,y,w,h        枠
  --ellipse x,y,w,h        丸。1語や見出しを囲むときに使う
  --arrow   x1,y1,x2,y2    矢印（x1,y1 から x2,y2 へ）
  --line    x1,y1,x2,y2    線。取り消し線や「ここは消す」の斜線に使う
  --label x,y,text       注釈の文字（x,y は左上）。text の中の \\n で改行
  --color red|green      これ以降の色。既定は red

--box / --ellipse / --arrow / --line / --label / --color は何度でも書ける。書いた順に描かれる。

必要なもの
  python3 と Pillow（pip install pillow）
  日本語を書くなら日本語フォント。macOS・Windows・主要な Linux は自動で見つける。
  見つからないときは --font でフォントファイルのパスを渡す。
"""
import argparse
import math
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit("Pillow が要ります: pip install pillow")

COLORS = {
    "red": (224, 45, 27),
    "green": (18, 122, 60),
    "blue": (23, 80, 94),
}

# 日本語が出るフォントを上から順に探す
FONT_CANDIDATES = [
    # macOS
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W5.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    # Windows
    "C:/Windows/Fonts/YuGothB.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
    # Linux
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def load_font(size, override=None):
    paths = [override] if override else FONT_CANDIDATES
    for path in paths:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    if override:
        raise SystemExit(f"フォントを開けません: {override}")
    print("フォントが見つからないので既定のものを使います（日本語は出ません）。"
          "--font でパスを渡してください", file=sys.stderr)
    return ImageFont.load_default()


class Collect(argparse.Action):
    """--box / --arrow / --label / --color を書いた順に集める"""

    def __call__(self, parser, ns, values, option_string=None):
        if ns.ops is None:
            ns.ops = []
        ns.ops.append((option_string.lstrip("-"), values))


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--in", dest="src", required=True, help="元の画像")
    ap.add_argument("--out", dest="dst", required=True, help="書き出す画像")
    ap.add_argument("--px", action="store_true", help="座標を % ではなく実寸ピクセルで読む")
    ap.add_argument("--scale", type=float, default=1.0, help="線の太さと文字の倍率")
    ap.add_argument("--font", help="フォントファイルのパス")
    ap.set_defaults(ops=None)
    for opt in ("--box", "--ellipse", "--arrow", "--line", "--label", "--color"):
        ap.add_argument(opt, action=Collect, dest="_ignored", metavar="…")
    ns = ap.parse_args()
    ops = ns.ops or []
    if not ops:
        raise SystemExit("--box / --arrow / --label を1つ以上指定してください")
    if not os.path.exists(ns.src):
        raise SystemExit(f"元の画像がありません: {ns.src}")

    im = Image.open(ns.src).convert("RGB")
    W, H = im.size
    dr = ImageDraw.Draw(im)
    # 幅2880pxの画像で線8px・文字44pxになる太さを基準にする。
    # 画像の大きさが違っても見た目が揃う
    unit = W / 2880 * ns.scale
    width = max(2, round(8 * unit))
    font = load_font(max(12, round(44 * unit)), ns.font)
    line_h = round(font.size * 1.45)

    def to_x(v):
        return float(v) if ns.px else float(v) / 100 * W

    def to_y(v):
        return float(v) if ns.px else float(v) / 100 * H

    def nums(value, n, kind):
        parts = value.split(",")
        if len(parts) != n:
            raise SystemExit(f"--{kind} は {n} 個の数を , で区切って渡します: {value}")
        try:
            return [float(p) for p in parts]
        except ValueError:
            raise SystemExit(f"--{kind} の数が読めません: {value}")

    color = COLORS["red"]
    for kind, value in ops:
        if kind == "color":
            if value not in COLORS:
                raise SystemExit(f"色は {' / '.join(COLORS)} のどれか: {value}")
            color = COLORS[value]
        elif kind == "box":
            x, y, w, h = nums(value, 4, "box")
            x, y, w, h = to_x(x), to_y(y), to_x(w), to_y(h)
            dr.rounded_rectangle([x, y, x + w, y + h], radius=round(6 * unit),
                                 outline=color, width=width)
        elif kind == "ellipse":
            x, y, w, h = nums(value, 4, "ellipse")
            x, y, w, h = to_x(x), to_y(y), to_x(w), to_y(h)
            dr.ellipse([x, y, x + w, y + h], outline=color, width=width)
        elif kind == "line":
            x1, y1, x2, y2 = nums(value, 4, "line")
            dr.line([to_x(x1), to_y(y1), to_x(x2), to_y(y2)], fill=color, width=width)
        elif kind == "arrow":
            x1, y1, x2, y2 = nums(value, 4, "arrow")
            x1, y1, x2, y2 = to_x(x1), to_y(y1), to_x(x2), to_y(y2)
            dr.line([x1, y1, x2, y2], fill=color, width=width)
            ang = math.atan2(y2 - y1, x2 - x1)
            head = 42 * unit
            for side in (-0.42, 0.42):
                dr.line([x2, y2,
                         x2 - head * math.cos(ang - side),
                         y2 - head * math.sin(ang - side)],
                        fill=color, width=width)
        elif kind == "label":
            parts = value.split(",", 2)
            if len(parts) != 3:
                raise SystemExit(f'--label は x,y,"文字" の形で渡します: {value}')
            x, y = to_x(parts[0]), to_y(parts[1])
            for i, line in enumerate(parts[2].split("\\n")):
                dr.text((x, y + i * line_h), line, font=font, fill=color)

    out_dir = os.path.dirname(os.path.abspath(ns.dst))
    os.makedirs(out_dir, exist_ok=True)
    im.save(ns.dst)
    print(f"{ns.dst} ({W}x{H})", file=sys.stderr)


if __name__ == "__main__":
    main()
