import re
import pandas as pd
import chardet
import os
import sys

def clean_description_from_extracted_values(description, extracted_values):
    """
    Remove extracted values from the description
    """
    for category, value in extracted_values.items():
        # Create patterns to remove the entire match
        removal_patterns = [
            # Keyword before value
            rf'(?:арт\.|артикул|код)\s*[:.]?\s*{re.escape(str(value))}',
            rf'(?:вага|weight|нетто)\s*[:.]?\s*{re.escape(str(value))}',
            rf'(?:кількість|qty|quantity)\s*[:.]?\s*{re.escape(str(value))}',
            
            # Value before keyword
            rf'{re.escape(str(value))}\s*(?:арт\.|артикул|код)',
            rf'{re.escape(str(value))}\s*(?:кг|kg|г|g)\s*(?:вага|weight|нетто)',
            rf'{re.escape(str(value))}\s*(?:шт|pcs|одиниць|pieces)'
        ]
        
        for pattern in removal_patterns:
            description = re.sub(pattern, '', description, flags=re.IGNORECASE)
    
    # Clean up extra spaces and punctuation
    description = re.sub(r'\s+', ' ', description)
    description = description.strip('.,; ')
    
    return description

def extract_contextual_values(text):
    """
    Extract values associated with specific keywords in various formats
    """
    # Define patterns for different types of information
    patterns = {
        'article_number': [
            # Keyword before value
            r'(?:арт\.|артикул|код)\s*[:.]?\s*([\w\-\.]+)',
            # Value before keyword
            r'([\w\-\.]+)\s*(?:арт\.|артикул|код)'
        ],
        'weight': [
            # Keyword before value
            r'(?:вага|weight|нетто)\s*[:.]?\s*(\d+(?:[.,]\d+)?)\s*(?:кг|kg|г|g)',
            # Value before keyword
            r'(\d+(?:[.,]\d+)?)\s*(?:кг|kg|г|g)\s*(?:вага|weight|нетто)'
        ],
        'quantity': [
            # Keyword before value
            r'(?:кількість|qty|quantity)\s*[:.]?\s*(\d+)',
            # Value before keyword
            r'(\d+)\s*(?:шт|pcs|одиниць|pieces)'
        ]
    }
    
    extracted_values = {}
    
    for category, keyword_patterns in patterns.items():
        for pattern in keyword_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                
                # Additional validation
                if category == 'article_number':
                    # Ensure it's a valid article number
                    if re.match(r'^[\w\-\.]+$', value):
                        extracted_values[category] = value
                elif category == 'weight':
                    # Ensure it's a valid number
                    try:
                        float(value.replace(',', '.'))
                        extracted_values[category] = f"{value} кг"
                    except ValueError:
                        pass
                elif category == 'quantity':
                    # Ensure it's a valid integer
                    try:
                        int(value)
                        extracted_values[category] = int(value)
                    except ValueError:
                        pass
    
    return extracted_values

def extract_main_description(text):
    """
    Extract main description with contextual value extraction
    """
    # First, extract contextual values
    extracted_values = extract_contextual_values(text)

    # List of indicators that signal the end of the main product description
    end_indicators = [
        # Quantities and measurements
        r'\d+\s*(?:кг|kg|г|g|мм|mm|см|cm|м|m)',
        r'(?:загальн(?:ою|а)\s+(?:вага|кількість|маса))',
        r'(?:вага|weight|нетто|брутто)',
        r'в\s+упаковках\s+масою',
        r'\d+\s*(?:шт|pcs|штук|pieces)',
        r'\d+\s*(?:мішків|упак|boxes|packs)',
        
        # Brand and manufacturer info
        r'торгов(?:а|ельна)\s+марка',
        r'виробник',
        r'країна\s+(?:походження|виробництва)',
        
        # Product identifiers
        r'арт\.',
        r'артикул',
        r'код',
        r'lot',
        r'партія',
        
        # Other technical info
        r'термін\s+придатності',
        r'виготовлено',
        r'контейнер'
    ]
    
    # Create pattern that matches any of these indicators
    combined_pattern = '|'.join(f'(?:{p})' for p in end_indicators)
    
    # Find the first occurrence of any indicator
    match = re.search(combined_pattern, text, re.IGNORECASE)
    
    if match:
        # Take everything before the first indicator
        main_desc = text[:match.start()].strip()
    else:
        # If no indicators found, take first sentence
        main_desc = re.split(r'[.!?]', text)[0].strip()
    
    # Clean up description by removing extracted values
    main_desc = clean_description_from_extracted_values(main_desc, extracted_values)
    
    # Final cleanup
    main_desc = re.sub(r'^[\d\.\s]+\.?\s*', '', main_desc)  # remove leading numbers and dots
    main_desc = re.sub(r'\s+', ' ', main_desc)  # normalize spaces
    main_desc = main_desc.strip('.,; ')
    
    return main_desc

def extract_value_around_keyword(text, keyword, max_chars=50):
    """
    Extract value that might appear before or after a keyword,
    handling complex values with dashes, commas, etc.
    """
    # Create pattern that looks both before and after the keyword
    pattern = f"""
        # Look before keyword
        (?:
            ([\w\d\-\.]+(?:\s*[\-,\.]\s*[\w\d\-\.]+)*)  # Value before
            \s*{keyword}
        )|
        # Look after keyword
        (?:
            {keyword}\s*
            ([\w\d\-\.]+(?:\s*[\-,\.]\s*[\w\d\-\.]+)*)  # Value after
        )
    """
    
    match = re.search(pattern, text, re.VERBOSE | re.IGNORECASE)
    if match:
        # Return the group that matched (before or after)
        return match.group(1) if match.group(1) else match.group(2)
    return None

# Example usage in rules:
PARSING_RULES = {
##    'article_numbers': {
#        'keywords': ['арт', 'артикул', 'код', 'art', 'article','lot', 'лот'],
#        'value_pattern': r'[\w\d\-\.]+(?:\s*[\-,\.]\s*[\w\d\-\.]+)*'  # Matches complex values
#    },
    'model_numbers': {
        'keywords': ['модель', 'model', 'мод'],
        'value_pattern': r'[\w\d\-\.]+(?:\s*[\-,\.]\s*[\w\d\-\.]+)*'
    },
#    'weight_indicators': {
#        'keywords': ['вага', 'weight', 'нетто', 'брутто', 'кг', 'kg', 'г', 'g'],
#        'pattern': r'(?:чиста\s+)?(?:вага|weight|нетто|брутто)?\s*:?\s*(\d+(?:[\.,]\d+)?)\s*(?:кг|kg|г|g)',
#        'cleanup': True  # Should be removed from technical specs
#    },
    'date_indicators': {
        'keywords': ['врожай', 'виготовлен', 'термін', 'дата'],
        'pattern': r'(?:врожаю|виготовлене?|термін придатності|дата)\s*:?\s*(\d{1,2}/\d{4}|\d{4})\s*(?:р\.?)?',
        'cleanup': False  # Keep in technical specs
    }    
    # Add more as needed
}

def extract_technical_specs(text, main_description):
    """
    Extract technical specifications while properly handling various indicators
    """
    specs = text
    
    # Remove main description
    specs = specs.replace(main_description, '')
    
    # Extract and remove cleanup items
    for rule_type, rule in PARSING_RULES.items():
        if rule.get('cleanup', False):
            matches = re.finditer(rule['pattern'], specs, re.IGNORECASE)
            for match in matches:
                specs = specs.replace(match.group(0), '')
    
    # Clean up the remaining text
    specs = re.sub(r'\s+', ' ', specs)
    specs = specs.strip(' .,;')
    
    return specs if specs.strip() else None

def smart_split_products(text):
    """
    Smart product splitting that considers various indicators
    """
    # First, extract the main product description
    # Usually everything before the first technical parameter
    desc_end_indicators = [
        r'чиста\s+вага',
        r'lot\.',
        r'арт\.',
        r'виготовлен',
        r'врожаю',
        r'термін',
        r'торговельна\s+марка'
    ]
    
    desc_pattern = f"^(.*?)(?={'|'.join(desc_end_indicators)})"
    desc_match = re.search(desc_pattern, text, re.IGNORECASE | re.DOTALL)
    main_description = desc_match.group(1).strip() if desc_match else text

    # Extract lot numbers which might indicate separate products
    lot_pattern = PARSING_RULES['lot_numbers']['pattern']
    lot_match = re.search(lot_pattern, text, re.IGNORECASE)
    
    products = []
    if lot_match:
        lot_numbers = re.split(PARSING_RULES['lot_numbers']['split_pattern'], lot_match.group(1))
        # Create a product entry for each lot number
        for lot in lot_numbers:
            products.append({
                'description': main_description,
                'lot': lot.strip(),
                'original_text': text
            })
    else:
        # If no lot numbers found, treat as single product
        products.append({
            'description': main_description,
            'original_text': text
        })

    return products

def smart_extract_values(text, rules=PARSING_RULES):
    """
    Smart extraction that handles values before and after keywords
    """
    extracted_values = {}
    
    for category, rule in rules.items():
        for keyword in rule['keywords']:
            value = extract_value_around_keyword(text, keyword)
            if value:
                extracted_values[category] = value.strip()
                break  # Found a value for this category
                
    return extracted_values

def extract_global_attributes(row):
    """
    Extract global attributes (manufacturer, brand, country) that apply to all products in the row.
    """
    # Expanded manufacturer patterns
    manufacturer_patterns = [
        r"(Виробник|Manufacturer|Made by)\s*-?\s*(.*?)(?=(?:Країна|Торг|$))",  # Modified to look ahead
        r"Виробник\s*:\s*(.*?)(?=(?:Країна|Торг|$))",
        r"(?:Виготовлено|Вир\.)\s*:?\s*-?\s*(.*?)(?=(?:Країна|Торг|$))"
    ]
    
    manufacturer = "Unknown"
    for pattern in manufacturer_patterns:
        match = re.search(pattern, row, flags=re.IGNORECASE)
        if match:
            manufacturer = match.group(2).strip() if len(match.groups()) > 1 else match.group(1).strip()
            break

    # Expanded brand patterns
    brand_patterns = [
        r"(?:Торговельна марка|Brand|Торг\. марка|Марка)\s*:?\s*-?\s*(.*?)(?=(?:Країна|Виробник|$))",  # Modified
        r"(?:під\s+)?(?:торговою\s+)?маркою\s+['\"]?(.*?)['\"]?(?=(?:Країна|Виробник|$))",
        r"TM\s*['\"]?(.*?)['\"]?(?=(?:Країна|Виробник|$))"
    ]
    
    brand = "Unknown"
    for pattern in brand_patterns:
        match = re.search(pattern, row, flags=re.IGNORECASE)
        if match:
            brand = match.group(1).strip()
            break

    # Expanded country patterns
    country_patterns = [
        r"(?:Країна виробництва|Country of Origin|Made in)\s*:?\s*-?\s*([A-Z]{2}|[A-Za-zА-Яа-я]+)(?=\s|$)",
        r"(?:Виготовлено в|Вироблено в)\s*([A-Za-zА-Яа-я]+)(?=\s|$)",
        r"Країна походження\s*:?\s*([A-Za-zА-Яа-я]+)(?=\s|$)"
    ]
    
    country = "Unknown"
    for pattern in country_patterns:
        match = re.search(pattern, row, flags=re.IGNORECASE)
        if match:
            country = match.group(1).strip()
            break

    # Clean up the values
    manufacturer = manufacturer.strip(' .,;:-')
    brand = brand.strip(' .,;:-')
    country = country.strip(' .,;:-')

    return {
        "Manufacturer": manufacturer,
        "Brand": brand,
        "Country": country
    }


def split_products(row):
    """
    Universal splitting logic for products with smart pattern recognition
    """
    if not row or not isinstance(row, str):
        return "", []

    # Check if row contains multiple products separated by semicolons
    semicolon_split = row.split(':')
    
    if len(semicolon_split) > 1:
        # First part before ':' is the main description
        main_description = semicolon_split[0].strip()
        
        # Products are in the parts after ':'
        product_parts = [part.strip() for part in semicolon_split[1].split(';')]
        
        products = []
        for product_text in product_parts:
            if product_text:
                # Ensure the product has a quantity indicator
                if re.search(r'\d+\s*(?:шт|pcs|кор|boxes|packs|мішків|kg|кг)', product_text):
                    products.append(product_text)
        
        # If no products found, use the whole text after ':'
        if not products:
            products = [semicolon_split[1].strip()]
        
        return main_description, products

    # If no semicolon split, use existing product splitting logic
    # First, extract the main description using the new method
    main_description = extract_main_description(row)

    # Product splitting patterns
    product_patterns = [
        # Pattern with quantity at the end
        r'(?:[A-ZА-ЯІЇЄ][^-\n]*?)\s*-\s*(\d+)\s*(?:шт|pcs|кор|boxes|packs|мішків|kg|кг)',
        
        # Pattern with article number and quantity
        r'(?:арт\.|артикул|код)\s*[:.]?\s*[A-Z0-9\-]+[^,]*?(\d+)\s*(?:шт|pcs|кор|boxes|packs)',
        
        # Pattern with quantity in parentheses
        r'[A-ZА-ЯІЇЄ][^(]*?\((\d+)\s*(?:шт|pcs|кор|boxes|packs|мішків|kg|кг)\)'
    ]
    
    products = []
    remaining_text = row

    # Find all product matches
    for pattern in product_patterns:
        matches = list(re.finditer(pattern, remaining_text, re.IGNORECASE))
        
        if matches:
            for match in matches:
                product_text = match.group(0).strip()
                
                # Clean up the product text
                product_text = re.sub(r'\s+', ' ', product_text)
                product_text = product_text.strip('.,;')
                
                products.append(product_text)

    # If no products found using patterns, try alternative splitting
    if not products:
        # Look for quantity indicators
        quantity_splits = re.split(r'(?<=\d)\s*(?:шт|pcs|кор|boxes|packs|мішків|kg|кг)[,;\s]*', row)
        products = [split.strip() for split in quantity_splits if re.search(r'\d+', split)]

    # If still no products, use the whole row
    if not products:
        products = [row]

    # Clean up products
    cleaned_products = []
    for product in products:
        # Remove global attribute information
        product = re.sub(r'Торговельна марка.*?(?=(?:Виробник|Країна|$))', '', product, flags=re.IGNORECASE)
        product = re.sub(r'Виробник.*?(?=(?:Країна|$))', '', product, flags=re.IGNORECASE)
        product = re.sub(r'Країна виробництва.*?$', '', product, flags=re.IGNORECASE)
        
        # Ensure the product has both name and quantity
        if re.search(r'\d+\s*(?:шт|pcs|кор|boxes|packs|мішків|kg|кг)', product):
            cleaned_products.append(product.strip())

    return main_description, cleaned_products


def parse_individual_product(product_section, product_description):
    """
    Enhanced parser with smart value extraction
    """
    # Extract contextual values
    extracted_values = extract_contextual_values(product_section)
    
    # Use extracted values
    model_article = extracted_values.get('article_number', 'Unknown')
    weight = extracted_values.get('weight')
    quantity = extracted_values.get('quantity')
    
    # Rest of the function remains the same...
    remaining_text = product_section
    
    # Remove extracted values from remaining text
    remaining_text = clean_description_from_extracted_values(remaining_text, extracted_values)
       
    # Use these values to help determine what's what
    if 'article_numbers' in extracted_values:
        model_article = extracted_values['article_numbers']
    else:
        model_article = "Unknown"
    
    remaining_text = product_section
    # Remove the extracted values from remaining text
    for value in extracted_values.values():
        remaining_text = remaining_text.replace(value, '')

    # First, try to identify the quantity and product name structure
    quantity_match = re.search(r'(.*?)\s*-\s*(\d+)\s*(шт|pcs|кор|boxes|packs|мішків|kg|кг)', product_section)
    if quantity_match:
        product_name = quantity_match.group(1).strip()
        quantity = int(quantity_match.group(2))
        remaining_text = remaining_text.replace(quantity_match.group(0), '').strip()
    else:
        # Try alternative quantity patterns
        quantity_patterns = [
            r'(\d+)\s*(шт|pcs|кор|boxes|packs|мішків|kg|кг)',
            r'кількість\s*[:.]?\s*(\d+)',
            r'(\d+)\s*(?:одиниць|pieces)',
            r'x\s*(\d+)(?:\s|$)',
            r'(\d+)\s*(?:штук|единиц|items)'
        ]
        
        quantity = None
        for pattern in quantity_patterns:
            match = re.search(pattern, remaining_text, flags=re.IGNORECASE)
            if match:
                quantity = int(match.group(1))
                remaining_text = remaining_text.replace(match.group(0), '').strip()
                break

    # Define base patterns
    model_patterns = [
        r"(Номер\s?(CAS|CAT):?\s?[\w\.\-/\\]+)",
        r"(арт\.:?\s?[\w\.\-/\\]+)",
        r"(артикул:?\s?[\w\.\-/\\]+)",
        r"(код:?\s?[\w\.\-/\\]+)",
        r"(№\s*[\w\.\-/\\]+)",
        r"([A-Z0-9][\w\-/\\]*\d+[\w\-/\\]*)",
        r"(\d{4,}(?:-[\w\-/\\]+)?)",
        r"((?:мод\.|модель)\s*[\w\.\-/\\]+)"
    ]
    
    # Process model/article
    model_article = "Unknown"
    for pattern in model_patterns:
        match = re.search(pattern, remaining_text, flags=re.IGNORECASE)
        if match:
            model_article = match.group(1).strip()
            remaining_text = remaining_text.replace(match.group(0), "").strip()
            break

    # Process weight
    weight_patterns = [
        r"(\d+(?:\.\d+)?)\s?(кг|kg|г|гр|g|мг|mg)",
        r"вага\s*[:.]?\s*(\d+(?:\.\d+)?)\s*(кг|kg|г|гр|g)",
        r"(\d+(?:\.\d+)?)\s*(тонн|tons|т)"
    ]
    
    weight = None
    for pattern in weight_patterns:
        match = re.search(pattern, remaining_text, flags=re.IGNORECASE)
        if match:
            weight = f"{match.group(1)} {match.group(2)}"
            remaining_text = remaining_text.replace(match.group(0), "").strip()
            break

    # Process packaging
    packaging_patterns = [
        r"(\d+\s?мішків|\d+\s?кор|boxes|packs|упак)",
        r"(\d+)\s*(коробок|упаковок|пакетів)",
        r"в\s*упаковці\s*(\d+)\s*(шт|pcs)"
    ]
    packaging = None
    for pattern in packaging_patterns:
        match = re.search(pattern, remaining_text, flags=re.IGNORECASE)
        if match:
            packaging = match.group(0).strip()
            remaining_text = remaining_text.replace(match.group(0), "").strip()
            break

    # Process chemical formula
    chemical_formula_patterns = [
        r"(?:[^\s]*?Хімічна формула|Хім\. формула|Формула|Хим\. формула|Формула хім\.|Формула речовини|Chemical Formula|Chem\. Formula|C\. Formula|Ф\. хім\.)\s*-?\s*([\w\*\.\d]+)",
        r"Chemical composition:\s*([\w\*\.\d]+)",
        r"Formula:\s*([\w\*\.\d]+)"
    ]
    
    chemical_formula = None
    for pattern in chemical_formula_patterns:
        match = re.search(pattern, remaining_text, flags=re.IGNORECASE)
        if match:
            chemical_formula = match.group(1).strip()
            remaining_text = remaining_text.replace(match.group(0), "").strip()
            break

    # Initialize manufacturer, brand, and country (will be filled by global attributes later)
    manufacturer = None
    brand = None
    country = None

    # Process technical specs
    if technical_specs := remaining_text.strip():
        # Remove product description content
        technical_specs = technical_specs.replace(product_description, '')
        
        # Remove all previously extracted information
        if model_article and model_article != "Unknown":
            technical_specs = technical_specs.replace(model_article, '')
        if quantity:
            technical_specs = re.sub(r'\d+\s*(шт|pcs|кор|boxes|packs|мішків|kg|кг)', '', technical_specs)
        if weight:
            technical_specs = technical_specs.replace(weight, '')
        if packaging:
            technical_specs = technical_specs.replace(packaging, '')
        if chemical_formula:
            technical_specs = technical_specs.replace(chemical_formula, '')
            
        # Clean up any remaining artifacts
        technical_specs = re.sub(r'\s+', ' ', technical_specs)  # Replace multiple spaces with single space
        technical_specs = re.sub(r'[,;.]\s*[,;.]', '.', technical_specs)  # Clean up multiple punctuation
        technical_specs = technical_specs.strip(' .,;')  # Remove leading/trailing punctuation and spaces
        
        # Additional cleaning patterns
        technical_specs = re.sub(r'(?:арт\.|артикул|код|model|модель)[\s:.]*[\w\-/\\]+', '', technical_specs, flags=re.IGNORECASE)
        technical_specs = re.sub(r'(?:к-ть|кількість|qty|quantity)\s*[-:=]?\s*\d+', '', technical_specs, flags=re.IGNORECASE)
        technical_specs = re.sub(r'(?:вес|вага|weight)\s*[-:=]?\s*\d+(?:\.\d+)?\s*(?:кг|kg|г|гр|g|мг|mg)', '', technical_specs, flags=re.IGNORECASE)
        technical_specs = re.sub(r'x\s*\d+(?:\s|$)', '', technical_specs)
        
        # If after cleaning nothing meaningful remains, set to None
        technical_specs = technical_specs if technical_specs.strip() else None

    return {
        "Product_Description": product_description,
        "Model_Article": model_article,
        "Quantity": quantity,
        "Weight": weight,
        "Packaging": packaging,
        "Technical_Specs": technical_specs,
        "Chemical_Formula": chemical_formula,
        "Brand": brand,
        "Manufacturer": manufacturer,
        "Country": country
    }    




def parse_row(row):
    """
    Parse a row with multiple products and ensure global attributes are applied to all products.
    """
    # Extract global attributes first
    global_attributes = extract_global_attributes(row)
    
    # Get main description and product sections
    main_description, product_sections = split_products(row)
    
    products = []
    for section in product_sections:
        product_data = parse_individual_product(section, main_description)
        
        # Apply global attributes
        product_data["Manufacturer"] = global_attributes["Manufacturer"]
        product_data["Brand"] = global_attributes["Brand"]
        product_data["Country"] = global_attributes["Country"]
        
        products.append(product_data)
    
    # If no products were found, create at least one entry with the main description
    if not products and main_description:
        product_data = {
            "Product_Description": main_description,
            "Model_Article": "Unknown",
            "Quantity": None,
            "Weight": None,
            "Packaging": None,
            "Technical_Specs": None,
            "Chemical_Formula": None,
            "Brand": global_attributes["Brand"],
            "Manufacturer": global_attributes["Manufacturer"],
            "Country": global_attributes["Country"]
        }
        products.append(product_data)

    return products


# Read the CSV file
# Replace the reading and processing part with this:

try:
    print("Starting to read file...")
    
    # Read the file line by line
    with open('D:/outputonly.csv', 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    print(f"Successfully loaded {len(lines)} lines from file.")
    
except Exception as e:
    print(f"Error reading file: {e}")
    print("Current working directory:", os.getcwd())
    exit()

# Parse all lines
parsed_data = []
total_lines = len(lines)

print(f"\nStarting to process {total_lines} lines...")

for index, line in enumerate(lines):
    print(f"\nProcessing line {index + 1}/{total_lines}")
    try:
        # Clean the line
        text = line.strip()
        
        # Skip empty lines
        if not text:
            print("Skipping empty line")
            continue
            
        print(f"Text length: {len(text)}")
        print(f"First 100 characters: {text[:100]}...")
        
        # Parse the line
        print("Starting to parse...")
        parsed_products = parse_row(text)
        print(f"Found {len(parsed_products)} products in this line")
        parsed_data.extend(parsed_products)
        
    except Exception as e:
        print(f"Error processing line {index + 1}: {str(e)}")
        print(f"Problematic text: {text[:200]}...")
        continue

print("\nAll lines processed")

# Convert to DataFrame for structured output
print("Converting to DataFrame...")
df = pd.DataFrame(parsed_data)

# Save to CSV
output_file = "D:/parsed_products.csv"
print(f"Saving to {output_file}...")
df.to_csv(output_file, index=False, encoding='utf-8')

print(f"\nParsing completed. Processed {total_lines} lines.")
print(f"Generated {len(parsed_data)} product entries.")
print(f"Output saved to '{output_file}'.")
print("\nFirst few rows of the output:")
print(df.head())