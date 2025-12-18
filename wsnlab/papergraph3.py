
import matplotlib.pyplot as plt
import sys
import os
import importlib

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

def generate_figure_4():
    print("Generating Figure 4: Network Lifetime vs Initial Energy")
    
    initial_energies = [0.5, 1.0, 2.0, 3.0]
    
    # Fixed low MIN_ENERGY so usable energy scales proportionally
    energy_params = {
        0.5: 0.05,
        1.0: 0.05,
        2.0: 0.05,
        3.0: 0.05
    }
    
    # Two traffic levels
    traffic_configs = [
        {"name": "Low traffic", "enable_data": False, "interval": 50},
        {"name": "High traffic", "enable_data": True, "interval": 0.3}, # Aggressive traffic to drain battery
    ]
    
    results = {}  # {traffic_name: [lifetimes]}
    
    sim_dur = 5000
    iterations_per_point = 1  # Reduced for speed during testing
    
    for traffic in traffic_configs:
        traffic_name = traffic["name"]
        results[traffic_name] = []
        
        for init_e in initial_energies:
            min_e = energy_params[init_e]
            print(f"\n=== {traffic_name}, Energy: {init_e} J ===")
            
            # Update config and verify
            data_collection_tree.INITIAL_ENERGY_J = init_e
            data_collection_tree.MIN_ENERGY_J = min_e
            data_collection_tree.ENABLE_DATA_PACKETS = traffic["enable_data"]
            data_collection_tree.DATA_INTERVAL = traffic["interval"]
            
            # Also update base config just in case
            config.INITIAL_ENERGY_J = init_e
            config.MIN_ENERGY_J = min_e
            config.ENABLE_DATA_PACKETS = traffic["enable_data"]
            config.DATA_INTERVAL = traffic["interval"]
            
            # Dynamic duration to ensure we capture the death event
            # 0.5J dies ~500s. 3.0J ~2300s? Wait, previous graph showed 3.0J ~2300s.
            # But high traffic should die faster.
            # Safety margins:
            if init_e >= 3.0:
                current_sim_dur = 8000
            elif init_e >= 2.0:
                current_sim_dur = 6000
            else:
                current_sim_dur = 4000
            
            lifetimes = []
            for i in range(iterations_per_point):
                print(f"  Run {i+1} (Dur {current_sim_dur}s)...", end="", flush=True)
                try:
                    result = data_collection_tree.run_simulation(
                        node_count=100,
                        visual=False,
                        duration=current_sim_dur,
                        nodes_to_kill=0
                    )
                    
                    if isinstance(result, tuple) and len(result) >= 4:
                        lifetime = result[3] 
                    else:
                        lifetime = None
                        
                    if lifetime is None:
                        # Logic Fix: Check if it never formed vs survived
                        if data_collection_tree.NETWORK_FORMED:
                            # Formed but never dropped below threshold - survived full duration
                            lifetime = current_sim_dur
                            print(f" {lifetime:.0f}s (Survived)")
                        else:
                            # Never formed - failed immediately due to congestion/death
                            lifetime = 0
                            print(f" {lifetime:.0f}s (Failed to Form)")
                        
                    lifetimes.append(lifetime)
                except Exception as e:
                    print(f" Failed: {e}")
                    lifetimes.append(0)
            
            avg_lifetime = sum(lifetimes) / len(lifetimes)
            results[traffic_name].append(avg_lifetime)
            print(f"  Average: {avg_lifetime:.0f}s")
    
    # Plot
    plt.figure(figsize=(8, 5))
    plt.plot(initial_energies, results["Low traffic"], marker='o', label='Low traffic')
    plt.plot(initial_energies, results["High traffic"], marker='s', label='High traffic')
    plt.xlabel(r'Initial Energy $E_0$ [J]')
    plt.ylabel('Network Lifetime [s]')
    plt.title('Figure 4: Network Lifetime vs Initial Energy Budget')
    plt.grid(True)
    plt.legend()
    # Force Y-axis to start at 0
    plt.ylim(bottom=0)
    plt.xticks(initial_energies)
    
    plt.savefig('graph_figure_4.png')
    print(f"\nSaved: graph_figure_4.png")
    plt.close()

if __name__ == "__main__":
    generate_figure_4()
