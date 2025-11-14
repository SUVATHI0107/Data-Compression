# Data-Compression
Python implementation of time-series floating-point compression. Includes our proposed ACTF algorithm and existing CHIMP and Gorilla compressors. Supports compression, and reconstruction accuracy checks for real-world sensor streams.
# Floating-Point Time-Series Data Compression  
### ACTF (Proposed) vs Chimp vs Gorilla

This repository implements and compares three compression algorithms for floating-point time-series data:

- **ACTF (Adaptive Chunked Temporal Framework)** – Proposed method  
- **Chimp** – Existing state-of-the-art compression  
- **Gorilla** – Facebook's time-series compression model  

The project includes:
- Compression of raw floating-point time-series streams  
- Decompression and lossless verification  
- Comparison of compression ratio, space savings, and time efficiency  
- Support for any user-provided floating-point dataset  

---

## Features
- Handles high-precision floating-point sequences  
- Chunk-wise adaptive compression (ACTF)  
- Bit-level XOR and prediction-based encoding (Chimp & Gorilla)  
- Complete compression + decompression pipeline  
- Works for real-time or stored time-series

---

## Project Structure
actf.py → proposed ACTF algorithm
chimp.py → chimp compression + decompression
gorilla.py → gorilla compression + decompression
comparison.py → compares ACTF, Chimp, Gorilla
