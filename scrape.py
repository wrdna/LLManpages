import gzip
import os
import json
import subprocess
import re

PATH = "/usr/share/man/" 
SECTIONS = ["man1"]# ,"man2","man3","man4","man5","man6","man7", "man8"]
OUTPUT_FILE = "man_pages.json"
TEST_FILE = "out.groff"

HTML_OUT = "index.html"
HTML_OUT_DIR = "pages/"

CREATE_HTML = False 
CREATE_GROFF = False 

REMOVE_ANSI_FORMAT = True 
REMOVE_GROFF_FORMAT = True 

history = { "totalValid" : 0,
           "totalNonvalid"  : 0,
        }

def clear_terminal_formatting(text):
    # Regular expression to match ANSI escape sequences
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def groff_to_html(groff_content):
    html = subprocess.run(
        ["groff","-Thtml", "-man"],  
        input=groff_content,
        text=True,             
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE 
    )
    return html.stdout

def is_standard_groff(content):
    required_sections = ["NAME"]
    groff_macros = [".SH", ".TH", ".PP", ".br"]
    has_sections = all(section in content.upper() for section in required_sections)
    has_groff_formatting = any(macro in content for macro in groff_macros)

    return has_sections and has_groff_formatting


def handle_groff(content):
    def remove_groff_format(content):
        status = False
        content = subprocess.run(
            ["groff", "-Tutf8","-man"],  
            input=content,
            text=True,             
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE 
        )
        if content.returncode == 0:
        
            if REMOVE_ANSI_FORMAT:
                content = clear_terminal_formatting(content.stdout)
            else:
                content = content.stdout
            
            status = True 
        else:
            print("Error:")
            print(content.stderr)
            status = False
    
        return status, content

    status, content = remove_groff_format(content)
    if not status:
        return status
    return status, content

def parse_groff_subsections(groff_content):
    # Uses .SH macro to find section titles
    section_regex = re.compile(r'^\s*\.SH\s+"?([\w\s\-:]+)"?\s*$', re.MULTILINE)
    matches = list(section_regex.finditer(content))

    print(matches)
    sections = {}

    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section_content = content[start:end].strip()
        sections[title] = section_content

    return sections

def extract_and_map_sections(groff_content, cleaned_content):

    section_regex = re.compile(r'^\s*\.SH\s+"?(.*?)"?\s*$', re.MULTILINE)
    
    # extract section headers and positions from the original Groff content
    matches = list(section_regex.finditer(groff_content))
    
    if not matches:
        print("No sections found in Groff content.")
        return {}

    # extract subsections and their content from the Groff content
    subsections = {}
    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(groff_content)
        groff_section_content = groff_content[start:end].strip()
        subsections[title] = groff_section_content

    mapped_sections = {}
    for i, title in enumerate(subsections):
        if title in cleaned_content:
            # print("TITLE:", title)
            start = cleaned_content.index(title) + len(title)  # skip the title text itself
            
            if i + 1 < len(subsections):
                # find the next title to determine the end position
                next_title = list(subsections.keys())[i + 1]
                end = cleaned_content.find(next_title, start)
            else:
                # for the last section, take everything until the end
                end = len(cleaned_content)
            
            # extract the section content, skip title
            section_content = cleaned_content[start:end].strip()
            mapped_sections[title] = section_content
        else:
            print(f"Warning: Title '{title}' not found in cleaned content.")

    return mapped_sections


def extract_man_pages(path, sections):
    data = []
    try:
        os.mkdir(HTML_OUT_DIR)
    except FileExistsError:
        print(f"{HTML_OUT_DIR} EXISTS")

    print(f"TOTAL MAN ENTRIES: {len(os.listdir(path))}")

    for section in sections:
        abs_path = os.path.join(path, section)

        for idx, file in enumerate(os.listdir(abs_path)):
            file_path = os.path.join(abs_path, file)

            if file.endswith(".gz"):
                try:
                    with gzip.open(file_path, 'rt', encoding='utf-8', errors='ignore') as f:
                        groff_content = f.read()
                        name_split = file.split('.')[0]

                        if is_standard_groff(groff_content):
                            cleaned_content = groff_content

                            if REMOVE_GROFF_FORMAT:
                                status, cleaned_content = handle_groff(groff_content)
                                if not status:
                                    continue

                            subsections = extract_and_map_sections(groff_content, cleaned_content)

                            data.append({"name": name_split, "sections": subsections})

                            print(f"SUCCESS {idx} {file}")

                            if CREATE_GROFF:
                                groff_filename = f"{file.split('.')[0]}.groff"
                                groff_path = os.path.join(HTML_OUT_DIR, groff_filename)
                                with open(groff_path, 'w', encoding='utf-8') as test:
                                    test.write(groff_content)

                            if CREATE_HTML:
                                html_content = groff_to_html(cleaned_content)
                                html_filename = f"{file.split('.')[0]}.html"
                                html_path = os.path.join(HTML_OUT_DIR, html_filename)
                                with open(html_path, 'w', encoding='utf-8') as htmlfile:
                                    htmlfile.write(html_content)

                        else:
                            print(f'NON STANDARD FORMATTING {idx} {file}')
                            continue

                except Exception as e:
                    print(f"Error processing {file}: {e}")

    return data



def print_man_page(filename):
    command_name = filename.split(".")[0]
    try:
        result = subprocess.run(
            ["man", command_name],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"Error opening man page for {command_name}: {result.stderr}")
    except Exception as e:
        print(f"Failed to open man page: {e}")


def main():
    SAVE = True
    if SAVE:
        man_pages = extract_man_pages(PATH, SECTIONS)
        with open(OUTPUT_FILE, 'w') as outfile:
            json.dump(man_pages, outfile, indent=2)
        print(f"Saved extracted data to {OUTPUT_FILE}")

    # with open('man_pages.json', 'r') as infile:
    #     man_pages = json.load(infile)
    # 
    # filename = input("Enter the man page filename (e.g., 'ls.1.gz') or press Enter to print all: ").strip()

    # if filename != '':
    #     print_man_page(filename)
     

if __name__ == "__main__":
    main()

