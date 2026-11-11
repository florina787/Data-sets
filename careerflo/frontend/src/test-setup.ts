import "@testing-library/jest-dom/vitest";

// jsdom has no ResizeObserver (used by Recharts' ResponsiveContainer).
class ResizeObserverStub { observe() {} unobserve() {} disconnect() {} }
(globalThis as any).ResizeObserver ??= ResizeObserverStub;
