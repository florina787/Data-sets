import { render, screen } from "@testing-library/react";
import { POSES, SherinCharacter, CHARACTER_ASSET } from "../sherin/Character";
import { canCelebrate, directiveFor, runPhase, syntheticEvents, type HarnessEvent } from "../sherin/machine";
import { Aborted, sherin } from "../sherin/director";

const plan = [{ step: 1, agent: "investment_judgment", tool: "guardian.evaluate", objective: "x" }];
const ev = (event: HarnessEvent["event"], extra: Partial<HarnessEvent> = {}): HarnessEvent => ({ seq: 0, event, message: "", synthetic: false, ...extra });

describe("event → character mapping", () => {
  it("maps each live execution event to a gesture and destination", () => {
    expect(directiveFor(ev("AGENT_STARTED", { agent: "esg" }))).toMatchObject({ pose: "point", target: { kind: "agent", id: "esg" } });
    expect(directiveFor(ev("TOOL_RUNNING", { tool: "esg.scores" })).pose).toBe("work");
    expect(directiveFor(ev("VALIDATION_STARTED")).target).toEqual({ kind: "node", id: "verify" });
    expect(directiveFor(ev("APPROVAL_REQUIRED", { approval_status: "pending" }))).toMatchObject({ pose: "waiting", target: { kind: "manager" } });
    expect(directiveFor(ev("APPROVAL_REQUIRED", { approval_status: "blocked" })).pose).toBe("error");
    expect(directiveFor(ev("TASK_COMPLETED", { verified: true })).pose).toBe("success");
    expect(directiveFor(ev("TASK_COMPLETED", { verified: false })).pose).toBe("warning");
    expect(directiveFor(ev("TASK_FAILED", { message: "boom" })).pose).toBe("error");
    expect(directiveFor(ev("TOOL_DENIED")).pose).toBe("warning");
  });

  it("never celebrates before the workflow finishes, or after a rejection", () => {
    const pending = syntheticEvents(plan);
    expect(runPhase(pending)).toBe("awaiting_approval");
    expect(canCelebrate(pending)).toBe(false);
    expect(canCelebrate(syntheticEvents(plan, "rejected"))).toBe(false);
    const ok = syntheticEvents(plan, "approved");
    expect(runPhase(ok)).toBe("completed");
    expect(canCelebrate(ok)).toBe(true);
    expect(canCelebrate([ev("TASK_COMPLETED", { verified: false })])).toBe(false);
    expect(canCelebrate([ev("TASK_COMPLETED", { verified: true })])).toBe(true);
  });

  it("labels demonstration events as synthetic", () => {
    expect(syntheticEvents(plan, "approved").every((e) => e.synthetic)).toBe(true);
  });
});

describe("character rig", () => {
  it("renders every state from one asset", () => {
    for (const p of POSES) {
      const { unmount } = render(<SherinCharacter pose={p} />);
      const el = screen.getByTestId("sherin-character");
      expect(el.getAttribute("data-pose")).toBe(p);
      expect(el.getAttribute("data-asset")).toBe(CHARACTER_ASSET.id);
      unmount();
    }
    expect(POSES).toHaveLength(10); // + walking left/right via facing = 11 states
  });
});

describe("director", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => { vi.useRealTimers(); sherin.resume(); sherin.setSpeed(1); sherin.setReduced(false); sherin.attachLane(null); });

  it("sleep honours pause and speed", async () => {
    sherin.setSpeed(2);
    let done = false;
    sherin.sleep(1000).then(() => (done = true));
    sherin.pause();
    await vi.advanceTimersByTimeAsync(2000);
    expect(done).toBe(false);
    sherin.resume();
    await vi.advanceTimersByTimeAsync(560);
    expect(done).toBe(true);
  });

  it("abort rejects pending choreography (skip / jump)", async () => {
    const p = sherin.sleep(5000);
    sherin.abort();
    const r = expect(p).rejects.toBeInstanceOf(Aborted);
    await vi.advanceTimersByTimeAsync(100);
    await r;
  });

  it("reduced motion repositions without walking", async () => {
    const lane = { width: () => 1000, left: () => 0, jump: vi.fn(), walk: vi.fn() };
    sherin.attachLane(lane as any);
    sherin.setReduced(true);
    await sherin.walkTo(0.8);
    expect(lane.jump).toHaveBeenCalledWith(800);
    expect(lane.walk).not.toHaveBeenCalled();
    expect(sherin.get().walking).toBe(false);
  });

  it("walks with a turn when changing direction", async () => {
    let finish!: () => void;
    const lane = { width: () => 1000, left: () => 0, jump: vi.fn(), walk: vi.fn(() => ({ done: new Promise<void>((r) => (finish = r)), pause() {}, play() {}, stop() {} })) };
    sherin.attachLane(lane as any);
    sherin.setX(800);
    const facing = sherin.get().facing;
    const p = sherin.walkTo(0.1);
    if (facing === 1) { expect(sherin.get().pose).toBe("turn"); await vi.advanceTimersByTimeAsync(300); }
    expect(sherin.get().pose).toBe("walk");
    expect(sherin.get().facing).toBe(-1);
    finish();
    await p;
    expect(sherin.get().pose).toBe("idle");
    expect(sherin.get().x).toBe(100);
  });
});
