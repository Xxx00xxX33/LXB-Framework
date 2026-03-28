package com.lxb.server.cortex.fsm;

import org.junit.Assert;
import org.junit.Test;

import java.util.Collections;
import java.util.List;

public class VisionCommandParserTest {

    @Test
    public void parseInstructions_handlesQuotedInput() throws Exception {
        List<VisionCommandParser.Instruction> out = VisionCommandParser.parseInstructions(
                "INPUT \"hello world\"",
                2
        );
        Assert.assertEquals(1, out.size());
        Assert.assertEquals("INPUT", out.get(0).op);
        Assert.assertEquals("hello world", out.get(0).args.get(0));
    }

    @Test
    public void parseInstructions_rejectsTooManyCommands() {
        try {
            VisionCommandParser.parseInstructions("WAIT 100\nWAIT 100", 1);
            Assert.fail("expected InstructionError");
        } catch (VisionCommandParser.InstructionError expected) {
            Assert.assertTrue(expected.getMessage().contains("too many instructions"));
        }
    }

    @Test
    public void validateAllowed_rejectsDisallowedOp() throws Exception {
        List<VisionCommandParser.Instruction> out = VisionCommandParser.parseInstructions("BACK", 1);
        try {
            VisionCommandParser.validateAllowed(out, Collections.singleton("TAP"));
            Assert.fail("expected InstructionError");
        } catch (VisionCommandParser.InstructionError expected) {
            Assert.assertTrue(expected.getMessage().contains("not allowed"));
        }
    }

    @Test
    public void extractStructuredCommandForVision_extractsCommandAndFields() {
        String raw = "<vision_analysis><lesson>avoid loop</lesson></vision_analysis>\n"
                + "<command>TAP 100 200</command>";
        VisionCommandParser.ExtractResult er = VisionCommandParser.extractStructuredCommandForVision(raw);
        Assert.assertEquals("TAP 100 200", er.commandText);
        Assert.assertEquals("avoid loop", String.valueOf(er.structured.get("lesson")));
    }
}
