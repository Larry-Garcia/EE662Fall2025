sim = None

# --- Failure & Recovery Simulation Globals ---
RECOVERY_START_TIME = None
RECOVERY_DURATION = None
MAX_ORPHAN_COUNT = 0
NETWORK_LIFETIME = None  # New for Figure 4


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
                    f"\n💀 NETWORK DEATH at time {time:.2f} ({len(dead_nodes)}/{total_nodes} nodes dead, {death_ratio:.2f})")

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

    print(
        f"\n💀 KILLING {len(victims)} node(s) at time {sim.now}: {[v.id for v in victims]}")

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


def log_connectivity(sim_ref):
    """Check if network connectivity drops below 80% (Figure 4)."""
    global NETWORK_LIFETIME
    
    total = len(ALL_NODES)
    alive_nodes = [n for n in ALL_NODES if getattr(n, "power", 0) > MIN_ENERGY_J]
    avg_power = sum(n.power for n in alive_nodes) / len(alive_nodes) if alive_nodes else 0
    
    # Print every 100s or if very early
    if sim_ref.now < 2 or int(sim_ref.now) % 100 == 0:
         print(f"t={sim_ref.now:.0f}: alive={len(alive_nodes)}/{total}, avg_power={avg_power:.4f}J, DATA={ENABLE_DATA_PACKETS}")
    
    total = len(ALL_NODES)
    # Count nodes that are connected (valid role) AND alive (energy > MIN)
    # Note: 'energy' attribute on Node is named 'power' in SensorNode.init
    connected = sum(1 for n in ALL_NODES 
                    if getattr(n, "role", None) in {Roles.REGISTERED, Roles.CLUSTER_HEAD, Roles.ROOT, Roles.ROUTER}
                    and getattr(n, "power", 0) > MIN_ENERGY_J)
    
    connectivity = connected / total if total > 0 else 0.0
    
    # Mark network lifetime when connectivity drops below 80% (after initial formation grace period)
    if sim_ref.now > 500 and connectivity < 0.80 and NETWORK_LIFETIME is None:
        NETWORK_LIFETIME = sim_ref.now
        print(f"📉 NETWORK LIFETIME REACHED (Connectivity < 80%) at time {sim_ref.now:.2f}")

    # Schedule next check
    if sim_ref.now + config.POWER_SAMPLING_INTERVAL < sim_ref.duration:
        sim_ref.delayed_exec(config.POWER_SAMPLING_INTERVAL, log_connectivity, sim_ref)


def run_simulation(node_count=None, visual=True, duration=5000, nodes_to_kill=1):
    global sim
    global NODE_POS, ADDR_TO_NODE, NODES_REGISTERED, ALL_NODES, CLUSTER_HEADS, ROLE_COUNTS
    global NETWORK_DEATH_TIME, RECOVERY_START_TIME, RECOVERY_DURATION, MAX_ORPHAN_COUNT
    global NETWORK_LIFETIME
    global ROOT_ID

    # Reset global state
    NODE_POS = {}
    ADDR_TO_NODE = {}
    NODES_REGISTERED = 0
    ALL_NODES = []
    CLUSTER_HEADS = []
    ROLE_COUNTS = Counter()
    
    NETWORK_DEATH_TIME = None
    RECOVERY_START_TIME = None
    RECOVERY_DURATION = None
    MAX_ORPHAN_COUNT = 0
    NETWORK_LIFETIME = None
    
    # Update config overrides if provided
    current_node_count = node_count if node_count is not None else config.SIM_NODE_COUNT
    
    # Override nodes to kill
    config.NUM_NODES_TO_KILL = nodes_to_kill

    # Pick a random root ID based on the (potentially new) count
    ROOT_ID = random.randrange(current_node_count)

    # Initialize Simulator
    # If not visual, execute fast (timescale=0)
    timescale = config.SIM_TIME_SCALE if visual else 0
    
    sim = wsn.Simulator(
        duration=duration,
        timescale=timescale,
        visual=visual,
        terrain_size=config.SIM_TERRAIN_SIZE,
        title=config.SIM_TITLE,
    )

    # Create network and pre-compute static distance CSVs
    create_network(SensorNode, current_node_count)
    write_node_distances_csv("node_distances.csv")
    write_node_distance_matrix_csv("node_distance_matrix.csv")

    # Initialize all CSV files
    init_csv_files()
    
    # Initialize failures log explicitly (as it was in original script)
    with open("failures.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "node_id", "event_type", "orphan_count"])

    # Schedule failure event
    sim.delayed_exec(config.FAILURE_TIME, kill_random_node)

    # Schedule initial power sampling
    sim.delayed_exec(0.1, sample_power_levels)

    # Schedule connectivity logging (New for Fig 4)
    sim.delayed_exec(0.1, log_connectivity, sim)

    # Run simulation
    start_time = time.time()
    sim.run()
    end_time = time.time()
    runtime = end_time - start_time

    # Export logged packets
    log_all_packets(sim.packet_log)

    # Check convergence
    converged = log_all_nodes_registered()

    print("\n" + "=" * 60)
    print("Simulation Finished Finally!!!!")
    print("=" * 60)
    print(f"⏱️  Runtime: {runtime:.2f} seconds ({runtime/60:.2f} minutes)")
    print("=" * 60)

    # Calculate statistics
    avg_join_time = 0
    if sim.join_times:
        avg_join_time = sum(sim.join_times) / len(sim.join_times)
    
    # --- Network Statistics Output (Condensed) ---
    print(f"Join Times: {len(sim.join_times)} nodes joined")
    print(f"  Average: {avg_join_time:.4f} sim seconds")

    # Packet Loss
    print("\n--- Packet Loss Statistics ---")
    attempts = getattr(sim, "total_tx_attempts", 0)
    dropped = getattr(sim, "total_tx_dropped", 0)
    if attempts > 0:
        loss_pct = dropped / attempts * 100.0
        print(f"  TX attempts: {attempts}, Dropped: {dropped}, Loss: {loss_pct:.2f}%")
        try:
            with open("packet_loss_stats.csv", "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["configured_loss_pct", "realized_loss_pct", "attempts", "dropped"])
                writer.writerow([config.PACKET_LOSS_RATIO * 100.0, loss_pct, attempts, dropped])
        except Exception:
            pass

    # Energy Metrics Export
    print("\n--- Energy Metrics ---")
    try:
        write_energy_metrics_csv("energy_metrics.csv")
        print(f"📁 Energy metrics exported to: energy_metrics.csv")
    except Exception as e:
        print(f"⚠️  Error exporting energy metrics: {e}")

    # Calculate final orphan count (after recovery)
    final_orphan_count = len([n for n in ALL_NODES
                       if getattr(n, "role", None) not in
                       {Roles.REGISTERED, Roles.CLUSTER_HEAD, Roles.ROOT, Roles.ROUTER}])

    # Return metrics for graph generation:
    # 1. Avg Join Time
    # 2. Peak disconnected nodes (MAX_ORPHAN_COUNT) - Line 1 (Nodes Disconnected)
    # 3. Final disconnected nodes (after recovery) - Line 2 (Nodes Reactivated / Recovered)
    # 4. Network Lifetime (time when connectivity < 80%)
    return avg_join_time, MAX_ORPHAN_COUNT, final_orphan_count, NETWORK_LIFETIME

if __name__ == "__main__":
    run_simulation()
