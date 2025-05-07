#!/bin/bash

# Script to convert all text files from CRLF to LF line endings

# Make sure dos2unix is installed
if ! command -v dos2unix &> /dev/null; then
    echo "dos2unix is not installed. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew install dos2unix
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        sudo apt-get update && sudo apt-get install -y dos2unix
    else
        echo "Unsupported OS. Please install dos2unix manually."
        exit 1
    fi
fi

echo "Converting files to LF line endings..."

# Convert shell scripts
find . -name "*.sh" -type f -exec dos2unix {} \;
echo "Converted shell scripts"

# Convert Python files
find . -name "*.py" -type f -exec dos2unix {} \;
echo "Converted Python files"

# Convert JavaScript files
find . -name "*.js" -type f -exec dos2unix {} \;
echo "Converted JavaScript files"

# Convert JSON files
find . -name "*.json" -type f -exec dos2unix {} \;
echo "Converted JSON files"

# Convert Markdown files
find . -name "*.md" -type f -exec dos2unix {} \;
echo "Converted Markdown files"

# Convert YAML files
find . -name "*.yml" -type f -exec dos2unix {} \;
find . -name "*.yaml" -type f -exec dos2unix {} \;
echo "Converted YAML files"

# Convert Docker files
find . -name "Dockerfile*" -type f -exec dos2unix {} \;
echo "Converted Docker files"

# Convert .env files
find . -name ".env*" -type f -exec dos2unix {} \;
echo "Converted .env files"

# Convert other common text files
find . -name "*.txt" -type f -exec dos2unix {} \;
find . -name "*.csv" -type f -exec dos2unix {} \;
find . -name "*.html" -type f -exec dos2unix {} \;
find . -name "*.css" -type f -exec dos2unix {} \;
echo "Converted other text files"

echo "Conversion complete!"
