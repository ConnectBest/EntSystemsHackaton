# Assignment Materials

This directory contains the original materials provided for the CMPE273 Enterprise Systems Hackathon assignment.

## 📁 Contents

### CMPE273HackathonData/
Sample data and images for the assignment:
- **TurbineImages/** - Images of turbine sites for AI processing
- **ThermalEngines/** - Images of thermal engine operations
- **ElectricalRotors/** - Images of electrical rotor equipment
- **OilAndGas/** - Images of oil & gas connected devices
- **LogData/logfiles.log** - Apache-style system logs for analysis

### BP_10K/
BP plc annual reports in PDF format:
- `bp-annual-report-and-form-20f-2023.pdf` - 2023 Annual Report
- `bp-annual-report-and-form-20f-2024.pdf` - 2024 Annual Report

These documents are used for RAG (Retrieval-Augmented Generation) queries about BP operations, safety incidents, and procedures.

### DataTemplates/
JSON schema examples for device telemetry:
- `Turbine_sample.json` - Gas turbine telemetry schema
- `ThermalEngine_sample.json` - Thermal engine telemetry schema
- `ElectricalRoter_sample.json` - Electrical rotor telemetry schema
- `OGD_sample.json` - Oil & Gas connected device schema
- `users_sample.json` - User session data schema
- `Template_Device.json` - Generic device template

### Assignment Documents
- **ReadMe.pdf** - Original assignment instructions
- **CMPE273_SRE_AI_Agentic_Hackathon_Hackathon_WireFrames-1.pdf** - Wireframes and design mockups

## 🔗 How These Are Used

### In Docker Services

The materials are mounted as volumes in the following services:

1. **Backend** (`/app/data` and `/app/bp_docs`)
   - Access to all data for API endpoints

2. **Image Processor** (`/app/images`)
   - Processes images from CMPE273HackathonData subdirectories
   - Generates AI embeddings using Cohere
   - Detects safety compliance (hard hats, equipment)

3. **RAG Service** (`/app/logs` and `/app/bp_docs`)
   - Analyzes system logs from LogData/
   - Queries BP annual reports for operational information
   - Provides natural language answers

### Data Attribution

All images are sourced from the Internet and remain the property of their respective owners. This project is for educational purposes only.

BP annual reports are publicly available documents from BP plc.

---

**Note:** These materials are read-only. The solution code resides in the parent directories (backend/, services/, simulators/, frontend/).
