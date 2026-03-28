package com.lxb.server.cortex.route;

import com.lxb.server.cortex.Locator;
import com.lxb.server.cortex.LocatorResolver;
import com.lxb.server.cortex.ResolvedNode;
import com.lxb.server.cortex.RouteMap;
import com.lxb.server.cortex.TraceLogger;
import com.lxb.server.execution.ExecutionEngine;
import com.lxb.server.perception.PerceptionEngine;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Route execution orchestration extracted from CortexFacade.
 * Keeps trace names and payload semantics unchanged.
 */
public class RouteExecutionService {

    private static final int LAUNCH_RETRY_MAX = 3;
    private static final long LAUNCH_WAIT_TIMEOUT_MS = 5000L;
    private static final long LAUNCH_WAIT_SAMPLE_MS = 500L;

    private final ExecutionEngine executionEngine;
    private final PerceptionEngine perceptionEngine;
    private final LocatorResolver locatorResolver;
    private final TraceLogger trace;

    public RouteExecutionService(
            ExecutionEngine executionEngine,
            PerceptionEngine perceptionEngine,
            LocatorResolver locatorResolver,
            TraceLogger trace
    ) {
        this.executionEngine = executionEngine;
        this.perceptionEngine = perceptionEngine;
        this.locatorResolver = locatorResolver;
        this.trace = trace;
    }

    public Map<String, Object> executeRoute(
            String pkg,
            String effectiveFrom,
            String effectiveTo,
            java.util.List<RouteMap.Transition> path
    ) {
        boolean launchOk = launchAppForRoute(pkg);
        Map<String, Object> launchEv = new LinkedHashMap<String, Object>();
        launchEv.put("package", pkg);
        launchEv.put("clear_task", true);
        launchEv.put("result", launchOk ? "ok" : "fail");
        trace.event("route_launch_app", launchEv);
        if (!launchOk) {
            Map<String, Object> outFail = new LinkedHashMap<String, Object>();
            outFail.put("ok", false);
            outFail.put("package", pkg);
            outFail.put("from_page", effectiveFrom);
            outFail.put("to_page", effectiveTo);
            outFail.put("steps", new java.util.ArrayList<Object>());
            outFail.put("reason", "launch_failed");
            return outFail;
        }
        try {
            Thread.sleep(1500);
        } catch (InterruptedException ignored) {
        }

        java.util.List<Map<String, Object>> stepSummaries = new java.util.ArrayList<Map<String, Object>>();
        int index = 0;
        boolean allOk = true;

        for (RouteMap.Transition t : path) {
            Map<String, Object> stepEv = new LinkedHashMap<String, Object>();
            stepEv.put("package", pkg);
            stepEv.put("from_page", t.fromPage);
            stepEv.put("to_page", t.toPage);
            stepEv.put("index", index);
            stepEv.put("description", t.description);
            trace.event("route_step_start", stepEv);

            Map<String, Object> step = new LinkedHashMap<String, Object>();
            step.put("index", index);
            step.put("from", t.fromPage);
            step.put("to", t.toPage);
            step.put("description", t.description);

            String result = "ok";
            String reason = "";
            String pickedStage = "";
            java.util.List<Object> pickedBounds = null;

            try {
                Locator locator = t.action != null ? t.action.locator : null;
                if (locator == null) {
                    result = "resolve_fail";
                    reason = "missing_locator";
                    allOk = false;
                } else {
                    ResolvedNode node = resolveWithRetry(locator);
                    pickedStage = node.pickedStage;
                    pickedBounds = node.bounds.toList();

                    int cx = (node.bounds.left + node.bounds.right) / 2;
                    int cy = (node.bounds.top + node.bounds.bottom) / 2;

                    ByteBuffer tapPayload = ByteBuffer.allocate(4).order(ByteOrder.BIG_ENDIAN);
                    tapPayload.putShort((short) cx);
                    tapPayload.putShort((short) cy);
                    byte[] resp = executionEngine.handleTap(tapPayload.array());

                    step.put("tap_resp_len", resp != null ? resp.length : 0);
                }
            } catch (Exception e) {
                allOk = false;
                String msg = String.valueOf(e);
                result = result.startsWith("resolve") ? result : "tap_fail";
                reason = msg;
            }

            step.put("picked_stage", pickedStage);
            if (pickedBounds != null) {
                step.put("picked_bounds", pickedBounds);
            }
            step.put("result", result);
            step.put("reason", reason);

            trace.event("route_step_end", step);

            stepSummaries.add(step);
            if (!"ok".equals(result)) {
                break;
            }
            index++;

            try {
                Thread.sleep(400);
            } catch (InterruptedException ignored) {
            }
        }

        Map<String, Object> out = new LinkedHashMap<String, Object>();
        out.put("ok", allOk);
        out.put("package", pkg);
        out.put("from_page", effectiveFrom);
        out.put("to_page", effectiveTo);
        out.put("steps", stepSummaries);
        if (!allOk) {
            out.put("reason", "step_failed");
        }

        trace.event("route_end", buildRouteEvent(pkg, effectiveFrom, effectiveTo, allOk ? "ok" : "failed"));

        return out;
    }

    public ResolvedNode resolveWithRetry(Locator locator) throws Exception {
        final int maxAttempts = 3;
        final long intervalMs = 300L;
        Exception last = null;

        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                ResolvedNode node = locatorResolver.resolve(locator);
                Map<String, Object> ev = new LinkedHashMap<String, Object>();
                ev.put("attempt", attempt);
                ev.put("result", "ok");
                trace.event("route_resolve_locator", ev);
                return node;
            } catch (IllegalStateException e) {
                last = e;
                String msg = String.valueOf(e.getMessage());
                boolean isNoCandidates = msg != null && msg.contains("no candidates");

                Map<String, Object> ev = new LinkedHashMap<String, Object>();
                ev.put("attempt", attempt);
                ev.put("err", msg);
                trace.event("route_resolve_retry", ev);

                if (!isNoCandidates || attempt == maxAttempts) {
                    throw e;
                }

                try {
                    Thread.sleep(intervalMs);
                } catch (InterruptedException ignored) {
                }
            }
        }

        if (last != null) {
            throw last;
        }
        throw new IllegalStateException("locator resolve failed");
    }

    public static Map<String, Object> buildRouteEvent(String pkg, String from, String to, String status) {
        Map<String, Object> m = new LinkedHashMap<String, Object>();
        m.put("package", pkg);
        m.put("from_page", from);
        m.put("to_page", to);
        m.put("status", status);
        return m;
    }

    private boolean launchAppForRoute(String packageName) {
        try {
            for (int attempt = 1; attempt <= LAUNCH_RETRY_MAX; attempt++) {
                stopAppBestEffortForRoute(packageName);
                boolean launchOk = launchAppClearTaskForRoute(packageName);
                boolean packageReady = launchOk && waitForForegroundPackageForRoute(
                        packageName, LAUNCH_WAIT_TIMEOUT_MS, LAUNCH_WAIT_SAMPLE_MS
                );

                Map<String, Object> ev = new LinkedHashMap<String, Object>();
                ev.put("package", packageName);
                ev.put("attempt", attempt);
                ev.put("launch_ok", launchOk);
                ev.put("package_ready", packageReady);
                trace.event("route_launch_attempt", ev);

                if (launchOk && packageReady) {
                    return true;
                }
            }
            Map<String, Object> ev = new LinkedHashMap<String, Object>();
            ev.put("package", packageName);
            ev.put("attempts", LAUNCH_RETRY_MAX);
            ev.put("reason", "package_not_ready");
            trace.event("route_launch_failed", ev);
            return false;
        } catch (Exception e) {
            Map<String, Object> ev = new LinkedHashMap<String, Object>();
            ev.put("err", String.valueOf(e));
            ev.put("package", packageName);
            trace.event("route_launch_err", ev);
            return false;
        }
    }

    private boolean launchAppClearTaskForRoute(String packageName) {
        byte[] pkgBytes = packageName.getBytes(StandardCharsets.UTF_8);
        ByteBuffer buf = ByteBuffer.allocate(1 + 2 + pkgBytes.length).order(ByteOrder.BIG_ENDIAN);
        int flags = 0x01;
        buf.put((byte) flags);
        buf.putShort((short) pkgBytes.length);
        buf.put(pkgBytes);
        byte[] resp = executionEngine.handleLaunchApp(buf.array());
        boolean ok = resp != null && resp.length > 0 && resp[0] == 0x01;
        if (!ok) {
            Map<String, Object> ev = new LinkedHashMap<String, Object>();
            ev.put("package", packageName);
            ev.put("status", resp != null && resp.length > 0 ? (int) resp[0] : 0);
            trace.event("route_launch_status", ev);
        }
        return ok;
    }

    private boolean waitForForegroundPackageForRoute(String expectedPackage, long timeoutMs, long sampleMs) {
        long deadline = System.currentTimeMillis() + Math.max(0L, timeoutMs);
        while (true) {
            String currentPkg = getCurrentPackageForRoute();
            if (expectedPackage.equals(currentPkg)) {
                return true;
            }
            if (System.currentTimeMillis() >= deadline) {
                return false;
            }
            try {
                Thread.sleep(Math.max(1L, sampleMs));
            } catch (InterruptedException ignored) {
                return false;
            }
        }
    }

    private String getCurrentPackageForRoute() {
        try {
            byte[] resp = perceptionEngine.handleGetActivity();
            if (resp == null || resp.length < 5) {
                return "";
            }
            ByteBuffer buf = ByteBuffer.wrap(resp).order(ByteOrder.BIG_ENDIAN);
            byte status = buf.get();
            if (status == 0) {
                return "";
            }
            int pkgLen = buf.getShort() & 0xFFFF;
            if (pkgLen <= 0 || buf.remaining() < pkgLen) {
                return "";
            }
            byte[] pkgBytes = new byte[pkgLen];
            buf.get(pkgBytes);
            return new String(pkgBytes, StandardCharsets.UTF_8).trim();
        } catch (Exception ignored) {
            return "";
        }
    }

    private void stopAppBestEffortForRoute(String packageName) {
        try {
            byte[] pkgBytes = packageName.getBytes(StandardCharsets.UTF_8);
            ByteBuffer buf = ByteBuffer.allocate(2 + pkgBytes.length).order(ByteOrder.BIG_ENDIAN);
            buf.putShort((short) pkgBytes.length);
            buf.put(pkgBytes);
            byte[] resp = executionEngine.handleStopApp(buf.array());
            boolean ok = resp != null && resp.length > 0 && resp[0] == 0x01;
            Map<String, Object> ev = new LinkedHashMap<String, Object>();
            ev.put("package", packageName);
            ev.put("result", ok ? "ok" : "fail");
            trace.event("route_stop_app", ev);
            try {
                Thread.sleep(150);
            } catch (InterruptedException ignored) {
            }
        } catch (Exception e) {
            Map<String, Object> ev = new LinkedHashMap<String, Object>();
            ev.put("package", packageName);
            ev.put("err", String.valueOf(e));
            trace.event("route_stop_err", ev);
        }
    }
}
