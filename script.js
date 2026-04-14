const treeRoot = document.getElementById("tree-root");
const detailsPanel = document.getElementById("details-panel");
const searchForm = document.getElementById("member-search-form");
const searchInput = document.getElementById("member-search-input");
const searchList = document.getElementById("member-search-list");
const searchStatus = document.getElementById("search-status");
const memberModal = document.getElementById("member-modal");
const memberModalClose = document.getElementById("member-modal-close");



let familyData = null;
let rootUnit = null;
let selectedMemberId = null;

const unitsById = new Map();
const memberIndex = new Map();
const expandedUnitIds = new Set();
let fitTreeFrame = 0;
let activeTreeLayout = "";

function normalizeText(value) {
  return (value || "").trim().toLowerCase();
}

function showLoadError(message) {
  treeRoot.innerHTML = `
    <div class="details-empty">
      <p>${message}</p>
    </div>
  `;

  detailsPanel.innerHTML = `
    <div class="details-empty">
      <p>Family tree data could not be loaded.</p>
    </div>
  `;

  updateSearchStatus("Data file could not be loaded.");
}

async function loadFamilyData() {
  if (window.familyTreeData) {
    return window.familyTreeData;
  }

  throw new Error("Family tree data (window.familyTreeData) is not loaded. Please ensure data/family-tree.from-html.js is included in index.html.");
}

function buildUnits(data) {
  unitsById.clear();
  memberIndex.clear();
  expandedUnitIds.clear();

  const peopleById = new Map(data.people.map((person) => [person.id, person]));

  data.families.forEach((family) => {
    const members = family.memberIds
      .map((memberId) => peopleById.get(memberId))
      .filter(Boolean)
      .map((person) => ({
        ...person,
        code: person.legacyCode || null
      }));

    unitsById.set(family.id, {
      id: family.id,
      parentId: null,
      code: family.legacyCode || null,
      label: family.label,
      sourceLabel: family.sourceLabel || family.label,
      generation: family.generation,
      childFamilyIds: family.childFamilyIds || [],
      members,
      children: []
    });
  });

  unitsById.forEach((unit) => {
    unit.childFamilyIds.forEach((childId) => {
      const child = unitsById.get(childId);
      if (!child) {
        return;
      }
      child.parentId = unit.id;
      unit.children.push(child);
    });
  });

  const rootFamilyId = data.meta.rootFamilyIds[0];
  rootUnit = unitsById.get(rootFamilyId) || Array.from(unitsById.values())[0] || null;
}

function getInitials(name) {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function createColorPair(name) {
  const palette = [
    ["#b96d3e", "#82421d"],
    ["#5d7d5f", "#37523a"],
    ["#7a6ab4", "#4d3f84"],
    ["#9d5c2f", "#6d3818"],
    ["#5b86a4", "#2f5f7b"],
    ["#a85d74", "#7b3550"]
  ];

  let hash = 0;
  for (const char of name) {
    hash = (hash * 31 + char.charCodeAt(0)) % palette.length;
  }

  return palette[Math.abs(hash) % palette.length];
}

function createAvatar(member) {
  const initials = getInitials(member.name);
  const [accentA, accentB] = createColorPair(member.name);
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 240" role="img" aria-label="${member.name}">
      <defs>
        <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="${accentA}" />
          <stop offset="100%" stop-color="${accentB}" />
        </linearGradient>
      </defs>
      <rect width="240" height="240" rx="40" fill="url(#grad)" />
      <circle cx="120" cy="90" r="44" fill="rgba(255,255,255,0.28)" />
      <path d="M50 202c14-36 42-54 70-54s56 18 70 54" fill="rgba(255,255,255,0.22)" />
      <text x="120" y="212" text-anchor="middle" font-family="Georgia, serif" font-size="52" font-weight="700" fill="white">${initials}</text>
    </svg>
  `;

  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

function createMemberImage(member, className) {
  const img = document.createElement("img");
  img.className = className;
  img.alt = member.name;
  img.src = member.photo || createAvatar(member);

  img.addEventListener("error", () => {
    img.src = createAvatar(member);
  });

  return img;
}

function createDetailRow(label, value) {
  if (!value) {
    return "";
  }

  return `
    <dl class="detail-line">
      <dt>${label}</dt>
      <dd>${value}</dd>
    </dl>
  `;
}

function indexMembers(unit, ancestors = []) {
  unit.members.forEach((member) => {
    memberIndex.set(member.id, {
      member,
      unit,
      ancestors
    });
  });

  unit.children.forEach((child) => {
    indexMembers(child, [...ancestors, unit.id]);
  });
}

function populateSearchList() {
  const options = Array.from(memberIndex.values())
    .map(({ member }) => member.name)
    .sort((a, b) => a.localeCompare(b));

  searchList.innerHTML = options
    .map((name) => `<option value="${name}"></option>`)
    .join("");
}

function updateSearchStatus(message) {
  searchStatus.textContent = message;
}

function scrollToUnit(unitId) {
  requestAnimationFrame(() => {
    const selectedNode = document.querySelector(`[data-unit-id="${unitId}"]`);

    if (selectedNode) {
      selectedNode.scrollIntoView({
        behavior: "smooth",
        block: "center",
        inline: "center"
      });
    }
  });
}

function getVisibleTreeDepth(unit, depth = 0) {
  if (!expandedUnitIds.has(unit.id) || unit.children.length === 0) {
    return depth;
  }

  return Math.max(...unit.children.map((child) => getVisibleTreeDepth(child, depth + 1)));
}

function fitTreeToViewport() {
  cancelAnimationFrame(fitTreeFrame);
  fitTreeFrame = requestAnimationFrame(() => {
    if (getTreeLayoutMode() !== "desktop") {
      return;
    }

    const shell = treeRoot.querySelector(".tree-fit-shell");
    const stage = treeRoot.querySelector(".tree-stage");

    if (!shell || !stage) {
      return;
    }

    shell.style.width = "";
    shell.style.height = "";
    stage.style.position = "";
    stage.style.left = "";
    stage.style.top = "";
    stage.style.transform = "";
    stage.style.transformOrigin = "";

    const availableWidth = Math.max(treeRoot.clientWidth - 16, 1);
    const contentWidth = stage.scrollWidth;
    const contentHeight = stage.scrollHeight;
    const visibleDepth = rootUnit ? getVisibleTreeDepth(rootUnit) : 0;
    const shouldFit = visibleDepth <= 1;
    const scale = shouldFit && contentWidth > availableWidth ? availableWidth / contentWidth : 1;

    shell.style.width = `${Math.ceil(contentWidth * scale)}px`;
    shell.style.height = `${Math.ceil(contentHeight * scale)}px`;
    stage.style.position = "absolute";
    stage.style.left = "0";
    stage.style.top = "0";
    stage.style.transform = `scale(${scale})`;
    stage.style.transformOrigin = "top left";
  });
}

function getTreeLayoutMode() {
  return window.matchMedia("(max-width: 720px)").matches ? "mobile" : "desktop";
}

function getBranchMeta(unit) {
  if (unit.children.length === 0) {
    return "Leaf branch";
  }

  return `${unit.children.length} child ${unit.children.length === 1 ? "branch" : "branches"}`;
}

function createThumbStack(unit) {
  const thumbStack = document.createElement("div");
  thumbStack.className = "member-thumb-stack";

  unit.members.slice(0, 2).forEach((member, index) => {
    const img = createMemberImage(
      member,
      `member-thumb ${index === 1 ? "is-secondary" : ""}`.trim()
    );
    thumbStack.appendChild(img);
  });

  return thumbStack;
}

function createMemberButton(member) {
  const button = document.createElement("button");
  button.className = `member-name ${member.id === selectedMemberId ? "is-active" : ""}`;
  button.type = "button";
  button.innerHTML = `
    <span>
      <span class="member-full-name">${member.name}</span>
      <span class="member-branch">${member.code || "Family member"}</span>
    </span>
  `;
  button.addEventListener("click", () => openMemberModal(member.id));
  return button;
}

function renderDetails(member) {
  const entry = memberIndex.get(member.id);
  const unit = entry.unit;
  detailsPanel.innerHTML = `
    <article class="details-card">
      <div class="detail-top">
        <div id="detail-photo-slot"></div>
        <div class="detail-copy">
          <h2 id="member-modal-title">${member.name}</h2>
          <p class="detail-role">${member.code || unit.code || unit.label || "Family member"}</p>
          <p class="detail-bio">
            Add this member's photo at <strong>${member.photo}</strong>. Until then,
            the site shows a generated placeholder.
          </p>
          <div class="detail-badge-row">
            <span class="detail-badge">${familyData.meta.source.split("/").pop()}</span>
            ${unit.code ? `<span class="detail-badge">${unit.code}</span>` : ""}
            <span class="detail-badge">${getBranchMeta(unit)}</span>
          </div>
        </div>
      </div>
      <div class="detail-grid">
        ${createDetailRow("Branch Label", unit.label)}
        ${createDetailRow("Original Source Label", unit.sourceLabel)}
        ${createDetailRow("Generation", `Generation ${unit.generation + 1}`)}
        ${createDetailRow("Photo File", member.photo)}
      </div>
      <div class="detail-related">
        <h3>Branch Members</h3>
        <div class="detail-related-list" id="related-members"></div>
      </div>
    </article>
  `;

  const photoSlot = document.getElementById("detail-photo-slot");
  photoSlot.appendChild(createMemberImage(member, "detail-photo"));

  const relatedMembers = document.getElementById("related-members");
  unit.members.forEach((relatedMember) => {
    const button = document.createElement("button");
    button.className = "detail-related-button";
    button.type = "button";
    button.textContent = relatedMember.name;

    button.addEventListener("click", () => {
      openMemberModal(relatedMember.id);
    });

    relatedMembers.appendChild(button);
  });
}

function openMemberModal(memberId) {
  const entry = memberIndex.get(memberId);

  if (!entry) {
    return;
  }

  selectedMemberId = memberId;
  renderTree();
  renderDetails(entry.member);
  memberModal.hidden = false;
}

function closeMemberModal() {
  memberModal.hidden = true;
}

function selectMember(memberId, options = {}) {
  const { scroll = false, openModal = false } = options;
  const entry = memberIndex.get(memberId);

  if (!entry) {
    return;
  }

  selectedMemberId = memberId;
  renderTree();

  if (scroll) {
    scrollToUnit(entry.unit.id);
  }

  if (openModal) {
    renderDetails(entry.member);
    memberModal.hidden = false;
  }
}

function expandPathToMember(memberId) {
  const entry = memberIndex.get(memberId);

  if (!entry) {
    return;
  }

  entry.ancestors.forEach((ancestorId) => expandedUnitIds.add(ancestorId));

  if (entry.unit.children.length > 0) {
    expandedUnitIds.add(entry.unit.id);
  }
}

function findMemberByQuery(query) {
  const normalizedQuery = normalizeText(query);

  if (!normalizedQuery) {
    return null;
  }

  const members = Array.from(memberIndex.values()).map(({ member }) => member);

  return (
    members.find((member) => normalizeText(member.name) === normalizedQuery) ||
    members.find((member) => normalizeText(member.name).includes(normalizedQuery)) ||
    null
  );
}

function handleSearch(event) {
  event.preventDefault();

  const query = searchInput.value.trim();

  if (!query) {
    updateSearchStatus("Type a name to jump to that branch.");
    return;
  }

  const matchedMember = findMemberByQuery(query);

  if (!matchedMember) {
    updateSearchStatus(`No family member found for "${query}".`);
    return;
  }

  expandPathToMember(matchedMember.id);
  selectMember(matchedMember.id, { scroll: true, openModal: true });
  updateSearchStatus(`Showing ${matchedMember.name}.`);
}

function createTreeCard(unit) {
  const isSelected = unit.members.some((member) => member.id === selectedMemberId);
  const card = document.createElement("div");
  card.className = `member-card ${isSelected ? "is-selected" : ""}`;

  const toggleButton = document.createElement("button");
  const hasChildren = unit.children.length > 0;
  const isExpanded = expandedUnitIds.has(unit.id);
  toggleButton.className = "toggle-branch";
  toggleButton.type = "button";
  toggleButton.setAttribute(
    "aria-label",
    hasChildren
      ? `${isExpanded ? "Collapse" : "Expand"} ${unit.label}'s branch`
      : "No children"
  );
  toggleButton.setAttribute("aria-expanded", hasChildren ? String(isExpanded) : "false");
  toggleButton.textContent = isExpanded ? "−" : "+";
  toggleButton.disabled = !hasChildren;

  if (hasChildren) {
    toggleButton.addEventListener("click", () => {
      if (expandedUnitIds.has(unit.id)) {
        expandedUnitIds.delete(unit.id);
      } else {
        expandedUnitIds.add(unit.id);
      }

      renderTree();
    });
  }

  const people = document.createElement("div");
  people.className = "member-people";

  unit.members.forEach((member) => {
    const button = createMemberButton(member);
    const metaLine = document.createElement("span");
    metaLine.className = "member-meta";
    metaLine.innerHTML = `<span class="branch-label">${member.code || unit.code || getBranchMeta(unit)}</span>`;
    button.querySelector("span").appendChild(metaLine);
    people.appendChild(button);
  });

  card.appendChild(toggleButton);
  card.appendChild(createThumbStack(unit));
  card.appendChild(people);
  return card;
}

function renderDesktopTreeNode(unit) {
  const node = document.createElement("li");
  node.className = "hierarchy-node";
  node.dataset.unitId = unit.id;
  node.appendChild(createTreeCard(unit));

  if (unit.children.length > 0 && expandedUnitIds.has(unit.id)) {
    const childrenContainer = document.createElement("ul");
    unit.children.forEach((child) => childrenContainer.appendChild(renderDesktopTreeNode(child)));
    node.appendChild(childrenContainer);
  }

  return node;
}

function renderMobileTreeNode(unit) {
  const item = document.createElement("li");
  item.className = "mobile-tree-item";
  item.dataset.unitId = unit.id;
  item.appendChild(createTreeCard(unit));

  if (unit.children.length > 0 && expandedUnitIds.has(unit.id)) {
    const childList = document.createElement("ul");
    childList.className = "mobile-tree-children";
    unit.children.forEach((child) => childList.appendChild(renderMobileTreeNode(child)));
    item.appendChild(childList);
  }

  return item;
}

function renderDesktopTree() {
  const shell = document.createElement("div");
  shell.className = "tree-fit-shell";

  const stage = document.createElement("div");
  stage.className = "tree-stage";

  const tree = document.createElement("ul");
  tree.className = "hierarchy-tree";
  tree.appendChild(renderDesktopTreeNode(rootUnit));
  stage.appendChild(tree);
  shell.appendChild(stage);

  treeRoot.replaceChildren(shell);
  fitTreeToViewport();
}

function renderMobileTree() {
  const tree = document.createElement("ul");
  tree.className = "mobile-tree";
  tree.appendChild(renderMobileTreeNode(rootUnit));
  treeRoot.replaceChildren(tree);
}

function renderTree() {
  const layoutMode = getTreeLayoutMode();
  activeTreeLayout = layoutMode;

  if (layoutMode === "mobile") {
    renderMobileTree();
    return;
  }

  renderDesktopTree();
}

function handleViewportChange() {
  const nextLayout = getTreeLayoutMode();

  if (nextLayout !== activeTreeLayout) {
    renderTree();
    return;
  }

  if (nextLayout === "desktop") {
    fitTreeToViewport();
  }
}

function initEvents() {
  searchForm.addEventListener("submit", handleSearch);

  memberModalClose.addEventListener("click", closeMemberModal);
  memberModal.addEventListener("click", (event) => {
    if (event.target === memberModal) {
      closeMemberModal();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !memberModal.hidden) {
      closeMemberModal();
    }
  });

  window.addEventListener("resize", handleViewportChange);
}

async function init() {
  try {
    familyData = await loadFamilyData();
    buildUnits(familyData);

    if (!rootUnit || rootUnit.members.length === 0) {
      throw new Error("Root family could not be resolved from JSON data.");
    }

    indexMembers(rootUnit);
    populateSearchList();
    selectedMemberId = rootUnit.members[0].id;
    expandedUnitIds.add(rootUnit.id);
    renderDetails(rootUnit.members[0]);
    renderTree();
    initEvents();
    updateSearchStatus("Type a name to jump to that branch.");
  } catch (error) {
    const isFileProtocol = window.location.protocol === "file:";
    const helpText = isFileProtocol
      ? 'Open this site through a local server such as "python3 -m http.server" so the browser can load JSON files.'
      : "Please check that the JSON file exists and is readable.";
    showLoadError(`${error.message} ${helpText}`);
    console.error(error);
  }
}

init();
