# Tortugas Running Club - Scoring System

## 📱 WhatsApp Explanation (Copy-Paste Ready)

```
🏃‍♂️ Tortugas Leaderboard - How It Works

We're launching a NEW scoring system that's fair for everyone, regardless of pace!

💯 HOW YOU EARN POINTS:

1️⃣ TIME = POINTS
Every minute you run = 1 point
- 30 min run = 30 points
- 60 min run = 60 points
- Same for everyone, fast or slow!

2️⃣ CONSISTENCY BONUSES (per week)
Run on different days to unlock bonuses:
- 3 days → +150 points
- 4 days → +350 points
- 5-6 days → +400 points

💡 Example: Run 4x per week for 30 min each
= (30×4) + 350 bonus = 470 points total

3️⃣ RACE BONUS
Mark your activity as "Race" in Strava:
- +250 points per race
- Must edit title after marking as race (Strava quirk)

📊 WHY THIS SYSTEM?
✅ Fair: Your 30 minutes = my 30 minutes
✅ Rewards showing up consistently
✅ Encourages sustainable training (4 days = max bonus)
✅ No gaming by running 2x per day for more points

🔄 RESET: Every Monday 00:00
📈 TWO LEADERBOARDS: Weekly + All-Time

Questions? Ask in the group! 💪
```

## Overview

A time-based scoring system that rewards consistency and effort over speed and distance. Designed to create an inclusive leaderboard where all club members - regardless of pace - are motivated to participate.

## Scoring Formula (v1 - Pilot)

### Base Score: Time Investment
```
Points = minutes of running × 1
```
- Applies to all running activities: runs, long runs, workouts, races
- Warmup + workout logged separately? Both count.
- Gender-neutral: 30 minutes = 30 points for everyone

### Weekly Consistency Bonuses
Awarded based on number of **different days** with at least one activity:

| Days Active | Bonus Points |
|-------------|--------------|
| 3 days      | 150 points   |
| 4 days      | 350 points   |
| 5 days      | 400 points   |
| 6+ days     | 400 points (capped) |

**Resets:** Every Monday at 00:00 Astana time

### Race Bonus
```
250 points per race
```
- Triggered by "race" tag in activity

## Design Philosophy

### Problems We're Solving
1. **Distance-based leaderboards favor faster runners** - Males typically dominate because they cover more ground in same effort
2. **Gaming behavior** - Members running 2x per day just to get more distance points
3. **Lack of inclusivity** - Slower runners feel demotivated when they can never catch up

### Our Approach
- **Time over distance:** Levels the playing field. A 5:00/km runner and 6:30/km runner both get same points for 30 minutes
- **Consistency is king:** 4-day bonus (350pts) is worth ~6 hours of running. Shows up > burns out
- **Diminishing returns:** Going from 4→5 days only adds 50pts more. Going from 5→6 days gives zero extra points. Discourages overtraining.
- **Coach-aligned:** Standard training plan (M/W/F sessions + weekend long run) = 4 days = maximum reasonable bonus

## Club Training Structure

**Regular Schedule:**
- Monday, Wednesday, Friday: 19:00 Astana time (club sessions)
- Weekends: Long run (distance/pace set by coach)
- Total: 4 sessions/week for most members
- Advanced athletes: May have 5-6 sessions prescribed

**Flexibility:**
- Members can run solo if they miss group session
- All runs count equally (no differentiation between club/solo for pilot)

## Implementation Notes

### Data Sources
- **Strava API** via webhooks (already implemented in `src/webhooks/`)
- Activity data stored in `activities` table with `raw_data` JSON field

### Required Fields from Strava
- `moving_time` (seconds) - convert to minutes for scoring
- `start_date_local` - determine which day activity happened (Astana timezone)
- `type` - must be "Run" type activities
- `workout_type` - detect races (1 = Race, 0 = Default, 2 = Long Run, 3 = Workout)

### Weekly Calculations
- Week starts Monday 00:00 Astana time
- Count unique dates (YYYY-MM-DD) per athlete per week
- Apply appropriate consistency bonus tier

### Race Detection
- Use Strava's `workout_type` field from detailed activity API response
- `workout_type == 1` indicates a Race (set by athlete in Strava app/website)
- **Important:** Strava update webhooks do NOT fire when workout_type changes
- **Club Policy:** Athletes must edit their activity title (add space/emoji) after marking as race to trigger update webhook
- Alternative: Athletes can contact admin for manual refresh
- Track which week the race was in to enforce 1/week cap (future feature)

### Leaderboard Display
- **All-time leaderboard:** Cumulative total points
- **Weekly leaderboard:** Current week's points (resets Monday)
- Display breakdown: base points + consistency bonus + race bonuses
- Consider: Separate male/female categories or unified (TBD based on pilot feedback)

## Pilot Plan

### Duration
2-3 weeks starting [TBD]

### Success Metrics
- Participation rate (% of club members with activities)
- Activity distribution (are people running 4-5 days consistently?)
- Feedback: Do members feel motivated? Is it fair?
- Anti-gaming check: Are people still doing 2x/day spam?

### Feedback to Collect
- Is the scoring easy to understand?
- Does it feel fair across different paces/genders?
- Are consistency bonuses valued appropriately?
- Should we add elevation bonuses?
- Do we need separate male/female leaderboards?

### Potential Adjustments After Pilot
- Add elevation gain bonuses (e.g., +1 point per 10m climb)
- Adjust consistency bonus values
- Weekly caps on base points to prevent extreme outliers
- Personal improvement multipliers (beat your average pace → bonus)
- Team challenges (combined score goals)

## Edge Cases & Rules

### Multiple Activities Same Day
**Allowed.** Both count for points.
- Example: 15min warmup + 45min intervals = 60 total minutes = 60 points
- Still counts as only 1 day for consistency bonus

### Manual vs GPS Activities
- If Strava provides `moving_time`, it counts
- Manual activities without time data: 0 base points (but counts as a day for consistency)

### Activities Starting Before Midnight
Use `start_date_local` to determine which day it belongs to.
- 11:50 PM Sunday run → counts for Sunday
- Even if it ends Monday, start date determines the day

### Retroactive Changes
- Activity deleted: Points removed
- Activity edited (time changed): Recalculate points
- Activity marked as race: Athlete must also edit title to trigger webhook update
  - Strava only sends update webhooks for: Title, Type, and Privacy changes
  - Changing workout_type alone does NOT trigger webhook
  - Simple workaround: Add a space or emoji to title after marking as race

### Week Boundaries
- Week = Monday 00:00 to Sunday 23:59:59 (Astana time, UTC+5)
- Activity at Sunday 11:59 PM counts for current week
- Activity at Monday 12:01 AM counts for new week

## Future Enhancements (Post-Pilot)

### Club Session Bonuses
- Small bonus for activities on M/W/F between 18:00-20:00 Astana time
- Or: Members tag club runs with "#tortugas" in title

### Personal Bests
- Bonus for setting monthly distance PR
- Bonus for setting monthly pace PR

### Team Challenges
- Monthly team goal (e.g., "Club runs 2000km combined")
- Bonus points for everyone if team hits goal

### Streaks
- Consecutive weeks with 4+ days active
- Example: 4-week streak = 100 bonus points

### Elevation
- +1 point per 10m of elevation gain
- Rewards members who choose hilly routes

## Questions to Resolve

- [ ] When does pilot start?
- [ ] How to communicate leaderboard to members? (Web dashboard, bot, weekly posts?)
- [ ] Do we want push notifications or weekly summaries?

---

**Version:** 1.0 (Pilot)
**Last Updated:** 2026-01-18
**Status:** Design Complete, Race Detection Implemented (workout_type field added)
