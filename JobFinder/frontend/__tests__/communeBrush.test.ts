import type L from "leaflet";

import { attachBrushInteractions, type TouchTool } from "@/app/profile/_components/communeBrush";
import type { CommuneFeature } from "@/app/profile/_components/communeGeo";

// Square commune around the fixed latlng returned by the map mock — every
// stamp lands inside it, so a committed stroke always selects it.
function makeCommune(code: string): CommuneFeature {
  const ring = [
    [1, 45],
    [3, 45],
    [3, 47],
    [1, 47],
    [1, 45],
  ];
  return {
    code,
    nom: `Commune ${code}`,
    pop: 0,
    dept: "74",
    bbox: [1, 45, 3, 47],
    feature: {
      type: "Feature",
      properties: { code, nom: `Commune ${code}` },
      geometry: { type: "Polygon", coordinates: [ring] },
    } as CommuneFeature["feature"],
  };
}

// attachBrushInteractions only touches these members of L.Map.
function makeMapMock(container: HTMLElement) {
  return {
    getContainer: () => container,
    mouseEventToLatLng: () => ({ lat: 46, lng: 2 }),
    getZoom: () => 6,
    panBy: jest.fn(),
  };
}

// jsdom has no TouchEvent constructor — a plain Event carrying a `touches`
// array is enough for the handlers, which only read type and touches.
function touchEvent(type: string, touches: { clientX: number; clientY: number }[]): Event {
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.defineProperty(event, "touches", { value: touches });
  return event;
}

describe("attachBrushInteractions — touch gestures", () => {
  let container: HTMLDivElement;
  let mapMock: ReturnType<typeof makeMapMock>;
  let detach: () => void;
  let onChange: jest.Mock;
  let onPaintingChange: jest.Mock;
  let onStrokeStart: jest.Mock;
  let touchTool: TouchTool;

  beforeEach(() => {
    jest.useFakeTimers();
    touchTool = "paint";
    container = document.createElement("div");
    document.body.appendChild(container);
    mapMock = makeMapMock(container);
    onChange = jest.fn();
    onPaintingChange = jest.fn();
    onStrokeStart = jest.fn();
    detach = attachBrushInteractions(mapMock as unknown as L.Map, {
      getSelected: () => new Set<string>(),
      communes: new Map([["74001", makeCommune("74001")]]),
      getTouchTool: () => touchTool,
      onStrokeStart,
      onChange,
      onPaintingChange,
    });
  });

  afterEach(() => {
    detach();
    container.remove();
    jest.useRealTimers();
  });

  it("never paints when a second finger lands during the grace (pinch gesture)", () => {
    container.dispatchEvent(touchEvent("touchstart", [{ clientX: 10, clientY: 10 }]));
    container.dispatchEvent(
      touchEvent("touchstart", [
        { clientX: 10, clientY: 10 },
        { clientX: 60, clientY: 60 },
      ]),
    );
    jest.runAllTimers();
    container.dispatchEvent(touchEvent("touchend", []));

    expect(onChange).not.toHaveBeenCalled();
    expect(onStrokeStart).not.toHaveBeenCalled();
    expect(onPaintingChange).not.toHaveBeenCalledWith(true);
  });

  it("starts painting once the grace expires with a single finger down", () => {
    container.dispatchEvent(touchEvent("touchstart", [{ clientX: 10, clientY: 10 }]));
    // Nothing painted during the grace window.
    expect(onChange).not.toHaveBeenCalled();

    jest.runAllTimers();

    expect(onPaintingChange).toHaveBeenCalledWith(true);
    expect(onStrokeStart).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(["74001"]);
  });

  it("commits a quick tap on touchend, before the grace expires", () => {
    container.dispatchEvent(touchEvent("touchstart", [{ clientX: 10, clientY: 10 }]));
    container.dispatchEvent(touchEvent("touchend", []));

    expect(onChange).toHaveBeenCalledWith(["74001"]);
    expect(onPaintingChange).toHaveBeenLastCalledWith(false);
  });

  it("pan tool pans the map instead of painting", () => {
    touchTool = "pan";
    container.dispatchEvent(touchEvent("touchstart", [{ clientX: 30, clientY: 30 }]));
    container.dispatchEvent(touchEvent("touchmove", [{ clientX: 20, clientY: 25 }]));
    jest.runAllTimers();
    container.dispatchEvent(touchEvent("touchend", []));

    expect(mapMock.panBy).toHaveBeenCalledWith([10, 5], { animate: false });
    expect(onChange).not.toHaveBeenCalled();
  });
});
