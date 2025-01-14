import pandas as pd
import os

# Define the list of HSN code prefixes to exclude
excluded_prefixes = [
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "16", "24", "36", "37", "41", "42", "43",
    "44", "45", "46", "47", "48", "49", "50", "51", "52", "53", "54", "55", "56", "57", "58", "59", "60", "61", "62", "63",
    "64", "65", "66", "67", "71", "72", "73", "74", "75", "76", "77", "78", "79", "80", "81", "82", "83", "86", "87", "88", "89", "93", "94", "95", "96", "97",
    "3915", "3916", "3917", "3918", "3919", "3920", "3921", "3922", "3923", "3924", "3925", "3926",
    "1401", "2504", "2512", "2513", "2514", "2516", "2524", "2525", "2526", "2529", "2701", "2702", "2703", "2704", "2705", "2706", "2708", "2713", "2714", "2715", "2716",
    "3810", "3813", "3818", "3819", "3920", "4010", "4011", "4012", "4013", "4206", "5006",
    "68", "84", "85", "91", "92", "9001", "9003", "9004", "9005", "9006", "9007", "9008", "9009", "9010", "901310", "901320", "901380", "9014", "9015", "9016", "9017", "9019", "9020", "9021", "9023",
    "1806", "19", "20", "210310", "210320", "210330", "2104", "2105", "2106", "2202", "2203", "2204", "2205", "2206", "2208", "2209", "23", "2505", "2506", "2515", "2517", "2518", "2523", "2530", "26", "2709", "2710", "2711",
    "2844", "31", "6904", "6905", "6906", "6910", "6911", "6912", "6913", "7009", "7010", "7013", "7015", "7016", "7019"
]

# Function to check if HSN code starts with any of the excluded prefixes
def is_excluded(hsn_code):
    for prefix in excluded_prefixes:
        if str(hsn_code).startswith(prefix):
            return True
    return False

# Split a DataFrame into chunks to ensure each file is < 200 MB
def split_dataframe(df, chunk_size=200):
    chunk_rows = chunk_size * 1024 * 1024 // (len(df.columns) * 8)  # Approximate rows per chunk
    return [df.iloc[i:i + chunk_rows] for i in range(0, len(df), chunk_rows)]

# Input and output directories
input_directory = r"C:\Users\Jamal\Downloads\Telegram Desktop\clean-all-inesen"
output_directory = r"C:\Users\Jamal\Downloads\Telegram Desktop\clean-all-inesen\done"

# Ensure the output directory exists
os.makedirs(output_directory, exist_ok=True)

# Process each file in the directory
for file_name in os.listdir(input_directory):
    if file_name.endswith((".xls", ".xlsx", ".xlsb")):
        file_path = os.path.join(input_directory, file_name)
        print(f"Processing file: {file_name}")
        
        try:
            # Choose the appropriate engine for reading the file
            if file_name.endswith(".xlsb"):
                df = pd.read_excel(file_path, engine="pyxlsb")
            else:
                df = pd.read_excel(file_path, engine="openpyxl")
            
            # Filter rows based on HSN codes
            if 'HSN_Code' in df.columns and 'Product_description' in df.columns:
                df['HSN_Code'] = df['HSN_Code'].astype(str)
                filtered_df = df[~df['HSN_Code'].apply(is_excluded)][['Product_description', 'HSN_Code']]
                
                total_exported_rows = 0  # Counter for rows exported
                
                # Split and save the filtered data
                chunks = split_dataframe(filtered_df)
                for i, chunk in enumerate(chunks):
                    output_file_name = f"filtered_{os.path.splitext(file_name)[0]}_part_{i + 1}.xlsx"
                    output_file_path = os.path.join(output_directory, output_file_name)
                    chunk.to_excel(output_file_path, index=False)
                    print(f"  Saved part {i + 1} with {len(chunk)} rows to: {output_file_path}")
                    total_exported_rows += len(chunk)
                
                print(f"Finished processing {file_name}. Total rows exported: {total_exported_rows}")
            else:
                print(f"Columns 'HSN_Code' or 'Product_description' not found in {file_name}")
        except Exception as e:
            print(f"Error processing file {file_name}: {e}")
