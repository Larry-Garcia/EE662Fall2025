
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

def generate_figure_2():
    print("Generating Figure 2: Average Join Time vs Network Size")
    
    network_sizes = [25, 50, 75, 100, 150, 200]
    avg_join_times = []
    
    for size in network_sizes:
        print(f"Running simulation for network size: {size} (5 iterations)...")
        join_times = []
        for i in range(5):
            print(f"  Iteration {i+1}...", end="", flush=True)
            try:
                # Assuming run_simulation returns avg_join_time or a tuple
                result = data_collection_tree.run_simulation(node_count=size, visual=False, duration=5000)
                
                # Handle tuple return (avg_join_time, max_orphan, final_orphan, lifetime)
                if isinstance(result, tuple):
                    val = result[0]
                else:
                    val = result
                    
                join_times.append(val)
                print(f" Done. Join time: {val:.2f}")
            except Exception as e:
                print(f" Failed: {e}")
                join_times.append(0)
        
        if join_times:
            avg_time = sum(join_times) / len(join_times)
        else:
            avg_time = 0
            
        avg_join_times.append(avg_time)
        print(f"--> Average Join Time for {size} nodes: {avg_time:.2f}")
    
    # Plotting
    plt.figure(figsize=(10, 6))
    plt.plot(network_sizes, avg_join_times, marker='o', linestyle='-', color='b')
    plt.title('Figure 2: Average Join Time vs Network Size')
    plt.xlabel('Network Size (Number of Nodes)')
    plt.ylabel('Average Join Time (seconds)')
    plt.grid(True)
    plt.xticks(network_sizes)
    
    output_file = 'graph_figure_2.png'
    plt.savefig(output_file)
    print(f"\nGraph saved to {output_file}")
    plt.close()

if __name__ == "__main__":
    generate_figure_2()
