import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// jsdom does not implement canvas rendering. Chart.js exercises the 2D
// context heavily and warns loudly (and can misbehave) when getContext is
// missing. Provide a minimal 2D context stub so chart tests run cleanly.
const contextStub = (): unknown => {
  const noop = (): void => {};
  const ctx: Record<string, unknown> = {
    canvas: null,
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
  value: vi.fn(() => contextStub()),
});

