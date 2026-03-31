package com.lxb.server.cortex.notify;

import org.junit.Assert;
import org.junit.Test;

import java.util.List;

public class NotificationDumpParserTest {

    @Test
    public void parse_shouldExtractPkgTitleTextAndPostTime() {
        String dump = ""
                + "NotificationRecord(0x1):\n"
                + "  key=0|com.tencent.mm|123|null|1000\n"
                + "  pkg=com.tencent.mm userId=0 id=123 tag=null\n"
                + "  postTime=1711111111222\n"
                + "  extras={android.title=张三 android.text=今晚有空吗}\n";

        NotificationDumpParser parser = new NotificationDumpParser();
        List<NotificationEvent> out = parser.parse(dump, System.currentTimeMillis());

        Assert.assertEquals(1, out.size());
        NotificationEvent e = out.get(0);
        Assert.assertEquals("com.tencent.mm", e.packageName);
        Assert.assertEquals(1711111111222L, e.postTime);
        Assert.assertTrue(e.title.contains("张三"));
        Assert.assertTrue(e.text.contains("今晚有空吗"));
    }
}

