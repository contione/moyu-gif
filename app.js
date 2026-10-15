"use strict";

const byId = (id) => document.getElementById(id);
const STORAGE_KEY = "moyu-favorites-v1";
const COLORS = ["#f4f6ef", "#f2f5f8", "#fbf4eb", "#f4f1f8", "#f0f5f6", "#fcf1ef", "#faf5e9", "#f0f5ef"];
const ICONS = {
  heart: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 4.6a5.4 5.4 0 0 0-7.6 0L12 5.8l-1.2-1.2a5.4 5.4 0 0 0-7.6 7.6L12 21l8.8-8.8a5.4 5.4 0 0 0 0-7.6Z"/></svg>',
  copy: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M15 8V4H4v11h4"/></svg>',
  download: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m-4-4 4 4 4-4M5 16v5h14v-5"/></svg>',
};
let items = [];
let filteredItems = [];
let category = "全部";
let query = "";
let favorites = new Set();
let animated = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let currentItem = null;
let toastTimer;
let loaded = false;

try {
  const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
  if (Array.isArray(stored)) favorites = new Set(stored.filter((id) => typeof id === "string"));
} catch {
  favorites = new Set();
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function toast(message) {
  clearTimeout(toastTimer);
  byId("toast").textContent = message;
  byId("toast").classList.add("visible");
  toastTimer = setTimeout(() => byId("toast").classList.remove("visible"), 2600);
}

function imageUrl(item) {
  return animated ? item.file : item.poster;
}

function emojiUrl(item) {
  return item.id.startsWith("duck-office-") ? `assets/emojis/${item.id}.gif` : item.file;
}

function downloadLabel(item) {
  return item.id.startsWith("duck-office-") ? "下载 Emoji" : "下载 GIF";
}

function setFavoriteButton(button, item) {
  const selected = favorites.has(item.id);
  button.innerHTML = ICONS.heart;
  button.setAttribute("aria-pressed", String(selected));
  button.setAttribute("aria-label", `${selected ? "取消收藏" : "收藏"}：${item.title}`);
  button.title = selected ? "取消收藏" : "收藏这张";
}

function toggleFavorite(item) {
  if (favorites.has(item.id)) favorites.delete(item.id);
  else favorites.add(item.id);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...favorites]));
  } catch {
    toast("浏览器无法保存收藏；本次打开期间仍可使用。");
  }
  document.querySelectorAll(`[data-favorite="${item.id}"]`).forEach((button) => setFavoriteButton(button, item));
  if (currentItem?.id === item.id) setFavoriteButton(byId("preview-favorite"), item);
  if (category === "我的收藏") renderGallery();
  renderCategories();
}

async function copyLink(item) {
  const url = new URL(item.file, document.baseURI).href;
  try {
    await navigator.clipboard.writeText(url);
    toast("GIF 链接已复制，去群里快乐一下！");
  } catch {
    byId("copy-fallback").value = url;
    byId("copy-dialog").showModal();
    byId("copy-fallback").focus();
    byId("copy-fallback").select();
  }
}

function renderCategories() {
  const names = ["全部", ...new Set(items.map((item) => item.category)), "我的收藏"];
  const fragment = document.createDocumentFragment();
  names.forEach((name) => {
    const button = element("button", `category${name === "我的收藏" ? " favorite-category" : ""}`);
    button.setAttribute("aria-pressed", String(category === name));
    if (name === "我的收藏") button.innerHTML = ICONS.heart;
    button.append(document.createTextNode(name));
    if (name === "全部" || name === "我的收藏") {
      const count = name === "全部" ? items.length : items.filter((item) => favorites.has(item.id)).length;
      button.append(element("span", "category-count", String(count)));
    }
    button.addEventListener("click", () => {
      category = name;
      renderCategories();
      renderGallery();
      [...byId("categories").children].find((child) => child.getAttribute("aria-pressed") === "true")?.focus({ preventScroll: true });
    });
    fragment.append(button);
  });
  byId("categories").replaceChildren(fragment);
}

function makeCard(item) {
  const card = element("article", "card");
  card.dataset.id = item.id;
  card.style.setProperty("--card-bg", COLORS[items.indexOf(item) % COLORS.length]);
  const art = element("div", "card-art");
  const open = element("button", "card-open");
  open.setAttribute("aria-label", `预览：${item.title}`);
  const image = element("img");
  image.src = imageUrl(item);
  image.alt = item.title;
  image.width = 320;
  image.height = 320;
  image.loading = "lazy";
  image.decoding = "async";
  image.addEventListener("error", () => {
    if (!image.dataset.failed) {
      image.dataset.failed = "true";
      image.src = item.poster;
    }
  });
  open.append(image);
  open.addEventListener("click", () => openPreview(item));
  const favorite = element("button", "favorite-button");
  favorite.dataset.favorite = item.id;
  setFavoriteButton(favorite, item);
  favorite.addEventListener("click", () => toggleFavorite(item));
  art.append(open, favorite);
  const content = element("div", "card-content");
  const heading = element("div", "card-heading");
  heading.append(element("h2", "card-title", item.title), element("span", "card-category", item.category));
  const actions = element("div", "card-actions");
  const copy = element("button", "button dark");
  copy.innerHTML = ICONS.copy;
  copy.append(document.createTextNode("复制链接"));
  copy.setAttribute("aria-label", `复制链接：${item.title}`);
  copy.addEventListener("click", () => copyLink(item));
  const download = element("a", "button outline");
  download.innerHTML = ICONS.download;
  download.append(document.createTextNode(downloadLabel(item)));
  download.href = emojiUrl(item);
  download.download = `${item.id}.gif`;
  download.setAttribute("aria-label", `${downloadLabel(item)}：${item.title}`);
  actions.append(copy, download);
  content.append(heading, actions);
  card.append(art, content);
  return card;
}

function renderGallery() {
  const terms = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  filteredItems = items.filter((item) => {
    const matchesCategory = category === "全部" || (category === "我的收藏" ? favorites.has(item.id) : item.category === category);
    const searchable = `${item.title} ${item.category} ${item.tags.join(" ")}`.toLocaleLowerCase();
    return matchesCategory && terms.every((term) => searchable.includes(term));
  });
  byId("gallery").replaceChildren(...filteredItems.map(makeCard));
  byId("result-count").textContent = `共 ${filteredItems.length} 张表情`;
  byId("random-button").disabled = filteredItems.length === 0;
  byId("empty-state").hidden = filteredItems.length !== 0;
  byId("empty-title").textContent = category === "我的收藏" && !query ? "把常用的梗，收进口袋" : "暂时没有这款心情";
  byId("empty-message").textContent = category === "我的收藏" && !query ? "点击表情右上角的爱心，就能在这里找到它。" : "换个关键词试试，比如「下班」「吃瓜」「崩溃」。";
}

function previewCollection() {
  return filteredItems.some((item) => item.id === currentItem?.id) ? filteredItems : items;
}

function openPreview(item) {
  currentItem = item;
  byId("preview-image").src = imageUrl(item);
  byId("preview-image").alt = item.title;
  byId("preview-title").textContent = item.title;
  byId("preview-category").textContent = item.category;
  byId("preview-tags").textContent = item.tags.map((tag) => `#${tag}`).join("  ");
  byId("preview-download").href = emojiUrl(item);
  byId("preview-download").download = `${item.id}.gif`;
  byId("preview-download").textContent = downloadLabel(item);
  setFavoriteButton(byId("preview-favorite"), item);
  byId("preview-dialog").style.setProperty("--card-bg", COLORS[items.indexOf(item) % COLORS.length]);
  const collection = previewCollection();
  byId("preview-position").textContent = `${collection.indexOf(item) + 1} / ${collection.length}`;
  if (!byId("preview-dialog").open) byId("preview-dialog").showModal();
}

function movePreview(direction) {
  if (!currentItem) return;
  const collection = previewCollection();
  openPreview(collection[(collection.indexOf(currentItem) + direction + collection.length) % collection.length]);
}

function updateMotion() {
  byId("motion-button").setAttribute("aria-checked", String(animated));
  byId("motion-label").textContent = animated ? "动起来" : "静一静";
  document.querySelectorAll(".card").forEach((card) => {
    const item = items.find((entry) => entry.id === card.dataset.id);
    if (item) card.querySelector("img").src = imageUrl(item);
  });
  if (currentItem) byId("preview-image").src = imageUrl(currentItem);
}

byId("search").addEventListener("input", (event) => {
  query = event.target.value;
  if (loaded) renderGallery();
});
byId("motion-button").addEventListener("click", () => {
  animated = !animated;
  updateMotion();
});
byId("random-button").addEventListener("click", () => {
  if (filteredItems.length) openPreview(filteredItems[Math.floor(Math.random() * filteredItems.length)]);
});
byId("preview-copy").addEventListener("click", () => currentItem && copyLink(currentItem));
byId("preview-favorite").addEventListener("click", () => currentItem && toggleFavorite(currentItem));
byId("previous-button").addEventListener("click", () => movePreview(-1));
byId("next-button").addEventListener("click", () => movePreview(1));
byId("reset-button").addEventListener("click", () => {
  if (!loaded) return loadData();
  category = "全部";
  query = "";
  byId("search").value = "";
  renderCategories();
  renderGallery();
});
["help-button", "note-help"].forEach((id) => byId(id).addEventListener("click", () => byId("help-dialog").showModal()));
["preview", "help", "copy"].forEach((name) => {
  const dialog = byId(`${name}-dialog`);
  byId(`close-${name}`).addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    const bounds = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) dialog.close();
  });
});
document.addEventListener("keydown", (event) => {
  const editing = event.target instanceof HTMLElement && (event.target.matches("input,textarea") || event.target.isContentEditable);
  if (event.key === "/" && !editing && !document.querySelector("dialog[open]")) {
    event.preventDefault();
    byId("search").focus();
  }
  if (byId("preview-dialog").open && !byId("copy-dialog").open && !editing && ["ArrowLeft", "ArrowRight"].includes(event.key)) {
    event.preventDefault();
    movePreview(event.key === "ArrowLeft" ? -1 : 1);
  }
});

function validateData(data) {
  const ids = new Set();
  if (!Array.isArray(data) || !data.length) throw new Error("表情清单为空或格式错误");
  for (const item of data) {
    if (!item || !/^[a-z0-9-]+$/.test(item.id) || ids.has(item.id) || typeof item.title !== "string" || typeof item.category !== "string" || !Array.isArray(item.tags) || item.tags.some((tag) => typeof tag !== "string") || !/^assets\/gifs\/[a-z0-9-]+\.gif$/.test(item.file) || !/^assets\/posters\/[a-z0-9-]+\.(webp|png|jpg)$/.test(item.poster)) throw new Error("表情清单存在无效或重复条目");
    ids.add(item.id);
  }
  return data;
}

async function loadData() {
  byId("random-button").disabled = true;
  byId("result-count").textContent = "补给加载中…";
  byId("empty-state").hidden = true;
  try {
    const response = await fetch("data/gifs.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    items = validateData(await response.json());
    loaded = true;
    byId("reset-button").textContent = "看看全部表情";
    renderCategories();
    renderGallery();
  } catch (error) {
    loaded = false;
    byId("result-count").textContent = "加载失败";
    byId("empty-state").hidden = false;
    byId("empty-title").textContent = "补给车暂时迷路了";
    byId("empty-message").textContent = "请检查网络后重试。维护者请检查 data/gifs.json 是否存在且格式正确。";
    byId("reset-button").textContent = "重新加载";
    console.error("GIF library load failed:", error);
  }
}

updateMotion();
loadData();
