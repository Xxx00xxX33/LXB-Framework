package com.lxb.server.cortex.notify;

import org.junit.Assert;
import org.junit.Test;

import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;

public class NotificationTriggerRuleTest {

    @Test
    public void fromMap_shouldNormalizeCoreFields() {
        Map<String, Object> action = new LinkedHashMap<String, Object>();
        action.put("type", "run_task");
        action.put("user_task", "帮我回复消息");
        action.put("package", "com.tencent.mm");
        action.put("use_map", true);

        Map<String, Object> row = new LinkedHashMap<String, Object>();
        row.put("id", "r1");
        row.put("enabled", true);
        row.put("priority", 200);
        row.put("package_mode", "allowlist");
        row.put("package_list", Arrays.asList("com.tencent.mm"));
        row.put("text_mode", "contains");
        row.put("title_pattern", "张三");
        row.put("llm_yes_token", "YES");
        row.put("llm_no_token", "NO");
        row.put("task_rewrite_fail_policy", "skip");
        row.put("action", action);

        NotificationTriggerRule rule = NotificationTriggerRule.fromMap(row, 1);
        Assert.assertNotNull(rule);
        Assert.assertEquals("r1", rule.id);
        Assert.assertEquals("allowlist", rule.packageMode);
        Assert.assertEquals("contains", rule.textMode);
        Assert.assertEquals("yes", rule.llmYesToken);
        Assert.assertEquals("no", rule.llmNoToken);
        Assert.assertEquals("skip", rule.taskRewriteFailPolicy);
        Assert.assertEquals("帮我回复消息", rule.action.userTask);
        Assert.assertEquals("com.tencent.mm", rule.action.packageName);
        Assert.assertEquals(Boolean.TRUE, rule.action.useMapOverride);
    }
}

