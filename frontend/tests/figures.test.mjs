/**
 * 阅读页 Figure 展示纯逻辑测试（node:test + 类型擦除）。
 *
 * 运行：npm --prefix frontend test
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  figureAnchorId,
  isYoloFigure,
  yoloFigures,
} from "../lib/figures.ts";

function figure(overrides = {}) {
  return {
    id: "f",
    paper_id: "p1",
    figure_number: 1,
    image_path: "p1/figures/page1_fig1.png",
    caption: null,
    bbox: null,
    type: "figure",
    page: 1,
    created_at: null,
    ...overrides,
  };
}

test("isYoloFigure distinguishes yolo crops from mineru images", () => {
  assert.equal(isYoloFigure(figure()), true);
  assert.equal(
    isYoloFigure(figure({ image_path: "p1/images/abc.jpg" })),
    false
  );
  assert.equal(isYoloFigure(figure({ image_path: "" })), false);
});

test("figureAnchorId builds a stable anchor", () => {
  assert.equal(figureAnchorId(3), "figure-3");
});

test("yoloFigures keeps only yolo crops sorted by figure_number", () => {
  const out = yoloFigures([
    figure({ id: "b", figure_number: 2, image_path: "p1/figures/page2_fig1.png", page: 2 }),
    figure({ id: "md", figure_number: 1, image_path: "p1/images/x.jpg", page: 1 }),
    figure({ id: "a", figure_number: 1, image_path: "p1/figures/page1_fig1.png", page: 1 }),
  ]);
  assert.deepEqual(out, [
    { id: "figure-1", number: 1, imagePath: "p1/figures/page1_fig1.png", page: 1 },
    { id: "figure-2", number: 2, imagePath: "p1/figures/page2_fig1.png", page: 2 },
  ]);
});

test("yoloFigures falls back to sequence when figure_number is null", () => {
  const out = yoloFigures([
    figure({ figure_number: null, page: null, image_path: "p1/figures/a.png" }),
    figure({ figure_number: null, page: 4, image_path: "p1/figures/b.png" }),
  ]);
  assert.deepEqual(
    out.map((f) => [f.id, f.number, f.page]),
    [
      ["figure-1", 1, null],
      ["figure-2", 2, 4],
    ]
  );
});

test("yoloFigures returns empty list when there is no detection", () => {
  assert.deepEqual(yoloFigures([]), []);
  assert.deepEqual(yoloFigures([figure({ image_path: "p1/images/x.jpg" })]), []);
});
