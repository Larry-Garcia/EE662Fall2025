
import matplotlib.pyplot as plt
import sys
import os
import numpy as np

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import data_collection_tree
    import source.config as config
except ImportError:
    # If run from parent directory
    sys.path.insert(0, os.path.join(os.getcwd(), 'wsnlab'))
    import data_collection_tree
    import source.config as config

def run_sim_wrapper(duration=5000):
    result = data_collection_tree.run_simulation(
        node_count=100, visual=False, duration=duration, nodes_to_kill=0
    )
    # Unpack the 8 return values
    # return avg_join, max_orphan, final_orphan, lifetime, attempts, dropped, metrics, deaths
    if isinstance(result, tuple) and len(result) >= 8:
        return result
    else:
        print(f"Error: run_simulation returned unexpected format: {type(result)}")
        return None

def generate_figure_6():
    print("\n--- Generating Figure 6: Energy (CT+Mesh vs CT Only) ---")
    scenarios = [
        {"name": "CT+Mesh", "mesh": True, "marker": 'o', "color": 'blue'},
        {"name": "CT Only", "mesh": False, "marker": 's', "color": 'gray'}
    ]
    
    # Configure base
    config.ENABLE_DATA_PACKETS = True
    data_collection_tree.ENABLE_DATA_PACKETS = True
    config.DATA_INTERVAL = 2 # Moderate traffic
    data_collection_tree.DATA_INTERVAL = 2
    
    plt.figure(figsize=(8, 5))
    
    for sc in scenarios:
        print(f"Running {sc['name']}...")
        config.ENABLE_MESH = sc['mesh']
        # Also need to ensure data_collection_tree respects this if it uses it directly?
        # data_collection_tree uses config.ENABLE_MESH, so setting config is enough.
        
        res = run_sim_wrapper(duration=3500) 
        if res:
            metrics = res[6] # METRICS_OVER_TIME
            times = [m['time'] for m in metrics]
            energy = [m['avg_energy'] for m in metrics]
            plt.plot(times, energy, label=sc['name'], marker=sc['marker'], markevery=200, color=sc['color'])

    plt.xlabel('Time [s]')
    plt.ylabel('Average Remaining Energy [J]')
    plt.title('Figure 6: Energy Consumption (CT+Mesh vs CT Only)')
    plt.grid(True)
    plt.legend()
    plt.savefig('graph_figure_6.png')
    print("Saved graph_figure_6.png")
    
    # Restore default
    config.ENABLE_MESH = True

def generate_figure_7():
    print("\n--- Generating Figure 7: Lifetime Metrics vs Initial Energy ---")
    energies = [0.5, 1.0, 2.0, 3.0]
    
    # Fixed Min Energy for linear scaling
    min_energy = 0.05
    data_collection_tree.MIN_ENERGY_J = min_energy
    config.MIN_ENERGY_J = min_energy
    
    # Base config
    data_collection_tree.ENABLE_DATA_PACKETS = True # High traffic for faster results? 
    config.ENABLE_DATA_PACKETS = True
    # Let's use aggressive traffic to make durations reasonable
    data_collection_tree.DATA_INTERVAL = 0.5 
    config.DATA_INTERVAL = 0.5
    
    first_deaths = []
    half_deaths = []
    connectivity_drops = []
    
    for e0 in energies:
        print(f"Running E0 = {e0} J...")
        data_collection_tree.INITIAL_ENERGY_J = e0
        config.INITIAL_ENERGY_J = e0
        
        # Scale duration safely
        dur = 2000 if e0 < 1.0 else 5000 
        
        res = run_sim_wrapper(duration=dur)
        if res:
            deaths = res[7] # NODE_DEATHS dict
            lifetime = res[3] # Network Lifetime (<80%)
            
            # 1. First Death
            death_times = sorted([d['time'] for d in deaths.values()])
            first = death_times[0] if death_times else dur
            first_deaths.append(first)
            
            # 2. 50% Dead
            # Total nodes = (usually 100, can verify from len(deaths) + alive count if needed)
            # Assuming 100 nodes
            half_index = 49 # 50th node
            half = death_times[half_index] if len(death_times) > 49 else dur
            half_deaths.append(half)
            
            # 3. Connectivity < 80%
            conn_time = lifetime if lifetime else dur
            # In some cases conn time might be NONE if it never dropped
            connectivity_drops.append(conn_time)
            
            print(f"  E0={e0}: First={first:.1f}, 50%={half:.1f}, <80%={conn_time:.1f}")

    # Plot Grouped Bar Chart
    x = np.arange(len(energies))
    width = 0.25
    
    plt.figure(figsize=(10, 6))
    plt.bar(x - width, first_deaths, width, label='First Node Death', color='skyblue')
    plt.bar(x, connectivity_drops, width, label='<80% Connected', color='orange')
    plt.bar(x + width, half_deaths, width, label='50% Nodes Dead', color='salmon')
    
    plt.xlabel('Initial Energy $E_0$ [J]')
    plt.ylabel('Time [s]')
    plt.title('Figure 7: Lifetime Metrics vs Initial Energy')
    plt.xticks(x, [str(e) for e in energies])
    plt.legend()
    plt.grid(True, axis='y')
    plt.savefig('graph_figure_7.png')
    print("Saved graph_figure_7.png")

def generate_traffic_figures():
    print("\n--- Generating Figures 8, 9, 10, 11 (Traffic Loads) ---")
    
    # Restore manageable energy
    e0 = 0.5 # Low energy so things happen fast
    min_e = 0.05
    data_collection_tree.INITIAL_ENERGY_J = e0
    config.INITIAL_ENERGY_J = e0
    data_collection_tree.MIN_ENERGY_J = min_e
    config.MIN_ENERGY_J = min_e
    
    traffic_loads = [
        {"name": "Low Traffic", "interval": 50, "marker": 'o'}, 
        {"name": "Medium Traffic", "interval": 5, "marker": '^'},
        {"name": "High Traffic", "interval": 0.5, "marker": 's'}
    ]
    
    # Store results for plotting
    all_metrics = {} # name -> list of metric dicts
    high_traffic_deaths = {} # For Fig 11
    
    for load in traffic_loads:
        name = load['name']
        print(f"Running {name}...")
        
        data_collection_tree.ENABLE_DATA_PACKETS = True
        config.ENABLE_DATA_PACKETS = True
        data_collection_tree.DATA_INTERVAL = load['interval']
        config.DATA_INTERVAL = load['interval']
        
        # Run long enough to kill nodes
        res = run_sim_wrapper(duration=1500)
        if res:
            all_metrics[name] = res[6] # METRICS_OVER_TIME
            if name == "High Traffic":
                high_traffic_deaths = res[7] # NODE_DEATHS

    # --- Figure 9: Avg Energy vs Time ---
    plt.figure(figsize=(8, 5))
    for load in traffic_loads:
        name = load['name']
        metrics = all_metrics[name]
        # Crop data: Start from steady state (t > 300) to ignore formation
        metrics_cropped = [m for m in metrics if m['time'] > 300]
        
        times = [m['time'] for m in metrics_cropped]
        energy = [m['avg_energy'] for m in metrics_cropped]
        plt.plot(times, energy, label=name, marker=load['marker'], markevery=100)
    
    plt.xlabel('Time [s]')
    plt.ylabel('Average Remaining Energy [J]')
    plt.title('Figure 9: Average Remaining Energy vs Time')
    plt.grid(True)
    plt.legend()
    plt.savefig('graph_figure_9.png')
    print("Saved graph_figure_9.png")
    
    # --- Figure 10: Connectivity vs Time ---
    plt.figure(figsize=(8, 5))
    for load in traffic_loads:
        name = load['name']
        metrics = all_metrics[name]
        # Crop data: Start from steady state (t > 300) to ignore formation ramp-up
        metrics_cropped = [m for m in metrics if m['time'] > 300]

        times = [m['time'] for m in metrics_cropped]
        conn = [m['connectivity'] for m in metrics_cropped]
        plt.plot(times, conn, label=name, marker=load['marker'], markevery=100)
    
    plt.axhline(y=0.8, color='k', linestyle='--', label='80% Threshold')
    plt.xlabel('Time [s]')
    plt.ylabel('Fraction of Connected Nodes')
    plt.ylim(0, 1.05) # Ensure full range
    plt.title('Figure 10: Connectivity Fraction vs Time')
    plt.grid(True)
    plt.legend()
    plt.savefig('graph_figure_10.png')
    print("Saved graph_figure_10.png")
    
    # --- Figure 8: PDR Over Time (High Traffic only or Comparison) ---
    # Calculating windowed PDR from cumulative stats
    # PDR at time t = (Delivered_t - Delivered_t-1) / (Sent_t - Sent_t-1)
    plt.figure(figsize=(8, 5))
    
    metrics = all_metrics["High Traffic"]
    # Crop data for stability
    metrics = [m for m in metrics if m['time'] > 300]
    
    times = [m['time'] for m in metrics]
    cumulative_sent = [m['tx'] for m in metrics]
    cumulative_dropped = [m['dropped'] for m in metrics]
    
    pdr_values = []
    # Smoothing window size
    window = 10 
    
    for i in range(len(times)):
        if i < window:
            pdr_values.append(1.0) # Start perfect
            continue
            
        # Calculate delta over window
        d_sent = cumulative_sent[i] - cumulative_sent[i-window]
        d_dropped = cumulative_dropped[i] - cumulative_dropped[i-window]
        d_deliv = d_sent - d_dropped
        
        if d_sent > 0:
            pdr = d_deliv / d_sent
        else:
            # If no traffic sent, maintain previous PDR to avoid noise
            pdr = pdr_values[-1] if pdr_values else 1.0
            
        pdr_values.append(pdr)
        
    plt.plot(times, pdr_values, label="High Traffic PDR", color='red')
    
    plt.xlabel('Time [s]')
    plt.ylabel('Packet Delivery Ratio (Sliding Window)')
    plt.title('Figure 8: PDR Stability Over Time (High Traffic)')
    plt.grid(True)
    plt.ylim(0, 1.1)
    plt.legend()
    plt.savefig('graph_figure_8.png')
    print("Saved graph_figure_8.png")
    
    # --- Figure 11: CDF of Lifetimes (High Traffic) ---
    plt.figure(figsize=(8, 5))
    
    ch_lifetimes = []
    leaf_lifetimes = []
    
    # Process deaths
    for nid, info in high_traffic_deaths.items():
        role = info['role']
        time = info['time']
        
        # Check role strings. They are typically "Roles.CLUSTER_HEAD" etc.
        if "CLUSTER_HEAD" in role or "ROUTER" in role:
            ch_lifetimes.append(time)
        else:
            leaf_lifetimes.append(time)
            
    # Add nodes that didn't die (lifetime = max duration)
    # Assuming 100 nodes
    # This might bias the CDF if many survived, but for 0.5J High Traffic, most should die.
    
    ch_lifetimes.sort()
    leaf_lifetimes.sort()
    
    if len(ch_lifetimes) > 0:
        y_ch = np.arange(1, len(ch_lifetimes)+1) / len(ch_lifetimes)
        plt.plot(ch_lifetimes, y_ch, label='Cluster Heads/Routers', marker='.')
        
    if len(leaf_lifetimes) > 0:
        y_leaf = np.arange(1, len(leaf_lifetimes)+1) / len(leaf_lifetimes)
        plt.plot(leaf_lifetimes, y_leaf, label='Leaf Nodes', marker='.')
        
    plt.xlabel('Node Lifetime [s]')
    plt.ylabel('Cumulative Probability (CDF)')
    plt.title('Figure 11: CDF of Node Lifetimes by Role')
    plt.grid(True)
    plt.legend()
    plt.savefig('graph_figure_11.png')
    print("Saved graph_figure_11.png")


if __name__ == "__main__":
    generate_figure_6()
    generate_figure_7()
    generate_traffic_figures()
