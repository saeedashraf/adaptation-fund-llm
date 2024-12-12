# Project Name

A web scraping tool for collecting data from specified URLs of adaptation fund projects.

## Setup Instructions

1. Clone this repository:
   ```bash
   git clone https://github.com/saeedashraf/adaptation-fund-scraper.git .
   cd adaptation-fund-scraper
   ```

2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### 1. Prepare Input Links
1. Open `input_links.txt`
2. Add URLs to scrape, one per line
3. Save the file

### 2. Run the Scraper
1. Execute script #1:
   ```bash
   python script1.py
   ```
2. **Important**: Run script #1 multiple times to catch any dropped requests
3. Continue running until no new data is being scraped
   - Note: Some links may be dead/invalid
   - Scraping is complete when no new data is collected

### 3. Generate Output
1. Run script #2 to process the scraped data:
   ```bash
   python script2.py
   ```
2. The processed data will be saved to the specified output directory
