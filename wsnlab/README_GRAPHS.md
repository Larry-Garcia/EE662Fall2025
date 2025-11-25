# Network Simulation Graphs

This script generates visualization graphs from simulation CSV outputs.

## Usage

```bash
cd wsnlab
python3 generate_graphs.py
or 
python generate_graphs.py
```

## Requirements

```bash
pip install matplotlib numpy
```

## Generated Graphs

### 1. **Graph 1: Join Times** (`graph_1_join_times.png`)
- **Histogram**: Distribution of node join times
- **CDF**: Cumulative distribution function
- **Data source**: `registration_log.csv`
- Shows how quickly nodes join the network

### 2. **Graph 2: Packet Delay** (`graph_2_packet_delay.png`)
- **Histogram**: Distribution of packet delays
- **Delay vs Hop Count**: How delay increases with network hops
- **Data source**: `packet_log.csv`
- Analyzes end-to-end packet delivery performance

### 3. **Graph 3: Failure & Recovery** (`graph_3_failure_recovery.png`)
- **Orphan Count Over Time**: Shows network recovery after failures
- **Markers**: KILLED (red X), RECOVERED (green circle), ENERGY_DEAD (orange square)
- **Data source**: `failures.csv`
- Visualizes self-healing capability

### 4. **Graph 4: Energy Consumption** (`graph_4_energy_consumption.png`)
- **Energy by Role**: Average energy consumption per role (ROOT, CH, ROUTER, REGISTERED)
- **TX vs RX Energy**: Breakdown by role
- **Energy per Packet**: Average energy cost per packet
- **Cumulative Deaths**: Energy deaths over time
- **Data source**: `energy_metrics.csv`, `failures.csv`

### 5. **Graph 5: Packet Loss** (`graph_5_packet_loss.png`)
- **Configured vs Realized**: Comparison of expected vs actual packet loss
- **Note**: Update realized loss value from simulation output
- Shows if packet loss simulation is working correctly

## Notes

- All graphs are saved as PNG files with 300 DPI resolution
- Graphs include statistics printed to console
- Some graphs may show warnings if CSV files are missing or empty
- Graph 5 (packet loss) may need manual update of realized loss value from simulation output

