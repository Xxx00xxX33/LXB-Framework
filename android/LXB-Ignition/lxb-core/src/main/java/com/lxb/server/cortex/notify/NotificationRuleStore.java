package com.lxb.server.cortex.notify;

import com.lxb.server.cortex.json.Json;

import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class NotificationRuleStore {

    private final String filePath;
    private long lastMtime = -1L;
    private List<NotificationTriggerRule> cachedRules = Collections.emptyList();

    public NotificationRuleStore(String filePath) {
        this.filePath = filePath;
    }

    public synchronized List<NotificationTriggerRule> loadRules() {
        try {
            File f = new File(filePath);
            if (!f.exists()) {
                cachedRules = Collections.emptyList();
                lastMtime = -1L;
                return cachedRules;
            }
            long mtime = f.lastModified();
            if (mtime == lastMtime && cachedRules != null) {
                return cachedRules;
            }

            String text = readText(f);
            List<NotificationTriggerRule> parsed = parseRules(text);
            Collections.sort(parsed, new Comparator<NotificationTriggerRule>() {
                @Override
                public int compare(NotificationTriggerRule a, NotificationTriggerRule b) {
                    int cmp = Integer.compare(b.priority, a.priority); // high priority first
                    if (cmp != 0) return cmp;
                    return a.id.compareTo(b.id);
                }
            });
            cachedRules = Collections.unmodifiableList(parsed);
            lastMtime = mtime;
            return cachedRules;
        } catch (Exception ignored) {
            return cachedRules != null ? cachedRules : Collections.<NotificationTriggerRule>emptyList();
        }
    }

    public synchronized void invalidateCache() {
        lastMtime = -1L;
    }

    public String getFilePath() {
        return filePath;
    }

    @SuppressWarnings("unchecked")
    private List<NotificationTriggerRule> parseRules(String text) {
        List<NotificationTriggerRule> out = new ArrayList<NotificationTriggerRule>();
        if (text == null || text.trim().isEmpty()) {
            return out;
        }
        Object parsed = Json.parse(text);
        List<Object> ruleObjs = null;
        if (parsed instanceof Map) {
            Map<String, Object> root = (Map<String, Object>) parsed;
            Object rulesObj = root.get("rules");
            if (rulesObj instanceof List) {
                ruleObjs = (List<Object>) rulesObj;
            }
        } else if (parsed instanceof List) {
            ruleObjs = (List<Object>) parsed;
        }
        if (ruleObjs == null) {
            return out;
        }
        int idx = 0;
        for (Object o : ruleObjs) {
            idx++;
            if (!(o instanceof Map)) continue;
            NotificationTriggerRule rule = NotificationTriggerRule.fromMap((Map<String, Object>) o, idx);
            if (rule == null) continue;
            if (rule.id.isEmpty()) continue;
            out.add(rule);
        }
        return out;
    }

    private static String readText(File f) throws Exception {
        InputStream in = null;
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
                if (total >= 4 * 1024 * 1024) {
                    break;
                }
            }
            return new String(out.toByteArray(), StandardCharsets.UTF_8);
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
