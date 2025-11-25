# EE 662 – Wireless Sensor Networks  
## Cluster-Tree Mesh Ad-Hoc Network  
### Implementation and Simulation 

You have developed a self-organizing cluster-tree network protocol in the first assignment
and reported your design in a design document. You have also been provided with a
Python-based simulation platform that has been discussed in detail in class.  

In this assignment, you are required to implement the protocol and run simulations to
report the metrics listed below.

---

## 1. Implementation

### 1.1 Neighbor Discovery

Design a neighbor discovery protocol and populate the neighbor table (more than one hop).

- You may initially develop a one-hop neighbor table.
- The final deliverable **must** include a multi-hop neighbor table populated by **neighbor-table sharing**.

---

### 1.2 Cluster-Tree Network and Tables

From your previous assignment, you have:

- A **cluster-tree network protocol**.
- A **member networks table**.
- A **members table**.

Both tables are implemented in each **cluster head**.

- The **member networks table** lists the networks below the cluster head.
- The **members table** lists the members of this cluster.

The **member networks table** will be used for routing.

> Note: The simulation model shared earlier does **not** implement routing; it directly delivers packets to the destination.  
> In this assignment, you must add routing (see Section 1.3).

---

### 1.3 Routing Implementation

Implement routing in your simulation platform.

#### 1.3.1 Routing Behavior

- Use **mesh routing** in the **local neighborhood**.
- If local mesh routing fails, **revert to tree routing**.

#### 1.3.2 Metrics to Report

1. **Average time to join the network**

   - Use simulation time.
   - Every packet created (both **control** and **data** packets) must be **timestamped**.
   - When a packet reaches its final destination, log:
     - `delay = receive_time – creation_time`.
   - Use this to measure delay within the network.
   - The current system does not consider processing or transmission time.
     - Models that **do** consider these times will receive **bonus points**.

2. **Packet tracing**

   - Implement packet tracing and record the **path between any two network nodes** when data packets are exchanged between random nodes.

---

## 2. Configuration Parameters

Your model should support the following configurable parameters:

1. **Number of child nodes allowed for a cluster**

   - By configuring the maximum number of nodes in a cluster, you can control the **topology** of the network.

2. **Transmit (Tx) power of each cluster**

   - For each cluster, allow the specification of a Tx power between **TxMin** and **TxMax**.
   - All nodes in a cluster share the **same power level**.
   - The system should also allow all nodes to use the **same (global) power level**.

3. **Packet loss ratio**

   - In the current model, the channel is assumed to be perfect (all packets are delivered).
   - Your model should allow a **packet loss rate** to be specified.
   - The simulator must **apply** this loss rate when delivering packets.

---

## 3. Cluster Overlap and Role Transfer

In the current model, clusters overlap by a large amount because the cluster head of a new cluster is chosen among nodes in an **existing cluster**.

You must:

- Develop a variation where **clusters overlap minimally**.
- Ensure **cluster heads communicate via a router**.
- Allow the **cluster head role** to **move from one node to another**.

---

## 4. Failure Recovery

Implement **network recovery** from **node** and **link** failures.

- This will be tested by:
  - Randomly **killing a node** after the simulation starts.
  - **Recovering** that node after some time.

Your system must **log and report**:

- Orphan networks and nodes.
- Nodes joining a network.
- Role changes (e.g., nodes becoming cluster heads).

### 4.1 Metrics

1. **Time to recover**
2. **Number of orphan nodes**

---

## 5. Cluster Optimization

Develop a **cluster optimization protocol** that will minimize:

1. The **number of clusters** and/or  
2. The **energy consumed in the network** (e.g., **per-packet energy consumption**).

---

## 6. Energy Model and Network Lifetime

Develop an **energy model** where:

- Each node’s energy is reduced by the amount required to **transmit/receive a packet**.
- When a node’s power level drops below a specified minimum, the node should be **turned off**.
- Use the **CC2420 radio** for these energy estimations.

Your protocol will be tested for **network lifetime**, and your system should **maximize** the network life.

---

## 7. Energy Required to Transmit a Packet on a CC2420 Node

### 7.1 Basic Parameters

- **Data rate (R)**: 250 kbps → 4 µs per bit  
- **Supply voltage (V)**: ≈ 3.0 V  
- **TX current at 0 dBm**: ≈ 17.4 mA → **Power (P)** ≈ 52.2 mW  
- **PHY overhead**: 6 bytes  
  - 4-byte preamble  
  - 1-byte SFD  
  - 1-byte PHR  

---

### 7.2 Energy Formula

Energy to transmit a packet with PSDU length **N bytes** (MAC frame length), excluding startup:

- \( E_\text{tx} \approx P \times \dfrac{8 \times (N + 6)}{R} \)
- \( E_\text{tx} \approx (V \times I) \times \dfrac{8 \times (N + 6)}{250000} \)

At **V = 3.0 V** and **I = 17.4 mA**:

- Energy per **bit** ≈ 0.208 µJ  
- Energy per **byte** ≈ 1.67 µJ  
- Optional **turnaround/PLL settling overhead** ≈ 10 µJ

---

### 7.3 Example Energy Values (3.0 V, 0 dBm)

At 0 dBm:

- CC2420 current ≈ 17.4 mA → Power ≈ 52.2 mW  
- PHY overhead = 6 bytes (preamble + SFD + PHR)

| PSDU (MAC) Bytes N | Total Over-Air Bytes N + 6 | Energy (µJ) |
|--------------------|----------------------------|-------------|
| 20                 | 26                         | ≈ 43        |
| 50                 | 56                         | ≈ 94        |
| 100                | 106                        | ≈ 177       |
| 127                | 133                        | ≈ 222       |

---

## 8. Dependence on TX Power

The CC2420’s **TX current** depends on the **output power**.

Example (typical) transmit currents:

| Output Power (dBm) | Typical TX Current (mA) |
|--------------------|-------------------------|
| -25                | 8.5                     |
| -15                | 9.9                     |
| -10                | 11                      |
| -5                 | 14                      |
| 0                  | 17.4                    |

- **RX current**: 18.8 mA  
- Energy scales **linearly** with TX current. Lower output power → proportionally lower energy consumption.

---

## 9. Relating Transmission Energy to Battery Lifetime

Consider **two AA alkaline batteries in series**.

### 9.1 Battery Energy

- Voltage ≈ 3.0 V  
- Capacity ≈ 2000 mAh  
- Total energy:

\[
E_\text{bat} = 3.0 \text{ V} \times 2.0 \text{ Ah} = 6.0 \text{ Wh} \approx 21{,}600 \text{ J}
\]

---

### 9.2 Example Packet Energy (CC2420 @ 0 dBm, 3.0 V)

- Energy per byte ≈ 1.67 µJ  
- 50-byte packet → ≈ 94 µJ  
- With overhead (startup/PLL) → ≈ 104 µJ per packet  
  - This includes about 10 µJ due to RX/TX PLL turnaround (≈192 µs).

---

### 9.3 Number of Packets from Two AA Cells

Ignoring idle/sleep energy:

- Packets:

\[
\text{Packets} = \dfrac{21{,}600 \text{ J}}{1.04 \times 10^{-4} \text{ J}} \approx 2.08 \times 10^{8} \text{ packets}
\]

- If one packet is sent per second:

\[
\text{Lifetime} \approx 2.08 \times 10^{8} \text{ s} \approx 6.6 \text{ years (theoretical upper bound)}
\]

---

### 9.4 Including Baseline Power Draw

Average power:

\[
P_\text{avg} = r \times E_\text{pkt} + V \times I_\text{base}
\]

Lifetime:

\[
\text{Lifetime} = \dfrac{E_\text{bat}}{P_\text{avg}}
\]

Where:

- \( r \): packet rate (packets/s)  
- \( E_\text{pkt} \): energy per packet  
- \( I_\text{base} \): baseline current draw  

Example scenarios (V = 3.0 V, \(E_\text{bat} = 21{,}600 \text{ J}\), \(E_\text{pkt} = 1.04 \times 10^{-4} \text{ J}\)):

| Packet Rate (r) | Baseline Current \(I_\text{base}\) | Average Power \(P_\text{avg}\) (W) | Lifetime (s) | Lifetime (days) |
|-----------------|-------------------------------------|-------------------------------------|--------------|-----------------|
| 1 pkt/min       | 100 µA                              | 0.000302                            | 2.5×10⁷      | ≈ 291           |
| 1 pkt/s         | 500 µA                              | 0.001604                            | 1.35×10⁷     | ≈ 156           |
| 1 pkt/s         | 5 mA                                | 0.015104                            | 1.43×10⁶     | ≈ 16.6          |

---

### 9.5 Continuous Transmission Limit

If the CC2420 transmits **continuously** at 0 dBm:

- TX current \(I_\text{TX} \approx 17.4 \text{ mA}\)

Battery life:

\[
\text{Lifetime} \approx \dfrac{2000 \text{ mAh}}{17.4 \text{ mA}} \approx 115 \text{ hours} \approx 4.8 \text{ days}
\]

---

### 9.6 Lifetime Formula Summary

To estimate your specific node lifetime:

1. Compute battery energy  

   \[
   E_\text{bat} = V \times \text{Ah} \times 3600
   \]

2. Compute per-packet energy  

   \[
   E_\text{pkt} = \dfrac{V \times I_\text{TX} \times 8 \times (N + 6)}{250{,}000}
   \]

3. Choose your:
   - Packet send rate \(r\) (packets/s)
   - Baseline current \(I_\text{base}\)

4. Compute:

   \[
   \text{Lifetime} = \dfrac{E_\text{bat}}{r \times E_\text{pkt} + V \times I_\text{base}}
   \]
