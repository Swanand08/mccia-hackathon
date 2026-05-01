# PackRight AI Inventory Intelligence System

A professional-grade, AI-powered inventory forecasting and procurement recommendation engine designed for packaging manufacturing.

## Features
- **Dynamic Forecasting**: BOM-aware demand calculation.
- **Credit-Aware Procurement**: Recommends orders while respecting credit limits and MOQs.
- **Excess Stock Identification**: Flags idle capital.
- **Interactive UI**: Streamlit dashboard with Claude AI integration.
- **Excel Reporting**: Generates formatted, multi-sheet weekly reports.

## Setup Instructions

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   - Copy `.env.example` to `.env`
   - Add your Anthropic API key: `ANTHROPIC_API_KEY=your_key_here`

3. **Generate Data**:
   ```bash
   python generate_data.py
   ```

4. **Run the Dashboard**:
   ```bash
   streamlit run app.py
   ```

5. **Run the CLI Pipeline (Optional)**:
   ```bash
   python main.py
   ```