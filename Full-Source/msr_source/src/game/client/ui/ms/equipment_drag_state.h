#ifndef MS_EQUIPMENT_DRAG_STATE_H
#define MS_EQUIPMENT_DRAG_STATE_H
#include <cstdint>
#include <string>
#include <vector>

namespace MSREquipment
{
    struct Position { std::string name; std::int64_t capacity, used; };
    struct Requirement { std::string name; int units; };
    inline bool Eligible(bool wearable, bool attacking, bool packed, bool worn, unsigned positions, bool stackable, int quantity)
    { return wearable && !attacking && (packed || !worn) && positions>0 && (!stackable || quantity>0); }
    inline bool Compatible(const std::vector<Position>& positions,
        const std::vector<Requirement>& requirements, const std::string& target)
    {
        bool matchesTarget = false;
        if (requirements.empty()) return false;
        for (const auto& requirement : requirements)
        {
            if (requirement.units <= 0) return false;
            const Position* position = nullptr;
            for (const auto& candidate : positions)
                if (candidate.name == requirement.name) { position = &candidate; break; }
            if (!position || position->capacity <= 0 || position->used < 0 ||
                position->used > position->capacity || requirement.units > position->capacity - position->used)
                return false;
            if (requirement.name == target) matchesTarget = true;
        }
        return matchesTarget;
    }
    // Contains IDs and value snapshots only. Never retains item/button pointers.
    struct Gesture
    {
        unsigned long id = 0, parent = 0;
        int quantity = 0, startX = 0, startY = 0, width = 0, height = 0;
        float started = 0;
        bool dragging = false, doubleClick = false;
        void Clear() { *this = Gesture{}; }
        void Arm(unsigned long item, unsigned long bag, int count, int x, int y, int w, int h, float now, bool twice)
        { Clear(); id=item; parent=bag; quantity=count; startX=x; startY=y; width=w; height=h; started=now; doubleClick=twice; }
        bool Move(int x, int y)
        {
            const std::int64_t dx=static_cast<std::int64_t>(x)-startX, dy=static_cast<std::int64_t>(y)-startY;
            const bool crossed = dx>=6 || dx<=-6 || dy>=6 || dy<=-6 || dx*dx+dy*dy>=36;
            const bool began = !dragging && crossed;
            dragging = dragging || crossed;
            return began;
        }
        bool Valid(unsigned long item, unsigned long bag, int count, int w, int h, float now) const
        { return id && item==id && bag==parent && count==quantity && w==width && h==height && now>=started && now-started<10.0f; }
        // A release consumes the gesture before any callback/command can reenter.
        Gesture Take() { const Gesture copy=*this; Clear(); return copy; }
    };
}
#endif
