# network properties
import random
BROADCAST_NET_ADDR = 255
BROADCAST_NODE_ADDR = 255

random.seed(12345)  # deterministic seed for reproducible runs


JOIN_REQUEST_TIME_INTERVAL = 10  # or 12, etc.
# ROLE_OPTIMIZE_TIME = 2000
# node properties
NODE_TX_RANGES = {
    0: 65,   # low power #prev 60
    1: 100,  # medium
    2: 140,  # high
}
TX_POWER_LEVELS = sorted(NODE_TX_RANGES.keys())
NODE_DEFAULT_TX_POWER = 1
ALLOW_TX_POWER_CHOICE = True

NODE_TX_RANGE = 100  # transmission range of nodes (fallback)
NODE_ARRIVAL_MAX = 200  # max time to wake up

# Advanced features
PACKET_LOSS_RATIO = 0.05   # 0.01% old value

# Failure Simulation of killing nodes
FAILURE_TIME = 500  # Time to kill node(s) #1000 old value
RECOVERY_TIME = 550  # Time to recover node(s) #1500 old value
NUM_NODES_TO_KILL = 3  # Number of nodes to kill (can be multiple)


NUM_OF_CHILDREN = 25

# simulation properties
SIM_NODE_COUNT = 100  # noce count in simulation
# 60 okay with performance #50 is good with power  #80 works but overlap with ower # cell size to place one node
SIM_NODE_PLACING_CELL_SIZE = 60
SIM_DURATION = 5000  # simulation Duration in seconds
# 0 for max speed (headless/fast-forward), >0 for real-time factor
SIM_TIME_SCALE = 0
SIM_TERRAIN_SIZE = (1400, 1400)  # terrain size
SIM_TITLE = 'Data Collection Tree'  # title of visualization window
SIM_VISUALIZATION = True  # visualization active

# optional performance toggles
ENABLE_PACKET_ROUTE_LOGGING = True  # Disable for performance
# set True to keep mesh routing/heartbeat export, False to skip for speed
ENABLE_MESH = True
SCALE = 1  # scale factor for visualization

# new limit for mesh export size to avoid huge heart‑beat packets
MAX_MESH_EXPORT = 500  # max number of mesh entries included in a HEART_BEAT

# application properties
HEARTH_BEAT_TIME_INTERVAL = 100
REPAIRING_METHOD = 'FIND_ANOTHER_PARENT'  # 'ALL_ORPHAN', 'FIND_ANOTHER_PARENT'
EXPORT_CH_CSV_INTERVAL = 10  # simulation time units;
EXPORT_NEIGHBOR_CSV_INTERVAL = 10  # simulation time units;
# interval to sample average node power (sim seconds)
POWER_SAMPLING_INTERVAL = 50
# Allow leaf/unregistered nodes to temporarily attach to a router when no CH/ROOT is reachable.
# Helps bridge isolated islands after CH death.
ALLOW_ROUTER_PARENT_FALLBACK = False

# routing properties
NEIGHBOR_TABLE_MAX_HOPS = 2  # max hops for neighbor table sharing (was 2)
MAX_MESH_ROUTE_HOPS = 5  # max hops to attempt mesh routing
ENABLE_DATA_PACKETS = True  # enable random data packet generation for testing

# --- Energy model / CC2420 (8) ---
VOLTAGE = 3.0            # V
DATARATE = 250_000       # bits per second (IEEE 802.15.4)
MTU = 127 * 8            # bits; you can override per-packet length if you want

# CC2420 currents (mA) at different output powers
# Map them to your TX_POWER_LEVELS (0=low, 1=med, 2=high)
TX_CURRENT_LEVELS_MA = {
    0: 9.9,   # approx -15 dBm
    1: 11.0,  # approx -10 dBm
    2: 17.4,  # 0 dBm
}

RX_CURRENT = 18.8        # mA

# Energy thresholds
# starting energy per node (pick value that lets nodes actually die during your sim)
INITIAL_ENERGY_J = 2
MIN_ENERGY_J = 1.7  # 0.01      # when power <= this, node is considered "dead"
# If you put 2.0 int energy and 1.8 it will show amount of death nodes and it will tries its best to not die

ENERGY_PSDU_BYTES = 50   # N in the formula E = V * I * 8 * (N+6) / R
TX_TURNAROUND_ENERGY_J = 10e-6   # ~10 μJ PLL/turnaround overhead
RX_TURNAROUND_ENERGY_J = 10e-6   # symmetric assumption

# Network lifetime threshold (percentage of nodes that must die before network is considered dead)
# 0.05 is good to see amount of death nodes # 50% of nodes dead
NETWORK_DEATH_THRESHOLD = 0.50
