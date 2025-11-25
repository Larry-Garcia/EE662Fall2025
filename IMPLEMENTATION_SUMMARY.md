# Wireless Sensor Network - Complete Implementation Summary

## Overview
This implementation extends the existing cluster-tree WSN simulation with comprehensive features including multi-hop neighbor discovery, mesh routing, energy modeling, failure recovery, TX power optimization, packet loss simulation, and extensive metrics tracking.

## Implemented Features

### Core Routing & Discovery (Items 1-3)

### 1. Multi-hop Neighbor Discovery & Neighbor Table Sharing

#### New Data Structures
- **`mesh_table`**: Multi-hop neighbor table in each SensorNode
  - Key: target node GUI (int)
  - Value: {next_hop_gui, hops, addr, role}
  - Built via neighbor table sharing in heartbeat messages

#### Neighbor Table Sharing Mechanism
- **Heartbeat Enhancement**: Each HEART_BEAT packet now includes:
  - `mesh_table` field containing neighbor info up to `NEIGHBOR_TABLE_MAX_HOPS`
  - Compact export format with GUI, hops, addr, role

- **Table Merging**: `update_mesh_table_from_neighbor()` method:
  - Processes advertised mesh tables from neighbors
  - Selects shortest-hop paths
  - Maintains 1-hop neighbors from direct heartbeats
  - Called for every HEART_BEAT packet across all roles

#### Configuration
- `NEIGHBOR_TABLE_MAX_HOPS = 2`: Maximum hops for neighbor table sharing
- `MAX_MESH_ROUTE_HOPS = 4`: Maximum hops for mesh routing attempts

---

### 2. Cluster-Tree Routing Support

#### Tree Routing Helper
- **`tree_route_next_hop(pck)`**: Extracted tree routing logic
  - Routes upward to parent cluster head by default
  - Routes downward to child cluster heads when destination is in subtree
  - Routes locally when destination is in same cluster
  - Uses existing `child_networks_table` and `members_table`

#### Preserved Behavior
- All existing cluster-tree structures remain functional
- Network updates, cluster head assignment unchanged
- Tree routing serves as reliable fallback

---

### 3. Hybrid Routing: Mesh First, Then Tree

#### Routing Strategy (`route_and_forward_package()`)
1. **Mesh Routing First**:
   - Checks `mesh_table` for destination GUI
   - Uses if path exists within `MAX_MESH_ROUTE_HOPS`
   - Leverages multi-hop neighbor discovery

2. **Tree Fallback**:
   - Falls back to `tree_route_next_hop()` if mesh fails
   - Ensures reliable delivery via cluster hierarchy

3. **Drop Handling**:
   - Silently drops if no route found (logging disabled by default)

#### Generic DATA Packet Routing
- All nodes can route DATA packets based on `dest_gui`
- Added routing check at top of `on_receive()`:
  ```python
  if pck.get('type') in ('DATA', 'SENSOR') and pck.get('dest_gui') is not None:
      if pck['dest_gui'] != self.id:
          self.route_and_forward_package(pck)
          return
  ```

---

### 4. Packet Tracking & Logging

#### Automatic Packet Timestamping (in `Node.send()`)
Every packet automatically receives:
- **`pkt_id`**: Unique sequential packet ID
- **`creation_time`**: Simulation time when packet first sent
- **`path`**: List of node GUIs traversed
- **`source_gui`**: Originating node GUI

#### Packet Delivery Logging
- **`maybe_log_packet_delivery(pck)`**: Called at start of `on_receive()`
  - Detects final destination by `dest_gui` or `dest` address
  - Records: pkt_id, type, source/dest GUIs, timestamps, delay, path
  - Appends to `sim.packet_log`

#### Simulator Extensions
Added to `Simulator.__init__()`:
- `packet_seq = 0`: Global packet ID counter
- `packet_log = []`: Delivery records
- `join_times = []`: Per-node join duration tracking

---

### 5. Join Time Tracking

#### Implementation
- **Start**: `join_start_time` set in `TIMER_ARRIVAL` handler
- **Complete**: `join_complete_time` set in `JOIN_REPLY` handler
- **Recording**: Join duration appended to `sim.join_times`

#### Attributes Added
- `self.join_start_time`: When node wakes up
- `self.join_complete_time`: When node becomes REGISTERED/CLUSTER_HEAD

---

### 6. Random Data Packet Generation

#### TIMER_DATA Handler
- Activated when nodes become REGISTERED or CLUSTER_HEAD
- **Behavior**:
  - Picks random eligible destination (REGISTERED/CLUSTER_HEAD/ROOT)
  - Creates DATA packet with `dest`, `dest_gui`, `type`, `source`
  - Calls `route_and_forward_package()`
  - Reschedules timer (50 + node_id % 50 sim seconds)

#### Configuration
- `ENABLE_DATA_PACKETS = True`: Toggle data packet generation

---

### 7. Final Statistics Output

#### Terminal Summary (after `sim.run()`)
```
============================================================
Simulation Finished
============================================================

--- Network Statistics ---
Join Times: X nodes joined
  Average: X.XXXX sim seconds
  Min: X.XXXX sim seconds
  Max: X.XXXX sim seconds

Packet Delivery: X packets delivered
  Average delay: X.XXXX sim seconds
  Min delay: X.XXXX sim seconds
  Max delay: X.XXXX sim seconds
  By type: {'DATA': X, 'SENSOR': X, ...}

  Sample paths (first 5 DATA packets):
    Packet 123: 5 -> 12 -> 3 -> 17 (delay: X.XXXX)
    ...

--- Final Role Distribution ---
  ROOT: 1
  CLUSTER_HEAD: X
  REGISTERED: X
  ...
============================================================
```

---

## Key Files Modified

### 1. `source/config.py`
- Added routing parameters: `NEIGHBOR_TABLE_MAX_HOPS`, `MAX_MESH_ROUTE_HOPS`, `ENABLE_DATA_PACKETS`

### 2. `source/wsnlab.py`
- **Simulator**: Added `packet_seq`, `packet_log`, `join_times`
- **Node.send()**: Auto-stamps packets with ID, timestamp, path

### 3. `wsnlab/data_collection_tree.py`
- **SensorNode.init()**: Added `mesh_table`, join time tracking
- **New Methods**:
  - `update_mesh_table_from_neighbor(pck)`
  - `tree_route_next_hop(pck)`
  - `maybe_log_packet_delivery(pck)`
- **Modified Methods**:
  - `send_heart_beat()`: Shares mesh table
  - `update_neighbor(pck)`: Maintains 1-hop mesh entries
  - `route_and_forward_package(pck)`: Mesh-first routing
  - `on_receive(pck)`: Packet logging, mesh updates, DATA routing
  - `on_timer_fired()`: Join time tracking, TIMER_DATA handler
- **Configuration**: Disabled verbose logging by default (`node.logging = False`)
- **Statistics**: Comprehensive end-of-simulation summary

---

## Testing & Verification

### Expected Behaviors
1. **Mesh Table Building**: Nodes should learn about 2-hop neighbors via heartbeat sharing
2. **Hybrid Routing**: DATA packets should prefer mesh routes within 4 hops, fall back to tree
3. **Path Tracing**: Packet logs should show actual traversal paths
4. **Join Time**: Average join time should be printed (typically < 50 sim seconds)
5. **Packet Delivery**: DATA packets should be delivered and logged with delays

### CSV Outputs (unchanged)
- `node_distances.csv`: Pairwise node distances
- `node_distance_matrix.csv`: Distance matrix
- `clusterhead_distances.csv`: CH-to-CH distances
- `neighbor_distances.csv`: Neighbor table exports

---

## Configuration Tuning

### For More Mesh Routing
- Increase `NEIGHBOR_TABLE_MAX_HOPS` (e.g., to 3 or 4)
- Increase `MAX_MESH_ROUTE_HOPS` (e.g., to 5 or 6)

### For Less Terminal Output
- Keep `node.logging = False` (default)
- Statistics summary appears only at end

### To Disable Data Packets
- Set `ENABLE_DATA_PACKETS = False` in config.py

---

## Implementation Notes

### Backward Compatibility
- All existing cluster-tree behaviors preserved
- Control packets (PROBE, JOIN_REQUEST, etc.) use tree routing
- Only DATA/SENSOR packets with `dest_gui` use mesh routing

### Performance
- Heartbeat packets slightly larger (mesh_table field)
- No significant computational overhead
- Mesh table updates on every heartbeat reception

### Edge Cases Handled
- Nodes without `dest_gui` fall back to tree routing
- Missing routes silently drop packets (no spam)
- Mesh table reset when node becomes UNREGISTERED

---

## Example Usage

Run the simulation:
```bash
python data_collection_tree.py
```

Expected output will show network formation, then final statistics including:
- Average join time for all nodes
- Packet delivery statistics (count, delays)
- Sample packet paths showing mesh/tree routing
- Final role distribution

---

---

## Advanced Features (Items 4-8)

### 4. TX Power Optimization

#### Dynamic TX Power Assignment
- **Cluster Heads & Root**: Automatically select minimum TX power to cover farthest relevant neighbor
- **Routers**: Always use highest TX power to bridge clusters
- **Leaf Nodes**: Use default TX power (inherit from CH on join)

#### Power Propagation
- CH advertises its TX power level in `JOIN_REPLY` packets
- Joining nodes adopt the CH's TX power level
- All nodes in a cluster use the same TX power level

#### Configuration
- `NODE_TX_RANGES = {0: 60, 1: 100, 2: 140}`: TX ranges for each power level
- `TX_POWER_LEVELS = [0, 1, 2]`: Available power levels
- `ALLOW_TX_POWER_CHOICE = True`: Enable dynamic power selection
- `NODE_DEFAULT_TX_POWER = 1`: Default power level

#### Visualization
- CLUSTER_HEADs show blue dashed TX range circles
- ROOT shows cyan dashed TX range circle
- TX range circles removed when nodes die

---

### 5. Packet Loss Model

#### Implementation
- **Location**: `wsnlab_vis.py` - `Node.send()` method
- **Mechanism**: Random packet drop before transmission
- **Formula**: `if random.random() < PACKET_LOSS_RATIO: return`
- **Scope**: Affects ALL packet types (control and data)

#### Configuration
- `PACKET_LOSS_RATIO = 0.05`: 5% packet loss (configurable 0.0-1.0)

#### Statistics Tracking
- Counts total TX attempts (`total_tx_attempts`)
- Counts dropped packets (`total_tx_dropped`)
- Calculates realized loss percentage
- Exports to `packet_loss_stats.csv` for graph generation

---

### 6. Node Failure & Recovery

#### Failure Mechanism
- **Scheduled Failure**: Random nodes killed at `FAILURE_TIME`
- **Configurable**: `NUM_NODES_TO_KILL` (default: 1, can be multiple)
- **Recovery**: Nodes recover at `RECOVERY_TIME`
- **Visual**: Killed nodes turn gray (0.3, 0.3, 0.3)

#### Recovery Process
- Recovered nodes become `UNREGISTERED` (yellow)
- Automatically rejoin network via `JOIN_REQUEST`
- Network self-heals by finding new parents

#### Energy Death
- Nodes die when energy drops below `MIN_ENERGY_J`
- Visual: Dark gray (0.2, 0.2, 0.2) to distinguish from killed nodes
- Network reorganization: Children automatically disconnected and rejoin

#### Metrics
- **Time to Recover**: Duration from recovery start until all orphans rejoin
- **Max Orphan Count**: Maximum number of orphaned nodes during recovery
- **Logging**: All events logged to `failures.csv`

#### Configuration
- `FAILURE_TIME = 500`: Time to kill node(s)
- `RECOVERY_TIME = 550`: Time to recover node(s)
- `NUM_NODES_TO_KILL = 3`: Number of nodes to kill simultaneously

---

### 7. Energy Model (CC2420)

#### CC2420 Radio Model
- **Voltage**: 3.0V
- **Data Rate**: 250 kbps (IEEE 802.15.4)
- **TX Currents**: 
  - Level 0 (low): 9.9 mA
  - Level 1 (med): 11.0 mA
  - Level 2 (high): 17.4 mA
- **RX Current**: 18.8 mA

#### Energy Consumption Formula
- **TX Energy**: `E = V × I × 8×(N+6) / R + overhead`
  - N = packet payload bytes (default: 50)
  - Overhead: 10 μJ (PLL/turnaround)
- **RX Energy**: Same formula with RX current
- **Per-Packet**: Energy consumed on every TX and RX operation

#### Node Death
- Nodes die when `power <= MIN_ENERGY_J`
- Root node protected: Cannot die from energy depletion
- Network reorganization: Children automatically rejoin

#### Energy Tracking
- Per-node metrics: TX energy, RX energy, packet counts
- Role-based statistics: Average energy consumption by role
- Network lifetime: Time until death threshold reached

#### Configuration
- `INITIAL_ENERGY_J = 2.1`: Starting energy per node
- `MIN_ENERGY_J = 1.8`: Death threshold
- `ENERGY_PSDU_BYTES = 50`: Packet size for energy calculation
- `NETWORK_DEATH_THRESHOLD = 0.5`: 50% nodes dead = network death

---

### 8. Network Topology Constraints

#### Leaf Node Constraint
- **REGISTERED/UNREGISTERED nodes cannot attach to ROUTERs**
- Must join CLUSTER_HEAD or ROOT only
- Enforced in:
  - `update_neighbor()`: Filters out routers from candidate parents
  - `select_and_join()`: Skips routers when selecting parent
  - `on_receive()`: Rejects JOIN_REPLY from routers

#### Router Constraint
- **ROUTERs cannot attach to other ROUTERs**
- Must connect to CLUSTER_HEAD or ROOT
- Enforced in:
  - `update_neighbor()`: Routers ignore router neighbors as parents
  - `become_router()`: Disconnects all REGISTERED children

#### Network Reorganization
- When CH/ROUTER dies: Children automatically become UNREGISTERED
- When invalid link detected: Node disconnects and rejoins
- Ensures topology always maintains: Leaf → CH/ROOT → Router → CH/ROOT

---

## Metrics & Logging

### CSV Exports

1. **`registration_log.csv`**: Node registration times
   - Columns: node_id, start_time, registered_time, delta_time

2. **`role_changes.csv`**: All role transitions
   - Columns: time, node_id, old_role, new_role

3. **`packet_log.csv`**: Packet delivery records
   - Columns: packet_id, type, source, dest, timestamps, delay, path

4. **`energy_metrics.csv`**: Per-node energy consumption
   - Columns: node_id, role, initial/final energy, TX/RX energy, packet counts, averages

5. **`failures.csv`**: Failure and recovery events
   - Columns: time, node_id, event_type, orphan_count

6. **`packet_loss_stats.csv`**: Packet loss statistics
   - Columns: configured_loss_pct, realized_loss_pct, attempts, dropped

7. **`topology.csv`**: Final network topology
8. **`neighbor_distances.csv`**: Neighbor relationships
9. **`clusterhead_distances.csv`**: CH-to-CH distances

### Graph Generation

**Script**: `generate_graphs.py`

Generates 5 publication-ready graphs:
1. **Join Times**: Histogram and CDF of node join times
2. **Packet Delay**: Distribution and delay vs hop count
3. **Failure & Recovery**: Orphan count over time with event markers
4. **Energy Consumption**: Energy by role, TX/RX breakdown, energy per packet, cumulative deaths
5. **Packet Loss**: Configured vs realized loss comparison

---

## Final Statistics Output

### Terminal Summary (after `sim.run()`)
```
============================================================
Simulation Finished
============================================================

--- Network Statistics ---
Join Times: X nodes joined
  Average: X.XXXX sim seconds
  Min: X.XXXX sim seconds
  Max: X.XXXX sim seconds

Packet Delivery: X packets delivered
  Average delay: X.XXXX sim seconds
  Min delay: X.XXXX sim seconds
  Max delay: X.XXXX sim seconds
  By type: {'DATA': X, 'SENSOR': X, ...}

--- Packet Loss Statistics ---
  TX attempts: XXXX
  Dropped by channel: XXX
  Realized loss: X.XX% (configured: X.XX%)

--- Failure Recovery Statistics ---
  Time to Recover: X.XX sim seconds
  Max Orphan Count: X

--- Network Lifetime (Maximize Network Life) ---
⏱️  NETWORK LIFETIME: X.XX sim seconds
   💀 Death threshold: 50% nodes dead OR root dead
   Dead nodes at death time: XX/100 (XX.X%)

--- Energy Metrics ---
📊 Total Network Energy Consumption: X.XXXXXX J
   TX Energy: X.XXXXXX J (XX.X%)
   RX Energy: X.XXXXXX J (XX.X%)
📦 Total Packets: XXXX
⚡ Average Energy per Packet: X.XXXXXXXXX J
📈 Energy Consumption by Role:
   [Breakdown by role...]

--- Final Role Distribution ---
  ROOT: 1
  CLUSTER_HEAD: X
  REGISTERED: X
  ROUTER: X
============================================================
```

---

## Key Files Modified

### 1. `source/config.py`
- **Routing**: `NEIGHBOR_TABLE_MAX_HOPS`, `MAX_MESH_ROUTE_HOPS`, `ENABLE_DATA_PACKETS`
- **TX Power**: `NODE_TX_RANGES`, `TX_POWER_LEVELS`, `ALLOW_TX_POWER_CHOICE`
- **Packet Loss**: `PACKET_LOSS_RATIO`
- **Failure/Recovery**: `FAILURE_TIME`, `RECOVERY_TIME`, `NUM_NODES_TO_KILL`
- **Energy Model**: `VOLTAGE`, `DATARATE`, `TX_CURRENT_LEVELS_MA`, `RX_CURRENT`, `INITIAL_ENERGY_J`, `MIN_ENERGY_J`, `NETWORK_DEATH_THRESHOLD`

### 2. `source/wsnlab.py`
- **Simulator**: Added `packet_seq`, `packet_log`, `join_times`, `total_tx_attempts`, `total_tx_dropped`
- **Node.send()**: Auto-stamps packets with ID, timestamp, path
- **Addr**: Added `__hash__()` method for dictionary keys

### 3. `source/wsnlab_vis.py`
- **Node.send()**: Packet loss simulation, attempt/drop counting
- **Simulator**: Packet loss statistics tracking
- **Line Styles**: Added cyan TX range style for root nodes

### 4. `wsnlab/data_collection_tree.py`
- **Energy Model**: TX/RX energy consumption, node death, network lifetime tracking
- **TX Power**: Dynamic power assignment, power propagation to children
- **Failure/Recovery**: Node killing, recovery, network reorganization
- **Topology Constraints**: Leaf/router attachment restrictions
- **Metrics**: Comprehensive CSV exports and statistics
- **Performance**: Optimized routing lookups, disabled verbose logging by default

### 5. `wsnlab/generate_graphs.py` (NEW)
- Graph generation script for all metrics
- Reads CSV files and creates publication-ready visualizations

---

## Assignment Requirements Met

### Core Requirements (Items 1-3)
✅ **Item 1**: Multi-hop neighbor discovery via neighbor table sharing
✅ **Item 2**: Cluster-tree structures used for routing fallback
✅ **Item 3a**: Mesh-first, tree-fallback routing implemented
✅ **Item 3b.i**: End-to-end delay timestamping and logging
✅ **Item 3b.ii**: Packet path tracing between arbitrary nodes

### Advanced Features (Items 4-8)
✅ **Item 4**: TX power optimization with dynamic assignment
✅ **Item 5**: Packet loss model with configurable ratio
✅ **Item 6**: Node failure and recovery with self-healing
✅ **Item 7**: CC2420 energy model with network lifetime tracking
✅ **Item 8**: Network topology constraints (leaf/router restrictions)

### Additional Features
✅ **Role Change Logging**: All role transitions logged to CSV
✅ **Energy Metrics**: Comprehensive per-node and network-wide energy statistics
✅ **Graph Generation**: Automated visualization of all metrics
✅ **Network Reorganization**: Automatic child reconnection on parent death
✅ **Root Protection**: Root node cannot die from energy depletion
✅ **Performance Optimizations**: O(1) routing lookups, configurable logging

All modifications preserve existing codebase structure and behaviors while cleanly extending functionality.
