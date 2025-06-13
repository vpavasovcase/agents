# Receipt Processing Agent

A complete, working receipt processing agent that:
1. Reads receipt images from a folder
2. Extracts data using OCR capabilities
3. Saves the data to a PostgreSQL database
4. Provides analysis capabilities for spending

## Setup

### Prerequisites
- Docker and Docker Compose
- Node.js (for MCP servers)
- Groq API key (for the LLM model)

### Environment Variables
Create a `.env` file with the following variables. change the values, the ones here are just for reference:
```
GROQ_API_KEY=your_groq_api_key
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/postgres
DATABASE_HOST=postgres
DATABASE_PORT=5432
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DATABASE_NAME=postgres
```
## Usage

### Processing Receipts
1. Copy receipt images to the `receipt-processor/receipts` folder
2. Process all receipts:
   ```bash
   docker-compose exec app python -m receipt_processor.app process-all
   ```
3. Process only new receipts (added today):
   ```bash
   docker-compose exec app python -m receipt_processor.app process-new
   ```

### Analyzing Spending
Run spending analysis with natural language queries:
```bash
python -m receipt_processor.app analyze "how much did I spend last month"
python -m receipt_processor.app analyze "what's my spending by category"
python -m receipt_processor.app analyze "how much did I spend at Walmart"
```

## Features

### Receipt Processing
- Extracts store name, date, total amount, and individual items
- Supports various image formats (JPEG, PNG, PDF, TIFF, BMP, GIF)
- Uses a hybrid OCR approach:
  1. First attempts traditional OCR with Tesseract
  2. Enhances OCR results with LLM processing
  3. Falls back to direct LLM vision processing if OCR fails
- Saves structured data to a PostgreSQL database

### Spending Analysis
- Analyze spending by time period (today, yesterday, this week, last month, etc.)
- Filter by category or store
- Get breakdowns by category, store, or date

## Database Schema

### Receipts Table
- `id`: Primary key
- `store_name`: Name of the store
- `date`: Date and time of purchase
- `total_amount`: Total amount on the receipt
- `payment_method`: Method of payment (optional)
- `receipt_id`: Unique identifier for the receipt (optional)
- `tax_amount`: Tax amount (optional)
- `currency`: Currency code (default: USD)
- `image_path`: Path to the receipt image
- `created_at`: Timestamp when the record was created

### Receipt Items Table
- `id`: Primary key
- `receipt_id`: Foreign key to receipts table
- `name`: Name of the item
- `price`: Price of the item
- `quantity`: Quantity of the item (default: 1.0)
- `category`: Category of the item (optional)
- `created_at`: Timestamp when the record was created
