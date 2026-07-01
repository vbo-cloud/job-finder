import { renderHook, act } from "@testing-library/react";

jest.mock("@/lib/theme/index", () => ({
  applyTheme: jest.fn(),
}));

// Must import after jest.mock so the mocked version is used.
import { useTheme } from "@/lib/theme/useTheme";
import { applyTheme } from "@/lib/theme/index";

const mockedApplyTheme = applyTheme as jest.Mock;

beforeEach(() => {
  localStorage.clear();
  mockedApplyTheme.mockClear();
});

describe("useTheme", () => {
  it("initialises to dark theme by default", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.themeId).toBe("dark");
  });

  it("reads light theme from localStorage on mount", () => {
    localStorage.setItem("theme", "light");
    const { result } = renderHook(() => useTheme());
    // The useEffect runs after the initial render.
    expect(result.current.themeId).toBe("light");
    expect(mockedApplyTheme).toHaveBeenCalled();
  });

  it("toggle switches from dark to light and persists to localStorage", () => {
    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.toggle();
    });

    expect(result.current.themeId).toBe("light");
    expect(localStorage.getItem("theme")).toBe("light");
    expect(mockedApplyTheme).toHaveBeenCalled();
  });

  it("toggle switches from light to dark", () => {
    localStorage.setItem("theme", "light");
    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.toggle();
    });

    expect(result.current.themeId).toBe("dark");
    expect(localStorage.getItem("theme")).toBe("dark");
  });
});
