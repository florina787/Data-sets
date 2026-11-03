import "@testing-library/jest-dom/vitest";

class RO { observe() {} unobserve() {} disconnect() {} }
(globalThis as any).ResizeObserver = (globalThis as any).ResizeObserver ?? RO;
(globalThis as any).matchMedia = (globalThis as any).matchMedia ?? ((q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }));
(globalThis as any).URL.createObjectURL = () => "blob:mock";
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? (() => {});
(globalThis as any).__NO_PLOTLY__ = true;
