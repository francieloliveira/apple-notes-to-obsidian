#!/usr/bin/env python3
"""Gera assets/menubar_icon.png — cubo isométrico para a menu bar."""

import os
from AppKit import (
    NSImage, NSBitmapImageRep, NSBezierPath, NSColor,
    NSMakeRect, NSMakeSize,
)
from Foundation import NSData

SIZE = 22
OUT = os.path.join(os.path.dirname(__file__), "menubar_icon.png")


def stroke_polygon(points, width=1.35):
    path = NSBezierPath.bezierPath()
    x0, y0 = points[0]
    path.moveToPoint_((x0, y0))
    for x, y in points[1:]:
        path.lineToPoint_((x, y))
    path.closePath()
    path.setLineWidth_(width)
    path.setLineJoinStyle_(1)  # round
    path.stroke()


def main():
    img = NSImage.alloc().initWithSize_(NSMakeSize(SIZE, SIZE))
    img.lockFocus()

    NSColor.clearColor().set()
    NSBezierPath.bezierPathWithRect_(NSMakeRect(0, 0, SIZE, SIZE)).fill()

    NSColor.blackColor().set()

    # cubo isométrico: topo + esquerda + direita
    cx, cy = 11.0, 10.5
    w, d = 6.0, 3.5

    top = [(cx, cy - 5), (cx - w, cy - 1), (cx, cy + 3), (cx + w, cy - 1)]
    left = [(cx - w, cy - 1), (cx, cy + 3), (cx, cy + 9), (cx - w, cy + 5)]
    right = [(cx + w, cy - 1), (cx, cy + 3), (cx, cy + 9), (cx + w, cy + 5)]

    stroke_polygon(top)
    stroke_polygon(left)
    stroke_polygon(right)

    img.unlockFocus()
    img.setTemplate_(True)

    rep = NSBitmapImageRep.alloc().initWithData_(img.TIFFRepresentation())
    png = rep.representationUsingType_properties_(4, None)
    NSData.dataWithBytes_length_(png.bytes(), len(png)).writeToFile_atomically_(OUT, True)
    print(OUT)


if __name__ == "__main__":
    main()