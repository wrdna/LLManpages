import json
import itertools

def generate_combinations(sections):
    combinations_list = []
    
    # iterate over all possible input section sizes (1 to len(sections)-1)
    for r in range(1, len(sections)):
        for input_sections in itertools.combinations(sections, r):
            output_sections = [s for s in sections if s not in input_sections]
            combinations_list.append((list(input_sections), output_sections))
    
    return combinations_list

def generate_fine_tuning_samples(data_file, output_file):
    with open(data_file, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
    
    total_entries = len(dataset)
    with open(output_file, 'w', encoding='utf-8') as f_out:
        for idx, entry in enumerate(dataset):
            sections = entry['sections']
            section_titles = list(sections.keys())
    
            if len(section_titles) < 2: 
                print(f"Skipping {entry.get('name', 'Unknown Filename')} - Not enough sections. {len(section_titles)}")
                continue

            if len(section_titles) > 10:
                print(f"Skipping {entry.get('name', 'Unknown Filename')} - Too many sections. {len(section_titles)}")
                continue
    
            combinations = generate_combinations(section_titles)
    
            # print(len(combinations), section_titles)

            for input_sections, output_sections in combinations:

                input_content = "\n".join(
                    f"<SECTION>{title}</SECTION>\n{sections[title].strip()}"
                    for title in input_sections
                )

                output_content = "\n".join(
                    f"<SECTION>{title}</SECTION>\n{sections[title].strip()}"
                    for title in output_sections
                )
                io_pair = {"input": input_content, "output": output_content}

                f_out.write(json.dumps(io_pair) + '\n')
    
            print(f"{idx + 1}/{total_entries}: {entry.get('name', 'Unknown Filename')}")
    
    print(f"Fine-tuning samples have been saved to {output_file}")

generate_fine_tuning_samples('man_pages.json', 'masked_man_pages.json')

