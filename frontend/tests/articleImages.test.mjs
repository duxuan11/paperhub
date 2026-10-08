/**
 * 文章图片操作纯逻辑测试（node:test + 类型擦除）。
 *
 * 运行：npm --prefix frontend test
 */

import test from "node:test";
import assert from "node:assert/strict";

import {
  appendImage,
  insertImageAtCursor,
  moveImage,
  removeImage,
} from "../lib/articleImages.ts";

test("moveImage 换图不换位并返回新数组", () => {
  const images = ["a", "b", "c"];
  assert.deepEqual(moveImage(images, 0, 2), ["b", "c", "a"]);
  assert.deepEqual(moveImage(images, 2, 0), ["c", "a", "b"]);
  assert.deepEqual(images, ["a", "b", "c"]); // 入参不被修改
  assert.deepEqual(moveImage(images, 1, 1), ["a", "b", "c"]);
});

test("removeImage 删除独占一行的图片引用并重编号", () => {
  const content = [
    "# T",
    "",
    "![Figure 1]({{figure:0}})",
    "",
    "![Figure 2]({{figure:1}})",
    "",
    "![Figure 3]({{figure:2}})",
  ].join("\n");
  const { content: out, images } = removeImage(content, ["a", "b", "c"], 1);
  assert.deepEqual(images, ["a", "c"]);
  assert.ok(out.includes("![Figure 1]({{figure:0}})"));
  assert.ok(!out.includes("Figure 2")); // 被删项整行移除
  assert.ok(out.includes("![Figure 3]({{figure:1}})")); // 原 figure:2 前移
});

test("removeImage 删除内联占位符并重编号", () => {
  const { content: out, images } = removeImage(
    "看图 $x$ 和 {{figure:2}} 以及 {{figure:0}}",
    ["a", "b", "c"],
    1
  );
  assert.deepEqual(images, ["a", "c"]);
  assert.equal(out, "看图 $x$ 和 {{figure:1}} 以及 {{figure:0}}");
});

test("removeImage 删除图片行时只局部收敛前后的空行", () => {
  const content = ["A", "", "![Figure 1]({{figure:0}})", "", "B"].join("\n");
  const { content: out, images } = removeImage(content, ["a"], 0);
  assert.equal(out, "A\n\nB");
  assert.deepEqual(images, []);
});

test("removeImage 不触碰代码块内的连续空行", () => {
  const content = [
    "![Figure 1]({{figure:0}})",
    "```",
    "a",
    "",
    "",
    "b",
    "```",
    "",
    "B",
  ].join("\n");
  const { content: out } = removeImage(content, ["a"], 0);
  // 代码块内连续空行必须逐字节保留
  assert.equal(out, "```\na\n\n\nb\n```\n\nB");
});

test("removeImage 下标越界时原样返回", () => {
  const { content, images } = removeImage("x {{figure:0}}", ["a"], 5);
  assert.equal(content, "x {{figure:0}}");
  assert.deepEqual(images, ["a"]);
});

test("appendImage 追加并返回新下标", () => {
  assert.deepEqual(appendImage(["a"], "b"), { images: ["a", "b"], index: 1 });
});

test("insertImageAtCursor 在行中插入独立图片行", () => {
  const r = insertImageAtCursor("abc", 1, 1, 0, "Figure 1");
  assert.equal(r.content, "a\n![Figure 1]({{figure:0}})\nbc");
  assert.equal(r.cursor, "a\n![Figure 1]({{figure:0}})\n".length);
});

test("insertImageAtCursor 替换选区", () => {
  const r = insertImageAtCursor("abcdef", 1, 4, 2, "Figure 3");
  assert.equal(r.content, "a\n![Figure 3]({{figure:2}})\nef");
});

test("insertImageAtCursor 空正文开头", () => {
  const r = insertImageAtCursor("", 0, 0, 0, "F");
  assert.equal(r.content, "![F]({{figure:0}})\n");
  assert.equal(r.cursor, r.content.length);
});
