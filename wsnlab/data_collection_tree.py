import time
import csv
from collections import Counter
from source import config
import math
from source import wsnlab_vis as wsn
import random
from enum import Enum
import sys
sys.path.insert(1, '.')

# Make runs reproducible but can have config overrides
random.seed(getattr(config, "SEED", 22))

# ---- Config fallbacks(backup) so this file works but overwritten by config.py ----
TX_RANGES = getattr(config, "NODE_TX_RANGES", {0: config.NODE_TX_RANGE})
TX_POWER_LEVELS = getattr(config, "TX_POWER_LEVELS", list(TX_RANGES.keys()))
NODE_DEFAULT_TX_POWER = getattr(
    config,
    "NODE_DEFAULT_TX_POWER",
    next(iter(TX_POWER_LEVELS), 0)
)
ALLOW_TX_POWER_CHOICE = getattr(config, "ALLOW_TX_POWER_CHOICE", False)
POWER_LEVELS_ASC = sorted(TX_POWER_LEVELS)

HEART_BEAT_INTERVAL = getattr(
    config,
    "HEART_BEAT_TIME_INTERVAL",
    getattr(config, "HEARTH_BEAT_TIME_INTERVAL", 101)
)
ROLE_OPTIMIZE_TIME = getattr(config, "ROLE_OPTIMIZE_TIME", 2000)
JOIN_REQ_EXPAND_THRESHOLD = getattr(config, "JOIN_REQ_EXPAND_THRESHOLD", 3)
JOIN_REQ_EXPAND_WINDOW = getattr(
    config, "JOIN_REQ_EXPAND_WINDOW", HEART_BEAT_INTERVAL * 2)
JOIN_REQUEST_INTERVAL = getattr(config, "JOIN_REQUEST_TIME_INTERVAL", 20)
DATA_INTERVAL = getattr(config, "DATA_INTERVAL", 50)
ENABLE_DATA_PACKETS = getattr(config, "ENABLE_DATA_PACKETS", False)
TABLE_SHARE_INTERVAL = getattr(
    config, "TABLE_SHARE_INTERVAL", HEART_BEAT_INTERVAL) #defaults to 100 for tableshare
MESH_HOP_N = getattr(
    config,
    "MESH_HOP_N",
    getattr(config, "NEIGHBOR_TABLE_MAX_HOPS", 2)
)
NUM_OF_CLUSTERS = getattr(config, "NUM_OF_CLUSTERS", 255)
NUM_OF_CHILDREN = getattr(config, "NUM_OF_CHILDREN", 254)

# Performance: disable detailed packet route logging (causes slowdown with many packets)
ENABLE_PACKET_ROUTE_LOGGING = getattr(
    config, "ENABLE_PACKET_ROUTE_LOGGING", False)

RX_CURRENT = getattr(config, "RX_CURRENT", 18.8)
VOLTAGE = getattr(config, "VOLTAGE", 3.0)
MTU_BITS = getattr(config, "MTU", 127 * 8)       # got some bits
DATARATE = getattr(config, "DATARATE", 250_000.)  #python allows _ for readability# bps per the ieee 802 standard 

# TX current mapping for energy model (8)
TX_CURRENTS_MA = getattr(
    config,
    "TX_CURRENT_LEVELS_MA",
    {level: 17.4 for level in TX_POWER_LEVELS}  # fallback: max power current
)

# Energy thresholds
INITIAL_ENERGY_J = getattr(config, "INITIAL_ENERGY_J", 5.0)
MIN_ENERGY_J = getattr(config, "MIN_ENERGY_J", 0.01)
ENERGY_PSDU_BYTES = getattr(config, "ENERGY_PSDU_BYTES", 50)
TX_TURNAROUND_ENERGY_J = getattr(config, "TX_TURNAROUND_ENERGY_J", 10e-6)
RX_TURNAROUND_ENERGY_J = getattr(config, "RX_TURNAROUND_ENERGY_J", 10e-6)
NETWORK_DEATH_THRESHOLD = getattr(config, "NETWORK_DEATH_THRESHOLD", 0.5)

# Network lifetime tracking
NETWORK_DEATH_TIME = None

# Track where each node is placed and basic mappings
NODE_POS = {}          # {node_id: (x, y)}
ADDR_TO_NODE = {}      # (net_addr, node_addr) -> node
NODES_REGISTERED = 0

# --- tracking containers ---
ALL_NODES = []              # node objects
CLUSTER_HEADS = []
ROLE_COUNTS = Counter()     # live tally per Roles enum


def _addr_str(a):
    """Helper to safely convert Addr to string, returns empty string if None."""
    # Example: _addr_str(None) -> "", _addr_str(Addr(1, 2)) -> "(1, 2)"
    return "" if a is None else str(a)


def _role_name(r):
    """Helper to get role name string from enum or other type."""
    # Example: _role_name(Roles.CLUSTER_HEAD) -> "CLUSTER_HEAD"
    return r.name if hasattr(r, "name") else str(r)


def _min_power_for_distance(distance):
    """
    Pick the lowest TX power whose range (scaled) covers the given distance.
    Falls back to highest level if none cover it or defaults if levels missing.
    """
    if not POWER_LEVELS_ASC:
        return NODE_DEFAULT_TX_POWER

    # Compare using scaled ranges to match node positions.
    sorted_levels = sorted(TX_RANGES.items(), key=lambda kv: kv[1])
    for level, rng in sorted_levels:
        if distance <= rng * config.SCALE:
            return level
    # Distance exceeds all ranges; use strongest available power.
    return sorted_levels[-1][0]


Roles = Enum(
    'Roles',
    'UNDISCOVERED UNREGISTERED ROOT REGISTERED CLUSTER_HEAD ROUTER'
)
"""Enumeration of roles"""


def log_all_nodes_registered():
    """Log every node's status and role to topology.csv and check if all are registered."""
    # Example: Exports final network state and verifies all nodes reached REGISTERED/CLUSTER_HEAD/ROOT/ROUTER
    filename = "topology.csv"

    with open(filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Node ID", "Position", "Role"])

        unregistered_nodes = []

        for node in ALL_NODES:
            role = getattr(node, "role", "UNKNOWN")
            position = getattr(node, "pos", None)
            writer.writerow([node.id, position, role])

            if role not in {Roles.REGISTERED, Roles.CLUSTER_HEAD, Roles.ROOT, Roles.ROUTER}:
                unregistered_nodes.append(node.id)

    if not unregistered_nodes:
        print(
            f"✅ All {len(ALL_NODES)} nodes are registered. Logged to {filename}.")
        return True
    else:
        print(
            f"⚠️ Unregistered nodes: {unregistered_nodes}. Logged to {filename}.")
        return False


# CSV files will be initialized in init_csv_files() before simulation runs


def init_csv_files():
    """Initialize all CSV files by clearing them and writing headers."""
    # Example: Overwrites all CSV files at simulation start to prevent data accumulation
    # Registration log CSV
    with open("registration_log.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["node_id", "start_time", "registered_time", "delta_time"])

    # Role change log CSV
    with open("role_changes.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "node_id", "old_role", "new_role"])

    # Packet route CSV (per-hop) - only initialize if logging is enabled
    if ENABLE_PACKET_ROUTE_LOGGING:
        with open("packet_routes.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "time",
                "packet_type",
                "source",
                "current_node",
                "next_hop",
                "dest",
                "hop_count",
                "routing_direction",
            ])

    # Power over time CSV
    with open("power_over_time.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "avg_power_j", "min_power_j", "max_power_j", "alive_nodes", "dead_nodes"])

    # Energy metrics CSV
    with open("energy_metrics.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "node_id",
            "role",
            "initial_energy_j",
            "final_energy_j",
            "total_energy_consumed_j",
            "tx_energy_consumed_j",
            "rx_energy_consumed_j",
            "tx_packet_count",
            "rx_packet_count",
            "total_packet_count",
            "avg_energy_per_tx_packet_j",
            "avg_energy_per_rx_packet_j",
            "energy_efficiency_j_per_packet",
        ])


def log_all_packets(packet_log, filename="packet_log.csv"):
    """
    Write all packet deliveries to a CSV file.

    Works with the list-of-dicts format we append to sim.packet_log
    in SensorNode.maybe_log_packet_delivery().
    """
    with open(filename, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "packet_id",
            "packet_type",
            "source_gui",
            "dest_gui",
            "created_at",
            "received_at",
            "delay",
            "path",
        ])

        # Accept either dict (old style) or list-of-dicts (our style)
        if isinstance(packet_log, dict):
            for pck_id, entry in packet_log.items():
                created_at = entry.get("created_at")
                source = entry.get("source")
                for recv_time in entry.get("received_at", []) or [""]:
                    delay = "" if not recv_time else (recv_time - created_at)
                    writer.writerow([
                        pck_id,
                        "",
                        source,
                        "",
                        created_at,
                        recv_time,
                        delay,
                        "",
                    ])
        else:
            for entry in packet_log:
                writer.writerow([
                    entry.get("pkt_id"),
                    entry.get("type"),
                    entry.get("source_gui"),
                    entry.get("dest_gui"),
                    entry.get("created_at"),
                    entry.get("received_at"),
                    entry.get("delay"),
                    " -> ".join(str(n) for n in entry.get("path", [])),
                ])


def log_registration_time(node_id, start_time, registered_time, diff):
    with open("registration_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([node_id, start_time, registered_time, diff])


def check_all_nodes_registered():
    """Return True when all nodes are registered / CH / ROOT / ROUTER."""
    global RECOVERY_DURATION, RECOVERY_START_TIME
    
    unregistered_nodes = []

    for node in ALL_NODES:
        role = getattr(node, "role", "UNKNOWN")
        if role not in {Roles.REGISTERED, Roles.CLUSTER_HEAD, Roles.ROOT, Roles.ROUTER}:
            unregistered_nodes.append(node.id)

    # Check if recovery is complete (0 orphans after recovery started)
    if RECOVERY_START_TIME is not None and RECOVERY_DURATION is None:
        if not unregistered_nodes:
            RECOVERY_DURATION = sim.now - RECOVERY_START_TIME
            print(
                f"✅ RECOVERY COMPLETE at time {sim.now:.2f}. Duration: {RECOVERY_DURATION:.2f} sim seconds")

    return not unregistered_nodes


# CSV files will be initialized in init_csv_files() before simulation runs


def log_packet_route(pck, current_node, next_hop, path_type):
    """Append a routing trace row to packet_routes.csv (only if enabled)."""
    if not ENABLE_PACKET_ROUTE_LOGGING:
        return
    with open("packet_routes.csv", "a", newline="") as f:
        w = csv.writer(f)
        time = getattr(current_node, "now", "")
        ptype = pck.get("type", "")
        src = str(pck.get("source", ""))
        dest = str(pck.get("dest", ""))
        hop = pck.get("hop_count", "")
        w.writerow([time, ptype, src, current_node.id,
                   next_hop, dest, hop, path_type])


###########################################################
class SensorNode(wsn.Node):
    """SensorNode class is inherited from Node class in wsnlab.py."""

    ###################
    def init(self):
        """Initialization of node."""
        self.scene.nodecolor(self.id, 1, 1, 1)  # white
        self.sleep()
        self.addr = None
        self.transfer_engaged = None
        self.ch_transfer_target = None
        self.ch_addr = None  # clusterhead address
        self.parent_gui = None
        self.root_addr = None
        self.wake_up_time = None
        # Energy model (8) - will be set to INITIAL_ENERGY_J below
        self.power = INITIAL_ENERGY_J

        self.set_role(Roles.UNDISCOVERED)
        self.is_root_eligible = True if self.id == ROOT_ID else False
        self.c_probe = 0
        self.th_probe = 10
        self.hop_count = 99999
        self.jr_threshold = 5
        self.neighbors_table = {}
        self.candidate_parents_table = []
        self.child_networks_table = {}
        self.members_table = []
        self.net_req_flag = None
        self.join_req_attempts = {}
        self.received_JR_guis = []
        self.node_available_dict = {}
        self.net_id_available_dict = {}
        self.awaiting_ack = False
        self.ch_nominee = None
        self.ch_nomination_blacklist = []
        self.tx_range_circle_id = None  # Track TX range circle for removal
        self.join_request_times = []
        self.max_pending_join_distance = 0
        self.failed = False
        # Energy model (8) - TX current initialized here
        self.tx_current_mA = TX_CURRENTS_MA.get(NODE_DEFAULT_TX_POWER, 17.4)
        # Energy metrics tracking
        self.tx_energy_consumed = 0.0  # Total TX energy consumed (J)
        self.rx_energy_consumed = 0.0  # Total RX energy consumed (J)
        self.tx_packet_count = 0       # Number of packets transmitted
        self.rx_packet_count = 0       # Number of packets received
        ALL_NODES.append(self)

    ###################
    def run(self):
        """Schedule wakeup."""
        self.set_timer('TIMER_ARRIVAL', self.arrival)
        # Schedule one-time role optimization check to trim unneeded CH/Router overlap
        self.set_timer('TIMER_ROLE_OPTIMIZE', ROLE_OPTIMIZE_TIME)

    ###################
    def set_address(self, addr):
        """Set node address and update global mapping."""
        global ADDR_TO_NODE

        if hasattr(self, 'addr') and self.addr is not None:
            old_key = (self.addr.net_addr, self.addr.node_addr)
            ADDR_TO_NODE.pop(old_key, None)

        self.addr = addr

        if addr is not None:
            key = (addr.net_addr, addr.node_addr)
            ADDR_TO_NODE[key] = self

    ###################
    def set_ch_address(self, ch_addr):
        """Set cluster head address and update global mapping."""
        global ADDR_TO_NODE

        if hasattr(self, 'ch_addr') and self.ch_addr is not None:
            old_key = (self.ch_addr.net_addr, self.ch_addr.node_addr)
            ADDR_TO_NODE.pop(old_key, None)

        self.ch_addr = ch_addr

        if ch_addr is not None:
            key = (ch_addr.net_addr, ch_addr.node_addr)
            ADDR_TO_NODE[key] = self

    ###################
    def register(self):
        """Called when node successfully registers."""
        self.registered_time = self.now
        diff = self.registered_time - self.wake_up_time

        # Track if this is the first registration (for join_times statistics)
        is_first_registration = not hasattr(self, '_has_registered_before')
        if is_first_registration:
            self._has_registered_before = True

        global NODES_REGISTERED
        NODES_REGISTERED += 1
        if NODES_REGISTERED == len(ALL_NODES) - 1:
            log_all_nodes_registered()

        log_registration_time(self.id, self.wake_up_time,
                              self.registered_time, diff)
        # Only count first registration in join_times (to avoid counting re-joins after demotion/recovery)
        if is_first_registration:
            self.sim.join_times.append(diff)

    ###################
    def assign_tx_power(self, power_level=None):
        """Pick a TX power level and update tx_range + tx_current."""
        # Example: CH selects minimum power level (0/1/2) needed to cover farthest child, reducing energy consumption
        global TX_RANGES, TX_POWER_LEVELS

        if power_level is not None:
            self.tx_power = power_level
        elif self.role == Roles.ROUTER:
            # Routers always run at highest power to bridge clusters.
            self.tx_power = POWER_LEVELS_ASC[-1] if POWER_LEVELS_ASC else NODE_DEFAULT_TX_POWER
        elif self.role in (Roles.CLUSTER_HEAD, Roles.ROOT):
            # CH/ROOT choose minimal power that covers farthest relevant neighbor.
            max_dist = self._max_cluster_distance()
            self.tx_power = _min_power_for_distance(
                max_dist) if max_dist > 0 else NODE_DEFAULT_TX_POWER
        else:
            # Leaf/unregistered nodes stay at default; clusters manage coverage.
            self.tx_power = NODE_DEFAULT_TX_POWER

        range_val = TX_RANGES.get(self.tx_power, config.NODE_TX_RANGE)
        self.tx_range = range_val * config.SCALE

        # Set TX current (mA) for energy model (8)
        self.tx_current_mA = TX_CURRENTS_MA.get(self.tx_power, 17.4)

    ###################
    def _consume_tx_energy(self, n_bytes=None):
        """Subtract TX energy for one packet from self.power (8)."""
        # Example: Calculates CC2420 TX energy (V*I*8*(N+6)/R + overhead) and decrements node's power, may trigger death
        if not hasattr(self, "power"):
            return  # safety

        # Choose packet length (PSDU). If not given, use config default.
        if n_bytes is None:
            n_bytes = ENERGY_PSDU_BYTES

        I_mA = getattr(self, "tx_current_mA", None)
        if I_mA is None:
            I_mA = 17.4  # fallback: worst-case current

        V = VOLTAGE
        R = DATARATE

        # Etx = (V * I * 8*(N+6)) / R  (I in Amps)  + overhead
        I_A = I_mA / 1000.0
        bits = 8 * (n_bytes + 6)
        base_E = V * I_A * (bits / R)
        overhead = TX_TURNAROUND_ENERGY_J
        dE = base_E + overhead

        # Track energy metrics
        self.tx_energy_consumed += dE
        self.tx_packet_count += 1

        self.power -= dE
        if self.power <= MIN_ENERGY_J:
            self._die_of_energy()

    ###################
    def _die_of_energy(self):
        """Turn node off permanently due to energy depletion (8)."""
        # Example: When power <= MIN_ENERGY_J, node turns dark gray, disconnects children, triggers network reorganization
        # Root node cannot die from energy depletion - it's critical for network
        if self.id == ROOT_ID:
            self.log("Root node energy depleted, but root cannot die. Energy set to minimum.")
            self.power = MIN_ENERGY_J  # Keep at minimum but alive
            return
        
        if getattr(self, "failed", False):
            return  # already dead/killed

        self.failed = True
        self.sleep()
        self.kill_all_timers()
        # Remove TX range circle (diameter) if visible (e.g., for CLUSTER_HEADs)
        self.remove_tx_range()
        # Dark gray to distinguish energy death
        self.scene.nodecolor(self.id, 0.2, 0.2, 0.2)
        
        # Network reorganization: disconnect all children and make them rejoin
        self._reorganize_network_after_death()
        
        # Log this as a failure event
        try:
            log_failure_event(self.now, self.id, "ENERGY_DEAD")
        except Exception:
            pass

    ###################
    def _reorganize_network_after_death(self):
        """Disconnect all children when this node dies, forcing them to rejoin."""
        # Example: When CH dies, all REGISTERED children become UNREGISTERED and restart JOIN_REQUEST timers
        # Erase this node's own parent arrow (if it has a parent)
        if hasattr(self, 'parent_gui') and self.parent_gui is not None:
            self.erase_parent()
        
        # Find all nodes that have this node as their parent
        children_to_disconnect = []
        for node in ALL_NODES:
            if (hasattr(node, 'parent_gui') and
                node.parent_gui == self.id and
                not getattr(node, "failed", False)):
                children_to_disconnect.append(node)
        
        # Disconnect each child and make them rejoin
        for child in children_to_disconnect:
            child.log(f"Parent {self.id} died (energy depletion). Rejoining network...")
            # Erase parent arrow (green arrow pointing from dead parent to child)
            child.erase_parent()
            # Clear parent relationship
            child.parent_gui = None
            child.ch_addr = None
            # Become unregistered to trigger rejoin process
            child.become_unregistered()
            # Restart join request timer
            child.set_timer('TIMER_JOIN_REQUEST', JOIN_REQUEST_INTERVAL)
        
        if children_to_disconnect:
            self.log(f"Disconnected {len(children_to_disconnect)} children due to energy death")

    ###################
    def send(self, pck):
        """Wrapper around base send that accounts for TX energy (8)."""
        # Example: Consumes TX energy before transmission, may cause node death
        # If I'm already dead (killed or energy), do nothing
        if getattr(self, "failed", False):
            return

        # Consume TX energy once per send
        self._consume_tx_energy()

        # If I died due to this transmission, don't actually send the packet
        if getattr(self, "failed", False):
            return

        # Call visual Node.send (which also does PACKET_LOSS and draws radio, etc.)
        super().send(pck)

    ###################
    def set_role(self, new_role, *, recolor=True):
        """Central place to switch roles, keep tallies, recolor, and schedule exports."""
        # Example: set_role(Roles.CLUSTER_HEAD) transitions node from REGISTERED to CH, updates GUI color, logs change
        old_role = getattr(self, "role", None)
        if old_role is not None:
            ROLE_COUNTS[old_role] -= 1
            if ROLE_COUNTS[old_role] <= 0:
                ROLE_COUNTS.pop(old_role, None)
        ROLE_COUNTS[new_role] += 1
        self.role = new_role

        # Log role transitions (skip initial None -> UNDISCOVERED)
        if old_role is not None and old_role != new_role:
            try:
                with open("role_changes.csv", "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        getattr(self, "now", ""),
                        self.id,
                        _role_name(old_role),
                        _role_name(new_role),
                    ])
            except Exception:
                # Don't break the sim if logging fails
                pass

        if recolor:
            if new_role == Roles.UNDISCOVERED:
                self.scene.nodecolor(self.id, 1, 1, 1)
            elif new_role == Roles.UNREGISTERED:
                self.scene.nodecolor(self.id, 1, 1, 0)
            elif new_role == Roles.REGISTERED:
                self.scene.nodecolor(self.id, 0, 1, 0)
            elif new_role == Roles.CLUSTER_HEAD:
                self.scene.nodecolor(self.id, 0, 0, 1)
                if ALLOW_TX_POWER_CHOICE:
                    self.assign_tx_power()
                else:
                    self.assign_tx_power(NODE_DEFAULT_TX_POWER)
                self.draw_tx_range()
            elif new_role == Roles.ROUTER:
                # Slightly different color so you can distinguish routers
                self.scene.nodecolor(self.id, 1, 0, 1)
                if ALLOW_TX_POWER_CHOICE:
                    self.assign_tx_power()
                else:
                    self.assign_tx_power(NODE_DEFAULT_TX_POWER)
                # Remove TX range circle if it exists (from previous CLUSTER_HEAD role)
                self.remove_tx_range()
            elif new_role == Roles.ROOT:
                self.scene.nodecolor(self.id, 0, 0, 0)
                self.assign_tx_power(NODE_DEFAULT_TX_POWER)
                # Draw TX range circle in cyan for root
                self.draw_tx_range()
                # Root drives CSV exports
                self.set_timer('TIMER_EXPORT_CH_CSV',
                               config.EXPORT_CH_CSV_INTERVAL)
                self.set_timer('TIMER_EXPORT_NEIGHBOR_CSV',
                               config.EXPORT_NEIGHBOR_CSV_INTERVAL)

    ###################
    def become_unregistered(self):
        if self.role != Roles.UNDISCOVERED:
            self.kill_all_timers()
            self.log('I became UNREGISTERED')
        self.scene.nodecolor(self.id, 1, 1, 0)
        self.erase_parent()
        self.addr = None
        self.ch_addr = None
        self.parent_gui = None
        self.root_addr = None
        self.set_role(Roles.UNREGISTERED)
        self.c_probe = 0
        self.th_probe = 10
        self.hop_count = 99999
        self.neighbors_table = {}
        self.candidate_parents_table = []
        self.child_networks_table = {}
        self.members_table = []
        self.received_JR_guis = []
        self.send_probe()
        self.set_timer('TIMER_JOIN_REQUEST', JOIN_REQUEST_INTERVAL)

    ###################
    def draw_tx_range(self):
        """Override to track circle ID so we can remove it later."""
        # Example: Draws blue dashed circle for CH or cyan dashed circle for ROOT, stores circle ID for later removal
        # Remove existing circle if any
        if self.tx_range_circle_id is not None:
            self.scene.delshape(self.tx_range_circle_id)
            self.tx_range_circle_id = None
        # Choose line style based on role: cyan for root, blue for cluster heads
        line_style = "wsnsimpy:tx_root" if self.role == Roles.ROOT else "wsnsimpy:tx"
        # Draw new circle and store its ID
        self.tx_range_circle_id = self.scene.circle(
            self.pos[0], self.pos[1], self.tx_range, line=line_style)

    ###################
    def remove_tx_range(self):
        """Remove the TX range circle if it exists."""
        if self.tx_range_circle_id is not None:
            self.scene.delshape(self.tx_range_circle_id)
            self.tx_range_circle_id = None

    ###################
    def become_router(self):
        """Turn a former CH into a router / bridge."""
        # Example: REGISTERED node becomes ROUTER to bridge two clusters, disconnects leaf children, uses max TX power
        # Remove TX range circle before changing role
        self.remove_tx_range()
        self.set_role(Roles.ROUTER)
        self.ch_addr = None
        self.send_network_update()

    ###################
    def send_ch_nomination(self):
        """Choose a child member to become the next CH (furthest away)."""
        candidates = {}
        for gui, neigh in self.neighbors_table.items():
            src = neigh['source']   # Addr
            # Skip if in blacklist
            if (src.net_addr, src.node_addr) in self.ch_nomination_blacklist:
                continue

            for member in self.members_table:
                if member == src:
                    distance = neigh.get('distance', 0)
                    candidates[(src.net_addr, src.node_addr)] = distance
                    break

        if candidates:
            best_src = max(candidates, key=candidates.get)
            self.log("candidate chosen for CH nomination")
            self.log(best_src)
            self.ch_nominee = best_src
            self.awaiting_ack = True
            self.send({
                'dest': wsn.Addr(best_src[0], best_src[1]),
                'type': 'CH_NOMINATION',
                'source': self.addr,
                'addr': self.ch_addr,
                'avail_dict': self.node_available_dict,
            })

    ###################
    def send_ch_nom_ack(self, pck):
        self.log("SENDING NOM ACK")
        self.send(
            {'dest': pck['source'], 'type': 'CH_NOMINATION_ACK', 'source': self.addr})

    ###################
    def bump_tx_power(self):
        """Increase TX power one level if possible; return True on change."""
        if not POWER_LEVELS_ASC:
            return False
        try:
            current_idx = POWER_LEVELS_ASC.index(self.tx_power)
        except ValueError:
            current_idx = -1

        if current_idx >= len(POWER_LEVELS_ASC) - 1:
            return False

        self.assign_tx_power(POWER_LEVELS_ASC[current_idx + 1])
        if self.role == Roles.CLUSTER_HEAD:
            self.draw_tx_range()
        return True

    ###################
    def record_join_request_and_maybe_expand(self):
        """
        Track join requests and expand TX power if we hear enough within a window.
        Keeps clusters minimal by default but allows opportunistic growth.
        """
        if self.role not in (Roles.CLUSTER_HEAD, Roles.ROOT):
            return

        now = getattr(self, "now", 0)
        self.join_request_times.append(now)
        self.join_request_times = [
            t for t in self.join_request_times if now - t <= JOIN_REQ_EXPAND_WINDOW]

        if len(self.join_request_times) >= JOIN_REQ_EXPAND_THRESHOLD:
            expanded = self.bump_tx_power()
            # Reset counter after an expansion attempt to avoid runaway growth
            self.join_request_times = []
            if expanded:
                self.log(
                    f"Increasing TX power after {JOIN_REQ_EXPAND_THRESHOLD} join requests.")

    def _max_cluster_distance(self):
        """
        Return the max neighbor distance we should cover for our cluster:
        parent, in-net neighbors, members we know about, and pending joiners.
        """
        max_dist = self.max_pending_join_distance

        parent_entry = self.neighbors_table.get(self.parent_gui)
        if parent_entry and parent_entry.get('distance') is not None:
            max_dist = max(max_dist, parent_entry['distance'])

        my_net = self.ch_addr.net_addr if self.ch_addr is not None else (
            self.addr.net_addr if self.addr is not None else None)

        # Consider neighbors already on our net
        if my_net is not None:
            for neigh in self.neighbors_table.values():
                neigh_net = None
                neigh_addr = neigh.get('addr')
                if neigh_addr is not None and hasattr(neigh_addr, "net_addr"):
                    neigh_net = neigh_addr.net_addr
                elif neigh.get('ch_addr') is not None:
                    neigh_net = neigh['ch_addr'].net_addr
                if neigh_net == my_net and neigh.get('distance') is not None:
                    max_dist = max(max_dist, neigh['distance'])

        # Consider members_table addresses by matching to neighbor entries for distance
        for member_addr in self.members_table:
            for neigh in self.neighbors_table.values():
                neigh_addr = neigh.get('addr') or neigh.get('source')
                try:
                    same = neigh_addr.is_equal(member_addr)
                except Exception:
                    same = neigh_addr == member_addr
                if same and neigh.get('distance') is not None:
                    max_dist = max(max_dist, neigh['distance'])
                    break

        return max_dist

    def _has_dependents(self):
        """Check if this node (CH/Router) has children or downstream networks."""
        # Any assigned IDs in node_available_dict?
        has_ids = any(val is not None for val in self.node_available_dict.values(
        )) if self.node_available_dict else False
        has_members = bool(self.members_table)
        has_child_networks = bool(self.child_networks_table)
        return has_ids or has_members or has_child_networks

    def demote_to_registered(self):
        """Step down from CH/Router to Registered when redundant."""
        # Example: CH with no children demotes to REGISTERED, removes TX range circle, resets to default TX power
        self.remove_tx_range()
        self.ch_addr = None
        self.node_available_dict = {}
        self.child_networks_table = {}
        self.members_table = []
        self.assign_tx_power(NODE_DEFAULT_TX_POWER)
        self.set_role(Roles.REGISTERED)
        # Ensure continued heartbeats and notify neighbors of new role
        self.send_heart_beat()
        self.set_timer('TIMER_HEART_BEAT', HEART_BEAT_INTERVAL)

    def optimize_role_choice(self):
        """
        After a grace period, decide if we can step down to reduce overlap.
        - Cluster Heads: if covered by parent CH/ROOT and no dependents, demote to Registered.
        - Routers: if covered by parent CH/ROOT and no dependents, demote to Registered.
        """
        if self.role not in (Roles.CLUSTER_HEAD, Roles.ROUTER):
            return

        parent_entry = self.neighbors_table.get(self.parent_gui)
        parent_role = parent_entry.get('role') if parent_entry else None
        covered_by_cluster = parent_role in (Roles.CLUSTER_HEAD, Roles.ROOT)
        connected = covered_by_cluster or (self.hop_count < 99999)

        if not self._has_dependents() and connected and self.role != Roles.ROOT:
            self.log(
                f"Demoting {self.role.name} to REGISTERED to reduce overlap")
            self.demote_to_registered()
            return

        # Re-schedule to keep checking as topology changes
        self.set_timer('TIMER_ROLE_OPTIMIZE', ROLE_OPTIMIZE_TIME)

    ###################
    def update_neighbor(self, pck):
        """Update neighbor table from HEART_BEAT packet."""
        # Example: Updates neighbor distance/role from HEART_BEAT, enforces topology constraints (no leaf→router, no router→router)
        pck = pck.copy()
        pck['arrival_time'] = self.now

        if pck['gui'] in NODE_POS and self.id in NODE_POS:
            x1, y1 = NODE_POS[self.id]
            x2, y2 = NODE_POS[pck['gui']]
            pck['distance'] = math.hypot(x1 - x2, y1 - y2)

        pck['neighbor_hop_count'] = 1
        self.neighbors_table[pck['gui']] = pck

        # Constraint: REGISTERED nodes cannot attach to routers - only CLUSTER_HEAD or ROOT
        # Routers cannot attach to other routers - only CLUSTER_HEAD or ROOT
        neighbor_role = pck.get('role')
        can_be_parent = True

        if self.role in (Roles.REGISTERED, Roles.UNREGISTERED):
            # Leaf nodes must point to CH/ROOT, never routers
            if neighbor_role == Roles.ROUTER:
                can_be_parent = False
            # If our current parent just became a router, drop it and re-join.
            if self.parent_gui == pck['gui'] and neighbor_role == Roles.ROUTER:
                self.log(
                    f"Dropping router parent {self.parent_gui}; rejoining.")
                self.erase_parent()
                self.parent_gui = None
                self.ch_addr = None
                self.set_role(Roles.UNREGISTERED)
                self.set_timer('TIMER_JOIN_REQUEST', JOIN_REQUEST_INTERVAL)
                can_be_parent = False
        elif self.role == Roles.ROUTER:
            # Routers can only attach to CLUSTER_HEAD or ROOT, not other routers
            if neighbor_role == Roles.ROUTER:
                can_be_parent = False
            # If our current parent became a router, drop and rejoin a proper CH/ROOT.
            if self.parent_gui == pck['gui'] and neighbor_role == Roles.ROUTER:
                self.log(
                    f"Dropping router parent {self.parent_gui}; rejoining.")
                self.erase_parent()
                self.parent_gui = None
                self.ch_addr = None
                self.set_role(Roles.UNREGISTERED)
                self.set_timer('TIMER_JOIN_REQUEST', JOIN_REQUEST_INTERVAL)
                can_be_parent = False

        if can_be_parent and (pck['gui'] not in self.child_networks_table.keys() or pck['addr'] not in self.members_table):
            # Find existing entry by GUI ID (safer than comparing Addr objects that might be None)
            existing_idx = None
            for idx, d in enumerate(self.candidate_parents_table):
                if d.get('gui') == pck['gui']:
                    existing_idx = idx
                    break
            
            if existing_idx is not None:
                existing = self.candidate_parents_table[existing_idx]
                if pck['arrival_time'] > existing.get('arrival_time', 0):
                    # Remove by index to avoid Addr comparison issues with None values
                    self.candidate_parents_table.pop(existing_idx)
                    self.candidate_parents_table.append(pck)
            else:
                self.candidate_parents_table.append(pck)

    ###################
    def select_and_join(self):
        """Select best parent from candidate_parents_table and send JOIN_REQUEST."""
        # Example: Picks closest CLUSTER_HEAD (not ROUTER), sends JOIN_REQUEST, waits for JOIN_REPLY with assigned address
        min_hop = 99999
        min_hop_gui = 99999

        for candidate in self.candidate_parents_table:
            gui = candidate['gui']
            attempts = self.join_req_attempts.get(gui, 0)
            if attempts >= self.jr_threshold:
                continue

            # Additional constraint check: filter out routers for REGISTERED/UNREGISTERED nodes
            # and filter out routers for routers
            neighbor_entry = self.neighbors_table.get(gui)
            if neighbor_entry:
                neighbor_role = neighbor_entry.get('role')
                if self.role in (Roles.REGISTERED, Roles.UNREGISTERED):
                    # Leaf nodes can only attach to CLUSTER_HEAD or ROOT, not routers
                    if neighbor_role == Roles.ROUTER:
                        continue
                # UNREGISTERED nodes CAN attach to Routers (triggering Router -> Proxy Parent)
                elif self.role == Roles.ROUTER:
                    # Routers cannot attach to other routers
                    if neighbor_role == Roles.ROUTER:
                        continue

            if (self.neighbors_table[gui]['hop_count'] < min_hop or
                    (self.neighbors_table[gui]['hop_count'] == min_hop and gui < min_hop_gui)):
                min_hop = self.neighbors_table[gui]['hop_count']
                min_hop_gui = gui

        if min_hop_gui < 99999:
            self.join_req_attempts[min_hop_gui] = self.join_req_attempts.get(
                min_hop_gui, 0) + 1
            selected_addr = self.neighbors_table[min_hop_gui]['source']
            self.send_join_request(selected_addr)

        self.set_timer('TIMER_JOIN_REQUEST', JOIN_REQUEST_INTERVAL)

    ###################
    def send_probe(self):
        """Broadcast PROBE to discover neighbors."""
        # Example: UNREGISTERED node broadcasts PROBE, neighbors respond with HEART_BEAT containing their role/distance
        self.send({'dest': wsn.BROADCAST_ADDR, 'type': 'PROBE'})

    ###################
    def send_heart_beat(self):
        """Broadcast HEART_BEAT with neighbor table, role, and address info."""
        # Example: CH/ROOT broadcasts HEART_BEAT with mesh_table, neighbors update distance/role, triggers neighbor discovery
        # Re-evaluate TX power before advertising (helps shrink overlap when cluster contracts)
        if self.role in (Roles.CLUSTER_HEAD, Roles.ROOT):
            prev_power = getattr(self, "tx_power", NODE_DEFAULT_TX_POWER)
            self.assign_tx_power()
            if self.role == Roles.CLUSTER_HEAD and self.tx_power != prev_power:
                self.draw_tx_range()
        self.send({
            'dest': wsn.BROADCAST_ADDR,
            'type': 'HEART_BEAT',
            'source': self.ch_addr if self.ch_addr is not None else self.addr,
            'gui': self.id,
            'role': self.role,
            'addr': self.addr,
            'ch_addr': self.ch_addr,
            'hop_count': self.hop_count,
        })

    ###################
    def send_join_request(self, dest):
        self.send({'dest': dest, 'type': 'JOIN_REQUEST', 'gui': self.id})

    ###################
    def send_join_reply(self, gui, addr):
        """Send JOIN_REPLY to node with given GUI, assigning address addr."""
        # Example: CH assigns (NetID, NodeID) to joining node, includes TX power level for child to adopt
        # Use ch_addr if available, otherwise use addr (for routers)
        source_addr = self.ch_addr if self.ch_addr is not None else self.addr
        if source_addr is None:
            self.log("Warning: Cannot send JOIN_REPLY - no valid source address")
            return
        
        self.send({
            'dest': wsn.BROADCAST_ADDR,
            'type': 'JOIN_REPLY',
            'source': source_addr,
            'gui': self.id,
            'dest_gui': gui,
            'addr': addr,
            'root_addr': self.root_addr,
            'tx_power': getattr(self, "tx_power", NODE_DEFAULT_TX_POWER),
            'hop_count': self.hop_count + 1,
        })

    ###################
    def send_join_ack(self, dest):
        # Ensure dest is not None - use BROADCAST if dest is invalid
        if dest is None:
            dest = wsn.BROADCAST_ADDR
        
        # Ensure source address exists - routers might not have addr yet
        source_addr = self.addr
        if source_addr is None:
            # If no address, try to use ch_addr or create a temporary one
            if self.ch_addr is not None:
                source_addr = self.ch_addr
            else:
                # Can't send without a valid source - skip this ACK
                self.log("Warning: Cannot send JOIN_ACK - no valid source address")
                return
        
        self.send({'dest': dest, 'type': 'JOIN_ACK',
                  'source': source_addr, 'gui': self.id})

    ###################
    def route_and_forward_package(self, pck):
        """Routing and forwarding given package (TREE / DIRECT / MESH)."""
        # Example: Routes DATA packet to dest_gui using mesh table first, falls back to tree routing via parent
        path_type = "UNKNOWN"

        # Default: route up the tree via parent
        if self.role != Roles.ROOT and self.parent_gui in self.neighbors_table:
            parent_entry = self.neighbors_table.get(self.parent_gui)
            if parent_entry:
                if parent_entry['role'] == Roles.ROUTER and parent_entry.get('addr'):
                    pck['next_hop'] = parent_entry['addr']
                else:
                    pck['next_hop'] = parent_entry.get(
                        'ch_addr') or parent_entry.get('addr')
                path_type = "TREE"

        # Direct or child cluster routing
        if self.ch_addr is not None and pck.get('dest') is not None:
            if pck['dest'].net_addr == self.ch_addr.net_addr:
                pck['next_hop'] = pck['dest']
                path_type = "TREE"
            else:
                for child_gui, child_networks in self.child_networks_table.items():
                    if pck['dest'].net_addr in child_networks:
                        pck['next_hop'] = self.neighbors_table[child_gui]['addr']
                        path_type = "TREE"
                        break
        elif self.role == Roles.ROUTER and pck.get('dest') is not None:
            for child_gui, child_networks in self.child_networks_table.items():
                if pck['dest'].net_addr in child_networks:
                    pck['next_hop'] = self.neighbors_table[child_gui]['addr']
                    path_type = "TREE"
                    break

        # Try direct / mesh based on neighbors_table
        # Restrictions: REGISTERED cannot directly talk to ROUTER, ROUTER cannot directly talk to ROUTER or REGISTERED
        dest = pck.get('dest')
        neighbor_match = None
        member_match = None

        if dest is not None:
            neighbor_match = next(
                (entry for entry in self.neighbors_table.values()
                 if entry['addr'] == dest),
                None
            )
            if not neighbor_match:
                member_match = next(
                    (entry for entry in self.members_table if entry == dest),
                    None
                )

        match = neighbor_match or member_match
        if match:
            # Get the neighbor's role from the match
            # neighbor_match is a dict with 'role', member_match is an Addr object
            if neighbor_match:
                neighbor_role = neighbor_match.get('role')
            else:
                # member_match is an address - look up the role from neighbors_table
                # Find the neighbor entry by matching the address
                neighbor_entry = next(
                    (entry for entry in self.neighbors_table.values()
                     if entry.get('addr') == member_match),
                    None
                )
                neighbor_role = neighbor_entry.get(
                    'role') if neighbor_entry else None

            # Check restrictions for direct/mesh communication
            can_communicate_directly = True

            # Only apply restrictions if we have a valid neighbor_role
            if neighbor_role is not None:
                # REGISTERED nodes cannot directly communicate with ROUTER
                if self.role == Roles.REGISTERED and neighbor_role == Roles.ROUTER:
                    can_communicate_directly = False

                # ROUTER cannot directly communicate with ROUTER
                elif self.role == Roles.ROUTER and neighbor_role == Roles.ROUTER:
                    can_communicate_directly = False

                # ROUTER cannot directly communicate with REGISTERED
                elif self.role == Roles.ROUTER and neighbor_role == Roles.REGISTERED:
                    can_communicate_directly = False

            if can_communicate_directly:
                if neighbor_match and neighbor_match.get('neighbor_hop_count', 1) > 1:
                    pck['next_hop'] = neighbor_match.get('next_hop', dest)
                    path_type = "MESH"
                else:
                    pck['next_hop'] = dest
                    path_type = "DIRECT"

        next_hop_str = str(pck.get('next_hop', 'UNKNOWN'))
        log_packet_route(pck, self, next_hop_str, path_type)
        self.send(pck)

    ###################
    def send_network_request(self):
        self.route_and_forward_package({
            'dest': self.root_addr,
            'type': 'NETWORK_REQUEST',
            'source': self.addr,
        })

    ###################
    def send_network_reply(self, dest, addr):
        self.route_and_forward_package({
            'dest': dest,
            'type': 'NETWORK_REPLY',
            'source': self.addr,
            'addr': addr,
        })

    ###################
    def send_network_update(self):
        """Broadcast network topology updates to children."""
        # Example: CH sends NETWORK_UPDATE with child_networks_table, enabling downstream routing to child clusters
        if self.ch_addr is None:
            child_networks = []
        else:
            child_networks = [self.ch_addr.net_addr]

        for networks in self.child_networks_table.values():
            child_networks.extend(networks)

        dest_entry = self.neighbors_table.get(self.parent_gui)
        if dest_entry is None:
            return

        dest = dest_entry.get('ch_addr') or dest_entry.get('source')
        self.send({
            'dest': dest,
            'type': 'NETWORK_UPDATE',
            'source': self.addr,
            'gui': self.id,
            'child_networks': child_networks,
        })

    ###################
    def send_sensor_data(self):
        """Send a random SENSOR_DATA packet to one of our neighbors."""
        if self.neighbors_table:
            rand_key = random.choice(list(self.neighbors_table.keys()))
            self.route_and_forward_package({
                'dest': self.neighbors_table[rand_key]['addr'],
                'type': 'SENSOR_DATA',
                'source': self.addr,
                'gui': self.id,
                'sensor_value': random.uniform(0, 100),
            })

    ###################
    def send_table_share(self):
        """Share neighbor table within MESH_HOP_N hops with 1-hop neighbors."""
        # Example: Sends MESH_TABLE_SHARE packet to neighbors, enabling multi-hop mesh routing discovery
        # Skip if we don't have a valid source address
        if self.addr is None:
            return
        
        mesh_neighbors = {}
        for neighbor, packet in self.neighbors_table.items():
            if packet['neighbor_hop_count'] <= MESH_HOP_N:
                mesh_neighbors[neighbor] = packet

        for neighbor in self.neighbors_table.values():
            # Only send to 1-hop neighbors with valid source addresses
            if (neighbor['neighbor_hop_count'] == 1 and 
                neighbor.get('source') is not None):
                self.send({
                    'dest': neighbor['source'],
                    'type': 'TABLE_SHARE',
                    'source': self.addr,
                    'gui': self.id,
                    'neighbors': mesh_neighbors,
                })

    ###################
    def maybe_log_packet_delivery(self, pck):
        """Log packet delivery if this node is the final destination."""
        # Example: Records packet_id, delay, path to packet_log when dest_gui matches this node's ID
        is_final_dest = False
        dest = pck.get('dest')

        if dest is not None:
            if self.addr and dest.is_equal(self.addr):
                is_final_dest = True
            elif self.ch_addr and dest.is_equal(self.ch_addr):
                is_final_dest = True

        if is_final_dest and 'creation_time' in pck:
            delay = self.now - pck['creation_time']
            path = list(pck.get('path', []))
            if not path or path[-1] != self.id:
                path.append(self.id)

            self.sim.packet_log.append({
                "pkt_id": pck.get("pkt_id"),
                "type": pck.get("type"),
                "source_gui": pck.get("source_gui"),
                "dest_gui": pck.get("dest_gui"),
                "created_at": pck.get("creation_time"),
                "received_at": self.now,
                "delay": delay,
                "path": path,
            })

    ###################
    def on_receive(self, pck):
        """Handle all packet types."""
        # Example: Processes HEART_BEAT, JOIN_REQUEST, DATA packets; consumes RX energy; may trigger role changes
        # Per-packet RX energy (8) - aligned with TX formula
        N = ENERGY_PSDU_BYTES
        I_A = RX_CURRENT / 1000.0
        bits = 8 * (N + 6)
        base_E = VOLTAGE * I_A * (bits / DATARATE)
        rx_overhead = RX_TURNAROUND_ENERGY_J
        dE = base_E + rx_overhead

        # Track energy metrics
        self.rx_energy_consumed += dE
        self.rx_packet_count += 1

        self.power -= dE
        # Root node cannot die from energy depletion
        if self.power <= MIN_ENERGY_J and self.id != ROOT_ID:
            self._die_of_energy()
            # Let this packet finish processing, future ones are dropped

        # Log delivery if this is the final destination
        self.maybe_log_packet_delivery(pck)

        # ROOT / CLUSTER_HEAD
        if self.role in (Roles.ROOT, Roles.CLUSTER_HEAD):
            dest = pck.get('dest')
            if 'next_hop' in pck:
                # If dest is missing, just route it
                if dest is None:
                    self.route_and_forward_package(pck)
                    return
                # Only compare if our addresses are not None
                is_for_me = (
                    (self.addr is not None and dest == self.addr) or
                    (self.ch_addr is not None and dest == self.ch_addr)
                )
                if not is_for_me:
                    self.route_and_forward_package(pck)
                    return

            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)

            if pck['type'] == 'PROBE':
                self.send_heart_beat()

            if pck['type'] == 'JOIN_REQUEST':
                # Track join interest; expand power if many requests arrive in a burst.
                self.record_join_request_and_maybe_expand()
                # Ensure we can actually reach the requester; bump power just enough.
                if self.id in NODE_POS and pck['gui'] in NODE_POS:
                    dist = math.hypot(
                        NODE_POS[self.id][0] - NODE_POS[pck['gui']][0],
                        NODE_POS[self.id][1] - NODE_POS[pck['gui']][1],
                    )
                    self.max_pending_join_distance = max(
                        self.max_pending_join_distance, dist)
                    if dist > getattr(self, "tx_range", 0):
                        desired_power = _min_power_for_distance(dist)
                        if desired_power != getattr(self, "tx_power", None):
                            self.assign_tx_power(desired_power)
                            if self.role == Roles.CLUSTER_HEAD:
                                self.draw_tx_range()
                # CH / ROOT assigns child address
                avail_node_id = None
                for node_id, avail in self.node_available_dict.items():
                    if avail is None or avail == pck['gui']:
                        avail_node_id = node_id
                        break
                if avail_node_id is not None:
                    self.node_available_dict[avail_node_id] = pck['gui']
                    self.send_join_reply(
                        pck['gui'],
                        wsn.Addr(self.ch_addr.net_addr, avail_node_id),
                    )

            if pck['type'] == 'NETWORK_REQUEST' and self.role == Roles.ROOT:
                avail_net_id = None
                for net_id, avail in self.net_id_available_dict.items():
                    if avail is None or avail == pck['source']:
                        avail_net_id = net_id
                        break
                new_addr = wsn.Addr(avail_net_id, 254)
                self.net_id_available_dict[avail_net_id] = pck['source']
                self.send_network_reply(pck['source'], new_addr)

            if pck['type'] == 'JOIN_ACK':
                self.members_table.append(pck['source'])
                if self.role == Roles.CLUSTER_HEAD:
                    if self.ch_transfer_target is not None and self.transfer_engaged is None:
                        target_addr = None
                        for gui in self.received_JR_guis:
                            if gui == self.ch_transfer_target:
                                for node_id, assigned_gui in self.node_available_dict.items():
                                    if assigned_gui == gui:
                                        target_addr = wsn.Addr(
                                            self.ch_addr.net_addr, node_id)
                                        break
                                break

                        if target_addr and pck['source'] == target_addr:
                            self.send_ch_nomination()
                            self.transfer_engaged = True

            if self.role == Roles.CLUSTER_HEAD and pck['type'] == 'CH_NOMINATION_ACK':
                if getattr(self, 'awaiting_ack', False) and getattr(self, 'ch_nominee', None):
                    if (pck['source'].net_addr == self.ch_nominee[0] and
                            pck['source'].node_addr == self.ch_nominee[1]):
                        self.log("CH nomination ACK received; becoming router")
                        self.become_router()
                        self.awaiting_ack = False
                        self.ch_nominee = None

            if pck['type'] == 'NETWORK_UPDATE':
                self.child_networks_table[pck['gui']] = pck['child_networks']
                if self.role != Roles.ROOT:
                    self.send_network_update()

            if pck['type'] == 'TABLE_SHARE' and self.role != Roles.ROOT:
                for neighbor, packet in pck['neighbors'].items():
                    if neighbor not in self.neighbors_table and neighbor != self.id:
                        cpy = packet.copy()
                        cpy['neighbor_hop_count'] += 1
                        cpy['next_hop'] = pck['source']
                        self.neighbors_table[neighbor] = cpy
                        if cpy['neighbor_hop_count'] > MESH_HOP_N + 1:
                            raise Exception("Something went wrong")

            if pck['type'] == 'SENSOR_DATA':
                pass

        # REGISTERED
        elif self.role == Roles.REGISTERED:
            dest = pck.get('dest')
            if 'next_hop' in pck:
                # If dest is missing, just route it
                if dest is None:
                    self.route_and_forward_package(pck)
                    return
                # Only compare if our addresses are not None
                is_for_me = (
                    (self.addr is not None and dest == self.addr) or
                    (self.ch_addr is not None and dest == self.ch_addr)
                )
                if not is_for_me:
                    self.route_and_forward_package(pck)
                    return

            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)

            if pck['type'] == 'PROBE':
                self.send_heart_beat()

            if pck['type'] == 'JOIN_REQUEST':
                self.received_JR_guis.append(pck['gui'])
                self.ch_transfer_target = pck['gui']
                self.send_network_request()

            if pck['type'] == 'TABLE_SHARE':
                for neighbor, packet in pck['neighbors'].items():
                    if neighbor not in self.neighbors_table and neighbor != self.id:
                        cpy = packet.copy()
                        cpy['neighbor_hop_count'] += 1
                        cpy['next_hop'] = pck['source']
                        self.neighbors_table[neighbor] = cpy
                        if cpy['neighbor_hop_count'] > MESH_HOP_N + 1:
                            raise Exception("Something went wrong")

            if pck['type'] == 'NETWORK_REPLY':
                self.set_role(Roles.CLUSTER_HEAD)
                check_all_nodes_registered()
                try:
                    write_clusterhead_distances_csv(
                        "clusterhead_distances.csv")
                except Exception as e:
                    self.log(f"CH CSV export error: {e}")
                self.set_ch_address(pck['addr'])
                self.send_network_update()
                self.node_available_dict = {
                    i: None for i in range(1, NUM_OF_CHILDREN + 1)}

                self.send_heart_beat()
                for gui in self.received_JR_guis:
                    avail_node_id = None
                    for node_id, avail in self.node_available_dict.items():
                        if avail is None or avail == gui:
                            avail_node_id = node_id
                            break
                    if avail_node_id is not None:
                        self.node_available_dict[avail_node_id] = gui
                        self.send_join_reply(gui, wsn.Addr(
                            self.ch_addr.net_addr, avail_node_id))

            if pck['type'] == 'CH_NOMINATION':
                self.send_ch_nom_ack(pck)
                self.set_role(Roles.CLUSTER_HEAD)
                self.set_ch_address(pck['addr'])
                self.send_network_update()
                self.node_available_dict = pck['avail_dict']

        # ROUTER
        elif self.role == Roles.ROUTER:
            dest = pck.get('dest')
            if 'next_hop' in pck:
                # If dest is missing, just route it
                if dest is None:
                    self.route_and_forward_package(pck)
                    return
                # Only compare if our addresses are not None
                is_for_me = (
                    (self.addr is not None and dest == self.addr) or
                    (self.ch_addr is not None and dest == self.ch_addr)
                )
                if not is_for_me:
                    self.route_and_forward_package(pck)
                    return

            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)

            if pck['type'] == 'PROBE':
                self.send_heart_beat()

            if pck['type'] == 'TABLE_SHARE':
                for neighbor, packet in pck['neighbors'].items():
                    if neighbor not in self.neighbors_table and neighbor != self.id:
                        cpy = packet.copy()
                        cpy['neighbor_hop_count'] += 1
                        cpy['next_hop'] = pck['source']
                        self.neighbors_table[neighbor] = cpy
                        if cpy['neighbor_hop_count'] > MESH_HOP_N + 1:
                            raise Exception("Something went wrong")

            if pck['type'] == 'NETWORK_UPDATE':
                self.child_networks_table[pck['gui']] = pck['child_networks']
                self.send_network_update()

            if pck['type'] == 'JOIN_REQUEST':
                # Orphan trying to join!
                # Keep it simple: adopt the child as a router child without spawning a new CH.
                self.log(
                    f"Received JOIN_REQUEST from orphan {pck['gui']}. Adopting without promotion.")

                # Find an available ID from the TOP (254 down) to minimize collision with CH's low IDs
                avail_node_id = None
                for i in range(NUM_OF_CHILDREN, 0, -1):
                    if self.node_available_dict.get(i) is None:
                        avail_node_id = i
                        break

                if avail_node_id is not None:
                    self.node_available_dict[avail_node_id] = pck['gui']
                    # Use our existing net; bias to high IDs to avoid clashes with CH-assigned low IDs.
                    # Router must have an address to assign child addresses
                    if self.addr is None:
                        self.log("Warning: Router cannot assign address - no addr available")
                        return
                    self.send_join_reply(pck['gui'], wsn.Addr(
                        self.addr.net_addr, avail_node_id))
                    pass
                    # Router adopts orphan: assigns high IDs (254 down) to minimize collision with CH-assigned low IDs.
                    # Router stays as Router (doesn't promote to CH) to avoid creating extra clusters/overlap.

        # UNDICOVERED
        elif self.role == Roles.UNDISCOVERED:
            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)
                self.kill_timer('TIMER_PROBE')
                self.become_unregistered()

        # UNREGISTERED
        elif self.role == Roles.UNREGISTERED:
            if pck['type'] == 'HEART_BEAT':
                self.update_neighbor(pck)

            if pck['type'] == 'JOIN_REPLY' and pck['dest_gui'] == self.id:
                # Constraint: REGISTERED nodes cannot attach to routers
                # Check if the sender is a router - if so, reject this JOIN_REPLY
                sender_gui = pck['gui']
                sender_entry = self.neighbors_table.get(sender_gui)
                if sender_entry:
                    sender_role = sender_entry.get('role')
                    # If sender is a router, reject - leaf nodes must join CLUSTER_HEAD or ROOT
                    if sender_role == Roles.ROUTER:
                        # Reject this JOIN_REPLY - don't attach to router
                        return

                self.set_address(pck['addr'])
                self.parent_gui = pck['gui']
                self.root_addr = pck['root_addr']
                self.hop_count = pck['hop_count']
                # Adopt the cluster's TX power advertised by CH/ROOT
                advertised_tx = pck.get('tx_power')
                if advertised_tx is not None:
                    self.assign_tx_power(advertised_tx)
                else:
                    # Fallback to existing behavior
                    self.assign_tx_power()
                self.draw_parent()
                self.kill_timer('TIMER_JOIN_REQUEST')
                self.send_heart_beat()
                self.set_timer('TIMER_HEART_BEAT', HEART_BEAT_INTERVAL)
                # Only schedule sensor data timer if enabled
                if ENABLE_DATA_PACKETS:
                    self.set_timer('TIMER_SENSOR', DATA_INTERVAL)
                self.send_join_ack(pck['source'])

                if self.ch_addr is not None:
                    self.set_role(Roles.CLUSTER_HEAD)
                    self.send_network_update()
                else:
                    self.set_role(Roles.REGISTERED)
                    self.register()
                    check_all_nodes_registered()
                    self.set_timer('TIMER_TABLE_SHARE', TABLE_SHARE_INTERVAL)

            if pck['type'] == 'CH_NOMINATION':
                self.send_ch_nom_ack(pck)
                self.set_role(Roles.CLUSTER_HEAD)
                self.set_ch_address(pck['addr'])
                self.send_network_update()
                self.node_available_dict = {
                    i: None for i in range(1, NUM_OF_CHILDREN + 1)}

    ###################
    def on_timer_fired(self, name, *args, **kwargs):
        """Executes when a timer fired."""
        # Example: Handles TIMER_ARRIVAL (wake up), TIMER_JOIN_REQUEST (retry join), TIMER_HEART_BEAT (periodic updates), TIMER_SENSOR (data packets)
        if name == 'TIMER_ARRIVAL':
            self.scene.nodecolor(self.id, 1, 0, 0)
            self.wake_up()
            self.wake_up_time = self.now
            self.set_timer('TIMER_PROBE', 1)

        elif name == 'TIMER_PROBE':
            if self.c_probe < self.th_probe:
                self.send_probe()
                self.c_probe += 1
                self.set_timer('TIMER_PROBE', 1)
            else:
                if self.is_root_eligible:
                    self.set_role(Roles.ROOT)
                    self.scene.nodecolor(self.id, 0, 0, 0)
                    self.set_address(wsn.Addr(0, 254))
                    self.set_ch_address(wsn.Addr(0, 254))
                    self.root_addr = self.addr
                    self.hop_count = 0
                    self.net_id_available_dict = {
                        i: None for i in range(1, NUM_OF_CLUSTERS)}
                    self.node_available_dict = {
                        i: None for i in range(1, NUM_OF_CHILDREN + 1)}
                    self.set_timer('TIMER_HEART_BEAT', HEART_BEAT_INTERVAL)
                else:
                    self.c_probe = 0
                    self.set_timer('TIMER_PROBE', 30)

        elif name == 'TIMER_HEART_BEAT':
            self.send_heart_beat()
            self.set_timer('TIMER_HEART_BEAT', HEART_BEAT_INTERVAL)

        elif name == 'TIMER_JOIN_REQUEST':
            if len(self.candidate_parents_table) == 0:
                self.become_unregistered()
            else:
                self.select_and_join()
        elif name == 'TIMER_ROLE_OPTIMIZE':
            self.optimize_role_choice()

        elif name == 'TIMER_TABLE_SHARE':
            self.send_table_share()
            self.set_timer('TIMER_TABLE_SHARE', TABLE_SHARE_INTERVAL)

        elif name == 'TIMER_SENSOR':
            self.send_sensor_data()
            self.set_timer('TIMER_SENSOR', DATA_INTERVAL)

        elif name == 'TIMER_EXPORT_CH_CSV':
            if self.role == Roles.ROOT:
                write_clusterhead_distances_csv("clusterhead_distances.csv")
                self.set_timer('TIMER_EXPORT_CH_CSV',
                               config.EXPORT_CH_CSV_INTERVAL)

        elif name == 'TIMER_EXPORT_NEIGHBOR_CSV':
            if self.role == Roles.ROOT:
                write_neighbor_distances_csv("neighbor_distances.csv")
                self.set_timer('TIMER_EXPORT_NEIGHBOR_CSV',
                               config.EXPORT_NEIGHBOR_CSV_INTERVAL)


ROOT_ID = random.randrange(config.SIM_NODE_COUNT)  # 0..count-1


def write_node_distances_csv(path="node_distances.csv"):
    """Write pairwise node-to-node Euclidean distances as an edge list."""
    ids = sorted(NODE_POS.keys())
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source_id", "target_id", "distance"])
        for i, sid in enumerate(ids):
            x1, y1 = NODE_POS[sid]
            for tid in ids[i + 1:]:
                x2, y2 = NODE_POS[tid]
                dist = math.hypot(x1 - x2, y1 - y2)
                w.writerow([sid, tid, f"{dist:.6f}"])


def write_node_distance_matrix_csv(path="node_distance_matrix.csv"):
    ids = sorted(NODE_POS.keys())
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["node_id"] + ids)
        for sid in ids:
            x1, y1 = NODE_POS[sid]
            row = [sid]
            for tid in ids:
                x2, y2 = NODE_POS[tid]
                dist = math.hypot(x1 - x2, y1 - y2)
                row.append(f"{dist:.6f}")
            w.writerow(row)


def write_clusterhead_distances_csv(path="clusterhead_distances.csv"):
    """Write pairwise distances between current cluster heads."""
    clusterheads = []
    for node in sim.nodes:
        if hasattr(node, "role") and node.role == Roles.CLUSTER_HEAD and node.id in NODE_POS:
            x, y = NODE_POS[node.id]
            clusterheads.append((node.id, x, y))

    if len(clusterheads) < 2:
        with open(path, "w", newline="") as f:
            csv.writer(f).writerow(
                ["clusterhead_1", "clusterhead_2", "distance"])
        return

    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["clusterhead_1", "clusterhead_2", "distance"])
        for i, (id1, x1, y1) in enumerate(clusterheads):
            for id2, x2, y2 in clusterheads[i + 1:]:
                dist = math.hypot(x1 - x2, y1 - y2)
                w.writerow([id1, id2, f"{dist:.6f}"])


def write_neighbor_distances_csv(path="neighbor_distances.csv", dedupe_undirected=True):
    """
    Export neighbor distances per node.
    Each row is (node -> neighbor) with distance from NODE_POS.
    """
    if not NODE_POS:
        raise RuntimeError(
            "NODE_POS is missing; record positions during create_network().")

    seen_pairs = set()

    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "node_id",
            "neighbor_id",
            "distance",
            "neighbor_role",
            "neighbor_hop_count",
            "arrival_time",
        ])

        for node in sim.nodes:
            if not hasattr(node, "neighbors_table"):
                continue

            x1, y1 = NODE_POS.get(node.id, (None, None))
            if x1 is None:
                continue

            for n_gui, pck in getattr(node, "neighbors_table", {}).items():
                if dedupe_undirected:
                    key = (min(node.id, n_gui), max(node.id, n_gui))
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)

                x2, y2 = NODE_POS.get(n_gui, (None, None))
                if x2 is None:
                    continue

                dist = pck.get("distance")
                if dist is None:
                    dist = math.hypot(x1 - x2, y1 - y2)

                n_role = getattr(pck.get("role", None),
                                 "name", pck.get("role", None))
                hop = pck.get("hop_count", pck.get("neighbor_hop_count", ""))
                at = pck.get("arrival_time", "")

                w.writerow([node.id, n_gui, f"{dist:.6f}", n_role, hop, at])


def write_energy_metrics_csv(path="energy_metrics.csv"):
    """Export energy metrics for all nodes."""
    if not ALL_NODES:
        print(f"⚠️  Warning: ALL_NODES is empty, cannot write energy metrics")
        return
    
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "node_id",
            "role",
            "initial_energy_j",
            "final_energy_j",
            "total_energy_consumed_j",
            "tx_energy_consumed_j",
            "rx_energy_consumed_j",
            "tx_packet_count",
            "rx_packet_count",
            "total_packet_count",
            "avg_energy_per_tx_packet_j",
            "avg_energy_per_rx_packet_j",
            "energy_efficiency_j_per_packet",
        ])

        for node in ALL_NODES:
            initial_energy = INITIAL_ENERGY_J
            final_energy = getattr(node, "power", INITIAL_ENERGY_J)
            tx_energy = getattr(node, "tx_energy_consumed", 0.0)
            rx_energy = getattr(node, "rx_energy_consumed", 0.0)
            total_energy = tx_energy + rx_energy
            tx_count = getattr(node, "tx_packet_count", 0)
            rx_count = getattr(node, "rx_packet_count", 0)
            total_count = tx_count + rx_count

            # Calculate averages
            avg_tx = tx_energy / tx_count if tx_count > 0 else 0.0
            avg_rx = rx_energy / rx_count if rx_count > 0 else 0.0
            efficiency = total_energy / total_count if total_count > 0 else 0.0

            role_name = _role_name(getattr(node, "role", None))

            w.writerow([
                node.id,
                role_name,
                f"{initial_energy:.6f}",
                f"{final_energy:.6f}",
                f"{total_energy:.6f}",
                f"{tx_energy:.6f}",
                f"{rx_energy:.6f}",
                tx_count,
                rx_count,
                total_count,
                f"{avg_tx:.9f}",
                f"{avg_rx:.9f}",
                f"{efficiency:.9f}",
            ])


###########################################################
def create_network(node_class, number_of_nodes=100):
    """Creates given number of nodes at random positions with random arrival times."""
    # Example: Creates 100 SensorNode instances in a grid pattern with random jitter
    edge = math.ceil(math.sqrt(number_of_nodes))
    for i in range(number_of_nodes):
        x = i / edge
        y = i % edge
        px = 300 + config.SCALE * x * config.SIM_NODE_PLACING_CELL_SIZE + \
            random.uniform(-1 * config.SIM_NODE_PLACING_CELL_SIZE / 3,
                           config.SIM_NODE_PLACING_CELL_SIZE / 3)
        py = 200 + config.SCALE * y * config.SIM_NODE_PLACING_CELL_SIZE + \
            random.uniform(-1 * config.SIM_NODE_PLACING_CELL_SIZE / 3,
                           config.SIM_NODE_PLACING_CELL_SIZE / 3)
        node = sim.add_node(node_class, (px, py))
        NODE_POS[node.id] = (px, py)
        default_range = TX_RANGES.get(
            NODE_DEFAULT_TX_POWER, config.NODE_TX_RANGE)
        node.tx_range = default_range * config.SCALE
        node.logging = True
        node.arrival = random.uniform(0, config.NODE_ARRIVAL_MAX)
        if node.id == ROOT_ID:
            node.arrival = 0.1


sim = wsn.Simulator(
    duration=config.SIM_DURATION,
    timescale=config.SIM_TIME_SCALE,
    visual=config.SIM_VISUALIZATION,
    terrain_size=config.SIM_TERRAIN_SIZE,
    title=config.SIM_TITLE,
)

# Create network and pre-compute static distance CSVs
create_network(SensorNode, config.SIM_NODE_COUNT)
write_node_distances_csv("node_distances.csv")
write_node_distance_matrix_csv("node_distance_matrix.csv")

# Initialize all CSV files (clear and write headers) before simulation
init_csv_files()

# --- Failure & Recovery Simulation ---
RECOVERY_START_TIME = None
RECOVERY_DURATION = None
MAX_ORPHAN_COUNT = 0


def log_failure_event(time, node_id, event_type):
    """Log failure/recovery events to CSV and track network lifetime (8)."""
    global RECOVERY_DURATION, MAX_ORPHAN_COUNT, NETWORK_DEATH_TIME

    orphan_count = len([n for n in ALL_NODES
                       if getattr(n, "role", None) not in
                       {Roles.REGISTERED, Roles.CLUSTER_HEAD, Roles.ROOT, Roles.ROUTER}])

    if orphan_count > MAX_ORPHAN_COUNT:
        MAX_ORPHAN_COUNT = orphan_count

    # Check if recovery is complete (0 orphans)
    if RECOVERY_START_TIME is not None and RECOVERY_DURATION is None:
        if orphan_count == 0:
            RECOVERY_DURATION = time - RECOVERY_START_TIME
            print(
                f"✅ RECOVERY COMPLETE at time {time:.2f}. Duration: {RECOVERY_DURATION:.2f} sim seconds")

    # Network lifetime tracking (8): check if network death threshold is reached
    if NETWORK_DEATH_TIME is None:
        dead_nodes = [n for n in ALL_NODES if getattr(n, "failed", False)]
        total_nodes = len(ALL_NODES)
        if total_nodes > 0:
            death_ratio = len(dead_nodes) / total_nodes
            # Check if root is dead or threshold percentage is reached
            root_dead = any(n.id == ROOT_ID and n.failed for n in ALL_NODES)
            if root_dead or death_ratio >= NETWORK_DEATH_THRESHOLD:
                NETWORK_DEATH_TIME = time
                print(
                    f"\n💀 NETWORK DEATH at time {time:.2f} ({len(dead_nodes)}/{total_nodes} nodes dead, {death_ratio*100:.1f}%)")

    with open("failures.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([time, node_id, event_type, orphan_count])


def kill_random_node():
    """Kill random non-root node(s) based on NUM_NODES_TO_KILL config."""
    num_to_kill = getattr(config, "NUM_NODES_TO_KILL", 1)
    candidates = [n for n in ALL_NODES if n.id != ROOT_ID and not n.failed]
    
    if not candidates:
        print(f"\n⚠️  No nodes available to kill at time {sim.now}")
        return
    
    # Limit number to kill to available candidates
    num_to_kill = min(num_to_kill, len(candidates))
    
    # Randomly select nodes to kill
    victims = random.sample(candidates, num_to_kill)
    
    print(f"\n💀 KILLING {len(victims)} node(s) at time {sim.now}: {[v.id for v in victims]}")
    
    for victim in victims:
        victim.failed = True
        victim.sleep()
        victim.kill_all_timers()
        victim.scene.nodecolor(victim.id, 0.3, 0.3, 0.3)  # Grey

        # Log the event
        log_failure_event(sim.now, victim.id, "KILLED")

        # Schedule recovery for each victim
        recovery_delay = config.RECOVERY_TIME - config.FAILURE_TIME
        sim.delayed_exec(recovery_delay, recover_node, victim)


def recover_node(node):
    """Recover a previously killed node."""
    global RECOVERY_START_TIME
    print(f"\n🚑 RECOVERING Node #{node.id} at time {sim.now}")
    node.failed = False
    node.wake_up()  # CRITICAL: Must wake up to receive packets!
    RECOVERY_START_TIME = sim.now
    node.scene.nodecolor(node.id, 1, 1, 0)  # Yellow (Unregistered)
    node.become_unregistered()

    # Log the event
    log_failure_event(sim.now, node.id, "RECOVERED")


# Initialize failures log
with open("failures.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["time", "node_id", "event_type", "orphan_count"])


def sample_power_levels():
    """Sample all nodes' power levels and log to CSV."""
    alive_powers = []
    dead_count = 0
    
    for node in ALL_NODES:
        power = getattr(node, "power", None)
        failed = getattr(node, "failed", False)
        
        if power is not None and not failed:
            alive_powers.append(power)
        else:
            dead_count += 1
    
    if alive_powers:
        avg_power = sum(alive_powers) / len(alive_powers)
        min_power = min(alive_powers)
        max_power = max(alive_powers)
    else:
        avg_power = 0.0
        min_power = 0.0
        max_power = 0.0
    
    alive_count = len(alive_powers)
    
    # Write to CSV
    with open("power_over_time.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            sim.now,
            f"{avg_power:.6f}",
            f"{min_power:.6f}",
            f"{max_power:.6f}",
            alive_count,
            dead_count
        ])
    
    # Schedule next sample
    if sim.now + config.POWER_SAMPLING_INTERVAL < sim.duration:
        sim.delayed_exec(config.POWER_SAMPLING_INTERVAL, sample_power_levels)


# Schedule the failure event
sim.delayed_exec(config.FAILURE_TIME, kill_random_node)

# Schedule initial power sampling (start with small delay, then every interval)
# Use 0.1 instead of 0 because SimPy requires delay > 0
sim.delayed_exec(0.1, sample_power_levels)

# Run simulation
start_time = time.time()
sim.run()
end_time = time.time()
runtime = end_time - start_time

# Export logged packets
log_all_packets(sim.packet_log)

# Check convergence and log final topology
converged = log_all_nodes_registered()

print("\n" + "=" * 60)
print("Simulation Finished")
print("=" * 60)
print(f"⏱️  Runtime: {runtime:.2f} seconds ({runtime/60:.2f} minutes)")
print("=" * 60)

# Prominent convergence status
print("\n" + "=" * 60)
if converged:
    print("✅✅✅  Network Convergence stats: SUCCESS  ✅✅✅") #should be impossible for this when energy enabled
    print(f"   All {len(ALL_NODES)} nodes are registered!")
else:
    print(" Network Convergence stats: ")
    unregistered = [n.id for n in ALL_NODES
                    if getattr(n, "role", None) not in
                    {Roles.REGISTERED, Roles.CLUSTER_HEAD, Roles.ROOT, Roles.ROUTER}]
    print(f"   {len(unregistered)} nodes are unregistered by end of sim:")
    print(
        f"   Node IDs: {unregistered[:20]}{'...' if len(unregistered) > 20 else ''}")
print("=" * 60)

# --- Network Statistics ---
print("\n--- Network Statistics ---")

# Join time statistics
if sim.join_times:
    avg_join = sum(sim.join_times) / len(sim.join_times)
    min_join = min(sim.join_times)
    max_join = max(sim.join_times)
    print(f"Join Times: {len(sim.join_times)} nodes joined")
    print(f"  Average: {avg_join:.4f} sim seconds")
    print(f"  Min: {min_join:.4f} sim seconds")
    print(f"  Max: {max_join:.4f} sim seconds")
else:
    print("No join times recorded.")

# Packet delivery statistics
if sim.packet_log:
    total_packets = len(sim.packet_log)
    avg_delay = sum(p['delay'] for p in sim.packet_log) / total_packets
    min_delay = min(p['delay'] for p in sim.packet_log)
    max_delay = max(p['delay'] for p in sim.packet_log)

    type_counts = {}
    for p in sim.packet_log:
        ptype = p['type']
        type_counts[ptype] = type_counts.get(ptype, 0) + 1

    print(f"\nPacket Delivery: {total_packets} packets delivered")
    print(f"  Average delay: {avg_delay:.4f} sim seconds")
    print(f"  Min delay: {min_delay:.4f} sim seconds")
    print(f"  Max delay: {max_delay:.4f} sim seconds")
    print(f"  By type: {type_counts}")
else:
    print("\nNo packets delivered (packet log is empty).")

# Packet Loss Statistics
print("\n--- Packet Loss Statistics ---")
attempts = getattr(sim, "total_tx_attempts", 0)
dropped = getattr(sim, "total_tx_dropped", 0)
if attempts > 0:
    loss_pct = dropped / attempts * 100.0
    configured_pct = config.PACKET_LOSS_RATIO * 100.0
    print(f"  TX attempts: {attempts}")
    print(f"  Dropped by channel: {dropped}")
    print(f"  Realized loss: {loss_pct:.2f}% "
          f"(configured: {configured_pct:.2f}%)")
    
    # Save packet loss stats for graph generation
    try:
        with open("packet_loss_stats.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["configured_loss_pct", "realized_loss_pct", "attempts", "dropped"])
            writer.writerow([configured_pct, loss_pct, attempts, dropped])
    except Exception:
        pass
else:
    print("  No transmissions recorded (no attempts).")

# Failure Recovery Statistics
print("\n--- Failure Recovery Statistics ---")
# Final check for recovery completion if recovery started but wasn't marked complete
if RECOVERY_START_TIME is not None and RECOVERY_DURATION is None:
    orphan_count = len([n for n in ALL_NODES
                       if getattr(n, "role", None) not in
                       {Roles.REGISTERED, Roles.CLUSTER_HEAD, Roles.ROOT, Roles.ROUTER}])
    if orphan_count == 0:
        RECOVERY_DURATION = sim.now - RECOVERY_START_TIME
        print(f"✅ RECOVERY COMPLETE (detected at end of simulation)")
    else:
        print(f"⚠️  Recovery started but not completed: {orphan_count} nodes still unregistered")

if RECOVERY_DURATION is not None:
    print(f"⏱️  Time to Recover: {RECOVERY_DURATION:.2f} sim seconds")
elif RECOVERY_START_TIME is not None:
    print(f"⏱️  Time to Recover: (recovery started at {RECOVERY_START_TIME:.2f}, ended at {sim.now:.2f})")
    orphan_count = len([n for n in ALL_NODES
                       if getattr(n, "role", None) not in
                       {Roles.REGISTERED, Roles.CLUSTER_HEAD, Roles.ROOT, Roles.ROUTER}])
    print(f"   {orphan_count} nodes still unregistered at end of simulation")
else:
    print("⏱️  Time to Recover: N/A (Recovery not started - no node was killed/recovered)")
print(f"⚠️  Max Orphan Count: {MAX_ORPHAN_COUNT}")

# Network Lifetime Statistics (8) - Maximize Network Life Metric
print("\n" + "=" * 60)
print("--- Network Lifetime (Maximize Network Life) ---")
print("=" * 60)
if NETWORK_DEATH_TIME is not None:
    dead_nodes = [n for n in ALL_NODES if getattr(n, "failed", False)]
    death_ratio = len(dead_nodes) / len(ALL_NODES) if ALL_NODES else 0
    print(f"⏱️  NETWORK LIFETIME: {NETWORK_DEATH_TIME:.2f} sim seconds")
    print(f"   (Time until network death threshold reached)")
    print(f"   💀 Death threshold: {NETWORK_DEATH_THRESHOLD*100:.0f}% nodes dead OR root dead")
    print(f"   Dead nodes at death time: {len(dead_nodes)}/{len(ALL_NODES)} ({death_ratio*100:.1f}%)")
    print(f"   Simulation duration: {config.SIM_DURATION} sim seconds")
    if NETWORK_DEATH_TIME < config.SIM_DURATION:
        print(f"   ✅ Network survived {NETWORK_DEATH_TIME/config.SIM_DURATION*100:.1f}% of simulation duration")
    else:
        print(f"   ⚠️  Network died at end of simulation")
else:
    dead_nodes = [n for n in ALL_NODES if getattr(n, "failed", False)]
    if dead_nodes:
        death_ratio = len(dead_nodes) / len(ALL_NODES) if ALL_NODES else 0
        print(f"✅ Network lifetime: FULL SIMULATION DURATION ({config.SIM_DURATION} sim seconds)")
        print(f"   Network death threshold NOT reached during simulation")
        print(f"   Dead nodes at end: {len(dead_nodes)}/{len(ALL_NODES)} ({death_ratio*100:.1f}%)")
        print(f"   ⚠️  Note: {death_ratio*100:.1f}% nodes dead, but 💀 threshold ({NETWORK_DEATH_THRESHOLD*100:.0f}%) not reached")
    else:
        print(f"✅ Network lifetime: FULL SIMULATION DURATION ({config.SIM_DURATION} sim seconds)")
        print(f"   All nodes survived the entire simulation!")
        print(f"   Perfect network lifetime: 100% survival rate")
print("=" * 60)

# Energy Metrics Statistics (8)
print("\n--- Energy Metrics ---")
try:
    # Calculate aggregate statistics
    total_tx_energy = sum(getattr(n, "tx_energy_consumed", 0.0) for n in ALL_NODES)
    total_rx_energy = sum(getattr(n, "rx_energy_consumed", 0.0) for n in ALL_NODES)
    total_energy_consumed = total_tx_energy + total_rx_energy
    total_tx_packets = sum(getattr(n, "tx_packet_count", 0) for n in ALL_NODES)
    total_rx_packets = sum(getattr(n, "rx_packet_count", 0) for n in ALL_NODES)
    total_packets = total_tx_packets + total_rx_packets

    # Per-node averages
    alive_nodes = [n for n in ALL_NODES if not getattr(n, "failed", False)]
    if alive_nodes:
        avg_remaining_energy = sum(getattr(n, "power", 0.0) for n in alive_nodes) / len(alive_nodes)
        avg_consumed_energy = sum(
            getattr(n, "tx_energy_consumed", 0.0) + getattr(n, "rx_energy_consumed", 0.0)
            for n in alive_nodes
        ) / len(alive_nodes)
    else:
        avg_remaining_energy = 0.0
        avg_consumed_energy = 0.0

    # Energy by role
    energy_by_role = {}
    for node in ALL_NODES:
        role = getattr(node, "role", None)
        role_name = _role_name(role)
        if role_name not in energy_by_role:
            energy_by_role[role_name] = {
                "count": 0,
                "total_tx": 0.0,
                "total_rx": 0.0,
                "total_remaining": 0.0,
            }
        energy_by_role[role_name]["count"] += 1
        energy_by_role[role_name]["total_tx"] += getattr(node, "tx_energy_consumed", 0.0)
        energy_by_role[role_name]["total_rx"] += getattr(node, "rx_energy_consumed", 0.0)
        energy_by_role[role_name]["total_remaining"] += getattr(node, "power", 0.0)

    print(f"📊 Total Network Energy Consumption: {total_energy_consumed:.6f} J")
    print(f"   TX Energy: {total_tx_energy:.6f} J ({total_tx_energy/total_energy_consumed*100:.1f}%)")
    print(f"   RX Energy: {total_rx_energy:.6f} J ({total_rx_energy/total_energy_consumed*100:.1f}%)")
    print(f"\n📦 Total Packets: {total_packets}")
    print(f"   TX Packets: {total_tx_packets}")
    print(f"   RX Packets: {total_rx_packets}")
    print(f"\n⚡ Average Energy per Packet: {total_energy_consumed/total_packets:.9f} J" if total_packets > 0 else "\n⚡ Average Energy per Packet: N/A (no packets)")
    print(f"   Average TX Energy per Packet: {total_tx_energy/total_tx_packets:.9f} J" if total_tx_packets > 0 else "   Average TX Energy per Packet: N/A")
    print(f"   Average RX Energy per Packet: {total_rx_energy/total_rx_packets:.9f} J" if total_rx_packets > 0 else "   Average RX Energy per Packet: N/A")
    print(f"\n🔋 Average Remaining Energy (alive nodes): {avg_remaining_energy:.6f} J")
    print(f"🔋 Average Consumed Energy (alive nodes): {avg_consumed_energy:.6f} J")

    if energy_by_role:
        print(f"\n📈 Energy Consumption by Role:")
        for role_name, stats in sorted(energy_by_role.items()):
            count = stats["count"]
            avg_tx = stats["total_tx"] / count if count > 0 else 0.0
            avg_rx = stats["total_rx"] / count if count > 0 else 0.0
            avg_remaining = stats["total_remaining"] / count if count > 0 else 0.0
            print(f"   {role_name}: {count} nodes")
            print(f"      Avg TX Energy: {avg_tx:.6f} J")
            print(f"      Avg RX Energy: {avg_rx:.6f} J")
            print(f"      Avg Remaining: {avg_remaining:.6f} J")

    # Export to CSV
    try:
        write_energy_metrics_csv("energy_metrics.csv")
        print(f"\n📁 Energy metrics exported to: energy_metrics.csv")
    except Exception as csv_error:
        print(f"⚠️  Error writing energy_metrics.csv: {csv_error}")
        import traceback
        traceback.print_exc()

except Exception as e:
    print(f"⚠️  Error calculating energy metrics: {e}")
    import traceback
    traceback.print_exc()

# Role distribution
print("\n--- Final Role Distribution ---")
for role, count in ROLE_COUNTS.items():
    print(f"  {role.name}: {count}")

# Convergence verification guide
print("\n--- Convergence Verification ---")
print("📁 Check these files to verify convergence:")
print("   1. topology.csv - Lists all nodes and their final roles")
print("   2. registration_log.csv - Shows registration times for each node")
print("   3. Terminal output above - Shows convergence status")
print("\n💡 Expected roles for convergence:")
print("   - ROOT: 1 node")
print("   - CLUSTER_HEAD: Multiple nodes (network clusters)")
print("   - REGISTERED: Leaf nodes (most nodes)")
print("   - ROUTER: Bridge nodes (if any)")
print("   - UNREGISTERED/UNDISCOVERED: Help me join the network")

# Optionally save final snapshot if visualization was enabled
SNAPSHOT_AT_END = getattr(config, "SNAPSHOT_AT_END", False)
if SNAPSHOT_AT_END and sim.visual and hasattr(sim, 'tkplot'):
    try:
        canvas = sim.tkplot.canvas
        # Update canvas to ensure everything is drawn
        canvas.update()
        # Save as PostScript (built-in Tkinter method)
        filename = "final_snapshot.eps"
        canvas.postscript(file=filename, colormode='color')
        print(f"\n📸 Final snapshot saved to {filename}")
        print("   (Convert to PNG: convert final_snapshot.eps final_snapshot.png)")
        print("   Or use: ps2pdf final_snapshot.eps final_snapshot.pdf")
    except Exception as e:
        print(f"\n⚠️  Could not save snapshot: {e}")

print("=" * 60 + "\n")
