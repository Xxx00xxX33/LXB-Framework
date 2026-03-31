package com.lxb.server.cortex.notify;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Best-effort dumpsys notification text parser.
 *
 * Supported sources:
 * - dumpsys notification --noredact
 * - dumpsys notification
 */
public class NotificationDumpParser {

    private static final Pattern PKG_PATTERN = Pattern.compile("\\bpkg=([A-Za-z0-9._]+)");
    private static final Pattern KEY_PATTERN = Pattern.compile("\\bkey=([^\\s]+)");
    private static final Pattern KEY_PKG_PATTERN = Pattern.compile("^\\d+\\|([A-Za-z0-9._]+)\\|");
    private static final Pattern ID_PATTERN = Pattern.compile("\\bid=(-?\\d+)");
    private static final Pattern TAG_PATTERN = Pattern.compile("\\btag=([^,\\s]+)");
    private static final Pattern POST_TIME_PATTERN = Pattern.compile("\\bpostTime=([0-9]{10,16})");
    private static final Pattern WHEN_PATTERN = Pattern.compile("\\bwhen=([0-9]{10,16})");
    private static final Pattern TITLE_PATTERN = Pattern.compile("android\\.title=([^\\n\\r]+)");
    private static final Pattern TEXT_PATTERN = Pattern.compile("android\\.text=([^\\n\\r]+)");
    private static final Pattern BIG_TEXT_PATTERN = Pattern.compile("android\\.bigText=([^\\n\\r]+)");
    private static final Pattern TICKER_PATTERN = Pattern.compile("tickerText=([^\\n\\r]+)");

    public List<NotificationEvent> parse(String dumpText, long nowMs) {
        List<NotificationEvent> out = new ArrayList<NotificationEvent>();
        if (dumpText == null || dumpText.trim().isEmpty()) {
            return out;
        }
        List<String> blocks = splitBlocks(dumpText);
        if (blocks.isEmpty()) {
            NotificationEvent single = parseOneBlock(dumpText, nowMs);
            if (single != null) {
                out.add(single);
            }
            return out;
        }
        for (String block : blocks) {
            NotificationEvent e = parseOneBlock(block, nowMs);
            if (e != null) {
                out.add(e);
            }
        }
        return out;
    }

    private List<String> splitBlocks(String dumpText) {
        List<String> blocks = new ArrayList<String>();
        String[] lines = dumpText.split("\\r?\\n");
        StringBuilder cur = null;
        for (String raw : lines) {
            String line = raw != null ? raw : "";
            if (isRecordStartLine(line)) {
                if (cur != null && cur.length() > 0) {
                    blocks.add(cur.toString());
                }
                cur = new StringBuilder();
            }
            if (cur != null) {
                cur.append(line).append('\n');
            }
        }
        if (cur != null && cur.length() > 0) {
            blocks.add(cur.toString());
        }
        return blocks;
    }

    private boolean isRecordStartLine(String line) {
        if (line == null) return false;
        return line.contains("NotificationRecord(")
                || line.contains("NotificationRecord{")
                || line.contains("StatusBarNotification(");
    }

    private NotificationEvent parseOneBlock(String block, long nowMs) {
        if (block == null || block.trim().isEmpty()) return null;
        String pkg = firstMatch(PKG_PATTERN, block);
        String key = firstMatch(KEY_PATTERN, block);
        if (pkg.isEmpty() && !key.isEmpty()) {
            Matcher m = KEY_PKG_PATTERN.matcher(key);
            if (m.find()) {
                pkg = safeGroup(m, 1);
            }
        }
        if (pkg.isEmpty()) {
            return null;
        }

        int id = parseIntOrDefault(firstMatch(ID_PATTERN, block), 0);
        String tag = normalizeNullText(firstMatch(TAG_PATTERN, block));

        long postTime = parseLongOrDefault(firstMatch(POST_TIME_PATTERN, block), 0L);
        if (postTime <= 0L) {
            postTime = parseLongOrDefault(firstMatch(WHEN_PATTERN, block), 0L);
        }
        if (postTime <= 0L) {
            postTime = nowMs;
        }

        String title = normalizeNullText(firstMatch(TITLE_PATTERN, block));
        String text = normalizeNullText(firstMatch(TEXT_PATTERN, block));
        if (text.isEmpty()) {
            text = normalizeNullText(firstMatch(BIG_TEXT_PATTERN, block));
        }
        String ticker = normalizeNullText(firstMatch(TICKER_PATTERN, block));

        String resolvedKey = !key.isEmpty() ? key : (pkg + "|" + id + "|" + tag);
        return new NotificationEvent(postTime, pkg, title, text, ticker, id, tag, resolvedKey);
    }

    private static String firstMatch(Pattern p, String s) {
        if (p == null || s == null) return "";
        Matcher m = p.matcher(s);
        if (!m.find()) return "";
        return safeGroup(m, 1).trim();
    }

    private static String safeGroup(Matcher m, int idx) {
        try {
            String g = m.group(idx);
            return g != null ? g : "";
        } catch (Exception ignored) {
            return "";
        }
    }

    private static int parseIntOrDefault(String s, int defVal) {
        if (s == null || s.isEmpty()) return defVal;
        try {
            return Integer.parseInt(s.trim());
        } catch (Exception ignored) {
            return defVal;
        }
    }

    private static long parseLongOrDefault(String s, long defVal) {
        if (s == null || s.isEmpty()) return defVal;
        try {
            return Long.parseLong(s.trim());
        } catch (Exception ignored) {
            return defVal;
        }
    }

    private static String normalizeNullText(String s) {
        if (s == null) return "";
        String t = s.trim();
        String lower = t.toLowerCase(Locale.ROOT);
        if ("null".equals(lower) || "(null)".equals(lower)) {
            return "";
        }
        return t;
    }
}

