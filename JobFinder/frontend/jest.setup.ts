import "@testing-library/jest-dom";

// jsdom does not implement URL.createObjectURL / revokeObjectURL.
// CVCard uses these to display blob thumbnails.
global.URL.createObjectURL = jest.fn(() => "blob:test-url");
global.URL.revokeObjectURL = jest.fn();
