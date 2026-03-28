package com.lxb.server.cortex;

import org.junit.Assert;
import org.junit.Test;

import java.util.Calendar;

public class CortexScheduleTimeTest {

    @Test
    public void normalizeRepeatMode_defaultsToOnce() {
        Assert.assertEquals("once", CortexScheduleTime.normalizeRepeatMode("unknown"));
        Assert.assertEquals("daily", CortexScheduleTime.normalizeRepeatMode("daily"));
    }

    @Test
    public void computeFirstRunAt_onceRejectsPast() {
        long now = System.currentTimeMillis();
        try {
            CortexScheduleTime.computeFirstRunAt(now - 1000, "once", 0, now);
            Assert.fail("expected IllegalArgumentException");
        } catch (IllegalArgumentException expected) {
            Assert.assertTrue(expected.getMessage().contains("future"));
        }
    }

    @Test
    public void computeNextDailyRun_movesToNextDayWhenPassed() {
        Calendar base = Calendar.getInstance();
        base.set(Calendar.SECOND, 0);
        base.set(Calendar.MILLISECOND, 0);
        base.set(Calendar.HOUR_OF_DAY, 12);
        base.set(Calendar.MINUTE, 30);

        long next = CortexScheduleTime.computeNextDailyRun(11, 0, base.getTimeInMillis());
        Calendar out = Calendar.getInstance();
        out.setTimeInMillis(next);
        Assert.assertEquals(11, out.get(Calendar.HOUR_OF_DAY));
        Assert.assertEquals(0, out.get(Calendar.MINUTE));
        Assert.assertTrue(next > base.getTimeInMillis());
    }

    @Test
    public void computeNextWeeklyRun_returnsFutureSelectedDay() {
        Calendar base = Calendar.getInstance();
        base.set(Calendar.SECOND, 0);
        base.set(Calendar.MILLISECOND, 0);

        int weekdaysMask = 0b0000001; // Monday
        long next = CortexScheduleTime.computeNextWeeklyRun(9, 15, weekdaysMask, base.getTimeInMillis());
        Assert.assertTrue(next > base.getTimeInMillis());
        Assert.assertTrue(CortexScheduleTime.isWeekdaySelected(next, weekdaysMask));
    }
}
