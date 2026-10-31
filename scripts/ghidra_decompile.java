// Ghidra Java post-script: export functions as pseudo-C.
// Usage: -postScript ghidra_decompile.java <output_file>
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionManager;
import ghidra.util.task.ConsoleTaskMonitor;
import java.io.FileWriter;
import java.io.PrintWriter;

public class ghidra_decompile extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outPath = (args.length > 0) ? args[0] : "decompiled.c";

        DecompInterface decomp = new DecompInterface();
        decomp.openProgram(currentProgram);
        ConsoleTaskMonitor monitor = new ConsoleTaskMonitor();

        FunctionManager fm = currentProgram.getFunctionManager();
        PrintWriter out = new PrintWriter(new FileWriter(outPath));
        int count = 0;
        for (Function f : fm.getFunctions(true)) {
            if (f.isExternal() || f.isThunk()) {
                continue;
            }
            DecompileResults res = decomp.decompileFunction(f, 60, monitor);
            if (res != null && res.decompileCompleted()) {
                out.println("/* FUNCTION: " + f.getName() + " */");
                out.println(res.getDecompiledFunction().getC());
                out.println();
                count++;
            } else {
                out.println("/* DECOMPILE_FAILED: " + f.getName() + " */");
            }
        }
        out.close();
        println("[ghidra_decompile] wrote " + count + " functions -> " + outPath);
    }
}
