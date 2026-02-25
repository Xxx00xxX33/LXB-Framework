# LXB-Cortex

## 1. Scope
LXB-Cortex implements Route-Then-Act automation: route to target page first using navigation map, then execute task actions with VLM guidance.

## 2. Architecture
Code directory: `src/cortex/`

```
src/cortex/
├── __init__.py
├── fsm_runtime.py          # FSM state machine engine
├── route_then_act.py       # Route-Then-Act core logic
└── fsm_instruction.py      # Instruction parser
```

### Module Relationships

```
LXB-Link (Device Communication)
       │
       v
LXB-Cortex
   ├── Routing Phase   → Routing phase (deterministic navigation)
   └── Action Phase    → Execution phase (VLM guided)
```

## 3. Core Flow

### 3.1 Three-Phase Execution

```
┌─────────────────────────────────────────────────────────┐
│ Phase 1: Planning (Planning Phase)                       │
│                                                          │
│  APP_RESOLVE → Select target application                │
│  ROUTE_PLAN  → Plan target page                          │
└─────────────────────────────────────────────────────────┘
                         │
                         v
┌─────────────────────────────────────────────────────────┐
│ Phase 2: Routing (Routing Phase)                        │
│                                                          │
│  1. BFS path planning: Find shortest path from home     │
│     to target page in navigation map                    │
│  2. Route replay: Sequentially click nodes on path     │
│  3. Route recovery: Handle popups, missing nodes, etc.  │
└─────────────────────────────────────────────────────────┘
                         │
                         v
┌─────────────────────────────────────────────────────────┐
│ Phase 3: Action (Execution Phase)                       │
│                                                          │
│  FSM state machine loop (VISION_ACT):                    │
│    a. Screenshot → VLM analysis → Generate action       │
│    b. Execute action (TAP/SWIPE/INPUT/BACK)             │
│    c. Loop detection → Prevent repeated invalid actions │
│    d. DONE → Task complete                              │
└─────────────────────────────────────────────────────────┘
```

### 3.2 FSM State Machine

```
         ┌─────────┐
         │  INIT   │  Initialize, probe coordinate space
         └────┬────┘
              │
    ┌─────────┴─────────┐
    │   APP_RESOLVE     │  LLM selects app
    │   ROUTE_PLAN       │  LLM plans page
    └───┬───────────────┬─┘
       │               │
       │               └──> ROUTING
       │
       └──> ROUTING      Route to target page
              │
              v
         VISION_ACT      Vision execution (loop)
              │
         ┌──┴──┐
         │DONE │  Success
         └────┘
```

## 4. Coordinate Space Calibration

### 4.1 Problem Background

**Problem**: VLM output coordinates are in model's internal coordinate system, not matching device screen pixels

Example:
- VLM may return [0, 0, 1000, 1000] (normalized coordinates)
- Device screen is [0, 0, 1080, 2400] (pixel coordinates)
- Different VLM models have different coordinate ranges (some use 0-1000, some use 0-1)

### 4.2 Calibration Image Design

**Solution**: Send calibration image (four corner colored markers) → VLM recognizes → Calculate mapping range → Runtime mapping

Calibration image format:
- Black background (RGB: 0, 0, 0)
- Four corner L-shaped colored markers (200×200 pixels)
  - Top-left: RED (255, 0, 0)
  - Top-right: GREEN (0, 255, 0)
  - Bottom-right: BLUE (0, 0, 255)
  - Bottom-left: YELLOW (255, 255, 0)

### 4.3 Mathematical Model

#### 4.3.1 Linear Scaling Model

Uses simple linear transformation (non-Homography):

$$
P_{device} = M \times P_{vlm}
$$

Where:
- $P_{device} = (x_{screen}, y_{screen})^T$ is screen pixel coordinate
- $P_{vlm} = (x_{vlm}, y_{vlm})^T$ is VLM output coordinate
- $M = \begin{bmatrix} s_x & 0 \\ 0 & s_y \end{bmatrix}$ is diagonal scaling matrix

Scaling factors:
$$
s_x = \frac{W_{screen} - 1}{\max_x}, \quad s_y = \frac{H_{screen} - 1}{\max_y}
$$

Complete mapping formula:
$$
x_{screen} = \left\lfloor \frac{x_{vlm}}{\max_x} \times (W_{screen} - 1) \right\rceil
$$
$$
y_{screen} = \left\lfloor \frac{y_{vlm}}{\max_y} \times (H_{screen} - 1) \right\rceil
$$

#### 4.3.2 Calibration Process

**Step 1**: VLM recognizes four corner marker positions

Send calibration image, VLM returns:
$$
C_{tl} = (x_{tl}, y_{tl}), \quad C_{tr} = (x_{tr}, y_{tr})
$$
$$
C_{br} = (x_{br}, y_{br}), \quad C_{bl} = (x_{bl}, y_{bl})
$$

**Step 2**: Calculate VLM coordinate range

$$
\max_x = \max(x_{tl}, x_{tr}, x_{br}, x_{bl})
$$
$$
\max_y = \max(y_{tl}, y_{tr}, y_{br}, y_{bl})
$$

**Step 3**: Runtime coordinate mapping

```python
def map_coordinates(raw_x, raw_y, max_x, max_y, screen_w, screen_h):
    """
    Map VLM coordinates to screen coordinates using linear scaling

    Args:
        raw_x, raw_y: VLM output coordinates
        max_x, max_y: Calibrated VLM coordinate range
        screen_w, screen_h: Screen dimensions

    Returns:
        (screen_x, screen_y): Screen pixel coordinates
    """
    # Linear mapping
    screen_x = int(round((raw_x / max_x) * (screen_w - 1)))
    screen_y = int(round((raw_y / max_y) * (screen_h - 1)))

    return screen_x, screen_y
```

## 5. FSM Formal Definition

### 5.1 Quintuple Definition

Define finite state machine $M = (S, \Sigma, \delta, s_0, F)$:

- **State set** $S = \{s_{init}, s_{app\_resolve}, s_{route\_plan}, s_{routing}, s_{vision\_act}, s_{done}, s_{fail}\}$
- **Input alphabet** $\Sigma = \{\text{CMD}, \text{RESPONSE}, \text{TIMEOUT}, \text{ERROR}, \text{DONE}, \text{FAIL}\}$
- **Transition function** $\delta: S \times \Sigma \to S$
- **Initial state** $s_0 = s_{init}$
- **Accepting states** $F = \{s_{done}\}$

### 5.2 State Transition Table

| Current State | Input Event | Next State | Action |
|---------------|-------------|------------|--------|
| INIT | Device ready | APP_RESOLVE | Start LLM planning |
| APP_RESOLVE | APP selected | ROUTE_PLAN | Plan target page |
| ROUTE_PLAN | Path determined | ROUTING | Start routing |
| ROUTING | Route success | VISION_ACT | Start execution |
| ROUTING | Route failure × N | FAIL | Routing failed |
| VISION_ACT | DONE | DONE | Task complete |
| VISION_ACT | Timeout × N | FAIL | Execution timeout |
| VISION_ACT | Other | VISION_ACT | Continue loop |

### 5.3 VISION_ACT Loop Detection

Define loop condition:
$$
\text{LoopDetected} = (c_{same} \geq 3) \land (a_{stable} \geq 3)
$$

Where:
- $c_{same}$: Consecutive identical command execution count
- $a_{stable}$: Activity unchange count

## 6. BFS Path Planning

### 6.1 Graph Model Definition

Define navigation graph $G = (V, E)$:
- **Vertex set** $V$: All pages in the app (page_id)
- **Edge set** $E$: Transition relationships between pages
- **Edge weights**: Each edge associated with a locator $locator(e)$

### 6.2 BFS Algorithm

```
Algorithm 2: BFS Path Finding for Route-Then-Act
Input: Graph G = (V, E), start vertex s, target vertex t
Output: Shortest path P = [v_0, v_1, ..., v_k] where v_0 = s, v_k = t

1:  if s = t then return [s]
2:
3:  queue ← [(s, [s])]     // (current_vertex, path_so_far)
4:  visited ← {s}
5:
6:  while queue is not empty do
7:      (v, path) ← queue.dequeue()
8:
9:      for each edge e ∈ out_edges(v) do
10:         u ← e.to
11:
12:         if u = t then
13:             return path + [u]
14:         end if
15:
16:         if u ∉ visited then
17:             visited ← visited ∪ {u}
18:             queue.enqueue((u, path + [u]))
19:         end if
20:     end for
21: end while
22:
23:  return ⊥  // No path found
```

### 6.3 Cycle Handling

**Problem**: Graph may contain cycles (A → B → A)

**Solution**:
1. `visited` set tracks visited vertices
2. Only enqueue unvisited vertices
3. Ensures each vertex is visited at most once

## 7. Design Principles

### 7.1 Routing Phase Determinism
- Use BFS algorithm to ensure shortest path is found
- Position based on XML hierarchy, not hardcoded coordinates
- Path is reproducible and verifiable

### 7.2 Action Phase Reflection Mechanism
- LLM outputs structured analysis each turn (step_review, reflection)
- Collect lessons (insights) to feed back to subsequent turns
- Prevent repeated invalid actions (loop detection)

### 7.3 Separation of Concerns
- Routing handles reaching target page (deterministic)
- Action handles executing specific tasks (VLM guided)
- Failure recovery decoupled from main flow

## 8. Code Structure

| File | Responsibility | Key Classes/Functions |
|------|----------------|----------------------|
| `fsm_runtime.py` | FSM engine | `CortexFSMEngine`, `_run_vision_state`, `_probe_coordinate_space` |
| `route_then_act.py` | Routing core | `RouteThenActCortex`, `_bfs_path`, `_execute_route` |
| `fsm_instruction.py` | Instruction parser | `parse_instructions`, `validate_allowed` |

## 9. Cross References
- `docs/en/lxb_map_builder.md` - Map building
- `docs/en/lxb_link.md` - Device communication
