(function () {
  function bootstrapPayload() {
    return window.__PHEMACAST_MAP_PHEMAR_BOOTSTRAP__ || window.__PHEMACAST_PERSONAL_AGENT_BOOTSTRAP__ || {};
  }

  function rawShapeId(shapeId) {
    return String(shapeId || "").trim().toLowerCase();
  }

  function isMapPhemarMode() {
    return rawShapeId(bootstrapPayload()?.meta?.app_mode) === "map_phemar";
  }

  function normalizeShapeId(shapeId) {
    const normalized = rawShapeId(shapeId);
    if (isMapPhemarMode() && normalized === "diamond") {
      return "branch";
    }
    return normalized;
  }

  const shared = {
    isMapPhemarMode,
    normalizeShapeId,
    filterShapePresets(presets) {
      const list = Array.isArray(presets) ? presets.map((entry) => ({ ...entry })) : [];
      return list.filter((entry) => {
        const shapeId = rawShapeId(entry && entry.id);
        return shapeId === "rectangle" || shapeId === "branch";
      });
    },
    getShapePresetOverrides() {
      return {
        branch: { w: 18, h: 18 },
      };
    },
    usesSquareFootprint(shapeId) {
      const normalized = normalizeShapeId(shapeId);
      return normalized === "branch" || (!isMapPhemarMode() && normalized === "diamond");
    },
    getNodeFootprintStyle(node) {
      if (!shared.usesSquareFootprint(node && node.type)) {
        return null;
      }
      const width = Number(node && node.w) || 0;
      const height = Number(node && node.h) || 0;
      const size = Math.max(width, height, 10);
      return { w: size, h: size };
    },
    constrainResize(shapeId, width, height) {
      if (!shared.usesSquareFootprint(shapeId)) {
        return null;
      }
      const size = Math.max(Number(width) || 0, Number(height) || 0, 10);
      return { w: size, h: size };
    },
  };

  window.__PHEMACAST_MAP_PHEMAR_SHARED__ = shared;
})();
