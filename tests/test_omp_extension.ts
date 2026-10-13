import { afterEach, describe, expect, test } from "bun:test";
import { chmod, mkdtemp, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import {
    createTaurusToolCallHandler,
    runTaurusGuard,
} from "../compat/omp/taurus.ts";

const repositoryRoot = join(import.meta.dir, "..");
const realGuard = join(repositoryRoot, "hooks", "guard-git.py");
const python = process.env.TAURUS_PYTHON || (process.platform === "win32" ? "python" : "python3");
let fixtureRoot: string | undefined;

async function fixtureGuard(source: (root: string) => string) {
    const root = await mkdtemp(join(tmpdir(), "taurus-omp-extension-"));
    fixtureRoot = root;
    const guard = join(root, "guard.py");
    await writeFile(guard, source(root), "utf8");
    await chmod(guard, 0o700);
    return guard;
}

async function fixtureRepository() {
    const root = await mkdtemp(join(tmpdir(), "taurus-omp-project-"));
    fixtureRoot = root;
    const result = Bun.spawnSync(["git", "init", "-q", root]);
    if (result.exitCode !== 0) throw new Error("git init failed for OMP guard test");
    await writeFile(join(root, "AGENTS.md"), "private agent instructions\n", "utf8");
    return root;
}

afterEach(async () => {
    if (fixtureRoot) await rm(fixtureRoot, { recursive: true, force: true });
    fixtureRoot = undefined;
});

describe("OMP Taurus extension", () => {

    test("allows a read-only git command through the real guard", async () => {
        const result = await runTaurusGuard("git status --short", repositoryRoot, {
            guardPath: realGuard,
            python,
        });

        expect(result).toEqual({ allowed: true });
    });

    test("blocks a git commit through the real guard", async () => {
        const result = await runTaurusGuard("git commit -m bad", repositoryRoot, {
            guardPath: realGuard,
            python,
        });

        expect(result).toMatchObject({ allowed: false });
    });

    test("blocks private staging when Bash supplies a relative cwd", async () => {
        const projectRoot = await fixtureRepository();
        const handler = createTaurusToolCallHandler({ guardPath: realGuard, python });

        const result = await handler(
            { toolName: "bash", input: { command: "git add AGENTS.md", cwd: "." } },
            { cwd: projectRoot },
        );

        expect(result).toMatchObject({ block: true });
    });

    test("blocks missing Bash input and ignores non-Bash calls", async () => {
        const handler = createTaurusToolCallHandler({ guardPath: realGuard, python });

        const missingInput = await handler({ toolName: "bash" }, { cwd: repositoryRoot });
        const otherTool = await handler({ toolName: "eval" }, { cwd: repositoryRoot });

        expect(missingInput).toMatchObject({ block: true });
        expect(otherTool).toBeUndefined();
    });

    test("fails closed when the guard cannot start", async () => {
        const result = await runTaurusGuard("git status --short", repositoryRoot, {
            guardPath: realGuard,
            python: join(repositoryRoot, "missing-python"),
        });

        expect(result).toMatchObject({ allowed: false });
    });

    test("fails closed when the guard exceeds its timeout", async () => {
        const guard = await fixtureGuard(() => "import time\ntime.sleep(60)\n");
        const result = await runTaurusGuard("git status --short", repositoryRoot, {
            guardPath: guard,
            python,
            timeoutMs: 20,
        });

        expect(result).toMatchObject({ allowed: false, reason: "Taurus guard timed out; Bash was blocked." });
    });

    test("fails closed when guard output exceeds its bound", async () => {
        const guard = await fixtureGuard(() => "import sys\nsys.stdout.write('x' * 9000)\nsys.stdout.flush()\n");
        const result = await runTaurusGuard("git status --short", repositoryRoot, {
            guardPath: guard,
            python,
        });

        expect(result).toMatchObject({ allowed: false, reason: "Taurus guard exceeded its output limit; Bash was blocked." });
    });

    test("kills guard descendants after a timeout", async () => {
        let pidFile = "";
        const guard = await fixtureGuard((root) => {
            pidFile = join(root, "child.pid");
            return [
                "import subprocess",
                "import sys",
                "import time",
                'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])',
                `with open(${JSON.stringify(pidFile)}, "w") as stream:`,
                "    stream.write(str(child.pid))",
                "time.sleep(60)",
            ].join("\n");
        });
        const result = await runTaurusGuard("git status --short", repositoryRoot, {
            guardPath: guard,
            python,
            timeoutMs: 1_000,
        });

        expect(result).toMatchObject({ allowed: false, reason: "Taurus guard timed out; Bash was blocked." });
        const pid = Number(await Bun.file(pidFile).text());
        const deadline = Date.now() + 2_000;
        let alive = true;
        try {
            while (alive && Date.now() < deadline) {
                try {
                    process.kill(pid, 0);
                    await Bun.sleep(25);
                } catch {
                    alive = false;
                }
            }
            expect(alive).toBeFalse();
        } finally {
            if (alive) process.kill(pid, "SIGKILL");
        }
    });
});
