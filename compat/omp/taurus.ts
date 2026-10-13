import { spawn, type ChildProcess } from "node:child_process";
import { resolve } from "node:path";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

const DEFAULT_TIMEOUT_MS = 5_000;
const MAX_OUTPUT_BYTES = 8_192;

type ToolCallEvent = {
    toolName: string;
    input?: Record<string, unknown>;
};

type ToolCallContext = {
    cwd: string;
};

type GuardOptions = {
    guardPath?: string;
    python?: string;
    timeoutMs?: number;
};

type GuardResult =
    | { allowed: true }
    | { allowed: false; reason: string };

const rejection = (reason: string): GuardResult => ({ allowed: false, reason });

function selectInterpreter(): string {
    const configured = process.env.TAURUS_PYTHON;
    if (configured) return configured;
    return process.platform === "win32" ? "python" : "python3";
}

export async function runTaurusGuard(
    command: unknown,
    cwd: string | undefined,
    options: GuardOptions = {},
): Promise<GuardResult> {
    if (typeof command !== "string" || command.length === 0 || !cwd) {
        return rejection("Taurus blocked Bash because its command or working directory was unavailable.");
    }

    const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    const guardPath = options.guardPath ?? resolve(import.meta.dir, "../taurus/hooks/guard-git.py");
    const python = options.python ?? selectInterpreter();
    const payload = JSON.stringify({
        tool_name: "Bash",
        tool_input: { command },
        cwd,
        taurus_strict: true,
    });

    const { promise, resolve: resolveResult } = Promise.withResolvers<GuardResult>();
    let settled = false;
    let stopping = false;
    let outputBytes = 0;
    let timer: NodeJS.Timeout | undefined;
    let child: ChildProcess;

    const finish = (result: GuardResult) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolveResult(result);
    };
    const stop = () => {
        if (stopping) return;
        stopping = true;
        if (process.platform === "win32") {
            const taskkill = resolve(process.env.SystemRoot ?? "C:\\Windows", "System32", "taskkill.exe");
            try {
                const cleanup = spawn(taskkill, ["/PID", String(child.pid), "/T", "/F"], {
                    shell: false,
                    stdio: "ignore",
                    windowsHide: true,
                });
                const cleanupTimer = setTimeout(() => {
                    cleanup.kill("SIGKILL");
                    child.kill("SIGKILL");
                }, 1_000);
                cleanup.once("close", () => clearTimeout(cleanupTimer));
                cleanup.once("error", () => child.kill("SIGKILL"));
            } catch {
                child.kill("SIGKILL");
            }
            return;
        }
        if (child.pid) {
            try {
                process.kill(-child.pid, "SIGKILL");
                return;
            } catch {
                // The process may have already exited or failed to create its own group.
            }
        }
        child.kill("SIGKILL");
    };
    const consumeOutput = (chunk: Buffer) => {
        outputBytes += chunk.length;
        if (outputBytes > MAX_OUTPUT_BYTES) {
            stop();
            finish(rejection("Taurus guard exceeded its output limit; Bash was blocked."));
        }
    };

    try {
        child = spawn(python, [guardPath], {
            cwd,
            detached: process.platform !== "win32",
            shell: false,
            stdio: ["pipe", "pipe", "pipe"],
        });
    } catch {
        finish(rejection("Taurus guard could not start; Bash was blocked."));
        return promise;
    }

    timer = setTimeout(() => {
        stop();
        finish(rejection("Taurus guard timed out; Bash was blocked."));
    }, timeoutMs);

    child.stdout.on("data", consumeOutput);
    child.stderr.on("data", consumeOutput);
    child.on("error", () => {
        finish(rejection("Taurus guard could not run; Bash was blocked."));
    });
    child.on("close", (code) => {
        if (code === 0) {
            finish({ allowed: true });
        } else {
            finish(rejection("Taurus guard rejected Bash."));
        }
    });
    child.stdin.on("error", () => {
        stop();
        finish(rejection("Taurus guard could not receive its input; Bash was blocked."));
    });
    child.stdin.end(payload);
    return promise;
}

export function createTaurusToolCallHandler(options: GuardOptions = {}) {
    return async (event: ToolCallEvent, ctx: ToolCallContext) => {
        if (event.toolName !== "bash") return;

        const input = event.input ?? {};
        const cwd = typeof input.cwd === "string" && input.cwd ? resolve(ctx.cwd, input.cwd) : ctx.cwd;
        const result = await runTaurusGuard(input.command, cwd, options);
        return result.allowed ? undefined : { block: true, reason: result.reason };
    };
}

export default function taurusExtension(pi: ExtensionAPI) {
    pi.on("tool_call", createTaurusToolCallHandler());
}
