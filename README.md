# EE662Fall2025 - WSN Data Collection Tree Simulation

A Wireless Sensor Network (WSN) simulation framework implementing a hierarchical data collection tree with mesh routing capabilities. This project simulates self-organized networks with cluster heads, routing protocols, energy consumption modeling, and comprehensive metrics collection.

## Features

- **Example Network Topology**: Root → Cluster Heads → Registered Nodes and there is router
- **Mesh Routing**: Multi-hop neighbor discovery and routing
- **Cluster-Tree Routing**: Fallback routing through cluster heads
- **Energy Modeling**: CC2420-based energy consumption tracking
- **Failure & Recovery**: Node failure simulation and network repair
- **Comprehensive Logging**: CSV traces for packets, routes, energy, and topology
- **Visualization**: Real-time network topology visualization (optional)

## Requirements

### Python Packages

Install the required packages:

```bash
pip install simpy
```

### Python Version

- Python 3.7 or higher recommended

## Quick Start

### 1. Navigate to the Project Directory and activate venv then cd 

```bash
source venv/bin/activate
```

```bash
cd wsnlab
```

### 2. Run the Simulation (to end sim just exit the sim click x on window or do ctrl c)

```bash
python data_collection_tree.py
```

### 3. What to Expect

The simulation will:
- Display a visualization window (if `SIM_VISUALIZATION = True` in config)
- Run for the configured duration (default: 5000 simulation seconds)
- Generate CSV output files in the `wsnlab/` directory
- Print statistics at the end

### Visualization Colors

- **White nodes**: Undiscovered (sleeping)
- **Red nodes**: Awake and probing
- **Yellow nodes**: Unregistered (discovered but not joined)
- **Green nodes**: Registered members
- **Blue nodes**: Cluster heads
- **Magenta nodes**: router heads
- **Black node**: Root node

## Configuration

Edit `wsnlab/source/config.py` to customize simulation parameters:

### Some Configuration example options look at config for list

```python
# Simulation Settings
SIM_NODE_COUNT = 100          # Number of nodes
SIM_DURATION = 5000           # Simulation duration (seconds)
SIM_VISUALIZATION = True      # Enable/disable visualization
SIM_TERRAIN_SIZE = (1400, 1400)  # Network area size

# Routing Settings
NEIGHBOR_TABLE_MAX_HOPS = 2   # Max hops for neighbor table sharing
MAX_MESH_ROUTE_HOPS = 4       # Max hops for mesh routing
ENABLE_MESH = True           # Enable mesh routing
ENABLE_DATA_PACKETS = True   # Enable random data packet generation

# Energy Settings
INITIAL_ENERGY_J = 2.0       # Starting energy per node
MIN_ENERGY_J = 1.7           # Death threshold
NETWORK_DEATH_THRESHOLD = 0.50  # 50% nodes dead = network death

# Failure Simulation
FAILURE_TIME = 500           # Time to kill node(s)
RECOVERY_TIME = 550          # Time to recover node(s)
NUM_NODES_TO_KILL = 3        # Number of nodes to kill
```

See `wsnlab/source/config.py` for all available options.

## Output Files

The simulation generates several CSV files in the `wsnlab/` directory:

### Trace Files
- **`packet_log.csv`**: Complete packet delivery records with paths
  - Columns: `packet_id`, `packet_type`, `source_gui`, `dest_gui`, `created_at`, `received_at`, `delay`, `path`
- **`packet_routes.csv`**: Per-hop routing trace (detailed)
  - Columns: `time`, `packet_type`, `source`, `current_node`, `next_hop`, `dest`, `hop_count`, `routing_direction`

### Network Metrics
- **`registration_log.csv`**: Node registration times
- **`role_changes.csv`**: Role transition history
- **`failures.csv`**: Failure and recovery events
- **`energy_metrics.csv`**: Per-node energy consumption statistics
- **`power_over_time.csv`**: Network-wide power consumption over time
- **`packet_loss_stats.csv`**: Packet loss statistics

### Topology Files
- **`topology.csv`**: Final network topology
- **`node_distances.csv`**: Pairwise node distances
- **`node_distance_matrix.csv`**: Full distance matrix
- **`neighbor_distances.csv`**: Neighbor relationships
- **`clusterhead_distances.csv`**: Cluster head distances

### Generated Graphs
- `graph_1_join_times.png`: Node join time distribution
- `graph_2_packet_delay.png`: Packet delay analysis
- `graph_3_failure_recovery.png`: Failure recovery timeline
- `graph_4_energy_consumption.png`: Energy consumption analysis
- `graph_5_packet_loss.png`: Packet loss statistics
- `graph_6_power_over_time.png`: Power consumption over time

To generate graphs, do this after run:
```bash
cd wsnlab
python generate_graphs.py
```

## Project Structure

```
.
├── wsnlab/                    # Main simulation directory
│   ├── data_collection_tree.py  # Main simulation script
│   ├── source/                 # Source code
│   │   ├── config.py           # Configuration file
│   │   ├── wsnlab.py           # Core simulation engine
│   │   └── wsnlab_vis.py       # Visualization module
│   ├── topovis/                # Topology visualization
│   └── [CSV output files]      # Generated data files
├── wsnsimpy/                   # Base simulation library
└── README.md                   # This file
```

## Documentation

- **`QUICK_START.md`**: Quick start guide with detailed running instructions
- **`IMPLEMENTATION_SUMMARY.md`**: Complete technical documentation
- **`wsnlab/README_GRAPHS.md`**: Graph generation documentation

## Example Output

After running the simulation, you'll see output like:

```
============================================================
Simulation Finished
============================================================

--- Network Statistics ---
Join Times: 100 nodes joined
  Average: 245.32 sim seconds
  Min: 5.04 sim seconds
  Max: 802.35 sim seconds

Packet Delivery: 1234 packets delivered
  Average delay: 0.0234 sim seconds
  Min delay: 0.0001 sim seconds
  Max delay: 0.1234 sim seconds
  By type: {'DATA': 500, 'SENSOR_DATA': 734}

--- Final Role Distribution ---
  ROOT: 1
  CLUSTER_HEAD: 12
  REGISTERED: 87
============================================================
```

## Troubleshooting

### Visualization Not Showing
- Check `SIM_VISUALIZATION = True` in `config.py`
- Ensure you have a display/GUI available (or disable visualization for headless runs)

### No Packets Delivered
- Increase `SIM_DURATION` in `config.py`
- Verify `ENABLE_DATA_PACKETS = True`

### Performance Issues
- Disable visualization: `SIM_VISUALIZATION = False`
- Disable packet route logging: `ENABLE_PACKET_ROUTE_LOGGING = False`
- Reduce node count: `SIM_NODE_COUNT = 50`

## License

This project is part of EE662 Fall 2025 coursework.

## Repository

GitHub: https://github.com/Larry-Garcia/EE662Fall2025
