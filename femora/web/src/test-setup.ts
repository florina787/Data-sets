import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach } from "vitest";
// Most tests start after onboarding; onboarding tests clear this flag themselves.
beforeEach(() => localStorage.setItem("femora:v1:onboarded", "true"));
afterEach(() => localStorage.clear());
