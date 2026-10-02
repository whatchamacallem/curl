const __NAME__ = (function () {
  "use strict";
  function deep_freeze(value) {
    if (value === null || typeof value !== "object") {
      return value;
    }
    Object.values(value).forEach(deep_freeze);
    return Object.freeze(value);
  }
  const values = deep_freeze(__DATA__);
  return function (name) {
    if (!Object.prototype.hasOwnProperty.call(values, name)) {
      throw new Error("no such setting: " + name);
    }
    return values[name];
  };
})();
