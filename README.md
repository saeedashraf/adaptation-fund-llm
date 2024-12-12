# Project Name

A web scraping tool for collecting data from specified URLs of adaptation fund projects.

## Prerequisites

Before running the scripts, ensure you have:
- Python 3.10 or above installed
- Required Python packages 

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

3. **Important Windows Setup**
   Before running the scripts, you need to remove the Windows path length limitation:
   1. Follow the instructions in the [Python Windows documentation](https://docs.python.org/3/using/windows.html#removing-the-max-path-limitation)
   2. This step is crucial as the scraper creates folders with long names
   3. Without this modification, you may encounter exceptions during file saving

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

### 4. Start Fresh (Optional)
To perform a fresh scraping run:
1. Delete the database file
2. Remove the output files folder
3. Repeat steps 1-3 above

## Troubleshooting

- If you encounter path-related errors, ensure you've completed the Windows path limitation removal step
- Dead links will be skipped automatically
- Check the logs for any error messages during scraping

## Contributing

[Add your contribution guidelines here]

## License

[Add your license information here]
