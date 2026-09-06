import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// jsdom does not implement canvas rendering. Chart.js exercises the 2D
// context heavily and warns loudly (and can misbehave) when getContext is
// missing. Provide a minimal 2D context stub whose `canvas` references the
// element it was acquired from, which Chart.js validates, so chart tests run
// cleanly.
const contextStub = (element: HTMLCanvasElement): unknown => {
  const noop = (): void => {};
  const ctx: Record<string, unknown> = {
    canvas: element,
    measureText: () => ({ width: 0 }),
    getLineDash: () => [],
    setLineDash: noop,
    beginPath: noop,
    closePath: noop,
    moveTo: noop,
    lineTo: noop,
    bezierCurveTo: noop,
    quadraticCurveTo: noop,
    arc: noop,
    arcTo: noop,
    ellipse: noop,
    rect: noop,
    fill: noop,
    stroke: noop,
    clip: noop,
    isPointInPath: () => false,
    isPointInStroke: () => false,
    fillText: noop,
    strokeText: noop,
    clearRect: noop,
    fillRect: noop,
    strokeRect: noop,
    createLinearGradient: () => ({ addColorStop: noop }),
    createRadialGradient: () => ({ addColorStop: noop }),
    createPattern: () => null,
    save: noop,
    restore: noop,
    translate: noop,
    rotate: noop,
    scale: noop,
    transform: noop,
    setTransform: noop,
    resetTransform: noop,
    drawImage: noop,
    getImageData: () => ({ data: [] }),
    putImageData: noop,
    createImageData: () => ({ data: [] }),
  };
  return ctx;
};

Object.defineProperty(HTMLCanvasElement.prototype, "getContext", {
  writable: true,
  configurable: true,
  value: vi.fn(function (this: HTMLCanvasElement): unknown {
    return contextStub(this);
  }),
});

// Chart.js attaches a ResizeObserver to the canvas's parent to drive its
// responsive platform. jsdom does not implement ResizeObserver, so provide a
// no-op stub to keep chart construction from throwing.
class ResizeObserverStub {
  constructor(_callback: ResizeObserverCallback) {}

  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

globalThis.ResizeObserver =
  ResizeObserverStub as unknown as typeof ResizeObserver;
