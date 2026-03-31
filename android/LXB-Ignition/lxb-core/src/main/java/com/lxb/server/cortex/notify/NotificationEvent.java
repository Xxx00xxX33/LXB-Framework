package com.lxb.server.cortex.notify;

/**
 * Normalized notification snapshot row parsed from dumpsys output.
 */
public class NotificationEvent {
    public final long postTime;
    public final String packageName;
    public final String title;
    public final String text;
    public final String ticker;
    public final int notificationId;
    public final String tag;
    public final String key;

    public NotificationEvent(
            long postTime,
            String packageName,
            String title,
            String text,
            String ticker,
            int notificationId,
            String tag,
            String key
    ) {
        this.postTime = postTime;
        this.packageName = packageName != null ? packageName : "";
        this.title = title != null ? title : "";
        this.text = text != null ? text : "";
        this.ticker = ticker != null ? ticker : "";
        this.notificationId = notificationId;
        this.tag = tag != null ? tag : "";
        this.key = key != null ? key : "";
    }

    public String shortSummary() {
        StringBuilder sb = new StringBuilder();
        sb.append("pkg=").append(packageName);
        sb.append(", title=").append(crop(title, 48));
        sb.append(", text=").append(crop(text, 72));
        sb.append(", post_time=").append(postTime);
        return sb.toString();
    }

    private static String crop(String s, int max) {
        if (s == null) return "";
        String t = s.trim();
        if (t.length() <= max) return t;
        return t.substring(0, max) + "...";
    }
}

