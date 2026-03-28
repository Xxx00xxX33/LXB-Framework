package com.lxb.server.cortex;

import org.junit.Assert;
import org.junit.Test;

import java.io.File;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class CortexTaskPersistenceTest {

    @Test
    public void taskMemory_roundTrip() throws Exception {
        File tmp = Files.createTempFile("task-memory", ".json").toFile();
        tmp.deleteOnExit();

        CortexTaskPersistence persistence = new CortexTaskPersistence();
        Map<String, Map<String, Object>> byTask = new ConcurrentHashMap<String, Map<String, Object>>();
        Map<String, Map<String, Object>> bySchedule = new ConcurrentHashMap<String, Map<String, Object>>();

        Map<String, Object> row = new LinkedHashMap<String, Object>();
        row.put("summary_text", "ok");
        byTask.put("task:demo", row);

        persistence.saveTaskMemory(tmp.getAbsolutePath(), byTask, bySchedule);

        Map<String, Map<String, Object>> outTask = new ConcurrentHashMap<String, Map<String, Object>>();
        Map<String, Map<String, Object>> outSchedule = new ConcurrentHashMap<String, Map<String, Object>>();
        persistence.loadTaskMemory(tmp.getAbsolutePath(), outTask, outSchedule);

        Assert.assertTrue(outTask.containsKey("task:demo"));
        Assert.assertEquals("ok", String.valueOf(outTask.get("task:demo").get("summary_text")));
    }

    @Test
    public void rows_roundTrip() throws Exception {
        File tmp = Files.createTempFile("schedule-rows", ".json").toFile();
        tmp.deleteOnExit();

        CortexTaskPersistence persistence = new CortexTaskPersistence();
        List<Object> rows = new ArrayList<Object>();
        Map<String, Object> row = new LinkedHashMap<String, Object>();
        row.put("schedule_id", "sid-1");
        rows.add(row);

        persistence.saveRows(tmp.getAbsolutePath(), "schedules.v1", "schedules", rows);
        List<Object> loaded = persistence.loadRows(tmp.getAbsolutePath(), "schedules");

        Assert.assertNotNull(loaded);
        Assert.assertEquals(1, loaded.size());
    }
}
