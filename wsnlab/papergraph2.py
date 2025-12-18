
import matplotlib.pyplot as plt
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import data_collection_tree
except ImportError:
    # If run from parent directory
    sys.path.insert(0, os.path.join(os.getcwd(), 'wsnlab'))
    import data_collection_tree

def generate_figure_3():
    print("Generating Figure 3: Nodes Killed vs Nodes Disconnected")
    
    # We will test varying number of killed nodes as requested by user.
    nodes_killed_counts = [0, 5, 10, 15, 20, 25]
    iterations_per_point = 5
    
    # Line 1: Disconnected nodes AFTER KILLING (Peak)
    avg_orphans_peak = []
    
    # Line 2: Disconnected nodes AFTER RECOVERY (Final)
    avg_orphans_final = []
    
    print(f"Target killed counts: {nodes_killed_counts}")
    print(f"Iterations per point: {iterations_per_point}")
    
    for count in nodes_killed_counts:
        print(f"\n=== Testing Nodes Killed: {count} ===")
        print(f"Running {iterations_per_point} iterations...")
        
        peak_orphans_list = []
        final_orphans_list = []
        
        for i in range(iterations_per_point):
            print(f"  > Iteration {i+1}/{iterations_per_point}...", end="", flush=True)
            try:
                # Need to run with default 100 nodes (or make it explicit)
                # Using 100 nodes for this sensitivity analysis
                # REDUCED DURATION TO 2000 to capture failure event (500s) but avoid energy death (~3000s)
                result = data_collection_tree.run_simulation(
                    node_count=100, 
                    visual=False, 
                    duration=2000, 
                    nodes_to_kill=count
                )
                
                # Check tuple result
                # Now supports 3 or 4 elements
                if isinstance(result, tuple) and len(result) >= 3:
                    _, max_orphan_count, final_orphan_count = result[:3]
                elif isinstance(result, tuple):
                    # Old signature fallback
                    _, max_orphan_count = result
                    final_orphan_count = 0 
                else:
                    # Not tuple
                    print(" Warning: run_simulation did not return tuple.")
                    max_orphan_count = 0
                    final_orphan_count = 0
                
                peak_orphans_list.append(max_orphan_count)
                final_orphans_list.append(final_orphan_count)
                print(f" Done. Peak Disconnected: {max_orphan_count}, Final: {final_orphan_count}")
            except Exception as e:
                print(f" Failed: {e}")
                peak_orphans_list.append(0)
                final_orphans_list.append(0)
            
        # Calculate averages
        if peak_orphans_list:
            mean_peak = sum(peak_orphans_list) / len(peak_orphans_list)
            mean_final = sum(final_orphans_list) / len(final_orphans_list)
        else:
            mean_peak = 0.0
            mean_final = 0.0
            
        avg_orphans_peak.append(mean_peak)
        avg_orphans_final.append(mean_final)
        print(f"--> Result for {count} killed (avg of {iterations_per_point} runs): Peak={mean_peak:.2f}, Final={mean_final:.2f}")
    
    # Plotting
    plt.figure(figsize=(10, 6))
    
    # Line 1: Peak Disconnected (Red)
    plt.plot(nodes_killed_counts, avg_orphans_peak, marker='o', linestyle='-', color='r', label='Nodes Disconnected (Peak)')
    
    # Line 2: Final Disconnected / Recovered (Green)
    plt.plot(nodes_killed_counts, avg_orphans_final, marker='x', linestyle='--', color='g', label='Nodes Disconnected (After Recovery)')
    
    plt.title(f'Figure 3: Impact of Node Failures & Recovery\n(Network Size: 100, Averaged over {iterations_per_point} runs)')
    plt.xlabel('Number of Nodes Killed')
    plt.ylabel('Number of Disconnected Nodes')
    plt.grid(True)
    plt.legend()
    plt.xticks(nodes_killed_counts)
    
    # Ensure y-axis starts at 0
    plt.ylim(bottom=0)
    
    output_file = 'graph_figure_3.png'
    plt.savefig(output_file)
    print(f"\nGraph saved to {output_file}")
    plt.close()

if __name__ == "__main__":
    generate_figure_3()
