import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CatMark } from "../components/CatMark";
import { Composer } from "../components/Composer";
import { Markdown } from "../components/Markdown";
import { StatusDot, Switch } from "../components/ui";

describe("CatMark", () => {
  it("renders the shared SVG mascot with an accessible label and mood class", () => {
    const { container } = render(<CatMark size={48} mood="listening" label="VEENA mascot" />);
    expect(container.querySelector("svg[aria-label='VEENA mascot']")).not.toBeNull();
    expect(container.firstElementChild).toHaveClass("is-listening");
    expect(container.querySelector(".veena-lid")?.getAttribute("opacity")).toBe("0");
  });
});

describe("Markdown", () => {
  it("renders code blocks with a language label and copy button, and tables", () => {
    render(<Markdown text={"Answer\n\n```python\nprint('hi')\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |"} />);
    expect(screen.getByText("python")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy" })).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("does not render raw HTML from model output", () => {
    const { container } = render(<Markdown text={'<img src=x onerror="alert(1)"> <script>alert(1)</script>'} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
  });
});

describe("Switch", () => {
  it("is an accessible switch that toggles", () => {
    const onChange = vi.fn();
    render(<Switch checked={false} onChange={onChange} label="Redact" />);
    const sw = screen.getByRole("switch", { name: "Redact" });
    expect(sw).toHaveAttribute("aria-checked", "false");
    fireEvent.click(sw);
    expect(onChange).toHaveBeenCalledWith(true);
  });
});

describe("StatusDot", () => {
  it("conveys state by shape and text, not by colour alone", () => {
    render(<StatusDot state="problem" label="Ollama offline" />);
    expect(screen.getByText("Ollama offline")).toBeInTheDocument();
  });
});

describe("Composer", () => {
  it("sends on Enter, keeps Shift+Enter for new lines, and clears", () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} showMic={false} />);
    const box = screen.getByLabelText("Message") as HTMLTextAreaElement;
    fireEvent.change(box, { target: { value: "line one" } });
    fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("line one", null);
    expect(box.value).toBe("");
  });

  it("passes an explicit answer style", () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} showMic={false} />);
    fireEvent.change(screen.getByLabelText("Answer style"), { target: { value: "deep_dive" } });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Explain Raft" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledWith("Explain Raft", "deep_dive");
  });
});
