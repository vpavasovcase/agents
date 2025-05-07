#!/bin/bash

# Script to convert all text files from CRLF to LF line endings using tr command

echo "Converting files to LF line endings..."

# Function to convert a file from CRLF to LF
convert_file() {
  if [ -f "$1" ]; then
    echo "Converting $1"
    # Create a temporary file
    tmp_file=$(mktemp)
    # Convert CRLF to LF
    tr -d '\r' < "$1" > "$tmp_file"
    # Replace the original file with the converted one
    mv "$tmp_file" "$1"
  fi
}

# Convert shell scripts
find . -name "*.sh" -type f | while read file; do
  convert_file "$file"
done
echo "Converted shell scripts"

# Convert Python files
find . -name "*.py" -type f | while read file; do
  convert_file "$file"
done
echo "Converted Python files"

# Convert JavaScript files
find . -name "*.js" -type f | while read file; do
  convert_file "$file"
done
echo "Converted JavaScript files"

# Convert JSON files
find . -name "*.json" -type f | while read file; do
  convert_file "$file"
done
echo "Converted JSON files"

# Convert Markdown files
find . -name "*.md" -type f | while read file; do
  convert_file "$file"
done
echo "Converted Markdown files"

# Convert YAML files
find . -name "*.yml" -type f | while read file; do
  convert_file "$file"
done
find . -name "*.yaml" -type f | while read file; do
  convert_file "$file"
done
echo "Converted YAML files"

# Convert Docker files
find . -name "Dockerfile*" -type f | while read file; do
  convert_file "$file"
done
echo "Converted Docker files"

# Convert .env files
find . -name ".env*" -type f | while read file; do
  convert_file "$file"
done
echo "Converted .env files"

# Convert other common text files
find . -name "*.txt" -type f | while read file; do
  convert_file "$file"
done
find . -name "*.csv" -type f | while read file; do
  convert_file "$file"
done
find . -name "*.html" -type f | while read file; do
  convert_file "$file"
done
find . -name "*.css" -type f | while read file; do
  convert_file "$file"
done
echo "Converted other text files"

echo "Conversion complete!"
