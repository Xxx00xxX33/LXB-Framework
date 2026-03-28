package com.lxb.server.cortex;

import java.util.Calendar;

/**
 * Shared schedule time calculation helpers for CortexTaskManager.
 */
public final class CortexScheduleTime {

    private CortexScheduleTime() {
    }

    public static long computeNextDailyRun(int hour, int minute, long baseMs) {
        Calendar now = Calendar.getInstance();
        now.setTimeInMillis(baseMs);

        Calendar next = Calendar.getInstance();
        next.setTimeInMillis(baseMs);
        next.set(Calendar.SECOND, 0);
        next.set(Calendar.MILLISECOND, 0);
        next.set(Calendar.HOUR_OF_DAY, hour);
        next.set(Calendar.MINUTE, minute);
        if (next.getTimeInMillis() <= now.getTimeInMillis()) {
            next.add(Calendar.DAY_OF_MONTH, 1);
        }
        return next.getTimeInMillis();
    }

    public static long computeNextWeeklyRun(int hour, int minute, int weekdaysMask, long baseMs) {
        if ((weekdaysMask & 0x7F) == 0) {
            return 0L;
        }
        Calendar base = Calendar.getInstance();
        base.setTimeInMillis(baseMs);
        long best = Long.MAX_VALUE;
        for (int offset = 0; offset <= 7; offset++) {
            Calendar cand = (Calendar) base.clone();
            cand.add(Calendar.DAY_OF_MONTH, offset);
            cand.set(Calendar.SECOND, 0);
            cand.set(Calendar.MILLISECOND, 0);
            cand.set(Calendar.HOUR_OF_DAY, hour);
            cand.set(Calendar.MINUTE, minute);
            int dayIndex = toMonFirstDayIndex(cand.get(Calendar.DAY_OF_WEEK));
            if (((weekdaysMask >> dayIndex) & 1) == 0) {
                continue;
            }
            long t = cand.getTimeInMillis();
            if (t > baseMs && t < best) {
                best = t;
            }
        }
        if (best != Long.MAX_VALUE) {
            return best;
        }

        for (int offset = 1; offset <= 14; offset++) {
            Calendar cand = (Calendar) base.clone();
            cand.add(Calendar.DAY_OF_MONTH, offset);
            cand.set(Calendar.SECOND, 0);
            cand.set(Calendar.MILLISECOND, 0);
            cand.set(Calendar.HOUR_OF_DAY, hour);
            cand.set(Calendar.MINUTE, minute);
            int dayIndex = toMonFirstDayIndex(cand.get(Calendar.DAY_OF_WEEK));
            if (((weekdaysMask >> dayIndex) & 1) == 1) {
                return cand.getTimeInMillis();
            }
        }
        return 0L;
    }

    public static boolean isWeekdaySelected(long whenMs, int weekdaysMask) {
        Calendar c = Calendar.getInstance();
        c.setTimeInMillis(whenMs);
        int dayIndex = toMonFirstDayIndex(c.get(Calendar.DAY_OF_WEEK));
        return ((weekdaysMask >> dayIndex) & 1) == 1;
    }

    public static String normalizeRepeatMode(String repeatModeRaw) {
        String s = repeatModeRaw != null ? repeatModeRaw.trim().toLowerCase() : "";
        if ("daily".equals(s) || "weekly".equals(s) || "once".equals(s)) {
            return s;
        }
        return "once";
    }

    public static long computeFirstRunAt(long runAtMs, String repeatMode, int repeatWeekdays, long now) {
        if ("daily".equals(repeatMode)) {
            if (runAtMs > now) {
                return runAtMs;
            }
            Calendar c = Calendar.getInstance();
            c.setTimeInMillis(runAtMs);
            return computeNextDailyRun(c.get(Calendar.HOUR_OF_DAY), c.get(Calendar.MINUTE), now);
        }
        if ("weekly".equals(repeatMode)) {
            if (runAtMs > now && isWeekdaySelected(runAtMs, repeatWeekdays)) {
                return runAtMs;
            }
            Calendar c = Calendar.getInstance();
            c.setTimeInMillis(runAtMs);
            return computeNextWeeklyRun(c.get(Calendar.HOUR_OF_DAY), c.get(Calendar.MINUTE), repeatWeekdays, now);
        }
        if (runAtMs <= now) {
            throw new IllegalArgumentException("run_at must be in the future for one-shot schedule");
        }
        return runAtMs;
    }

    private static int toMonFirstDayIndex(int dayOfWeek) {
        switch (dayOfWeek) {
            case Calendar.MONDAY:
                return 0;
            case Calendar.TUESDAY:
                return 1;
            case Calendar.WEDNESDAY:
                return 2;
            case Calendar.THURSDAY:
                return 3;
            case Calendar.FRIDAY:
                return 4;
            case Calendar.SATURDAY:
                return 5;
            case Calendar.SUNDAY:
            default:
                return 6;
        }
    }
}
