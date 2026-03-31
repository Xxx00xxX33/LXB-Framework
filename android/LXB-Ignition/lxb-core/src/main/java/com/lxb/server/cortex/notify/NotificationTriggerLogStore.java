package com.lxb.server.cortex.notify;

import com.lxb.server.cortex.json.Json;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class NotificationTriggerLogStore {

    private final String filePath;
    private final int maxEntries;
    private final List<Map<String, Object>> rows = new ArrayList<Map<String, Object>>();

    public NotificationTriggerLogStore(String filePath, int maxEntries) {
        this.filePath = filePath;
        this.maxEntries = Math.max(20, maxEntries);
        loadFromDisk();
    }

    public synchronized void append(Map<String, Object> row) {
        if (row == null || row.isEmpty()) return;
        rows.add(new LinkedHashMap<String, Object>(row));
        trim();
        saveToDisk();
    }

    public synchronized List<Map<String, Object>> listRecent(int limit) {
        int n = Math.max(1, Math.min(limit, rows.size()));
        List<Map<String, Object>> out = new ArrayList<Map<String, Object>>(n);
        for (int i = rows.size() - n; i < rows.size(); i++) {
            out.add(new LinkedHashMap<String, Object>(rows.get(i)));
        }
        return out;
    }

    @SuppressWarnings("unchecked")
    private void loadFromDisk() {
        rows.clear();
        try {
            File f = new File(filePath);
            if (!f.exists() || f.length() <= 0) return;
            byte[] data = readAllBytes(f);
            if (data.length == 0) return;
            Object parsed = Json.parse(new String(data, StandardCharsets.UTF_8));
            if (!(parsed instanceof Map)) return;
            Map<String, Object> root = (Map<String, Object>) parsed;
            Object logsObj = root.get("logs");
            if (!(logsObj instanceof List)) return;
            List<Object> logs = (List<Object>) logsObj;
            for (Object o : logs) {
                if (o instanceof Map) {
                    rows.add(new LinkedHashMap<String, Object>((Map<String, Object>) o));
                }
            }
            trim();
        } catch (Exception ignored) {
            rows.clear();
        }
    }

    private void saveToDisk() {
        try {
            File f = new File(filePath);
            File parent = f.getParentFile();
            if (parent != null && !parent.exists()) {
                parent.mkdirs();
            }
            Map<String, Object> root = new LinkedHashMap<String, Object>();
            root.put("schema_version", 1);
            root.put("logs", new ArrayList<Map<String, Object>>(rows));
            byte[] data = Json.stringify(root).getBytes(StandardCharsets.UTF_8);
            FileOutputStream out = null;
            try {
                out = new FileOutputStream(f, false);
                out.write(data);
                out.flush();
            } finally {
                if (out != null) {
                    try {
                        out.close();
                    } catch (Exception ignored) {
                    }
                }
            }
        } catch (Exception ignored) {
        }
    }

    private void trim() {
        while (rows.size() > maxEntries) {
            rows.remove(0);
        }
    }

    private static byte[] readAllBytes(File f) throws Exception {
        FileInputStream in = null;
        ByteArrayOutputStream out = null;
        try {
            in = new FileInputStream(f);
            out = new ByteArrayOutputStream();
            byte[] buf = new byte[4096];
            int n;
            int total = 0;
            while ((n = in.read(buf)) != -1) {
                out.write(buf, 0, n);
                total += n;
                if (total >= 2 * 1024 * 1024) {
                    break;
                }
            }
            return out.toByteArray();
        } finally {
            if (in != null) {
                try {
                    in.close();
                } catch (Exception ignored) {
                }
            }
            if (out != null) {
                try {
                    out.close();
                } catch (Exception ignored) {
                }
            }
        }
    }
}
