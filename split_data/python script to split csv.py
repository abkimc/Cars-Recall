import pandas as pd
import os

# 1. CONFIGURATION
# This tells Python to save the output in your Downloads folder specifically
output_folder = r"OUTPUT" 

# input file
input_file = r"FILE LOCATION"
plate_column = 'MISPAR_RECHEV'

# Create folder if it doesn't exist
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# 2. LOAD AND CLEAN
print("Loading large CSV...")



# cols_to_keep = [
#     'MISPAR_RECHEV', 
#     'SUG_RECALL',     # Recall Type
#     'SUG_TAKALA',     # Fault Type
#     'TEUR_TAKALA',    # Fault Description
#     'TAARICH_PTICHA'  # Date
# ]

# sep='|' (pipe separator)
# added encoding (Hebrew files often need 'cp1255' or 'utf-8')
try:
    df = pd.read_csv(input_file, sep='|',dtype={plate_column: str}, encoding='utf-8') #  usecols=cols_to_keep, dtype={plate_column: str}, encoding='utf-8')
except UnicodeDecodeError:
    # If UTF-8 fails, try the standard Windows Hebrew encoding
    print("UTF-8 failed, trying Windows-1255 encoding...")
    df = pd.read_csv(input_file, sep='|', dtype={plate_column: str}, encoding='cp1255')  # usecols=cols_to_keep, dtype={plate_column: str}, encoding='cp1255')

# Ensure plate numbers are strings and have no whitespace
df[plate_column] = df[plate_column].astype(str).str.strip()

# 3. SPLIT LOGIC
print("Splitting files...")

for digit in range(10):
    subset = df[df[plate_column].str[-1] == str(digit)]
    
    filename = f"{output_folder}/data_{digit}.csv"
    # We save as standard comma-separated CSV for the website to read easily
    subset.to_csv(filename, index=False, encoding='utf-8')
    print(f"Created {filename} with {len(subset)} records")

print("Done! Upload the 'split_data' folder to GitHub.")
