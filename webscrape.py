import gzip
import os
import json
import subprocess
import re
import requests
from bs4 import BeautifulSoup
import time

# Constants and Configuration
LOCAL_MAN_PATH = "/usr/share/man/man1"  # Path to local man pages
OUTPUT_JSON = "man_pages.json"          # Output JSON file
TEST_FILE = "out.groff"                 # Temporary Groff file
HTML_OUT_DIR = "pages/"                 # Directory to save HTML pages

DIE_NET_BASE_URL = "https://linux.die.net/man/"  # Base URL for die.net man pages
SCRAPE_DELAY = 1  # Delay in seconds between HTTP requests to be respectful
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "text/html,application/xhtml+xml",
    # Add other headers if necessary
}

ANSI_FORMAT = False  # Whether to clear ANSI formatting
GROFF_FORMAT = False  # Whether to process Groff formatting
SCRAPE_ONLY = True   # Set to True to only scrape die.net for man pages

REQUIRED_SECTIONS = ["NAME", "DESCRIPTION", "USAGE", "OPTIONS"]  # Required sections
GROFF_MACROS = [".SH", ".TH", ".PP", ".br"]  # Minimal Groff macros


# Ensure output directories exist
os.makedirs(HTML_OUT_DIR, exist_ok=True)

def clear_terminal_formatting(text):
    """
    Removes ANSI escape sequences from the text.
    """
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def groff_to_html(groff_content):
    """
    Converts Groff content to HTML using the groff command.
    """
    result = subprocess.run(
        ["groff", "-Thtml", "-man"],
        input=groff_content,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if result.returncode != 0:
        print("Groff to HTML conversion error:", result.stderr)
        return None
    return result.stdout

def html_to_groff(html_content):
    """
    Converts HTML content to Groff format by mapping HTML tags to Groff macros.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    groff_output = []

    for element in soup.recursiveChildGenerator():
        if element.name:
            if element.name == "h1":
                groff_output.append(f".SH {element.get_text(strip=True)}\n")
            elif element.name == "h2":
                groff_output.append(f".SS {element.get_text(strip=True)}\n")
            elif element.name == "p":
                groff_output.append(".PP\n")
                groff_output.append(f"{element.get_text(strip=True)}\n")
            elif element.name == "pre":
                groff_output.append(".nf\n")
                groff_output.append(f"{element.get_text()}\n")
                groff_output.append(".fi\n")
            elif element.name == "li":
                groff_output.append(f".IP \\(bu\n{element.get_text(strip=True)}\n")
            elif element.name == "b":
                groff_output.append(f"\\fB{element.get_text(strip=True)}\\fP")
            elif element.name == "i":
                groff_output.append(f"\\fI{element.get_text(strip=True)}\\fP")
            # Add more tag mappings as needed
        elif isinstance(element, str):
            groff_output.append(element)

    return "".join(groff_output)

def is_standard_groff(content):
    """
    Checks if the Groff content contains the required standard elements.
    Args:
        content (str): The Groff file content as a string.
    Returns:
        bool: True if all elements are present, False otherwise.
    """
    # Check for required sections
    has_sections = all(section in content.upper() for section in REQUIRED_SECTIONS)
    # Check for minimal Groff macros
    has_groff_formatting = any(macro in content for macro in GROFF_MACROS)
    return has_sections and has_groff_formatting

def scrape_die_net(command, section=1):
    """
    Scrapes the man page for a given command from linux.die.net.
    Args:
        command (str): The command to scrape.
        section (int): The man page section.
    Returns:
        str or None: HTML content of the man page or None if not found.
    """
    url = f"{DIE_NET_BASE_URL}{section}/{command}"

    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            print(f"Scraped man page from die.net: {command}")
            return response.text
        else:
            print(f"Man page not found on die.net: {command} (Status Code: {response.status_code})")
            return None
    except Exception as e:
        print(f"Error scraping {command} from die.net: {e}")
        return None

def process_scraped_man_pages(commands, section=1):
    """
    Processes man pages scraped from die.net.
    Args:
        commands (list): List of command names to scrape and process.
    Returns:
        list: List of dictionaries with filename and content.
    """
    data = []
    total_commands = len(commands)
    for idx, command in enumerate(commands):
        print(f"Processing scraped man page: {command} ({idx+1}/{total_commands})")
        html_content = scrape_die_net(command, section)
        if html_content:
            # Convert HTML to Groff
            groff_content = html_to_groff(html_content)
            if groff_content:
                # Verify standard formatting
                if is_standard_groff(groff_content):
                    print(f"Valid Groff formatting for {command}")
                    data.append({"filename": f"{command}.groff", "content": groff_content})

                    # Save Groff file
                    groff_file_path = os.path.join(HTML_OUT_DIR, f"{command}.groff")
                    with open(groff_file_path, 'w') as groff_file:
                        groff_file.write(groff_content)

                    # Convert Groff back to HTML
                    converted_html = groff_to_html(groff_content)
                    if converted_html:
                        # Save converted HTML
                        html_file_path = os.path.join(HTML_OUT_DIR, f"{command}.html")
                        with open(html_file_path, 'w') as htmlfile:
                            htmlfile.write(converted_html)
                    else:
                        print(f"Failed to convert Groff to HTML for {command}")
                else:
                    print(f"Non-standard Groff formatting for {command}")
            else:
                print(f"Failed to convert HTML to Groff for {command}")
        else:
            print(f"Skipping {command} due to scraping failure.")

        # Respectful scraping: avoid overwhelming the server
        time.sleep(SCRAPE_DELAY)

    return data

def get_commands_from_die_net(section=1):
    """
    Retrieves a list of commands from die.net by parsing the man page index.
    Args:
        section (int): The man page section to scrape.
    Returns:
        list: List of command names.
    """
    commands = []
    url = f"{DIE_NET_BASE_URL}{section}/"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            # Find all links to man pages in the section
            links = soup.find_all('a', href=True)
            print(links)
            for link in links:
                href = link['href']
                # Example href: "/man/1/ls"
                if href.startswith(f"/man/{section}/"):
                    command = href.split(f"/man/{section}/")[-1]
                    if command and command not in commands:
                        commands.append(command)
        else:
            print(f"Failed to retrieve index for section '{section}': Status {response.status_code}")
    except Exception as e:
        print(f"Error retrieving index for section '{section}': {e}")

    print(f"Total scraped commands from die.net section {section}: {len(commands)}")
    return commands

def extract_man_pages():
    """
    Extracts and processes man pages by scraping die.net.
    Returns:
        list: List of man pages from scraped sources.
    """
    # Get list of commands from die.net
    commands = []
    # You can specify which sections to scrape
    sections = [1, 2, 3, 4, 5, 6, 7, 8]  # Standard man sections
    for section in sections:
        print(f"Retrieving commands from die.net section {section}...")
        section_commands = get_commands_from_die_net(section)
        commands.extend([(cmd, section) for cmd in section_commands])

    # Remove duplicates
    commands = list(set(commands))
    print(f"Total unique commands to process: {len(commands)}")

    # Process scraped man pages
    scraped_data = []
    total_commands = len(commands)
    for idx, (command, section) in enumerate(commands):
        print(f"Processing {command} from section {section} ({idx+1}/{total_commands})")
        html_content = scrape_die_net(command, section)
        if html_content:
            # Convert HTML to Groff
            groff_content = html_to_groff(html_content)
            if groff_content:
                # Verify standard formatting
                if is_standard_groff(groff_content):
                    print(f"Valid Groff formatting for {command}")
                    scraped_data.append({"filename": f"{command}.{section}.groff", "content": groff_content})

                    # Save Groff file
                    groff_file_path = os.path.join(HTML_OUT_DIR, f"{command}.{section}.groff")
                    with open(groff_file_path, 'w') as groff_file:
                        groff_file.write(groff_content)

                    # Convert Groff back to HTML
                    converted_html = groff_to_html(groff_content)
                    if converted_html:
                        # Save converted HTML
                        html_file_path = os.path.join(HTML_OUT_DIR, f"{command}.{section}.html")
                        with open(html_file_path, 'w') as htmlfile:
                            htmlfile.write(converted_html)
                    else:
                        print(f"Failed to convert Groff to HTML for {command}")
                else:
                    print(f"Non-standard Groff formatting for {command}")
            else:
                print(f"Failed to convert HTML to Groff for {command}")
        else:
            print(f"Skipping {command} due to scraping failure.")

        # Respectful scraping: avoid overwhelming the server
        time.sleep(SCRAPE_DELAY)

    return scraped_data

def main():
    """
    Main function to extract, process, and save man pages.
    """
    print("Starting man pages extraction and processing...")

    if SCRAPE_ONLY:
        # Only scrape man pages from die.net
        man_pages = extract_man_pages()
    else:
        # Extract local man pages and scrape missing ones (original behavior)
        man_pages = extract_man_pages_with_local(LOCAL_MAN_PATH)

    # Save to JSON
    try:
        with open(OUTPUT_JSON, 'w') as outfile:
            json.dump(man_pages, outfile, indent=2)
        print(f"Saved extracted data to {OUTPUT_JSON}")
    except Exception as e:
        print(f"Error saving to JSON: {e}")

    # Generate a main index HTML
    try:
        with open("index.html", 'w') as index_file:
            index_file.write("<html><head><title>Man Pages</title></head><body>\n")
            index_file.write("<h1>Man Pages Index</h1>\n<ul>\n")
            for page in man_pages:
                filename = page['filename']
                html_filename = f"{filename.replace('.groff', '')}.html"
                index_file.write(f'<li><a href="pages/{html_filename}">{filename}</a></li>\n')
            index_file.write("</ul>\n</body></html>")
        print("Generated main index HTML at 'index.html'")
    except Exception as e:
        print(f"Error generating index HTML: {e}")

if __name__ == "__main__":
    main()

