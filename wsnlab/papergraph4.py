
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

def generate_figure_5():
    print("Generating Figure 5: Packets Delivered vs Packets Sent")
    
    # Loss rates to compare
    loss_rates = [0.0, 0.001, 0.01]
    
    # Durations to generate increasing number of packets
    durations = [100, 500, 1000, 2000, 3000, 5000]
    
    results = {}  # {loss_rate: {'sent': [], 'delivered': []}}
    
    # Reset other config to defaults to ensure consistency
    config.NUM_NODES_TO_KILL = 0
    data_collection_tree.NUM_NODES_TO_KILL = 0
    # Use High Traffic for more packets? 
    # Use standard traffic to keep it clean. 
    # Let's ensure Data Packets are enabled to get good volume.
    config.ENABLE_DATA_PACKETS = True
    data_collection_tree.ENABLE_DATA_PACKETS = True
    # Moderate interval to get enough points but not crash
    config.DATA_INTERVAL = 2
    data_collection_tree.DATA_INTERVAL = 2
    
    for loss in loss_rates:
        print(f"\n=== Testing Packet Loss Ratio: {loss} ===")
        results[loss] = {'sent': [], 'delivered': []}
        
        # Set config
        config.PACKET_LOSS_RATIO = loss
        # Note: data_collection_tree doesn't have a global for this, it uses config direct
        # But we need to make sure config is reloaded or used dynamically
        
        for dur in durations:
            print(f"  Duration {dur}s...", end="", flush=True)
            try:
                # Force reload of config if needed, or just trust the attribute set
                # attributes on config module are mutable, so this should work
                
                result = data_collection_tree.run_simulation(
                    node_count=100,
                    visual=False,
                    duration=dur,
                    nodes_to_kill=0
                )
                
                # Check for expanded return tuple
                if isinstance(result, tuple) and len(result) >= 6:
                    sent = result[4]
                    dropped = result[5]
                    delivered = sent - dropped
                    
                    results[loss]['sent'].append(sent)
                    results[loss]['delivered'].append(delivered)
                    print(f" Sent: {sent}, Delivered: {delivered}")
                else:
                    print(" Error: run_simulation did not return packet stats.")
                    
            except Exception as e:
                print(f" Failed: {e}")

    # Plot
    plt.figure(figsize=(8, 6))
    
    # Plot perfect line reference? No, 0.0 loss should overlap it.
    
    colors = {0.0: 'blue', 0.001: 'green', 0.01: 'red'}
    markers = {0.0: 'o', 0.001: 's', 0.01: '^'}
    labels = {0.0: 'Loss = 0', 0.001: 'Loss = 0.001', 0.01: 'Loss = 0.01'}
    
    for loss in loss_rates:
        sent_data = results[loss]['sent']
        deliv_data = results[loss]['delivered']
        
        plt.plot(sent_data, deliv_data, 
                 marker=markers[loss], 
                 color=colors[loss], 
                 label=labels[loss],
                 linestyle='-')

    # Add diagonal reference line for context if needed, but 0 loss is effectively that
    # max_val = max(max(results[0.0]['sent']), 10)
    # plt.plot([0, max_val], [0, max_val], 'k--', alpha=0.3, label='Ideal')

    plt.xlabel('Packets Sent')
    plt.ylabel('Packets Delivered')
    plt.title('Figure 5: Packets Delivered vs Sent (Varying Loss Rates)')
    plt.grid(True)
    plt.legend()
    
    plt.savefig('graph_figure_5.png')
    print(f"\nSaved: graph_figure_5.png")
    plt.close()

if __name__ == "__main__":
    generate_figure_5()
