# Quick Start Guide

## Running the Simulation

```bash
cd /Users/lg/Downloads/EE662Fall2025_claude/wsnlab
python data_collection_tree.py
```

## What to Expect

### 1. Visualization Window (if enabled)
- **White nodes**: Undiscovered (sleeping)
- **Red nodes**: Awake and probing
- **Yellow nodes**: Unregistered (discovered but not joined)
- **Green nodes**: Registered members
- **Blue nodes**: Cluster heads
- **Black node**: Root node

### 2. Terminal Output
The simulation will run mostly silently (logging disabled to reduce spam) and then display:

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
    Packet 123: 5 -> 12 -> 3 -> 17 (delay: 0.1234)
    [Shows mesh/tree routing paths]

--- Final Role Distribution ---
  ROOT: 1
  CLUSTER_HEAD: X
  REGISTERED: X
============================================================
```

### 3. CSV Outputs
- `node_distances.csv`: Pairwise Euclidean distances
- `node_distance_matrix.csv`: Full distance matrix
- `clusterhead_distances.csv`: Cluster head distances
- `neighbor_distances.csv`: Neighbor relationships

## Configuration Tweaks

Edit `source/config.py`:

### For More Mesh Routing
```python
NEIGHBOR_TABLE_MAX_HOPS = 3  # Share up to 3-hop neighbors
MAX_MESH_ROUTE_HOPS = 5      # Try mesh routing up to 5 hops
```

### To Disable Random Data Packets
```python
ENABLE_DATA_PACKETS = False
```

### To Reduce Simulation Time
```python
SIM_DURATION = 2000  # Default: 5000
```

### To See Verbose Logs
In `data_collection_tree.py`, line ~784:
```python
node.logging = True  # Change from False
```

## Verifying Implementation

### 1. Check Mesh Table Building
Enable logging for one node and grep for "mesh_table" in heartbeats - you should see nodes advertising their neighbor tables.

### 2. Check Routing Behavior
Look at packet paths in the final output:
- **Short paths** (2-3 hops): Likely using mesh routing
- **Longer paths** through cluster heads: Likely using tree fallback

### 3. Check Packet Delivery
The statistics should show:
- Total packets delivered > 0
- Average delays in reasonable range (< 1.0 sim seconds for typical network)
- Sample paths showing different routes

## Troubleshooting

### "No packets delivered"
- Increase `SIM_DURATION` (simulation may need more time)
- Check `ENABLE_DATA_PACKETS = True`

### "No join times recorded"
- Check that ROOT_ID is being selected (random)
- Ensure nodes are waking up (check NODE_ARRIVAL_MAX)

### Visualization not showing
```python
SIM_VISUALIZATION = True  # in config.py
```

## Assignment Verification Checklist

✅ **Multi-hop neighbor discovery**: Check heartbeat mesh_table fields
✅ **Neighbor table sharing**: Verify mesh_table updates on receive
✅ **Cluster-tree routing**: Tree fallback when mesh fails
✅ **Mesh-first routing**: Shorter paths for nearby nodes
✅ **Packet timestamping**: All packets have creation_time, pkt_id
✅ **Path tracing**: Sample paths show node-to-node routes
✅ **Join time tracking**: Average join time printed
✅ **Statistics output**: Clean summary at end

## Key Implementation Files

- **config.py**: Routing parameters (NEIGHBOR_TABLE_MAX_HOPS, etc.)
- **wsnlab.py**: Packet tracking in Simulator and Node.send()
- **data_collection_tree.py**: Main implementation with mesh routing
- **IMPLEMENTATION_SUMMARY.md**: Full technical documentation
