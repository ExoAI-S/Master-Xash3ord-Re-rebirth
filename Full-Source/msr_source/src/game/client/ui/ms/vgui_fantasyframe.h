#pragma once

// Original resolution-aware ivy linework. Geometry only: no texture/context or
// input ownership, and no references to character/item objects.
#include <algorithm>
#include <cmath>
#include <vector>

namespace MSRFantasyFrame
{
struct Point { float x, y; };
struct Color { int r, g, b, a; };
struct Span { int x0, y0, x1, y1; Color color; };
const Color Stem{105, 91, 55, 0}, StemLight{154, 130, 76, 0};
const Color LeafDark{36, 61, 42, 0}, LeafLight{66, 93, 54, 0};
const Color LeafVein{123, 132, 74, 0}, Bronze{105, 89, 54, 0};

class Canvas
{
public:
    int width, height;
    std::vector<Span> spans;
    Canvas(int w, int h) : width(w), height(h) {}
    void Rect(float x0, float y0, float x1, float y1, Color color)
    {
        const int l = std::max(0, (int)std::floor(std::min(x0, x1)));
        const int t = std::max(0, (int)std::floor(std::min(y0, y1)));
        const int r = std::min(width, (int)std::ceil(std::max(x0, x1)));
        const int b = std::min(height, (int)std::ceil(std::max(y0, y1)));
        if (l < r && t < b) spans.push_back({l, t, r, b, color});
    }
    void Line(Point a, Point b, Color color, float thickness = 1)
    {
        const float dx = b.x - a.x, dy = b.y - a.y;
        const int steps = std::max(1, (int)std::ceil(std::max(std::fabs(dx), std::fabs(dy))));
        for (int i = 0; i <= steps; ++i)
        {
            const float f = (float)i / steps;
            Rect(a.x + dx*f, a.y + dy*f, a.x + dx*f + thickness, a.y + dy*f + thickness, color);
        }
    }
    void Polygon(const std::vector<Point>& points, Color color)
    {
        if (points.size() < 3) return;
        float low = points[0].y, high = low;
        for (const auto& p : points) { low = std::min(low, p.y); high = std::max(high, p.y); }
        for (int y = std::max(0, (int)std::floor(low)); y < std::min(height, (int)std::ceil(high)); ++y)
        {
            std::vector<float> crossings;
            const float scan = y + .5f;
            for (unsigned i = 0, j = (unsigned)points.size()-1; i < points.size(); j = i++)
            {
                const auto& a = points[j]; const auto& b = points[i];
                if ((a.y <= scan && b.y > scan) || (b.y <= scan && a.y > scan))
                    crossings.push_back(a.x + (scan-a.y) * (b.x-a.x) / (b.y-a.y));
            }
            std::sort(crossings.begin(), crossings.end());
            for (unsigned i = 0; i + 1 < crossings.size(); i += 2)
                Rect(crossings[i], (float)y, crossings[i+1], (float)y+1, color);
        }
    }
    void Leaf(Point base, Point tip, float breadth)
    {
        const float dx = tip.x-base.x, dy = tip.y-base.y;
        const float length = std::sqrt(dx*dx + dy*dy);
        if (length < 1) return;
        const float nx = -dy/length, ny = dx/length;
        const Point mid{base.x+dx*.46f, base.y+dy*.46f};
        const Point left{mid.x+nx*breadth, mid.y+ny*breadth};
        const Point right{mid.x-nx*breadth*.8f, mid.y-ny*breadth*.8f};
        Polygon({base, left, {tip.x-dx*.16f+nx*breadth*.55f,tip.y-dy*.16f+ny*breadth*.55f}, tip, right}, LeafDark);
        Polygon({base, left, tip}, LeafLight);
        Line(base, tip, LeafVein);
    }
};

inline std::vector<Span> Build(int w, int h)
{
    Canvas c(w, h);
    if (w < 64 || h < 64) return c.spans;
    const float scale = std::min(2.4f, std::max(.85f, h / 960.f));
    const float margin = (float)std::max(16, h/35);
    const float edge = std::max(4.f, margin*.26f);
    const Color edgeShadow{45, 43, 29, 0};
    c.Rect(edge, edge, w-edge, edge+1, edgeShadow);
    c.Rect(edge, h-edge-1, w-edge, h-edge, edgeShadow);
    c.Rect(edge, edge, edge+1, h-edge, edgeShadow);
    c.Rect(w-edge-1, edge, w-edge, h-edge, edgeShadow);

    // Confine foliage to the outside gutter. Even at 720p it stays clear of
    // the header, bottom help text, Close button, scrollbars and item targets.
    for (int corner = 0; corner < 4; ++corner)
    {
        const bool right = (corner & 1) != 0, bottom = (corner & 2) != 0;
        auto map = [&](float along, float across, bool vertical) -> Point
        {
            float x = vertical ? across : along;
            float y = vertical ? along : across;
            return {right ? w-1-x : x, bottom ? h-1-y : y};
        };
        for (int axis = 0; axis < 2; ++axis)
        {
            const float extent = std::min((axis ? h : w)*.27f, (axis ? 155.f : 210.f)*scale);
            Point previous = map(edge, edge+3*scale, axis != 0);
            for (int n = 1; n <= 28; ++n)
            {
                const float t = n/28.f;
                const float along = edge + t*extent;
                const float across = edge + 3*scale + std::sin(t*8.f)*2.1f*scale;
                const Point next = map(along, across, axis != 0);
                c.Line(previous, next, n < 16 ? StemLight : Stem, std::max(1.f, scale*.8f));
                previous = next;
                if (n % 4 == 0 && n < 27)
                {
                    const float direction = ((n/4 + corner + axis) % 2) ? 1.f : -1.f;
                    const float leafSize = (9.f - t*2.f)*scale;
                    const float tipAcross = std::max(1.5f, std::min(margin-5.f, across + direction*leafSize*.62f));
                    c.Leaf(next, map(along+leafSize, tipAcross, axis != 0), 2.5f*scale);
                }
            }
        }
        // Small bronze corner clasp over the ivy root.
        const Point clasp = map(edge+2*scale, edge+2*scale, false);
        const float d = 2.5f*scale;
        c.Polygon({{clasp.x,clasp.y-d},{clasp.x+d,clasp.y},{clasp.x,clasp.y+d},{clasp.x-d,clasp.y}}, Bronze);
    }

    // A restrained compass/leaf crest belongs to the header divider, below
    // the character vitals and above the tabs; it never receives input.
    const float mid = w*.5f, y = margin+65.f;
    const float d = 5.f*scale;
    c.Rect(mid-49*scale, y-1, mid-13*scale, y+1, Bronze);
    c.Rect(mid+13*scale, y-1, mid+49*scale, y+1, Bronze);
    c.Polygon({{mid,y-d},{mid+d*.7f,y},{mid,y+d},{mid-d*.7f,y}}, StemLight);
    c.Line({mid-11*scale,y},{mid-5*scale,y}, StemLight);
    c.Line({mid+5*scale,y},{mid+11*scale,y}, StemLight);
    return c.spans;
}

inline const std::vector<Span>& Cached(int w, int h)
{
    static int previousW = -1, previousH = -1;
    static std::vector<Span> frame;
    if (w != previousW || h != previousH)
    {
        frame = Build(w, h);
        previousW = w; previousH = h;
    }
    return frame;
}
}
