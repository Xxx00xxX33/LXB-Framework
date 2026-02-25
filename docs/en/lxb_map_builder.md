# LXB-MapBuilder

## 1. Scope
LXB-MapBuilder automatically builds app navigation maps through real device interaction, outputting pages, transitions, popups, and exception page information.

## 2. Architecture
Code directory: `src/auto_map_builder/`

```
src/auto_map_builder/
├── __init__.py
├── node_explorer.py        # Main engine: node-driven mapping (v5)
├── fusion_engine.py        # VLM-XML fusion engine
├── vlm_engine.py          # VLM API wrapper
├── models.py               # Data structure definitions
└── legacy/                 # Archived strategies (v1-v4)
```

### Module Relationships

```
LXB-Link (Device Interaction)
       │
       v
NodeMapBuilder
       │
       ├──> VLM Engine (Visual Analysis)
       │      └── Identify page types, interactive elements
       │
       └──> Fusion Engine
              └── VLM+XML node fusion
```

## 3. Core Flow

### 3.1 Map Building Process

```
1. Launch app → Home page analysis
   │
   v
2. VLM analyzes home page → Identify NAV nodes (navigation elements)
   │
   v
3. Iterate NAV nodes → Click → Analyze new page
   │
   v
4. Classify page type:
   - PAGE → Enqueue for exploration
   - NAV → Skip
   - POPUP → Record and close
   - BLOCK → Wait or retry
   │
   v
5. Path replay → Return from home to target page
   │
   v
6. Recursive exploration → Depth-first (DFS)
   │
   v
7. Generate map JSON → Save to file
```

### 3.2 VLM Page Classification

| Type | Description | Handling |
|------|-------------|----------|
| PAGE | Independent functional page with multiple interactive elements | Create page node, explore NAV nodes |
| NAV | Navigation element (tabs, menus, buttons) | Click to navigate to other pages |
| POPUP | Popup, ad overlay | Record locator and close |
| BLOCK | Loading, empty state | Wait or retry |
| NODE | Interactive element (button, input) | Bind XML, create locator |

## 4. VLM-XML Fusion Algorithm (Core Innovation)

### 4.1 Fusion Principle

```
VLM Detection (bbox + label)
        +
XML Node (bounds + resource_id)
        ↓
    IoU Calculation (Overlap)
        ↓
   Select Best Match
        ↓
  FusedNode (VLM Semantics + XML Attributes)
```

**Fusion Significance**:
- VLM provides semantic understanding (what is this button)
- XML provides precise positioning (resource_id, bounds)
- Combining both yields reliable automation locators

### 4.2 Mathematical Formulation

#### 4.2.1 IoU (Intersection over Union) Calculation

Given two bounding boxes:
- VLM detection box: $B_{vlm} = (x_1^{vlm}, y_1^{vlm}, x_2^{vlm}, y_2^{vlm})$
- XML node box: $B_{xml} = (x_1^{xml}, y_1^{xml}, x_2^{xml}, y_2^{xml})$

IoU is defined as:

$$
\text{IoU}(B_{vlm}, B_{xml}) = \frac{A(B_{vlm} \cap B_{xml})}{A(B_{vlm} \cup B_{xml})}
$$

Where:
- Intersection area:
  $$
  A(B_{vlm} \cap B_{xml}) = \max(0, \min(x_2^{vlm}, x_2^{xml}) - \max(x_1^{vlm}, x_1^{xml})) \\
  \times \max(0, \min(y_2^{vlm}, y_2^{xml}) - \max(y_1^{vlm}, y_1^{xml}))
  $$

- Union area:
  $$
  A(B_{vlm} \cup B_{xml}) = A(B_{vlm}) + A(B_{xml}) - A(B_{vlm} \cap B_{xml})
  $$

- Single box area:
  $$
  A(B) = (x_2 - x_1) \times (y_2 - y_1)
  $$

#### 4.2.2 Selection Function

Define selection function $f: \mathcal{B} \times \mathcal{B}^n \to \mathbb{N} \cup \{\bot\}$:

$$
f(B_{vlm}, \{B_{xml}^1, ..., B_{xml}^n\}) = \begin{cases}
i^* & \text{if } \exists i: \text{IoU}(B_{vlm}, B_{xml}^i) \geq \tau \land i^* = \arg\max_j \text{IoU}(B_{vlm}, B_{xml}^j) \\
\bot & \text{otherwise}
\end{cases}
$$

Where:
- $\tau$ is the IoU threshold (default $\tau = 0.3$)
- $i^*$ is the best-matching XML node index
- $\bot$ indicates no match (VLM detection is a false positive)

#### 4.2.3 Coordinate Normalization Linear Transformation

Given VLM normalized coordinates $(x', y') \in [0, 1000]^2$ and screen size $W \times H$:

$$
\begin{bmatrix} x \\ y \end{bmatrix} =
\begin{bmatrix} \frac{W}{1000} & 0 \\ 0 & \frac{H}{1000} \end{bmatrix}
\begin{bmatrix} x' \\ y' \end{bmatrix} =
\begin{bmatrix} x' \cdot \frac{W}{1000} \\ y' \cdot \frac{H}{1000} \end{bmatrix}
$$

Complete form:
$$
x_{pixel} = \left\lfloor \frac{x_{vlm} \times W_{screen}}{1000} \right\rceil
$$
$$
y_{pixel} = \left\lfloor \frac{y_{vlm} \times H_{screen}}{1000} \right\rceil
$$

### 4.3 Fusion Algorithm Pseudocode

```
Algorithm 1: VLM-XML Fusion
Input: VLM detections D_vlm = {d_1, ..., d_m}, XML nodes N_xml = {n_1, ..., n_n}
Output: Fused nodes F = {f_1, ..., f_k}

1:  F ← ∅
2:  U ← ∅              // Used XML node indices
3:
4:  for each detection d_i ∈ D_vlm do
5:      best_idx ← -1
6:      best_iou ← 0
7:
8:      for each node n_j ∈ N_xml do
9:          if j ∈ U then continue
10:
11:             iou ← IoU(d_i.bbox, n_j.bounds)
12:             if iou > best_iou and iou ≥ τ then
13:                 best_iou ← iou
14:                 best_idx ← j
15:             end if
16:         end for
17:
18:         if best_idx ≠ -1 then
19:             U ← U ∪ {best_idx}
20:             f ← CreateFusedNode(d_i, N_xml[best_idx], best_iou)
21:             F ← F ∪ {f}
22:         end if
23:     end for
24:
25:     return F
```

### 4.4 Prompt Design

**Objective**: Make VLM identify only core UI elements for page navigation, filtering out dynamic content

```python
_PROMPT_OD = """Analyze this mobile App screenshot, **ONLY identify core UI elements used for page navigation**.

**Must identify** (these are navigation anchors):
1. Top navigation bar: back button, title bar buttons, search entry, menu button
2. Bottom navigation bar: Home/Messages/Cart/Profile Tab buttons
3. Top Tab switching: category tabs like "Follow", "Recommend", "Hot"
4. Floating buttons: post button, customer service, back to top
5. Sidebar entry: drawer menu button

**Do NOT identify** (these are dynamic content, not navigation):
- Product cards, product images, prices, titles
- Any content in feeds (posts, articles, video thumbnails)
- Ad banners, promotions, coupons
- Each item in lists
- Search history, suggested keywords, hot search
- User avatars, usernames, comments
- Any dynamic content in scrollable areas

**Coordinate format**: Pixel coordinates [x1, y1, x2, y2]

Return JSON:
```json
{
  "elements": [
    {"label": "nav_button", "bbox": [20, 50, 80, 110], "text": "Back"},
    {"label": "tab", "bbox": [55, 180, 165, 241], "text": "Recommend"},
    {"label": "bottom_nav", "bbox": [100, 2700, 200, 2772], "text": "Home"}
  ]
}
```

Label types: nav_button, tab, bottom_nav, fab, search, menu, icon
Return JSON only, max 15 elements."""
```

## 5. Data Structures

### 5.1 NavigationMap (Output)

```json
{
  "package": "com.example.app",
  "pages": {
    "home": {"name": "Home", "target_aliases": ["main"]},
    "settings": {"name": "Settings", "features": ["Search Box"]}
  },
  "transitions": [
    {
      "from": "home",
      "to": "settings",
      "locator": {"text": "Settings", "resource_id": "..."}
    }
  ],
  "popups": [{"type": "ad", "close_locator": {...}}],
  "blocks": [{"type": "loading", "identifiers": [...]}]
}
```

### 5.2 Locator

```python
{
  "resource_id": "com.app:id/button",  # Precise ID
  "text": "Submit",                      # Auxiliary text
  "bounds_hint": [100, 200, 500, 250],   # Coordinate hint
  "class_name": "android.widget.Button"  # Class name
}
```

## 6. Design Principles

### 6.1 Node-Driven (v5)
- **Reason**: Hardcoded coordinates are not universal, fail on different devices/resolutions
- **Solution**: Use VLM for semantic understanding + XML for precise positioning

### 6.2 Retrieval-First Positioning
- **Reason**: Reduce dependency on coordinates
- **Solution**: Prioritize resource_id/text retrieval, coordinates as hint only

### 6.3 Exploration Limits
- `max_pages` - Prevent infinite exploration
- `max_depth` - Control exploration depth
- `max_time_seconds` - Timeout stop

## 7. Code Structure

| File | Responsibility | Key Classes/Functions |
|------|----------------|----------------------|
| `node_explorer.py` | Main mapping engine | `NodeMapBuilder.explore()` |
| `fusion_engine.py` | Fusion engine | `compute_iou()`, `fuse()` |
| `vlm_engine.py` | VLM wrapper | `_call_api()`, `_run_od()` |
| `models.py` | Data structures | `XMLNode`, `FusedNode`, `NavigationMap` |

## 8. Cross References
- `docs/en/lxb_link.md` - Device communication
- `docs/en/lxb_cortex.md` - Automation execution
